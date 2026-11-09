#!/usr/bin/env python3
"""Merge two TSV files: keep every row of the base file and append the rows
of the additional file whose key (one or more columns) is not present yet.

Rows are written byte-for-byte as they appear in the inputs (quotes, line
endings and encoding are preserved). Input files are only ever read.

By default every line is one row and double quotes are ordinary characters.
With --quoted, CSV-style quoting is honoured: quoted fields may contain tabs
and line breaks, and surrounding quotes are ignored when comparing keys.

Examples:
    python tsv_merge.py base.tsv extra.tsv -k 1 -o merged.tsv
    python tsv_merge.py base.tsv extra.tsv -k 1,3 --header -o merged.tsv
    python tsv_merge.py base.tsv extra.tsv -k 1 --quoted -o merged.tsv
"""

import argparse
import csv
import os
import sys

BOM = "﻿"


class MergeError(Exception):
    pass


def read_records(f, quoting=False):
    """Yield (raw_record, line_no) from a text file opened with newline=''.

    With quoting, a record may span several physical lines when a quoted field
    contains a line break, so lines are joined until the quote count is
    balanced. Without quoting, every line is one record.
    """
    if not quoting:
        for line_no, line in enumerate(f, 1):
            yield line, line_no
        return
    buf = []
    quotes = 0
    start = 1
    line_no = 0
    for line in f:
        line_no += 1
        buf.append(line)
        quotes += line.count('"')
        if quotes % 2 == 0:
            yield "".join(buf), start
            buf, quotes, start = [], 0, line_no + 1
    if buf:
        raise MergeError(f"unterminated quoted field starting at line {start}")


def strip_eol(record):
    if record.endswith("\r\n"):
        return record[:-2], "\r\n"
    if record.endswith(("\n", "\r")):
        return record[:-1], record[-1]
    return record, ""


def parse_fields(body, quoting=False):
    if not quoting:
        return body.split("\t") if body else []
    return next(csv.reader([body], delimiter="\t", quotechar='"'), [])


def make_key(fields, key_cols, path, line_no):
    try:
        return tuple(fields[i] for i in key_cols)
    except IndexError:
        raise MergeError(
            f"{path}:{line_no}: row has {len(fields)} column(s), "
            f"key needs column {max(key_cols) + 1}"
        ) from None


def parse_key_columns(text):
    try:
        cols = [int(part) for part in text.split(",") if part.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid column list: {text!r}") from None
    if not cols or any(c < 1 for c in cols):
        raise argparse.ArgumentTypeError("columns are 1-based positive numbers, e.g. 1 or 1,3")
    return [c - 1 for c in cols]


def merge(base_path, extra_path, out_path, key_cols, header, encoding, skip_duplicates, quoting=False):
    stats = {"base": 0, "extra": 0, "added": 0, "skipped": 0}
    keys = set()
    column_count = None
    eol = "\n"
    # surrogateescape round-trips any byte that is invalid in the chosen encoding.
    open_args = {"encoding": encoding, "errors": "surrogateescape", "newline": ""}

    with open(out_path, "x", **open_args) as out:
        last_had_eol = True

        with open(base_path, "r", **open_args) as f:
            for i, (record, line_no) in enumerate(read_records(f, quoting)):
                body, rec_eol = strip_eol(record)
                if i == 0:
                    eol = rec_eol or eol
                fields = parse_fields(body.lstrip(BOM) if i == 0 else body, quoting)
                if column_count is None:
                    column_count = len(fields)
                if i == 0 and header:
                    base_header = fields
                else:
                    keys.add(make_key(fields, key_cols, base_path, line_no))
                    stats["base"] += 1
                out.write(record)
                last_had_eol = bool(rec_eol)

        if column_count is not None and max(key_cols) >= column_count:
            raise MergeError(f"{base_path}: key column {max(key_cols) + 1} exceeds {column_count} column(s)")

        with open(extra_path, "r", **open_args) as f:
            for i, (record, line_no) in enumerate(read_records(f, quoting)):
                if i == 0:
                    record = record.lstrip(BOM)
                body, rec_eol = strip_eol(record)
                fields = parse_fields(body, quoting)
                if i == 0 and header:
                    if column_count is not None and fields != base_header:
                        raise MergeError(f"header of {extra_path} differs from header of {base_path}")
                    continue
                if column_count is not None and len(fields) != column_count:
                    raise MergeError(
                        f"{extra_path}:{line_no}: expected {column_count} column(s), got {len(fields)}"
                    )
                stats["extra"] += 1
                key = make_key(fields, key_cols, extra_path, line_no)
                if key in keys:
                    stats["skipped"] += 1
                    continue
                if skip_duplicates:
                    keys.add(key)
                if not last_had_eol:
                    out.write(eol)
                out.write(record)
                last_had_eol = bool(rec_eol)
                stats["added"] += 1

    return stats


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Append rows from EXTRA to BASE when their key columns are not already in BASE."
    )
    p.add_argument("base", help="base TSV file (all of its rows are kept)")
    p.add_argument("extra", help="additional TSV file (only rows with new keys are added)")
    p.add_argument("-k", "--key", required=True, type=parse_key_columns,
                   help="1-based key column(s), comma separated, e.g. 1 or 1,3")
    p.add_argument("-o", "--output", required=True, help="output file (must not exist unless --force)")
    p.add_argument("--header", action="store_true",
                   help="files have a header row; the base header is kept, the extra header must match and is skipped")
    p.add_argument("--encoding", default="utf-8",
                   help="encoding of both input files, also used for output (default: utf-8)")
    p.add_argument("--skip-duplicates", action="store_true",
                   help="when a new key repeats within EXTRA, add only its first row (default: add every row)")
    p.add_argument("--quoted", action="store_true",
                   help="honour CSV-style quoting: quoted fields may span lines and quotes are "
                        "ignored in key comparison (default: every line is one row, quotes are plain text)")
    p.add_argument("-f", "--force", action="store_true", help="overwrite the output file if it exists")
    args = p.parse_args(argv)

    for path in (args.base, args.extra):
        if not os.path.isfile(path):
            p.error(f"file not found: {path}")
    if os.path.exists(args.output):
        if any(os.path.samefile(args.output, path) for path in (args.base, args.extra)):
            p.error("output file must differ from the input files")
        if not args.force:
            p.error(f"output file already exists: {args.output} (use --force to overwrite)")
        os.remove(args.output)

    try:
        stats = merge(args.base, args.extra, args.output, args.key, args.header,
                      args.encoding, args.skip_duplicates, args.quoted)
    except (MergeError, LookupError) as e:
        if os.path.exists(args.output):
            os.remove(args.output)
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(
        f"base rows: {stats['base']}, extra rows: {stats['extra']}, "
        f"added: {stats['added']}, skipped: {stats['skipped']} -> {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
