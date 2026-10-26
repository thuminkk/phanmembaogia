"""Copy toàn bộ dữ liệu từ CSDL SQLite cũ (03. Dữ liệu/app.db) sang PostgreSQL (Neon).

Cách chạy (trong thư mục "02. Mã nguồn"):
    .venv\\Scripts\\python scripts\\chuyen_du_lieu_sang_neon.py "postgresql://...neon.tech/neondb?sslmode=require"

- Chỉ ĐỌC file SQLite, không sửa gì trong đó.
- CSDL đích phải đang TRỐNG (chưa có dữ liệu) — có dữ liệu rồi thì dừng, không ghi đè.
- PostgreSQL bắt buộc khóa ngoại phải trỏ tới dòng có thật (SQLite không kiểm) -> dòng trỏ tới giá NCC
  đã bị xóa được sửa thành giá hiện tại của đúng linh kiện đó (hoặc để trống nếu cột cho phép).
"""
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DATA_DIR, _normalize_database_url  # noqa: E402
from app.db import models  # noqa: E402, F401 - đăng ký bảng
from app.db.database import Base  # noqa: E402

BATCH = 500


def repair_supplier_price_refs(table_name: str, rows: list[dict], price_ids: set[int], price_by_part: dict[int, int]) -> int:
    fixed = 0
    for row in rows:
        sp = row.get("supplier_price_id")
        if sp is not None and sp not in price_ids:
            new_id = price_by_part.get(row.get("part_id"))
            print(f"  sửa {table_name} id={row['id']}: supplier_price_id {sp} (đã bị xóa) -> {new_id}")
            row["supplier_price_id"] = new_id
            fixed += 1
    return fixed


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    source = create_engine(f"sqlite:///{DATA_DIR / 'app.db'}")
    target = create_engine(_normalize_database_url(sys.argv[1]))
    if target.dialect.name != "postgresql":
        sys.exit("Link CSDL đích phải là PostgreSQL (Neon).")

    Base.metadata.create_all(target)
    with target.connect() as conn:
        non_empty = [t.name for t in Base.metadata.sorted_tables if conn.scalar(select(func.count()).select_from(t))]
    if non_empty:
        sys.exit(f"CSDL đích đã có dữ liệu ở các bảng: {', '.join(non_empty)} — dừng để không ghi đè.")

    tables = Base.metadata.sorted_tables  # đã sắp theo thứ tự phụ thuộc khóa ngoại (bảng cha trước)
    with source.connect() as src:
        prices = src.execute(text("select id, part_id from part_supplier_prices")).all()
        price_ids = {p.id for p in prices}
        price_by_part = {p.part_id: p.id for p in prices}

        with target.begin() as dst:  # 1 transaction: lỗi giữa chừng thì không để lại dữ liệu dở dang
            for table in tables:
                src_cols = {r[1] for r in src.execute(text(f"pragma table_info({table.name})"))}
                if not src_cols:
                    print(f"{table.name:28} (không có trong SQLite, bỏ qua)")
                    continue
                cols = [c for c in table.columns if c.name in src_cols]
                rows = [dict(r._mapping) for r in src.execute(select(*cols))]
                if "supplier_price_id" in table.columns:
                    repair_supplier_price_refs(table.name, rows, price_ids, price_by_part)
                for i in range(0, len(rows), BATCH):
                    dst.execute(table.insert(), rows[i : i + BATCH])
                # Bảng có id tự tăng: đặt lại bộ đếm sau khi chèn id có sẵn, nếu không lần thêm mới đầu tiên sẽ trùng id.
                if "id" in table.columns and rows:
                    dst.execute(text(
                        f"select setval(pg_get_serial_sequence('{table.name}', 'id'), (select max(id) from {table.name}))"
                    ))
                print(f"{table.name:28} {len(rows):>6} dòng")

    print("\nĐối chiếu số dòng nguồn / đích:")
    ok = True
    with source.connect() as src, target.connect() as dst:
        for table in tables:
            try:
                n_src = src.scalar(text(f"select count(*) from {table.name}"))
            except Exception:
                n_src = 0
            n_dst = dst.scalar(select(func.count()).select_from(table))
            ok &= n_src == n_dst
            print(f"  {table.name:28} {n_src:>6} / {n_dst:<6} {'OK' if n_src == n_dst else 'LỆCH!'}")
    print("\nHOÀN TẤT — dữ liệu đã khớp." if ok else "\nCÓ BẢNG LỆCH SỐ DÒNG — kiểm tra lại.")


if __name__ == "__main__":
    main()
