// Khung dán trực tiếp từ Excel — dán 1 vùng ô (dữ liệu dạng tab/xuống dòng) vào bảng, tự trải
// ra đúng dòng/cột kế tiếp theo đúng cột đã bấm vào, tự thêm dòng nếu paste dài hơn bảng hiện có.
document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("paste-grid");
    if (!table || typeof PASTE_GRID_COLUMNS === "undefined") return;
    const tbody = table.querySelector("tbody");
    const columns = PASTE_GRID_COLUMNS;

    function addRow() {
        const idx = tbody.rows.length;
        const tr = document.createElement("tr");
        columns.forEach((col) => {
            const td = document.createElement("td");
            const input = document.createElement("input");
            input.type = "text";
            input.name = `row_${idx}_${col}`;
            input.dataset.col = col;
            td.appendChild(input);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
        return tr;
    }

    function sanitizeForColumn(col, text) {
        text = text.trim();
        if (col === "don_gia") {
            return text.replace(/[^\d.]/g, "");
        }
        return text;
    }

    tbody.addEventListener("paste", function (e) {
        const target = e.target;
        if (!target || target.tagName !== "INPUT") return;
        const text = (e.clipboardData || window.clipboardData).getData("text/plain");
        if (!text || (text.indexOf("\t") === -1 && text.indexOf("\n") === -1)) return; // dán 1 ô, để hành vi mặc định

        e.preventDefault();

        const startRow = target.closest("tr");
        const startRowIndex = Array.prototype.indexOf.call(tbody.rows, startRow);
        const startColIndex = columns.indexOf(target.dataset.col);
        if (startColIndex === -1) return;

        const lines = text.replace(/\r/g, "").split("\n");
        while (lines.length && lines[lines.length - 1] === "") lines.pop();

        lines.forEach((lineText, r) => {
            const cells = lineText.split("\t");
            let rowEl = tbody.rows[startRowIndex + r];
            if (!rowEl) rowEl = addRow();
            cells.forEach((cellText, c) => {
                const colIndex = startColIndex + c;
                if (colIndex >= columns.length) return; // vượt quá số cột cố định, bỏ qua phần thừa
                const col = columns[colIndex];
                const input = rowEl.cells[colIndex].querySelector("input, select");
                if (input) input.value = sanitizeForColumn(col, cellText);
            });
        });

        document.getElementById("row_count").value = tbody.rows.length;
    });

    const addRowBtn = document.getElementById("add-row-btn");
    if (addRowBtn) {
        const rowsToAdd = typeof PASTE_GRID_ROWS_TO_ADD !== "undefined" ? PASTE_GRID_ROWS_TO_ADD : 1;
        addRowBtn.addEventListener("click", function () {
            for (let i = 0; i < rowsToAdd; i++) addRow();
            document.getElementById("row_count").value = tbody.rows.length;
        });
    }

    const clearGridBtn = document.getElementById("clear-grid-btn");
    if (clearGridBtn) {
        clearGridBtn.addEventListener("click", function () {
            if (!confirm("Xóa hết nội dung đã nhập trong bảng?")) return;
            tbody.querySelectorAll("input").forEach((input) => (input.value = ""));
        });
    }

    const form = document.getElementById("paste-form");
    if (form) {
        form.addEventListener("submit", function () {
            document.getElementById("row_count").value = tbody.rows.length;
        });
    }
});
