from idp.layout.regions import LayoutRegion, postprocess_regions


def R(label, score, box):
    return LayoutRegion(label=label, score=score, bbox=box)


def labels(regions):
    return sorted((r.label, r.bbox) for r in regions)


def test_same_box_different_labels_keeps_best_score():
    out = postprocess_regions([R("caption", 0.75, (166, 1238, 327, 1288)), R("text", 0.59, (166, 1238, 327, 1288))])
    assert labels(out) == [("caption", (166, 1238, 327, 1288))]


def test_checkbox_wins_over_overlapping_text():
    out = postprocess_regions([R("text", 0.9, (205, 1309, 278, 1345)), R("checkbox_selected", 0.64, (205, 1309, 278, 1345))])
    assert [r.label for r in out] == ["checkbox_selected"]


def test_form_and_key_value_containers_are_dropped_children_kept():
    out = postprocess_regions(
        [R("form", 0.93, (91, 263, 1143, 1389)), R("key_value_region", 0.5, (100, 1100, 1000, 1380)), R("text", 0.8, (460, 270, 900, 320))]
    )
    assert labels(out) == [("text", (460, 270, 900, 320))]


def test_text_inside_table_or_picture_is_absorbed():
    out = postprocess_regions(
        [
            R("table", 0.95, (100, 300, 1100, 1400)),
            R("text", 0.8, (150, 400, 400, 430)),
            R("picture", 0.9, (100, 1500, 600, 1700)),
            R("caption", 0.7, (150, 1550, 300, 1580)),
            R("text", 0.8, (100, 100, 1000, 140)),
        ]
    )
    assert labels(out) == [("picture", (100, 1500, 600, 1700)), ("table", (100, 300, 1100, 1400)), ("text", (100, 100, 1000, 140))]


def test_box_containing_several_finer_regions_is_dropped():
    out = postprocess_regions(
        [
            R("section_header", 0.61, (350, 79, 846, 140)),
            R("section_header", 0.52, (350, 78, 845, 112)),
            R("text", 0.58, (442, 113, 754, 139)),
        ]
    )
    assert labels(out) == [("section_header", (350, 78, 845, 112)), ("text", (442, 113, 754, 139))]


def test_low_score_regions_filtered():
    out = postprocess_regions([R("text", 0.2, (0, 0, 10, 10))], min_score=0.4)
    assert out == []
