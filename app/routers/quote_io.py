from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import quote_io as crud
from app.crud import quotes as quotes_crud
from app.db.database import get_db
from app.db.models import QuoteIOLine, QuotePLCLine

router = APIRouter(prefix="/bao-gia")


def _io_context(db: Session, quote_id: int) -> dict:
    quote = quotes_crud.get_quote(db, quote_id)
    return {
        "active_page": "projects",
        "active_tab": "io",
        "quote": quote,
        "summary": crud.io_summary(quote) if quote else None,
    }


@router.get("/{quote_id:int}/io")
def io_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "quotes/io.html", _io_context(db, quote_id))


def _parse_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


# ---- Bảng tính I/O ----


@router.post("/{quote_id:int}/io/dong")
def add_io_line(
    quote_id: int,
    la_nhom: str = Form(""),
    ten_thiet_bi: str = Form(...),
    so_luong: str = Form(""),
    so_input: str = Form(""),
    so_output: str = Form(""),
    db: Session = Depends(get_db),
):
    crud.add_io_line(
        db,
        quote_id,
        la_nhom=bool(la_nhom),
        ten_thiet_bi=ten_thiet_bi,
        so_luong=_parse_float(so_luong),
        so_input=_parse_float(so_input),
        so_output=_parse_float(so_output),
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/{group_line_id:int}/dong")
def add_io_line_in_group(
    quote_id: int,
    group_line_id: int,
    ten_thiet_bi: str = Form(...),
    so_luong: str = Form(""),
    so_input: str = Form(""),
    so_output: str = Form(""),
    db: Session = Depends(get_db),
):
    crud.add_io_line_in_group(
        db,
        quote_id,
        group_line_id,
        ten_thiet_bi=ten_thiet_bi,
        so_luong=_parse_float(so_luong),
        so_input=_parse_float(so_input),
        so_output=_parse_float(so_output),
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/{line_id:int}/sua")
def edit_io_line(
    quote_id: int,
    line_id: int,
    ten_thiet_bi: str = Form(...),
    so_luong: str = Form(""),
    so_input: str = Form(""),
    so_output: str = Form(""),
    db: Session = Depends(get_db),
):
    line = db.get(QuoteIOLine, line_id)
    crud.update_io_line(
        db,
        line,
        ten_thiet_bi=ten_thiet_bi,
        so_luong=_parse_float(so_luong),
        so_input=_parse_float(so_input),
        so_output=_parse_float(so_output),
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/{line_id:int}/xoa")
def delete_io_line(quote_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(QuoteIOLine, line_id)
    crud.delete_io_line(db, line)
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/du-phong")
def update_du_phong(quote_id: int, du_phong_io_percent: float = Form(20), db: Session = Depends(get_db)):
    quote = quotes_crud.get_quote(db, quote_id)
    crud.update_du_phong_percent(db, quote, du_phong_io_percent)
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/nap-mau")
def load_standard_catalog(quote_id: int, db: Session = Depends(get_db)):
    crud.seed_standard_catalog(db, quote_id)
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


# ---- Cấu hình PLC ----


@router.post("/{quote_id:int}/io/plc")
def add_plc_line(
    quote_id: int,
    ten_thiet_bi: str = Form(...),
    so_luong: str = Form(""),
    so_input: str = Form(""),
    so_output: str = Form(""),
    db: Session = Depends(get_db),
):
    crud.add_plc_line(
        db,
        quote_id,
        ten_thiet_bi=ten_thiet_bi,
        so_luong=_parse_float(so_luong),
        so_input=_parse_float(so_input),
        so_output=_parse_float(so_output),
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/plc/{line_id:int}/sua")
def edit_plc_line(
    quote_id: int,
    line_id: int,
    ten_thiet_bi: str = Form(...),
    so_luong: str = Form(""),
    so_input: str = Form(""),
    so_output: str = Form(""),
    db: Session = Depends(get_db),
):
    line = db.get(QuotePLCLine, line_id)
    crud.update_plc_line(
        db,
        line,
        ten_thiet_bi=ten_thiet_bi,
        so_luong=_parse_float(so_luong),
        so_input=_parse_float(so_input),
        so_output=_parse_float(so_output),
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)


@router.post("/{quote_id:int}/io/plc/{line_id:int}/xoa")
def delete_plc_line(quote_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(QuotePLCLine, line_id)
    crud.delete_plc_line(db, line)
    return RedirectResponse(f"/bao-gia/{quote_id}/io", status_code=303)
