// Gửi ngầm (fetch) 1 form sửa nhanh 1 trường ngay trong bảng (VD Loại, Đơn vị) — không chuyển
// trang/reload, tránh mất vị trí cuộn đang xem dở của người dùng.
function quickEditSubmit(el) {
    const form = document.getElementById(el.getAttribute("form"));
    if (!form) return;
    const originalValue = el.value;
    const data = new FormData(form);
    const row = el.closest("tr");

    fetch(form.action, { method: "POST", body: data })
        .then((resp) => {
            if (!resp.ok) throw new Error("save failed");
            el.defaultValue = originalValue;
            if (row) {
                row.classList.add("table-success");
                setTimeout(() => row.classList.remove("table-success"), 600);
            }
        })
        .catch(() => {
            alert("Lưu thất bại, thử lại.");
        });
}

document.addEventListener("DOMContentLoaded", function () {
    const filterForm = document.getElementById("filter-form");
    if (filterForm) {
        let debounceTimer;
        filterForm.querySelectorAll('input[type="text"]').forEach((el) => {
            el.addEventListener("input", function () {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => filterForm.submit(), 500);
            });
        });
        filterForm.querySelectorAll("select").forEach((el) => {
            el.addEventListener("change", () => filterForm.submit());
        });
    }

    const selectAll = document.getElementById("select-all");
    const rowCheckboxes = document.querySelectorAll(".row-checkbox");
    const deleteBtn = document.getElementById("bulk-delete-btn");
    const countLabel = document.getElementById("selected-count");

    function updateState() {
        const checked = document.querySelectorAll(".row-checkbox:checked").length;
        if (countLabel) countLabel.textContent = checked;
        if (deleteBtn) deleteBtn.disabled = checked === 0;
        const moveBtn = document.getElementById("bulk-move-btn");
        const moveGroup = document.getElementById("bulk-move-group");
        if (moveBtn) moveBtn.disabled = checked === 0 || !moveGroup.value;
        if (selectAll) selectAll.checked = checked > 0 && checked === rowCheckboxes.length;
    }

    if (selectAll) {
        selectAll.addEventListener("change", function () {
            rowCheckboxes.forEach((cb) => (cb.checked = selectAll.checked));
            updateState();
        });
    }
    rowCheckboxes.forEach((cb) => cb.addEventListener("change", updateState));
    document.getElementById("bulk-move-group")?.addEventListener("change", updateState);
    updateState();
});
