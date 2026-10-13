class AIProvider:
    """Giao diện chung: mỗi provider chỉ cần biết cách gửi 1 prompt (+ ảnh tuỳ chọn) và trả về text thô."""

    def generate(self, prompt: str, image_bytes: bytes | None = None, image_mime: str | None = None) -> str:
        raise NotImplementedError
