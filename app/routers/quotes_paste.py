import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as crud
from app.crud import quotes as quotes_crud
from app.db.database import get_db
from app.schemas.parts import CandidateRow

router = APIRouter(prefix="/bao-gia")

# Cùng thứ tự cột như /cum-tieu-chuan/{id}/nhap-dan — Tên/Mã/Hãng/Loại/Đơn vị khớp bảng danh sách
# Linh kiện, Số lượng đặt trước Đơn giá — dán xong dùng chung khung xem trước quotes/ai_preview.html
# và chung nút "Xác nhận thêm vào báo giá" (nhap-ai/xac-nhan) với luồng nhập AI.
COLUMNS = [
    ("ten_linh_kien", "Tên linh kiện"),
    ("ma_linh_kien", "Mã linh kiện"),
    ("hang", "Hãng"),
    ("loai", "Loại"),
    ("don_vi", "Đơn vị"),
    ("nha_cung_cap", "Nhà cung cấp"),
    ("so_luong", "Số lượng"),
    ("don_gia", "Đơn giá (VND)"),
]
STARTER_ROWS = 15


@router.get("/{quote_id:int}/linh-kien/nhap-dan")
def form(request: Request, quote_id: int, db: Session = Depends(get_db)):
    quote = quotes_crud.get_quote(db, quote_id)
    return templates.TemplateResponse(
        request,
        "quotes/import_paste.html",
        {
            "active_page": "projects",
            "quote": quote,
            "columns": COLUMNS,
            "starter_rows": STARTER_ROWS,
            "error": None,
        },
    )


@router.post("/{quote_id:int}/linh-kien/nhap-dan/xem-truoc")
async def preview(request: Request, quote_id: int, db: Session = Depends(get_db)):
    quote = quotes_crud.get_quote(db, quote_id)
    form = await request.form()
    row_count = int(form.get("row_count", 0))
    group_id = form.get("group_id") or ""

    rows = []
    for i in range(row_count):
        ten_linh_kien = (form.get(f"row_{i}_ten_linh_kien") or "").strip() or None
        ma_linh_kien = (form.get(f"row_{i}_ma_linh_kien") or "").strip() or None
        if not ten_linh_kien and not ma_linh_kien:
            continue  # dòng trống trong khung dán, bỏ qua không đưa vào bảng xem trước

        don_gia_raw = re.sub(r"[^\d.]", "", form.get(f"row_{i}_don_gia") or "")
        try:
            don_gia = float(don_gia_raw) if don_gia_raw else None
        except ValueError:
            don_gia = None

        so_luong_raw = re.sub(r"[^\d.]", "", form.get(f"row_{i}_so_luong") or "")
        try:
            so_luong = float(so_luong_raw) if so_luong_raw else None
        except ValueError:
            so_luong = None

        loai = (form.get(f"row_{i}_loai") or "").strip() or None
        if loai not in crud.LOAI_OPTIONS:
            loai = None

        row = CandidateRow(
            status="?",
            ten_linh_kien=ten_linh_kien,
            ma_linh_kien=ma_linh_kien,
            loai=loai,
            hang=(form.get(f"row_{i}_hang") or "").strip() or None,
            nha_cung_cap=(form.get(f"row_{i}_nha_cung_cap") or "").strip() or None,
            don_vi=(form.get(f"row_{i}_don_vi") or "").strip() or None,
            don_gia=don_gia,
            so_luong=so_luong,
        )
        rows.append(crud.classify_candidate(db, row))

    if not rows:
        return templates.TemplateResponse(
            request,
            "quotes/import_paste.html",
            {
                "active_page": "projects",
                "quote": quote,
                "columns": COLUMNS,
                "starter_rows": STARTER_ROWS,
                "error": "Chưa có dòng dữ liệu nào — dán dữ liệu vào khung rồi thử lại.",
            },
        )

    return templates.TemplateResponse(
        request,
        "quotes/ai_preview.html",
        {
            "active_page": "projects",
            "quote": quote,
            "rows": rows,
            "group_id": group_id,
            "loai_options": crud.LOAI_OPTIONS,
        },
    )
