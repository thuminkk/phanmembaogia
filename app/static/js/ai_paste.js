// Cho phép dán ảnh trực tiếp (Ctrl+V) từ clipboard vào các trang "Nhập nhanh bằng AI" —
// gán ảnh dán được vào đúng ô <input type="file" name="file"> hiện có để form gửi đi như bình thường.
document.addEventListener("paste", function (e) {
    var fileInput = document.querySelector('input[type="file"][name="file"]');
    if (!fileInput) return;

    var items = (e.clipboardData || window.clipboardData || {}).items;
    if (!items) return;

    for (var i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") === 0) {
            var file = items[i].getAsFile();
            var dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;

            var preview = document.getElementById("ai-paste-preview");
            if (!preview) {
                preview = document.createElement("div");
                preview.id = "ai-paste-preview";
                preview.className = "mt-2";
                fileInput.closest(".mb-3").appendChild(preview);
            }
            preview.innerHTML =
                '<img src="' + URL.createObjectURL(file) + '" style="max-height:150px" class="img-thumbnail"> ' +
                '<span class="text-muted small">Đã dán ảnh từ clipboard</span>';

            e.preventDefault();
            break;
        }
    }
});
