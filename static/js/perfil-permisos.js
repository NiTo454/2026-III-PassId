(() => {
    const normalize = (value) => value
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase()
        .trim();

    const humanize = (value) => value
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .replace(/[._-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .split(" ")
        .filter(Boolean)
        .map((word) => (
            word.length <= 3
                ? word.toLocaleUpperCase()
                : `${word.charAt(0).toLocaleUpperCase()}${word.slice(1).toLocaleLowerCase()}`
        ))
        .join(" ");

    const cleanDescription = (value) => value
        .replace(/_/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/^./, (letter) => letter.toLocaleUpperCase());

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("[data-permission-chip]").forEach((chip) => {
            const name = chip.dataset.permissionName.trim();
            chip.textContent = name
                ? cleanDescription(name)
                : humanize(chip.dataset.permissionCode);
        });

        const container = document.getElementById("role-permission-groups");
        const tools = document.querySelector("[data-permission-tools]");
        const search = document.getElementById("role-permission-search");
        const moduleFilter = document.getElementById("role-permission-module");
        const selectedOnly = document.getElementById(
            "role-permission-selected-only"
        );
        const selectionCount = document.getElementById(
            "role-permission-selection-count"
        );
        const results = document.getElementById("role-permission-results");
        const emptyState = document.getElementById("role-permission-empty");
        const selectVisibleButton = document.querySelector("[data-select-visible]");
        const clearVisibleButton = document.querySelector("[data-clear-visible]");
        const resetFiltersButton = document.querySelector("[data-reset-filters]");

        if (
            !container ||
            !tools ||
            !search ||
            !moduleFilter ||
            !selectedOnly ||
            !selectionCount ||
            !results ||
            !emptyState ||
            !selectVisibleButton ||
            !clearVisibleButton ||
            !resetFiltersButton
        ) {
            return;
        }

        const options = Array.from(
            container.querySelectorAll("[data-permission-option]")
        );
        const groups = new Map();
        let filtersWereActive = false;
        let savedOpenState = null;

        options.forEach((option) => {
            const label = option.querySelector(".role-permission-label");
            const checkbox = option.querySelector('input[type="checkbox"]');
            if (!label || !checkbox) return;

            const fullLabel = label.textContent.trim();
            const separatorIndex = fullLabel.indexOf(" - ");
            const permissionCode = separatorIndex >= 0
                ? fullLabel.slice(0, separatorIndex).trim()
                : fullLabel;
            const description = separatorIndex >= 0
                ? fullLabel.slice(separatorIndex + 3).trim()
                : "";
            const moduleSeparatorIndex = permissionCode.indexOf(".");
            const moduleKey = moduleSeparatorIndex >= 0
                ? permissionCode.slice(0, moduleSeparatorIndex)
                : "otros";
            const codename = moduleSeparatorIndex >= 0
                ? permissionCode.slice(moduleSeparatorIndex + 1)
                : permissionCode;
            const moduleLabel = humanize(moduleKey);
            const cleanName = description
                ? cleanDescription(description)
                : humanize(codename);

            label.textContent = cleanName;
            option.title = `${moduleLabel} · ${codename}`;
            option.dataset.search =
                `${fullLabel} ${moduleLabel} ${cleanName} ${humanize(codename)}`;
            option.dataset.module = moduleKey;

            let group = groups.get(moduleKey);
            if (!group) {
                const element = document.createElement("details");
                element.className = "role-permission-module";
                element.dataset.module = moduleKey;

                const summary = document.createElement("summary");
                const name = document.createElement("span");
                name.className = "role-permission-module-name";
                name.textContent = moduleLabel;

                const count = document.createElement("span");
                count.className = "role-permission-module-count";

                const items = document.createElement("div");
                items.className = "role-permission-module-items";
                summary.append(name, count);
                element.append(summary, items);
                group = { element, count, items };
                groups.set(moduleKey, group);
                container.append(element);

                const moduleOption = document.createElement("option");
                moduleOption.value = moduleKey;
                moduleOption.textContent = moduleLabel;
                moduleFilter.append(moduleOption);
            }

            group.items.append(option);
        });

        const updateCounts = () => {
            const selectedCount = options.filter((option) =>
                option.querySelector('input[type="checkbox"]').checked
            ).length;
            selectionCount.textContent =
                `${selectedCount} de ${options.length} permisos seleccionados`;

            groups.forEach((group) => {
                const checkboxes = Array.from(
                    group.items.querySelectorAll('input[type="checkbox"]')
                );
                const selected = checkboxes.filter((checkbox) => checkbox.checked).length;
                group.count.textContent =
                    `${selected}/${checkboxes.length} seleccionados`;
            });
        };

        const filterOptions = () => {
            const query = normalize(search.value);
            const selectedModule = moduleFilter.value;
            const filterSelectedOnly = selectedOnly.checked;
            const filtersAreActive = Boolean(
                query || selectedModule || filterSelectedOnly
            );
            let visibleCount = 0;
            let visibleSelectedCount = 0;

            if (filtersAreActive && !filtersWereActive) {
                savedOpenState = new Map(
                    Array.from(groups, ([key, group]) => [key, group.element.open])
                );
            }

            options.forEach((option) => {
                const checkbox = option.querySelector('input[type="checkbox"]');
                const matchesQuery =
                    !query || normalize(option.dataset.search).includes(query);
                const matchesModule =
                    !selectedModule || option.dataset.module === selectedModule;
                const matchesSelection =
                    !filterSelectedOnly || checkbox.checked;
                const matches =
                    matchesQuery && matchesModule && matchesSelection;
                option.hidden = !matches;
                if (matches) {
                    visibleCount += 1;
                    if (checkbox.checked) visibleSelectedCount += 1;
                }
            });

            groups.forEach((group) => {
                const hasVisibleOption = Array.from(
                    group.items.querySelectorAll("[data-permission-option]")
                ).some((option) => !option.hidden);
                group.element.hidden = !hasVisibleOption;
                if (filtersAreActive) {
                    group.element.open = hasVisibleOption;
                }
            });

            if (!filtersAreActive && filtersWereActive) {
                groups.forEach((group, key) => {
                    group.element.open = savedOpenState.get(key) || false;
                });
                savedOpenState = null;
            }

            results.textContent = filterSelectedOnly
                ? `${visibleSelectedCount} ${visibleSelectedCount === 1 ? "permiso seleccionado visible" : "permisos seleccionados visibles"}`
                : `Mostrando ${visibleCount} de ${options.length} permisos`;
            emptyState.hidden = visibleCount > 0;
            selectVisibleButton.disabled =
                visibleCount === 0 || filterSelectedOnly;
            clearVisibleButton.disabled = visibleSelectedCount === 0;
            resetFiltersButton.disabled =
                !query && !selectedModule && !filterSelectedOnly;
            updateCounts();
            filtersWereActive = filtersAreActive;
        };

        search.addEventListener("input", filterOptions);
        moduleFilter.addEventListener("change", filterOptions);
        selectedOnly.addEventListener("change", filterOptions);
        container.addEventListener("change", filterOptions);

        selectVisibleButton.addEventListener("click", () => {
            options.forEach((option) => {
                if (!option.hidden) {
                    option.querySelector('input[type="checkbox"]').checked = true;
                }
            });
            filterOptions();
        });

        clearVisibleButton.addEventListener("click", () => {
            options.forEach((option) => {
                if (!option.hidden) {
                    option.querySelector('input[type="checkbox"]').checked = false;
                }
            });
            filterOptions();
        });

        resetFiltersButton.addEventListener("click", () => {
            search.value = "";
            moduleFilter.value = "";
            selectedOnly.checked = false;
            filterOptions();
        });

        tools.hidden = false;
        filterOptions();
    });
})();
