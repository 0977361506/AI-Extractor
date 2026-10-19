from idp.core.ast import TableCell
from idp.table.checks import run_arithmetic_checks


def _grid(rows, header_rows=1):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            cells.append(TableCell(row=r, col=c, text=text, is_header=r < header_rows))
    return cells


def _failed(cells):
    return sorted((c.row, c.col) for c in cells if c.check_failed)


BCTC = [
    ["Chỉ tiêu", "Mã số", "Quý I", "Quý II"],
    ["1. Doanh thu bán hàng", "01", "12.450", "13.870"],
    ["2. Các khoản giảm trừ", "02", "(320)", "(410)"],
    ["3. Doanh thu thuần (10 = 01 - 02)", "10", "12.130", "13.460"],
    ["4. Giá vốn hàng bán", "11", "(7.100)", "(7.700)"],
    ["5. Lợi nhuận gộp (20 = 10 - 11)", "20", "5.030", "5.760"],
    ["10. Lợi nhuận thuần", "30", "1.625", "2.133"],
    ["13. Lợi nhuận khác", "40", "55", "(15)"],
    ["14. Tổng lợi nhuận (50 = 30 + 40)", "50", "1.680", "2.118"],
]


def test_bctc_formulas_pass():
    cells = _grid(BCTC)
    report = run_arithmetic_checks(cells)
    assert _failed(cells) == []
    assert report.checked >= 6


def test_bctc_formula_failure_is_flagged():
    rows = [list(r) for r in BCTC]
    rows[5][3] = "5.780"  # OCR error: should be 5.760
    cells = _grid(rows)
    report = run_arithmetic_checks(cells)
    assert _failed(cells) == [(5, 3)]
    assert report.failed == 1


ALLOCATION = [
    ["Khoản mục", "Kinh doanh", "Kỹ thuật", "Cộng"],
    ["Lương cơ bản", "620", "840", "1.460"],
    ["Thưởng", "210", "260", "470"],
    ["Cộng nhóm", "830", "1.100", "1.930"],
    ["Thuê văn phòng", "95", "120", "215"],
    ["Cộng nhóm", "95", "120", "215"],
    ["TỔNG CỘNG", "925", "1.220", "2.145"],
]


def test_group_totals_and_row_totals_pass():
    cells = _grid(ALLOCATION)
    run_arithmetic_checks(cells)
    assert _failed(cells) == []


def test_wrong_row_total_and_wrong_grand_total_flagged():
    rows = [list(r) for r in ALLOCATION]
    rows[1][3] = "1.406"  # row total wrong
    rows[6][1] = "952"  # grand total wrong
    cells = _grid(rows)
    run_arithmetic_checks(cells)
    assert (1, 3) in _failed(cells)
    assert (6, 1) in _failed(cells)


INVOICE = [
    ["STT", "Tên hạng mục", "ĐVT", "SL", "Đơn giá", "Thành tiền"],
    ["1", "Phân tích", "Gói", "1", "120.000.000", "120.000.000"],
    ["2", "Lập trình", "Module", "3", "85.500.000", "256.500.000"],
    ["", "Cộng tiền hàng", "", "", "", "376.500.000"],
    ["", "Thuế GTGT (10%)", "", "", "", "37.650.000"],
    ["", "TỔNG CỘNG (đã gồm VAT)", "", "", "", "414.150.000"],
]


def test_invoice_product_vat_and_total_pass():
    cells = _grid(INVOICE)
    run_arithmetic_checks(cells)
    assert _failed(cells) == []


def test_invoice_product_error_flagged():
    rows = [list(r) for r in INVOICE]
    rows[2][5] = "265.500.000"
    cells = _grid(rows)
    run_arithmetic_checks(cells)
    assert (2, 5) in _failed(cells)


def test_non_numeric_table_has_nothing_to_check():
    cells = _grid([["Họ tên", "Chức vụ"], ["Nguyễn Văn A", "Giám đốc"]])
    report = run_arithmetic_checks(cells)
    assert report.checked == 0 and _failed(cells) == []


def test_percentage_row_shown_negative_in_parentheses_passes():
    rows = [
        ["Chỉ tiêu", "Mã số", "Quý I"],
        ["14. Tổng lợi nhuận trước thuế", "50", "1.680"],
        ["15. Chi phí thuế TNDN hiện hành (20%)", "51", "(336)"],
    ]
    cells = _grid(rows)
    run_arithmetic_checks(cells)
    assert _failed(cells) == []


def test_malformed_number_in_numeric_column_is_the_flagged_cell():
    rows = [list(r) for r in ALLOCATION]
    rows[6][2] = "1211.220"  # noise digits glued before 1.220
    cells = _grid(rows)
    run_arithmetic_checks(cells)
    assert (6, 2) in _failed(cells)
