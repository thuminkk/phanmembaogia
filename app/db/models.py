import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Part(Base):
    """Định danh 1 linh kiện là cặp (mã linh kiện, hãng) — khác mã HOẶC khác hãng là 2 linh kiện khác nhau."""

    __tablename__ = "parts"
    __table_args__ = (UniqueConstraint("ma_linh_kien", "hang", name="uq_part_ma_hang"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ma_linh_kien: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ten_linh_kien: Mapped[str] = mapped_column(String(500))
    hang: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    loai: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    xuat_xu: Mapped[str | None] = mapped_column(String(255), nullable=True)
    don_vi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    suppliers: Mapped[list["PartSupplierPrice"]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )

    @property
    def price(self) -> "PartSupplierPrice | None":
        """Giá/NCC duy nhất đang hiệu lực của linh kiện này (tối đa 1, xem PartSupplierPrice)."""
        active = [s for s in self.suppliers if s.is_active]
        return active[0] if active else None


class PartSupplierPrice(Base):
    """Giá + nhà cung cấp DUY NHẤT của 1 linh kiện (đã đổi từ đa-NCC sang 1-NCC/1-giá 2026-09-23) —
    ràng buộc unique trên part_id đảm bảo mỗi Part có tối đa 1 dòng giá."""

    __tablename__ = "part_supplier_prices"
    __table_args__ = (UniqueConstraint("part_id", name="uq_supplier_price_part"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    nha_cung_cap: Mapped[str] = mapped_column(String(255))
    don_gia: Mapped[float] = mapped_column(Float, default=0)
    ngay_cap_nhat: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    part: Mapped["Part"] = relationship(back_populates="suppliers")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ma_du_an: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    ten_thiet_bi: Mapped[str] = mapped_column(String(500))
    khach_hang: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dia_chi: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chung_loai: Mapped[str | None] = mapped_column(String(255), nullable=True)
    yeu_cau_dac_biet: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    quotes: Mapped[list["Quote"]] = relationship(back_populates="project")


class Quote(Base):
    """1 phiên bản báo giá. project_id NULL + is_template=True nghĩa là 1 mẫu dùng chung, không thuộc dự án nào."""

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("project_id", "rev", "dot", name="uq_quote_project_rev_dot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    rev: Mapped[int] = mapped_column(Integer, default=0)
    dot: Mapped[int] = mapped_column(Integer, default=1)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ten_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    khach_hang: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trang_thai: Mapped[str] = mapped_column(String(50), default="nhap")
    ngay_bao_gia: Mapped[datetime.date | None] = mapped_column(DateTime, nullable=True)
    nguoi_tinh_gia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    du_phong_io_percent: Mapped[float] = mapped_column(Float, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    project: Mapped["Project | None"] = relationship(back_populates="quotes")
    part_lines: Mapped[list["QuotePartLine"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuotePartLine.thu_tu"
    )
    material_lines: Mapped[list["QuoteMaterialLine"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )
    fabricated_lines: Mapped[list["QuoteFabricatedLine"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )
    groups: Mapped[list["QuoteComponentGroup"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuoteComponentGroup.thu_tu"
    )
    io_lines: Mapped[list["QuoteIOLine"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuoteIOLine.thu_tu"
    )
    plc_lines: Mapped[list["QuotePLCLine"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", order_by="QuotePLCLine.thu_tu"
    )

    @property
    def ma_bao_gia(self) -> str:
        if self.is_template:
            return self.ten_template or f"Mẫu #{self.id}"
        ma = self.project.ma_du_an if self.project else "?"
        return f"{ma}-{self.rev:02d}-{self.dot:02d}"


class QuoteComponentGroup(Base):
    """Cụm linh kiện (VD: cụm tủ điện, cụm van...) — nhóm các dòng linh kiện tiêu chuẩn để dễ quản lý,
    đồng thời lưu mô tả kỹ thuật theo 4 mảng (đúng cấu trúc sheet SPEC trong file báo giá mẫu)."""

    __tablename__ = "quote_component_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    ten_cum: Mapped[str] = mapped_column(String(255))
    mo_ta_co_khi: Mapped[str | None] = mapped_column(Text, nullable=True)
    mo_ta_dien: Mapped[str | None] = mapped_column(Text, nullable=True)
    mo_ta_khi_nen: Mapped[str | None] = mapped_column(Text, nullable=True)
    mo_ta_thuy_luc: Mapped[str | None] = mapped_column(Text, nullable=True)
    thu_tu: Mapped[int] = mapped_column(Integer, default=0)

    quote: Mapped["Quote"] = relationship(back_populates="groups")
    part_lines: Mapped[list["QuotePartLine"]] = relationship(
        back_populates="group", order_by="QuotePartLine.thu_tu"
    )


class QuotePartLine(Base):
    """1 dòng linh kiện bán sẵn trong báo giá — giá là bản chụp tại thời điểm thêm, không tự đổi theo CSDL sau đó."""

    __tablename__ = "quote_part_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("quote_component_groups.id"), nullable=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"), nullable=True)
    supplier_price_id: Mapped[int | None] = mapped_column(ForeignKey("part_supplier_prices.id"), nullable=True)
    ten_linh_kien: Mapped[str] = mapped_column(String(500))
    ma_linh_kien: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hang: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nha_cung_cap: Mapped[str | None] = mapped_column(String(255), nullable=True)
    don_vi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    so_luong: Mapped[float] = mapped_column(Float, default=1)
    don_gia: Mapped[float] = mapped_column(Float, default=0)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    thu_tu: Mapped[int] = mapped_column(Integer, default=0)

    quote: Mapped["Quote"] = relationship(back_populates="part_lines")
    group: Mapped["QuoteComponentGroup | None"] = relationship(back_populates="part_lines")
    part: Mapped["Part | None"] = relationship()
    supplier_price: Mapped["PartSupplierPrice | None"] = relationship()

    @property
    def thanh_tien(self) -> float:
        return self.so_luong * self.don_gia

    @property
    def gia_lech_csdl(self) -> bool:
        """True nếu giá dòng báo giá này khác với giá hiện tại của đúng NCC đó trong CSDL linh kiện."""
        return self.supplier_price is not None and self.don_gia != self.supplier_price.don_gia


class QuoteMaterialLine(Base):
    __tablename__ = "quote_material_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    chung_loai: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quy_cach: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vat_lieu: Mapped[str | None] = mapped_column(String(255), nullable=True)
    xuat_xu: Mapped[str | None] = mapped_column(String(255), nullable=True)
    don_vi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    so_luong: Mapped[float] = mapped_column(Float, default=1)
    don_gia: Mapped[float] = mapped_column(Float, default=0)
    nha_cung_cap: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quote: Mapped["Quote"] = relationship(back_populates="material_lines")


class QuoteFabricatedLine(Base):
    __tablename__ = "quote_fabricated_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    ten_linh_kien: Mapped[str] = mapped_column(String(500))
    ma_ban_ve: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vat_lieu: Mapped[str | None] = mapped_column(String(255), nullable=True)
    so_luong: Mapped[float] = mapped_column(Float, default=1)
    don_gia: Mapped[float] = mapped_column(Float, default=0)
    nha_cung_cap: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)

    quote: Mapped["Quote"] = relationship(back_populates="fabricated_lines")


class QuoteIOLine(Base):
    """1 dòng trong bảng tính I/O (nhu cầu vào/ra) — theo đúng cấu trúc sheet "Tính toán IO" tham khảo:
    dòng "là nhóm" chỉ có tên (VD "Tủ HMI", "Khí nén") để phân nhóm hiển thị, không có số liệu.
    Tổng số input/output = số lượng × số input/output trên 1 thiết bị, tính khi hiển thị (không lưu)."""

    __tablename__ = "quote_io_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    thu_tu: Mapped[int] = mapped_column(Integer, default=0)
    la_nhom: Mapped[bool] = mapped_column(Boolean, default=False)
    ten_thiet_bi: Mapped[str] = mapped_column(String(500))
    so_luong: Mapped[float | None] = mapped_column(Float, nullable=True)
    so_input: Mapped[float | None] = mapped_column(Float, nullable=True)
    so_output: Mapped[float | None] = mapped_column(Float, nullable=True)

    quote: Mapped["Quote"] = relationship(back_populates="io_lines")

    @property
    def tong_input(self) -> float:
        if self.la_nhom or self.so_luong is None or self.so_input is None:
            return 0
        return self.so_luong * self.so_input

    @property
    def tong_output(self) -> float:
        if self.la_nhom or self.so_luong is None or self.so_output is None:
            return 0
        return self.so_luong * self.so_output


class QuotePLCLine(Base):
    """1 dòng trong bảng "Cấu hình PLC" — thiết bị/module PLC thực tế chọn, để đối chiếu số I/O
    khả dụng với nhu cầu tính ở QuoteIOLine (kèm dự phòng)."""

    __tablename__ = "quote_plc_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    thu_tu: Mapped[int] = mapped_column(Integer, default=0)
    ten_thiet_bi: Mapped[str] = mapped_column(String(500))
    so_luong: Mapped[float | None] = mapped_column(Float, nullable=True)
    so_input: Mapped[float | None] = mapped_column(Float, nullable=True)
    so_output: Mapped[float | None] = mapped_column(Float, nullable=True)

    quote: Mapped["Quote"] = relationship(back_populates="plc_lines")

    @property
    def tong_input(self) -> float:
        if self.so_luong is None or self.so_input is None:
            return 0
        return self.so_luong * self.so_input

    @property
    def tong_output(self) -> float:
        if self.so_luong is None or self.so_output is None:
            return 0
        return self.so_luong * self.so_output


class StandardGroup(Base):
    """Cụm linh kiện tiêu chuẩn dùng chung (VD: Cụm HMI, Cụm nút ấn, Cụm FRL...) — không gắn báo giá
    nào, dùng để thêm nhanh cả cụm vào bất kỳ báo giá nào qua apply_standard_group_to_quote()."""

    __tablename__ = "standard_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ten_cum: Mapped[str] = mapped_column(String(255))
    mo_ta: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    lines: Mapped[list["StandardGroupLine"]] = relationship(
        back_populates="standard_group", cascade="all, delete-orphan"
    )

    @property
    def tong_gia(self) -> float:
        """Giá thành ước tính của cả cụm = tổng (SL × đơn giá CSDL hiện tại) — tính khi hiển thị, không lưu."""
        return sum(line.thanh_tien for line in self.lines)

    @property
    def so_dong_chua_co_gia(self) -> int:
        """Số dòng chưa có giá (0đ) — tổng cụm khi đó đang thấp hơn thực tế."""
        return sum(1 for line in self.lines if not line.don_gia)


class StandardGroupLine(Base):
    __tablename__ = "standard_group_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    standard_group_id: Mapped[int] = mapped_column(ForeignKey("standard_groups.id"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    supplier_price_id: Mapped[int] = mapped_column(ForeignKey("part_supplier_prices.id"))
    so_luong: Mapped[float] = mapped_column(Float, default=1)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)

    standard_group: Mapped["StandardGroup"] = relationship(back_populates="lines")
    part: Mapped["Part"] = relationship()
    supplier_price: Mapped["PartSupplierPrice"] = relationship()

    @property
    def don_gia(self) -> float:
        """Đơn giá LIVE từ CSDL — cùng nguồn giá mà apply_group_to_quote() dùng khi áp cụm vào báo giá."""
        price = self.supplier_price if self.supplier_price and self.supplier_price.is_active else self.part.price
        return price.don_gia if price else 0

    @property
    def thanh_tien(self) -> float:
        return self.so_luong * self.don_gia


class AISettings(Base):
    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active_provider: Mapped[str] = mapped_column(String(50), default="claude")
    claude_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    openai_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gemini_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deepseek_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)


class User(Base):
    """Tài khoản đăng nhập. is_admin: được quản lý tài khoản và trang Cài đặt (API key AI);
    mọi tài khoản đều xem/sửa được dữ liệu linh kiện, dự án, báo giá như nhau."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    ho_ten: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
