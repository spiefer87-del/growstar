(() => {
    "use strict";

    const drawer = document.querySelector("[data-growstar-menu]");
    const overlay = document.querySelector("[data-growstar-menu-overlay]");
    const openButton = document.querySelector("[data-growstar-menu-open]");
    const closeButton = document.querySelector("[data-growstar-menu-close]");

    if (!drawer || !overlay || !openButton || !closeButton) return;

    let previouslyFocused = null;
    let touchStartX = null;
    let touchStartY = null;

    const focusableSelector = [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        '[tabindex]:not([tabindex="-1"])'
    ].join(",");

    function isOpen() {
        return drawer.classList.contains("is-open");
    }

    function setOpen(nextOpen, { restoreFocus = true } = {}) {
        if (nextOpen === isOpen()) return;

        if (nextOpen) {
            previouslyFocused = document.activeElement;
            drawer.classList.add("is-open");
            overlay.hidden = false;
            requestAnimationFrame(() => overlay.classList.add("is-open"));
            drawer.setAttribute("aria-hidden", "false");
            openButton.setAttribute("aria-expanded", "true");
            document.body.classList.add("growstar-menu-open");

            const firstFocusable = drawer.querySelector(focusableSelector);
            firstFocusable?.focus({ preventScroll: true });
            return;
        }

        drawer.classList.remove("is-open");
        overlay.classList.remove("is-open");
        drawer.setAttribute("aria-hidden", "true");
        openButton.setAttribute("aria-expanded", "false");
        document.body.classList.remove("growstar-menu-open");

        window.setTimeout(() => {
            if (!isOpen()) overlay.hidden = true;
        }, 220);

        if (restoreFocus && previouslyFocused instanceof HTMLElement) {
            previouslyFocused.focus({ preventScroll: true });
        }
        previouslyFocused = null;
    }

    function setGroupExpanded(group, expanded) {
        const toggle = group.querySelector("[data-growstar-nav-group-toggle]");
        const submenu = group.querySelector("[data-growstar-nav-submenu]");
        if (!toggle || !submenu) return;

        group.classList.toggle("is-expanded", expanded);
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
        submenu.hidden = !expanded;
    }

    function trapFocus(event) {
        if (!isOpen() || event.key !== "Tab") return;

        const focusable = Array.from(drawer.querySelectorAll(focusableSelector))
            .filter(element => !element.hasAttribute("disabled"));

        if (!focusable.length) {
            event.preventDefault();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    openButton.addEventListener("click", () => setOpen(true));
    closeButton.addEventListener("click", () => setOpen(false));
    overlay.addEventListener("click", () => setOpen(false));

    drawer.addEventListener("click", event => {
        const toggle = event.target.closest("[data-growstar-nav-group-toggle]");
        if (toggle) {
            event.preventDefault();
            event.stopPropagation();
            const group = toggle.closest("[data-growstar-nav-group]");
            if (group) setGroupExpanded(group, !group.classList.contains("is-expanded"));
            return;
        }

        const link = event.target.closest("a[href]");
        if (link) setOpen(false, { restoreFocus: false });
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && isOpen()) {
            event.preventDefault();
            setOpen(false);
            return;
        }
        trapFocus(event);
    });

    // A deliberate left swipe closes the drawer on touch devices.
    // Opening remains hamburger-only so controller sliders cannot trigger it.
    drawer.addEventListener("touchstart", event => {
        const touch = event.touches?.[0];
        if (!touch) return;
        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
    }, { passive: true });

    drawer.addEventListener("touchend", event => {
        const touch = event.changedTouches?.[0];
        if (!touch || touchStartX === null || touchStartY === null) return;

        const deltaX = touch.clientX - touchStartX;
        const deltaY = touch.clientY - touchStartY;

        touchStartX = null;
        touchStartY = null;

        if (deltaX < -70 && Math.abs(deltaX) > Math.abs(deltaY) * 1.35) {
            setOpen(false);
        }
    }, { passive: true });

    drawer.querySelectorAll("[data-growstar-nav-group]").forEach(group => {
        setGroupExpanded(group, group.classList.contains("is-expanded"));
    });

    window.addEventListener("pageshow", () => {
        if (isOpen()) setOpen(false, { restoreFocus: false });
    });
})();
