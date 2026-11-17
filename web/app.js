const cameraGrid = document.querySelector("#camera-grid");
const alertList = document.querySelector("#alert-list");
const connectionStatus = document.querySelector("#connection-status");
const cameraDialog = document.querySelector("#camera-dialog");
const cameraForm = document.querySelector("#camera-form");
const cameraSearch = document.querySelector("#camera-search");
const cameraFilter = document.querySelector("#camera-filter");
const toast = document.querySelector("#toast");

const cameraStates = new Map();
const mediaConnections = new Map();
const detectionTimers = new Map();
let cameras = [];
let cameraRenderKey = null;
let refreshInProgress = false;
let toastTimeout;

const stateLabels = {
  conectando: "Conectando",
  normal: "En línea",
  alerta: "Alerta",
  sin_conexion: "Sin conexión",
  inactiva: "Inactiva",
};

const frameObserver = "IntersectionObserver" in window
  ? new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      const preview = entry.target;
      const video = preview.querySelector("video[data-camera-id]");
      if (!video) return;
      if (entry.isIntersecting) {
        preview.dataset.inView = "true";
        startStream(video);
      } else {
        preview.dataset.inView = "false";
        stopStream(video);
      }
    });
  }, { rootMargin: "100px" })
  : null;

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...options.headers };
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers });

  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      message = JSON.parse(body).detail ?? body;
    } catch {
      // Some server errors are returned as plain text.
    }
    throw new Error(message || `Error ${response.status}`);
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
  connectionStatus.setAttribute("aria-live", "polite");
  document.querySelector("#system-health-dot").classList.toggle("offline", !connected);
  document.querySelector("#system-health-label").textContent = connected
    ? "Backend disponible"
    : "Backend sin conexión";
  document.querySelector("#system-health-detail").textContent = connected
    ? "API y monitoreo activos"
    : "No se reciben datos";
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("es-MX", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function matchesCameraFilter(camera) {
  const query = cameraSearch.value.trim().toLocaleLowerCase("es");
  if (query && !camera.nombre.toLocaleLowerCase("es").includes(query)) return false;

  const status = cameraStates.get(camera.id)?.estado ?? (camera.activa ? "conectando" : "inactiva");
  switch (cameraFilter.value) {
    case "activas":
      return camera.activa;
    case "alerta":
      return status === "alerta";
    case "sin_conexion":
      return status === "sin_conexion";
    case "inactivas":
      return !camera.activa || status === "inactiva";
    default:
      return true;
  }
}

function resetFrameObservers() {
  if (frameObserver) frameObserver.disconnect();
  cameraGrid.querySelectorAll(".camera-preview video[data-camera-id]").forEach(stopStream);
}

function waitForIceGathering(peer) {
  if (peer.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const onStateChange = () => {
      if (peer.iceGatheringState === "complete") {
        peer.removeEventListener("icegatheringstatechange", onStateChange);
        resolve();
      }
    };
    peer.addEventListener("icegatheringstatechange", onStateChange);
  });
}

function startStream(video) {
  const camera = cameras.find((item) => item.id === Number(video.dataset.cameraId));
  if (!camera?.activa) return;
  if (video.dataset.streaming === "true" && video.dataset.source === camera.url) return;
  stopStream(video);

  video.dataset.streaming = "true";
  video.dataset.source = camera.url;
  video.dataset.receivedFrame = "false";
  video.hidden = false;
  const placeholder = video.closest(".camera-preview").querySelector(".preview-placeholder");
  placeholder.hidden = false;
  placeholder.textContent = "Conectando con la fuente...";

  connectWebRTC(video, camera).catch((error) => {
    console.error("No se pudo iniciar WebRTC:", error);
    if (video.dataset.streaming === "true") {
      stopStream(video);
      placeholder.hidden = false;
      placeholder.textContent = "No se pudo conectar con la fuente";
    }
  });
}

async function connectWebRTC(video, camera) {
  const peer = new RTCPeerConnection();
  const connection = { peer, sessionId: null, cameraId: camera.id };
  mediaConnections.set(video, connection);

  peer.addTransceiver("video", { direction: "recvonly" });
  peer.addEventListener("track", (event) => {
    video.srcObject = event.streams[0] ?? new MediaStream([event.track]);
    video.play().catch((error) => console.error("No se pudo reproducir WebRTC:", error));
  });

  const offer = await peer.createOffer();
  await peer.setLocalDescription(offer);
  await waitForIceGathering(peer);
  const answer = await api(`/camaras/${camera.id}/webrtc`, {
    method: "POST",
    body: JSON.stringify(peer.localDescription),
  });

  if (video.dataset.streaming !== "true" || mediaConnections.get(video) !== connection) {
    await api(`/camaras/${camera.id}/webrtc/${answer.session_id}`, { method: "DELETE" });
    peer.close();
    return;
  }

  connection.sessionId = answer.session_id;
  await peer.setRemoteDescription({ type: answer.type, sdp: answer.sdp });
  startDetectionPolling(video);
}

function startDetectionPolling(video) {
  if (detectionTimers.has(video)) return;
  const update = async () => {
    if (video.dataset.streaming !== "true") return;
    try {
      const data = await api(`/camaras/${video.dataset.cameraId}/detecciones`);
      drawDetections(video, data);
    } catch (error) {
      console.error("No se pudieron actualizar las detecciones:", error);
    }
  };
  update();
  detectionTimers.set(video, setInterval(update, 250));
}

function drawDetections(video, data) {
  const canvas = video.closest(".camera-preview").querySelector("canvas");
  if (!video.videoWidth || !video.videoHeight) return;
  if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }

  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  const sourceWidth = data.ancho || canvas.width;
  const sourceHeight = data.alto || canvas.height;
  const scaleX = canvas.width / sourceWidth;
  const scaleY = canvas.height / sourceHeight;
  for (const detection of data.detecciones ?? []) {
    const [x1, y1, x2, y2] = detection.caja.map((value) => Number(value));
    const left = x1 * scaleX;
    const top = y1 * scaleY;
    const width = (x2 - x1) * scaleX;
    const height = (y2 - y1) * scaleY;
    const color = detection.clase.toLowerCase() === "fire" ? "#ff8277" : "#9ee2ad";
    context.strokeStyle = color;
    context.lineWidth = Math.max(2, canvas.width / 400);
    context.strokeRect(left, top, width, height);
    context.font = `${Math.max(14, canvas.width / 60)}px Segoe UI`;
    context.fillStyle = color;
    context.fillText(
      `${detection.clase} ${Math.round(detection.confianza * 100)}%`,
      left,
      Math.max(top - 6, 16),
    );
  }
}

function stopStream(video) {
  const connection = mediaConnections.get(video);
  if (video.dataset.streaming !== "true" && !connection) return;
  video.dataset.streaming = "false";
  video.dataset.receivedFrame = "false";
  const timer = detectionTimers.get(video);
  if (timer) clearInterval(timer);
  detectionTimers.delete(video);

  if (connection) {
    connection.peer.close();
    mediaConnections.delete(video);
    if (connection.sessionId) {
      api(`/camaras/${connection.cameraId}/webrtc/${connection.sessionId}`, {
        method: "DELETE",
      }).catch((error) => console.error("No se pudo cerrar WebRTC:", error));
    }
  }
  video.pause();
  video.srcObject = null;
  video.removeAttribute("src");
  video.load();
  video.hidden = true;
  const canvas = video.closest(".camera-preview").querySelector("canvas");
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  const placeholder = video.closest(".camera-preview").querySelector(".preview-placeholder");
  placeholder.hidden = false;
}

function renderCameraCards() {
  const visibleCameras = cameras.filter(matchesCameraFilter);
  const renderKey = visibleCameras.map((camera) => camera.id).join(",");
  document.querySelector("#camera-count").textContent = cameraSearch.value || cameraFilter.value !== "todas"
    ? `${visibleCameras.length} de ${cameras.length} cámaras`
    : `${cameras.length} ${cameras.length === 1 ? "cámara" : "cámaras"}`;

  if (renderKey !== cameraRenderKey) {
    resetFrameObservers();
    cameraRenderKey = renderKey;

    if (!visibleCameras.length) {
      const emptyMessage = cameras.length
        ? "No hay cámaras que coincidan con estos filtros."
        : "Aún no hay cámaras configuradas. Agrega una fuente de video para comenzar.";
      cameraGrid.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
      return;
    }

    cameraGrid.innerHTML = visibleCameras.map((camera) => `
      <article class="camera-card" data-camera-id="${camera.id}">
        <div class="camera-preview">
          <video data-camera-id="${camera.id}" aria-label="Video de ${escapeHtml(camera.nombre)}"
            autoplay muted playsinline loop hidden></video>
          <canvas aria-hidden="true"></canvas>
          <span class="preview-placeholder">Esperando fotogramas</span>
          <div class="camera-overlay">
            <span class="camera-label">${escapeHtml(camera.nombre)}</span>
            <span class="status-pill">Conectando</span>
          </div>
        </div>
        <div class="camera-info">
          <div class="camera-meta">
            <strong title="${escapeHtml(camera.nombre)}">${escapeHtml(camera.nombre)}</strong>
            <small class="camera-updated">Esperando señal</small>
          </div>
          <div class="camera-actions">
            <button class="camera-toggle" type="button" data-action="toggle"
              aria-label="Cambiar estado de ${escapeHtml(camera.nombre)}"></button>
            <button class="camera-delete" type="button" data-action="delete"
              aria-label="Eliminar ${escapeHtml(camera.nombre)}">Eliminar</button>
          </div>
        </div>
      </article>
    `).join("");

    cameraGrid.querySelectorAll(".camera-preview").forEach((preview) => {
      const video = preview.querySelector("video[data-camera-id]");
      if (frameObserver) frameObserver.observe(preview);
      else {
        preview.dataset.inView = "true";
        startStream(video);
      }
    });
  }

  visibleCameras.forEach(updateCameraCard);
}

function updateCameraCard(camera) {
  const card = cameraGrid.querySelector(`[data-camera-id="${camera.id}"].camera-card`);
  if (!card) return;

  const state = cameraStates.get(camera.id);
  const status = state?.estado ?? (camera.activa ? "conectando" : "inactiva");
  const video = card.querySelector("video");
  const placeholder = card.querySelector(".preview-placeholder");
  const statusPill = card.querySelector(".status-pill");
  const toggle = card.querySelector(".camera-toggle");
  const deleteButton = card.querySelector(".camera-delete");

  statusPill.className = `status-pill ${escapeHtml(status)}`;
  statusPill.textContent = stateLabels[status] ?? status;
  card.querySelector(".camera-updated").textContent = state?.ultima_actualizacion
    ? `Actualizado ${formatDate(state.ultima_actualizacion)}`
    : status === "sin_conexion"
      ? "No se recibe señal"
      : status === "inactiva"
        ? "Cámara pausada"
        : "Esperando primer fotograma";

  if (!camera.activa) {
    stopStream(video);
    video.hidden = true;
    placeholder.hidden = false;
    placeholder.textContent = "Cámara pausada";
  } else {
    if (video.dataset.source !== camera.url) stopStream(video);
    if (card.querySelector(".camera-preview").dataset.inView === "true") {
      startStream(video);
    }
    if (video.dataset.receivedFrame === "true") {
      placeholder.hidden = true;
    } else {
      video.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = status === "sin_conexion"
        ? "Sin conexión con la cámara"
        : status === "conectando"
          ? "Conectando con la cámara..."
          : "Esperando video";
    }
  }

  toggle.textContent = camera.activa ? "Pausar" : "Activar";
  toggle.dataset.id = camera.id;
  toggle.dataset.active = String(camera.activa);
  toggle.disabled = toggle.dataset.pending === "true";
  toggle.setAttribute("aria-label", `${camera.activa ? "Pausar" : "Activar"} ${camera.nombre}`);
  deleteButton.dataset.id = camera.id;
  deleteButton.disabled = deleteButton.dataset.pending === "true";
}

function renderAlerts(alerts, newCount) {
  document.querySelector("#new-alerts").textContent = newCount ?? 0;
  if (!alerts.length) {
    alertList.innerHTML = '<tr><td colspan="7" class="table-empty">No hay alertas registradas.</td></tr>';
    return;
  }

  const statusLabels = {
    nueva: "Nueva",
    confirmada: "Confirmada",
    falsa_alarma: "Falsa alarma",
  };
  alertList.innerHTML = alerts.map((alert) => {
    const clase = String(alert.clase ?? "").toLocaleLowerCase("es");
    const isSmoke = clase.includes("smoke") || clase.includes("humo");
    const isFire = clase.includes("fire") || clase.includes("fuego");
    const eventLabel = isSmoke ? "Humo" : isFire ? "Fuego" : escapeHtml(alert.clase);
    const statusLabel = statusLabels[alert.estado] ?? escapeHtml(alert.estado);
    const confidence = Number.isFinite(Number(alert.confianza))
      ? `${Math.round(Number(alert.confianza) * 100)}%`
      : "—";
    const evidenceUrl = typeof alert.imagen_url === "string"
      && alert.imagen_url.startsWith("/")
      && !alert.imagen_url.startsWith("//")
      ? `<a class="evidence-link" href="${escapeHtml(alert.imagen_url)}" target="_blank" rel="noreferrer">Ver imagen</a>`
      : "—";
    const actions = alert.estado === "nueva"
      ? `<button type="button" data-action="confirm" data-id="${alert.id}">Confirmar</button>
         <button type="button" data-action="false-alarm" data-id="${alert.id}">Falsa alarma</button>`
      : "";

    return `<tr>
      <td><span class="event-name"><span class="event-icon ${isSmoke ? "smoke" : ""}">${isSmoke ? "≋" : "△"}</span>${eventLabel}</span></td>
      <td>${escapeHtml(alert.camara_nombre ?? `Cámara ${alert.camara_id}`)}</td>
      <td>${confidence}</td>
      <td>${escapeHtml(formatDate(alert.fecha))}</td>
      <td><span class="alert-state ${escapeHtml(alert.estado)}">${statusLabel}</span></td>
      <td>${evidenceUrl}</td>
      <td><div class="row-actions">${actions}</div></td>
    </tr>`;
  }).join("");
}

function renderSummary(summary) {
  const cameraSummary = summary.camaras;
  document.querySelector("#active-cameras").textContent = cameraSummary.activas ?? 0;
  document.querySelector("#total-cameras").textContent = `de ${cameraSummary.total ?? 0} cámaras`;
  document.querySelector("#detecting-cameras").textContent = cameraSummary.alerta ?? 0;
  document.querySelector("#offline-cameras").textContent = cameraSummary.sin_conexion ?? 0;
  renderAlerts(summary.ultimas_alertas ?? [], summary.alertas.nueva ?? 0);
}

async function refreshDashboard() {
  if (refreshInProgress || document.hidden) return;
  refreshInProgress = true;
  const refreshButton = document.querySelector("#refresh-button");
  refreshButton.classList.add("is-refreshing");

  try {
    const [cameraList, statuses, summary] = await Promise.all([
      api("/camaras"),
      api("/camaras/estado"),
      api("/monitoreo/resumen"),
    ]);

    cameras = cameraList;
    cameraStates.clear();
    statuses.forEach((status) => cameraStates.set(status.camara_id, status));
    renderSummary(summary);
    renderCameraCards();
    setConnection(true);
    document.querySelector("#last-updated").textContent = `Actualizado ${new Intl.DateTimeFormat("es-MX", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date())}`;
  } catch (error) {
    setConnection(false);
    console.error("No se pudo actualizar el panel:", error);
    document.querySelector("#last-updated").textContent = "No se pudieron cargar los datos";
  } finally {
    refreshInProgress = false;
    refreshButton.classList.remove("is-refreshing");
  }
}

document.querySelector("#refresh-button").addEventListener("click", refreshDashboard);
document.querySelector("#open-camera-form").addEventListener("click", () => {
  document.querySelector("#camera-form-error").textContent = "";
  cameraDialog.showModal();
});
document.querySelector("#close-camera-form").addEventListener("click", () => cameraDialog.close());
document.querySelector("#cancel-camera-form").addEventListener("click", () => cameraDialog.close());
cameraSearch.addEventListener("input", renderCameraCards);
cameraFilter.addEventListener("change", renderCameraCards);

cameraForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(cameraForm);
  const payload = {
    nombre: String(formData.get("nombre")).trim(),
    url: String(formData.get("url")).trim(),
    activa: true,
    conf_humo: Number(formData.get("conf_humo")),
    conf_fuego: Number(formData.get("conf_fuego")),
  };
  const submitButton = cameraForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  document.querySelector("#camera-form-error").textContent = "";

  try {
    await api("/camaras", { method: "POST", body: JSON.stringify(payload) });
    cameraDialog.close();
    cameraForm.reset();
    cameraForm.elements.namedItem("conf_humo").value = "0.3";
    cameraForm.elements.namedItem("conf_fuego").value = "0.3";
    showToast("Cámara agregada correctamente.");
    await refreshDashboard();
  } catch (error) {
    document.querySelector("#camera-form-error").textContent = `No se pudo guardar: ${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
});

cameraGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  if (button.dataset.action === "delete") {
    const camera = cameras.find((item) => item.id === Number(button.dataset.id));
    if (!camera || !window.confirm(`¿Eliminar la cámara "${camera.nombre}" y sus alertas?`)) return;

    button.dataset.pending = "true";
    button.disabled = true;
    try {
      await api(`/camaras/${camera.id}`, { method: "DELETE" });
      showToast(`Cámara "${camera.nombre}" eliminada.`);
      await refreshDashboard();
    } catch (error) {
      button.dataset.pending = "false";
      button.disabled = false;
      showToast(`No se pudo eliminar la cámara: ${error.message}`);
    }
    return;
  }

  if (button.dataset.action !== "toggle") return;
  button.dataset.pending = "true";
  button.disabled = true;
  try {
    await api(`/camaras/${button.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ activa: button.dataset.active !== "true" }),
    });
    button.dataset.pending = "false";
    showToast(button.dataset.active === "true" ? "Cámara pausada." : "Cámara activada.");
    await refreshDashboard();
  } catch (error) {
    button.dataset.pending = "false";
    button.disabled = false;
    showToast(`No se pudo actualizar la cámara: ${error.message}`);
  }
});

cameraGrid.addEventListener("loadeddata", (event) => {
  if (!(event.target instanceof HTMLVideoElement)) return;
  event.target.dataset.receivedFrame = "true";
  event.target.hidden = false;
  const placeholder = event.target.closest(".camera-preview").querySelector(".preview-placeholder");
  placeholder.hidden = true;
}, true);

cameraGrid.addEventListener("error", (event) => {
  if (!(event.target instanceof HTMLVideoElement)) return;
  const video = event.target;
  stopStream(video);
  video.hidden = true;
  const placeholder = video.closest(".camera-preview").querySelector(".preview-placeholder");
  placeholder.hidden = false;
  placeholder.textContent = "Video no disponible";
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
    button.disabled = false;
    showToast(`No se pudo actualizar la alerta: ${error.message}`);
  }
});

refreshDashboard();
setInterval(refreshDashboard, 3000);
