from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import parts as parts_crud
from app.crud import quotes as quotes_crud
from app.db.models import Part, PartSupplierPrice, StandardGroup, StandardGroupLine


def list_groups(db: Session) -> list[StandardGroup]:
    return db.scalars(
        select(StandardGroup).where(StandardGroup.is_active.is_(True)).order_by(StandardGroup.ten_cum)
    ).all()


def get_group(db: Session, group_id: int) -> StandardGroup | None:
    return db.get(StandardGroup, group_id)


def create_group(db: Session, ten_cum: str, mo_ta: str | None) -> StandardGroup:
    group = StandardGroup(ten_cum=ten_cum, mo_ta=mo_ta)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_group(db: Session, group: StandardGroup, ten_cum: str, mo_ta: str | None) -> StandardGroup:
    group.ten_cum = ten_cum
    group.mo_ta = mo_ta
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group: StandardGroup) -> None:
    group.is_active = False
    db.commit()


def clone_group(db: Session, source_group_id: int, ten_cum: str, mo_ta: str | None) -> StandardGroup:
    """Copy 1 cụm mẫu có sẵn thành 1 cụm mới để sửa nhanh — copy nguyên part_id/supplier_price_id
    (giá vẫn luôn lấy LIVE từ CSDL khi áp dụng vào báo giá, không đóng băng lúc copy)."""
    source = db.get(StandardGroup, source_group_id)
    new_group = StandardGroup(ten_cum=ten_cum, mo_ta=mo_ta)
    db.add(new_group)
    db.flush()

    for line in source.lines:
        db.add(
            StandardGroupLine(
                standard_group_id=new_group.id,
                part_id=line.part_id,
                supplier_price_id=line.supplier_price_id,
                so_luong=line.so_luong,
                ghi_chu=line.ghi_chu,
            )
        )
    db.commit()
    db.refresh(new_group)
    return new_group


def add_line(
    db: Session,
    standard_group_id: int,
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
    loai: str | None = None,
) -> StandardGroupLine:
    if part_id and supplier_price_id:
        part = db.get(Part, part_id)
        price = db.get(PartSupplierPrice, supplier_price_id)
    else:
        part, price, _action = parts_crud.find_or_create_part_price(
            db,
            ma_linh_kien=ma_linh_kien,
            ten_linh_kien=ten_linh_kien,
            hang=hang,
            nha_cung_cap=nha_cung_cap,
            don_gia=don_gia,
            don_vi=don_vi,
            loai=loai,
        )
    line = StandardGroupLine(
        standard_group_id=standard_group_id,
        part_id=part.id,
        supplier_price_id=price.id,
        so_luong=so_luong,
        ghi_chu=ghi_chu,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def update_line(db: Session, line: StandardGroupLine, *, so_luong: float, ghi_chu: str | None) -> StandardGroupLine:
    # NCC/giá không sửa ở đây nữa — mỗi linh kiện chỉ có 1 giá/NCC duy nhất, luôn lấy từ
    # PartSupplierPrice hiện tại của part_id (line.supplier_price_id trỏ sẵn đúng dòng đó,
    # không cần chọn lại). Sửa giá/NCC thì vào trang Linh kiện (CSDL) sửa trực tiếp.
    line.so_luong = so_luong
    line.ghi_chu = ghi_chu
    db.commit()
    db.refresh(line)
    return line


def delete_line(db: Session, line: StandardGroupLine) -> None:
    db.delete(line)
    db.commit()


def apply_group_to_quote(db: Session, quote_id: int, standard_group_id: int) -> int:
    """Tạo 1 QuoteComponentGroup mới trong báo giá đích, copy các dòng — luôn lấy giá NCC HIỆN TẠI
    (không đóng băng giá lúc tạo cụm chuẩn). Trả về id của cụm vừa tạo trong báo giá."""
    standard_group = db.get(StandardGroup, standard_group_id)
    new_group = quotes_crud.add_group(db, quote_id, standard_group.ten_cum)

    for line in standard_group.lines:
        quotes_crud.add_part_line(
            db,
            quote_id,
            group_id=new_group.id,
            part_id=line.part_id,
            supplier_price_id=line.supplier_price_id,
            ten_linh_kien=line.part.ten_linh_kien,
            ma_linh_kien=line.part.ma_linh_kien,
            hang=line.part.hang,
            nha_cung_cap=line.supplier_price.nha_cung_cap,
            don_vi=line.part.don_vi,
            don_gia=line.supplier_price.don_gia,
            so_luong=line.so_luong,
            ghi_chu=line.ghi_chu,
        )
    return new_group.id
