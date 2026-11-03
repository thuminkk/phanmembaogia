import datetime
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import bom as crud
from app.crud import quotes as quotes_crud
from app.db.database import get_db
from app.db.models import AiExperience
from app.services import ai_bom, bom_form

router = APIRouter()

EXPERIENCE_GROUPS = ["Chung", "Tủ điện", "HMI", "Khí nén", "Thủy lực", "Servo/Động cơ", "Cảm biến"]


def _form_page(request: Request, db: Session, quote_id: int, form_data: dict, error: str | None = None):
    return templates.TemplateResponse(
        request,
        "quotes/bom_form.html",
        {
            "active_page": "projects",
            "active_tab": "linh_kien",
            "quote": quotes_crud.get_quote(db, quote_id),
            "sections": bom_form.SECTIONS,
            "mo_ta_key": bom_form.MO_TA_KEY,
            "values": form_data,
            "requests": crud.list_requests(db, quote_id),
            "so_kinh_nghiem": len(ai_bom.active_experiences(db)),
            "error": error,
        },
    )


@router.get("/bao-gia/{quote_id:int}/tu-dong-bom")
def bom_form_page(request: Request, quote_id: int, db: Session = Depends(get_db)):
    return _form_page(request, db, quote_id, crud.last_form(db, quote_id))


@router.post("/bao-gia/{quote_id:int}/tu-dong-bom")
async def bom_generate(request: Request, quote_id: int, db: Session = Depends(get_db)):
    form_data = bom_form.parse_form(await request.form())
    if not form_data:
        return _form_page(request, db, quote_id, form_data, "Phiếu đang trống — nhập ít nhất vài thông tin.")
    try:
        proposal, provider = ai_bom.generate_bom(db, form_data)
    except ValueError as exc:
        return _form_page(request, db, quote_id, form_data, str(exc))
    req = crud.create_request(db, quote_id, form_data, proposal, provider)
    return RedirectResponse(f"/bao-gia/{quote_id}/tu-dong-bom/{req.id}", status_code=303)


@router.get("/bao-gia/{quote_id:int}/tu-dong-bom/{req_id:int}")
def bom_request_page(request: Request, quote_id: int, req_id: int, added: int | None = None, db: Session = Depends(get_db)):
    req = crud.get_request(db, quote_id, req_id)
    if req is None:
        return RedirectResponse(f"/bao-gia/{quote_id}/tu-dong-bom", status_code=303)
    quote = quotes_crud.get_quote(db, quote_id)
    proposal = json.loads(req.proposal_json or "{}")
    group_names = {g.ten_cum.strip().lower(): g.id for g in quote.groups}
    return templates.TemplateResponse(
        request,
        "quotes/bom_preview.html",
        {
            "active_page": "projects",
            "active_tab": "linh_kien",
            "quote": quote,
            "req": req,
            "phieu": bom_form.describe(json.loads(req.form_json)),
            "proposal": proposal,
            "group_names": group_names,
            "changes": ai_bom.compute_diff(db, req) if req.applied_at else [],
            "added": added,
        },
    )


@router.post("/bao-gia/{quote_id:int}/tu-dong-bom/{req_id:int}/ap-dung")
async def bom_apply(request: Request, quote_id: int, req_id: int, db: Session = Depends(get_db)):
    req = crud.get_request(db, quote_id, req_id)
    if req is None:
        return RedirectResponse(f"/bao-gia/{quote_id}/tu-dong-bom", status_code=303)
    form = await request.form()
    proposal = json.loads(req.proposal_json or "{}")
    groups = []
    for gi, cum in enumerate(proposal.get("cum", [])):
        dong = []
        for li, d in enumerate(cum["dong"]):
            if not form.get(f"chon_{gi}_{li}"):
                continue
            try:
                sl = float(form.get(f"sl_{gi}_{li}") or d["sl"])
            except ValueError:
                sl = d["sl"]
            if sl > 0:
                dong.append({**d, "sl": sl})
        target = form.get(f"cum_{gi}_dich") or ""
        groups.append({
            "ten_cum": (form.get(f"cum_{gi}_ten") or cum["ten_cum"]).strip(),
            "target_group_id": int(target) if target.isdigit() else None,
            "dong": dong,
        })
    added = crud.apply_request(db, req, groups)
    return RedirectResponse(f"/bao-gia/{quote_id}/tu-dong-bom/{req_id}?added={added}", status_code=303)


@router.post("/bao-gia/{quote_id:int}/tu-dong-bom/{req_id:int}/rut-kinh-nghiem")
def bom_lessons(request: Request, quote_id: int, req_id: int, ghi_chu: str = Form(""), db: Session = Depends(get_db)):
    req = crud.get_request(db, quote_id, req_id)
    if req is None or not req.applied_at:
        return RedirectResponse(f"/bao-gia/{quote_id}/tu-dong-bom", status_code=303)
    changes = ai_bom.compute_diff(db, req)
    error, lessons = None, []
    try:
        lessons = ai_bom.suggest_lessons(db, req, changes, ghi_chu)
    except ValueError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        request,
        "quotes/bom_lessons.html",
        {
            "active_page": "projects",
            "active_tab": "linh_kien",
            "quote": quotes_crud.get_quote(db, quote_id),
            "req": req,
            "changes": changes,
            "ghi_chu": ghi_chu,
            "lessons": lessons,
            "experience_groups": EXPERIENCE_GROUPS,
            "error": error,
        },
    )


@router.post("/bao-gia/{quote_id:int}/tu-dong-bom/{req_id:int}/luu-kinh-nghiem")
async def bom_save_lessons(request: Request, quote_id: int, req_id: int, db: Session = Depends(get_db)):
    req = crud.get_request(db, quote_id, req_id)
    if req is None:
        return RedirectResponse(f"/bao-gia/{quote_id}/tu-dong-bom", status_code=303)
    form = await request.form()
    i = 0
    while f"noi_dung_{i}" in form:
        if form.get(f"chon_{i}") and (form.get(f"noi_dung_{i}") or "").strip():
            crud.add_experience(db, form.get(f"nhom_{i}"), form.get(f"noi_dung_{i}"), "ai", req.id)
        i += 1
    req.learned_at = datetime.datetime.utcnow()
    db.commit()
    return RedirectResponse("/kinh-nghiem-ai", status_code=303)


# ---- Trang quản lý kinh nghiệm AI ----


@router.get("/kinh-nghiem-ai")
def experiences_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "ai_experience.html",
        {"active_page": "ai_experience", "items": crud.list_experiences(db), "experience_groups": EXPERIENCE_GROUPS},
    )


@router.post("/kinh-nghiem-ai/moi")
def experience_add(nhom: str = Form("Chung"), noi_dung: str = Form(...), db: Session = Depends(get_db)):
    if noi_dung.strip():
        crud.add_experience(db, nhom, noi_dung)
    return RedirectResponse("/kinh-nghiem-ai", status_code=303)


@router.post("/kinh-nghiem-ai/{exp_id:int}/sua")
def experience_update(
    exp_id: int, nhom: str = Form("Chung"), noi_dung: str = Form(...), is_active: str = Form(""), db: Session = Depends(get_db)
):
    exp = db.get(AiExperience, exp_id)
    if exp is not None and noi_dung.strip():
        crud.update_experience(db, exp, nhom, noi_dung, bool(is_active))
    return RedirectResponse("/kinh-nghiem-ai", status_code=303)


@router.post("/kinh-nghiem-ai/{exp_id:int}/xoa")
def experience_delete(exp_id: int, db: Session = Depends(get_db)):
    exp = db.get(AiExperience, exp_id)
    if exp is not None:
        crud.delete_experience(db, exp)
    return RedirectResponse("/kinh-nghiem-ai", status_code=303)
