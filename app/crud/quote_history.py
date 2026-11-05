"""Quay lại / Tiếp cho tab Linh kiện của báo giá — áp dụng cho MỌI thao tác (sửa ô, thêm/xóa dòng, đổi cụm,
kéo thả, thay linh kiện, áp dụng cụm mẫu, nhập AI, BOM AI...).

Cách làm: middleware `record_changes` (app/main.py) chụp toàn bộ cụm + dòng linh kiện của báo giá trước
và sau mỗi POST làm thay đổi tab này; nếu có khác biệt thì lưu bản TRƯỚC vào ngăn "undo". Quay lại =
khôi phục bản chụp đó (giữ nguyên id cũ của cụm/dòng). Chỉ khôi phục dữ liệu của báo giá — CSDL linh
kiện (giá/NCC) không bị quay lại.
"""
import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import QuoteComponentGroup, QuoteHistory, QuotePartLine

MAX_UNDO = 50
FIELD_LABELS = {
    "ten_linh_kien": "Tên", "ma_linh_kien": "Mã", "hang": "Hãng", "don_vi": "Đ.vị", "so_luong": "SL",
    "don_gia": "Giá", "nha_cung_cap": "NCC", "ghi_chu": "Ghi chú",
}


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def snapshot(db: Session, quote_id: int) -> str:
    groups = db.scalars(select(QuoteComponentGroup).where(QuoteComponentGroup.quote_id == quote_id).order_by(QuoteComponentGroup.id))
    lines = db.scalars(select(QuotePartLine).where(QuotePartLine.quote_id == quote_id).order_by(QuotePartLine.id))
    return json.dumps({"groups": [_row(g) for g in groups], "lines": [_row(l) for l in lines]}, ensure_ascii=False)


def _restore(db: Session, quote_id: int, data: str) -> None:
    state = json.loads(data)
    db.execute(delete(QuotePartLine).where(QuotePartLine.quote_id == quote_id))
    db.execute(delete(QuoteComponentGroup).where(QuoteComponentGroup.quote_id == quote_id))
    db.flush()
    db.expunge_all()

    def taken(model, id_):
        return db.scalar(select(model.id).where(model.id == id_)) is not None

    # Giữ đúng id cũ (BOM AI, kéo thả... tham chiếu theo id); hiếm khi id đó đã bị dùng cho chỗ khác thì cấp id mới.
    gid_map = {}
    for g in state["groups"]:
        old_id = g["id"]
        if taken(QuoteComponentGroup, old_id):
            obj = QuoteComponentGroup(**{k: v for k, v in g.items() if k != "id"})
        else:
            obj = QuoteComponentGroup(**g)
        db.add(obj)
        db.flush()
        gid_map[old_id] = obj.id
    for l in state["lines"]:
        l = dict(l, group_id=gid_map.get(l["group_id"]) if l["group_id"] else None)
        if taken(QuotePartLine, l["id"]):
            l.pop("id")
        db.add(QuotePartLine(**l))
    db.flush()


def describe(before: str, after: str) -> str:
    """Mô tả ngắn thao tác từ khác biệt giữa 2 bản chụp — hiện trên nút Quay lại / Tiếp."""
    b, a = json.loads(before), json.loads(after)
    bl, al = {l["id"]: l for l in b["lines"]}, {l["id"]: l for l in a["lines"]}
    bg, ag = {g["id"]: g for g in b["groups"]}, {g["id"]: g for g in a["groups"]}
    parts = []
    added, removed = [i for i in al if i not in bl], [i for i in bl if i not in al]
    if added:
        parts.append(f"Thêm {len(added)} dòng" if len(added) > 1 else f"Thêm «{al[added[0]]['ten_linh_kien']}»")
    if removed:
        parts.append(f"Xóa {len(removed)} dòng" if len(removed) > 1 else f"Xóa «{bl[removed[0]]['ten_linh_kien']}»")
    g_added, g_removed = [i for i in ag if i not in bg], [i for i in bg if i not in ag]
    if g_added:
        parts.append("Thêm cụm " + ", ".join(f"«{ag[i]['ten_cum']}»" for i in g_added))
    if g_removed:
        parts.append("Xóa cụm " + ", ".join(f"«{bg[i]['ten_cum']}»" for i in g_removed))
    for i in ag:
        if i in bg and ag[i]["ten_cum"] != bg[i]["ten_cum"]:
            parts.append(f"Đổi tên cụm «{bg[i]['ten_cum']}» → «{ag[i]['ten_cum']}»")
        elif i in bg and ag[i] != bg[i] and ag[i]["thu_tu"] == bg[i]["thu_tu"]:
            parts.append(f"Sửa mô tả cụm «{ag[i]['ten_cum']}»")
    if any(i in bg and ag[i]["thu_tu"] != bg[i]["thu_tu"] for i in ag) and not g_added and not g_removed:
        parts.append("Di chuyển cụm")
    common = [i for i in al if i in bl]
    # Dòng của cụm vừa xóa tự về "Chưa phân cụm" — đã nằm trong "Xóa cụm", không tính là chuyển cụm.
    moved = [i for i in common if al[i]["group_id"] != bl[i]["group_id"] and bl[i]["group_id"] not in g_removed]
    if moved:
        parts.append(f"Chuyển {len(moved)} dòng sang cụm khác")
    edits = []
    for i in common:
        for f, lbl in FIELD_LABELS.items():
            if al[i][f] != bl[i][f]:
                fmt = {"so_luong": lambda v: f"{v:g}", "don_gia": lambda v: f"{v:,.0f}"}.get(f, lambda v: v or "")
                edits.append(f"Sửa {lbl} «{bl[i]['ten_linh_kien']}»: {fmt(bl[i][f])} → {fmt(al[i][f])}")
    for i in common:
        if (al[i]["part_id"] is None) != (bl[i]["part_id"] is None):
            verb = "Chuyển tự do" if al[i]["part_id"] is None else "Gắn CSDL"
            edits.append(f"{verb} «{al[i]['ten_linh_kien']}»")
    if len(edits) == 1:
        parts.append(edits[0])
    elif edits:
        parts.append(f"Sửa {len(edits)} ô")
    if not parts and any(al[i]["thu_tu"] != bl[i]["thu_tu"] for i in common):
        parts.append("Sắp xếp lại dòng")
    label = "; ".join(parts) or "Thay đổi linh kiện"
    return label if len(label) <= 250 else label[:247] + "..."


def record(db: Session, quote_id: int, before: str) -> None:
    """Gọi SAU 1 thao tác: nếu dữ liệu đã đổi so với `before` thì lưu `before` vào ngăn Quay lại, xóa ngăn Tiếp."""
    after = snapshot(db, quote_id)
    if after == before:
        return
    db.add(QuoteHistory(quote_id=quote_id, kind="undo", label=describe(before, after), data=before))
    db.execute(delete(QuoteHistory).where(QuoteHistory.quote_id == quote_id, QuoteHistory.kind == "redo"))
    old = db.scalars(
        select(QuoteHistory.id).where(QuoteHistory.quote_id == quote_id, QuoteHistory.kind == "undo")
        .order_by(QuoteHistory.id.desc()).offset(MAX_UNDO)
    ).all()
    if old:
        db.execute(delete(QuoteHistory).where(QuoteHistory.id.in_(old)))
    db.commit()


def _top(db: Session, quote_id: int, kind: str) -> QuoteHistory | None:
    return db.scalars(
        select(QuoteHistory).where(QuoteHistory.quote_id == quote_id, QuoteHistory.kind == kind)
        .order_by(QuoteHistory.id.desc()).limit(1)
    ).first()


def _step(db: Session, quote_id: int, src: str, dst: str) -> str | None:
    entry = _top(db, quote_id, src)
    if entry is None:
        return None
    label, data = entry.label, entry.data
    db.add(QuoteHistory(quote_id=quote_id, kind=dst, label=label, data=snapshot(db, quote_id)))
    db.delete(entry)
    db.flush()
    _restore(db, quote_id, data)
    db.commit()
    return label


def undo(db: Session, quote_id: int) -> str | None:
    return _step(db, quote_id, "undo", "redo")


def redo(db: Session, quote_id: int) -> str | None:
    return _step(db, quote_id, "redo", "undo")


def status(db: Session, quote_id: int) -> dict:
    u, r = _top(db, quote_id, "undo"), _top(db, quote_id, "redo")
    return {"undo": u.label if u else None, "redo": r.label if r else None}
