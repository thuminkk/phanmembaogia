import io
import re

import openpyxl
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as crud
from app.db.database import get_db
from app.schemas.parts import CandidateRow

router = APIRouter(prefix="/linh-kien/nhap-dan")

# Cùng thứ tự cột cố định hiển thị trên khung dán — không cho người dùng đổi thứ tự,
# vì paste dạng bảng cần khớp đúng cột nguồn từ Excel. Thứ tự khớp với bảng danh sách Linh kiện
# (/linh-kien: Tên linh kiện, Mã linh kiện, Hãng, Loại, Đơn vị...) để không bị lẫn cột khi đối chiếu.
COLUMNS = [
    ("ten_linh_kien", "Tên linh kiện"),
    ("ma_linh_kien", "Mã linh kiện"),
    ("hang", "Hãng"),
    ("loai", "Loại"),
    ("don_vi", "Đơn vị"),
    ("nha_cung_cap", "Nhà cung cấp"),
    ("don_gia", "Đơn giá (VND)"),
    ("xuat_xu", "Xuất xứ"),
]
STARTER_ROWS = 15


@router.get("")
def form(request: Request):
    return templates.TemplateResponse(
        request,
        "parts/import_paste.html",
        {"active_page": "parts", "columns": COLUMNS, "starter_rows": STARTER_ROWS, "error": None},
    )


@router.get("/mau.xlsx")
def download_sample():
    """File Excel mẫu chỉ có đúng dòng tiêu đề theo thứ tự cột cố định — để người dùng tự định dạng
    dữ liệu của mình theo đúng cột trước khi copy/dán vào khung."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Linh kien"
    ws.append([label for _field, label in COLUMNS])
    for col_idx in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = 20

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=mau_nhap_linh_kien.xlsx"},
    )


@router.post("/xem-truoc")
async def preview(request: Request, db: Session = Depends(get_db)):
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

        row = CandidateRow(
            status="?",
            ten_linh_kien=ten_linh_kien,
            ma_linh_kien=ma_linh_kien,
            loai=loai,
            hang=(form.get(f"row_{i}_hang") or "").strip() or None,
            xuat_xu=(form.get(f"row_{i}_xuat_xu") or "").strip() or None,
            nha_cung_cap=(form.get(f"row_{i}_nha_cung_cap") or "").strip() or None,
            don_vi=(form.get(f"row_{i}_don_vi") or "").strip() or None,
            don_gia=don_gia,
        )
        rows.append(crud.classify_candidate(db, row))

    if not rows:
        return templates.TemplateResponse(
            request,
            "parts/import_paste.html",
            {
                "active_page": "parts",
                "columns": COLUMNS,
                "starter_rows": STARTER_ROWS,
                "error": "Chưa có dòng dữ liệu nào — dán dữ liệu vào khung rồi thử lại.",
            },
        )

    return templates.TemplateResponse(
        request,
        "parts/preview.html",
        {
            "active_page": "parts",
            "rows": rows,
            "nguon": "Dán trực tiếp từ Excel",
            "loai_options": crud.LOAI_OPTIONS,
        },
    )
