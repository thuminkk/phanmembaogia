from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import parts as crud
from app.db.database import get_db
from app.db.models import PartSupplierPrice
from app.schemas.parts import PartIn, SupplierPriceIn

router = APIRouter(prefix="/linh-kien")


@router.get("")
def list_parts(
    request: Request,
    ma: str = "",
    ten: str = "",
    hang: str = "",
    loai: str = "",
    ncc: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
):
    items, total = crud.list_parts(db, ma=ma, ten=ten, hang=hang, loai=loai, ncc=ncc, page=page)
    total_pages = max(1, (total + crud.PAGE_SIZE - 1) // crud.PAGE_SIZE)
    return templates.TemplateResponse(
        request,
        "parts/list.html",
        {
            "active_page": "parts",
            "parts": items,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "filters": {"ma": ma, "ten": ten, "hang": hang, "loai": loai, "ncc": ncc},
            "hang_options": crud.distinct_values(db, "hang"),
            "loai_options": crud.LOAI_OPTIONS,
            "ncc_options": crud.distinct_suppliers(db),
        },
    )


@router.get("/tim-kiem")
def search_parts(q: str = "", db: Session = Depends(get_db)):
    parts = crud.search_parts_with_prices(db, q)
    return [
        {
            "part_id": p.id,
            "ten_linh_kien": p.ten_linh_kien,
            "ma_linh_kien": p.ma_linh_kien,
            "hang": p.hang,
            "don_vi": p.don_vi,
            "suppliers": [
                {
                    "supplier_price_id": sp.id,
                    "nha_cung_cap": sp.nha_cung_cap or "(chưa rõ NCC)",
                    "don_gia": sp.don_gia,
                }
                for sp in p.suppliers
                if sp.is_active
            ],
        }
        for p in parts
    ]


@router.post("/{part_id:int}/sua-loai")
def quick_update_loai(
    part_id: int,
    loai: str = Form(""),
    db: Session = Depends(get_db),
):
    # Sửa nhanh ngay trong danh sách bằng fetch() (xem parts.js) — không chuyển trang/reload,
    # nên chỉ cần trả về 204, không redirect.
    part = crud.get_part(db, part_id)
    if part:
        crud.update_part_loai(db, part, loai or None)
    return Response(status_code=204)


@router.post("/{part_id:int}/sua-don-vi")
def quick_update_don_vi(
    part_id: int,
    don_vi: str = Form(""),
    db: Session = Depends(get_db),
):
    part = crud.get_part(db, part_id)
    if part:
        crud.update_part_don_vi(db, part, don_vi or None)
    return Response(status_code=204)


@router.post("/xoa-nhieu")
async def delete_many(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("ids")]
    for part_id in ids:
        part = crud.get_part(db, part_id)
        if part:
            crud.delete_part(db, part)
    return RedirectResponse("/linh-kien", status_code=303)


@router.get("/moi")
def new_part_form(request: Request):
    return templates.TemplateResponse(
        request,
        "parts/form.html",
        {"active_page": "parts", "part": None, "loai_options": crud.LOAI_OPTIONS},
    )


@router.post("/moi")
def create_part(
    request: Request,
    ma_linh_kien: str = Form(""),
    ten_linh_kien: str = Form(...),
    hang: str = Form(""),
    loai: str = Form(""),
    xuat_xu: str = Form(""),
    don_vi: str = Form(""),
    ghi_chu: str = Form(""),
    nha_cung_cap: str = Form(""),
    don_gia: float | None = Form(None),
    db: Session = Depends(get_db),
):
    data = PartIn(
        ma_linh_kien=ma_linh_kien or None,
        ten_linh_kien=ten_linh_kien,
        hang=hang or None,
        loai=loai or None,
        xuat_xu=xuat_xu or None,
        don_vi=don_vi or None,
        ghi_chu=ghi_chu or None,
    )
    try:
        part = crud.create_part(db, data)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "parts/form.html",
            {"active_page": "parts", "part": None, "loai_options": crud.LOAI_OPTIONS, "error": str(exc)},
        )
    if don_gia is not None:
        crud.add_supplier_price(db, part, SupplierPriceIn(nha_cung_cap=nha_cung_cap, don_gia=don_gia))
    return RedirectResponse(f"/linh-kien/{part.id}", status_code=303)


@router.get("/{part_id:int}")
def part_detail(request: Request, part_id: int, db: Session = Depends(get_db)):
    part = crud.get_part(db, part_id)
    return templates.TemplateResponse(
        request, "parts/detail.html", {"active_page": "parts", "part": part}
    )


@router.get("/{part_id:int}/sua")
def edit_part_form(request: Request, part_id: int, db: Session = Depends(get_db)):
    part = crud.get_part(db, part_id)
    return templates.TemplateResponse(
        request,
        "parts/form.html",
        {"active_page": "parts", "part": part, "loai_options": crud.LOAI_OPTIONS},
    )


@router.post("/{part_id:int}/sua")
def update_part(
    request: Request,
    part_id: int,
    ma_linh_kien: str = Form(""),
    ten_linh_kien: str = Form(...),
    hang: str = Form(""),
    loai: str = Form(""),
    xuat_xu: str = Form(""),
    don_vi: str = Form(""),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    part = crud.get_part(db, part_id)
    data = PartIn(
        ma_linh_kien=ma_linh_kien or None,
        ten_linh_kien=ten_linh_kien,
        hang=hang or None,
        loai=loai or None,
        xuat_xu=xuat_xu or None,
        don_vi=don_vi or None,
        ghi_chu=ghi_chu or None,
    )
    try:
        crud.update_part(db, part, data)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "parts/form.html",
            {"active_page": "parts", "part": part, "loai_options": crud.LOAI_OPTIONS, "error": str(exc)},
        )
    return RedirectResponse(f"/linh-kien/{part_id}", status_code=303)


@router.post("/{part_id:int}/xoa")
def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = crud.get_part(db, part_id)
    if part:
        crud.delete_part(db, part)
    return RedirectResponse("/linh-kien", status_code=303)


@router.post("/{part_id:int}/ncc")
def add_supplier_price(
    part_id: int,
    nha_cung_cap: str = Form(...),
    don_gia: float = Form(...),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    part = crud.get_part(db, part_id)
    # Mỗi linh kiện chỉ 1 giá/NCC — form "Thêm giá" chỉ hiện khi part.price chưa có (xem detail.html),
    # nhưng vẫn chặn ở đây để không tạo dòng thứ 2 nếu bị gọi lại (VD double-submit).
    if part and part.price is None:
        crud.add_supplier_price(db, part, SupplierPriceIn(nha_cung_cap=nha_cung_cap, don_gia=don_gia, ghi_chu=ghi_chu or None))
    return RedirectResponse(f"/linh-kien/{part_id}", status_code=303)


@router.post("/{part_id:int}/ncc/{price_id:int}/sua")
def edit_supplier_price(
    part_id: int,
    price_id: int,
    nha_cung_cap: str = Form(...),
    don_gia: float = Form(...),
    ghi_chu: str = Form(""),
    db: Session = Depends(get_db),
):
    price = db.get(PartSupplierPrice, price_id)
    crud.update_supplier_price(db, price, SupplierPriceIn(nha_cung_cap=nha_cung_cap, don_gia=don_gia, ghi_chu=ghi_chu or None))
    return RedirectResponse(f"/linh-kien/{part_id}", status_code=303)


@router.post("/{part_id:int}/ncc/{price_id:int}/xoa")
def delete_supplier_price(part_id: int, price_id: int, db: Session = Depends(get_db)):
    price = db.get(PartSupplierPrice, price_id)
    if price:
        crud.delete_supplier_price(db, price)
    return RedirectResponse(f"/linh-kien/{part_id}", status_code=303)
