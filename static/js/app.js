const root = document.documentElement;
const storageKey = "skraft-theme";
const sessionStorageKey = "skraft-session-id";
let sessionHeartbeatTimer = null;
let historyRefreshTimer = null;
let alertsRefreshTimer = null;
let selectedHistoryRange = "24h";

function cryptoRandomUuidFallback() {
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);

  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`;
}

function getSessionId() {
  const existing = window.sessionStorage.getItem(sessionStorageKey);
  if (existing) {
    return existing;
  }

  const sessionId = window.crypto?.randomUUID?.() ?? cryptoRandomUuidFallback();
  window.sessionStorage.setItem(sessionStorageKey, sessionId);
  return sessionId;
}

function getNestedValue(data, path) {
  return path.split(".").reduce((current, segment) => current?.[segment], data);
}

function formatMetricValue(node, value) {
  const format = node.dataset.format;
  if (value === null || value === undefined) {
    return "N/A";
  }

  if (format === "percent") {
    return `${value}%`;
  }

  if (format === "temp") {
    return `${value}\u00B0C`;
  }

  return value;
}

function applyTheme(theme) {
  root.setAttribute("data-theme", theme);
  window.localStorage.setItem(storageKey, theme);
}

function initTheme() {
  const saved = window.localStorage.getItem(storageKey);
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
    return;
  }

  const preferredDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(preferredDark ? "dark" : "light");
}

function initTabs() {
  const tabs = document.querySelectorAll("[data-tab-target]");
  const panels = document.querySelectorAll("[data-tab-panel]");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((item) => item.classList.remove("is-active"));
      panels.forEach((panel) => panel.classList.remove("is-active"));

      tab.classList.add("is-active");
      document
        .querySelector(`[data-tab-panel="${tab.dataset.tabTarget}"]`)
        ?.classList.add("is-active");
    });
  });
}

function updateMetrics(data) {
  document.querySelectorAll("[data-metric]").forEach((node) => {
    const nextValue = getNestedValue(data, node.dataset.metric);
    node.textContent = formatMetricValue(node, nextValue);
  });

  document.querySelectorAll("[data-meter]").forEach((node) => {
    const nextValue = getNestedValue(data, node.dataset.meter);
    node.style.width = `${nextValue ?? 0}%`;
  });
}

function buildSparklinePath(values) {
  const cleaned = values.map((value) => Number(value) || 0);
  if (!cleaned.length) {
    return "";
  }

  const max = Math.max(...cleaned);
  const min = Math.min(...cleaned);
  const range = max - min || 1;
  const width = 100;
  const height = 30;
  const padding = 3;

  return cleaned
    .map((value, index) => {
      const x = cleaned.length === 1 ? width / 2 : (index / (cleaned.length - 1)) * width;
      const normalized = (value - min) / range;
      const y = height - padding - normalized * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function renderSparkline(svg, values) {
  const pathData = buildSparklinePath(values);
  svg.replaceChildren();

  if (!pathData) {
    return;
  }

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathData);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", svg.dataset.historyColor || "#98d84d");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
}

function renderHistoryPanel(data) {
  const samples = data.samples || [];
  selectedHistoryRange = data.range || selectedHistoryRange;
  const historyPanel = document.querySelector('[data-tab-panel="history"]');
  const chartNodes = historyPanel?.querySelectorAll("[data-history-chart]") || [];
  const rangeLabel = historyPanel?.querySelector("[data-history-range-label]");
  const rangeButtons = historyPanel?.querySelectorAll("[data-history-range]") || [];

  if (rangeLabel) {
    rangeLabel.textContent = selectedHistoryRange;
  }

  rangeButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.historyRange === selectedHistoryRange);
  });

  chartNodes.forEach((svg) => {
    const seriesKey = svg.dataset.historyChart;
    const values = samples.map((sample) => getNestedValue(sample, seriesKey));
    renderSparkline(svg, values);
  });

  const historyList = historyPanel?.querySelector(".inventory-list");
  if (historyList) {
    historyList.innerHTML = samples.length
      ? samples
          .map(
            (sample) => `
              <div class="inventory-row">
                <dt>${sample.captured_at}</dt>
                <dd>CPU ${sample.cpu_percent}% / Memory ${sample.memory_percent}% / Storage ${sample.storage_percent}%</dd>
              </div>
            `,
          )
          .join("")
      : `
        <div class="inventory-row">
          <dt>No history yet</dt>
          <dd>N/A</dd>
        </div>
      `;
  }
}

function renderAlertPanel(data) {
  const alerts = data.alerts || [];
  const alertEvents = data.alert_events || [];
  const alertPanel = document.querySelector('[data-tab-panel="alerts"]');
  const alertList = alertPanel?.querySelector(".inventory-list");

  if (alertList) {
    alertList.innerHTML = alerts.length
      ? alerts
              .map(
                (alert) => `
              <div class="inventory-row">
                <dt>${alert.title}</dt>
                <dd>
                  <div>${alert.message}</div>
                  <div class="row-actions">
                    <span class="alert-state">${alert.acknowledged ? "Acknowledged" : "Unacknowledged"}</span>
                    <button
                      class="history-filter"
                      type="button"
                      data-alert-acknowledge
                      data-alert-fingerprint="${alert.fingerprint}"
                      ${alert.acknowledged ? "disabled" : ""}
                    >
                      Acknowledge
                    </button>
                  </div>
                </dd>
              </div>
            `,
              )
          .join("")
      : `
        <div class="inventory-row">
          <dt>All clear</dt>
          <dd>No active alerts</dd>
        </div>
      `;
  }

  if (!alertPanel) {
    return;
  }

  let log = alertPanel.querySelector("[data-alert-log]");
  if (!log) {
    log = document.createElement("div");
    log.dataset.alertLog = "true";
    log.style.marginTop = "22px";
    log.innerHTML = `
      <p class="eyebrow">Alert log</p>
      <dl class="inventory-list" data-alert-log-list></dl>
    `;
    alertPanel.querySelector(".inventory-card")?.appendChild(log);
  }

  const logList = log.querySelector("[data-alert-log-list]");
  if (logList) {
    logList.innerHTML = alertEvents.length
      ? alertEvents
          .map(
            (event) => `
              <div class="inventory-row">
                <dt>${event.title}</dt>
                <dd>${event.severity} / ${event.occurrences} times / ${
                  event.active ? "active" : "resolved"
                }</dd>
              </div>
            `,
          )
          .join("")
      : `
        <div class="inventory-row">
          <dt>No alert events yet</dt>
          <dd>N/A</dd>
        </div>
      `;
  }
}

async function refreshMetrics() {
  try {
    const response = await fetch("/api/metrics/", {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!response.ok) {
      return;
    }

    const data = await response.json();
    updateMetrics(data);
  } catch (error) {
    console.error("Unable to refresh metrics", error);
  }
}

async function refreshHistory() {
  try {
    const response = await fetch(`/api/history/?range=${encodeURIComponent(selectedHistoryRange)}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!response.ok) {
      return;
    }

    renderHistoryPanel(await response.json());
  } catch (error) {
    console.error("Unable to refresh history", error);
  }
}

async function refreshAlerts() {
  try {
    const response = await fetch("/api/alerts/", {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!response.ok) {
      return;
    }

    renderAlertPanel(await response.json());
  } catch (error) {
    console.error("Unable to refresh alerts", error);
  }
}

async function acknowledgeAlert(fingerprint) {
  try {
    const response = await fetch("/api/alerts/acknowledge/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fingerprint }),
    });

    if (!response.ok) {
      return;
    }

    refreshAlerts();
  } catch (error) {
    console.error("Unable to acknowledge alert", error);
  }
}

async function postSessionState(url) {
  const sessionId = getSessionId();
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId }),
      keepalive: true,
    });
  } catch (error) {
    console.error("Unable to sync session state", error);
  }
}

function initSessionLifecycle() {
  postSessionState("/api/session/heartbeat/");
  sessionHeartbeatTimer = window.setInterval(() => {
    postSessionState("/api/session/heartbeat/");
  }, 5000);

  const closePayload = JSON.stringify({ sessionId: getSessionId() });
  const closeUrl = `${window.location.origin}/api/session/close/`;

  const sendClose = () => {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(closeUrl, new Blob([closePayload], { type: "application/json" }));
      return;
    }
    postSessionState("/api/session/close/");
  };

  window.addEventListener("pagehide", sendClose);
  window.addEventListener("beforeunload", sendClose);
}

async function quitApp() {
  if (sessionHeartbeatTimer) {
    window.clearInterval(sessionHeartbeatTimer);
  }

  try {
    await fetch("/api/quit/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      keepalive: true,
    });
  } catch (error) {
    console.error("Unable to quit app cleanly", error);
  }

  window.setTimeout(() => {
    window.close();
  }, 300);
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initTabs();
  initSessionLifecycle();

  document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });

  document.querySelector("[data-quit-app]")?.addEventListener("click", quitApp);

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const historyButton = target.closest("[data-history-range]");
    if (historyButton instanceof HTMLElement) {
      selectedHistoryRange = historyButton.dataset.historyRange || selectedHistoryRange;
      refreshHistory();
      return;
    }

    const ackButton = target.closest("[data-alert-acknowledge]");
    if (ackButton instanceof HTMLElement) {
      const fingerprint = ackButton.dataset.alertFingerprint;
      if (fingerprint) {
        acknowledgeAlert(fingerprint);
      }
    }
  });

  refreshMetrics();
  window.setInterval(refreshMetrics, 3000);
  refreshHistory();
  historyRefreshTimer = window.setInterval(refreshHistory, 15000);
  refreshAlerts();
  alertsRefreshTimer = window.setInterval(refreshAlerts, 15000);
});
