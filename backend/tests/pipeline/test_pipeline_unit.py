import numpy as np

from idp.core.ast import Element, ElementType, Page
from idp.pipeline.page import attach_notes, downscale
from idp.viz.overlay import draw_overlay


def E(eid, type_, box, **kw):
    return Element(element_id=eid, type=type_, reading_order=0, bbox_normalized=box, **kw)


def test_downscale_keeps_aspect_and_reports_scale():
    img = np.zeros((3508, 2480, 3), np.uint8)
    small, scale = downscale(img, 1600)
    assert small.shape[0] == 1600 and abs(small.shape[1] - 1131) <= 1
    assert abs(scale - 1600 / 3508) < 1e-6
    tiny = np.zeros((100, 50), np.uint8)
    assert downscale(tiny, 1600)[1] == 1.0


def test_mark_is_attached_to_the_element_it_circles():
    table = E("t", ElementType.TABLE, (0.1, 0.1, 0.9, 0.5))
    para = E("p", ElementType.PARAGRAPH, (0.1, 0.6, 0.9, 0.7))
    mark = E("m", ElementType.HANDWRITTEN_NOTE, (0.7, 0.4, 0.85, 0.48), description="Khoanh tròn đánh dấu")
    note = E("n", ElementType.HANDWRITTEN_NOTE, (0.1, 0.72, 0.5, 0.75), text="Đã soát")
    attach_notes([table, para, mark, note])
    assert mark.attached_to == "t"
    assert note.attached_to == "p"


def test_overlay_draws_on_a_copy():
    img = np.full((200, 100, 3), 255, np.uint8)
    page = Page(page_number=1, width=100, height=200, elements=[E("a", ElementType.PARAGRAPH, (0.1, 0.1, 0.9, 0.3), needs_human_review=True)])
    out = draw_overlay(img, page)
    assert out.shape == img.shape
    assert (img == 255).all()
    assert (out != 255).any()
