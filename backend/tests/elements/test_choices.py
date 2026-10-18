from idp.core.ast import ElementType
from idp.elements.choices import build_choice_groups
from idp.layout.regions import LayoutRegion
from idp.table.builder import OcrLine


def L(text, x0, y0, x1, y1):
    return OcrLine(text=text, confidence=0.9, bbox=(x0, y0, x1, y1))


def test_options_on_one_row_form_a_group_with_question():
    regions = [
        LayoutRegion("checkbox_selected", 0.91, (464, 554, 550, 589)),
        LayoutRegion("checkbox_unselected", 0.93, (614, 553, 684, 587)),
        LayoutRegion("checkbox_unselected", 0.92, (763, 550, 853, 582)),
        LayoutRegion("text", 0.9, (100, 560, 300, 585)),
    ]
    lines = [
        L("5. Giới tính:", 100, 560, 300, 585),
        L("Nam", 500, 558, 548, 586),
        L("Nữ", 650, 556, 682, 584),
        L("Khác", 800, 553, 850, 580),
        L("dòng khác", 100, 700, 400, 730),
    ]
    groups, consumed = build_choice_groups(regions, lines, 1241, 1755)
    assert len(groups) == 1
    g = groups[0]
    assert g.type == ElementType.CHOICE_GROUP
    assert g.question == "Giới tính"
    assert [(o.label, o.checked) for o in g.options] == [("Nam", True), ("Nữ", False), ("Khác", False)]
    assert not g.multi_select
    assert consumed == {0, 1, 2, 3}


def test_two_rows_two_groups_and_multi_select():
    regions = [
        LayoutRegion("checkbox_selected", 0.9, (100, 100, 200, 130)),
        LayoutRegion("checkbox_selected", 0.9, (300, 100, 420, 130)),
        LayoutRegion("checkbox_unselected", 0.9, (100, 300, 200, 330)),
    ]
    lines = [L("SMS", 130, 102, 190, 128), L("Thư điện tử", 330, 102, 418, 128), L("Có", 130, 302, 180, 328)]
    groups, _ = build_choice_groups(regions, lines, 1000, 1000)
    assert len(groups) == 2
    assert groups[0].multi_select
    assert [o.label for o in groups[0].options] == ["SMS", "Thư điện tử"]


def test_marker_glyph_noise_is_stripped_from_label():
    regions = [LayoutRegion("checkbox_selected", 0.9, (100, 100, 260, 130))]
    groups, _ = build_choice_groups(regions, [L("☑ Hợp lệ", 100, 100, 260, 130)], 1000, 1000)
    assert groups[0].options[0].label == "Hợp lệ"
