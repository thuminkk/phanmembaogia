// Nút "Chọn tất cả" cho các bảng xem trước sau khi phân tích AI/Excel/dán trực tiếp —
// người dùng không cần tick từng dòng một, đặc biệt hữu ích khi nhiều dòng bị đánh dấu
// "Bỏ qua" (chưa tick sẵn) nhưng người dùng vẫn muốn lưu tất cả.
document.addEventListener("DOMContentLoaded", function () {
    const selectAll = document.getElementById("select-all-preview");
    if (!selectAll) return;
    const checkboxes = document.querySelectorAll(".row-include-checkbox");

    selectAll.addEventListener("change", function () {
        checkboxes.forEach((cb) => (cb.checked = selectAll.checked));
    });
});
