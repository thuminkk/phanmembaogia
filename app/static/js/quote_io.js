// Trang Tính toán IO: bỏ nút "Lưu" riêng từng dòng, chỉ còn nút "Lưu tất cả" chung (2 nút giống hệt
// nhau — 1 ở đầu trang, 1 ở cuối trang, để không phải cuộn lên/xuống mới bấm được) — vẫn lưu từng
// dòng qua đúng form/request riêng của dòng đó (không gộp thành 1 request lớn), chỉ là bấm 1 lần để
// kích hoạt lưu hết mọi dòng đang có trên trang (cả bảng I/O lẫn bảng Cấu hình PLC).
document.addEventListener("DOMContentLoaded", function () {
    const btns = Array.from(document.querySelectorAll(".save-all-io-btn"));
    if (!btns.length) return;

    function setBtnsState(disabled, text) {
        btns.forEach((b) => {
            b.disabled = disabled;
            b.textContent = text;
        });
    }

    btns.forEach((btn) => {
        btn.addEventListener("click", function () {
            const forms = Array.from(document.querySelectorAll('form[id^="io-"], form[id^="plc-"]'));
            if (!forms.length) return;
            setBtnsState(true, "Đang lưu...");
            Promise.all(forms.map((form) => fetch(form.action, { method: "POST", body: new FormData(form) })))
                .then(() => location.reload())
                .catch(() => {
                    alert("Có lỗi khi lưu — vui lòng thử lại.");
                    setBtnsState(false, "Lưu tất cả");
                });
        });
    });
});
