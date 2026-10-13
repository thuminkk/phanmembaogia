import itertools

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import projects as crud
from app.crud import quotes as quotes_crud
from app.db.database import get_db
from app.schemas.projects import ProjectIn

router = APIRouter(prefix="/du-an")


def _grouped_templates(db: Session):
    items = quotes_crud.list_templates(db)
    return [
        (khach_hang or "Chưa gắn khách hàng", list(rows))
        for khach_hang, rows in itertools.groupby(items, key=lambda q: q.khach_hang)
    ]


@router.get("")
def list_projects(
    request: Request,
    ma_du_an: str = "",
    ten_thiet_bi: str = "",
    khach_hang: str = "",
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "projects/list.html",
        {
            "active_page": "projects",
            "projects": crud.list_projects(db, ma_du_an=ma_du_an, ten_thiet_bi=ten_thiet_bi, khach_hang=khach_hang),
            "filters": {"ma_du_an": ma_du_an, "ten_thiet_bi": ten_thiet_bi, "khach_hang": khach_hang},
            "khach_hang_options": crud.distinct_khach_hang(db),
        },
    )


@router.get("/moi")
def new_project_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "projects/form.html",
        {
            "active_page": "projects",
            "project": None,
            "error": None,
            "template_groups": _grouped_templates(db),
            "source_quotes": quotes_crud.list_source_quotes(db),
        },
    )


@router.post("/moi")
def create_project(
    request: Request,
    ma_du_an: str = Form(...),
    ten_thiet_bi: str = Form(...),
    khach_hang: str = Form(""),
    dia_chi: str = Form(""),
    chung_loai: str = Form(""),
    yeu_cau_dac_biet: str = Form(""),
    dot: int = Form(1),
    rev: int = Form(0),
    source_quote_id: str = Form(""),
    db: Session = Depends(get_db),
):
    data = ProjectIn(
        ma_du_an=ma_du_an,
        ten_thiet_bi=ten_thiet_bi,
        khach_hang=khach_hang or None,
        dia_chi=dia_chi or None,
        chung_loai=chung_loai or None,
        yeu_cau_dac_biet=yeu_cau_dac_biet or None,
    )
    try:
        project = crud.create_project(db, data)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "projects/form.html",
            {
                "active_page": "projects",
                "project": None,
                "error": str(exc),
                "template_groups": _grouped_templates(db),
                "source_quotes": quotes_crud.list_source_quotes(db),
            },
        )
    # Tạo luôn báo giá đầu tiên của dự án cùng lúc, không cần bước riêng — nạp từ mẫu/báo giá cũ nếu có chọn.
    source_id = int(source_quote_id) if source_quote_id else None
    if source_id:
        quote = quotes_crud.clone_quote(db, source_id, project_id=project.id, rev=rev, dot=dot)
    else:
        quote = quotes_crud.create_blank_quote(db, project.id, rev, dot)
    return RedirectResponse(f"/bao-gia/{quote.id}", status_code=303)


@router.get("/{project_id:int}")
def project_detail(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = crud.get_project(db, project_id)
    quotes = crud.list_quotes_for_project(db, project_id) if project else []
    return templates.TemplateResponse(
        request,
        "projects/detail.html",
        {"active_page": "projects", "project": project, "quotes": quotes},
    )


@router.post("/{project_id:int}/xoa")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = crud.get_project(db, project_id)
    crud.delete_project(db, project)
    return RedirectResponse("/du-an", status_code=303)


@router.get("/{project_id:int}/sua")
def edit_project_form(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = crud.get_project(db, project_id)
    return templates.TemplateResponse(
        request, "projects/form.html", {"active_page": "projects", "project": project, "error": None}
    )


@router.post("/{project_id:int}/sua")
def update_project(
    request: Request,
    project_id: int,
    ma_du_an: str = Form(...),
    ten_thiet_bi: str = Form(...),
    khach_hang: str = Form(""),
    dia_chi: str = Form(""),
    chung_loai: str = Form(""),
    yeu_cau_dac_biet: str = Form(""),
    db: Session = Depends(get_db),
):
    project = crud.get_project(db, project_id)
    data = ProjectIn(
        ma_du_an=ma_du_an,
        ten_thiet_bi=ten_thiet_bi,
        khach_hang=khach_hang or None,
        dia_chi=dia_chi or None,
        chung_loai=chung_loai or None,
        yeu_cau_dac_biet=yeu_cau_dac_biet or None,
    )
    try:
        crud.update_project(db, project, data)
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "projects/form.html", {"active_page": "projects", "project": project, "error": str(exc)}
        )
    return RedirectResponse(f"/du-an/{project_id}", status_code=303)


@router.get("/{project_id:int}/bao-gia/moi")
def new_quote_form(
    request: Request, project_id: int, source_quote_id: int | None = None, db: Session = Depends(get_db)
):
    project = crud.get_project(db, project_id)
    source_quote = quotes_crud.get_quote(db, source_quote_id) if source_quote_id else None
    if source_quote:
        # "Copy rev để sửa nhanh": tiếp tục đúng chu kỳ đặt hàng (dot) của bản đang copy, tăng rev lên 1.
        suggested_rev, suggested_dot = source_quote.rev + 1, source_quote.dot
    else:
        suggested_rev, suggested_dot = quotes_crud.suggest_next_numbers(db, project_id)
    return templates.TemplateResponse(
        request,
        "quotes/form_new.html",
        {
            "active_page": "projects",
            "project": project,
            "suggested_rev": suggested_rev,
            "suggested_dot": suggested_dot,
            "template_groups": _grouped_templates(db),
            "source_quotes": quotes_crud.list_source_quotes(db),
            "preselected_source_id": source_quote_id,
            "error": None,
        },
    )


@router.post("/{project_id:int}/bao-gia/moi")
def create_quote(
    request: Request,
    project_id: int,
    rev: int = Form(...),
    dot: int = Form(...),
    source_quote_id: str = Form(""),
    db: Session = Depends(get_db),
):
    source_quote_id = int(source_quote_id) if source_quote_id else None

    try:
        if source_quote_id:
            quote = quotes_crud.clone_quote(db, source_quote_id, project_id=project_id, rev=rev, dot=dot)
        else:
            quote = quotes_crud.create_blank_quote(db, project_id, rev, dot)
    except ValueError as exc:
        project = crud.get_project(db, project_id)
        return templates.TemplateResponse(
            request,
            "quotes/form_new.html",
            {
                "active_page": "projects",
                "project": project,
                "suggested_rev": rev,
                "suggested_dot": dot,
                "template_groups": _grouped_templates(db),
                "source_quotes": quotes_crud.list_source_quotes(db),
                "preselected_source_id": source_quote_id,
                "error": str(exc),
            },
        )

    return RedirectResponse(f"/bao-gia/{quote.id}", status_code=303)
