(() => {
    const page = document.getElementById("attendance-page");
    const modal = document.getElementById("location-modal");
    if (!page || !modal) return;

    const message = document.getElementById("location-modal-message");
    const attemptsLabel = document.getElementById("location-attempts");
    const retryButton = document.getElementById("location-retry");
    const csrfToken = document.querySelector("#csrf-form [name=csrfmiddlewaretoken]").value;
    let activeButton = null;
    let failedAttempts = 0;

    const showModal = (reason) => {
        message.textContent = reason;
        attemptsLabel.textContent = failedAttempts
            ? `Fallos reportados: ${failedAttempts} de 3.`
            : "";
        retryButton.hidden = failedAttempts >= 3;
        modal.hidden = false;
        retryButton.focus();
    };

    const closeModal = () => {
        modal.hidden = true;
        activeButton = null;
    };

    const post = async (url, values) => {
        const body = new URLSearchParams({ ...values, csrfmiddlewaretoken: csrfToken });
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-CSRFToken": csrfToken,
                "X-Requested-With": "XMLHttpRequest",
            },
            credentials: "same-origin",
            body,
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "No se pudo completar la solicitud.");
        return result;
    };

    const reportFailure = async (reason) => {
        try {
            const result = await post(page.dataset.failureUrl, {
                horario_id: activeButton.dataset.horarioId,
                motivo: reason,
            });
            failedAttempts = result.intentos;
            showModal(reason);
            attemptsLabel.textContent = result.mensaje;
            if (result.visible_administrador) {
                retryButton.hidden = true;
            }
        } catch (error) {
            showModal(`${reason} Además, no se pudo enviar el reporte al servidor: ${error.message}`);
        }
    };

    const locationError = (error) => {
        if (error.code === 1) return "El permiso de ubicación está denegado. Actívalo para este sitio en los ajustes del navegador.";
        if (error.code === 2) return "El dispositivo no pudo determinar la ubicación. Revisa los servicios de ubicación y la conexión.";
        if (error.code === 3) return "La solicitud de ubicación tardó demasiado. Inténtalo otra vez.";
        return "Este navegador no pudo obtener la ubicación del dispositivo.";
    };

    const requestAttendance = () => {
        if (!activeButton) return;
        if (!window.isSecureContext) {
            reportFailure("El sitio no se está ejecutando en un contexto HTTPS seguro.");
            return;
        }
        if (!navigator.geolocation) {
            reportFailure("El navegador no ofrece el servicio de geolocalización.");
            return;
        }

        activeButton.disabled = true;
        activeButton.textContent = "Obteniendo ubicación…";
        navigator.geolocation.getCurrentPosition(async (position) => {
            try {
                await post(page.dataset.submitUrl, {
                    horario_id: activeButton.dataset.horarioId,
                    latitud: position.coords.latitude,
                    longitud: position.coords.longitude,
                });
                window.location.reload();
            } catch (error) {
                activeButton.disabled = false;
                activeButton.textContent = "Marcar asistencia con ubicación";
                showModal(error.message);
            }
        }, async (error) => {
            const reason = locationError(error);
            activeButton.disabled = false;
            activeButton.textContent = "Marcar asistencia con ubicación";
            showModal(reason);
            await reportFailure(reason);
        }, {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0,
        });
    };

    page.querySelectorAll(".attendance-submit").forEach((button) => {
        button.addEventListener("click", () => {
            activeButton = button;
            failedAttempts = 0;
            requestAttendance();
        });
    });

    retryButton.addEventListener("click", requestAttendance);
    document.getElementById("location-dismiss").addEventListener("click", closeModal);
    modal.querySelector(".location-modal-close").addEventListener("click", closeModal);

})();
