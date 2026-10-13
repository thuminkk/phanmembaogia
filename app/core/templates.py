from fastapi.templating import Jinja2Templates

from app.core.config import APP_NAME, BASE_DIR

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["app_name"] = APP_NAME


def static_url(path: str) -> str:
    """URL cho 1 file tĩnh (css/js) kèm ?v=<thời điểm sửa file gần nhất> — buộc trình duyệt tải lại
    đúng bản mới nhất mỗi khi file thay đổi, thay vì giữ mãi bản cũ đã cache (StaticFiles mặc định
    không gửi Cache-Control, nhưng trình duyệt vẫn có thể tự suy đoán cache theo Last-Modified,
    từng gây hiện tượng "sửa code rồi mà hành vi trên trình duyệt vẫn như cũ")."""
    file_path = BASE_DIR / "static" / path
    try:
        version = int(file_path.stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{path}?v={version}"


templates.env.globals["static_url"] = static_url
