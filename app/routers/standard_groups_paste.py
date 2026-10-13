import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as crud
from app.crud import standard_groups as groups_crud
from app.db.database import get_db
from app.schemas.parts import CandidateRow

router = APIRouter(prefix="/cum-tieu-chuan")

# Cùng thứ tự cột như /linh-kien/nhap-dan (Tên/Mã/Hãng/Loại/Đơn vị khớp bảng danh sách Linh kiện),
# bỏ Xuất xứ vì cụm mẫu không dùng cột đó, Số lượng đặt trước Đơn giá — dán xong dùng chung khung
# xem trước standard_groups/ai_preview.html (SL đọc từ row.so_luong nếu có, về 1 nếu không) và
# chung nút "Xác nhận thêm vào cụm mẫu" (nhap-ai/xac-nhan) với luồng nhập AI.
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


@router.get("/{group_id:int}/nhap-dan")
def form(request: Request, group_id: int, db: Session = Depends(get_db)):
    group = groups_crud.get_group(db, group_id)
    return templates.TemplateResponse(
        request,
        "standard_groups/import_paste.html",
        {
            "active_page": "standard_groups",
            "group": group,
            "columns": COLUMNS,
            "starter_rows": STARTER_ROWS,
            "error": None,
        },
    )


@router.post("/{group_id:int}/nhap-dan/xem-truoc")
async def preview(request: Request, group_id: int, db: Session = Depends(get_db)):
    group = groups_crud.get_group(db, group_id)
    form = await request.form()
    row_count = int(form.get("row_count", 0))

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

        loai = (form.get(f"row_{i}_loai") or "").strip() or None
        if loai not in crud.LOAI_OPTIONS:
            loai = None

        so_luong_raw = re.sub(r"[^\d.]", "", form.get(f"row_{i}_so_luong") or "")
        try:
            so_luong = float(so_luong_raw) if so_luong_raw else 1
        except ValueError:
            so_luong = 1

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
            "standard_groups/import_paste.html",
            {
                "active_page": "standard_groups",
                "group": group,
                "columns": COLUMNS,
                "starter_rows": STARTER_ROWS,
                "error": "Chưa có dòng dữ liệu nào — dán dữ liệu vào khung rồi thử lại.",
            },
        )

    return templates.TemplateResponse(
        request,
        "standard_groups/ai_preview.html",
        {
            "active_page": "standard_groups",
            "group": group,
            "rows": rows,
            "loai_options": crud.LOAI_OPTIONS,
        },
    )
