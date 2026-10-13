import urllib.parse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as parts_crud
from app.crud import quotes as crud
from app.crud import standard_groups as standard_groups_crud
from app.db.database import get_db
from app.db.models import QuoteComponentGroup, QuoteFabricatedLine, QuoteMaterialLine, QuotePartLine
from app.schemas.quotes import TRANG_THAI_LABELS, TRANG_THAI_OPTIONS, QuoteUpdateIn
from app.services import quote_export

router = APIRouter(prefix="/bao-gia")


def _quote_context(db: Session, quote_id: int, active_tab: str, error: str | None = None) -> dict:
    quote = crud.get_quote(db, quote_id)
    return {
        "active_page": "projects",
        "active_tab": active_tab,
        "quote": quote,
        "totals": crud.quote_totals(quote) if quote else None,
        "breakdown_loai": crud.quote_part_breakdown_by_loai(quote) if quote else None,
        "trang_thai_options": TRANG_THAI_OPTIONS,
        "trang_thai_labels": TRANG_THAI_LABELS,
        "error": error,
    }


@router.get("/{quote_id:int}")
def quote_overview(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "quotes/overview.html", _quote_context(db, quote_id, "overview")
    )


@router.get("/{quote_id:int}/nvl")
def quote_nvl_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "quotes/nvl.html", _quote_context(db, quote_id, "nvl"))


@router.get("/{quote_id:int}/linh-kien")
def quote_parts_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    context = _quote_context(db, quote_id, "linh_kien")
    context["standard_groups"] = standard_groups_crud.list_groups(db)
    return templates.TemplateResponse(request, "quotes/parts.html", context)


@router.get("/{quote_id:int}/linh-kien/xuat-excel")
def quote_parts_export_excel(quote_id: int, db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    buf = quote_export.build_parts_excel(quote)
    # Tên file có thể chứa tiếng Việt có dấu (VD ten_template) -> header Content-Disposition phải
    # theo RFC 6266 (filename ASCII dự phòng + filename* UTF-8 mã hoá phần trăm) để không lỗi HTTP header.
    raw_name = f"{quote.ma_bao_gia} - Danh sach linh kien.xlsx".replace("/", "-")
    ascii_name = raw_name.encode("ascii", "ignore").decode("ascii") or "danh_sach_linh_kien.xlsx"
    encoded_name = urllib.parse.quote(raw_name)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"},
    )


@router.get("/{quote_id:int}/linh-kien/dong-bo-gia")
def quote_sync_price_preview(request: Request, quote_id: int, db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    lines = crud.list_price_mismatched_lines(quote) if quote else []
    return templates.TemplateResponse(
        request, "quotes/dong_bo_gia.html", {"active_page": "projects", "quote": quote, "lines": lines}
    )


@router.post("/{quote_id:int}/linh-kien/dong-bo-gia/xac-nhan")
def quote_sync_price_confirm(quote_id: int, line_ids: list[int] = Form([]), db: Session = Depends(get_db)):
    for line_id in line_ids:
        line = db.get(QuotePartLine, line_id)
        if line and line.quote_id == quote_id:
            crud.sync_line_price_from_csdl(db, line)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.get("/{quote_id:int}/gia-cong")
def quote_fabricated_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "quotes/fabricated.html", _quote_context(db, quote_id, "gia_cong")
    )


@router.get("/{quote_id:int}/spec")
def quote_spec_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "quotes/spec.html", _quote_context(db, quote_id, "spec"))


@router.get("/{quote_id:int}/ghi-chu")
def quote_ghi_chu_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "quotes/ghi_chu.html", _quote_context(db, quote_id, "ghi_chu"))


@router.post("/{quote_id:int}/ghi-chu")
def update_quote_ghi_chu(quote_id: int, ghi_chu: str = Form(""), db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    crud.update_ghi_chu(db, quote, ghi_chu or None)
    return RedirectResponse(f"/bao-gia/{quote_id}/ghi-chu", status_code=303)


@router.post("/{quote_id:int}/sua")
def update_quote(
    request: Request,
    quote_id: int,
    rev: int = Form(...),
    dot: int = Form(...),
    trang_thai: str = Form(...),
    nguoi_tinh_gia: str = Form(""),
    db: Session = Depends(get_db),
):
    quote = crud.get_quote(db, quote_id)
    try:
        crud.update_quote(
            db,
            quote,
            QuoteUpdateIn(rev=rev, dot=dot, trang_thai=trang_thai, nguoi_tinh_gia=nguoi_tinh_gia or None),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "quotes/overview.html", _quote_context(db, quote_id, "overview", error=str(exc))
        )
    return RedirectResponse(f"/bao-gia/{quote_id}", status_code=303)


@router.post("/{quote_id:int}/xoa")
def delete_quote(quote_id: int, db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    project_id = quote.project_id
    crud.delete_quote(db, quote)
    if project_id:
        return RedirectResponse(f"/du-an/{project_id}", status_code=303)
    return RedirectResponse("/mau-bao-gia", status_code=303)


@router.get("/{quote_id:int}/luu-mau")
def save_as_template_form(request: Request, quote_id: int, db: Session = Depends(get_db)):
    quote = crud.get_quote(db, quote_id)
    return templates.TemplateResponse(
        request, "quotes/save_as_template.html", {"active_page": "projects", "quote": quote}
    )


@router.post("/{quote_id:int}/luu-mau")
def save_as_template(
    quote_id: int, ten_template: str = Form(...), khach_hang: str = Form(""), db: Session = Depends(get_db)
):
    new_quote = crud.save_as_template(db, quote_id, ten_template, khach_hang or None)
    return RedirectResponse(f"/bao-gia/{new_quote.id}/linh-kien", status_code=303)


# ---- Cụm linh kiện ----


@router.post("/{quote_id:int}/cum")
def add_group(quote_id: int, ten_cum: str = Form(...), db: Session = Depends(get_db)):
    crud.add_group(db, quote_id, ten_cum)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/linh-kien/ap-dung-cum-mau")
def apply_standard_group(quote_id: int, standard_group_id: str = Form(""), db: Session = Depends(get_db)):
    if standard_group_id:
        standard_groups_crud.apply_group_to_quote(db, quote_id, int(standard_group_id))
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/cum/{group_id:int}/sua")
def edit_group(
    quote_id: int,
    group_id: int,
    ten_cum: str = Form(...),
    mo_ta_co_khi: str = Form(""),
    mo_ta_dien: str = Form(""),
    mo_ta_khi_nen: str = Form(""),
    mo_ta_thuy_luc: str = Form(""),
    redirect_to: str = Form("linh-kien"),
    db: Session = Depends(get_db),
):
    group = db.get(QuoteComponentGroup, group_id)
    crud.update_group(
        db,
        group,
        ten_cum=ten_cum,
        mo_ta_co_khi=mo_ta_co_khi or None,
        mo_ta_dien=mo_ta_dien or None,
        mo_ta_khi_nen=mo_ta_khi_nen or None,
        mo_ta_thuy_luc=mo_ta_thuy_luc or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/{redirect_to}", status_code=303)


@router.post("/{quote_id:int}/cum/{group_id:int}/xoa")
def remove_group(quote_id: int, group_id: int, db: Session = Depends(get_db)):
    group = db.get(QuoteComponentGroup, group_id)
    crud.delete_group(db, group)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/cum/{group_id:int}/di-chuyen")
def move_group(quote_id: int, group_id: int, huong: str = Form(...), db: Session = Depends(get_db)):
    crud.move_group(db, quote_id, group_id, huong)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


# ---- Nguyên vật liệu ----


@router.post("/{quote_id:int}/nvl")
def add_material_line(
    quote_id: int,
    chung_loai: str = Form(""),
    quy_cach: str = Form(""),
    vat_lieu: str = Form(""),
    xuat_xu: str = Form(""),
    don_vi: str = Form(""),
    so_luong: float = Form(1),
    don_gia: float = Form(0),
    nha_cung_cap: str = Form(""),
    db: Session = Depends(get_db),
):
    crud.add_material_line(
        db,
        quote_id,
        chung_loai=chung_loai or None,
        quy_cach=quy_cach or None,
        vat_lieu=vat_lieu or None,
        xuat_xu=xuat_xu or None,
        don_vi=don_vi or None,
        so_luong=so_luong,
        don_gia=don_gia,
        nha_cung_cap=nha_cung_cap or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/nvl", status_code=303)


@router.post("/{quote_id:int}/nvl/{line_id:int}/sua")
def edit_material_line(
    quote_id: int,
    line_id: int,
    chung_loai: str = Form(""),
    quy_cach: str = Form(""),
    vat_lieu: str = Form(""),
    xuat_xu: str = Form(""),
    don_vi: str = Form(""),
    so_luong: float = Form(1),
    don_gia: float = Form(0),
    nha_cung_cap: str = Form(""),
    db: Session = Depends(get_db),
):
    line = db.get(QuoteMaterialLine, line_id)
    crud.update_material_line(
        db,
        line,
        chung_loai=chung_loai or None,
        quy_cach=quy_cach or None,
        vat_lieu=vat_lieu or None,
        xuat_xu=xuat_xu or None,
        don_vi=don_vi or None,
        so_luong=so_luong,
        don_gia=don_gia,
        nha_cung_cap=nha_cung_cap or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/nvl", status_code=303)


@router.post("/{quote_id:int}/nvl/{line_id:int}/xoa")
def delete_material_line(quote_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(QuoteMaterialLine, line_id)
    crud.delete_material_line(db, line)
    return RedirectResponse(f"/bao-gia/{quote_id}/nvl", status_code=303)


# ---- Linh kiện gia công ----


@router.post("/{quote_id:int}/gia-cong")
def add_fabricated_line(
    quote_id: int,
    ten_linh_kien: str = Form(...),
    ma_ban_ve: str = Form(""),
    vat_lieu: str = Form(""),
    so_luong: float = Form(1),
    don_gia: float = Form(0),
    nha_cung_cap: str = Form(""),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    crud.add_fabricated_line(
        db,
        quote_id,
        ten_linh_kien=ten_linh_kien,
        ma_ban_ve=ma_ban_ve or None,
        vat_lieu=vat_lieu or None,
        so_luong=so_luong,
        don_gia=don_gia,
        nha_cung_cap=nha_cung_cap or None,
        ghi_chu=ghi_chu or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/gia-cong", status_code=303)


@router.post("/{quote_id:int}/gia-cong/{line_id:int}/sua")
def edit_fabricated_line(
    quote_id: int,
    line_id: int,
    ten_linh_kien: str = Form(...),
    ma_ban_ve: str = Form(""),
    vat_lieu: str = Form(""),
    so_luong: float = Form(1),
    don_gia: float = Form(0),
    nha_cung_cap: str = Form(""),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    line = db.get(QuoteFabricatedLine, line_id)
    crud.update_fabricated_line(
        db,
        line,
        ten_linh_kien=ten_linh_kien,
        ma_ban_ve=ma_ban_ve or None,
        vat_lieu=vat_lieu or None,
        so_luong=so_luong,
        don_gia=don_gia,
        nha_cung_cap=nha_cung_cap or None,
        ghi_chu=ghi_chu or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/gia-cong", status_code=303)


@router.post("/{quote_id:int}/gia-cong/{line_id:int}/xoa")
def delete_fabricated_line(quote_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(QuoteFabricatedLine, line_id)
    crud.delete_fabricated_line(db, line)
    return RedirectResponse(f"/bao-gia/{quote_id}/gia-cong", status_code=303)


# ---- Linh kiện bán sẵn (nối CSDL) ----


@router.post("/{quote_id:int}/linh-kien")
def add_part_line(
    quote_id: int,
    group_id: str = Form(""),
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
    crud.add_part_line(
        db,
        quote_id,
        group_id=int(group_id) if group_id else None,
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
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/linh-kien/{line_id:int}/sua")
def edit_part_line(
    quote_id: int,
    line_id: int,
    ten_linh_kien: str = Form(...),
    ma_linh_kien: str = Form(""),
    hang: str = Form(""),
    don_vi: str = Form(""),
    so_luong: float = Form(1),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    # Chỉ sửa thông tin mô tả + số lượng. Cụm đổi qua route /doi-cum riêng. NCC/giá không sửa ở đây
    # nữa — mỗi linh kiện chỉ có 1 NCC/giá duy nhất trong CSDL, sửa trực tiếp ở trang Linh kiện.
    line = db.get(QuotePartLine, line_id)
    crud.update_part_line(
        db,
        line,
        ten_linh_kien=ten_linh_kien,
        ma_linh_kien=ma_linh_kien or None,
        hang=hang or None,
        don_vi=don_vi or None,
        so_luong=so_luong,
        ghi_chu=ghi_chu or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/linh-kien/{line_id:int}/xoa")
def delete_part_line(quote_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(QuotePartLine, line_id)
    crud.delete_part_line(db, line)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/linh-kien/xoa-nhieu")
async def delete_part_lines(quote_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("ids")]
    crud.delete_part_lines(db, quote_id, ids)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.post("/{quote_id:int}/linh-kien/sap-xep")
def reorder_part_lines(quote_id: int, group_id: str = Form(""), line_ids: str = Form(""), db: Session = Depends(get_db)):
    ids = [int(x) for x in line_ids.split(",") if x]
    crud.reorder_part_lines(db, quote_id, int(group_id) if group_id else None, ids)
    return {"ok": True}


@router.post("/{quote_id:int}/linh-kien/{line_id:int}/doi-cum")
def change_part_line_group(quote_id: int, line_id: int, group_id: str = Form(""), db: Session = Depends(get_db)):
    line = db.get(QuotePartLine, line_id)
    crud.update_part_line(db, line, group_id=int(group_id) if group_id else None)
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)


@router.get("/{quote_id:int}/linh-kien/{line_id:int}/cap-nhat-gia")
def update_price_form(request: Request, quote_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.get(QuotePartLine, line_id)
    return templates.TemplateResponse(
        request,
        "quotes/update_price.html",
        {"active_page": "projects", "quote_id": quote_id, "line": line},
    )


@router.post("/{quote_id:int}/linh-kien/{line_id:int}/cap-nhat-gia")
def update_price_submit(
    quote_id: int,
    line_id: int,
    nha_cung_cap: str = Form(""),
    don_gia: float = Form(...),
    don_vi: str = Form(""),
    db: Session = Depends(get_db),
):
    line = db.get(QuotePartLine, line_id)
    parts_crud.find_or_create_part_price(
        db,
        ma_linh_kien=line.ma_linh_kien,
        ten_linh_kien=line.ten_linh_kien,
        hang=line.hang,
        nha_cung_cap=nha_cung_cap or None,
        don_gia=don_gia,
        don_vi=don_vi or None,
    )
    return RedirectResponse(f"/bao-gia/{quote_id}/linh-kien", status_code=303)
