from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as crud
from app.crud.settings import get_settings
from app.db.database import get_db
from app.schemas.parts import CandidateRow
from app.services import ai_extract, doc_extract

router = APIRouter(prefix="/linh-kien/nhap-ai")


def _provider_context(db: Session) -> dict:
    settings = get_settings(db)
    return {
        "active_provider": ai_extract.PROVIDER_LABELS.get(settings.active_provider, settings.active_provider),
        "supports_vision": ai_extract.PROVIDER_SUPPORTS_VISION.get(settings.active_provider, False),
    }


@router.get("")
def form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "parts/import_ai.html",
        {"active_page": "parts", "error": None, "message": "", **_provider_context(db)},
    )


@router.post("/xem-truoc")
async def preview(
    request: Request,
    message: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    image_bytes = None
    image_mime = None
    if file is not None and file.filename:
        try:
            extra_text, image_bytes, image_mime = await doc_extract.resolve_ai_upload(file)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "parts/import_ai.html",
                {"active_page": "parts", "error": str(exc), "message": message, **_provider_context(db)},
            )
        if extra_text:
            message = f"{message}\n\n{extra_text}" if message.strip() else extra_text

    if not message.strip() and not image_bytes:
        return templates.TemplateResponse(
            request,
            "parts/import_ai.html",
            {
                "active_page": "parts",
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
            "parts/import_ai.html",
            {
                "active_page": "parts",
                "error": str(exc),
                "message": message,
                **_provider_context(db),
            },
        )

    if not raw_rows:
        return templates.TemplateResponse(
            request,
            "parts/import_ai.html",
            {
                "active_page": "parts",
                "error": "AI không tách được linh kiện nào từ nội dung đã gửi. Thử diễn giải rõ hơn hoặc ảnh rõ hơn.",
                "message": message,
                **_provider_context(db),
            },
        )

    rows = [crud.classify_candidate(db, CandidateRow(status="?", **r)) for r in raw_rows]
    return templates.TemplateResponse(
        request,
        "parts/preview.html",
        {
            "active_page": "parts",
            "rows": rows,
            "nguon": "Nhập nhanh bằng AI",
            "loai_options": crud.LOAI_OPTIONS,
        },
    )
