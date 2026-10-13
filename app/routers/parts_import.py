import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR
from app.core.templates import templates
from app.crud import parts as crud
from app.db.database import get_db
from app.schemas.parts import CandidateRow
from app.services import excel_import

router = APIRouter(prefix="/linh-kien/nhap-excel")

TMP_DIR = DATA_DIR / "tmp_uploads"
TMP_DIR.mkdir(exist_ok=True)


@router.get("")
def upload_form(request: Request):
    return templates.TemplateResponse(
        request, "parts/import_excel.html", {"active_page": "parts", "sheets": None, "error": None}
    )


@router.post("")
async def upload_file(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    token = uuid.uuid4().hex
    (TMP_DIR / f"{token}.xlsx").write_bytes(content)
    try:
        sheets = excel_import.list_sheets(content)
        error = None
    except Exception as exc:  # file lỗi định dạng
        sheets = None
        error = f"Không đọc được file Excel: {exc}"
    return templates.TemplateResponse(
        request,
        "parts/import_excel.html",
        {"active_page": "parts", "sheets": sheets, "token": token, "error": error},
    )


@router.post("/xem-truoc")
def preview(
    request: Request, token: str = Form(...), sheet: str = Form(...), db: Session = Depends(get_db)
):
    file_path = TMP_DIR / f"{token}.xlsx"
    if not file_path.exists():
        return templates.TemplateResponse(
            request,
            "parts/import_excel.html",
            {
                "active_page": "parts",
                "sheets": None,
                "error": "File tạm đã hết hạn hoặc không tồn tại, vui lòng tải lên lại.",
            },
        )
    content = file_path.read_bytes()
    try:
        raw_rows = excel_import.parse_sheet(content, sheet)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "parts/import_excel.html",
            {
                "active_page": "parts",
                "sheets": excel_import.list_sheets(content),
                "token": token,
                "error": str(exc),
            },
        )
    file_path.unlink(missing_ok=True)

    rows = [crud.classify_candidate(db, CandidateRow(status="?", **r)) for r in raw_rows]
    return templates.TemplateResponse(
        request,
        "parts/preview.html",
        {
            "active_page": "parts",
            "rows": rows,
            "nguon": f"Excel — sheet “{sheet}”",
            "loai_options": crud.LOAI_OPTIONS,
        },
    )
