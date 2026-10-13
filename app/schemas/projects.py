from pydantic import BaseModel


class ProjectIn(BaseModel):
    ma_du_an: str
    ten_thiet_bi: str
    khach_hang: str | None = None
    dia_chi: str | None = None
    chung_loai: str | None = None
    yeu_cau_dac_biet: str | None = None
