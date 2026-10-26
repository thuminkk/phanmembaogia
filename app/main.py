from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import APP_NAME, BASE_DIR, SECRET_KEY, SESSION_HTTPS_ONLY
from app.crud import users as users_crud
from app.db import models  # noqa: F401 - đăng ký model với Base trước khi create_all
from app.db.database import Base, SessionLocal, engine
from app.routers import (
    auth,
    dashboard,
    parts,
    parts_ai,
    parts_confirm,
    parts_import,
    parts_paste,
    projects,
    quote_io,
    quote_templates,
    quotes,
    quotes_ai,
    quotes_paste,
    settings,
    standard_groups,
    standard_groups_ai,
    standard_groups_paste,
)

Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    users_crud.ensure_first_admin(_db)

# Tắt trang /docs tự sinh của FastAPI — không cần cho người dùng, và không nên phơi danh sách API ra internet.
app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)

# Các đường dẫn không cần đăng nhập; mọi trang khác đều bắt đăng nhập.
PUBLIC_PATHS = ("/dang-nhap", "/healthz", "/static/")
# Chỉ quản trị viên: quản lý tài khoản + Cài đặt (chứa API key AI).
ADMIN_PATHS = ("/quan-tri", "/cai-dat")


def _load_active_user(user_id: int):
    with SessionLocal() as db:
        user = users_crud.get_user(db, user_id)
        return user if user and user.is_active else None


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path.startswith(PUBLIC_PATHS):
        return await call_next(request)
    user_id = request.session.get("user_id")
    user = await run_in_threadpool(_load_active_user, user_id) if user_id else None
    if user is None:
        request.session.clear()
        target = path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/dang-nhap?next={quote(target)}", status_code=303)
    if path.startswith(ADMIN_PATHS) and not user.is_admin:
        return HTMLResponse("Chỉ quản trị viên mới truy cập được trang này.", status_code=403)
    request.state.user = user
    return await call_next(request)


# Thêm SAU middleware require_login để bọc ngoài nó (Starlette: middleware thêm sau chạy trước) —
# request.session phải có sẵn khi require_login chạy.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="baogia_session",
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(parts_import.router)
app.include_router(parts_ai.router)
app.include_router(parts_confirm.router)
app.include_router(parts_paste.router)
app.include_router(settings.router)
app.include_router(parts.router)
app.include_router(projects.router)
app.include_router(quote_templates.router)
app.include_router(standard_groups_ai.router)
app.include_router(standard_groups_paste.router)
app.include_router(standard_groups.router)
app.include_router(quotes_ai.router)
app.include_router(quotes_paste.router)
app.include_router(quote_io.router)
app.include_router(quotes.router)
