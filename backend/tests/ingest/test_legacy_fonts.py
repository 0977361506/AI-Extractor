import pytest

from idp.ingest.legacy_fonts import Charset, convert_legacy, detect_charset, tcvn3_to_unicode, vni_to_unicode


@pytest.mark.parametrize(
    ("tcvn3", "unicode"),
    [
        ("Ng©n hµng", "Ngân hàng"),
        ("B¸o c¸o tµi chÝnh", "Báo cáo tài chính"),
        ("§¬n vÞ tÝnh", "Đơn vị tính"),
        ("Hîp ®ång", "Hợp đồng"),
        ("ViÖt Nam", "Việt Nam"),
    ],
)
def test_tcvn3(tcvn3, unicode):
    assert tcvn3_to_unicode(tcvn3) == unicode


def test_tcvn3_uppercase_font_variant():
    assert tcvn3_to_unicode("b¸o c¸o", uppercase=True) == "BÁO CÁO"


@pytest.mark.parametrize(
    ("vni", "unicode"),
    [
        ("Vieät Nam", "Việt Nam"),
        ("Ngaân haøng", "Ngân hàng"),
        ("Coâng ty coå phaàn", "Công ty cổ phần"),
        ("Ñoàng", "Đồng"),
        ("Hôïp ñoàng", "Hợp đồng"),
        ("thöïc hieän", "thực hiện"),
        ("Baùo caùo taøi chính", "Báo cáo tài chính"),
    ],
)
def test_vni(vni, unicode):
    assert vni_to_unicode(vni) == unicode


def test_detect_charset():
    assert detect_charset("Báo cáo tài chính năm 2025") == Charset.UNICODE
    assert detect_charset("B¸o c¸o tµi chÝnh n¨m 2025 cña C«ng ty") == Charset.TCVN3
    assert detect_charset("Baùo caùo taøi chính naêm 2025 cuûa Coâng ty") == Charset.VNI
    assert detect_charset("Annual report 2025") == Charset.UNICODE


def test_convert_legacy_by_font_name_and_autodetect():
    assert convert_legacy("Ng©n hµng", font=".VnTime") == "Ngân hàng"
    assert convert_legacy("Ngaân haøng", font="VNI-Times") == "Ngân hàng"
    assert convert_legacy("B¸o c¸o tµi chÝnh n¨m 2025 cña C«ng ty") == "Báo cáo tài chính năm 2025 của Công ty"
    assert convert_legacy("Báo cáo") == "Báo cáo"
