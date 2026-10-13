from pydantic import BaseModel

TRANG_THAI_OPTIONS = ["nhap", "da_gui", "da_duyet", "huy"]
TRANG_THAI_LABELS = {
    "nhap": "Nháp",
    "da_gui": "Đã gửi khách",
    "da_duyet": "Đã duyệt",
    "huy": "Hủy",
}


class QuoteUpdateIn(BaseModel):
    rev: int
    dot: int
    trang_thai: str
    nguoi_tinh_gia: str | None = None
