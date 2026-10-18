import pytest

from idp.table.numbers import fix_numeric_ocr, looks_numeric, parse_vn_number


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("12.450", 12450),
        ("15.250.000.000", 15250000000),
        ("(1.290)", -1290),
        ("( 7.100 )", -7100),
        ("-320", -320),
        ("2,5", 2.5),
        ("99,5%", 99.5),
        ("0", 0),
        ("120.000.000", 120000000),
        ("802", 802),
        ("1.344", 1344),
    ],
)
def test_parse_vn_number(text, value):
    assert parse_vn_number(text) == pytest.approx(value)


@pytest.mark.parametrize("text", ["", "VI.01", "Gói", "abc", "01/2026", "Quý I", "-"])
def test_non_numbers(text):
    assert parse_vn_number(text) is None


@pytest.mark.parametrize(
    ("raw", "fixed"),
    [
        ("15.O00.00O", "15.000.000"),
        ("1.2l0", "1.210"),
        ("(3OO)", "(300)"),
        ("27:800.000", "27.800.000"),
        ("9.000.000", "9.000.000"),
        ("2,118", "2.118"),
    ],
)
def test_fix_numeric_ocr(raw, fixed):
    assert fix_numeric_ocr(raw) == fixed


def test_fix_numeric_ocr_leaves_words_alone():
    assert fix_numeric_ocr("Gói") == "Gói"
    assert fix_numeric_ocr("VI.01") == "VI.01"


def test_looks_numeric():
    assert looks_numeric("(1.290)")
    assert not looks_numeric("Doanh thu")
