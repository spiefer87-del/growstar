let currentDevice = null;

const DEVICE_REFRESH_INTERVAL = 10000;

let loadInProgress = false;


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

async function loadBluetoothDevice(showResult=false){

    if(loadInProgress){

        return;

    }

    loadInProgress = true;

    try{

        const response = await fetch(
            "/api/hardware/device/" +
            encodeURIComponent(
                deviceId
            )
        );

        const data =
            await response.json();

        if(!data.success){

            if(showResult){

                showDialog(
                    "Bluetooth Gerät",
                    JSON.stringify(
                        data,
                        null,
                        2
                    )
                );

            }

            return;

        }

        currentDevice =
            data.device;

        renderBluetoothDevice(
            currentDevice
        );

        if(showResult){

            showDialog(
                "Anzeige aktualisiert",
                "Die aktuellen gespeicherten Gerätedaten wurden geladen."
            );

        }

    }

    catch(err){

        console.error(err);

        if(showResult){

            showDialog(
                "Fehler",
                String(err)
            );

        }

    }

    finally{

        loadInProgress = false;

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
        props.rssi !== undefined && props.rssi !== null
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
        props.temperature !== undefined && props.temperature !== null
        ? props.temperature + " °C"
        : "--"
    );

    setText(
        "device-humidity",
        props.humidity !== undefined && props.humidity !== null
        ? props.humidity + " %"
        : "--"
    );

    setText(
        "device-battery",
        props.battery !== undefined && props.battery !== null
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

        const data =
            await response.json();

        showDialog(
            "Sensorwerte Einrichtung",
            JSON.stringify(
                data,
                null,
                2
            )
        );

        await loadBluetoothDevice(
            false
        );

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


async function pairCurrentGateway(){

    try{

        if(
            !currentDevice ||
            !currentDevice.properties ||
            !currentDevice.properties.gateway_id
        ){

            showDialog(
                "Bluetooth koppeln",
                "Kein Gateway beim Gerät hinterlegt."
            );

            return;

        }

        const gatewayId =
            currentDevice.properties.gateway_id;

        showDialog(
            "Bluetooth koppeln",
            "Gerät wird mit Gateway " +
            gatewayId +
            " gekoppelt..."
        );

        const response = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/ble/device/" +
            encodeURIComponent(
                deviceId
            ) +
            "/pair",
            {
                method:"POST"
            }
        );

        const data =
            await response.json();

        showDialog(
            "Bluetooth koppeln",
            JSON.stringify(
                data,
                null,
                2
            )
        );

        await loadBluetoothDevice(
            false
        );

    }

    catch(err){

        console.error(err);

        showDialog(
            "Bluetooth koppeln Fehler",
            String(err)
        );

    }

}


async function unpairCurrentGateway(){

    try{

        if(
            !currentDevice ||
            !currentDevice.properties ||
            !currentDevice.properties.gateway_id
        ){

            showDialog(
                "Bluetooth entkoppeln",
                "Kein Gateway beim Gerät hinterlegt."
            );

            return;

        }

        const gatewayId =
            currentDevice.properties.gateway_id;

        showDialog(
            "Bluetooth entkoppeln",
            "Gerät wird von Gateway " +
            gatewayId +
            " entkoppelt..."
        );

        const response = await fetch(
            "/api/hardware/" +
            encodeURIComponent(
                gatewayId
            ) +
            "/ble/device/" +
            encodeURIComponent(
                deviceId
            ) +
            "/unpair",
            {
                method:"POST"
            }
        );

        const data =
            await response.json();

        showDialog(
            "Bluetooth entkoppeln",
            JSON.stringify(
                data,
                null,
                2
            )
        );

        await loadBluetoothDevice(
            false
        );

    }

    catch(err){

        console.error(err);

        showDialog(
            "Bluetooth entkoppeln Fehler",
            String(err)
        );

    }

}


// ----------------------------------------------------
// Buttons verbinden
// ----------------------------------------------------

function bindButtons(){

    document
    .getElementById("refresh-btn")
    ?.addEventListener(
        "click",
        ()=>loadBluetoothDevice(true)
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

    document
    .getElementById("pair-current-gateway-btn")
    ?.addEventListener(
        "click",
        pairCurrentGateway
    );

    document
    .getElementById("unpair-current-gateway-btn")
    ?.addEventListener(
        "click",
        unpairCurrentGateway
    );

}


// ----------------------------------------------------
// Start
// ----------------------------------------------------

bindButtons();

loadBluetoothDevice();

setInterval(
    ()=>loadBluetoothDevice(false),
    DEVICE_REFRESH_INTERVAL
);
