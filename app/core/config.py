import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # thư mục "app/"
SOURCE_DIR = BASE_DIR.parent  # thư mục "02. Mã nguồn"
PROJECT_ROOT = SOURCE_DIR.parent  # gốc dự án "05. PHẦN MỀM BÁO GIÁ"

# Cấu hình bí mật (link CSDL Neon, SECRET_KEY...) đọc từ biến môi trường. Khi chạy trên máy có thể
# để trong file "02. Mã nguồn/.env" (không đưa lên GitHub, xem .gitignore). Trên Render thì khai báo
# ở mục Environment của service.
load_dotenv(SOURCE_DIR / ".env")

# Toàn bộ dữ liệu (CSDL, file tạm khi nhập Excel...) nằm ở thư mục riêng NGOÀI mã nguồn,
# để mỗi lần cập nhật/thay code trong "02. Mã nguồn" không đụng tới hay xóa mất dữ liệu.
# Trên Render ổ đĩa không lưu lâu dài -> DATA_DIR chỉ dùng cho file tạm, CSDL nằm ở Neon.
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "03. Dữ liệu")
DATA_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "Quản lý giá thành"


def _normalize_database_url(url: str) -> str:
    # Neon/Render đưa link dạng "postgres://" hoặc "postgresql://" -> chỉ rõ driver psycopg (v3) cho SQLAlchemy.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# Không khai báo DATABASE_URL -> dùng SQLite cục bộ như trước (03. Dữ liệu/app.db).
DATABASE_URL = _normalize_database_url(os.environ.get("DATABASE_URL") or f"sqlite:///{DATA_DIR / 'app.db'}")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Khóa ký cookie đăng nhập. Bắt buộc đặt cố định khi chạy thật; không đặt thì sinh ngẫu nhiên mỗi lần
# khởi động (chỉ hợp khi chạy thử trên máy — khởi động lại là mọi người phải đăng nhập lại).
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
# Chỉ gửi cookie qua HTTPS — bật trên Render (luôn có HTTPS), tắt khi chạy http://localhost.
SESSION_HTTPS_ONLY = os.environ.get("SESSION_HTTPS_ONLY", "").lower() in ("1", "true", "yes")

# Tài khoản quản trị đầu tiên: chỉ dùng khi CSDL chưa có tài khoản nào (xem app.crud.users.ensure_first_admin).
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME") or "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
