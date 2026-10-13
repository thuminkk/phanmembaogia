from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as parts_crud
from app.crud import standard_groups as crud
from app.crud.settings import get_settings
from app.db.database import get_db
from app.schemas.parts import CandidateRow
from app.services import ai_extract, doc_extract

router = APIRouter(prefix="/cum-tieu-chuan")


def _provider_context(db: Session) -> dict:
    settings = get_settings(db)
    return {
        "active_provider": ai_extract.PROVIDER_LABELS.get(settings.active_provider, settings.active_provider),
        "supports_vision": ai_extract.PROVIDER_SUPPORTS_VISION.get(settings.active_provider, False),
    }


@router.get("/{group_id:int}/nhap-ai")
def ai_import_form(request: Request, group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    return templates.TemplateResponse(
        request,
        "standard_groups/ai_import.html",
        {"active_page": "standard_groups", "group": group, "error": None, "message": "", **_provider_context(db)},
    )


@router.post("/{group_id:int}/nhap-ai/xem-truoc")
async def ai_import_preview(
    request: Request,
    group_id: int,
    message: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    group = crud.get_group(db, group_id)
    image_bytes = None
    image_mime = None
    if file is not None and file.filename:
        try:
            extra_text, image_bytes, image_mime = await doc_extract.resolve_ai_upload(file)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "standard_groups/ai_import.html",
                {"active_page": "standard_groups", "group": group, "error": str(exc), "message": message, **_provider_context(db)},
            )
        if extra_text:
            message = f"{message}\n\n{extra_text}" if message.strip() else extra_text

    if not message.strip() and not image_bytes:
        return templates.TemplateResponse(
            request,
            "standard_groups/ai_import.html",
            {
                "active_page": "standard_groups",
                "group": group,
                "error": "Cần dán tin nhắn hoặc tải lên/dán 1 ảnh, PDF, Excel.",
                "message": message,
                **_provider_context(db),
            },
        )

    try:
        raw_rows = ai_extract.extract_candidates(db, message, image_bytes=image_bytes, image_mime=image_mime)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "standard_groups/ai_import.html",
            {
                "active_page": "standard_groups",
                "group": group,
                "error": str(exc),
                "message": message,
                **_provider_context(db),
            },
        )

    if not raw_rows:
        return templates.TemplateResponse(
            request,
            "standard_groups/ai_import.html",
            {
                "active_page": "standard_groups",
                "group": group,
                "error": "AI không tách được linh kiện nào từ nội dung đã gửi.",
                "message": message,
                **_provider_context(db),
            },
        )

    rows = [parts_crud.classify_candidate(db, CandidateRow(status="?", **r)) for r in raw_rows]
    return templates.TemplateResponse(
        request,
        "standard_groups/ai_preview.html",
        {
            "active_page": "standard_groups",
            "group": group,
            "rows": rows,
            "loai_options": parts_crud.LOAI_OPTIONS,
        },
    )


@router.post("/{group_id:int}/nhap-ai/xac-nhan")
async def ai_import_confirm(request: Request, group_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    row_count = int(form.get("row_count", 0))

    ket_qua = {"moi": 0, "loi": 0}
    for i in range(row_count):
        if not form.get(f"row_{i}_include"):
            continue
        ten_linh_kien = form.get(f"row_{i}_ten_linh_kien") or ""
        don_gia_raw = form.get(f"row_{i}_don_gia") or ""
        try:
            # Chưa rõ giá (VD nhập theo catalogue, chưa có báo giá NCC) -> mặc định 0đ, không chặn lưu —
            # khớp với hành vi form "Thêm dòng" nhập tay (đã cho phép don_gia=0 từ trước), giá có thể
            # cập nhật lại sau khi có báo giá NCC thật.
            don_gia = float(don_gia_raw) if don_gia_raw else 0
        except ValueError:
            don_gia = 0
        try:
            so_luong = float(form.get(f"row_{i}_so_luong") or "1")
        except ValueError:
            so_luong = 1

        if not ten_linh_kien:
            ket_qua["loi"] += 1
            continue

        crud.add_line(
            db,
            group_id,
            part_id=None,
            supplier_price_id=None,
            ten_linh_kien=ten_linh_kien,
            ma_linh_kien=form.get(f"row_{i}_ma_linh_kien") or None,
            loai=form.get(f"row_{i}_loai") or None,
            hang=form.get(f"row_{i}_hang") or None,
            nha_cung_cap=form.get(f"row_{i}_nha_cung_cap") or None,
            don_vi=form.get(f"row_{i}_don_vi") or None,
            don_gia=don_gia,
            so_luong=so_luong,
            ghi_chu=None,
        )
        ket_qua["moi"] += 1

    return templates.TemplateResponse(
        request,
        "standard_groups/ai_result.html",
        {"active_page": "standard_groups", "group_id": group_id, "ket_qua": ket_qua},
    )
