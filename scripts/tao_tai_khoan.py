"""Tạo tài khoản hoặc đặt lại mật khẩu từ dòng lệnh — dùng khi chưa có tài khoản nào hoặc quên mật khẩu quản trị.

Cách chạy (trong thư mục "02. Mã nguồn"; CSDL lấy theo DATABASE_URL trong file .env, không có thì SQLite cục bộ):
    .venv\\Scripts\\python scripts\\tao_tai_khoan.py <tên đăng nhập> <mật khẩu> [--admin]

Tên đăng nhập đã tồn tại -> đặt lại mật khẩu (và kích hoạt lại nếu đang bị khóa).
"""
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.crud import users as crud  # noqa: E402
from app.db import models  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--admin"]
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    username, password = args
    is_admin = "--admin" in sys.argv
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = db.scalar(select(models.User).where(func.lower(models.User.username) == username.lower()))
        try:
            if user:
                crud.set_password(db, user, password)
                user.is_active = True
                user.is_admin = user.is_admin or is_admin
                db.commit()
                print(f"Đã đặt lại mật khẩu cho \"{user.username}\" (quản trị: {user.is_admin}).")
            else:
                user = crud.create_user(db, username, password, is_admin=is_admin)
                print(f"Đã tạo tài khoản \"{user.username}\" (quản trị: {user.is_admin}).")
        except ValueError as exc:
            sys.exit(str(exc))


if __name__ == "__main__":
    main()
