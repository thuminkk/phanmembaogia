from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # thư mục "app/"
SOURCE_DIR = BASE_DIR.parent  # thư mục "02. Mã nguồn"
PROJECT_ROOT = SOURCE_DIR.parent  # gốc dự án "05. PHẦN MỀM BÁO GIÁ"

# Toàn bộ dữ liệu (CSDL, file tạm khi nhập Excel...) nằm ở thư mục riêng NGOÀI mã nguồn,
# để mỗi lần cập nhật/thay code trong "02. Mã nguồn" không đụng tới hay xóa mất dữ liệu.
DATA_DIR = PROJECT_ROOT / "03. Dữ liệu"
DATA_DIR.mkdir(exist_ok=True)

APP_NAME = "Quản lý giá thành"
DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"
