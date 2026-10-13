import itertools

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import quotes as crud
from app.db.database import get_db

router = APIRouter(prefix="/mau-bao-gia")


@router.get("")
def list_templates(request: Request, db: Session = Depends(get_db)):
    items = crud.list_templates(db)
    groups = [
        (khach_hang or "Chưa gắn khách hàng", list(rows))
        for khach_hang, rows in itertools.groupby(items, key=lambda q: q.khach_hang)
    ]
    return templates.TemplateResponse(
        request, "quote_templates/list.html", {"active_page": "quote_templates", "groups": groups}
    )


@router.get("/moi")
def new_template_form(request: Request):
    return templates.TemplateResponse(
        request, "quote_templates/form.html", {"active_page": "quote_templates", "quote": None}
    )


@router.post("/moi")
def create_template(
    request: Request, ten_template: str = Form(...), khach_hang: str = Form(""), db: Session = Depends(get_db)
):
    quote = crud.create_blank_template(db, ten_template, khach_hang or None)
    return RedirectResponse(f"/bao-gia/{quote.id}/linh-kien", status_code=303)


@router.get("/{quote_id:int}/sua")
def edit_template_form(request: Request, quote_id: int, db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    return templates.TemplateResponse(
        request, "quote_templates/form.html", {"active_page": "quote_templates", "quote": quote}
    )


@router.post("/{quote_id:int}/sua")
def update_template(
    request: Request,
    quote_id: int,
    ten_template: str = Form(...),
    khach_hang: str = Form(""),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote(db, quote_id)
    crud.update_template_meta(db, quote, ten_template, khach_hang or None)
    return RedirectResponse("/mau-bao-gia", status_code=303)


@router.post("/{quote_id:int}/xoa")
def delete_template(quote_id: int, db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    crud.delete_template(db, quote)
    return RedirectResponse("/mau-bao-gia", status_code=303)
