import hashlib

import pytest

import tsv_merge

BOM = b"\xef\xbb\xbf"


@pytest.fixture
def run(tmp_path):
    """Write base/extra bytes, run the CLI, return (exit_code, output_bytes)."""

    def _run(base, extra, *args, output="out.tsv"):
        base_path = tmp_path / "base.tsv"
        extra_path = tmp_path / "extra.tsv"
        out_path = tmp_path / output
        base_path.write_bytes(base)
        extra_path.write_bytes(extra)
        code = tsv_merge.main([str(base_path), str(extra_path), "-o", str(out_path), *args])
        return code, (out_path.read_bytes() if out_path.exists() else None)

    return _run


def test_adds_only_rows_with_new_keys(run):
    code, out = run(b"1\ta\n2\tb\n", b"2\tB\n3\tc\n", "-k", "1")
    assert code == 0
    assert out == b"1\ta\n2\tb\n3\tc\n"


def test_multi_column_key(run):
    code, out = run(b"1\tA\tx\n1\tB\ty\n", b"1\tA\tz\n1\tC\tw\n2\tA\tq\n", "-k", "1,2")
    assert code == 0
    assert out == b"1\tA\tx\n1\tB\ty\n1\tC\tw\n2\tA\tq\n"


def test_non_first_key_column(run):
    code, out = run(b"a\t1\n", b"b\t1\nc\t2\n", "-k", "2")
    assert code == 0
    assert out == b"a\t1\nc\t2\n"


def test_duplicates_in_extra_are_all_added_by_default(run):
    code, out = run(b"1\ta\n", b"2\tb\n2\tc\n", "-k", "1")
    assert code == 0
    assert out == b"1\ta\n2\tb\n2\tc\n"


def test_skip_duplicates_adds_first_row_only(run):
    code, out = run(b"1\ta\n", b"2\tb\n2\tc\n", "-k", "1", "--skip-duplicates")
    assert code == 0
    assert out == b"1\ta\n2\tb\n"


def test_duplicates_in_base_are_kept(run):
    code, out = run(b"1\ta\n1\tb\n", b"1\tc\n", "-k", "1")
    assert code == 0
    assert out == b"1\ta\n1\tb\n"


def test_match_is_exact(run):
    code, out = run(b"A\t1\n", b"a\t2\n A\t3\n", "-k", "1")
    assert code == 0
    assert out == b"A\t1\na\t2\n A\t3\n"


def test_header_kept_from_base_and_skipped_from_extra(run):
    code, out = run(b"id\tname\n1\ta\n", b"id\tname\n2\tb\n", "-k", "1", "--header")
    assert code == 0
    assert out == b"id\tname\n1\ta\n2\tb\n"


def test_without_header_flag_first_row_is_data(run):
    code, out = run(b"id\tname\n", b"id\tother\nx\ty\n", "-k", "1")
    assert code == 0
    assert out == b"id\tname\nx\ty\n"


def test_header_mismatch_is_error(run):
    code, out = run(b"id\tname\n", b"id\tother\n", "-k", "1", "--header")
    assert code == 1
    assert out is None


def test_quotes_are_plain_text_by_default(run):
    base = b'1\tSymbol "Pilar\n2\tx"y\n'
    extra = b'1\tdup\n3\t"open\n4\tz"\n'
    code, out = run(base, extra, "-k", "1")
    assert code == 0
    assert out == base + b'3\t"open\n4\tz"\n'


def test_keys_keep_quotes_by_default(run):
    code, out = run(b'"1"\ta\n', b"1\tb\n", "-k", "1")
    assert code == 0
    assert out == b'"1"\ta\n1\tb\n'


def test_quoted_fields_with_tabs_newlines_and_quotes(run):
    base = b'1\t"a\tb"\n2\t"multi\nline"\n'
    extra = b'2\tdup\n3\t"x ""q"""\n4\t"new\nline"\n'
    code, out = run(base, extra, "-k", "1", "--quoted")
    assert code == 0
    assert out == base + b'3\t"x ""q"""\n4\t"new\nline"\n'


def test_quoted_key_matches_unquoted_value(run):
    code, out = run(b'"1"\ta\n', b"1\tb\n", "-k", "1", "--quoted")
    assert code == 0
    assert out == b'"1"\ta\n'


def test_crlf_bom_and_utf8_preserved(run):
    base = BOM + "id\tname\r\n1\tzażółć\r\n".encode()
    extra = BOM + "id\tname\r\n2\tgęś\r\n".encode()
    code, out = run(base, extra, "-k", "1", "--header")
    assert code == 0
    assert out == base + "2\tgęś\r\n".encode()


def test_missing_final_newline_in_base(run):
    code, out = run(b"1\ta\r\n2\tb", b"3\tc\r\n", "-k", "1")
    assert code == 0
    assert out == b"1\ta\r\n2\tb\r\n3\tc\r\n"


def test_other_encoding(run):
    base = "ś\tżółw\n".encode("cp1250")
    extra = "ś\tdup\nł\tgęś\n".encode("cp1250")
    code, out = run(base, extra, "-k", "1", "--encoding", "cp1250")
    assert code == 0
    assert out == base + "ł\tgęś\n".encode("cp1250")


def test_invalid_bytes_round_trip(run):
    code, out = run(b"1\t\xff\n", b"2\t\xfe\n", "-k", "1")
    assert code == 0
    assert out == b"1\t\xff\n2\t\xfe\n"


def test_empty_extra(run):
    code, out = run(b"1\ta\n", b"", "-k", "1")
    assert code == 0
    assert out == b"1\ta\n"


def test_empty_base(run):
    code, out = run(b"", b"1\ta\n", "-k", "1")
    assert code == 0
    assert out == b"1\ta\n"


def test_column_count_mismatch_is_error(run):
    code, out = run(b"1\ta\n", b"2\tb\tc\n", "-k", "1")
    assert code == 1
    assert out is None


def test_key_column_out_of_range_is_error(run):
    code, out = run(b"1\ta\n", b"2\tb\n", "-k", "3")
    assert code == 1
    assert out is None


def test_unterminated_quote_is_error(run):
    code, out = run(b"1\ta\n", b'2\t"open\n', "-k", "1", "--quoted")
    assert code == 1
    assert out is None


def test_inputs_are_not_modified(tmp_path):
    base = tmp_path / "base.tsv"
    extra = tmp_path / "extra.tsv"
    base.write_bytes(b"1\ta\n")
    extra.write_bytes(b"2\tb\n")
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (base, extra)]
    assert tsv_merge.main([str(base), str(extra), "-k", "1", "-o", str(tmp_path / "out.tsv")]) == 0
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (base, extra)] == before


def test_existing_output_requires_force(run, tmp_path):
    (tmp_path / "out.tsv").write_bytes(b"old")
    with pytest.raises(SystemExit):
        run(b"1\ta\n", b"2\tb\n", "-k", "1")
    assert (tmp_path / "out.tsv").read_bytes() == b"old"
    code, out = run(b"1\ta\n", b"2\tb\n", "-k", "1", "--force")
    assert code == 0
    assert out == b"1\ta\n2\tb\n"


def test_output_cannot_be_an_input(run):
    with pytest.raises(SystemExit):
        run(b"1\ta\n", b"2\tb\n", "-k", "1", "--force", output="base.tsv")


@pytest.mark.parametrize("key", ["0", "a", "1,x", ""])
def test_invalid_key_argument(run, key):
    with pytest.raises(SystemExit):
        run(b"1\ta\n", b"2\tb\n", "-k", key)
