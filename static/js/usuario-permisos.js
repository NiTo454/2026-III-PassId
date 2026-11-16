document.addEventListener("DOMContentLoaded", () => {
    const table = document.getElementById("direct-permissions-table");
    const moduleFilter = document.getElementById("filter-direct-permission-type");
    const searchInput = document.getElementById("filter-direct-permission-query");
    const applyButton = document.getElementById("apply-direct-permission-filters");
    const clearButton = document.getElementById("clear-direct-permission-filters");
    const selectAll = document.getElementById("select-all-direct-permissions");
    const count = document.getElementById("direct-permission-selection-count");
    const emptyState = document.getElementById("direct-permission-empty");
    const selectedPanel = document.getElementById("selected-direct-permissions-panel");
    const selectedList = document.getElementById("selected-direct-permissions-list");
    const selectedPanelCount = document.getElementById(
        "selected-direct-permissions-count"
    );
    const pagination = document.getElementById("direct-permission-pagination");
    const previousButton = document.getElementById("direct-permission-previous");
    const nextButton = document.getElementById("direct-permission-next");
    const pageInfo = document.getElementById("direct-permission-page-info");

    if (
        !table ||
        !moduleFilter ||
        !searchInput ||
        !applyButton ||
        !selectAll ||
        !count ||
        !emptyState ||
        !selectedPanel ||
        !selectedList ||
        !selectedPanelCount ||
        !pagination ||
        !previousButton ||
        !nextButton ||
        !pageInfo
    ) {
        return;
    }

    const pageSize = 6;
    const rows = Array.from(table.querySelectorAll(".direct-permission-option"));
    const checkboxes = rows.map((row) =>
        row.querySelector(".direct-permission-checkbox")
    );
    let currentPage = 1;
    const normalize = (value) =>
        value
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase()
            .trim();

    const renderSelectedPanel = () => {
        const selectedOutsidePage = rows.filter(
            (row) =>
                row.hidden &&
                row.querySelector(".direct-permission-checkbox").checked
        );
        selectedList.replaceChildren();
        selectedPanel.hidden = selectedOutsidePage.length === 0;
        selectedPanelCount.textContent = String(selectedOutsidePage.length);

        selectedOutsidePage.forEach((row) => {
            const label = document.createElement("label");
            label.className = "selectable-item";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = true;
            checkbox.setAttribute("aria-label", "Quitar permiso seleccionado");
            checkbox.addEventListener("change", () => {
                row.querySelector(".direct-permission-checkbox").checked =
                    checkbox.checked;
                renderPage();
            });

            const details = document.createElement("span");
            details.className = "selectable-item-details";

            const name = document.createElement("strong");
            name.textContent = row.dataset.permissionName;

            const metadata = document.createElement("span");
            metadata.textContent =
                `${row.dataset.permissionModule} · ${row.dataset.permissionCode}`;

            details.append(name, metadata);
            label.append(checkbox, details);
            selectedList.append(label);
        });
    };

    const updateSelection = () => {
        const selectedCount = checkboxes.filter(
            (checkbox) => checkbox.checked
        ).length;
        count.textContent = String(selectedCount);

        const visibleCheckboxes = rows
            .filter((row) => !row.hidden)
            .map((row) => row.querySelector(".direct-permission-checkbox"));
        const visibleSelected = visibleCheckboxes.filter(
            (checkbox) => checkbox.checked
        ).length;
        selectAll.checked =
            visibleCheckboxes.length > 0 &&
            visibleSelected === visibleCheckboxes.length;
        selectAll.indeterminate =
            visibleSelected > 0 && visibleSelected < visibleCheckboxes.length;
    };

    const renderPage = () => {
        const filteredRows = rows.filter(
            (row) => row.dataset.matchesFilters === "true"
        );
        const pageCount = Math.ceil(filteredRows.length / pageSize);
        currentPage = Math.min(currentPage, Math.max(pageCount, 1));
        const firstVisibleIndex = (currentPage - 1) * pageSize;
        const visibleRows = new Set(
            filteredRows.slice(firstVisibleIndex, firstVisibleIndex + pageSize)
        );

        rows.forEach((row) => {
            row.hidden = !visibleRows.has(row);
        });
        emptyState.hidden = filteredRows.length > 0;
        pagination.hidden = pageCount <= 1;
        pageInfo.textContent = pageCount
            ? `Página ${currentPage} de ${pageCount}`
            : "Sin resultados";
        const previousDisabled = currentPage <= 1;
        const nextDisabled = currentPage >= pageCount;
        previousButton.setAttribute("aria-disabled", String(previousDisabled));
        nextButton.setAttribute("aria-disabled", String(nextDisabled));
        previousButton.tabIndex = previousDisabled ? -1 : 0;
        nextButton.tabIndex = nextDisabled ? -1 : 0;
        updateSelection();
        renderSelectedPanel();
    };

    const applyFilters = (resetPage = true) => {
        const selectedModule = moduleFilter.value;
        const query = normalize(searchInput.value);

        rows.forEach((row) => {
            const matchesModule =
                !selectedModule || row.dataset.permissionModule === selectedModule;
            const matchesQuery =
                !query || normalize(row.dataset.permissionSearch).includes(query);
            row.dataset.matchesFilters =
                matchesModule && matchesQuery ? "true" : "false";
        });
        if (resetPage) {
            currentPage = 1;
        }
        renderPage();
    };

    applyButton.addEventListener("click", () => applyFilters());
    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            applyFilters();
        }
    });

    clearButton?.addEventListener("click", () => {
        moduleFilter.value = "";
        searchInput.value = "";
        applyFilters();
    });

    selectAll.addEventListener("change", () => {
        rows.forEach((row) => {
            if (!row.hidden) {
                row.querySelector(".direct-permission-checkbox").checked =
                    selectAll.checked;
            }
        });
        renderPage();
    });

    previousButton.addEventListener("click", (event) => {
        event.preventDefault();
        if (previousButton.getAttribute("aria-disabled") !== "true") {
            currentPage -= 1;
            renderPage();
        }
    });

    nextButton.addEventListener("click", (event) => {
        event.preventDefault();
        if (nextButton.getAttribute("aria-disabled") !== "true") {
            currentPage += 1;
            renderPage();
        }
    });

    checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", renderPage);
    });

    applyFilters();
});
