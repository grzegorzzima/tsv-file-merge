# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```
python -m pytest                                              # all tests (pytest config in pyproject.toml adds src/ to the path)
python -m pytest tests/test_tsv_merge.py::test_multi_column_key   # single test
python src/tsv_merge.py BASE EXTRA -k 1,3 --header -o OUT     # run the tool
pip install -e ".[test]"                                      # installs the `tsv-merge` console command + pytest
```

There is no linter or build step. Runtime has no dependencies; keep it standard-library only and compatible with Python 3.9 (CI runs 3.9 and 3.13 on Linux/Windows/macOS via `.github/workflows/tests.yml`).

## Architecture

Single module `src/tsv_merge.py` (installed as a top-level module, not a package). Merge semantics: every base row is kept; an extra row is appended only if its key tuple (1-based columns from `-k`) is not in the base. Duplicate keys within EXTRA are all added unless `--skip-duplicates`.

The core design constraint is **byte-exact output**: rows are never re-serialized. Keep this when changing anything:

- Files are opened as text with `newline=""` (preserves `\r\n`/`\n`) and `errors="surrogateescape"` (round-trips bytes invalid in `--encoding`). The same encoding is used for output.
- By default one line = one record, fields are split on `\t`, and `"` is literal text (real data contains values like `Symbol "Pilar` with unbalanced quotes). With `--quoted`, `read_records` groups physical lines into logical records by counting `"` until balanced and `csv.reader` parses the fields, so quoted fields may contain tabs/newlines. Either way, the raw record is written as-is; parsing only extracts fields for the key.
- BOM: the base file's BOM is copied through; the extra file's BOM is stripped. If the base lacks a trailing newline, the base's line ending is inserted before appended rows.
- Only base keys are held in memory; both files are streamed.

Validation raises `MergeError`; `main()` catches it, deletes the partial output and returns exit code 1. Argument problems (bad `-k`, existing output without `--force`, output equal to an input) go through `argparse` and raise `SystemExit` — tests rely on this distinction. Output is opened with mode `"x"` so inputs can never be overwritten.

## Tests

`tests/test_tsv_merge.py` calls `tsv_merge.main([...])` with byte fixtures written to `tmp_path` and asserts on exact output bytes. `.gitattributes` marks `*.tsv` as binary so git never rewrites line endings of TSV fixtures.
