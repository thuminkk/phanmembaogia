from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import standard_groups as crud
from app.db.database import get_db
from app.db.models import StandardGroupLine

router = APIRouter(prefix="/cum-tieu-chuan")


@router.get("")
def list_groups(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "standard_groups/list.html", {"active_page": "standard_groups", "groups": crud.list_groups(db)}
    )


@router.get("/moi")
def new_group_form(request: Request, source_group_id: int | None = None, db: Session = Depends(get_db)):
    source_group = crud.get_group(db, source_group_id) if source_group_id else None
    return templates.TemplateResponse(
        request,
        "standard_groups/form.html",
        {"active_page": "standard_groups", "group": None, "source_group": source_group},
    )


@router.post("/moi")
def create_group(
    request: Request,
    ten_cum: str = Form(...),
    mo_ta: str = Form(""),
    source_group_id: str = Form(""),
    db: Session = Depends(get_db),
):
    if source_group_id:
        group = crud.clone_group(db, int(source_group_id), ten_cum, mo_ta or None)
    else:
        group = crud.create_group(db, ten_cum, mo_ta or None)
    return RedirectResponse(f"/cum-tieu-chuan/{group.id}", status_code=303)


@router.get("/{group_id:int}/sua")
def edit_group_form(request: Request, group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    return templates.TemplateResponse(
        request, "standard_groups/form.html", {"active_page": "standard_groups", "group": group}
    )


@router.post("/{group_id:int}/sua")
def update_group(
    request: Request, group_id: int, ten_cum: str = Form(...), mo_ta: str = Form(""), db: Session = Depends(get_db)
):
    group = crud.get_group(db, group_id)
    crud.update_group(db, group, ten_cum, mo_ta or None)
    return RedirectResponse(f"/cum-tieu-chuan/{group_id}", status_code=303)


@router.post("/{group_id:int}/xoa")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    crud.delete_group(db, group)
    return RedirectResponse("/cum-tieu-chuan", status_code=303)


@router.get("/{group_id:int}")
def group_detail(request: Request, group_id: int, db: Session = Depends(get_db)):
    group = crud.get_group(db, group_id)
    return templates.TemplateResponse(
        request, "standard_groups/detail.html", {"active_page": "standard_groups", "group": group}
    )


@router.post("/{group_id:int}/dong")
def add_line(
    group_id: int,
    part_id: str = Form(""),
    supplier_price_id: str = Form(""),
    ten_linh_kien: str = Form(...),
    ma_linh_kien: str = Form(""),
    hang: str = Form(""),
    nha_cung_cap: str = Form(""),
    don_vi: str = Form(""),
    don_gia: float = Form(0),
    so_luong: float = Form(1),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    crud.add_line(
        db,
        group_id,
        part_id=int(part_id) if part_id else None,
        supplier_price_id=int(supplier_price_id) if supplier_price_id else None,
        ten_linh_kien=ten_linh_kien,
        ma_linh_kien=ma_linh_kien or None,
        hang=hang or None,
        nha_cung_cap=nha_cung_cap or None,
        don_vi=don_vi or None,
        don_gia=don_gia,
        so_luong=so_luong,
        ghi_chu=ghi_chu or None,
    )
    return RedirectResponse(f"/cum-tieu-chuan/{group_id}", status_code=303)


@router.post("/{group_id:int}/dong/{line_id:int}/sua")
def edit_line(
    group_id: int,
    line_id: int,
    so_luong: float = Form(1),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    line = db.get(StandardGroupLine, line_id)
    crud.update_line(db, line, so_luong=so_luong, ghi_chu=ghi_chu or None)
    return RedirectResponse(f"/cum-tieu-chuan/{group_id}", status_code=303)


@router.post("/{group_id:int}/dong/{line_id:int}/xoa")
def delete_line(group_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(StandardGroupLine, line_id)
    crud.delete_line(db, line)
    return RedirectResponse(f"/cum-tieu-chuan/{group_id}", status_code=303)
