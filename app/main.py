from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_NAME, BASE_DIR
from app.db import models  # noqa: F401 - đăng ký model với Base trước khi create_all
from app.db.database import Base, engine
from app.routers import (
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

app = FastAPI(title=APP_NAME)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

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
