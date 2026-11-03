"""Định nghĩa "Phiếu yêu cầu" cho tính năng Tự lên BOM bằng AI — 1 nơi duy nhất khai báo các nhóm/trường:
template tự vẽ form theo danh sách này, AI nhận lại đúng nhãn tiếng Việt của từng trường.
Thêm/bớt/sửa trường chỉ cần sửa SECTIONS (phiếu cũ đã lưu vẫn đọc được, trường thiếu coi như để trống)."""

HANG_PLC = ["Mitsubishi", "LS", "Omron", "Keyence", "Siemens", "Panasonic", "Delta", "Khác"]
HANG_DONG_CAT = ["Mitsubishi", "LS", "Schneider", "Idec", "Fuji", "Khác"]
HANG_KHI_NEN = ["SMC", "Airtac", "Festo", "Pisco", "CKD", "Koganei", "Khác"]
HANG_SERVO = ["Mitsubishi", "Panasonic", "Yaskawa", "Omron", "LS", "Delta", "Khác"]

# (key, nhãn, kiểu, tuỳ chọn) — kiểu: text | number | select | check | textarea
SECTIONS = [
    ("chung", "Thông tin chung", [
        ("loai_may", "Loại máy / chức năng", "text", None),
        ("nguon_cap", "Nguồn cấp", "select", ["3 pha 380V", "3 pha 220V", "1 pha 220V"]),
        ("hang_plc", "Hãng PLC / HMI", "select", HANG_PLC),
        ("hang_dong_cat", "Hãng thiết bị đóng cắt", "select", HANG_DONG_CAT),
        ("tong_cong_suat_kw", "Tổng công suất tải ước tính (kW)", "number", None),
        ("tieu_chuan", "Tiêu chuẩn / yêu cầu khách (CE, an toàn...)", "text", None),
    ]),
    ("tu_dien", "Tủ điện", [
        ("so_tu_dien", "Số tủ điện", "number", None),
        ("kich_thuoc_tu", "Kích thước tủ (nếu đã biết)", "text", None),
        ("safety_relay", "Có mạch an toàn (safety relay)", "check", None),
        ("quat_lam_mat", "Quạt làm mát tủ", "check", None),
        ("o_cam_den_tu", "Ổ cắm + đèn trong tủ", "check", None),
    ]),
    ("hmi", "HMI / Bảng điều khiển", [
        ("hmi_inch", "Màn hình HMI", "select", ["Không có", "4.3 inch", "7 inch", "10 inch", "12 inch", "15 inch"]),
        ("nut_an_phi", "Cỡ nút ấn", "select", ["Phi 22", "Phi 16"]),
        ("so_nut_co_den", "Số nút ấn có đèn", "number", None),
        ("so_nut_khong_den", "Số nút ấn không đèn", "number", None),
        ("so_dung_khan", "Số nút dừng khẩn", "number", None),
        ("so_cong_tac_chon", "Số công tắc chọn / key switch", "number", None),
        ("so_den_bao", "Số đèn báo", "number", None),
        ("den_thap", "Đèn tháp", "check", None),
        ("coi_bao", "Còi báo", "check", None),
        ("so_hop_nut_rieng", "Số hộp nút ấn rời", "number", None),
    ]),
    ("khi_nen", "Khí nén", [
        ("hang_khi_nen", "Hãng khí nén", "select", HANG_KHI_NEN),
        ("so_van_52_don", "Số van 5/2 đơn (1 cuộn coil)", "number", None),
        ("so_van_52_kep", "Số van 5/2 kép (2 cuộn coil)", "number", None),
        ("so_van_53", "Số van 5/3", "number", None),
        ("so_xi_lanh", "Số xi lanh khí", "number", None),
        ("frl_size", "Cụm FRL (lọc-điều áp)", "select", ["Không có", "Size 20", "Size 30", "Size 40"]),
        ("so_van_thoi_khi", "Số van thổi khí", "number", None),
        ("so_cb_ap_suat", "Số cảm biến áp suất", "number", None),
        ("van_cap_khi_tong", "Van cấp/xả khí tổng (soft start)", "check", None),
    ]),
    ("thuy_luc", "Thủy lực", [
        ("co_thuy_luc", "Có hệ thủy lực", "check", None),
        ("cong_suat_bom_kw", "Công suất bơm (kW)", "number", None),
        ("ap_suat_bar", "Áp suất làm việc (bar)", "number", None),
        ("so_van_tl", "Số van điện từ thủy lực", "number", None),
        ("so_xi_lanh_tl", "Số xi lanh thủy lực", "number", None),
    ]),
    ("dong_co", "Servo / Động cơ", [
        ("hang_servo", "Hãng servo / biến tần", "select", HANG_SERVO),
        ("so_truc_servo", "Số trục servo", "number", None),
        ("cong_suat_servo", "Công suất từng trục (VD: 2x100W, 1x400W)", "text", None),
        ("so_servo_phanh", "Số trục có phanh", "number", None),
        ("so_bien_tan", "Số biến tần", "number", None),
        ("cong_suat_bien_tan", "Công suất biến tần (VD: 2x0.75kW)", "text", None),
        ("so_dong_co_thuong", "Số động cơ thường (không biến tần)", "number", None),
        ("so_xi_lanh_dien", "Số xi lanh điện", "number", None),
    ]),
    ("cam_bien", "Cảm biến", [
        ("so_cb_tiem_can", "Cảm biến tiệm cận", "number", None),
        ("so_cb_quang", "Cảm biến quang", "number", None),
        ("so_cb_soi_quang", "Cảm biến sợi quang", "number", None),
        ("so_cb_xi_lanh", "Cảm biến từ xi lanh", "number", None),
        ("so_cb_hanh_trinh", "Công tắc hành trình", "number", None),
        ("cb_khac", "Cảm biến khác (VD: 2 cảm biến GT2 Keyence)", "text", None),
    ]),
    ("dac_biet", "Thiết bị đặc biệt", [
        ("so_rfid", "RFID (số đầu đọc)", "number", None),
        ("so_camera", "Camera", "number", None),
        ("so_loadcell", "Loadcell", "number", None),
        ("pc_cong_nghiep", "PC công nghiệp", "check", None),
        ("may_doc_ma", "Máy đọc mã vạch/QR (số lượng)", "number", None),
        ("thiet_bi_khac", "Thiết bị khác", "text", None),
    ]),
]

MO_TA_KEY = "mo_ta_them"


def all_fields():
    for _key, _label, fields in SECTIONS:
        yield from fields


def parse_form(form) -> dict:
    """Đọc phiếu từ form HTML -> dict chỉ gồm trường có giá trị (bỏ trống / 0 / "Không có")."""
    data = {}
    for key, _label, kind, _opts in all_fields():
        raw = form.get(key)
        if kind == "check":
            if raw:
                data[key] = True
            continue
        value = (raw or "").strip()
        if not value or value == "Không có":
            continue
        if kind == "number":
            try:
                number = float(value)
            except ValueError:
                continue
            if number <= 0:
                continue
            data[key] = int(number) if number.is_integer() else number
        else:
            data[key] = value
    mo_ta = (form.get(MO_TA_KEY) or "").strip()
    if mo_ta:
        data[MO_TA_KEY] = mo_ta
    return data


def describe(data: dict) -> str:
    """Phiếu -> văn bản theo nhóm để đưa cho AI (và hiện lại cho người dùng)."""
    lines = []
    for _key, section_label, fields in SECTIONS:
        items = []
        for key, label, kind, _opts in fields:
            if key not in data:
                continue
            items.append(f"- {label}: {'Có' if kind == 'check' else data[key]}")
        if items:
            lines.append(f"[{section_label}]")
            lines.extend(items)
    if data.get(MO_TA_KEY):
        lines.append("[Mô tả thêm]")
        lines.append(data[MO_TA_KEY])
    return "\n".join(lines) or "(phiếu trống)"
