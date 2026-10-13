import json
import re

from sqlalchemy.orm import Session

from app.crud.parts import LOAI_OPTIONS, get_ma_hang_reference
from app.crud.settings import get_settings
from app.db.models import AISettings
from app.services.ai_providers.claude_provider import ClaudeProvider
from app.services.ai_providers.deepseek_provider import DeepSeekProvider
from app.services.ai_providers.gemini_provider import GeminiProvider
from app.services.ai_providers.openai_provider import OpenAIProvider

PROVIDER_LABELS = {
    "claude": "Claude (Anthropic)",
    "openai": "OpenAI",
    "gemini": "Gemini (Google)",
    "deepseek": "DeepSeek",
}

PROVIDER_SUPPORTS_VISION = {
    "claude": True,
    "openai": True,
    "gemini": True,
    "deepseek": False,
}

PROMPT_TEMPLATE = """Bạn nhận được tin nhắn và/hoặc hình ảnh báo giá của nhà cung cấp linh kiện cơ khí/điện/khí nén
(có thể là ảnh chụp bảng linh kiện, ảnh chụp tin nhắn, hoặc văn bản thuần). Tin nhắn thực tế thường RẤT NGẮN
(VD chỉ có mã + giá, không ghi rõ tên hay hãng) — bạn phải tự suy luận phần còn thiếu từ chính mã linh kiện.

{reference}

Hãy tách thông tin thành 1 mảng JSON, mỗi phần tử là 1 linh kiện với các trường sau (để trống "" hoặc null nếu không có):
- ma_linh_kien: mã/model linh kiện, giữ nguyên chính xác như trong tin nhắn/ảnh
- hang: hãng sản xuất (maker). QUAN TRỌNG — đây là trường hay bị bỏ trống oan, hãy làm theo đúng thứ tự sau
  trước khi kết luận không xác định được:
  1) Nếu tin nhắn/ảnh nêu rõ hãng → dùng luôn.
  2) Nếu không, đối chiếu tiền tố/kiểu đặt mã của mã linh kiện với danh sách "Mã linh kiện công ty đã từng nhập"
     ở trên — nếu giống cùng 1 series/tiền tố với hãng nào đó đã có, đó gần như chắc chắn là hãng đó.
  3) Nếu vẫn chưa rõ, dùng kiến thức của bạn về quy ước đặt mã của các hãng công nghiệp phổ biến
     (SMC, Mitsubishi Electric, Omron, Festo, IDEC, Autonics, Hanyoung Nux, Schneider Electric, Fuji Electric,
     Panasonic, Keyence, LS Electric, Sick, v.v.) để nhận diện hãng từ chính mã — nhiều hãng có tiền tố
     hoặc cấu trúc mã rất đặc trưng, đừng bỏ cuộc quá sớm.
  4) CHỈ để trống "" nếu sau khi thử cả 3 bước trên vẫn thực sự không có căn cứ nào — tuyệt đối không bịa/đoán
     đại 1 hãng ngẫu nhiên chỉ vì mã "nhìn giống" hàng công nghiệp.
- ten_linh_kien: tên tiếng Anh CHÍNH THỨC của linh kiện do chính hãng đặt cho đúng mã/model đó (tra theo
  catalogue/datasheet thực tế của hãng đã xác định ở trên — VD mã SMC "CDG1FN32-150Z" → "Air Cylinder, Guide
  Rod Type"). Nếu xác định được hãng nhưng không chắc chắn tên gọi chính xác, dịch nghĩa sát nhất sang tiếng
  Anh kỹ thuật chuẩn ngành (Title Case). CHỈ để trống "" nếu hoàn toàn không có căn cứ để đoán ngay cả loại
  sản phẩm chung chung — KHÔNG bịa ra 1 tên loại sản phẩm cụ thể (VD "Solenoid Valve") nếu không có căn cứ
  thực sự, vì để trống sẽ được đánh dấu cần người dùng kiểm tra lại tay, còn bịa sai sẽ bị lưu nhầm vào CSDL.
- loai: phân loại kỹ thuật của linh kiện — CHỈ được chọn đúng 1 trong các giá trị sau: "Điện", "Khí nén", "Thủy lực", "Cơ khí", "Khác"
  (dựa vào tên/mã/mô tả linh kiện để đoán; nếu không đủ căn cứ để đoán chắc thì để trống "")
- xuat_xu: xuất xứ
- nha_cung_cap: tên nhà cung cấp gửi tin nhắn/ảnh (nếu có nêu, không thì để trống)
- don_vi: đơn vị tính
- don_gia: đơn giá, CHỈ là số (VND), không kèm đơn vị tiền tệ hay dấu phẩy phân cách nghìn
- so_luong: số lượng đặt/mua của linh kiện đó, CHỈ là số, nếu tin nhắn/ảnh có nêu rõ (VD "SL: 5", "x3", "5 cái",
  "số lượng 10"...). Để trống null nếu không thấy đề cập số lượng — KHÔNG tự mặc định là 1.

Chỉ trả về duy nhất mảng JSON, không thêm giải thích, không thêm markdown code fence.

Tin nhắn (có thể để trống nếu chỉ có ảnh):
---
{text}
---
"""


def _build_provider(settings: AISettings):
    provider = settings.active_provider
    if provider == "claude":
        if not settings.claude_api_key:
            raise ValueError("Chưa cấu hình API key cho Claude trong Cài đặt.")
        return ClaudeProvider(settings.claude_api_key)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("Chưa cấu hình API key cho OpenAI trong Cài đặt.")
        return OpenAIProvider(settings.openai_api_key)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("Chưa cấu hình API key cho Gemini trong Cài đặt.")
        return GeminiProvider(settings.gemini_api_key)
    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("Chưa cấu hình API key cho DeepSeek trong Cài đặt.")
        return DeepSeekProvider(settings.deepseek_api_key)
    raise ValueError(f"Nhà cung cấp AI không hợp lệ: {provider}")


def _build_reference_block(db: Session) -> str:
    groups = get_ma_hang_reference(db)
    if not groups:
        return ""
    lines = ["Mã linh kiện công ty đã từng nhập, theo hãng (tham khảo để nhận diện hãng cho mã mới cùng series/tiền tố):"]
    for hang, ma_list in groups:
        lines.append(f"- {hang}: {', '.join(ma_list)}")
    return "\n".join(lines)


def _parse_json_array(raw_text: str) -> list[dict]:
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("AI không trả về dữ liệu dạng danh sách hợp lệ. Nội dung nhận được: " + raw_text[:300])
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Không đọc được JSON do AI trả về: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("AI không trả về 1 danh sách linh kiện.")
    return data


def extract_candidates(
    db: Session, text: str, image_bytes: bytes | None = None, image_mime: str | None = None
) -> list[dict]:
    settings = get_settings(db)
    label = PROVIDER_LABELS.get(settings.active_provider, settings.active_provider)
    if image_bytes and not PROVIDER_SUPPORTS_VISION.get(settings.active_provider, False):
        raise ValueError(f"{label} không hỗ trợ đọc ảnh — chọn Claude, OpenAI hoặc Gemini trong Cài đặt.")
    provider = _build_provider(settings)
    prompt = PROMPT_TEMPLATE.format(text=text or "(không có)", reference=_build_reference_block(db))
    try:
        raw = provider.generate(prompt, image_bytes, image_mime)
    except Exception as exc:
        raise ValueError(f"Lỗi khi gọi API {label}: {exc}") from exc
    items = _parse_json_array(raw)

    rows = []
    for item in items:
        don_gia = item.get("don_gia")
        try:
            don_gia = float(don_gia) if don_gia not in (None, "") else None
        except (TypeError, ValueError):
            don_gia = None
        loai = (item.get("loai") or "").strip() or None
        if loai not in LOAI_OPTIONS:
            loai = None
        so_luong = item.get("so_luong")
        try:
            so_luong = float(so_luong) if so_luong not in (None, "") else None
        except (TypeError, ValueError):
            so_luong = None
        rows.append(
            {
                "ten_linh_kien": (item.get("ten_linh_kien") or "").strip() or None,
                "ma_linh_kien": (item.get("ma_linh_kien") or "").strip() or None,
                "loai": loai,
                "hang": (item.get("hang") or "").strip() or None,
                "xuat_xu": (item.get("xuat_xu") or "").strip() or None,
                "nha_cung_cap": (item.get("nha_cung_cap") or "").strip() or None,
                "don_vi": (item.get("don_vi") or "").strip() or None,
                "don_gia": don_gia,
                "so_luong": so_luong,
            }
        )
    return rows
