let currentDevice = null;


// ----------------------------------------------------
// Helfer
// ----------------------------------------------------

function setText(id, value){

    const element =
        document.getElementById(id);

    if(!element){

        console.warn(
            "Element nicht gefunden:",
            id
        );

        return;

    }

    element.textContent =
        value ?? "--";

}


function setHtml(id, value){

    const element =
        document.getElementById(id);

    if(!element){

        console.warn(
            "Element nicht gefunden:",
            id
        );

        return;

    }

    element.innerHTML =
        value ?? "--";

}


function formatLastSeen(value){

    if(!value){
        return "--";
    }

    return new Date(
        value * 1000
    ).toLocaleString();

}


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

    setText(
        "device-name",
        device.name || "Bluetooth Gerät"
    );

    setText(
        "device-model",
        device.model || "--"
    );

    setText(
        "device-model-detail",
        device.model || "--"
    );

    setText(
        "device-manufacturer",
        device.manufacturer || "--"
    );

    setText(
        "device-type",
        device.type || "--"
    );

    setHtml(
        "device-online",
        device.online
        ? '<span class="badge online">Verbunden</span>'
        : '<span class="badge offline">Offline</span>'
    );

    setText(
        "device-addr",
        props.addr || "--"
    );

    setText(
        "device-rssi",
        props.rssi !== undefined
        ? props.rssi + " dBm"
        : "--"
    );

    setText(
        "device-encrypted",
        props.encrypted
        ? "Ja"
        : "Nein"
    );

    setText(
        "device-model-id",
        props.model_id ?? "--"
    );

    setText(
        "device-gateway",
        props.gateway_ip ||
        props.gateway_id ||
        "--"
    );

    setText(
        "device-temperature",
        props.temperature !== undefined
        ? props.temperature + " °C"
        : "--"
    );

    setText(
        "device-humidity",
        props.humidity !== undefined
        ? props.humidity + " %"
        : "--"
    );

    setText(
        "device-battery",
        props.battery !== undefined
        ? props.battery + " %"
        : "--"
    );

    setText(
        "device-last-seen",
        formatLastSeen(
            props.last_seen
        )
    );

}


// ----------------------------------------------------
// Aktionen
// ----------------------------------------------------
async function setupSensors(){

    try{

        showDialog(
            "Sensorwerte",
            "Sensorwerte werden eingerichtet...\n\nBitte den BLU H&T kurz aufwecken."
        );

        const response = await fetch(
            "/api/hardware/device/" +
            encodeURIComponent(
                deviceId
            ) +
            "/setup-sensors",
            {
                method:"POST"
            }
        );

        const data = await response.json();

        showDialog(
            "Sensorwerte Einrichtung",
            JSON.stringify(
                data,
                null,
                2
            )
        );

        loadBluetoothDevice();

    }

    catch(err){

        console.error(err);

        showDialog(
            "Sensorwerte Fehler",
            String(err)
        );

    }

}

function openGateway(){

    if(
        !currentDevice ||
        !currentDevice.properties
    ){

        showDialog(
            "Gateway",
            "Keine Gerätedaten geladen."
        );

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

    document
    .getElementById("setup-sensors-btn")
    ?.addEventListener(
        "click",
        setupSensors
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
