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
// Gateway laden
// ----------------------------------------------------

async function loadGateway(){

    try{

        const response = await fetch(

            "/api/hardware/" +
            gatewayId

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

    }

}



// ----------------------------------------------------
// Gateway aktualisieren
// ----------------------------------------------------

async function refreshGateway(){

    try{

        const response = await fetch(

            "/api/hardware/" +
            gatewayId +
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

    }

}



// ----------------------------------------------------
// Gateway anzeigen
// ----------------------------------------------------

function updateGateway(gateway){

    document
    .getElementById("gateway-name")
    .textContent =
        gateway.name;


    document
    .getElementById("gateway-ip")
    .textContent =
        gateway.ip;


    document
    .getElementById("gateway-firmware")
    .textContent =
        gateway.firmware || "--";


    document
    .getElementById("gateway-rssi")
    .textContent =
        (gateway.rssi ?? "--")
        + " dBm";


    document
    .getElementById("gateway-uptime")
    .textContent =
        gateway.uptime ?? "--";


    document
    .getElementById("gateway-model")
    .textContent =
        gateway.model;


    document
    .getElementById("gateway-mac")
    .textContent =
        gateway.mac;


    document
    .getElementById("gateway-online")
    .innerHTML =

        gateway.online

        ?

        '<span class="badge">Online</span>'

        :

        'Offline';



    document
    .getElementById("gateway-bluetooth")
    .innerHTML =

        gateway.bluetooth_enabled

        ?

        '<span class="badge">🟢 Aktiv</span>'

        :

        '<span class="badge" style="background:#dc2626">🔴 Deaktiviert</span>';



    renderActions(
        gateway
    );

}

//
// ----------------------------------------------------
// Gateway Aktionen
// ----------------------------------------------------

function renderActions(gateway){

    const actions =

        document.getElementById(
            "gateway-actions"
        );


    actions.innerHTML = "";



    actions.innerHTML += `

        <button id="refresh-btn">

            Gateway aktualisieren

        </button>

    `;



    if(gateway.capabilities?.ble_config){

        actions.innerHTML += `

            <button id="bt-enable">

                🟢 Bluetooth aktivieren

            </button>

            <button id="bt-disable">

                🔴 Bluetooth deaktivieren

            </button>

        `;

    }



    if(gateway.capabilities?.bthome_discovery){

        actions.innerHTML += `

            <button id="ble-scan-btn">

                🔎 BLE Scan starten

            </button>

        `;

    }



    actions.innerHTML += `

        <button id="methods-btn">

            RPC Methoden anzeigen

        </button>

    `;



    bindButtons();

}

//
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

//
// ----------------------------------------------------
// Bluetooth
// ----------------------------------------------------

async function enableBluetooth(){

    await fetch(

        "/api/hardware/" +

        gatewayId +

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

        gatewayId +

        "/bluetooth/disable",

        {

            method:"POST"

        }

    );

    loadGateway();

}

//
// ----------------------------------------------------
// RPC Methoden
// ----------------------------------------------------

async function listMethods(){

    try{

        const response = await fetch(

            "/api/hardware/" +
            gatewayId +
            "/methods"

        );

        const data = await response.json();

        const methods = data.methods.methods;

        const groups = {};

        methods.forEach(method=>{

            const parts = method.split(".");

            const group = parts[0];

            const name = parts
                .slice(1)
                .join(".");

            if(!groups[group]){

                groups[group] = [];

            }

            groups[group].push(name);

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

            text

        );

    }

    catch(err){

        console.error(err);

    }

}


//
// ----------------------------------------------------
// BLE Scan
// ----------------------------------------------------

async function startBleScan(){

    try{

        const response = await fetch(

            "/api/hardware/" +

            gatewayId +

            "/ble/scan",

            {

                method:"POST"

            }

        );

        const data = await response.json();

        showDialog(

            "BLE Scan",

            JSON.stringify(

                data,

                null,

                2

            )

        );

    }

    catch(err){

        console.error(err);

    }

}

//
// ----------------------------------------------------
// Initialisierung
// ----------------------------------------------------

loadGateway();

setInterval(

    loadGateway,

    REFRESH_INTERVAL

);


