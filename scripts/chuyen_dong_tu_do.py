"""Chuyển dữ liệu cũ sang "dòng tự do" (2026-11-05) — linh kiện KHÔNG có mã (tủ điện, phụ kiện khác,
dây điện...) không còn là linh kiện tiêu chuẩn trong CSDL nữa:

  1. Dòng cụm mẫu đang dùng linh kiện không mã -> dòng tự do của cụm mẫu (giữ tên, đơn vị, giá hiện tại).
  2. Dòng báo giá không mã còn gắn CSDL -> dòng tự do (giữ nguyên tên, SL, giá đang có trên báo giá).
  3. Ẩn (xóa mềm) các linh kiện không mã khỏi CSDL linh kiện.

Trước khi sửa, sao lưu toàn bộ dòng bị ảnh hưởng ra "03. Dữ liệu/backups/" (hoặc DATA_DIR/backups).

Cách chạy (trong thư mục "02. Mã nguồn"; CSDL lấy theo DATABASE_URL trong file .env, không có thì SQLite cục bộ):
    .venv\\Scripts\\python scripts\\chuyen_dong_tu_do.py            # chạy thử: chỉ in ra sẽ đổi gì
    .venv\\Scripts\\python scripts\\chuyen_dong_tu_do.py --apply    # sao lưu rồi ghi thật
Chạy lại nhiều lần vẫn an toàn (lần sau không còn gì để chuyển).
"""
import datetime
import json
import sys
from pathlib import Path

from sqlalchemy import func, or_, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import DATA_DIR  # noqa: E402
from app.db.database import Base, SessionLocal, engine, upgrade_schema  # noqa: E402
from app.db.models import Part, QuotePartLine, StandardGroupLine  # noqa: E402


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def main() -> None:
    apply = "--apply" in sys.argv
    Base.metadata.create_all(engine)
    upgrade_schema()
    with SessionLocal() as db:
        no_ma = or_(Part.ma_linh_kien.is_(None), func.trim(Part.ma_linh_kien) == "")
        parts = db.scalars(select(Part).where(no_ma)).all()
        part_ids = {p.id for p in parts}
        sg_lines = db.scalars(select(StandardGroupLine).where(StandardGroupLine.part_id.in_(part_ids))).all() if part_ids else []
        q_lines = db.scalars(
            select(QuotePartLine).where(
                QuotePartLine.part_id.is_not(None),
                or_(QuotePartLine.ma_linh_kien.is_(None), func.trim(QuotePartLine.ma_linh_kien) == ""),
            )
        ).all()
        active_parts = [p for p in parts if p.is_active]

        print(f"CSDL: {DATA_DIR if 'sqlite' in str(engine.url) else engine.url.host}")
        print(f"1. Dòng cụm mẫu -> tự do: {len(sg_lines)}")
        for l in sg_lines:
            print(f"   - [{l.standard_group.ten_cum}] {l.part.ten_linh_kien} | {l.part.don_vi or ''} | {l.don_gia:,.0f}")
        print(f"2. Dòng báo giá -> tự do: {len(q_lines)}")
        for l in q_lines:
            print(f"   - BG {l.quote_id}: {l.ten_linh_kien} | {l.don_gia:,.0f}")
        print(f"3. Ẩn linh kiện không mã: {len(active_parts)}")
        if not apply:
            print("\n(Chạy thử — chưa ghi gì. Thêm --apply để sao lưu rồi ghi thật.)")
            return
        if not (sg_lines or q_lines or active_parts):
            print("Không có gì để chuyển.")
            return

        backup_dir = DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"chuyen_dong_tu_do_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
        backup.write_text(json.dumps({
            "standard_group_lines": [_row(l) for l in sg_lines],
            "quote_part_lines": [_row(l) for l in q_lines],
            "parts": [_row(p) for p in active_parts],
        }, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
        print(f"Đã sao lưu: {backup}")

        for l in sg_lines:
            l.ten_tu_do, l.don_vi_tu_do, l.gia_tu_do = l.part.ten_linh_kien, l.part.don_vi, l.don_gia
            l.part_id = None
            l.supplier_price_id = None
        for l in q_lines:
            l.part_id = None
            l.supplier_price_id = None
        for p in active_parts:
            p.is_active = False
        db.commit()
        print("Xong.")


if __name__ == "__main__":
    main()
