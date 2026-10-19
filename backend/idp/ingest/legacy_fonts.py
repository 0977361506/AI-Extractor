"""Legacy Vietnamese encodings (TCVN3/ABC ``.VnTime``, VNI ``VNI-Times``) → Unicode NFC."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class Charset(StrEnum):
    UNICODE = "UNICODE_NFC"
    TCVN3 = "TCVN3"
    VNI = "VNI"


# TCVN3 (TCVN 5712:1993 VN3): one byte per precomposed lowercase letter; uppercase via the ".VnTimeH" font.
_TCVN3 = {
    "¸": "á", "µ": "à", "¶": "ả", "·": "ã", "¹": "ạ",
    "¨": "ă", "¾": "ắ", "»": "ằ", "¼": "ẳ", "½": "ẵ", "Æ": "ặ",
    "©": "â", "Ê": "ấ", "Ç": "ầ", "È": "ẩ", "É": "ẫ", "Ë": "ậ",
    "®": "đ",
    "Ð": "é", "Ì": "è", "Î": "ẻ", "Ï": "ẽ", "Ñ": "ẹ",
    "ª": "ê", "Õ": "ế", "Ò": "ề", "Ó": "ể", "Ô": "ễ", "Ö": "ệ",
    "Ý": "í", "×": "ì", "Ø": "ỉ", "Ü": "ĩ", "Þ": "ị",
    "ã": "ó", "ß": "ò", "á": "ỏ", "â": "õ", "ä": "ọ",
    "«": "ô", "è": "ố", "å": "ồ", "æ": "ổ", "ç": "ỗ", "é": "ộ",
    "¬": "ơ", "í": "ớ", "ê": "ờ", "ë": "ở", "ì": "ỡ", "î": "ợ",
    "ó": "ú", "ï": "ù", "ñ": "ủ", "ò": "ũ", "ô": "ụ",
    "\xad": "ư", "ø": "ứ", "õ": "ừ", "ö": "ử", "÷": "ữ", "ù": "ự",
    "ý": "ý", "ú": "ỳ", "û": "ỷ", "ü": "ỹ", "þ": "ỵ",
    "¡": "Ă", "¢": "Â", "§": "Đ", "£": "Ê", "¤": "Ô", "¥": "Ơ", "¦": "Ư",
}
_TCVN3_STRONG = set("¸µ¶·¹¨¾»¼½©®ª«¬\xad×÷§¡¢£¤¥¦Þ")

# VNI-Windows: base vowel followed by a mark character.
_TONES = {"ù": "́", "ø": "̀", "û": "̉", "õ": "̃", "ï": "̣"}
_CIRC = {"â": "", "á": "́", "à": "̀", "å": "̉", "ã": "̃", "ä": "̣"}
_BREVE = {"ê": "", "é": "́", "è": "̀", "ú": "̉", "ü": "̃", "ë": "̣"}


def _build_vni() -> dict[str, str]:
    table: dict[str, str] = {}

    def add(seq: str, base: str, *marks: str) -> None:
        lo = unicodedata.normalize("NFC", base + "".join(marks))
        table[seq] = lo
        table[seq.upper()] = lo.upper()

    for v in "aeouy":
        for k, m in _TONES.items():
            add(v + k, v, m)
    for v in "aeo":
        for k, m in _CIRC.items():
            add(v + k, v, "̂", m)
    for k, m in _BREVE.items():
        add("a" + k, "a", "̆", m)
    for k, m in _TONES.items():
        add("ô" + k, "o", "̛", m)  # ơ + tone
        add("ö" + k, "u", "̛", m)  # ư + tone
    return table


_VNI_PAIRS = _build_vni()
_VNI_SINGLE = {"ô": "ơ", "Ô": "Ơ", "ö": "ư", "Ö": "Ư", "ñ": "đ", "Ñ": "Đ", "æ": "ỉ", "Æ": "Ỉ", "ó": "ĩ", "Ó": "Ĩ", "ò": "ị", "Ò": "Ị"}
_VNI_ALL = {**_VNI_SINGLE, **_VNI_PAIRS}
_VNI_RE = re.compile("|".join(sorted(map(re.escape, _VNI_ALL), key=len, reverse=True)))
_VNI_MARKER_RE = re.compile(r"[aeouyAEOUY][ùøûõïâáàåãäêéèúüëÙØÛÕÏÂÁÀÅÃÄÊÉÈÚÜË]|[ôö][ùøûõï]")


def tcvn3_to_unicode(text: str, uppercase: bool = False) -> str:
    out = "".join(_TCVN3.get(c, c) for c in text)
    out = unicodedata.normalize("NFC", out)
    return out.upper() if uppercase else out


def vni_to_unicode(text: str) -> str:
    # single pass, longest match first: converted output is never re-read as VNI codes
    return unicodedata.normalize("NFC", _VNI_RE.sub(lambda m: _VNI_ALL[m.group(0)], text))


def detect_charset(text: str) -> Charset:
    letters = sum(c.isalpha() for c in text) or 1
    strong = sum(c in _TCVN3_STRONG for c in text)
    if strong >= 2 and strong / letters >= 0.01:
        return Charset.TCVN3
    if len(_VNI_MARKER_RE.findall(text)) >= 2:
        return Charset.VNI
    return Charset.UNICODE


def convert_legacy(text: str, font: str | None = None) -> str:
    name = (font or "").strip().lower()
    if name.startswith(".vn"):
        return tcvn3_to_unicode(text, uppercase=name.endswith("h"))
    if name.startswith("vni"):
        return vni_to_unicode(text)
    charset = detect_charset(text)
    if charset == Charset.TCVN3:
        return tcvn3_to_unicode(text)
    if charset == Charset.VNI:
        return vni_to_unicode(text)
    return unicodedata.normalize("NFC", text)
