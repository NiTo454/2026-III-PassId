(() => {
    document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
        const inputId = toggle.getAttribute("aria-controls");
        const password = inputId ? document.getElementById(inputId) : null;
        if (!(password instanceof HTMLInputElement)) return;

        const icon = toggle.querySelector("i");
        toggle.addEventListener("click", () => {
            const showPassword = password.type === "password";
            password.type = showPassword ? "text" : "password";
            toggle.setAttribute("aria-pressed", String(showPassword));
            toggle.setAttribute(
                "aria-label",
                showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
            );
            if (icon) {
                icon.classList.toggle("fa-eye", !showPassword);
                icon.classList.toggle("fa-eye-slash", showPassword);
            }
        });
    });

    const portal = document.querySelector("[data-auth-mode]");
    if (!portal) return;

    const links = Array.from(document.querySelectorAll(".auth-mode-tabs [data-auth-link]"));
    const resetLink = document.querySelector("[data-auth-reset-link]");
    const modeTitles = {
        login: "Iniciar sesión | PassID",
        register: "Crear cuenta | PassID",
        reset: "Recuperar contraseña | PassID",
    };

    const activateMode = (mode, direction) => {
        if (!Object.hasOwn(modeTitles, mode)) return;

        portal.dataset.authMode = mode;
        portal.dataset.authDirection = direction;
        document.title = modeTitles[mode];

        portal.querySelectorAll("[data-auth-view]").forEach((view) => {
            view.hidden = view.dataset.authView !== mode;
        });
        portal.querySelectorAll("[data-auth-welcome]").forEach((welcome) => {
            welcome.hidden = welcome.dataset.authWelcome !== mode;
        });
        const activeTab = mode === "reset" ? "login" : mode;
        links.forEach((link) => {
            if (link.dataset.authLink === activeTab) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        });
    };

    const modeFromPath = (pathname) => {
        const allLinks = resetLink ? [...links, resetLink] : links;
        const activeLink = allLinks.find((link) => {
            const linkPath = new URL(link.href, window.location.href).pathname;
            return linkPath === pathname;
        });
        return activeLink
            ? activeLink.dataset.authLink || "reset"
            : null;
    };

    links.forEach((link) => {
        link.addEventListener("click", (event) => {
            if (
                event.defaultPrevented ||
                event.button !== 0 ||
                event.metaKey ||
                event.ctrlKey ||
                event.shiftKey ||
                event.altKey
            ) {
                return;
            }

            const mode = link.dataset.authLink;
            if (portal.dataset.authMode === mode) {
                event.preventDefault();
                return;
            }

            event.preventDefault();
            const direction = mode === "register" ? "left" : "right";
            window.history.pushState({ mode }, "", link.href);
            activateMode(mode, direction);
        });
    });

    window.addEventListener("popstate", () => {
        const mode = modeFromPath(window.location.pathname);
        if (mode) {
            activateMode(mode, mode === "register" ? "left" : "right");
        }
    });
})();
