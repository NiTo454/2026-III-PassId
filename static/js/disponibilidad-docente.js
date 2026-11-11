document.addEventListener("DOMContentLoaded", () => {
    const periodSelect = document.getElementById("id_periodo_filtro");
    const newPeriodDetails = document.getElementById("availability-new-period");
    const newPeriodInput = document.getElementById("id_nuevo_periodo");

    if (!periodSelect || !newPeriodDetails || !newPeriodInput) {
        return;
    }

    periodSelect.addEventListener("change", () => {
        newPeriodDetails.open = periodSelect.value === "__nuevo__";
        if (newPeriodDetails.open) {
            newPeriodInput.focus();
        }
    });
});
