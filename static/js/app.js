const container = document.getElementById("canvas-container");
const workspace = document.getElementById("workspace");
const infoPanel = document.getElementById("info-panel");

let scale = 1;
let posX = 0;
let posY = 0;
let isDragging = false;
let startX, startY;

let currentPlano = "plano";
let createMode = false;
let newDevicePosition = null;

let devicesMap = {};
let connections = [];
let selectedDevice = null;
let connectMode = false;
let firstDeviceForConnection = null;

// =========================
// LOAD PLANO (SVG + DEVICES + CONNECTIONS)
// =========================

async function loadPlano(planoName) {
    currentPlano = planoName;

    const res = await fetch(`/static/svg/${planoName}.svg`);
    const svgText = await res.text();

    container.innerHTML = svgText;

    await loadDevices();
    await loadConnections();
}

// Default load
loadPlano("plano");

// Plano selector
document.getElementById("plano-selector")
    .addEventListener("change", (e) => {
        loadPlano(e.target.value);
    });

// =========================
// ZOOM
// =========================

workspace.addEventListener("wheel", (e) => {
    e.preventDefault();
    scale += e.deltaY * -0.001;
    scale = Math.min(Math.max(.5, scale), 3);
    updateTransform();
});

// =========================
// PAN
// =========================

workspace.addEventListener("mousedown", (e) => {
    if (createMode) return;

    isDragging = true;
    startX = e.clientX - posX;
    startY = e.clientY - posY;
    workspace.style.cursor = "grabbing";
});

workspace.addEventListener("mouseup", () => {
    isDragging = false;
    workspace.style.cursor = "grab";
});

workspace.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    posX = e.clientX - startX;
    posY = e.clientY - startY;
    updateTransform();
});

function updateTransform() {
    container.style.transform = `translate(${posX}px, ${posY}px) scale(${scale})`;
}

// =========================
// CREATE DEVICE MODE
// =========================

document.getElementById("create-device-btn")
    .addEventListener("click", () => {
        createMode = true;
        workspace.style.cursor = "crosshair";
    });

workspace.addEventListener("click", (e) => {
    if (!createMode) return;

    const svg = container.querySelector("svg");
    if (!svg) return;

    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;

    const svgP = pt.matrixTransform(svg.getScreenCTM().inverse());

    newDevicePosition = {
        x: Math.round(svgP.x),
        y: Math.round(svgP.y)
    };

    createMode = false;
    workspace.style.cursor = "grab";

    showDeviceForm();
});

// =========================
// LOAD DEVICES
// =========================

async function loadDevices() {
    devicesMap = {};

    const res = await fetch(`/api/devices?plano=${currentPlano}`);
    const devices = await res.json();

    const svg = container.querySelector("svg");
    if (!svg) return;

    devices.forEach(device => {
        devicesMap[device.id] = device;

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");

        circle.setAttribute("cx", device.x);
        circle.setAttribute("cy", device.y);
        circle.setAttribute("r", 8);
        circle.setAttribute("fill", getColor(device.status));
        circle.classList.add("device");
        circle.dataset.id = device.id;

        circle.addEventListener("click", (e) => {
            e.stopPropagation();

            if (connectMode) {
                createConnection(firstDeviceForConnection, device.id);
                connectMode = false;
                firstDeviceForConnection = null;
                return;
            }

            selectDevice(device.id);
        });

        // Dragging
        circle.addEventListener("mousedown", (e) => {
            if (!selectedDevice || selectedDevice !== device.id) return;

            e.stopPropagation();
            startDeviceDrag(e, circle, device);
        });

        svg.appendChild(circle);
    });
}

function getColor(status) {
    if (status === "online") return "lime";
    if (status === "offline") return "red";
    return "orange";
}

// =========================
// DEVICE SELECTION UI
// =========================

function selectDevice(deviceId) {
    selectedDevice = deviceId;
    const device = devicesMap[deviceId];

    infoPanel.innerHTML = `
        <strong>${device.name}</strong><br>
        Tipo: ${device.type}<br>
        IP: ${device.ip || "-"}<br>
        Estado: ${device.status || "-"}<br><br>

        <button onclick="enableConnectMode()">Conectar</button>
        <button onclick="deleteDevice(${deviceId})">Eliminar</button>
    `;
}

function enableConnectMode() {
    connectMode = true;
    firstDeviceForConnection = selectedDevice;
    infoPanel.innerHTML = "Selecciona el segundo dispositivo...";
}

// =========================
// CONNECTIONS
// =========================

async function createConnection(id1, id2) {
    if (id1 === id2) return;

    await fetch("/api/connections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            from_device_id: id1,
            to_device_id: id2,
            connection_type: "ethernet"
        })
    });

    loadPlano(currentPlano);
}

async function loadConnections() {
    const res = await fetch(`/api/connections?plano=${currentPlano}`);
    connections = await res.json();

    const svg = container.querySelector("svg");

    connections.forEach(conn => {
        const d1 = devicesMap[conn.from_device_id];
        const d2 = devicesMap[conn.to_device_id];

        if (!d1 || !d2) return;

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");

        line.setAttribute("x1", d1.x);
        line.setAttribute("y1", d1.y);
        line.setAttribute("x2", d2.x);
        line.setAttribute("y2", d2.y);
        line.setAttribute("stroke", "#00bfff");
        line.setAttribute("stroke-width", 2);

        svg.insertBefore(line, svg.firstChild);
    });
}

// =========================
// DRAG TO MOVE DEVICE
// =========================

function startDeviceDrag(e, circle, device) {
    let dragging = true;

    function onMouseMove(ev) {
        if (!dragging) return;

        const svg = container.querySelector("svg");
        const pt = svg.createSVGPoint();
        pt.x = ev.clientX;
        pt.y = ev.clientY;

        const svgP = pt.matrixTransform(svg.getScreenCTM().inverse());

        circle.setAttribute("cx", svgP.x);
        circle.setAttribute("cy", svgP.y);

        device.x = Math.round(svgP.x);
        device.y = Math.round(svgP.y);
    }

    function onMouseUp() {
        dragging = false;

        fetch(`/api/devices`, {
            method: "POST", // ideally PUT for proper update
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(device)
        });

        loadPlano(currentPlano);

        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
}

// =========================
// DELETE DEVICE
// =========================

async function deleteDevice(id) {
    await fetch(`/api/devices/${id}`, { method: "DELETE" });
    selectedDevice = null;
    loadPlano(currentPlano);
}

// =========================
// DEVICE CREATION FORM
// =========================

function showDeviceForm() {
    infoPanel.innerHTML = `
        <h3>Nuevo Dispositivo</h3>
        Nombre: <input id="dev-name"><br>
        Tipo:
        <select id="dev-type">
            <option value="pc">PC</option>
        </select><br>
        IP: <input id="dev-ip"><br>
        Estado:
        <select id="dev-status">
            <option value="online">Online</option>
            <option value="offline">Offline</option>
        </select><br>

        <div id="extra-fields"></div>

        <button onclick="submitDevice()">Guardar</button>
    `;

    document.getElementById("dev-type")
        .addEventListener("change", renderExtraFields);

    renderExtraFields();
}

function renderExtraFields() {
    const type = document.getElementById("dev-type").value;
    const container = document.getElementById("extra-fields");

    if (type === "pc") {
        container.innerHTML = `
            <hr>
            <strong>Datos PC</strong><br>
            CPU: <input id="pc-cpu"><br>
            RAM (GB): <input id="pc-ram" type="number"><br>
            GPU: <input id="pc-gpu"><br>
        `;
    } else {
        container.innerHTML = "";
    }
}

async function submitDevice() {
    const type = document.getElementById("dev-type").value;

    const payload = {
        name: document.getElementById("dev-name").value,
        type: type,
        ip: document.getElementById("dev-ip").value,
        status: document.getElementById("dev-status").value,
        x: newDevicePosition.x,
        y: newDevicePosition.y,
        plano: currentPlano
    };

    if (type === "pc") {
        payload.cpu = document.getElementById("pc-cpu").value;
        payload.ram = parseInt(document.getElementById("pc-ram").value || 0);
        payload.gpu = document.getElementById("pc-gpu").value;
    }

    await fetch("/api/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    infoPanel.innerHTML = "Dispositivo creado correctamente";

    loadPlano(currentPlano);
}
