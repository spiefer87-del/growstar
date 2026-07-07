//
// ----------------------------------------------------
// Growstar
// Gateway.js
// ----------------------------------------------------


// ----------------------------------------------------
// Konstanten
// ----------------------------------------------------

const REFRESH_INTERVAL = 5000;



// ----------------------------------------------------
// Helfer
// ----------------------------------------------------

function wait(ms){

    return new Promise(
        resolve => setTimeout(
            resolve,
            ms
        )
    );

}



// ----------------------------------------------------
// Gateway laden
// ----------------------------------------------------

async function loadGateway(){

    try{

        const response = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            )
        );

        const data = await response.json();

        if(data.success){

            updateGateway(
                data.gateway
            );

        }

    }

    catch(err){

        console.error(err);

        showDialog(
            "Gateway Fehler",
            String(err)
        );

    }

}



// ----------------------------------------------------
// Gateway aktualisieren
// ----------------------------------------------------

async function refreshGateway(){

    try{

        const response = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/refresh",
            {
                method:"POST"
            }
        );

        const data = await response.json();

        if(data.success){

            updateGateway(
                data.gateway
            );

        }

    }

    catch(err){

        console.error(err);

        showDialog(
            "Gateway Fehler",
            String(err)
        );

    }

}



// ----------------------------------------------------
// Gateway anzeigen
// ----------------------------------------------------

function updateGateway(gateway){

    document
    .getElementById("gateway-name")
    .textContent =
        gateway.name || "Gateway";


    document
    .getElementById("gateway-ip")
    .textContent =
        gateway.ip || "--";


    document
    .getElementById("gateway-firmware")
    .textContent =
        gateway.firmware || "--";


    document
    .getElementById("gateway-rssi")
    .textContent =
        (gateway.rssi ?? "--") +
        " dBm";


    document
    .getElementById("gateway-uptime")
    .textContent =
        gateway.uptime ?? "--";


    document
    .getElementById("gateway-model")
    .textContent =
        gateway.model || "--";


    document
    .getElementById("gateway-mac")
    .textContent =
        gateway.mac || "--";


    document
    .getElementById("gateway-online")
    .innerHTML =
        gateway.online
        ? '<span class="badge online">Online</span>'
        : '<span class="badge offline">Offline</span>';


    document
    .getElementById("gateway-bluetooth")
    .innerHTML =
        gateway.bluetooth_enabled
        ? '<span class="badge online">Bluetooth aktiv</span>'
        : '<span class="badge danger">Bluetooth deaktiviert</span>';


    renderActions(
        gateway
    );

}



// ----------------------------------------------------
// Gateway Aktionen anzeigen
// ----------------------------------------------------

function renderActions(gateway){

    const actions =
        document.getElementById(
            "gateway-actions"
        );

    if(!actions){

        console.warn(
            "gateway-actions nicht gefunden"
        );

        return;

    }

    actions.innerHTML = "";


    actions.innerHTML += `

        <button id="refresh-btn">

            Gateway aktualisieren

        </button>

    `;


    if(gateway.capabilities?.ble_config){

        actions.innerHTML += `

            <button id="bt-enable">

                Bluetooth aktivieren

            </button>

            <button
                id="bt-disable"
                class="secondary">

                Bluetooth deaktivieren

            </button>

        `;

    }


    if(gateway.capabilities?.bthome_discovery){

        actions.innerHTML += `

            <button id="ble-scan-btn">

                BLE Scan starten

            </button>

        `;

    }


    actions.innerHTML += `

        <button
            id="methods-btn"
            class="secondary">

            RPC Methoden anzeigen

        </button>

    `;


    bindButtons();

}



// ----------------------------------------------------
// Buttons verbinden
// ----------------------------------------------------

function bindButtons(){

    document
    .getElementById("refresh-btn")
    ?.addEventListener(
        "click",
        refreshGateway
    );


    document
    .getElementById("bt-enable")
    ?.addEventListener(
        "click",
        enableBluetooth
    );


    document
    .getElementById("bt-disable")
    ?.addEventListener(
        "click",
        disableBluetooth
    );


    document
    .getElementById("methods-btn")
    ?.addEventListener(
        "click",
        listMethods
    );


    document
    .getElementById("ble-scan-btn")
    ?.addEventListener(
        "click",
        startBleScan
    );

}



// ----------------------------------------------------
// Bluetooth
// ----------------------------------------------------

async function enableBluetooth(){

    await fetch(
        "/api/hardware/" +
        encodeURIComponent(
            gatewayId
        ) +
        "/bluetooth/enable",
        {
            method:"POST"
        }
    );

    loadGateway();

}



async function disableBluetooth(){

    await fetch(
        "/api/hardware/" +
        encodeURIComponent(
            gatewayId
        ) +
        "/bluetooth/disable",
        {
            method:"POST"
        }
    );

    loadGateway();

}



// ----------------------------------------------------
// RPC Methoden
// ----------------------------------------------------

async function listMethods(){

    try{

        const response = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/methods"
        );

        const data = await response.json();

        const methods =
            data.methods?.methods || [];

        const groups = {};

        methods.forEach(method=>{

            const parts =
                method.split(".");

            const group =
                parts[0];

            const name =
                parts
                .slice(1)
                .join(".");

            if(!groups[group]){

                groups[group] = [];

            }

            groups[group].push(
                name
            );

        });

        let text = "";

        Object.keys(groups)
        .sort()
        .forEach(group=>{

            text += group + "\n";
            text += "────────────────────────\n";

            groups[group]
            .sort()
            .forEach(name=>{

                text +=
                    "• " +
                    name +
                    "\n";

            });

            text += "\n";

        });

        showDialog(
            "RPC Methoden",
            text || "Keine Methoden gefunden."
        );

    }

    catch(err){

        console.error(err);

        showDialog(
            "RPC Methoden Fehler",
            String(err)
        );

    }

}



// ----------------------------------------------------
// BLE Scan
// ----------------------------------------------------

async function startBleScan(){

    try{

        showDialog(
            "BLE Scan",
            "Scan wird gestartet..."
        );

        const scanResponse = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/ble/scan",
            {
                method:"POST"
            }
        );

        const scanData = await scanResponse.json();

        if(!scanData.success){

            showDialog(
                "BLE Scan Fehler",
                JSON.stringify(
                    scanData,
                    null,
                    2
                )
            );

            return;

        }

        const duration =
            scanData.result?.duration ||
            60;

        showDialog(
            "BLE Scan",
            "Scan läuft...\n\nDauer: " +
            duration +
            " Sekunden\n\nFalls es ein neuer Sensor ist: bitte Pairing-Modus aktivieren.\n\nBereits gekoppelte Sensoren müssen nur kurz senden."
        );

        await wait(
            (duration + 3) * 1000
        );

        const resultResponse = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/ble/discovered"
        );

        const resultData = await resultResponse.json();


        // Wichtig:
        // Immer ausführen, auch wenn device_count 0 ist.
        // Bereits gekoppelte Sensoren kommen als sensor_events.
        let addData = null;

        const addResponse = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/ble/add-discovered",
            {
                method:"POST"
            }
        );

        addData = await addResponse.json();


        showDialog(
            "BLE Scan Ergebnis",
            JSON.stringify(
                {
                    scan: resultData,
                    added: addData
                },
                null,
                2
            )
        );

        loadGateway();

    }

    catch(err){

        console.error(err);

        showDialog(
            "BLE Scan Fehler",
            String(err)
        );

    }

}



// ----------------------------------------------------
// Initialisierung
// ----------------------------------------------------

loadGateway();

setInterval(
    loadGateway,
    REFRESH_INTERVAL
);
