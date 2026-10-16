// Giữ nguyên vị trí cuộn qua các thao tác nộp-form-rồi-chuyển-hướng (Lưu/Xóa/Thêm dòng/Thêm cụm...)
// — áp dụng TOÀN CỤC cho mọi trang trong app, vì phần lớn form ở đây vẫn theo cách cũ (POST rồi
// RedirectResponse 303) chứ không phải AJAX, nên mỗi thao tác nhỏ đều load lại cả trang và kéo về
// đầu trang, rất bất tiện khi đang thao tác ở giữa/cuối 1 danh sách dài.
(function () {
    var KEY_PREFIX = "scrollY:";

    var ANCHOR_PREFIX = "scrollAnchor:";

    // Ngoài scrollY còn lưu 1 "mốc": phần tử có id gần nhất bao quanh chỗ đang thao tác (VD khối
    // "cum-body-unassigned") + vị trí của nó trên màn hình. Khi đổi cụm, dòng bị chuyển lên 1 cụm phía
    // trên -> mọi thứ bên dưới bị đẩy xuống 1 dòng; khôi phục theo mốc giữ đúng khối đang làm ở đúng
    // chỗ cũ trên màn hình, thay vì lệch đi 1 dòng như khi chỉ khôi phục scrollY.
    function findAnchor(el) {
        while (el && el !== document.body && el !== document.documentElement) {
            if (el.id && el.tagName !== "FORM") return el;
            el = el.parentElement;
        }
        return null;
    }

    function saveScrollNow(e) {
        try {
            sessionStorage.setItem(KEY_PREFIX + location.pathname, String(window.scrollY));
            // Với "submit", e.target là chính form — mà phần lớn form ở đây là form ẩn (id="pl-..",
            // "cum-..") trong hàng d-none, không có vị trí thật -> lấy nút đã bấm/ô đang focus thay thế.
            var origin = null;
            if (e && e.type === "submit") origin = e.submitter || document.activeElement;
            else if (e && e.target instanceof Element) origin = e.target;
            else origin = document.activeElement;
            var anchor = findAnchor(origin);
            if (anchor) {
                sessionStorage.setItem(
                    ANCHOR_PREFIX + location.pathname,
                    JSON.stringify({ id: anchor.id, top: anchor.getBoundingClientRect().top })
                );
            } else {
                sessionStorage.removeItem(ANCHOR_PREFIX + location.pathname);
            }
        } catch (err) {
            /* sessionStorage có thể bị chặn (private mode...) — bỏ qua, không ảnh hưởng chức năng chính */
        }
    }

    // Lưu NGAY LẬP TỨC tại thời điểm BẮT ĐẦU thao tác (bấm nút/nộp form) — không dùng cách lắng
    // nghe sự kiện "scroll" chung chung, vì thực tế kiểm bằng Playwright cho thấy: một số nút (VD
    // "Lưu tất cả") tự set disabled=true ngay khi bấm để chặn bấm 2 lần, và việc disable 1 phần tử
    // đang giữ focus khiến trình duyệt tự dời focus + TỰ CUỘN TRANG VỀ ĐẦU — sự kiện "scroll" giả
    // này sẽ bị bắt nhầm là hành động của người dùng và ghi đè mất giá trị đúng. Bắt ở pha "capture"
    // trên document để chạy TRƯỚC bất kỳ handler nào gắn trực tiếp lên chính nút đó (vốn có thể gây
    // ra side-effect cuộn giả nói trên), đảm bảo luôn lưu đúng vị trí cuộn thật trước khi việc đó
    // kịp xảy ra. Bắt cả "submit" (form nộp bình thường, kể cả bằng phím Enter) lẫn "click" trên
    // button/[type=submit]/a (các nút tự xử lý bằng fetch()+reload() không bắn sự kiện "submit").
    document.addEventListener("submit", saveScrollNow, true);
    document.addEventListener(
        "click",
        function (e) {
            if (e.target.closest("button, [type=submit], a")) saveScrollNow(e);
        },
        true
    );
    // form.submit() gọi bằng code (VD ô chọn "Cụm" có onchange="this.form.submit()") KHÔNG bắn sự
    // kiện "submit" và cũng không có click nút nào -> bọc lại hàm submit để vẫn lưu được vị trí.
    var nativeSubmit = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function () {
        saveScrollNow();
        return nativeSubmit.apply(this, arguments);
    };
    // Kéo-thả dòng (quotes.js) xong thì location.reload() — cũng không qua click/submit.
    document.addEventListener("drop", saveScrollNow, true);

    // Khôi phục ở sự kiện "load" (sau khi toàn bộ trang — CSS, ảnh, layout — đã dựng xong), KHÔNG
    // phải "DOMContentLoaded" — kiểm thực tế cho thấy ở "DOMContentLoaded" trang (đặc biệt bảng
    // dài nhiều dòng) đôi khi chưa đủ chiều cao để cuộn tới đúng vị trí cũ, khiến scrollTo() bị
    // trình duyệt tự giới hạn (clamp) về 1 giá trị thấp hơn và không tự điều chỉnh lại sau đó.
    window.addEventListener("load", function () {
        var saved = null;
        var anchor = null;
        try {
            saved = sessionStorage.getItem(KEY_PREFIX + location.pathname);
            anchor = JSON.parse(sessionStorage.getItem(ANCHOR_PREFIX + location.pathname) || "null");
            // Xóa ngay sau khi đọc — chỉ áp dụng đúng 1 lần cho lần load ngay sau submit, không áp
            // dụng lại cho các lần load sau không liên quan (VD người dùng chủ động bấm F5/mở lại tab).
            sessionStorage.removeItem(KEY_PREFIX + location.pathname);
            sessionStorage.removeItem(ANCHOR_PREFIX + location.pathname);
        } catch (e) {
            return;
        }
        if (saved === null) return;
        var el = anchor && document.getElementById(anchor.id);
        var top = el && el.getClientRects().length
            ? window.scrollY + el.getBoundingClientRect().top - anchor.top
            : parseInt(saved, 10) || 0;
        // behavior "instant": Bootstrap 5 đặt scroll-behavior: smooth cho cả trang -> scrollTo() mặc
        // định sẽ trượt từ từ (~1.5s với bảng dài) thay vì nhảy thẳng tới chỗ đang làm.
        window.scrollTo({ top: top, left: 0, behavior: "instant" });
    });
})();
