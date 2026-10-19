import json

import numpy as np

from idp.core.ast import Element, ElementType, Page, ReviewReason, TableCell
from idp.vlm.client import VlmClient
from idp.vlm.refine import refine_page
from idp.vlm.router import route
from tests.vlm.conftest import FakeGateway, transport

BLANK = np.full((100, 200, 3), 255, np.uint8)


def E(eid, type_, conf=0.95, **kw):
    return Element(element_id=eid, type=type_, reading_order=0, bbox_normalized=(0.1, 0.1, 0.5, 0.2), confidence_score=conf, **kw)


def test_router_selects_low_confidence_failed_tables_and_always_types(settings):
    settings.vlm_threshold = 0.85
    good = E("a", ElementType.PARAGRAPH, 0.95, text="ok")
    low = E("b", ElementType.PARAGRAPH, 0.6, text="mờ")
    hand = E("c", ElementType.HANDWRITTEN_NOTE, 0.9, text="ghi chú")
    table = E("d", ElementType.TABLE, 0.95, cells=[TableCell(row=0, col=0, text="1", check_failed=True)])
    footer = E("e", ElementType.PAGE_FOOTER, 0.5, text="Trang 1")
    picked = [e.element_id for e in route([good, low, hand, table, footer], settings)]
    assert picked == ["b", "c", "d"]


def test_router_respects_budget_lowest_confidence_first(settings):
    settings.max_calls_per_page = 2
    els = [E(str(i), ElementType.PARAGRAPH, 0.3 + i * 0.1, text="x") for i in range(5)]
    assert [e.element_id for e in route(els, settings)] == ["0", "1"]


def _table_chat(body):
    return json.dumps(
        {
            "header_rows": 1,
            "cells": [
                {"row": 0, "col": 0, "rowspan": 1, "colspan": 1, "text": "Chỉ tiêu"},
                {"row": 0, "col": 1, "rowspan": 1, "colspan": 1, "text": "Số tiền"},
                {"row": 1, "col": 0, "rowspan": 1, "colspan": 1, "text": "Tiền"},
                {"row": 1, "col": 1, "rowspan": 1, "colspan": 1, "text": "15.250.000"},
            ],
        }
    )


def test_refine_table_applies_vlm_and_flags_numeric_disagreement(settings):
    settings.structured_output = "json_schema"
    cells = [
        TableCell(row=0, col=0, text="Chỉ tiêu", is_header=True, bbox=(0.1, 0.1, 0.3, 0.15)),
        TableCell(row=0, col=1, text="Số tiền", is_header=True, bbox=(0.3, 0.1, 0.5, 0.15)),
        TableCell(row=1, col=0, text="Tiền", bbox=(0.1, 0.15, 0.3, 0.2)),
        TableCell(row=1, col=1, text="15.260.000", confidence=0.6, bbox=(0.3, 0.15, 0.5, 0.2)),
    ]
    page = Page(page_number=1, width=200, height=100, elements=[E("t", ElementType.TABLE, 0.6, cells=cells)])
    client = VlmClient(settings, transport=transport(FakeGateway(chat=_table_chat)))
    stats = refine_page(page, BLANK, client, settings)
    t = page.elements[0]
    cell = next(c for c in t.cells if (c.row, c.col) == (1, 1))
    assert cell.text == "15.250.000" and cell.alt_text == "15.260.000"
    assert cell.bbox == (0.3, 0.15, 0.5, 0.2)  # geometry kept from the OCR grid
    assert ReviewReason.OCR_VLM_MISMATCH in t.review_reasons
    assert t.extraction_engine.startswith("vlm:")
    assert stats["calls"] == 1


def test_refine_text_and_unavailable_gateway(settings):
    settings.structured_output = "json_schema"
    page = Page(page_number=1, width=200, height=100, elements=[E("n", ElementType.HANDWRITTEN_NOTE, 0.5, text="Đà soát")])
    ok = VlmClient(settings, transport=transport(FakeGateway(chat=lambda b: json.dumps({"text": "Đã soát số liệu", "confidence": 0.93}))))
    refine_page(page, BLANK, ok, settings)
    assert page.elements[0].text == "Đã soát số liệu"

    page2 = Page(page_number=1, width=200, height=100, elements=[E("m", ElementType.HANDWRITTEN_NOTE, 0.5, text="Đà soát")])
    settings.retries = 0
    down = VlmClient(settings, transport=transport(FakeGateway(status=503)))
    refine_page(page2, BLANK, down, settings)
    assert page2.elements[0].text == "Đà soát"
    assert ReviewReason.VLM_UNAVAILABLE in page2.elements[0].review_reasons


def test_refine_figure_to_mermaid_diagram(settings):
    settings.structured_output = "json_schema"
    page = Page(page_number=1, width=200, height=100, elements=[E("f", ElementType.FIGURE, 0.9, text="Bắt đầu\nKết thúc")])
    chat = lambda b: json.dumps({"is_diagram": True, "mermaid": "flowchart TD\n  A[Bắt đầu] --> B[Kết thúc]", "description": "Quy trình"})
    refine_page(page, BLANK, VlmClient(settings, transport=transport(FakeGateway(chat=chat))), settings)
    el = page.elements[0]
    assert el.type == ElementType.DIAGRAM and "flowchart TD" in el.mermaid


def test_refine_form_field_and_signature(settings):
    settings.structured_output = "json_schema"

    def chat(body):
        prompt = body["messages"][-1]["content"][0]["text"]
        if "chữ ký" in prompt.lower():
            return json.dumps({"signer_name": "Trần Thị Thu Hằng"})
        return json.dumps({"label": "Họ và tên", "value": "LÊ HOÀNG MINH"})

    field = E("ff", ElementType.FORM_FIELD, 0.6, label="Họ và tên", value="LÊ HOANG MINH", is_handwritten=True)
    sig = E("sg", ElementType.SIGNATURE, 0.2)
    page = Page(page_number=1, width=200, height=100, elements=[field, sig])
    refine_page(page, BLANK, VlmClient(settings, transport=transport(FakeGateway(chat=chat))), settings)
    assert page.elements[0].value == "LÊ HOÀNG MINH"
    assert page.elements[1].signer_name == "Trần Thị Thu Hằng"
