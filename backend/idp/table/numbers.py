"""Vietnamese number formats (``15.250.000``, ``(1.290)``, ``2,5``) and OCR repair for numeric cells."""

from __future__ import annotations

import re

_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+(?:,\d+)?$")
_PLAIN = re.compile(r"^\d+(?:,\d+)?$")
_CONFUSABLE = {"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1"}


def parse_vn_number(text: str) -> float | None:
    s = text.strip().replace(" ", "")
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    elif s[0] in "-−–" and len(s) > 1:
        negative, s = True, s[1:]
    s = s.rstrip("%")
    if not (_THOUSANDS.match(s) or _PLAIN.match(s)):
        return None
    value = float(s.replace(".", "").replace(",", "."))
    return -value if negative else value


def fix_numeric_ocr(text: str) -> str:
    """Repair typical OCR confusions inside numbers. Text containing real words is returned unchanged."""
    s = text.strip()
    alnum = [c for c in s if c.isalnum()]
    if not alnum or not any(c.isdigit() for c in alnum):
        return text
    if any(not c.isdigit() and c not in _CONFUSABLE for c in alnum):
        return text
    s = "".join(_CONFUSABLE.get(c, c) for c in s)
    s = re.sub(r"(?<=\d)[:;](?=\d{3})", ".", s)
    core = s.strip("()-−– ")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", core):
        s = s.replace(",", ".")
    return s


def looks_numeric(text: str) -> bool:
    return parse_vn_number(fix_numeric_ocr(text)) is not None
