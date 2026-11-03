"""Tự lên BOM (danh sách linh kiện chia theo cụm) bằng AI từ "Phiếu yêu cầu" + học dần kinh nghiệm.

Luồng: phiếu (bom_form) -> prompt gồm [toàn bộ cụm mẫu + kinh nghiệm đã duyệt + vài lần làm trước] -> AI trả
về các cụm, mỗi dòng trỏ thẳng tới 1 dòng cụm mẫu (L<id>) hoặc là linh kiện ngoài cụm mẫu -> đối chiếu CSDL
-> người dùng duyệt/sửa -> tạo vào báo giá. Sau đó so sánh đề xuất với báo giá cuối cùng (diff) để AI rút
bài học; bài học được người dùng duyệt mới lưu vào AiExperience và dùng cho các lần sau.
"""
import json
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.crud.settings import get_settings
from app.db.models import AiExperience, BomRequest, Part, QuotePartLine, StandardGroup, StandardGroupLine
from app.services import bom_form
from app.services.ai_extract import PROVIDER_LABELS, _build_provider

BOM_MAX_TOKENS = 16000
EXAMPLE_COUNT = 2

BOM_PROMPT = """Bạn là kỹ sư báo giá của 1 công ty chế tạo máy tự động hoá (tủ điện, HMI, khí nén, thủy lực,
servo, cảm biến). Nhiệm vụ: từ PHIẾU YÊU CẦU bên dưới, lên danh sách linh kiện (BOM) CHIA THEO CỤM, bám sát
các CỤM MẪU mà công ty đang dùng.

QUY TẮC:
1. Mỗi cụm trong BOM nên dựa trên 1 cụm mẫu phù hợp nhất (đúng hãng, đúng size theo phiếu). Ghi "cum_mau_id".
   Không có cụm mẫu phù hợp thì cum_mau_id = null.
2. Cụm mẫu là DANH MỤC TUỲ CHỌN, thường chứa nhiều biến thể cùng loại (VD manifold 2F/4F/6F..., bộ nguồn
   60W/120W/240W, đủ màu đèn báo). CHỈ chọn đúng biến thể cần dùng, KHÔNG lấy hết.
3. Dòng lấy từ cụm mẫu: dùng {{"L": <số sau chữ L>, "sl": <số lượng>}}. Số lượng phải tính theo phiếu
   (số van, số trục, số nút...), không chép nguyên SL mẫu nếu phiếu khác.
4. Linh kiện cần mà không có trong cụm mẫu nào: dùng {{"ma": "<mã nếu chắc chắn, không thì "">", "ten": "<tên
   tiếng Anh kỹ thuật>", "hang": "<hãng>", "sl": <số>, "ly_do": "<vì sao cần>"}}. KHÔNG bịa mã nếu không chắc.
5. "ly_do" ngắn gọn cho dòng có lựa chọn không hiển nhiên (chọn biến thể/size, cách tính SL). Dòng hiển nhiên bỏ trống.
6. Áp dụng các KINH NGHIỆM CÔNG TY bên dưới — đó là cách làm đã được kiểm chứng, ưu tiên hơn suy luận chung.
7. Chỗ phiếu thiếu thông tin quan trọng: tự giả định hợp lý và ghi vào "luu_y" để người dùng kiểm tra.

PHIẾU YÊU CẦU:
{phieu}

KINH NGHIỆM CÔNG TY (đã được duyệt):
{kinh_nghiem}

CÁC LẦN LÊN BOM TRƯỚC (phiếu -> BOM cuối cùng người dùng đã chốt, tham khảo cách làm):
{vi_du}

DANH MỤC CỤM MẪU (mỗi dòng: L<id> | mã | tên | hãng | SL mẫu):
{cum_mau}

Chỉ trả về duy nhất 1 object JSON, không markdown, không giải thích, đúng dạng:
{{"cum": [{{"ten_cum": "...", "cum_mau_id": 7, "dong": [{{"L": 123, "sl": 1, "ly_do": ""}}, {{"ma": "", "ten": "...", "hang": "...", "sl": 2, "ly_do": "..."}}]}}],
 "luu_y": ["..."]}}
"""

LESSON_PROMPT = """Bạn là trợ lý rút kinh nghiệm cho việc lên BOM tự động của 1 công ty chế tạo máy.
AI đã đề xuất BOM từ phiếu yêu cầu; người dùng (kỹ sư báo giá) đã sửa lại thành BOM cuối cùng.
Dưới đây là phiếu, các thay đổi người dùng đã làm, và ghi chú của người dùng (nếu có).

Hãy rút ra 0-6 BÀI HỌC NGẮN, TỔNG QUÁT HOÁ được cho các lần sau (quy tắc chọn biến thể, cách tính số lượng,
linh kiện hay bị thiếu/thừa, hãng ưu tiên...). Không ghi bài học chỉ đúng riêng cho dự án này. Không lặp lại
kinh nghiệm đã có. Nếu thay đổi không cho thấy quy luật gì thì trả về mảng rỗng.

PHIẾU YÊU CẦU:
{phieu}

THAY ĐỔI CỦA NGƯỜI DÙNG SO VỚI ĐỀ XUẤT:
{diff}

GHI CHÚ CỦA NGƯỜI DÙNG:
{ghi_chu}

KINH NGHIỆM ĐÃ CÓ:
{kinh_nghiem}

Chỉ trả về mảng JSON, không markdown: [{{"nhom": "Tủ điện|HMI|Khí nén|Thủy lực|Servo/Động cơ|Cảm biến|Chung", "noi_dung": "..."}}]
"""


# ---- Gọi AI ----


def _call_ai(db: Session, prompt: str) -> tuple[str, str]:
    settings = get_settings(db)
    label = PROVIDER_LABELS.get(settings.active_provider, settings.active_provider)
    provider = _build_provider(settings)
    try:
        return provider.generate(prompt, max_tokens=BOM_MAX_TOKENS), label
    except Exception as exc:
        raise ValueError(f"Lỗi khi gọi API {label}: {exc}") from exc


def _parse_json(raw: str, opener: str, closer: str):
    text = re.sub(r"^```(json)?|```$", "", raw.strip()).strip()
    start, end = text.find(opener), text.rfind(closer)
    if start == -1 or end == -1:
        raise ValueError("AI không trả về JSON hợp lệ. Nội dung nhận được: " + raw[:300])
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Không đọc được JSON do AI trả về (có thể bị cắt vì quá dài): {exc}") from exc


def _number(value, default: float = 1) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


# ---- Ngữ cảnh đưa cho AI ----


def _catalog_block(db: Session) -> str:
    groups = db.scalars(
        select(StandardGroup)
        .where(StandardGroup.is_active.is_(True))
        .options(selectinload(StandardGroup.lines).selectinload(StandardGroupLine.part))
        .order_by(StandardGroup.ten_cum)
    ).all()
    out = []
    for g in groups:
        out.append(f"### [cum_mau_id={g.id}] {g.ten_cum}" + (f" — {g.mo_ta}" if g.mo_ta else ""))
        for line in g.lines:
            p = line.part
            if p is None:
                continue
            out.append(f"L{line.id} | {p.ma_linh_kien or '-'} | {p.ten_linh_kien} | {p.hang or '-'} | {line.so_luong:g}")
    return "\n".join(out) or "(chưa có cụm mẫu)"


def active_experiences(db: Session) -> list[AiExperience]:
    return db.scalars(
        select(AiExperience).where(AiExperience.is_active.is_(True)).order_by(AiExperience.nhom, AiExperience.id)
    ).all()


def _experience_block(db: Session) -> str:
    items = active_experiences(db)
    return "\n".join(f"- [{e.nhom or 'Chung'}] {e.noi_dung}" for e in items) or "(chưa có)"


def final_lines(db: Session, req: BomRequest) -> list[QuotePartLine]:
    """Các dòng HIỆN TẠI của báo giá trong những cụm mà lần lên BOM này đã tạo/ghi vào — tức BOM sau khi
    người dùng đã chỉnh sửa (kể cả sửa sau này trên trang báo giá)."""
    group_ids = json.loads(req.applied_json or "{}").get("group_ids", [])
    if not group_ids:
        return []
    return db.scalars(
        select(QuotePartLine)
        .where(QuotePartLine.quote_id == req.quote_id, QuotePartLine.group_id.in_(group_ids))
        .options(selectinload(QuotePartLine.group))
        .order_by(QuotePartLine.group_id, QuotePartLine.thu_tu)
    ).all()


def _examples_block(db: Session, exclude_id: int | None = None) -> str:
    reqs = db.scalars(
        select(BomRequest)
        .where(BomRequest.applied_at.is_not(None), BomRequest.id != (exclude_id or 0))
        .order_by(BomRequest.learned_at.desc().nulls_last(), BomRequest.applied_at.desc())
        .limit(EXAMPLE_COUNT)
    ).all()
    blocks = []
    for req in reqs:
        lines = final_lines(db, req)
        if not lines:
            continue
        by_group: dict[str, list[str]] = {}
        for l in lines:
            by_group.setdefault(l.group.ten_cum if l.group else "?", []).append(
                f"{l.ma_linh_kien or l.ten_linh_kien}×{l.so_luong:g}"
            )
        bom = "\n".join(f"  * {name}: {', '.join(items)}" for name, items in by_group.items())
        blocks.append(f"--- Phiếu:\n{bom_form.describe(json.loads(req.form_json))}\n--- BOM đã chốt:\n{bom}")
    return "\n\n".join(blocks) or "(chưa có)"


# ---- Lên BOM ----


def _match_part(db: Session, ma: str, hang: str) -> Part | None:
    if not ma:
        return None
    query = select(Part).where(Part.is_active.is_(True), func.lower(Part.ma_linh_kien) == ma.lower())
    candidates = db.scalars(query).all()
    if not candidates:
        return None
    same_hang = [p for p in candidates if (p.hang or "").lower() == (hang or "").lower()]
    return (same_hang or candidates)[0]


def _item_from_part(part: Part, so_luong: float, ly_do: str, nguon: str, nguon_ten: str = "") -> dict:
    price = part.price
    return {
        "nguon": nguon,  # mau = dòng cụm mẫu | csdl = khớp mã trong CSDL | moi = chưa có trong CSDL
        "nguon_ten": nguon_ten,
        "part_id": part.id,
        "ma": part.ma_linh_kien or "",
        "ten": part.ten_linh_kien,
        "hang": part.hang or "",
        "don_vi": part.don_vi or "",
        "don_gia": price.don_gia if price else 0,
        "sl": so_luong,
        "ly_do": ly_do,
    }


def generate_bom(db: Session, form_data: dict) -> tuple[dict, str]:
    """Gọi AI lên BOM -> (đề xuất đã đối chiếu CSDL, tên nhà cung cấp AI)."""
    prompt = BOM_PROMPT.format(
        phieu=bom_form.describe(form_data),
        kinh_nghiem=_experience_block(db),
        vi_du=_examples_block(db),
        cum_mau=_catalog_block(db),
    )
    raw, label = _call_ai(db, prompt)
    data = _parse_json(raw, "{", "}")

    proposal = {"cum": [], "luu_y": [str(x) for x in data.get("luu_y") or [] if x]}
    for cum in data.get("cum") or []:
        sg_id = cum.get("cum_mau_id")
        sg = db.get(StandardGroup, sg_id) if isinstance(sg_id, int) else None
        out = {"ten_cum": (cum.get("ten_cum") or (sg.ten_cum if sg else "Cụm mới")).strip(),
               "cum_mau_id": sg.id if sg else None, "cum_mau_ten": sg.ten_cum if sg else "", "dong": []}
        for d in cum.get("dong") or []:
            sl = _number(d.get("sl"))
            ly_do = (d.get("ly_do") or "").strip()
            ref = d.get("L")
            if ref is not None:
                try:
                    sgl = db.get(StandardGroupLine, int(str(ref).lstrip("Ll")))
                except ValueError:
                    sgl = None
                if sgl is None or sgl.part is None:
                    proposal["luu_y"].append(f"AI trỏ tới dòng cụm mẫu L{ref} không tồn tại — đã bỏ qua.")
                    continue
                out["dong"].append(_item_from_part(sgl.part, sl, ly_do, "mau", sgl.standard_group.ten_cum))
                continue
            ma, ten, hang = (d.get("ma") or "").strip(), (d.get("ten") or "").strip(), (d.get("hang") or "").strip()
            part = _match_part(db, ma, hang)
            if part is not None:
                out["dong"].append(_item_from_part(part, sl, ly_do, "csdl"))
            elif ten or ma:
                out["dong"].append({"nguon": "moi", "nguon_ten": "", "part_id": None, "ma": ma, "ten": ten or ma,
                                    "hang": hang, "don_vi": "", "don_gia": 0, "sl": sl, "ly_do": ly_do})
        if out["dong"]:
            proposal["cum"].append(out)
    if not proposal["cum"]:
        raise ValueError("AI không đề xuất được linh kiện nào — thử bổ sung thông tin vào phiếu.")
    return proposal, label


# ---- Rút kinh nghiệm ----


def _key(part_id, ma, ten) -> str:
    return f"p{part_id}" if part_id else "m" + " ".join((ma or ten or "").split()).casefold()


def compute_diff(db: Session, req: BomRequest) -> list[str]:
    """So đề xuất AI với BOM hiện tại trong báo giá -> danh sách thay đổi dạng câu (đưa cho AI + hiện cho người dùng)."""
    proposal = json.loads(req.proposal_json or "{}")
    # Cụm đề xuất thứ i đã được ghi vào cụm báo giá nào (người dùng có thể đổi tên / gộp vào cụm có sẵn
    # lúc duyệt) -> so cụm theo id thật, không theo tên, để đổi tên không bị tính là "chuyển cụm".
    cum_group_ids = json.loads(req.applied_json or "{}").get("cum_group_ids", [])
    proposed: dict[str, tuple[int | None, str, float, str]] = {}
    for i, cum in enumerate(proposal.get("cum", [])):
        gid = cum_group_ids[i] if i < len(cum_group_ids) else None
        for d in cum["dong"]:
            proposed[_key(d.get("part_id"), d.get("ma"), d.get("ten"))] = (
                gid, cum["ten_cum"], d["sl"], f"{d.get('ma') or '-'} {d.get('ten')} ({d.get('hang') or '-'})")
    final: dict[str, tuple[int | None, str, float, str]] = {}
    for l in final_lines(db, req):
        k = _key(l.part_id, l.ma_linh_kien, l.ten_linh_kien)
        if k not in proposed:
            # Dòng "Mới" của AI chưa có part_id lúc đề xuất -> lúc tạo mới có; khớp lại theo mã/tên.
            k = _key(None, l.ma_linh_kien, l.ten_linh_kien)
        old = final.get(k)
        final[k] = (l.group_id, l.group.ten_cum if l.group else "?", (old[2] if old else 0) + l.so_luong,
                    f"{l.ma_linh_kien or '-'} {l.ten_linh_kien} ({l.hang or '-'})")

    changes = []
    for k, (gid, cum, sl, label) in proposed.items():
        if k not in final:
            changes.append(f"BỎ khỏi cụm \"{cum}\": {label} (AI đề xuất SL {sl:g})")
            continue
        f_gid, f_cum, f_sl, _ = final[k]
        if f_sl != sl:
            changes.append(f"SỬA SL trong cụm \"{f_cum}\": {label} — AI {sl:g} -> chốt {f_sl:g}")
        if gid is not None and f_gid != gid:
            changes.append(f"CHUYỂN CỤM: {label} — AI để ở \"{cum}\" -> chốt ở \"{f_cum}\"")
    for k, (_gid, cum, sl, label) in final.items():
        if k not in proposed:
            changes.append(f"THÊM vào cụm \"{cum}\": {label} × {sl:g} (AI không đề xuất)")
    return changes


def suggest_lessons(db: Session, req: BomRequest, changes: list[str], ghi_chu: str) -> list[dict]:
    prompt = LESSON_PROMPT.format(
        phieu=bom_form.describe(json.loads(req.form_json)),
        diff="\n".join(f"- {c}" for c in changes) or "(không thay đổi gì)",
        ghi_chu=ghi_chu or "(không có)",
        kinh_nghiem=_experience_block(db),
    )
    raw, _label = _call_ai(db, prompt)
    items = _parse_json(raw, "[", "]")
    return [
        {"nhom": (i.get("nhom") or "Chung").strip(), "noi_dung": (i.get("noi_dung") or "").strip()}
        for i in items if isinstance(i, dict) and (i.get("noi_dung") or "").strip()
    ]
