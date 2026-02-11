const container = document.getElementById("canvas-container");
const workspace = document.getElementById("workspace");
const infoPanel = document.getElementById("info-panel");

let scale = 1;
let posX = 0;
let posY = 0;
let isDragging = false;
let startX, startY;

// Cargar SVG externo
fetch("/static/svg/plano.svg")
    .then(res => res.text())
    .then(svgText => {
        container.innerHTML = svgText;
        loadDevices();
    });

// Zoom con rueda
workspace.addEventListener("wheel", (e) => {
    e.preventDefault();
    scale += e.deltaY * -0.001;
    scale = Math.min(Math.max(.5, scale), 3);
    updateTransform();
});

// Pan estilo Photoshop
workspace.addEventListener("mousedown", (e) => {
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

// Cargar dispositivos
async function loadDevices() {
    const res = await fetch("/api/devices");
    const devices = await res.json();
    const svg = container.querySelector("svg");

    devices.forEach(device => {
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", device.x);
        circle.setAttribute("cy", device.y);
        circle.setAttribute("r", 8);
        circle.setAttribute("fill", getColor(device.status));
        circle.classList.add("device");

        circle.addEventListener("click", () => {
            infoPanel.innerHTML = `
                <strong>${device.name}</strong><br>
                Tipo: ${device.type}<br>
                IP: ${device.ip}<br>
                Estado: ${device.status}
            `;
        });

        svg.appendChild(circle);
    });
}

function getColor(status) {
    if (status === "online") return "lime";
    if (status === "offline") return "red";
    return "orange";
}
