"""Quality metrics: CER for text, TEDS (tree-edit-distance similarity) for table structure + content."""

from __future__ import annotations

import unicodedata

from apted import APTED, Config
from lxml import html as lxml_html
from rapidfuzz.distance import Levenshtein


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def cer(pred: str, ref: str) -> float:
    p, r = normalize_text(pred), normalize_text(ref)
    if not r:
        return 0.0 if not p else 1.0
    return Levenshtein.distance(p, r) / len(r)


class _Node:
    def __init__(self, tag: str, colspan: int = 1, rowspan: int = 1, text: str = ""):
        self.tag, self.colspan, self.rowspan, self.text = tag, colspan, rowspan, text
        self.children: list[_Node] = []


def _tree(html_text: str) -> tuple[_Node, int]:
    root = lxml_html.fromstring(html_text)
    table = root if root.tag == "table" else root.find(".//table")
    count = 0

    def build(el) -> _Node:
        nonlocal count
        count += 1
        if el.tag in ("td", "th"):
            return _Node("td", int(el.get("colspan", 1)), int(el.get("rowspan", 1)), normalize_text(el.text_content()))
        node = _Node(el.tag if el.tag != "th" else "td")
        for child in el:
            if child.tag in ("thead", "tbody"):
                for row in child:
                    node.children.append(build(row))
            elif child.tag in ("tr", "td", "th"):
                node.children.append(build(child))
        return node

    return build(table), count


class _TedsConfig(Config):
    def rename(self, a: _Node, b: _Node) -> float:
        if a.tag != b.tag or a.colspan != b.colspan or a.rowspan != b.rowspan:
            return 1.0
        if a.tag == "td":
            if not a.text and not b.text:
                return 0.0
            return Levenshtein.normalized_distance(a.text, b.text)
        return 0.0

    def children(self, node: _Node):
        return node.children


def teds(pred_html: str, ref_html: str) -> float:
    if not pred_html or not ref_html:
        return 0.0
    a, na = _tree(pred_html)
    b, nb = _tree(ref_html)
    distance = APTED(a, b, _TedsConfig()).compute_edit_distance()
    return 1.0 - distance / max(na, nb, 1)
