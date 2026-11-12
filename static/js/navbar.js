(function () {
    const toggle = document.getElementById('navToggle');
    const links  = document.getElementById('navLinks');

    const closeDropdowns = () => {
        document.querySelectorAll('.nav-dropdown.is-open').forEach(dropdown => {
            dropdown.classList.remove('is-open');
            dropdown.querySelector('.nav-trigger')?.setAttribute('aria-expanded', 'false');
        });
    };

    const setMenuOpen = open => {
        if (!toggle || !links) return;
        links.classList.toggle('is-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
        const icon = toggle.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-bars', !open);
            icon.classList.toggle('fa-xmark', open);
        }
        if (!open) closeDropdowns();
    };

    if (toggle && links) {
        toggle.addEventListener('click', () => {
            setMenuOpen(!links.classList.contains('is-open'));
        });
    }

    document.querySelectorAll('.nav-trigger').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            const parent = btn.closest('.nav-dropdown');
            const isOpen = parent.classList.contains('is-open');
            closeDropdowns();
            if (!isOpen) {
                parent.classList.add('is-open');
                btn.setAttribute('aria-expanded', 'true');
            }
        });
    });

    document.addEventListener('click', () => {
        closeDropdowns();
    });

    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;

        const openDropdownTrigger = document.querySelector('.nav-dropdown.is-open > .nav-trigger');
        if (openDropdownTrigger) {
            closeDropdowns();
            openDropdownTrigger.focus();
        } else if (links?.classList.contains('is-open')) {
            setMenuOpen(false);
            toggle?.focus();
        }
    });
})();
