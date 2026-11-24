(() => {
    const normalize = (value) => value
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase()
        .trim();

    const initializeOptionSearch = (scope) => {
        scope.querySelectorAll('select[data-search-options="true"]').forEach((select) => {
            if (select.dataset.searchInitialized || select.options.length < 12) return;
            select.dataset.searchInitialized = "true";

            const wrapper = document.createElement("div");
            wrapper.className = "academic-option-search";

            const input = document.createElement("input");
            input.type = "search";
            input.className = "form-control academic-option-search-input";
            input.placeholder = "Escribe para filtrar opciones";
            input.autocomplete = "off";
            const label = document.querySelector(`label[for="${select.id}"]`);
            input.setAttribute(
                "aria-label",
                `Buscar ${label ? label.textContent.trim().toLocaleLowerCase() : "opciones"}`
            );

            const status = document.createElement("span");
            status.className = "academic-option-search-status";
            status.setAttribute("aria-live", "polite");
            status.hidden = true;

            select.parentNode.insertBefore(wrapper, select);
            wrapper.append(input, select, status);

            const reset = () => {
                Array.from(select.options).forEach((option) => {
                    option.hidden = false;
                });
                status.hidden = true;
                status.textContent = "";
            };

            input.addEventListener("input", () => {
                const query = normalize(input.value);
                let visibleCount = 0;
                Array.from(select.options).forEach((option) => {
                    const matches = !query || normalize(option.textContent).includes(query);
                    option.hidden = !matches && option !== select.selectedOptions[0];
                    if (matches && option.value) visibleCount += 1;
                });
                status.textContent = query
                    ? `${visibleCount} opción${visibleCount === 1 ? "" : "es"}`
                    : "";
                status.hidden = !query;

                const exactMatch = Array.from(select.options).find(
                    (option) => option.value && normalize(option.textContent) === query
                );
                if (exactMatch) select.value = exactMatch.value;
            });

            select.addEventListener("change", () => {
                input.value = "";
                reset();
            });
        });
    };

    document.addEventListener("DOMContentLoaded", () => {
        const container = document.querySelector("[data-bulk-formset]");
        initializeOptionSearch(document);
        if (!container) return;

        const prefix = container.dataset.prefix;
        const totalForms = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
        const maxForms = document.getElementById(`id_${prefix}-MAX_NUM_FORMS`);
        const rowTemplate = document.getElementById("academic-bulk-empty-row");
        const addButton = document.querySelector("[data-add-row]");
        const visibleCount = document.getElementById("academic-bulk-visible-count");
        if (!totalForms || !rowTemplate || !addButton || !visibleCount) return;

        const rows = () => Array.from(container.querySelectorAll("[data-form-row]"));
        const updateState = () => {
            const visibleRows = rows().filter((row) => !row.hidden);
            visibleRows.forEach((row, index) => {
                const title = row.querySelector("[data-row-title]");
                if (title) title.textContent = `Registro ${index + 1}`;
            });
            visibleCount.textContent = String(visibleRows.length);
            const maximum = maxForms ? Number(maxForms.value) : 100;
            addButton.disabled = Number(totalForms.value) >= maximum;
        };

        container.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-remove-row]");
            if (!removeButton) return;
            const row = removeButton.closest("[data-form-row]");
            const deleteField = row && row.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (!row || !deleteField) return;
            deleteField.checked = true;
            row.hidden = true;
            updateState();
        });

        addButton.addEventListener("click", () => {
            const index = Number(totalForms.value);
            const maximum = maxForms ? Number(maxForms.value) : 100;
            if (index >= maximum) return;

            const html = rowTemplate.innerHTML.replace(/__prefix__/g, String(index));
            const template = document.createElement("template");
            template.innerHTML = html.trim();
            const newRow = template.content.firstElementChild;
            if (!newRow) return;

            const previousRow = rows().filter((row) => !row.hidden).slice(-1)[0];
            const repeatedFields = new Set([
                "activa", "activo", "asistencias", "aula", "carrera",
                "dia_semana", "edificio", "grupo", "horas_semana",
                "materia", "periodo", "profesor", "tipo", "usuario",
            ]);
            if (previousRow) {
                previousRow.querySelectorAll("[name]").forEach((previousField) => {
                    const fieldName = previousField.name.split("-").pop();
                    if (!repeatedFields.has(fieldName)) return;
                    const nextField = newRow.querySelector(`[name$="-${fieldName}"]`);
                    if (!nextField) return;
                    if (previousField.type === "checkbox") {
                        nextField.checked = previousField.checked;
                    } else {
                        nextField.value = previousField.value;
                    }
                });
            }

            container.append(newRow);
            totalForms.value = String(index + 1);
            initializeOptionSearch(newRow);
            updateState();
            const firstField = newRow.querySelector("input:not([type=hidden]), select");
            if (firstField) firstField.focus();
        });

        updateState();
    });
})();
