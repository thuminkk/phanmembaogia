from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL, IS_SQLITE

if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Neon tự đóng kết nối khi rảnh (scale-to-zero) -> pool_pre_ping kiểm tra trước khi dùng lại,
    # tránh lỗi "connection closed" ở request đầu tiên sau một lúc không ai dùng.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upgrade_schema() -> None:
    """Nâng cấp bảng cũ cho khớp model (create_all chỉ tạo bảng MỚI, không sửa bảng đã có). Chạy lúc
    khởi động, gọi nhiều lần vẫn an toàn — đã nâng cấp rồi thì không làm gì.

    2026-11-05: standard_group_lines có "dòng tự do" -> thêm cột *_tu_do, part_id/supplier_price_id cho phép NULL.
    """
    from sqlalchemy import inspect, text

    table = Base.metadata.tables["standard_group_lines"]
    cols = {c["name"]: c for c in inspect(engine).get_columns("standard_group_lines")}
    with engine.begin() as conn:
        for name, ddl in (("ten_tu_do", "VARCHAR(500)"), ("don_vi_tu_do", "VARCHAR(50)"), ("gia_tu_do", "FLOAT")):
            if name not in cols:
                conn.execute(text(f"ALTER TABLE standard_group_lines ADD COLUMN {name} {ddl}"))
        if cols["part_id"]["nullable"]:
            return
        if not IS_SQLITE:
            conn.execute(text("ALTER TABLE standard_group_lines ALTER COLUMN part_id DROP NOT NULL"))
            conn.execute(text("ALTER TABLE standard_group_lines ALTER COLUMN supplier_price_id DROP NOT NULL"))
            return
        # SQLite không bỏ được NOT NULL -> dựng lại bảng theo model rồi chép dữ liệu sang (giữ nguyên id).
        names = ", ".join(c.name for c in table.columns)
        for idx in table.indexes:
            conn.execute(text(f"DROP INDEX IF EXISTS {idx.name}"))
        conn.execute(text("ALTER TABLE standard_group_lines RENAME TO _standard_group_lines_old"))
        table.create(conn)
        conn.execute(text(f"INSERT INTO standard_group_lines ({names}) SELECT {names} FROM _standard_group_lines_old"))
        conn.execute(text("DROP TABLE _standard_group_lines_old"))
