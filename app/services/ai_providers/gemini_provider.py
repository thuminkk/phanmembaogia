from app.services.ai_providers.base import AIProvider


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-flash-lite-latest"):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, image_bytes: bytes | None = None, image_mime: str | None = None) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        parts = [prompt]
        if image_bytes:
            parts.append({"mime_type": image_mime or "image/png", "data": image_bytes})
        response = model.generate_content(parts)
        return response.text
