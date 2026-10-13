from sqlalchemy import distinct, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Project, Quote
from app.schemas.projects import ProjectIn


def list_projects(
    db: Session,
    ma_du_an: str | None = None,
    ten_thiet_bi: str | None = None,
    khach_hang: str | None = None,
) -> list[Project]:
    query = select(Project).where(Project.is_active.is_(True))
    if ma_du_an:
        query = query.where(Project.ma_du_an.ilike(f"%{ma_du_an}%"))
    if ten_thiet_bi:
        query = query.where(Project.ten_thiet_bi.ilike(f"%{ten_thiet_bi}%"))
    if khach_hang:
        query = query.where(Project.khach_hang == khach_hang)
    query = query.order_by(Project.created_at.desc())
    return db.scalars(query).all()


def distinct_khach_hang(db: Session) -> list[str]:
    rows = db.scalars(
        select(distinct(Project.khach_hang))
        .where(Project.is_active.is_(True), Project.khach_hang.is_not(None))
        .order_by(Project.khach_hang)
    ).all()
    return [r for r in rows if r]


def get_project(db: Session, project_id: int) -> Project | None:
    return db.get(Project, project_id)


def create_project(db: Session, data: ProjectIn) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"Mã dự án '{data.ma_du_an}' đã tồn tại.") from exc
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, data: ProjectIn) -> Project:
    for field, value in data.model_dump().items():
        setattr(project, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"Mã dự án '{data.ma_du_an}' đã tồn tại.") from exc
    db.refresh(project)
    return project


def list_quotes_for_project(db: Session, project_id: int) -> list[Quote]:
    return db.scalars(
        select(Quote)
        .where(Quote.project_id == project_id, Quote.is_active.is_(True))
        .order_by(Quote.dot.desc(), Quote.rev.desc())
    ).all()


def delete_project(db: Session, project: Project) -> None:
    """Xoá HẲN dự án khỏi CSDL (2026-09-30: đổi từ xoá mềm sang xoá thật theo yêu cầu người dùng —
    xoá mềm trước đây chỉ ẩn đi chứ không giải phóng dữ liệu, gây tồn đọng vĩnh viễn). Xoá kèm TOÀN
    BỘ báo giá/rev thuộc dự án (kể cả những rev đã bị ẩn từ trước) — mỗi Quote bị xoá qua ORM
    (db.delete) để tự cuốn theo đúng cascade "all, delete-orphan" đã khai báo trên Quote
    (part_lines/material_lines/fabricated_lines/groups/io_lines/plc_lines), không cần tự tay xoá
    từng bảng con. Project.quotes tự nó KHÔNG có cascade delete nên phải lặp xoá từng Quote trước."""
    for quote in list(project.quotes):
        db.delete(quote)
    db.delete(project)
    db.commit()
