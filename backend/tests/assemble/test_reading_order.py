from idp.assemble.reading_order import xy_cut_order


def test_vertical_stack():
    boxes = [(50, 300, 900, 340), (50, 100, 900, 140), (50, 200, 900, 240)]
    assert xy_cut_order(boxes) == [1, 2, 0]


def test_two_column_header_block_reads_column_by_column():
    boxes = [
        (50, 50, 400, 80),  # 0 left line 1
        (600, 50, 1000, 80),  # 1 right line 1
        (50, 90, 400, 120),  # 2 left line 2
        (600, 90, 1000, 120),  # 3 right line 2
        (50, 200, 1000, 260),  # 4 full-width body
    ]
    assert xy_cut_order(boxes) == [0, 2, 1, 3, 4]


def test_same_row_left_to_right():
    boxes = [(500, 100, 600, 130), (100, 100, 200, 130)]
    assert xy_cut_order(boxes) == [1, 0]


def test_empty_and_single():
    assert xy_cut_order([]) == []
    assert xy_cut_order([(0, 0, 1, 1)]) == [0]
