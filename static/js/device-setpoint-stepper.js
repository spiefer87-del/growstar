(() => {
    "use strict";

    const STYLE_ID = "growstar-setpoint-stepper-style";
    const ROW_SELECTOR = ".setpoint-row";
    const NUMBER_SELECTOR = ".js-state-number, .js-controller-number";
    const RANGE_SELECTOR = ".js-state-range, .js-controller-range";

    function installStyle() {
        if (document.getElementById(STYLE_ID)) return;

        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            .setpoint-row.growstar-stepper-row {
                grid-template-columns: 42px minmax(0, 1fr) 42px 92px;
                gap: 9px;
                align-items: center;
            }

            .growstar-stepper-button {
                width: 42px !important;
                min-width: 42px;
                height: 42px;
                padding: 0 !important;
                border: 1px solid rgba(56, 189, 248, .28) !important;
                border-radius: 11px !important;
                background: rgba(15, 23, 42, .92) !important;
                color: #bae6fd !important;
                font: 800 1.35rem/1 system-ui, -apple-system, BlinkMacSystemFont, sans-serif !important;
                box-shadow: inset 0 1px 0 rgba(255, 255, 255, .035);
                cursor: pointer;
                touch-action: manipulation;
                -webkit-tap-highlight-color: transparent;
                transition:
                    border-color .14s ease,
                    background .14s ease,
                    transform .08s ease;
            }

            .growstar-stepper-button:hover {
                border-color: rgba(56, 189, 248, .52) !important;
                background: rgba(30, 41, 59, .98) !important;
            }

            .growstar-stepper-button:active {
                transform: scale(.94);
                background: rgba(14, 116, 144, .24) !important;
            }

            .growstar-stepper-button:focus-visible {
                outline: 2px solid #38bdf8;
                outline-offset: 2px;
            }

            .growstar-stepper-button:disabled {
                opacity: .38;
                cursor: not-allowed;
            }

            .setpoint-row.growstar-stepper-row input[type="range"] {
                min-width: 0;
            }

            @media (max-width: 600px) {
                .setpoint-row.growstar-stepper-row {
                    grid-template-columns: 40px minmax(0, 1fr) 40px 70px;
                    gap: 7px;
                }

                .growstar-stepper-button {
                    width: 40px !important;
                    min-width: 40px;
                    height: 40px;
                    border-radius: 10px !important;
                }

                .setpoint-row.growstar-stepper-row input[type="number"] {
                    padding-left: 7px;
                    padding-right: 7px;
                    text-align: center;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function finiteAttribute(input, name, fallback) {
        const value = Number(input.getAttribute(name));
        return Number.isFinite(value) ? value : fallback;
    }

    function decimalPlaces(value) {
        const text = String(value);
        if (text.includes("e-")) {
            const power = Number(text.split("e-")[1]);
            return Number.isFinite(power) ? power : 0;
        }
        const dot = text.indexOf(".");
        return dot === -1 ? 0 : text.length - dot - 1;
    }

    function normalizedValue(input, direction) {
        const minimum = finiteAttribute(input, "min", -Infinity);
        const maximum = finiteAttribute(input, "max", Infinity);
        const stepAttr = input.getAttribute("step");
        const parsedStep = Number(stepAttr);
        const step = Number.isFinite(parsedStep) && parsedStep > 0 ? parsedStep : 1;

        let current = Number(input.value);
        if (!Number.isFinite(current)) {
            current = Number.isFinite(minimum) ? minimum : 0;
        }

        let next = current + direction * step;
        next = Math.max(minimum, Math.min(maximum, next));

        const precision = Math.max(
            decimalPlaces(step),
            Number.isFinite(minimum) ? decimalPlaces(minimum) : 0
        );

        if (precision > 0) {
            next = Number(next.toFixed(precision));
        }

        return next;
    }

    function updateButtonState(row) {
        const number = row.querySelector(NUMBER_SELECTOR);
        if (!number) return;

        const minus = row.querySelector('[data-step-direction="-1"]');
        const plus = row.querySelector('[data-step-direction="1"]');
        const current = Number(number.value);
        const minimum = finiteAttribute(number, "min", -Infinity);
        const maximum = finiteAttribute(number, "max", Infinity);
        const locked = number.disabled;

        if (minus) {
            minus.disabled = locked || (Number.isFinite(current) && current <= minimum);
        }
        if (plus) {
            plus.disabled = locked || (Number.isFinite(current) && current >= maximum);
        }
    }

    function stepRow(row, direction) {
        const number = row.querySelector(NUMBER_SELECTOR);
        const range = row.querySelector(RANGE_SELECTOR);
        if (!number || number.disabled) return;

        const next = normalizedValue(number, direction);

        number.value = String(next);
        if (range) range.value = String(next);

        // Existing Growstar handlers remain the single source for display sync,
        // dirty state and later saving. The stepper only behaves like manual input.
        number.dispatchEvent(new Event("input", { bubbles: true }));
        updateButtonState(row);
    }

    function makeButton(direction) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "growstar-stepper-button";
        button.dataset.stepDirection = String(direction);
        button.textContent = direction < 0 ? "−" : "+";
        button.setAttribute(
            "aria-label",
            direction < 0 ? "Eine Stufe verringern" : "Eine Stufe erhöhen"
        );
        return button;
    }

    function enhanceRow(row) {
        if (!(row instanceof HTMLElement)) return;
        if (row.dataset.growstarStepper === "1") {
            updateButtonState(row);
            return;
        }

        const number = row.querySelector(NUMBER_SELECTOR);
        const range = row.querySelector(RANGE_SELECTOR);
        if (!number || !range) return;

        const minus = makeButton(-1);
        const plus = makeButton(1);

        row.classList.add("growstar-stepper-row");
        row.insertBefore(minus, range);
        row.insertBefore(plus, number);
        row.dataset.growstarStepper = "1";

        minus.addEventListener("click", () => stepRow(row, -1));
        plus.addEventListener("click", () => stepRow(row, 1));

        row.addEventListener("input", () => updateButtonState(row));
        row.addEventListener("change", () => updateButtonState(row));

        updateButtonState(row);
    }

    function enhanceAll(root = document) {
        if (root instanceof Element && root.matches(ROW_SELECTOR)) {
            enhanceRow(root);
        }

        root.querySelectorAll?.(ROW_SELECTOR).forEach(enhanceRow);
    }

    function start() {
        installStyle();
        enhanceAll(document);

        const observer = new MutationObserver(mutations => {
            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (!(node instanceof Element)) continue;
                    enhanceAll(node);
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
})();
