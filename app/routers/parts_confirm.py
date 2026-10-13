from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as crud
from app.db.database import get_db
from app.schemas.parts import CandidateRow

router = APIRouter(prefix="/linh-kien/nhap")


@router.post("/xac-nhan")
async def confirm(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    row_count = int(form.get("row_count", 0))

    ket_qua = {"moi": 0, "cap_nhat_gia": 0, "khong_doi": 0, "bo_qua": 0, "loi": 0}
    for i in range(row_count):
        if not form.get(f"row_{i}_include"):
            continue
        don_gia_raw = form.get(f"row_{i}_don_gia") or ""
        try:
            don_gia = float(don_gia_raw) if don_gia_raw else None
        except ValueError:
            don_gia = None

        row = CandidateRow(
            status="?",
            ten_linh_kien=form.get(f"row_{i}_ten_linh_kien") or None,
            ma_linh_kien=form.get(f"row_{i}_ma_linh_kien") or None,
            loai=form.get(f"row_{i}_loai") or None,
            hang=form.get(f"row_{i}_hang") or None,
            xuat_xu=form.get(f"row_{i}_xuat_xu") or None,
            nha_cung_cap=form.get(f"row_{i}_nha_cung_cap") or None,
            don_vi=form.get(f"row_{i}_don_vi") or None,
            don_gia=don_gia,
        )
        if not row.ten_linh_kien or row.don_gia is None:
            ket_qua["loi"] += 1
            continue

        action = crud.apply_candidate(db, row)
        if action == "created":
            ket_qua["moi"] += 1
        elif action == "updated":
            ket_qua["cap_nhat_gia"] += 1
        elif action == "unchanged":
            ket_qua["khong_doi"] += 1

    return templates.TemplateResponse(
        request, "parts/import_result.html", {"active_page": "parts", "ket_qua": ket_qua}
    )
