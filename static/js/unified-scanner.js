(() => {
    const root = document.getElementById("unified-scanner");
    if (!root) return;

    const classSelect = document.getElementById("scanner-class-select");
    const eventSelect = document.getElementById("id_evento");
    const modeButtons = [...root.querySelectorAll("[data-mode-button]")];
    const classContext = root.querySelector('[data-context="clase"]');
    const eventContext = root.querySelector('[data-context="evento"]');
    const startButton = document.getElementById("scanner-start");
    const stopButton = document.getElementById("scanner-stop");
    const manualInput = document.getElementById("scanner-manual-input");
    const manualButton = document.getElementById("scanner-manual-submit");
    const cameraPlaceholder = document.getElementById("scanner-camera-placeholder");
    const statusBox = document.getElementById("scanner-status");
    const historyList = document.getElementById("scanner-history");
    const historyEmpty = document.getElementById("scanner-history-empty");
    const counter = document.getElementById("scanner-counter");
    const activityContext = document.getElementById("scanner-activity-context");
    const enrollAction = document.getElementById("scanner-enrollment-action");
    const enrollMessage = document.getElementById("scanner-enrollment-message");
    const enrollButton = document.getElementById("scanner-enroll-confirm");
    const registerAtDoor = document.getElementById("scanner-register-at-door");
    const eventInfoButton = document.getElementById("scanner-event-info");
    const eventQrLink = document.getElementById("scanner-event-qr-link");
    const csrfToken = root.querySelector("[name=csrfmiddlewaretoken]").value;

    let mode = root.dataset.initialMode;
    let reader = null;
    let cameraActive = false;
    let requestPending = false;
    let successfulCount = 0;
    let queuedAction = null;
    let lastDecodedValue = "";
    let lastDecodedAt = 0;

    const isAvailable = (select) => Boolean(select && select.value);

    const selectedContextName = () => {
        if (mode === "clase") {
            return classSelect?.selectedOptions[0]?.textContent.trim() || "Clase";
        }
        return eventSelect?.selectedOptions[0]?.textContent.trim() || "Evento";
    };

    const updateStatus = (message, type = "idle") => {
        const icons = {
            idle: "fa-circle-info",
            success: "fa-circle-check",
            warning: "fa-triangle-exclamation",
            error: "fa-circle-xmark",
        };
        statusBox.className = `scanner-status scanner-status-${type}`;
        statusBox.replaceChildren();
        const icon = document.createElement("i");
        icon.className = `fa-solid ${icons[type] || icons.idle}`;
        icon.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.textContent = message;
        statusBox.append(icon, text);
    };

    const addHistoryEntry = (message, type) => {
        historyEmpty.hidden = true;
        const item = document.createElement("li");
        item.className = `scanner-history-item scanner-history-${type}`;
        const icon = document.createElement("i");
        icon.className = `fa-solid ${
            type === "success" ? "fa-circle-check" :
                type === "warning" ? "fa-triangle-exclamation" :
                    "fa-circle-xmark"
        }`;
        icon.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.textContent = message;
        item.append(icon, text);
        historyList.prepend(item);
        while (historyList.children.length > 7) {
            historyList.lastElementChild.remove();
        }
    };

    const clearQueuedAction = () => {
        queuedAction = null;
        enrollAction.hidden = true;
        enrollMessage.textContent = "";
    };

    const updateControls = () => {
        const hasContext = mode === "clase" ? isAvailable(classSelect) : isAvailable(eventSelect);
        startButton.disabled = cameraActive || !hasContext;
        manualButton.disabled = requestPending || !hasContext;
        if (classContext) classContext.hidden = mode !== "clase";
        if (eventContext) eventContext.hidden = mode !== "evento";
        modeButtons.forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.modeButton === mode));
        });
        [classSelect, eventSelect].filter(Boolean).forEach((select) => {
            select.disabled = cameraActive || requestPending;
        });
        modeButtons.forEach((button) => {
            button.disabled = cameraActive || requestPending;
        });
        activityContext.textContent = hasContext
            ? `Registrando: ${selectedContextName()}`
            : "Elige un contexto para ver su actividad.";
        if (mode === "evento") updateEventTools();
    };

    const eventUrlFor = (template, eventId) => {
        const url = new URL(template, window.location.origin);
        url.pathname = url.pathname.replace(/\/0\/?$/, `/${encodeURIComponent(eventId)}/`);
        return url.toString();
    };

    const updateEventTools = () => {
        const eventId = eventSelect?.value;
        const tools = document.getElementById("scanner-event-tools");
        if (!eventId || !tools) {
            tools.hidden = true;
            return;
        }
        tools.hidden = false;
        eventQrLink.href = eventUrlFor(root.dataset.eventQrTemplate, eventId);
        eventQrLink.hidden = true;
    };

    const sendScan = async (value, isQr, action = null) => {
        if (requestPending || !isAvailable(mode === "clase" ? classSelect : eventSelect)) return;
        requestPending = true;
        clearQueuedAction();
        updateControls();
        updateStatus("Validando asistencia…", "idle");

        const payload = new URLSearchParams({
            csrfmiddlewaretoken: csrfToken,
            token: isQr ? value : "",
            matricula: isQr ? "" : value.trim(),
        });
        if (mode === "clase") {
            payload.set("horario", classSelect.value);
            if (action === "enroll") payload.set("inscribir", "on");
        } else {
            payload.set("evento", eventSelect.value);
            if (action === "register-event" || registerAtDoor.checked) {
                payload.set("registrar_si_no_existe", "on");
            }
        }

        try {
            const response = await fetch(
                mode === "clase" ? root.dataset.classSubmitUrl : root.dataset.eventSubmitUrl,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "X-CSRFToken": csrfToken,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    credentials: "same-origin",
                    body: payload,
                },
            );
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error("El servidor devolvió una respuesta que no se pudo leer.");
            }
            if (!response.ok || !result.ok) {
                const message = result.message || result.error || "No se pudo registrar la asistencia.";
                addHistoryEntry(message, result.duplicate ? "warning" : "error");
                updateStatus(message, result.duplicate ? "warning" : "error");
                if (mode === "clase" && result.enrollment_required && result.can_enroll) {
                    queuedAction = { value, isQr, action: "enroll" };
                    enrollMessage.textContent = `${message} Confirma antes de crear o reactivar la inscripción.`;
                    enrollButton.textContent = "Confirmar inscripción y registrar asistencia";
                    enrollAction.hidden = false;
                } else if (mode === "evento" && result.can_register) {
                    queuedAction = { value, isQr, action: "register-event" };
                    enrollMessage.textContent = `${message} Confirma para registrar a esta persona en puerta y darle acceso.`;
                    enrollButton.textContent = "Confirmar registro en puerta y acceso";
                    enrollAction.hidden = false;
                }
                return;
            }

            successfulCount += 1;
            counter.textContent = String(successfulCount);
            addHistoryEntry(result.message || "Asistencia registrada.", "success");
            updateStatus(result.message || "Asistencia registrada.", "success");
            if (navigator.vibrate) navigator.vibrate(50);
            manualInput.value = "";
        } catch (error) {
            addHistoryEntry(error.message, "error");
            updateStatus(error.message, "error");
        } finally {
            requestPending = false;
            updateControls();
        }
    };

    const onDecoded = (decodedText) => {
        const now = Date.now();
        if (requestPending || (decodedText === lastDecodedValue && now - lastDecodedAt < 1800)) return;
        lastDecodedValue = decodedText;
        lastDecodedAt = now;
        sendScan(decodedText, true);
    };

    const startCamera = async () => {
        if (!window.Html5Qrcode || !isAvailable(mode === "clase" ? classSelect : eventSelect)) {
            updateStatus("No fue posible iniciar el lector. Verifica la conexión local y el contexto seleccionado.", "error");
            return;
        }
        startButton.disabled = true;
        updateStatus("Solicitando acceso a la cámara…", "idle");
        try {
            reader = new Html5Qrcode("qr-reader");
            await reader.start(
                { facingMode: "environment" },
                { fps: 12, qrbox: { width: 240, height: 240 }, aspectRatio: 1.15 },
                onDecoded,
                () => {},
            );
            cameraActive = true;
            cameraPlaceholder.hidden = true;
            stopButton.hidden = false;
            startButton.querySelector("span").textContent = "Cámara activa";
            updateStatus(`Cámara lista. Escaneando para ${selectedContextName()}.`, "success");
            updateControls();
        } catch (error) {
            reader = null;
            cameraActive = false;
            startButton.querySelector("span").textContent = "Iniciar cámara";
            cameraPlaceholder.hidden = false;
            updateStatus(`No se pudo iniciar la cámara: ${error.message || "revisa el permiso del navegador y la conexión segura del sitio."}`, "error");
            updateControls();
        }
    };

    const stopCamera = async () => {
        if (reader && cameraActive) {
            try {
                await reader.stop();
                await reader.clear();
            } catch (error) {
                updateStatus(`No se pudo detener correctamente la cámara: ${error.message}`, "error");
            }
        }
        reader = null;
        cameraActive = false;
        cameraPlaceholder.hidden = false;
        stopButton.hidden = true;
        startButton.querySelector("span").textContent = "Iniciar cámara";
        updateControls();
    };

    modeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            if (cameraActive || requestPending) return;
            mode = button.dataset.modeButton;
            clearQueuedAction();
            manualInput.value = "";
            updateControls();
            updateStatus(`Modo ${mode === "clase" ? "clase" : "evento"} seleccionado.`, "idle");
        });
    });

    classSelect?.addEventListener("change", () => {
        clearQueuedAction();
        updateControls();
    });
    eventSelect?.addEventListener("change", () => {
        clearQueuedAction();
        updateControls();
    });
    startButton.addEventListener("click", startCamera);
    stopButton.addEventListener("click", stopCamera);
    manualButton.addEventListener("click", () => {
        if (manualInput.value.trim()) sendScan(manualInput.value, false);
        else manualInput.focus();
    });
    manualInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            manualButton.click();
        }
    });
    enrollButton.addEventListener("click", () => {
        if (!queuedAction) return;
        const action = queuedAction;
        sendScan(action.value, action.isQr, action.action);
    });
    eventInfoButton?.addEventListener("click", async () => {
        if (!eventSelect?.value) return;
        eventInfoButton.disabled = true;
        try {
            const response = await fetch(eventUrlFor(root.dataset.eventInfoTemplate, eventSelect.value), {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.message || "No se pudo cargar el evento.");
            updateStatus(
                `${result.nombre} · ${result.fecha_hora} · ${result.lugar} · ${result.total_asistencias} asistencias de ${result.total_registrados} registros.`,
                "idle",
            );
            eventQrLink.hidden = !result.permitir_autorregistro;
        } catch (error) {
            updateStatus(error.message, "error");
        } finally {
            eventInfoButton.disabled = false;
        }
    });
    window.addEventListener("pagehide", () => {
        if (reader && cameraActive) reader.stop().catch(() => {});
    });

    updateControls();
    if (!isAvailable(mode === "clase" ? classSelect : eventSelect)) {
        updateStatus(
            mode === "clase"
                ? "No hay horarios disponibles para escanear."
                : "Selecciona un evento para comenzar.",
            "warning",
        );
    } else {
        updateStatus(`Listo para registrar en ${selectedContextName()}.`, "idle");
    }
})();
