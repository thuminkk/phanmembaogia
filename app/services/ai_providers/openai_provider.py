import base64

from app.services.ai_providers.base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, image_bytes: bytes | None = None, image_mime: str | None = None) -> str:
        from openai import OpenAI

        if image_bytes:
            data_url = f"data:{image_mime or 'image/png'};base64,{base64.b64encode(image_bytes).decode('ascii')}"
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        else:
            content = prompt

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content
