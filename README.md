# tsv-merge

Merge two TSV files. Every row of the **base** file is kept, and rows from the
**extra** file are appended only when their key (one or more columns) does not
exist in the base file.

- Input files are only read, never modified.
- Rows are copied byte-for-byte: quoting, line endings (LF/CRLF), BOM and
  encoding are preserved.
- Quoted fields may contain tabs, line breaks and `""` escaped quotes.
- Files are streamed; only the base file's keys are held in memory.
- No dependencies beyond Python 3.9+.

## Usage

```
python src/tsv_merge.py BASE EXTRA -k COLUMNS -o OUTPUT [options]
```

| Option | Description |
|---|---|
| `-k`, `--key` | 1-based key column(s), comma separated, e.g. `1` or `1,3` |
| `-o`, `--output` | Output file. Must not exist unless `--force`; can never be an input file |
| `--header` | Files have a header row. The base header is kept; the extra header must match and is skipped |
| `--encoding` | Encoding of both inputs, also used for the output (default `utf-8`) |
| `--skip-duplicates` | When a new key repeats within EXTRA, add only its first row (default: add every row) |
| `-f`, `--force` | Overwrite the output file if it exists |

Optionally install it to get a `tsv-merge` command:

```
pip install .
tsv-merge base.tsv extra.tsv -k 1 -o merged.tsv
```

## Example

`base.tsv`

```
id	name
1	Alice
2	Bob
```

`extra.tsv`

```
id	name
2	Robert
3	Carol
3	Caroline
```

```
python src/tsv_merge.py base.tsv extra.tsv -k 1 --header -o merged.tsv
```

`merged.tsv`

```
id	name
1	Alice
2	Bob
3	Carol
3	Caroline
```

With `--skip-duplicates` the `3	Caroline` row is left out.

## Rules

- Keys are compared exactly (case and whitespace sensitive). Quoting does not
  matter: `"1"` and `1` are the same value.
- All rows must have the same number of columns as the first row of the base
  file; otherwise the merge stops with an error.
- On any error the partially written output file is removed and the exit code
  is `1`.

## Development

```
pip install -e ".[test]"
python -m pytest
```
