import io

import openpyxl
import pymupdf
from fastapi import UploadFile

MAX_ROWS_PER_SHEET = 500
MIN_PDF_TEXT_CHARS = 40


def excel_to_text(content: bytes) -> str:
    """Dump toàn bộ nội dung 1 file Excel thành văn bản dạng bảng để AI tự đọc/phân tích linh hoạt —
    khác với `excel_import.py` (vốn yêu cầu đúng cấu trúc cột cố định 'Tên linh kiện'/'Mã linh kiện'...),
    hàm này dùng cho luồng "Nhập nhanh bằng AI" nên không đòi hỏi bố cục cụ thể.
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        lines.append(f"--- Sheet: {ws.title} ---")
        row_count = 0
        for row in ws.iter_rows(values_only=True):
            if row_count >= MAX_ROWS_PER_SHEET:
                lines.append("... (còn nữa, đã cắt bớt)")
                break
            values = [str(v).strip() if v is not None else "" for v in row]
            if not any(values):
                continue
            lines.append(" | ".join(values))
            row_count += 1
    return "\n".join(lines)


def pdf_to_text_or_image(content: bytes) -> tuple[str, bytes | None, str | None]:
    """Trích văn bản từ PDF. Nếu PDF gần như không có lớp văn bản (PDF quét/ảnh chụp), render trang đầu
    thành ảnh PNG để AI đọc bằng khả năng nhận diện ảnh — dùng lại đúng cơ chế ảnh hiện có.
    Trả về (text, image_bytes hoặc None, image_mime hoặc None).
    """
    doc = pymupdf.open(stream=content, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc).strip()

    if len(text) >= MIN_PDF_TEXT_CHARS or len(doc) == 0:
        return text, None, None

    pix = doc[0].get_pixmap(dpi=150)
    return text, pix.tobytes("png"), "image/png"


def classify_upload(filename: str | None, content_type: str | None) -> str | None:
    """Phân loại file tải lên dựa vào đuôi file (ưu tiên) rồi tới content-type: 'image' | 'pdf' | 'excel' | None."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        return "excel"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
        return "image"

    ct = (content_type or "").lower()
    if "spreadsheet" in ct or "ms-excel" in ct:
        return "excel"
    if ct == "application/pdf":
        return "pdf"
    if ct.startswith("image/"):
        return "image"
    return None


async def resolve_ai_upload(file: UploadFile) -> tuple[str, bytes | None, str | None]:
    """Nhận 1 file tải lên bất kỳ (ảnh/PDF/Excel) từ form "Nhập nhanh bằng AI", trả về:
    (đoạn text trích thêm để nối vào tin nhắn — rỗng nếu là ảnh thuần hoặc PDF có ảnh,
     image_bytes để AI đọc ảnh — None nếu không có ảnh, image_mime tương ứng).
    Raise ValueError (thông báo tiếng Việt thân thiện) nếu không đọc được file.
    """
    content = await file.read()
    kind = classify_upload(file.filename, file.content_type)

    if kind == "image":
        return "", content, file.content_type or "image/png"

    if kind == "pdf":
        try:
            text, image_bytes, image_mime = pdf_to_text_or_image(content)
        except Exception as exc:
            raise ValueError(f"Không đọc được file PDF: {exc}") from exc
        return text, image_bytes, image_mime

    if kind == "excel":
        try:
            text = excel_to_text(content)
        except Exception as exc:
            raise ValueError(f"Không đọc được file Excel: {exc}") from exc
        return text, None, None

    raise ValueError("Định dạng file không được hỗ trợ — chỉ nhận ảnh, PDF hoặc Excel (.xlsx/.xls).")
