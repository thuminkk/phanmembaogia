document.addEventListener("DOMContentLoaded", function () {
    initDragDropReorder();
    initCollapseAllGroups();
    initSaveAllLines();
    initGroupSelectAll();
    initReplacePart();

    const searchBox = document.getElementById("part-search");
    if (!searchBox) return;

    const resultsBox = document.getElementById("part-search-results");
    const fieldIds = ["ten_linh_kien", "ma_linh_kien", "hang", "nha_cung_cap", "don_vi", "don_gia"];
    const hiddenPartId = document.getElementById("line-part-id");
    const hiddenSupplierPriceId = document.getElementById("line-supplier-price-id");

    function clearLink() {
        hiddenPartId.value = "";
        hiddenSupplierPriceId.value = "";
    }

    fieldIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("input", clearLink);
    });

    let debounceTimer;
    searchBox.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        const q = searchBox.value.trim();
        if (!q) {
            resultsBox.innerHTML = "";
            return;
        }
        debounceTimer = setTimeout(() => {
            fetch("/linh-kien/tim-kiem?q=" + encodeURIComponent(q))
                .then((r) => r.json())
                .then((parts) => renderResults(parts));
        }, 300);
    });

    function renderResults(parts) {
        resultsBox.innerHTML = "";
        if (!parts.length) {
            resultsBox.innerHTML = '<div class="list-group-item text-muted small">Không tìm thấy</div>';
            return;
        }
        parts.forEach((p) => {
            const suppliers = p.suppliers.length ? p.suppliers : [{ supplier_price_id: null, nha_cung_cap: "", don_gia: 0 }];
            suppliers.forEach((sp) => {
                const item = document.createElement("button");
                item.type = "button";
                item.className = "list-group-item list-group-item-action small";
                item.textContent =
                    (p.ma_linh_kien || "(chưa có mã)") + " — " + p.ten_linh_kien +
                    " — " + (p.hang || "?") + " — " + sp.nha_cung_cap +
                    " — " + Number(sp.don_gia).toLocaleString("vi-VN") + "đ";
                item.addEventListener("click", function () {
                    document.getElementById("ten_linh_kien").value = p.ten_linh_kien;
                    document.getElementById("ma_linh_kien").value = p.ma_linh_kien || "";
                    document.getElementById("hang").value = p.hang || "";
                    document.getElementById("nha_cung_cap").value = sp.nha_cung_cap || "";
                    document.getElementById("don_vi").value = p.don_vi || "";
                    document.getElementById("don_gia").value = sp.don_gia || 0;
                    hiddenPartId.value = p.part_id;
                    hiddenSupplierPriceId.value = sp.supplier_price_id || "";
                    resultsBox.innerHTML = "";
                    searchBox.value = "";
                });
                resultsBox.appendChild(item);
            });
        });
    }
});

function initCollapseAllGroups() {
    // Nhớ trạng thái thu gọn/mở của TỪNG cụm vào localStorage (theo đúng URL trang báo giá này) —
    // để sau khi di chuyển/xóa/thêm cụm (mỗi thao tác đều load lại cả trang), các cụm đã thu gọn để
    // xem tổng quan KHÔNG bị tự mở lại hết. Chỉ là tiện ích hiển thị riêng trên máy người xem, không
    // phải dữ liệu nghiệp vụ, nên lưu ở trình duyệt (localStorage) thay vì CSDL là hợp lý.
    const cumBodies = document.querySelectorAll(".cum-body.collapse");
    if (!cumBodies.length) return;

    const storageKey = "quoteGroupCollapse:" + location.pathname;

    function loadState() {
        try {
            return JSON.parse(localStorage.getItem(storageKey) || "{}");
        } catch (e) {
            return {};
        }
    }
    function saveState(state) {
        try {
            localStorage.setItem(storageKey, JSON.stringify(state));
        } catch (e) {
            /* localStorage có thể bị chặn (private mode...) — bỏ qua, không ảnh hưởng chức năng chính */
        }
    }

    // Áp lại trạng thái đã lưu NGAY khi tải trang, trước khi Bootstrap tạo Collapse instance cho
    // từng cụm (Bootstrap đọc class "show" hiện có làm trạng thái ban đầu ngay lần đầu cần tới,
    // nên chỉnh trực tiếp classList ở đây — không qua API .hide() — để không tự bắn sự kiện thừa).
    const savedState = loadState();
    cumBodies.forEach((el) => {
        if (savedState[el.id] === true) {
            el.classList.remove("show");
            document.querySelectorAll(`[data-bs-target="#${el.id}"]`).forEach((btn) => {
                btn.classList.add("collapsed");
                btn.setAttribute("aria-expanded", "false");
            });
        }
    });

    // Ghi lại mỗi khi 1 cụm thật sự đóng/mở xong — bắt sự kiện của chính Bootstrap nên tự động bao
    // luôn cả 2 trường hợp: bấm mũi tên từng cụm riêng, VÀ bấm "Thu gọn tất cả"/"Mở tất cả" (2 nút
    // đó cũng gọi qua đúng API Collapse show()/hide() nên vẫn bắn đúng các sự kiện này).
    cumBodies.forEach((el) => {
        el.addEventListener("shown.bs.collapse", () => {
            const state = loadState();
            state[el.id] = false;
            saveState(state);
        });
        el.addEventListener("hidden.bs.collapse", () => {
            const state = loadState();
            state[el.id] = true;
            saveState(state);
        });
    });

    const collapseAllBtn = document.getElementById("collapse-all-groups");
    const expandAllBtn = document.getElementById("expand-all-groups");

    function toggleAll(show) {
        cumBodies.forEach((el) => {
            bootstrap.Collapse.getOrCreateInstance(el, { toggle: false })[show ? "show" : "hide"]();
        });
    }

    if (collapseAllBtn) collapseAllBtn.addEventListener("click", () => toggleAll(false));
    if (expandAllBtn) expandAllBtn.addEventListener("click", () => toggleAll(true));
}

function initSaveAllLines() {
    // Vẫn lưu từng dòng riêng biệt như nút "Lưu" của từng dòng (mỗi dòng 1 form/1 request riêng,
    // KHÔNG gộp thành 1 request lớn) — chỉ bấm 1 lần để kích hoạt lưu tất cả các form đang có trên
    // trang, tránh rủi ro của việc gộp toàn bộ ô nhập liệu vào 1 lần submit duy nhất.
    const btn = document.getElementById("save-all-lines");
    if (!btn) return;

    btn.addEventListener("click", function () {
        const forms = Array.from(document.querySelectorAll('form[id^="pl-"]'));
        if (!forms.length) return;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = "Đang lưu...";
        Promise.all(forms.map((form) => fetch(form.action, { method: "POST", body: new FormData(form) })))
            .then(() => location.reload())
            .catch(() => {
                alert("Có lỗi khi lưu — vui lòng thử lại.");
                btn.disabled = false;
                btn.textContent = originalText;
            });
    });
}

function initGroupSelectAll() {
    // Mỗi bảng (từng cụm + bảng "Chưa phân cụm") có 1 checkbox "chọn tất cả" riêng ở đầu cột —
    // bên cạnh checkbox "Chọn tất cả" chung toàn trang đã có sẵn (app/static/js/parts.js, dùng lại
    // nguyên vẹn, không đụng vào). Tick/tắt 1 dòng vẫn tự đồng bộ lại đúng trạng thái checkbox
    // của riêng bảng đó (đủ/thiếu), và dispatch "change" trên từng row-checkbox để logic đếm
    // số dòng đã chọn + bật nút "Xóa đã chọn" trong parts.js tự cập nhật theo, không cần viết lại.
    const groupCheckboxes = document.querySelectorAll(".group-select-all");
    if (!groupCheckboxes.length) return;

    function syncGroupCheckbox(table) {
        const groupCb = table.querySelector(".group-select-all");
        const rowCbs = table.querySelectorAll(".row-checkbox");
        if (groupCb) groupCb.checked = rowCbs.length > 0 && Array.from(rowCbs).every((cb) => cb.checked);
    }

    groupCheckboxes.forEach((cb) => {
        const table = cb.closest("table");
        if (!table) return;
        cb.addEventListener("change", function () {
            // Chốt sẵn trạng thái đích TRƯỚC khi lặp — không đọc lại cb.checked bên trong vòng lặp,
            // vì mỗi lần dispatchEvent bên dưới chạy đồng bộ tới syncGroupCheckbox(), và hàm đó ghi
            // đè ngược cb.checked (thành false) ngay khi thấy còn dòng chưa xử lý tới — khiến các
            // dòng xử lý sau dòng đầu tiên bị đọc nhầm giá trị false vừa bị ghi đè đó.
            const shouldCheck = cb.checked;
            table.querySelectorAll(".row-checkbox").forEach((rowCb) => {
                rowCb.checked = shouldCheck;
                rowCb.dispatchEvent(new Event("change", { bubbles: true }));
            });
        });
        table.querySelectorAll(".row-checkbox").forEach((rowCb) => {
            rowCb.addEventListener("change", () => syncGroupCheckbox(table));
        });
    });
}

function initDragDropReorder() {
    const zones = document.querySelectorAll(".drop-zone");
    const handles = document.querySelectorAll(".drag-handle");
    if (!zones.length || !handles.length) return;

    let draggedRow = null;
    let dropHandled = false;

    // Kéo bắt đầu CHỈ từ tay cầm ⠿⠿ (không phải cả dòng) — tránh xung đột với việc
    // bấm/gõ vào các ô input trong dòng, vốn là nguyên nhân khiến thao tác kéo trước đây
    // không nhất quán (có lúc kéo được, có lúc lại chỉ focus vào ô nhập).
    handles.forEach((handle) => {
        handle.addEventListener("dragstart", function (e) {
            const tr = handle.closest("tr[data-line-id]");
            if (!tr) return;
            draggedRow = tr;
            dropHandled = false;
            tr.classList.add("dragging-row");
            e.dataTransfer.effectAllowed = "move";
            try {
                e.dataTransfer.setDragImage(tr, 20, 20);
            } catch (err) {
                /* một số trình duyệt không hỗ trợ setDragImage, bỏ qua */
            }
        });

        handle.addEventListener("dragend", function () {
            // Luôn dọn trạng thái mờ khi kết thúc kéo, kể cả khi thả ra ngoài vùng hợp lệ
            // (trước đây bị kẹt mờ vĩnh viễn nếu không thả trúng bảng).
            if (draggedRow) draggedRow.classList.remove("dragging-row");
            const wasHandled = dropHandled;
            draggedRow = null;
            if (!wasHandled) {
                // Thả hụt ra ngoài (huỷ kéo): DOM có thể đã bị dời chỗ khi rê chuột qua các
                // bảng nhưng chưa lưu gì lên máy chủ — tải lại để khớp đúng dữ liệu thật.
                location.reload();
            }
        });
    });

    zones.forEach((tbody) => {
        tbody.addEventListener("dragover", function (e) {
            if (!draggedRow) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            const targetRow = e.target.closest("tr[data-line-id]");
            if (targetRow && targetRow !== draggedRow) {
                const rect = targetRow.getBoundingClientRect();
                const before = (e.clientY - rect.top) / rect.height < 0.5;
                const referenceNode = before ? targetRow : targetRow.nextSibling;
                // Chỉ di chuyển DOM khi thực sự đổi vị trí — tránh giật/rung khi chuột đứng yên.
                if (draggedRow.nextSibling !== referenceNode) {
                    targetRow.parentNode.insertBefore(draggedRow, referenceNode);
                }
            } else if (!targetRow && !tbody.contains(draggedRow)) {
                tbody.appendChild(draggedRow);
            }
        });

        tbody.addEventListener("drop", function (e) {
            e.preventDefault();
            if (!draggedRow) return;
            dropHandled = true;
            const quoteId = tbody.dataset.quoteId;
            const groupId = tbody.dataset.groupId;
            const lineIds = Array.from(tbody.querySelectorAll("tr[data-line-id]")).map((tr) => tr.dataset.lineId);
            fetch(`/bao-gia/${quoteId}/linh-kien/sap-xep`, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "group_id=" + encodeURIComponent(groupId) + "&line_ids=" + encodeURIComponent(lineIds.join(",")),
            }).then(() => location.reload());
        });
    });
}

function initReplacePart() {
    // Nút "⇄ Thay" trên từng dòng linh kiện báo giá -> hộp tìm linh kiện khác trong CSDL -> chọn 1 kết
    // quả là nộp form thay luôn (server giữ SL/cụm/vị trí/ghi chú, lấy tên/mã/giá theo linh kiện mới).
    const modalEl = document.getElementById("replace-part-modal");
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);
    const searchBox = document.getElementById("rp-search");
    const resultsBox = document.getElementById("rp-results");
    const currentBox = document.getElementById("rp-current");
    const allWrap = document.getElementById("rp-all-wrap");
    const allBox = document.getElementById("rp-all");
    const allLabel = document.getElementById("rp-all-label");
    const form = document.getElementById("rp-form");
    const fmt = (n) => Number(n || 0).toLocaleString("vi-VN");
    let current = null;
    let debounceTimer;

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    document.querySelectorAll(".replace-part-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            current = btn.dataset;
            currentBox.textContent =
                (current.ma || "(không mã)") + " — " + current.ten + " — " + (current.hang || "?") +
                " — " + fmt(current.gia) + "đ × " + current.soLuong;
            const n = parseInt(current.cungLinhKien, 10) || 1;
            allWrap.hidden = n <= 1;
            allBox.checked = false;
            allLabel.textContent = "Thay luôn cả " + n + " dòng đang dùng linh kiện này trong báo giá";
            searchBox.value = current.ten;
            resultsBox.innerHTML = "";
            modal.show();
            search();
        });
    });

    modalEl.addEventListener("shown.bs.modal", () => {
        searchBox.focus();
        searchBox.select();
    });

    searchBox.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(search, 300);
    });

    function search() {
        const q = searchBox.value.trim();
        if (!q) {
            resultsBox.innerHTML = "";
            return;
        }
        fetch("/linh-kien/tim-kiem?q=" + encodeURIComponent(q))
            .then((r) => r.json())
            .then(render);
    }

    function render(parts) {
        resultsBox.innerHTML = "";
        if (!parts.length) {
            resultsBox.appendChild(el("div", "list-group-item text-muted small", "Không tìm thấy trong CSDL"));
            return;
        }
        const giaCu = Number(current.gia || 0);
        parts.forEach((p) => {
            const sp = p.suppliers[0] || { nha_cung_cap: "(chưa rõ NCC)", don_gia: 0 };
            const isCurrent = String(p.part_id) === current.partId;
            const item = el("button", "list-group-item list-group-item-action d-flex justify-content-between align-items-center gap-3 small");
            item.type = "button";
            item.disabled = isCurrent;

            const left = el("div");
            left.appendChild(el("div", "fw-semibold", (p.ma_linh_kien || "(không mã)") + (isCurrent ? "  (đang dùng)" : "")));
            left.appendChild(el("div", "text-muted", p.ten_linh_kien + " · " + (p.hang || "—") + " · " + sp.nha_cung_cap));

            const right = el("div", "text-end text-nowrap");
            right.appendChild(el("div", "fw-bold", fmt(sp.don_gia) + "đ"));
            const diff = Number(sp.don_gia || 0) - giaCu;
            if (!isCurrent && diff !== 0) {
                right.appendChild(el("div", diff > 0 ? "text-danger" : "text-success", (diff > 0 ? "+" : "−") + fmt(Math.abs(diff)) + "đ"));
            }
            item.append(left, right);
            item.addEventListener("click", () => {
                form.action = current.action;
                form.elements.part_id.value = p.part_id;
                form.elements.ca_bao_gia.value = allBox.checked ? "1" : "";
                form.submit();
            });
            resultsBox.appendChild(item);
        });
    }
}
