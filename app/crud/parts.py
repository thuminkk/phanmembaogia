import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import distinct, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Part, PartSupplierPrice, QuotePartLine, StandardGroupLine
from app.schemas.parts import CandidateRow, PartIn, SupplierPriceIn

PAGE_SIZE = 50

LOAI_OPTIONS = ["Điện", "Khí nén", "Thủy lực", "Cơ khí", "Khác"]


def list_parts(
    db: Session,
    ma: str | None = None,
    ten: str | None = None,
    hang: str | None = None,
    loai: str | None = None,
    ncc: str | None = None,
    page: int = 1,
):
    query = select(Part).where(Part.is_active.is_(True))
    if ma:
        query = query.where(Part.ma_linh_kien.ilike(f"%{ma}%"))
    if ten:
        query = query.where(Part.ten_linh_kien.ilike(f"%{ten}%"))
    if hang:
        query = query.where(Part.hang == hang)
    if loai:
        query = query.where(Part.loai == loai)
    if ncc:
        query = query.join(Part.suppliers).where(PartSupplierPrice.nha_cung_cap == ncc)

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    query = query.order_by(Part.updated_at.desc())
    query = query.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    items = db.scalars(query).unique().all()
    return items, total or 0


def get_part(db: Session, part_id: int) -> Part | None:
    return db.get(Part, part_id)


def search_parts_with_prices(db: Session, q: str, limit: int = 20) -> list[Part]:
    """Tìm linh kiện theo tên/mã, dùng cho ô tìm-chọn nhanh khi thêm dòng vào báo giá."""
    if not q or not q.strip():
        return []
    q = q.strip()
    query = (
        select(Part)
        .where(Part.is_active.is_(True))
        .where(Part.ten_linh_kien.ilike(f"%{q}%") | Part.ma_linh_kien.ilike(f"%{q}%"))
        .order_by(Part.ten_linh_kien)
        .limit(limit)
    )
    return db.scalars(query).unique().all()


def create_part(db: Session, data: PartIn) -> Part:
    part = Part(**data.model_dump())
    db.add(part)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Đã có linh kiện khác trùng cả mã linh kiện và hãng này.") from exc
    db.refresh(part)
    return part


def update_part(db: Session, part: Part, data: PartIn) -> Part:
    for field, value in data.model_dump().items():
        setattr(part, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Đã có linh kiện khác trùng cả mã linh kiện và hãng này.") from exc
    db.refresh(part)
    return part


def delete_part(db: Session, part: Part) -> None:
    """Xóa hẳn linh kiện khỏi CSDL (không phải xóa mềm) — theo yêu cầu người dùng 2026-09-21.
    Xóa kèm mọi dòng đang tham chiếu tới linh kiện này trong báo giá/cụm mẫu (nếu có) trước,
    để không để lại tham chiếu "mồ côi" (part_id trỏ tới linh kiện không còn tồn tại) — cùng thứ tự
    phụ thuộc đã dùng khi dọn dữ liệu cũ. Giá/NCC của linh kiện tự động bị xóa theo qua
    cascade "all, delete-orphan" đã khai báo trên Part.suppliers.
    """
    db.execute(sa_delete(QuotePartLine).where(QuotePartLine.part_id == part.id))
    db.execute(sa_delete(StandardGroupLine).where(StandardGroupLine.part_id == part.id))
    db.delete(part)
    db.commit()


def update_part_loai(db: Session, part: Part, loai: str | None) -> Part:
    # Sửa nhanh 1 trường ngay trong bảng danh sách không nên đẩy linh kiện lên đầu danh sách
    # (danh sách sắp theo updated_at) -> cập nhật qua Core update() với updated_at giữ nguyên giá trị cũ,
    # để tránh bị "onupdate" của cột tự động ghi đè thành thời điểm hiện tại.
    db.execute(sa_update(Part).where(Part.id == part.id).values(loai=loai, updated_at=part.updated_at))
    db.commit()
    db.refresh(part)
    return part


def update_part_don_vi(db: Session, part: Part, don_vi: str | None) -> Part:
    db.execute(sa_update(Part).where(Part.id == part.id).values(don_vi=don_vi, updated_at=part.updated_at))
    db.commit()
    db.refresh(part)
    return part


def get_ma_hang_reference(db: Session, max_hang: int = 40, max_ma_per_hang: int = 8) -> list[tuple[str, list[str]]]:
    """Lấy mẫu (hãng, [mã linh kiện...]) từ CSDL hiện có — dùng làm ngữ cảnh tham khảo cho AI khi
    đoán hãng/tên cho 1 mã mới có tiền tố/kiểu đặt mã giống 1 hãng công ty đã từng nhập trước đó.
    """
    rows = db.execute(
        select(Part.hang, Part.ma_linh_kien)
        .where(Part.is_active.is_(True), Part.hang.is_not(None), Part.ma_linh_kien.is_not(None))
        .order_by(Part.hang, Part.id)
    ).all()

    grouped: dict[str, list[str]] = {}
    for hang, ma in rows:
        bucket = grouped.setdefault(hang, [])
        if len(bucket) < max_ma_per_hang:
            bucket.append(ma)

    return list(grouped.items())[:max_hang]


def distinct_values(db: Session, field: str) -> list[str]:
    column = getattr(Part, field)
    rows = db.scalars(
        select(distinct(column)).where(Part.is_active.is_(True)).where(column.is_not(None)).order_by(column)
    ).all()
    return [r for r in rows if r]


def distinct_suppliers(db: Session) -> list[str]:
    rows = db.scalars(
        select(distinct(PartSupplierPrice.nha_cung_cap))
        .where(PartSupplierPrice.is_active.is_(True))
        .order_by(PartSupplierPrice.nha_cung_cap)
    ).all()
    return [r for r in rows if r]


def add_supplier_price(db: Session, part: Part, data: SupplierPriceIn) -> PartSupplierPrice:
    """Thêm giá/NCC đầu tiên cho 1 linh kiện CHƯA có giá — mỗi linh kiện chỉ có tối đa 1 giá/NCC
    (ràng buộc unique part_id), nên hàm này chỉ dùng khi part.price hiện đang là None."""
    price = PartSupplierPrice(part_id=part.id, **data.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


def update_supplier_price(db: Session, price: PartSupplierPrice, data: SupplierPriceIn) -> PartSupplierPrice:
    price.nha_cung_cap = data.nha_cung_cap
    price.don_gia = data.don_gia
    price.ghi_chu = data.ghi_chu
    price.ngay_cap_nhat = datetime.datetime.utcnow()
    db.commit()
    db.refresh(price)
    return price


def delete_supplier_price(db: Session, price: PartSupplierPrice) -> None:
    """Xóa hẳn giá/NCC — đưa linh kiện về trạng thái "chưa có giá" (không phải xóa mềm, vì mỗi
    linh kiện chỉ có tối đa 1 dòng giá nên không có gì để phân biệt "còn dòng khác" nữa)."""
    db.delete(price)
    db.commit()


def _find_part(db: Session, ma_linh_kien: str, hang: str | None) -> Part | None:
    """Định danh 1 linh kiện = (mã linh kiện, hãng). Khác mã HOẶC khác hãng là 2 linh kiện khác nhau."""
    query = select(Part).where(func.lower(Part.ma_linh_kien) == ma_linh_kien.strip().lower())
    if hang:
        return db.scalar(query.where(func.lower(Part.hang) == hang.strip().lower()))
    # Không rõ hãng: nếu đúng 1 linh kiện có mã này thì coi là khớp (best-effort);
    # nếu mã này đã tồn tại ở nhiều hãng khác nhau thì không đủ căn cứ để đoán, không khớp.
    candidates = db.scalars(query).all()
    return candidates[0] if len(candidates) == 1 else None


def _get_supplier_price(db: Session, part_id: int) -> PartSupplierPrice | None:
    """Mỗi linh kiện chỉ có tối đa 1 dòng giá/NCC (ràng buộc unique part_id) — lấy đúng dòng đó."""
    return db.scalar(select(PartSupplierPrice).where(PartSupplierPrice.part_id == part_id))


def find_or_create_part_price(
    db: Session,
    ma_linh_kien: str | None,
    ten_linh_kien: str,
    hang: str | None,
    nha_cung_cap: str | None,
    don_gia: float,
    loai: str | None = None,
    xuat_xu: str | None = None,
    don_vi: str | None = None,
    cap_nhat_gia: bool = True,
) -> tuple[Part, PartSupplierPrice | None, str]:
    """Tìm hoặc tạo 1 linh kiện + giá/NCC DUY NHẤT (2026-09-23: bỏ đa-NCC, mỗi linh kiện chỉ còn
    1 giá/NCC). Dùng chung cho nhập Excel/AI/dán trực tiếp (`apply_candidate`) và khi thêm dòng
    linh kiện bán sẵn nhập tay vào báo giá.

    cap_nhat_gia=False (2026-09-30): linh kiện ĐÃ có giá sẵn trong CSDL nhưng người dùng không tích
    xác nhận đổi giá -> GIỮ NGUYÊN giá/NCC cũ trong CSDL, bỏ qua don_gia/nha_cung_cap mới truyền
    vào. Chỉ có ý nghĩa khi đã có giá sẵn để giữ; linh kiện/giá hoàn toàn mới vẫn luôn được tạo
    đúng theo giá truyền vào (không có "giá cũ" nào để giữ).

    Trả về (part, supplier_price, hành động: created/updated/unchanged) — supplier_price trả về
    LUÔN LÀ giá thực tế đang có trong CSDL sau lệnh gọi này (giá mới nếu vừa cập nhật, giá cũ nếu
    giữ nguyên) — bên gọi nên dùng đúng price.don_gia/price.nha_cung_cap này cho mọi mục đích hiển
    thị/lưu tiếp theo, không dùng lại giá trị don_gia/nha_cung_cap đã truyền vào hàm.
    """
    part = _find_part(db, ma_linh_kien, hang) if ma_linh_kien else None
    if part is None:
        part = Part(
            ma_linh_kien=ma_linh_kien,
            ten_linh_kien=ten_linh_kien,
            hang=hang,
            loai=loai,
            xuat_xu=xuat_xu,
            don_vi=don_vi,
        )
        db.add(part)
        db.flush()
    elif not part.is_active:
        # Linh kiện đã bị xóa (xóa mềm) trước đó nhưng nay lại xuất hiện qua nhập tay/Excel/AI
        # (đúng mã + hãng) -> coi như được thêm lại, khôi phục hiện diện trong danh sách.
        part.is_active = True

    price = _get_supplier_price(db, part.id)
    if price is None:
        price = PartSupplierPrice(part_id=part.id, nha_cung_cap=nha_cung_cap or "", don_gia=don_gia or 0)
        db.add(price)
        db.commit()
        db.refresh(price)
        return part, price, "created"

    if not price.is_active:
        # Giá này từng bị xóa mềm cùng linh kiện, nay khôi phục lại.
        price.is_active = True

    if not cap_nhat_gia:
        db.commit()
        db.refresh(price)
        return part, price, "unchanged"

    changed = price.don_gia != (don_gia or 0) or (price.nha_cung_cap or "") != (nha_cung_cap or "")
    if changed:
        price.nha_cung_cap = nha_cung_cap or ""
        price.don_gia = don_gia or 0
        price.ngay_cap_nhat = datetime.datetime.utcnow()
        db.commit()
        db.refresh(price)
        return part, price, "updated"

    db.commit()
    return part, price, "unchanged"


def classify_candidate(db: Session, row: CandidateRow) -> CandidateRow:
    """Điền status (moi/cap_nhat_gia/khong_doi/bo_qua) cho 1 dòng ứng viên, chưa ghi DB.
    "cap_nhat_gia" giờ bao gồm cả đổi giá LẪN đổi nhà cung cấp (mỗi linh kiện chỉ có 1 NCC/giá
    duy nhất) — row.gia_cu/row.nha_cu lưu giá trị cũ để hiển thị "X → Y" trước khi xác nhận lưu.

    2026-09-30: nếu dòng KHÔNG điền đơn giá (VD ô Excel để trống khi dán) nhưng linh kiện đã có
    giá sẵn trong CSDL, không còn coi là "bo_qua" nữa — tự động lấy đúng giá/NCC hiện có trong
    CSDL vào row (không coi là có thay đổi, vì người dùng không hề đề cập gì tới giá). Chỉ thực sự
    "bo_qua" khi vừa thiếu tên VỪA không có giá nào để dùng (không nhập, không có sẵn trong CSDL).
    """
    if not row.ten_linh_kien:
        row.status = "bo_qua"
        row.ly_do_bo_qua = "Thiếu tên linh kiện"
        return row

    part = _find_part(db, row.ma_linh_kien, row.hang) if row.ma_linh_kien else None
    if part is None or not part.is_active:
        # Linh kiện chưa từng có, hoặc đã bị xóa (xóa mềm) trước đó -> không có giá cũ nào để dùng.
        if row.don_gia is None:
            row.status = "bo_qua"
            row.ly_do_bo_qua = "Thiếu đơn giá (linh kiện chưa có trong CSDL để lấy giá cũ)"
            return row
        row.status = "moi"
        return row

    price = _get_supplier_price(db, part.id)
    if price is None:
        if row.don_gia is None:
            row.status = "bo_qua"
            row.ly_do_bo_qua = "Thiếu đơn giá (linh kiện chưa có giá trong CSDL)"
            return row
        row.status = "moi"
        return row

    row.gia_cu = price.don_gia
    row.nha_cu = price.nha_cung_cap or None

    if row.don_gia is None:
        # Không điền giá -> lấy đúng giá/NCC hiện có trong CSDL, không báo "đổi giá".
        row.don_gia = price.don_gia
        if not row.nha_cung_cap:
            row.nha_cung_cap = price.nha_cung_cap or None
        row.status = "khong_doi"
        return row

    gia_doi = price.don_gia != row.don_gia
    ncc_doi = (row.nha_cung_cap or "") != (price.nha_cung_cap or "")
    row.status = "cap_nhat_gia" if (gia_doi or ncc_doi) else "khong_doi"
    return row


def apply_candidate(db: Session, row: CandidateRow) -> str:
    """Ghi 1 dòng ứng viên đã được người dùng xác nhận vào DB. Trả về hành động đã thực hiện."""
    _part, _price, action = find_or_create_part_price(
        db,
        ma_linh_kien=row.ma_linh_kien,
        ten_linh_kien=row.ten_linh_kien,
        hang=row.hang,
        nha_cung_cap=row.nha_cung_cap,
        don_gia=row.don_gia or 0,
        loai=row.loai,
        xuat_xu=row.xuat_xu,
        don_vi=row.don_vi,
    )
    return action
