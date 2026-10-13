import datetime

from pydantic import BaseModel, ConfigDict


class SupplierPriceIn(BaseModel):
    nha_cung_cap: str
    don_gia: float
    ghi_chu: str | None = None


class SupplierPriceOut(SupplierPriceIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_id: int
    ngay_cap_nhat: datetime.datetime
    is_active: bool


class PartIn(BaseModel):
    ma_linh_kien: str | None = None
    ten_linh_kien: str
    hang: str | None = None
    loai: str | None = None
    xuat_xu: str | None = None
    don_vi: str | None = None
    ghi_chu: str | None = None


class PartOut(PartIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    suppliers: list[SupplierPriceOut] = []


class CandidateRow(BaseModel):
    """1 dòng ứng viên trước khi ghi vào DB — dùng chung cho import Excel & AI."""

    include: bool = True
    status: str  # "moi" | "cap_nhat_gia" | "khong_doi" | "bo_qua"
    ly_do_bo_qua: str | None = None
    ma_linh_kien: str | None = None
    ten_linh_kien: str | None = None
    hang: str | None = None
    loai: str | None = None
    xuat_xu: str | None = None
    nha_cung_cap: str | None = None
    don_vi: str | None = None
    don_gia: float | None = None
    gia_cu: float | None = None
    nha_cu: str | None = None
    so_luong: float | None = None  # chỉ dùng cho luồng nhập cụm mẫu (dán Excel) — các luồng khác bỏ trống
