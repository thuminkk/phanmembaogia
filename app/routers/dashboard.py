from fastapi import APIRouter, Request

from app.core.templates import templates

router = APIRouter()


@router.get("/")
def index(request: Request):
    stats = {
        "so_linh_kien": None,
        "so_du_an": None,
    }
    return templates.TemplateResponse(
        request, "dashboard.html", {"active_page": "dashboard", "stats": stats}
    )
