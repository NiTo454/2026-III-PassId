document.addEventListener("DOMContentLoaded", () => {
    const selectAll = document.getElementById("select-all-attendees");
    const filterForm = document.querySelector(".event-registration-filters");
    const attendeeForm = document.querySelector(".event-registration-form");
    const count = document.getElementById("selected-attendees-count");
    const selectedCheckboxes = attendeeForm
        ? Array.from(attendeeForm.querySelectorAll('input[name="usuarios"]'))
        : [];
    const candidateCheckboxes = selectedCheckboxes.filter(
        (checkbox) => checkbox.classList.contains("event-registration-candidate")
    );

    const updateCount = () => {
        const totalSelected = selectedCheckboxes.filter(
            (checkbox) => checkbox.checked
        ).length;
        if (count) {
            count.textContent = String(totalSelected);
        }

        if (selectAll) {
            const visibleSelected = candidateCheckboxes.filter(
                (checkbox) => checkbox.checked
            ).length;
            selectAll.checked =
                candidateCheckboxes.length > 0 &&
                visibleSelected === candidateCheckboxes.length;
            selectAll.indeterminate =
                visibleSelected > 0 &&
                visibleSelected < candidateCheckboxes.length;
        }
    };

    if (selectAll) {
        selectAll.addEventListener("change", () => {
            candidateCheckboxes.forEach((checkbox) => {
                checkbox.checked = selectAll.checked;
            });
            updateCount();
        });
    }

    selectedCheckboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", updateCount);
    });

    if (filterForm) {
        filterForm.addEventListener("submit", () => {
            const currentEvent = filterForm.dataset.currentEvent;
            const selectedEvent = document.getElementById("filter-evento").value;
            if (!attendeeForm || currentEvent !== selectedEvent) {
                return;
            }

            selectedCheckboxes.forEach((checkbox) => {
                if (!checkbox.checked) {
                    return;
                }
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "seleccionados";
                input.value = checkbox.value;
                filterForm.append(input);
            });
        });

        document
            .getElementById("clear-registration-filters")
            ?.addEventListener("click", () => {
                document.getElementById("filter-grupo").value = "";
                document.getElementById("filter-categoria").value = "";
                document.getElementById("filter-query").value = "";
                filterForm.requestSubmit();
            });
    }

    updateCount();
});
