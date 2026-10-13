from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud.settings import get_settings, update_settings
from app.db.database import get_db
from app.services.ai_extract import PROVIDER_LABELS

router = APIRouter(prefix="/cai-dat")


@router.get("")
def show_settings(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"active_page": "settings", "settings": settings, "provider_labels": PROVIDER_LABELS, "saved": False},
    )


@router.post("")
def save_settings(
    request: Request,
    active_provider: str = Form(...),
    claude_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    gemini_api_key: str = Form(""),
    deepseek_api_key: str = Form(""),
    db: Session = Depends(get_db),
):
    settings = update_settings(
        db,
        active_provider=active_provider,
        claude_api_key=claude_api_key,
        openai_api_key=openai_api_key,
        gemini_api_key=gemini_api_key,
        deepseek_api_key=deepseek_api_key,
    )
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"active_page": "settings", "settings": settings, "provider_labels": PROVIDER_LABELS, "saved": True},
    )
