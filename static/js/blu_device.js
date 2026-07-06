let currentDevice = null;


// ----------------------------------------------------
// Gerät laden
// ----------------------------------------------------

async function loadBluetoothDevice(){

    try{

        const response = await fetch(
            "/api/hardware/device/" +
            encodeURIComponent(
                deviceId
            )
        );

        const data = await response.json();

        if(!data.success){

            showDialog(
                "Bluetooth Gerät",
                JSON.stringify(
                    data,
                    null,
                    2
                )
            );

            return;
        }

        currentDevice = data.device;

        renderBluetoothDevice(
            currentDevice
        );

    }

    catch(err){

        console.error(err);

        showDialog(
            "Fehler",
            String(err)
        );

    }

}


// ----------------------------------------------------
// Gerät anzeigen
// ----------------------------------------------------

function renderBluetoothDevice(device){

    const props =
        device.properties || {};

    document
    .getElementById("device-name")
    .textContent =
        device.name || "Bluetooth Gerät";

    document
    .getElementById("device-model")
    .textContent =
        device.model || "--";

    document
    .getElementById("device-model-detail")
    .textContent =
        device.model || "--";

    document
    .getElementById("device-manufacturer")
    .textContent =
        device.manufacturer || "--";

    document
    .getElementById("device-type")
    .textContent =
        device.type || "--";

    document
    .getElementById("device-online")
    .innerHTML =
        device.online
        ? '<span class="badge">Verbunden</span>'
        : "Offline";

    document
    .getElementById("device-addr")
    .textContent =
        props.addr || "--";

    document
    .getElementById("device-rssi")
    .textContent =
        props.rssi !== undefined
        ? props.rssi + " dBm"
        : "--";

    document
    .getElementById("device-encrypted")
    .textContent =
        props.encrypted
        ? "Ja"
        : "Nein";

    document
    .getElementById("device-model-id")
    .textContent =
        props.model_id ?? "--";

    document
    .getElementById("device-gateway")
    .textContent =
        props.gateway_ip || props.gateway_id || "--";

    document
    .getElementById("device-temperature")
    .textContent =
        props.temperature !== undefined
        ? props.temperature + " °C"
        : "--";

    document
    .getElementById("device-humidity")
    .textContent =
        props.humidity !== undefined
        ? props.humidity + " %"
        : "--";

    document
    .getElementById("device-battery")
    .textContent =
        props.battery !== undefined
        ? props.battery + " %"
        : "--";

    document
    .getElementById("device-last-seen")
    .textContent =
        props.last_seen
        ? new Date(
            props.last_seen * 1000
        ).toLocaleString()
        : "--";

}


// ----------------------------------------------------
// Aktionen
// ----------------------------------------------------

function openGateway(){

    if(
        !currentDevice ||
        !currentDevice.properties
    ){
        return;
    }

    const gatewayId =
        currentDevice.properties.gateway_id;

    if(!gatewayId){

        showDialog(
            "Gateway",
            "Kein Gateway hinterlegt."
        );

        return;
    }

    window.location.href =
        "/devices/" +
        encodeURIComponent(
            gatewayId
        );

}


function showRawData(){

    if(!currentDevice){

        showDialog(
            "Rohdaten",
            "Keine Daten geladen."
        );

        return;
    }

    showDialog(
        "Bluetooth Rohdaten",
        JSON.stringify(
            currentDevice,
            null,
            2
        )
    );

}


// ----------------------------------------------------
// Buttons verbinden
// ----------------------------------------------------

function bindButtons(){

    document
    .getElementById("refresh-btn")
    ?.addEventListener(
        "click",
        loadBluetoothDevice
    );

    document
    .getElementById("gateway-btn")
    ?.addEventListener(
        "click",
        openGateway
    );

    document
    .getElementById("raw-btn")
    ?.addEventListener(
        "click",
        showRawData
    );

}


// ----------------------------------------------------
// Start
// ----------------------------------------------------

bindButtons();

loadBluetoothDevice();

setInterval(
    loadBluetoothDevice,
    5000
);
