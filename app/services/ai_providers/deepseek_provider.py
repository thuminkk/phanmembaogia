from app.services.ai_providers.openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek dùng API tương thích OpenAI, chỉ khác base_url và tên model."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key=api_key, model=model, base_url="https://api.deepseek.com")

    def generate(self, prompt: str, image_bytes: bytes | None = None, image_mime: str | None = None) -> str:
        if image_bytes:
            raise ValueError("DeepSeek (deepseek-chat) không hỗ trợ đọc ảnh — chọn Claude, OpenAI hoặc Gemini.")
        return super().generate(prompt)
