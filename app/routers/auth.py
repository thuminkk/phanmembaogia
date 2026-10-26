import time
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.templates import templates
from app.crud import users as crud
from app.db.database import get_db

router = APIRouter()

# Chặn dò mật khẩu: sai quá MAX_FAILS lần trong LOCK_SECONDS giây (theo IP + tên đăng nhập) thì khóa tạm.
# Lưu trong bộ nhớ tiến trình — đủ cho 1 instance trên Render, khởi động lại thì xóa.
MAX_FAILS = 5
LOCK_SECONDS = 300
_failed: dict[str, list[float]] = {}


def _fail_key(request: Request, username: str) -> str:
    client = request.client.host if request.client else "?"
    return f"{client}|{username.strip().lower()}"


def _recent_fails(key: str) -> list[float]:
    now = time.time()
    fails = [t for t in _failed.get(key, []) if now - t < LOCK_SECONDS]
    _failed[key] = fails
    return fails


def _safe_next(next_url: str) -> str:
    # Chỉ cho chuyển tới đường dẫn nội bộ, không cho "?next=https://trang-khac" hay "//trang-khac" (open redirect).
    parsed = urlparse(next_url or "")
    if parsed.scheme or parsed.netloc or not (next_url or "").startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/dang-nhap")
def login_form(request: Request, next: str = "/"):
    return templates.TemplateResponse(request, "auth/login.html", {"error": None, "next": next, "username": ""})


@router.post("/dang-nhap")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    key = _fail_key(request, username)
    if len(_recent_fails(key)) >= MAX_FAILS:
        error = f"Sai mật khẩu quá {MAX_FAILS} lần. Vui lòng thử lại sau {LOCK_SECONDS // 60} phút."
        return templates.TemplateResponse(
            request, "auth/login.html", {"error": error, "next": next, "username": username}, status_code=429
        )
    user = crud.authenticate(db, username, password)
    if user is None:
        _failed.setdefault(key, []).append(time.time())
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Sai tên đăng nhập hoặc mật khẩu.", "next": next, "username": username},
            status_code=401,
        )
    _failed.pop(key, None)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(_safe_next(next), status_code=303)


@router.post("/dang-xuat")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/dang-nhap", status_code=303)


# ---- Đổi mật khẩu của chính mình ----


@router.get("/doi-mat-khau")
def change_password_form(request: Request):
    return templates.TemplateResponse(request, "auth/change_password.html", {"error": None, "saved": False})


@router.post("/doi-mat-khau")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = crud.get_user(db, request.state.user.id)
    error = None
    if not crud.authenticate(db, user.username, current_password):
        error = "Mật khẩu hiện tại không đúng."
    elif new_password != confirm_password:
        error = "Mật khẩu mới nhập lại không khớp."
    else:
        try:
            crud.set_password(db, user, new_password)
        except ValueError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        request, "auth/change_password.html", {"error": error, "saved": error is None}
    )


# ---- Quản trị tài khoản (chỉ quản trị viên — chặn ở middleware theo tiền tố /quan-tri) ----


def _users_page(request: Request, db: Session, error: str | None = None, message: str | None = None):
    return templates.TemplateResponse(
        request,
        "auth/users.html",
        {"active_page": "users", "users": crud.list_users(db), "error": error, "message": message},
    )


@router.get("/quan-tri/tai-khoan")
def users_page(request: Request, db: Session = Depends(get_db)):
    return _users_page(request, db)


@router.post("/quan-tri/tai-khoan/moi")
def create_user(
    request: Request,
    username: str = Form(...),
    ho_ten: str = Form(""),
    password: str = Form(...),
    is_admin: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user = crud.create_user(db, username, password, ho_ten=ho_ten.strip() or None, is_admin=bool(is_admin))
    except ValueError as exc:
        return _users_page(request, db, error=str(exc))
    return _users_page(request, db, message=f"Đã tạo tài khoản \"{user.username}\".")


@router.post("/quan-tri/tai-khoan/{user_id:int}/sua")
def update_user(
    request: Request,
    user_id: int,
    ho_ten: str = Form(""),
    is_admin: str = Form(""),
    is_active: str = Form(""),
    db: Session = Depends(get_db),
):
    user = crud.get_user(db, user_id)
    try:
        crud.update_user(db, user, ho_ten=ho_ten.strip() or None, is_admin=bool(is_admin), is_active=bool(is_active))
    except ValueError as exc:
        return _users_page(request, db, error=str(exc))
    return RedirectResponse("/quan-tri/tai-khoan", status_code=303)


@router.post("/quan-tri/tai-khoan/{user_id:int}/dat-mat-khau")
def reset_password(request: Request, user_id: int, password: str = Form(...), db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    try:
        crud.set_password(db, user, password)
    except ValueError as exc:
        return _users_page(request, db, error=str(exc))
    return _users_page(request, db, message=f"Đã đặt mật khẩu mới cho \"{user.username}\".")
