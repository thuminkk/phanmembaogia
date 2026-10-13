from sqlalchemy.orm import Session

from app.db.models import Quote, QuoteIOLine, QuotePLCLine

# Danh mục thiết bị chuẩn + số lượng/input/output trên 1 thiết bị — copy nguyên từ sheet "Tính toán IO"
# tham khảo (file "Form báo giá.xlsx"). Số lượng: 3 nhóm Tủ HMI/Button Box/Khí nén dùng đúng số mẫu
# người dùng xác nhận (2026-09-24, ảnh chụp) làm sẵn giá trị gợi ý; các nhóm còn lại (Động cơ, Cảm
# biến, Thiết bị an toàn, Thiết bị khác) CHƯA được xác nhận số lượng mẫu nên vẫn để None — người
# dùng tự điền theo dự án, đúng chính sách ban đầu.
STANDARD_IO_CATALOG: list[tuple[str, list[tuple[str, float | None, float | None, float | None]]]] = [
    ("Tủ HMI", [
        ("Chuyển mạch 2 vị trí", 1, 1, None),
        ("Key switch 2 vị trí", 1, 1, None),
        ("Nút ấn có đèn", 5, 1, 1),
        ("Nút ấn không đèn", None, 1, None),
        ("Đèn báo", None, None, 1),
        ("Dừng khẩn", 1, 1, None),
        ("Còi báo", None, None, 1),
        ("Đèn tháp", 1, None, 4),
    ]),
    ("Button Box", [
        ("Dừng khẩn", 1, 1, None),
        ("Nút start", 1, 1, 1),
    ]),
    ("Khí nén", [
        ("Xi lanh", 5, 2, 2),
        ("Van điện", 0, 1, 1),
        ("Cảm biến áp suất", 1, 1, 0),
        ("Van cấp khí tổng", 1, 0, 1),
        ("Van thổi khí", None, None, 1),
    ]),
    ("Động cơ", [
        ("Servo", None, 3, 4),
        ("Xi lanh điện", None, 1, None),
        ("Biến tần", None, 3, 2),
        ("Speed controller", None, 2, 2),
        ("Động cơ", None, 2, 2),
    ]),
    ("Cảm biến", [
        ("Cảm biến quang", None, 1, 0),
        ("Cảm biến sợi quang", None, 2, None),
        ("Cảm biến tiệm cận", None, 1, None),
        ("Cảm biến servo", None, 1, None),
        ("Cảm biến đo lường", None, 3, 3),
    ]),
    ("Thiết bị an toàn", [
        ("Safety fence", None, 2, 0),
        ("Khóa cửa", None, 1, 1),
        ("Cảm biến cửa", None, 1, 0),
        ("Công tắc an toàn", None, 1, None),
    ]),
    ("Thiết bị khác", [
        ("Rơ le PLC Ready", None, 0, 1),
    ]),
]

# Cấu hình PLC mặc định — theo đúng mẫu người dùng xác nhận (2026-09-25, ảnh chụp): 1 PLC chính +
# 3 module input/output/input-output đi kèm, số lượng luôn =1 (mỗi dự án thường chỉ dùng 1 bộ,
# khác STANDARD_IO_CATALOG ở chỗ đây là cấu hình phần cứng thực tế chọn sẵn, không phải thông số
# kỹ thuật của loại thiết bị).
STANDARD_PLC_CATALOG: list[tuple[str, float | None, float | None, float | None]] = [
    ("FX5U-80MT-ES", 1, 40, 40),
    ("Module input", 1, 16, None),
    ("Module output", 1, None, 16),
    ("Module input/output", 1, 16, 16),
]


def _next_thu_tu(lines: list) -> int:
    return (max((l.thu_tu for l in lines), default=-1)) + 1


def seed_standard_catalog(db: Session, quote_id: int) -> None:
    """Nạp danh mục thiết bị chuẩn (nhóm + thiết bị) vào bảng tính I/O + cấu hình PLC mặc định —
    nối tiếp sau các dòng đã có (không xóa dòng cũ), để người dùng tự điền số lượng theo dự án +
    có thể thêm dòng tùy biến khác bên dưới."""
    quote = db.get(Quote, quote_id)
    thu_tu = _next_thu_tu(quote.io_lines)
    for nhom, items in STANDARD_IO_CATALOG:
        db.add(QuoteIOLine(quote_id=quote_id, thu_tu=thu_tu, la_nhom=True, ten_thiet_bi=nhom))
        thu_tu += 1
        for ten, so_luong, so_input, so_output in items:
            db.add(
                QuoteIOLine(
                    quote_id=quote_id,
                    thu_tu=thu_tu,
                    la_nhom=False,
                    ten_thiet_bi=ten,
                    so_luong=so_luong,
                    so_input=so_input,
                    so_output=so_output,
                )
            )
            thu_tu += 1

    plc_thu_tu = _next_thu_tu(quote.plc_lines)
    for ten, so_luong, so_input, so_output in STANDARD_PLC_CATALOG:
        db.add(
            QuotePLCLine(
                quote_id=quote_id,
                thu_tu=plc_thu_tu,
                ten_thiet_bi=ten,
                so_luong=so_luong,
                so_input=so_input,
                so_output=so_output,
            )
        )
        plc_thu_tu += 1
    db.commit()


# ---- Bảng tính I/O (nhu cầu) ----


def add_io_line(db: Session, quote_id: int, **fields) -> QuoteIOLine:
    quote = db.get(Quote, quote_id)
    line = QuoteIOLine(quote_id=quote_id, thu_tu=_next_thu_tu(quote.io_lines), **fields)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def add_io_line_in_group(db: Session, quote_id: int, group_line_id: int, **fields) -> QuoteIOLine:
    """Thêm 1 dòng thiết bị MỚI ngay bên trong 1 nhóm cụ thể — chèn vào cuối danh sách thiết bị của
    đúng nhóm đó (trước dòng tiêu đề nhóm kế tiếp, hoặc cuối bảng nếu là nhóm cuối cùng), khác với
    add_io_line() luôn nối vào tận cuối TOÀN BẢNG bất kể đang thêm cho nhóm nào. Đánh số lại thu_tu
    tuần tự cho toàn bộ danh sách sau khi chèn (giống cách move_group() làm với cụm linh kiện) —
    không phụ thuộc các giá trị thu_tu cũ, luôn ra đúng vị trí bất kể dữ liệu thu_tu trước đó thế nào."""
    quote = db.get(Quote, quote_id)
    lines = sorted(quote.io_lines, key=lambda l: l.thu_tu)
    group_idx = next((i for i, l in enumerate(lines) if l.id == group_line_id), None)
    if group_idx is None:
        return add_io_line(db, quote_id, la_nhom=False, **fields)

    insert_idx = group_idx + 1
    while insert_idx < len(lines) and not lines[insert_idx].la_nhom:
        insert_idx += 1

    new_line = QuoteIOLine(quote_id=quote_id, la_nhom=False, thu_tu=0, **fields)
    lines.insert(insert_idx, new_line)
    db.add(new_line)
    for i, l in enumerate(lines):
        l.thu_tu = i
    db.commit()
    db.refresh(new_line)
    return new_line


def update_io_line(db: Session, line: QuoteIOLine, **fields) -> QuoteIOLine:
    for key, value in fields.items():
        setattr(line, key, value)
    db.commit()
    db.refresh(line)
    return line


def delete_io_line(db: Session, line: QuoteIOLine) -> None:
    db.delete(line)
    db.commit()


# ---- Cấu hình PLC ----


def add_plc_line(db: Session, quote_id: int, **fields) -> QuotePLCLine:
    quote = db.get(Quote, quote_id)
    line = QuotePLCLine(quote_id=quote_id, thu_tu=_next_thu_tu(quote.plc_lines), **fields)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def update_plc_line(db: Session, line: QuotePLCLine, **fields) -> QuotePLCLine:
    for key, value in fields.items():
        setattr(line, key, value)
    db.commit()
    db.refresh(line)
    return line


def delete_plc_line(db: Session, line: QuotePLCLine) -> None:
    db.delete(line)
    db.commit()


def update_du_phong_percent(db: Session, quote: Quote, percent: float) -> Quote:
    quote.du_phong_io_percent = percent
    db.commit()
    db.refresh(quote)
    return quote


def io_summary(quote: Quote) -> dict:
    """Tổng hợp bảng tính I/O — đúng công thức sheet tham khảo:
    dự phòng = INT(p * tổng / (100 - p)) (dự phòng chiếm p% trên TỔNG SAU DỰ PHÒNG, không phải trên tổng gốc);
    tổng cuối = tổng gốc + dự phòng."""
    tong_input = sum(l.tong_input for l in quote.io_lines)
    tong_output = sum(l.tong_output for l in quote.io_lines)
    p = quote.du_phong_io_percent or 0

    def _du_phong(tong: float) -> float:
        if p <= 0 or p >= 100:
            return 0
        return int(p * tong / (100 - p))

    du_phong_input = _du_phong(tong_input)
    du_phong_output = _du_phong(tong_output)

    plc_tong_input = sum(l.tong_input for l in quote.plc_lines)
    plc_tong_output = sum(l.tong_output for l in quote.plc_lines)

    final_input = tong_input + du_phong_input
    final_output = tong_output + du_phong_output

    return {
        "tong_input": tong_input,
        "tong_output": tong_output,
        "du_phong_input": du_phong_input,
        "du_phong_output": du_phong_output,
        "final_input": final_input,
        "final_output": final_output,
        "plc_tong_input": plc_tong_input,
        "plc_tong_output": plc_tong_output,
        "du_input": plc_tong_input >= final_input,
        "du_output": plc_tong_output >= final_output,
    }
