const cameraGrid = document.querySelector("#camera-grid");
const alertList = document.querySelector("#alert-list");
const connectionStatus = document.querySelector("#connection-status");
const cameraDialog = document.querySelector("#camera-dialog");
const cameraForm = document.querySelector("#camera-form");
const toast = document.querySelector("#toast");
const cameraStates = new Map();
let refreshInProgress = false;
let toastTimeout;

const stateLabels = {
  conectando: "Conectando",
  normal: "En línea",
  alerta: "Alerta",
  sin_conexion: "Sin conexión",
  inactiva: "Inactiva",
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Error ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toast.classList.remove("visible"), 3500);
}

function setConnection(connected) {
  connectionStatus.classList.toggle("offline", !connected);
  connectionStatus.innerHTML = `<i></i>${connected ? "Sistema conectado" : "Sin conexión con el servidor"}`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("es-MX", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

function renderCameras(cameras) {
  const activeCount = cameras.filter((camera) => camera.activa).length;
  const alertCount = [...cameraStates.values()].filter((camera) => camera.estado === "alerta").length;
  document.querySelector("#active-cameras").textContent = activeCount;
  document.querySelector("#total-cameras").textContent = `de ${cameras.length} cámaras`;
  document.querySelector("#detecting-cameras").textContent = alertCount;
  document.querySelector("#camera-count").textContent = `${cameras.length} ${cameras.length === 1 ? "cámara" : "cámaras"}`;

  if (!cameras.length) {
    cameraGrid.innerHTML = '<div class="empty-state">Aún no hay cámaras configuradas. Agrega una fuente de video para comenzar.</div>';
    return;
  }

  cameraGrid.innerHTML = cameras.map((camera) => {
    const state = cameraStates.get(camera.id);
    const status = state?.estado ?? (camera.activa ? "conectando" : "inactiva");
    const stateLabel = stateLabels[status] ?? status;
    const updated = state?.ultima_actualizacion ? `Actualizado ${formatDate(state.ultima_actualizacion)}` : "Esperando fotogramas";
    return `<article class="camera-card">
      <div class="camera-preview">
        <img src="/camaras/${camera.id}/ultimo-frame?t=${Date.now()}" alt="Fotograma de ${escapeHtml(camera.nombre)}">
        <span class="preview-placeholder">Sin fotogramas disponibles</span>
        <div class="camera-overlay"><span class="camera-label">${escapeHtml(camera.nombre)}</span><span class="status-pill ${escapeHtml(status)}">${escapeHtml(stateLabel)}</span></div>
      </div>
      <div class="camera-info">
        <div><strong title="${escapeHtml(camera.nombre)}">${escapeHtml(camera.nombre)}</strong><small>${escapeHtml(updated)}</small></div>
        <div class="camera-actions">
          <button type="button" data-action="toggle" data-id="${camera.id}" data-active="${camera.activa}" aria-label="${camera.activa ? "Desactivar" : "Activar"} ${escapeHtml(camera.nombre)}">${camera.activa ? "Pausar" : "Activar"}</button>
        </div>
      </div>
    </article>`;
  }).join("");
}

function renderAlerts(alerts, cameras, newCount) {
  document.querySelector("#new-alerts").textContent = newCount;
  if (!alerts.length) {
    alertList.innerHTML = '<tr><td colspan="6" class="table-empty">No hay alertas registradas.</td></tr>';
    return;
  }
  const cameraNames = new Map(cameras.map((camera) => [camera.id, camera.nombre]));
  alertList.innerHTML = alerts.map((alert) => {
    const isSmoke = alert.clase.toLowerCase().includes("smoke") || alert.clase.toLowerCase().includes("humo");
    const eventLabel = isSmoke ? "Humo" : "Fuego";
    const statusLabel = { nueva: "Nueva", confirmada: "Confirmada", falsa_alarma: "Falsa alarma" }[alert.estado] ?? alert.estado;
    const actions = alert.estado === "nueva"
      ? `<button type="button" data-action="confirm" data-id="${alert.id}">Confirmar</button><button type="button" data-action="false-alarm" data-id="${alert.id}">Falsa</button>`
      : "";
    return `<tr>
      <td><span class="event-name"><span class="event-icon ${isSmoke ? "smoke" : ""}">${isSmoke ? "≋" : "△"}</span>${eventLabel}</span></td>
      <td>${escapeHtml(cameraNames.get(alert.camara_id) ?? `Cámara ${alert.camara_id}`)}</td>
      <td>${Math.round(alert.confianza * 100)}%</td>
      <td>${escapeHtml(formatDate(alert.fecha))}</td>
      <td><span class="alert-state ${escapeHtml(alert.estado)}">${escapeHtml(statusLabel)}</span></td>
      <td><div class="row-actions">${actions}</div></td>
    </tr>`;
  }).join("");
}

async function refreshDashboard() {
  if (refreshInProgress) return;
  refreshInProgress = true;
  try {
    const [cameras, statuses, alerts] = await Promise.all([
      api("/camaras"),
      api("/camaras/estado"),
      api("/alertas?limit=200"),
    ]);
    cameraStates.clear();
    statuses.forEach((status) => cameraStates.set(status.camara_id, status));
    renderCameras(cameras);
    renderAlerts(alerts.slice(0, 8), cameras, alerts.filter((alert) => alert.estado === "nueva").length);
    setConnection(true);
    document.querySelector("#last-updated").textContent = `Actualizado ${new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date())}`;
  } catch (error) {
    setConnection(false);
    console.error("No se pudo actualizar el panel:", error);
    document.querySelector("#last-updated").textContent = "No se pudieron cargar los datos";
  } finally {
    refreshInProgress = false;
  }
}

document.querySelector("#refresh-button").addEventListener("click", refreshDashboard);
document.querySelector("#open-camera-form").addEventListener("click", () => {
  document.querySelector("#camera-form-error").textContent = "";
  cameraDialog.showModal();
});
document.querySelector("#close-camera-form").addEventListener("click", () => cameraDialog.close());
document.querySelector("#cancel-camera-form").addEventListener("click", () => cameraDialog.close());

cameraForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(cameraForm);
  const payload = {
    nombre: formData.get("nombre").trim(),
    url: formData.get("url").trim(),
    activa: true,
    conf_humo: Number(formData.get("conf_humo")),
    conf_fuego: Number(formData.get("conf_fuego")),
  };
  try {
    await api("/camaras", { method: "POST", body: JSON.stringify(payload) });
    cameraDialog.close();
    cameraForm.reset();
    cameraForm.elements.conf_humo.value = "0.3";
    cameraForm.elements.conf_fuego.value = "0.3";
    showToast("Cámara agregada correctamente.");
    await refreshDashboard();
  } catch (error) {
    document.querySelector("#camera-form-error").textContent = `No se pudo guardar: ${error.message}`;
  }
});

cameraGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action='toggle']");
  if (!button) return;
  button.disabled = true;
  try {
    await api(`/camaras/${button.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ activa: button.dataset.active !== "true" }),
    });
    showToast(button.dataset.active === "true" ? "Cámara pausada." : "Cámara activada.");
    await refreshDashboard();
  } catch (error) {
    showToast(`No se pudo actualizar la cámara: ${error.message}`);
    button.disabled = false;
  }
});

cameraGrid.addEventListener("load", (event) => {
  if (event.target instanceof HTMLImageElement) {
    event.target.nextElementSibling.hidden = true;
  }
}, true);

cameraGrid.addEventListener("error", (event) => {
  if (event.target instanceof HTMLImageElement) {
    event.target.hidden = true;
  }
}, true);

alertList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const estado = button.dataset.action === "confirm" ? "confirmada" : "falsa_alarma";
  button.disabled = true;
  try {
    await api(`/alertas/${button.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ estado }),
    });
    showToast(estado === "confirmada" ? "Alerta confirmada." : "Alerta marcada como falsa.");
    await refreshDashboard();
  } catch (error) {
    showToast(`No se pudo actualizar la alerta: ${error.message}`);
    button.disabled = false;
  }
});

refreshDashboard();
setInterval(refreshDashboard, 3000);
