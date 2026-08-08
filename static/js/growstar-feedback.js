(() => {
    "use strict";

    if (window.__growstarFeedbackInstalled) return;
    window.__growstarFeedbackInstalled = true;

    const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
    const recentMessages = new Map();
    let sessionRedirectScheduled = false;

    function installStyles() {
        if (document.getElementById("growstar-feedback-styles")) return;

        const style = document.createElement("style");
        style.id = "growstar-feedback-styles";
        style.textContent = `
            #growstar-toast-region {
                position: fixed;
                top: 18px;
                right: 18px;
                z-index: 2147483647;
                width: min(390px, calc(100vw - 28px));
                display: grid;
                gap: 10px;
                pointer-events: none;
            }
            .growstar-toast {
                --toast-accent: #38bdf8;
                display: grid;
                grid-template-columns: auto minmax(0,1fr) auto;
                gap: 11px;
                align-items: start;
                padding: 13px 13px 13px 14px;
                border: 1px solid rgba(148,163,184,.22);
                border-left: 4px solid var(--toast-accent);
                border-radius: 13px;
                background: rgba(15,23,42,.97);
                color: #e5e7eb;
                box-shadow: 0 16px 40px rgba(0,0,0,.38);
                backdrop-filter: blur(10px);
                pointer-events: auto;
                opacity: 0;
                transform: translateY(-8px) scale(.985);
                transition: opacity .18s ease, transform .18s ease;
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            .growstar-toast.visible {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
            .growstar-toast.error { --toast-accent: #ef4444; }
            .growstar-toast.warning { --toast-accent: #f59e0b; }
            .growstar-toast.success { --toast-accent: #22c55e; }
            .growstar-toast.info { --toast-accent: #38bdf8; }
            .growstar-toast-icon { font-size: 1.2rem; line-height: 1.25; }
            .growstar-toast-title {
                margin: 0 0 3px;
                font-size: .92rem;
                font-weight: 800;
                line-height: 1.3;
            }
            .growstar-toast-message {
                margin: 0;
                color: #cbd5e1;
                font-size: .83rem;
                line-height: 1.45;
                overflow-wrap: anywhere;
            }
            .growstar-toast-close {
                border: 0;
                background: transparent;
                color: #94a3b8;
                font: inherit;
                font-size: 1rem;
                line-height: 1;
                cursor: pointer;
                padding: 2px 3px;
            }
            .growstar-toast-close:hover { color: #e5e7eb; }
            @media (max-width: 600px) {
                #growstar-toast-region {
                    top: 10px;
                    right: 10px;
                    left: 10px;
                    width: auto;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function getRegion() {
        installStyles();

        let region = document.getElementById("growstar-toast-region");
        if (region) return region;

        region = document.createElement("div");
        region.id = "growstar-toast-region";
        region.setAttribute("role", "region");
        region.setAttribute("aria-label", "Growstar Meldungen");
        region.setAttribute("aria-live", "polite");

        (document.body || document.documentElement).appendChild(region);
        return region;
    }

    function iconFor(type) {
        return {
            error: "⛔",
            warning: "🔒",
            success: "✅",
            info: "ℹ️",
        }[type] || "ℹ️";
    }

    function removeToast(toast) {
        if (!toast || !toast.isConnected) return;
        toast.classList.remove("visible");
        window.setTimeout(() => toast.remove(), 190);
    }

    function showToast(title, message, type = "info", options = {}) {
        const region = getRegion();
        const toast = document.createElement("div");
        const duration = Number(options.duration ?? 5200);

        toast.className = `growstar-toast ${type}`;
        toast.innerHTML = `
            <div class="growstar-toast-icon" aria-hidden="true"></div>
            <div>
                <div class="growstar-toast-title"></div>
                <p class="growstar-toast-message"></p>
            </div>
            <button type="button" class="growstar-toast-close" aria-label="Meldung schließen">×</button>
        `;

        toast.querySelector(".growstar-toast-icon").textContent = iconFor(type);
        toast.querySelector(".growstar-toast-title").textContent = title || "Growstar";
        toast.querySelector(".growstar-toast-message").textContent = message || "";
        toast.querySelector(".growstar-toast-close").addEventListener("click", () => removeToast(toast));

        region.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add("visible"));

        if (duration > 0) {
            window.setTimeout(() => removeToast(toast), duration);
        }

        return toast;
    }

    function shouldShow(key, interval = 6000) {
        const now = Date.now();
        const last = recentMessages.get(key) || 0;
        if (now - last < interval) return false;

        recentMessages.set(key, now);
        return true;
    }

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || "";
    }

    function toUrl(input) {
        try {
            const value = input instanceof Request ? input.url : input;
            return new URL(String(value), window.location.href);
        } catch (_) {
            return null;
        }
    }

    function requestMethod(input, init) {
        return String(
            init?.method ||
            (input instanceof Request ? input.method : "GET")
        ).toUpperCase();
    }

    function withCsrfHeader(input, init) {
        const url = toUrl(input);
        const method = requestMethod(input, init);

        if (!url || url.origin !== window.location.origin || SAFE_METHODS.has(method)) {
            return init;
        }

        const token = csrfToken();
        if (!token) return init;

        const headers = new Headers(
            init?.headers ||
            (input instanceof Request ? input.headers : undefined)
        );

        if (!headers.has("X-CSRF-Token")) {
            headers.set("X-CSRF-Token", token);
        }

        return {
            ...(init || {}),
            headers,
        };
    }

    async function errorPayload(response) {
        try {
            return await response.clone().json();
        } catch (_) {
            return {};
        }
    }

    function scheduleLoginRedirect() {
        if (sessionRedirectScheduled || window.location.pathname === "/login") return;
        sessionRedirectScheduled = true;

        window.setTimeout(() => {
            const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
            window.location.assign(`/login?next=${encodeURIComponent(next)}`);
        }, 1400);
    }

    async function handleResponse(response, input) {
        const url = toUrl(input);
        if (!url || url.origin !== window.location.origin) return;

        if (response.status === 401) {
            const payload = await errorPayload(response);
            const key = `401:${url.pathname}`;

            if (shouldShow(key, 10000)) {
                showToast(
                    "Sitzung abgelaufen",
                    payload.message || "Bitte melde dich erneut an.",
                    "info",
                    { duration: 6500 }
                );
            }

            scheduleLoginRedirect();
            return;
        }

        if (response.status === 403) {
            const payload = await errorPayload(response);
            const labels = Array.isArray(payload.required_labels)
                ? payload.required_labels.filter(Boolean)
                : [];

            let message = payload.message || "Du hast keine Berechtigung für diese Aktion.";

            if (!payload.message && labels.length) {
                message = labels.length === 1
                    ? `Benötigte Berechtigung: ${labels[0]}.`
                    : `Benötigte Berechtigungen: ${labels.join(", ")}.`;
            }

            const key = `403:${url.pathname}:${labels.join("|")}`;
            if (shouldShow(key)) {
                showToast("Keine Berechtigung", message, "warning");
            }
            return;
        }

        if (response.status === 400) {
            const payload = await errorPayload(response);
            if (payload.error !== "invalid_csrf") return;

            const key = `csrf:${url.pathname}`;
            if (shouldShow(key, 8000)) {
                showToast(
                    "Sicherheitsprüfung fehlgeschlagen",
                    payload.message || "Bitte lade die Seite neu und versuche es erneut.",
                    "warning",
                    { duration: 6500 }
                );
            }
        }
    }

    const originalFetch = window.fetch.bind(window);

    window.fetch = async function growstarFetch(input, init) {
        const nextInit = withCsrfHeader(input, init);

        try {
            const response = await originalFetch(input, nextInit);
            await handleResponse(response, input);
            return response;
        } catch (error) {
            const url = toUrl(input);
            if (url && url.origin === window.location.origin) {
                const key = `network:${url.pathname}`;
                if (shouldShow(key, 10000)) {
                    showToast(
                        "Verbindung fehlgeschlagen",
                        "Growstar konnte den Server nicht erreichen.",
                        "error"
                    );
                }
            }
            throw error;
        }
    };

    window.showGrowstarToast = showToast;
    window.GrowstarFeedback = {
        show: showToast,
        csrfToken,
    };
})();
