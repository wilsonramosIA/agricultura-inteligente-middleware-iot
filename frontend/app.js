const state = { telemetry: [], alerts: [], sensors: [], loading: false };
const apiKeyStorage = "terrapulse-api-key";
const defaultApiKey = "grupo8-demo-key";

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const apiKey = () => localStorage.getItem(apiKeyStorage) || defaultApiKey;
const apiFetch = async (path, options = {}) => {
  const response = await fetch(path, { ...options, headers: { "X-API-Key": apiKey(), ...(options.headers || {}) } });
  if (!response.ok) { const detail = await response.json().catch(() => ({})); throw new Error(detail.detail || `Erro ${response.status}`); }
  return response.status === 204 ? null : response.json();
};
const formatTime = (dateValue) => { if (!dateValue) return "—"; const date = new Date(dateValue); if (Number.isNaN(date.getTime())) return "—"; return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); };
const relativeTime = (dateValue) => { if (!dateValue) return "sem dados"; const seconds = Math.max(0, Math.floor((Date.now() - new Date(dateValue).getTime()) / 1000)); if (seconds < 60) return "agora"; if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`; return `há ${Math.floor(seconds / 3600)} h`; };
const metricLabel = (metric) => ({ soil_moisture: "Umidade do solo", temperature: "Temperatura", humidity: "Umidade do ar", smoke: "Fumaça", sensor_offline: "Sensor offline" }[metric] || metric);
const metricUnit = (metric) => ({ soil_moisture: "%", temperature: "°C", humidity: "%", smoke: "ppm" }[metric] || "");
const showToast = (message, error = false) => { const toast = $("#toast"); $("#toastMessage").textContent = message; $("#toastIcon").textContent = error ? "!" : "✓"; toast.classList.toggle("error", error); toast.classList.add("show"); clearTimeout(showToast.timer); showToast.timer = setTimeout(() => toast.classList.remove("show"), 3600); };

async function loadDashboard(showFeedback = false) {
  if (state.loading) return;
  state.loading = true;
  try {
    const [telemetry, alerts, heartbeat] = await Promise.all([apiFetch("/api/v1/telemetry?limit=100"), apiFetch("/api/v1/alerts?only_open=true"), apiFetch("/api/v1/sensor-heartbeats")]);
    state.telemetry = telemetry || []; state.alerts = alerts || []; state.sensors = heartbeat?.sensors || [];
    renderAll();
    $("#connectionLabel").textContent = "Dados ao vivo";
    $("#gatewayLatency").textContent = `última leitura ${formatTime(state.telemetry[0]?.received_at)}`;
    if (showFeedback) showToast("Painel atualizado");
  } catch (error) {
    $("#connectionLabel").textContent = "Falha na conexão";
    $("#gatewayLatency").textContent = "verifique a API key";
    showToast(error.message, true);
  } finally { state.loading = false; }
}

function renderAll() { renderMetrics(); renderChart(); renderAlerts(); renderSensors(); renderTelemetry(); }
function renderMetrics() {
  const online = state.sensors.filter((sensor) => sensor.status === "online").length;
  const offline = state.sensors.filter((sensor) => sensor.status !== "online").length;
  const moisture = state.telemetry.filter((row) => row.metric === "soil_moisture").map((row) => Number(row.value));
  const average = moisture.length ? moisture.reduce((sum, value) => sum + value, 0) / moisture.length : null;
  $("#activeSensors").textContent = state.sensors.length ? `${online}/${state.sensors.length}` : "—";
  $("#sensorTrend").textContent = state.sensors.length ? `${Math.round((online / state.sensors.length) * 100)}%` : "—";
  $("#openAlerts").textContent = state.alerts.length;
  $("#navAlertCount").textContent = state.alerts.length;
  $("#alertHeadingCount").textContent = state.alerts.length;
  const critical = state.alerts.filter((alert) => alert.severity === "critical").length;
  $("#criticalAlerts").textContent = critical ? `${critical} crítico${critical > 1 ? "s" : ""}` : "nenhum crítico";
  $("#averageMoisture").textContent = average == null ? "—" : `${average.toFixed(1)}%`;
  $("#moistureState").textContent = average == null ? "aguardando dados" : average <= 20 ? "abaixo do ideal" : "faixa saudável";
  $("#lastUpdate").textContent = state.telemetry[0] ? formatTime(state.telemetry[0].received_at) : "—";
  $("#sensorSummaryOnline").textContent = online; $("#sensorSummaryOffline").textContent = offline;
  $("#sensorBarOnline").style.width = state.sensors.length ? `${(online / state.sensors.length) * 100}%` : "0%";
}

function renderChart() {
  const selected = $("#metricSelect").value;
  const rows = state.telemetry.filter((row) => row.metric === selected).slice(0, 24).reverse();
  $("#chartMetricLabel").textContent = metricLabel(selected);
  const latest = rows[rows.length - 1]; $("#chartCurrent").textContent = latest ? `${Number(latest.value).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${latest.unit || metricUnit(selected)}` : "sem dados";
  $("#chartEmpty").style.display = rows.length ? "none" : "grid";
  const svg = $("#trendChart"); if (!rows.length) { svg.innerHTML = ""; return; }
  const values = rows.map((row) => Number(row.value)); const min = Math.min(...values); const max = Math.max(...values); const padding = Math.max((max - min) * .22, 1); const low = min - padding; const high = max + padding; const width = 760; const height = 260; const xStep = rows.length === 1 ? width : width / (rows.length - 1);
  const points = rows.map((row, index) => { const x = index * xStep; const y = height - ((Number(row.value) - low) / (high - low)) * height; return { x, y, value: row.value }; });
  const path = points.map((point, i) => `${i ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" "); const area = `${path} L ${width},${height} L 0,${height} Z`;
  svg.innerHTML = `<defs><linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#48bd8c" stop-opacity=".22"/><stop offset="100%" stop-color="#48bd8c" stop-opacity="0"/></linearGradient></defs><path class="chart-area" d="${area}"/><path class="chart-path" d="${path}"/>${points.map((point) => `<circle class="chart-point" cx="${point.x}" cy="${point.y}" r="${points.length > 20 ? 2.5 : 4}"/>`).join("")}`;
}

function renderAlerts() {
  const list = $("#alertList");
  if (!state.alerts.length) { list.innerHTML = `<div class="empty-state"><div><div style="font-size:24px;color:#62bd8d;margin-bottom:7px">✓</div><b style="display:block;color:#60736a;font-size:11px">Tudo tranquilo por aqui</b><span style="display:block;margin-top:5px">Nenhum alerta aberto no momento.</span></div></div>`; return; }
  list.innerHTML = state.alerts.slice(0, 6).map((alert) => `<div class="alert-item"><div class="alert-severity ${alert.severity === "critical" ? "critical" : ""}">${alert.severity === "critical" ? "!" : "△"}</div><div class="alert-body"><strong>${escapeHtml(alert.message)}</strong><p>${escapeHtml(alert.sensor_id)} · ${escapeHtml(alert.location || "campo")}</p><div class="alert-meta"><span>${relativeTime(alert.created_at)}</span><i></i><span class="${alert.severity === "critical" ? "orange-text" : ""}">${alert.severity === "critical" ? "Crítico" : "Atenção"}</span></div></div><button class="ack-button" data-ack="${alert.id}" type="button">Reconhecer</button></div>`).join("");
  list.querySelectorAll("[data-ack]").forEach((button) => button.addEventListener("click", () => acknowledgeAlert(button.dataset.ack, button)));
}

async function acknowledgeAlert(id, button) { button.disabled = true; button.textContent = "..."; try { await apiFetch(`/api/v1/alerts/${id}/acknowledge`, { method: "PATCH" }); state.alerts = state.alerts.filter((alert) => String(alert.id) !== String(id)); renderAll(); showToast("Alerta reconhecido"); } catch (error) { button.disabled = false; button.textContent = "Reconhecer"; showToast(error.message, true); } }
function renderSensors() { const list = $("#sensorList"); if (!state.sensors.length) { list.innerHTML = `<div class="empty-inline">Nenhum heartbeat recebido ainda.</div>`; return; } list.innerHTML = state.sensors.map((sensor) => `<div class="sensor-row"><span class="sensor-status ${sensor.status === "online" ? "" : "offline"}"></span><div class="sensor-copy"><b>${escapeHtml(sensor.sensor_id)}</b><small>${sensor.status === "online" ? "Operacional" : "Sem comunicação"}</small></div><span class="sensor-time">${relativeTime(sensor.last_seen)}</span></div>`).join(""); }
function renderTelemetry() { const body = $("#telemetryBody"); if (!state.telemetry.length) { body.innerHTML = `<tr><td colspan="4" class="table-empty">Nenhuma leitura registrada.</td></tr>`; return; } body.innerHTML = state.telemetry.slice(0, 7).map((row) => `<tr><td>${escapeHtml(row.sensor_id)}</td><td><span class="metric-tag">${escapeHtml(metricLabel(row.metric))}</span></td><td>${Number(row.value).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${escapeHtml(row.unit)}</td><td>${relativeTime(row.received_at)}</td></tr>`).join(""); }

function openModal() { $("#readingModal").hidden = false; setTimeout(() => $("[name=sensor_id]").focus(), 20); }
function closeModal() { $("#readingModal").hidden = true; $("#readingForm").reset(); }
async function submitReading(event) { event.preventDefault(); const form = new FormData(event.currentTarget); const submit = $("#submitReading"); submit.disabled = true; submit.innerHTML = "Enviando..."; try { await apiFetch("/api/v1/telemetry", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sensor_id: form.get("sensor_id"), location: form.get("location"), metric: form.get("metric"), value: Number(form.get("value")), unit: form.get("unit") }) }); closeModal(); await loadDashboard(); showToast("Leitura registrada com sucesso"); } catch (error) { showToast(error.message, true); } finally { submit.disabled = false; submit.innerHTML = `Enviar leitura <span>→</span>`; } }

$("#newReadingButton").addEventListener("click", openModal); $("#closeModal").addEventListener("click", closeModal); $("#cancelModal").addEventListener("click", closeModal); $("#readingModal").addEventListener("click", (event) => { if (event.target === $("#readingModal")) closeModal(); }); $("#readingForm").addEventListener("submit", submitReading); $("#metricSelect").addEventListener("change", renderChart); $("#refreshButton").addEventListener("click", () => loadDashboard(true)); $("#tableRefresh").addEventListener("click", () => loadDashboard(true)); $("#mobileMenu").addEventListener("click", () => $("#sidebar").classList.toggle("open")); document.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", () => $("#sidebar").classList.remove("open")));
$("#apiKeyButton").addEventListener("click", () => { const value = window.prompt("Informe a X-API-Key configurada no gateway:", apiKey()); if (value?.trim()) { localStorage.setItem(apiKeyStorage, value.trim()); loadDashboard(true); } });
document.querySelectorAll(".period-button").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll(".period-button").forEach((item) => item.classList.remove("active")); button.classList.add("active"); showToast("O período de 7 dias estará disponível com histórico consolidado.", button.textContent === "7 dias"); }));
loadDashboard(); setInterval(() => loadDashboard(), 30000);
