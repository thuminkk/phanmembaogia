"""Lưu trữ cho tính năng Tự lên BOM bằng AI (BomRequest) và kho kinh nghiệm AI (AiExperience)."""
import datetime
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import quotes as quotes_crud
from app.db.models import AiExperience, BomRequest, QuoteComponentGroup


def list_requests(db: Session, quote_id: int) -> list[BomRequest]:
    return db.scalars(
        select(BomRequest).where(BomRequest.quote_id == quote_id).order_by(BomRequest.id.desc())
    ).all()


def get_request(db: Session, quote_id: int, req_id: int) -> BomRequest | None:
    req = db.get(BomRequest, req_id)
    return req if req is not None and req.quote_id == quote_id else None


def last_form(db: Session, quote_id: int) -> dict:
    req = db.scalars(
        select(BomRequest).where(BomRequest.quote_id == quote_id).order_by(BomRequest.id.desc()).limit(1)
    ).first()
    return json.loads(req.form_json) if req else {}


def create_request(db: Session, quote_id: int, form_data: dict, proposal: dict, provider: str) -> BomRequest:
    req = BomRequest(
        quote_id=quote_id,
        form_json=json.dumps(form_data, ensure_ascii=False),
        proposal_json=json.dumps(proposal, ensure_ascii=False),
        provider=provider,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def apply_request(db: Session, req: BomRequest, groups: list[dict]) -> int:
    """groups: [{"ten_cum", "target_group_id" (None = tạo cụm mới), "dong": [item đề xuất kèm "sl" đã sửa]}].
    Dòng có part_id lấy giá hiện tại trong CSDL; dòng "moi" (chưa có trong CSDL) được tạo linh kiện mới 0đ
    để người dùng xin giá rồi cập nhật sau. Trả về số dòng đã thêm."""
    applied = json.loads(req.applied_json or "{}")
    group_ids: list[int] = applied.get("group_ids", [])
    cum_group_ids: list[int | None] = []  # cụm đề xuất thứ i -> id cụm báo giá (để so diff khi rút kinh nghiệm)
    added = 0
    for g in groups:
        if not g["dong"]:
            cum_group_ids.append(None)
            continue
        target = db.get(QuoteComponentGroup, g["target_group_id"]) if g["target_group_id"] else None
        if target is None or target.quote_id != req.quote_id:
            target = quotes_crud.add_group(db, req.quote_id, g["ten_cum"] or "Cụm mới")
        catalog_items = [(d["part_id"], d["sl"]) for d in g["dong"] if d.get("part_id")]
        added += quotes_crud.add_part_lines_from_catalog(db, req.quote_id, catalog_items, target.id)
        for d in g["dong"]:
            if d.get("part_id"):
                continue
            quotes_crud.add_part_line(
                db, req.quote_id, part_id=None, supplier_price_id=None,
                ten_linh_kien=d["ten"], ma_linh_kien=d.get("ma") or None, hang=d.get("hang") or None,
                nha_cung_cap=None, don_vi=d.get("don_vi") or None, don_gia=0, so_luong=d["sl"],
                ghi_chu=d.get("ly_do") or None, group_id=target.id, cap_nhat_gia=False,
            )
            added += 1
        if target.id not in group_ids:
            group_ids.append(target.id)
        cum_group_ids.append(target.id)
    req.applied_json = json.dumps({"group_ids": group_ids, "cum_group_ids": cum_group_ids})
    req.applied_at = datetime.datetime.utcnow()
    db.commit()
    return added


# ---- Kinh nghiệm AI ----


def list_experiences(db: Session) -> list[AiExperience]:
    return db.scalars(select(AiExperience).order_by(AiExperience.is_active.desc(), AiExperience.nhom, AiExperience.id)).all()


def add_experience(db: Session, nhom: str | None, noi_dung: str, nguon: str = "tay", bom_request_id: int | None = None) -> AiExperience:
    exp = AiExperience(nhom=nhom or "Chung", noi_dung=noi_dung.strip(), nguon=nguon, bom_request_id=bom_request_id)
    db.add(exp)
    db.commit()
    return exp


def update_experience(db: Session, exp: AiExperience, nhom: str | None, noi_dung: str, is_active: bool) -> None:
    exp.nhom = nhom or "Chung"
    exp.noi_dung = noi_dung.strip()
    exp.is_active = is_active
    db.commit()


def delete_experience(db: Session, exp: AiExperience) -> None:
    db.delete(exp)
    db.commit()
