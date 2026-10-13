from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import parts as parts_crud
from app.crud import quote_io as quote_io_crud
from app.db.models import (
    Part,
    PartSupplierPrice,
    Quote,
    QuoteComponentGroup,
    QuoteFabricatedLine,
    QuoteIOLine,
    QuoteMaterialLine,
    QuotePartLine,
    QuotePLCLine,
)
from app.schemas.quotes import QuoteUpdateIn

DUPLICATE_VERSION_ERROR = "Dự án này đã có báo giá với đúng cặp lần đặt hàng + rev đó."


def get_quote(db: Session, quote_id: int) -> Quote | None:
    return db.get(Quote, quote_id)


def suggest_next_numbers(db: Session, project_id: int) -> tuple[int, int]:
    """Gợi ý rev/dot tiếp theo (điền sẵn vào form, người dùng có thể tự sửa lại)."""
    existing = db.scalars(
        select(Quote).where(Quote.project_id == project_id, Quote.is_active.is_(True))
    ).all()
    if not existing:
        return 0, 1
    max_dot = max(q.dot for q in existing)
    current_cycle_revs = [q.rev for q in existing if q.dot == max_dot]
    return max(current_cycle_revs) + 1, max_dot


def create_blank_quote(db: Session, project_id: int, rev: int, dot: int) -> Quote:
    quote = Quote(project_id=project_id, rev=rev, dot=dot)
    db.add(quote)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(DUPLICATE_VERSION_ERROR) from exc
    db.refresh(quote)
    quote_io_crud.seed_standard_catalog(db, quote.id)
    return quote


def clone_quote(
    db: Session,
    source_quote_id: int,
    *,
    project_id: int | None = None,
    rev: int = 0,
    dot: int = 1,
    is_template: bool = False,
    ten_template: str | None = None,
    khach_hang: str | None = None,
) -> Quote:
    source = db.get(Quote, source_quote_id)
    new_quote = Quote(
        project_id=project_id,
        rev=rev,
        dot=dot,
        is_template=is_template,
        ten_template=ten_template,
        khach_hang=khach_hang,
        du_phong_io_percent=source.du_phong_io_percent,
    )
    db.add(new_quote)
    db.flush()

    group_id_map: dict[int, int] = {}
    for group in source.groups:
        new_group = QuoteComponentGroup(
            quote_id=new_quote.id,
            ten_cum=group.ten_cum,
            mo_ta_co_khi=group.mo_ta_co_khi,
            mo_ta_dien=group.mo_ta_dien,
            mo_ta_khi_nen=group.mo_ta_khi_nen,
            mo_ta_thuy_luc=group.mo_ta_thuy_luc,
            thu_tu=group.thu_tu,
        )
        db.add(new_group)
        db.flush()
        group_id_map[group.id] = new_group.id

    for line in source.part_lines:
        # Copy sang rev/báo giá mới = "tính giá lại" -> lấy đúng giá NCC HIỆN TẠI trong CSDL cho các dòng
        # còn liên kết tới CSDL (part_id + supplier_price_id còn hiệu lực), không đóng băng giá cũ đã copy.
        # Dòng nhập tay không có liên kết CSDL (hoặc NCC đã bị xóa) thì giữ nguyên giá cũ vì không có gì để lấy mới.
        if line.supplier_price_id and line.supplier_price and line.supplier_price.is_active:
            current_don_gia = line.supplier_price.don_gia
        else:
            current_don_gia = line.don_gia
        db.add(
            QuotePartLine(
                quote_id=new_quote.id,
                group_id=group_id_map.get(line.group_id),
                part_id=line.part_id,
                supplier_price_id=line.supplier_price_id,
                ten_linh_kien=line.ten_linh_kien,
                ma_linh_kien=line.ma_linh_kien,
                hang=line.hang,
                nha_cung_cap=line.nha_cung_cap,
                don_vi=line.don_vi,
                so_luong=line.so_luong,
                don_gia=current_don_gia,
                ghi_chu=line.ghi_chu,
            )
        )
    for line in source.material_lines:
        db.add(
            QuoteMaterialLine(
                quote_id=new_quote.id,
                chung_loai=line.chung_loai,
                quy_cach=line.quy_cach,
                vat_lieu=line.vat_lieu,
                xuat_xu=line.xuat_xu,
                don_vi=line.don_vi,
                so_luong=line.so_luong,
                don_gia=line.don_gia,
                nha_cung_cap=line.nha_cung_cap,
            )
        )
    for line in source.fabricated_lines:
        db.add(
            QuoteFabricatedLine(
                quote_id=new_quote.id,
                ten_linh_kien=line.ten_linh_kien,
                ma_ban_ve=line.ma_ban_ve,
                vat_lieu=line.vat_lieu,
                so_luong=line.so_luong,
                don_gia=line.don_gia,
                nha_cung_cap=line.nha_cung_cap,
                ghi_chu=line.ghi_chu,
            )
        )
    for line in source.io_lines:
        db.add(
            QuoteIOLine(
                quote_id=new_quote.id,
                thu_tu=line.thu_tu,
                la_nhom=line.la_nhom,
                ten_thiet_bi=line.ten_thiet_bi,
                so_luong=line.so_luong,
                so_input=line.so_input,
                so_output=line.so_output,
            )
        )
    for line in source.plc_lines:
        db.add(
            QuotePLCLine(
                quote_id=new_quote.id,
                thu_tu=line.thu_tu,
                ten_thiet_bi=line.ten_thiet_bi,
                so_luong=line.so_luong,
                so_input=line.so_input,
                so_output=line.so_output,
            )
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(DUPLICATE_VERSION_ERROR) from exc
    db.refresh(new_quote)
    return new_quote


def save_as_template(db: Session, quote_id: int, ten_template: str, khach_hang: str | None = None) -> Quote:
    return clone_quote(
        db, quote_id, project_id=None, rev=0, dot=1, is_template=True, ten_template=ten_template, khach_hang=khach_hang
    )


def create_blank_template(db: Session, ten_template: str, khach_hang: str | None = None) -> Quote:
    quote = Quote(project_id=None, is_template=True, ten_template=ten_template, khach_hang=khach_hang)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_io_crud.seed_standard_catalog(db, quote.id)
    return quote


def update_template_meta(db: Session, quote: Quote, ten_template: str, khach_hang: str | None) -> Quote:
    quote.ten_template = ten_template
    quote.khach_hang = khach_hang
    db.commit()
    db.refresh(quote)
    return quote


def delete_template(db: Session, quote: Quote) -> None:
    quote.is_active = False
    db.commit()


def delete_quote(db: Session, quote: Quote) -> None:
    """Xoá mềm 1 phiên bản báo giá (rev) — không đụng tới các rev khác của cùng dự án."""
    quote.is_active = False
    db.commit()


def list_templates(db: Session) -> list[Quote]:
    """Sắp theo khách hàng (rồi tên mẫu) để tiện nhóm hiển thị theo khách hàng."""
    return db.scalars(
        select(Quote)
        .where(Quote.is_template.is_(True), Quote.is_active.is_(True))
        .order_by(Quote.khach_hang.is_(None), Quote.khach_hang, Quote.ten_template)
    ).all()


def list_source_quotes(db: Session) -> list[Quote]:
    """Báo giá thật (không phải mẫu) để chọn làm nguồn copy — kể cả từ dự án khác."""
    return db.scalars(
        select(Quote)
        .where(Quote.is_template.is_(False), Quote.is_active.is_(True))
        .order_by(Quote.created_at.desc())
        .limit(100)
    ).all()


def update_quote(db: Session, quote: Quote, data: QuoteUpdateIn) -> Quote:
    quote.rev = data.rev
    quote.dot = data.dot
    quote.trang_thai = data.trang_thai
    quote.nguoi_tinh_gia = data.nguoi_tinh_gia
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(DUPLICATE_VERSION_ERROR) from exc
    db.refresh(quote)
    return quote


def update_ghi_chu(db: Session, quote: Quote, ghi_chu: str | None) -> Quote:
    quote.ghi_chu = ghi_chu
    db.commit()
    db.refresh(quote)
    return quote


def quote_totals(quote: Quote) -> dict:
    tong_linh_kien = sum(line.so_luong * line.don_gia for line in quote.part_lines)
    tong_nvl = sum(line.so_luong * line.don_gia for line in quote.material_lines)
    tong_gia_cong = sum(line.so_luong * line.don_gia for line in quote.fabricated_lines)
    return {
        "linh_kien": tong_linh_kien,
        "nvl": tong_nvl,
        "gia_cong": tong_gia_cong,
        "tong": tong_linh_kien + tong_nvl + tong_gia_cong,
    }


# ---- Dòng Nguyên vật liệu ----


def add_material_line(db: Session, quote_id: int, **fields) -> QuoteMaterialLine:
    line = QuoteMaterialLine(quote_id=quote_id, **fields)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def update_material_line(db: Session, line: QuoteMaterialLine, **fields) -> QuoteMaterialLine:
    for key, value in fields.items():
        setattr(line, key, value)
    db.commit()
    db.refresh(line)
    return line


def delete_material_line(db: Session, line: QuoteMaterialLine) -> None:
    db.delete(line)
    db.commit()


# ---- Dòng Linh kiện gia công ----


def add_fabricated_line(db: Session, quote_id: int, **fields) -> QuoteFabricatedLine:
    line = QuoteFabricatedLine(quote_id=quote_id, **fields)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def update_fabricated_line(db: Session, line: QuoteFabricatedLine, **fields) -> QuoteFabricatedLine:
    for key, value in fields.items():
        setattr(line, key, value)
    db.commit()
    db.refresh(line)
    return line


def delete_fabricated_line(db: Session, line: QuoteFabricatedLine) -> None:
    db.delete(line)
    db.commit()


# ---- Dòng Linh kiện bán sẵn (nối CSDL linh kiện) ----


def _next_part_line_thu_tu(db: Session, quote_id: int, group_id: int | None) -> int:
    max_thu_tu = db.scalar(
        select(func.max(QuotePartLine.thu_tu)).where(
            QuotePartLine.quote_id == quote_id, QuotePartLine.group_id == group_id
        )
    )
    return (max_thu_tu or 0) + 1


def add_part_line(
    db: Session,
    quote_id: int,
    *,
    part_id: int | None,
    supplier_price_id: int | None,
    ten_linh_kien: str,
    ma_linh_kien: str | None,
    hang: str | None,
    nha_cung_cap: str | None,
    don_vi: str | None,
    don_gia: float,
    so_luong: float,
    ghi_chu: str | None,
    group_id: int | None = None,
    loai: str | None = None,
    cap_nhat_gia: bool = True,
) -> QuotePartLine:
    thu_tu = _next_part_line_thu_tu(db, quote_id, group_id)
    if part_id and supplier_price_id:
        # Chọn thẳng từ CSDL: dùng đúng giá hiện tại của NCC đã chọn.
        part = db.get(Part, part_id)
        price = db.get(PartSupplierPrice, supplier_price_id)
        line = QuotePartLine(
            quote_id=quote_id,
            group_id=group_id,
            thu_tu=thu_tu,
            part_id=part.id,
            supplier_price_id=price.id,
            ten_linh_kien=part.ten_linh_kien,
            ma_linh_kien=part.ma_linh_kien,
            hang=part.hang,
            nha_cung_cap=price.nha_cung_cap,
            don_vi=part.don_vi,
            so_luong=so_luong,
            don_gia=price.don_gia,
            ghi_chu=ghi_chu,
        )
    else:
        # Nhập tay: tự động tìm/tạo trong CSDL linh kiện (không bao giờ có giá "trôi nổi").
        # cap_nhat_gia=False (dòng đổi giá nhưng người dùng KHÔNG tích xác nhận): CSDL giữ nguyên
        # giá cũ -> dòng báo giá cũng phải lấy đúng giá cũ đó (price.don_gia sau lệnh gọi), TUYỆT
        # ĐỐI không dùng lại don_gia/nha_cung_cap gõ/dán vào form, để không có giá "trôi nổi" khác
        # với CSDL ngay trên chính dòng vừa thêm.
        part, price, _action = parts_crud.find_or_create_part_price(
            db,
            ma_linh_kien=ma_linh_kien,
            ten_linh_kien=ten_linh_kien,
            hang=hang,
            nha_cung_cap=nha_cung_cap,
            don_gia=don_gia,
            don_vi=don_vi,
            loai=loai,
            cap_nhat_gia=cap_nhat_gia,
        )
        line = QuotePartLine(
            quote_id=quote_id,
            group_id=group_id,
            thu_tu=thu_tu,
            part_id=part.id,
            supplier_price_id=price.id if price else None,
            ten_linh_kien=ten_linh_kien,
            ma_linh_kien=ma_linh_kien,
            hang=hang,
            nha_cung_cap=price.nha_cung_cap if price else nha_cung_cap,
            don_vi=don_vi,
            so_luong=so_luong,
            don_gia=price.don_gia if price else don_gia,
            ghi_chu=ghi_chu,
        )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def list_price_mismatched_lines(quote: Quote) -> list[QuotePartLine]:
    """Các dòng linh kiện trong báo giá đang có giá/NCC (đông cứng tại thời điểm thêm) khác với
    giá/NCC HIỆN TẠI trong CSDL — thường do linh kiện được thêm khi CSDL chưa có giá (0đ), hoặc
    giá CSDL đã được người dùng cập nhật sau đó. Dùng cho trang "Đồng bộ giá theo CSDL" (2026-09-30)
    — ngược hướng với "Cập nhật giá" từng dòng đã có (route đó đẩy giá BÁO GIÁ vào CSDL; hàm này
    phục vụ chiều ngược lại — kéo giá CSDL vào báo giá, áp dụng hàng loạt)."""
    return [
        l
        for l in quote.part_lines
        if l.supplier_price is not None
        and (l.don_gia != l.supplier_price.don_gia or (l.nha_cung_cap or "") != (l.supplier_price.nha_cung_cap or ""))
    ]


def sync_line_price_from_csdl(db: Session, line: QuotePartLine) -> None:
    """Đồng bộ giá/NCC của 1 dòng báo giá theo đúng giá/NCC hiện tại trong CSDL — chỉ đổi dòng báo
    giá này, không đụng gì tới CSDL (CSDL vốn đã là nguồn giá đúng, chỉ có dòng báo giá là đang cũ)."""
    if not line.supplier_price:
        return
    line.don_gia = line.supplier_price.don_gia
    line.nha_cung_cap = line.supplier_price.nha_cung_cap
    db.commit()


# ---- Cụm linh kiện ----


def add_group(db: Session, quote_id: int, ten_cum: str) -> QuoteComponentGroup:
    max_thu_tu = db.scalar(
        select(func.max(QuoteComponentGroup.thu_tu)).where(QuoteComponentGroup.quote_id == quote_id)
    )
    group = QuoteComponentGroup(quote_id=quote_id, ten_cum=ten_cum, thu_tu=(max_thu_tu or 0) + 1)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_group(db: Session, group: QuoteComponentGroup, **fields) -> QuoteComponentGroup:
    for key, value in fields.items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group: QuoteComponentGroup) -> None:
    for line in group.part_lines:
        line.group_id = None
    db.delete(group)
    db.commit()


def move_group(db: Session, quote_id: int, group_id: int, huong: str) -> None:
    """Đổi vị trí 1 cụm lên/xuống 1 bậc (huong = "len"/"xuong") — luôn đánh số lại thu_tu tuần tự
    0..n-1 sau khi đổi chỗ trong danh sách (thay vì hoán đổi thẳng giá trị thu_tu cũ), để tự sửa
    luôn mọi thu_tu trùng/lệch từ trước, không phụ thuộc giá trị hiện có."""
    groups = db.scalars(
        select(QuoteComponentGroup)
        .where(QuoteComponentGroup.quote_id == quote_id)
        .order_by(QuoteComponentGroup.thu_tu, QuoteComponentGroup.id)
    ).all()
    idx = next((i for i, g in enumerate(groups) if g.id == group_id), None)
    if idx is None:
        return
    swap_idx = idx - 1 if huong == "len" else idx + 1
    if swap_idx < 0 or swap_idx >= len(groups):
        return
    groups[idx], groups[swap_idx] = groups[swap_idx], groups[idx]
    for i, g in enumerate(groups):
        g.thu_tu = i
    db.commit()


def quote_part_breakdown_by_loai(quote: Quote) -> dict[str, float]:
    """Tổng tiền linh kiện tiêu chuẩn chia theo Loại (Điện/Khí nén/Thủy lực/Cơ khí/Khác) — đúng cách sheet SUMMARY chia nhỏ."""
    breakdown: dict[str, float] = {}
    for line in quote.part_lines:
        loai = line.part.loai if line.part else None
        key = loai or "Chưa phân loại"
        breakdown[key] = breakdown.get(key, 0) + line.so_luong * line.don_gia
    return breakdown


def update_part_line(db: Session, line: QuotePartLine, **fields) -> QuotePartLine:
    """Sửa trực tiếp dòng báo giá (bản chụp) — không đụng tới CSDL linh kiện."""
    for key, value in fields.items():
        setattr(line, key, value)
    db.commit()
    db.refresh(line)
    return line


def delete_part_line(db: Session, line: QuotePartLine) -> None:
    db.delete(line)
    db.commit()


def delete_part_lines(db: Session, quote_id: int, line_ids: list[int]) -> None:
    for line_id in line_ids:
        line = db.get(QuotePartLine, line_id)
        if line and line.quote_id == quote_id:
            db.delete(line)
    db.commit()


def reorder_part_lines(db: Session, quote_id: int, group_id: int | None, line_ids: list[int]) -> None:
    """Kéo-thả: cập nhật group_id (nếu đổi bảng) + thu_tu theo đúng thứ tự line_ids cho bảng đích."""
    for index, line_id in enumerate(line_ids):
        line = db.get(QuotePartLine, line_id)
        if line is None or line.quote_id != quote_id:
            continue
        line.group_id = group_id
        line.thu_tu = index
    db.commit()
