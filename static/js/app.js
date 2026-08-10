const root = document.documentElement;
const storageKey = "skraft-theme";
const sessionStorageKey = "skraft-session-id";
const shutdownOnCloseKey = "skraft-shutdown-on-close";
let selectedHistoryRange = "24h";
const pollers = {};
let connectionBannerDismissed = false;

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

function getConnectionBanner() {
  return document.querySelector("[data-connection-banner]");
}

function setConnectionState(online, message) {
  const banner = getConnectionBanner();
  if (!banner) {
    return;
  }

  const title = banner.querySelector("[data-connection-title]");
  const body = banner.querySelector("[data-connection-message]");

  if (online) {
    banner.hidden = true;
    banner.dataset.state = "online";
    if (!connectionBannerDismissed) {
      console.info("Local connection restored.");
      connectionBannerDismissed = true;
    }
    return;
  }

  banner.hidden = false;
  banner.dataset.state = "offline";
  if (title) {
    title.textContent = "Offline";
  }
  if (body) {
    body.textContent = message || "Lost connection to the local app. Retrying...";
  }
}

function markConnectionFailure(message) {
  setConnectionState(false, message);
}

function markConnectionRecovered() {
  setConnectionState(true);
}

function getShutdownOnClosePreference() {
  return window.localStorage.getItem(shutdownOnCloseKey) === "1";
}

function setShutdownOnClosePreference(enabled) {
  window.localStorage.setItem(shutdownOnCloseKey, enabled ? "1" : "0");
}

function registerPoller(name, task, baseDelay, maxDelay) {
  pollers[name] = {
    task,
    baseDelay,
    maxDelay,
    delay: baseDelay,
    timer: null,
    running: false,
  };
}

function clearPoller(name) {
  const poller = pollers[name];
  if (poller?.timer) {
    window.clearTimeout(poller.timer);
    poller.timer = null;
  }
}

function schedulePoller(name, delay) {
  const poller = pollers[name];
  if (!poller) {
    return;
  }

  clearPoller(name);
  poller.timer = window.setTimeout(() => {
    void runPoller(name);
  }, delay);
}

async function runPoller(name) {
  const poller = pollers[name];
  if (!poller || poller.running) {
    return;
  }

  poller.running = true;
  let ok = false;
  try {
    ok = await poller.task();
  } finally {
    poller.running = false;
  }

  if (ok) {
    poller.delay = poller.baseDelay;
    markConnectionRecovered();
  } else {
    poller.delay = Math.min(Math.max(poller.delay * 1.8, poller.baseDelay), poller.maxDelay);
    markConnectionFailure("Lost connection to the local app. Retrying...");
  }

  schedulePoller(name, poller.delay);
}

function startPoller(name, immediate = false) {
  const poller = pollers[name];
  if (!poller) {
    return;
  }

  clearPoller(name);
  poller.delay = poller.baseDelay;
  schedulePoller(name, immediate ? 0 : poller.baseDelay);
}

function startAllPollers(immediate = false) {
  Object.keys(pollers).forEach((name) => startPoller(name, immediate));
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
      return false;
    }

    const data = await response.json();
    updateMetrics(data);
    return true;
  } catch (error) {
    return false;
  }
}

async function refreshHistory() {
  try {
    const response = await fetch(`/api/history/?range=${encodeURIComponent(selectedHistoryRange)}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!response.ok) {
      return false;
    }

    renderHistoryPanel(await response.json());
    return true;
  } catch (error) {
    return false;
  }
}

async function refreshAlerts() {
  try {
    const response = await fetch("/api/alerts/", {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (!response.ok) {
      return false;
    }

    renderAlertPanel(await response.json());
    return true;
  } catch (error) {
    return false;
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

    void refreshAlerts();
  } catch (error) {
    markConnectionFailure("Lost connection while acknowledging an alert. Retrying...");
  }
}

async function postSessionState(url) {
  const sessionId = getSessionId();
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId }),
      keepalive: true,
    });

    return response.ok;
  } catch (error) {
    return false;
  }
}

function getQuitModal() {
  return document.querySelector("[data-quit-modal]");
}

function openQuitModal() {
  const modal = getQuitModal();
  const checkbox = modal?.querySelector("[data-shutdown-on-close]");
  if (!modal || !checkbox) {
    return;
  }

  checkbox.checked = getShutdownOnClosePreference();
  modal.hidden = false;
  modal.dataset.open = "true";
  checkbox.focus();
}

function closeQuitModal() {
  const modal = getQuitModal();
  if (!modal) {
    return;
  }

  modal.hidden = true;
  delete modal.dataset.open;
}

async function sendServerQuit() {
  Object.keys(pollers).forEach((name) => clearPoller(name));

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
}

function initSessionLifecycle() {
  registerPoller("session", () => postSessionState("/api/session/heartbeat/"), 5000, 60000);
  startPoller("session", true);

  const closePayload = JSON.stringify({ sessionId: getSessionId() });
  const closeUrl = `${window.location.origin}/api/session/close/`;
  const quitPayload = "{}";
  const quitUrl = `${window.location.origin}/api/quit/`;

  const sendClose = () => {
    if (getShutdownOnClosePreference()) {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(quitUrl, new Blob([quitPayload], { type: "application/json" }));
        return;
      }
      void sendServerQuit();
      return;
    }

    if (navigator.sendBeacon) {
      navigator.sendBeacon(closeUrl, new Blob([closePayload], { type: "application/json" }));
      return;
    }
    postSessionState("/api/session/close/");
  };

  window.addEventListener("pagehide", sendClose);
  window.addEventListener("beforeunload", (event) => {
    if (getShutdownOnClosePreference()) {
      return;
    }

    event.preventDefault();
    event.returnValue =
      "Closing this browser keeps the local server running. Use Quit server if you want to stop it.";
    return event.returnValue;
  });
}

async function quitApp() {
  const modal = getQuitModal();
  const checkbox = modal?.querySelector("[data-shutdown-on-close]");
  if (checkbox) {
    setShutdownOnClosePreference(checkbox.checked);
  }

  closeQuitModal();
  await sendServerQuit();
  window.setTimeout(() => {
    window.close();
  }, 300);
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initTabs();
  initSessionLifecycle();
  registerPoller("metrics", refreshMetrics, 3000, 30000);
  registerPoller("history", refreshHistory, 15000, 60000);
  registerPoller("alerts", refreshAlerts, 15000, 60000);

  document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });

  document.querySelector("[data-quit-app]")?.addEventListener("click", openQuitModal);
  document.querySelector("[data-quit-confirm]")?.addEventListener("click", quitApp);
  document.querySelector("[data-quit-cancel]")?.addEventListener("click", closeQuitModal);

  const quitModal = getQuitModal();
  quitModal?.addEventListener("click", (event) => {
    if (event.target === quitModal) {
      closeQuitModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && quitModal && !quitModal.hidden) {
      closeQuitModal();
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const historyButton = target.closest("[data-history-range]");
    if (historyButton instanceof HTMLElement) {
      selectedHistoryRange = historyButton.dataset.historyRange || selectedHistoryRange;
      void refreshHistory();
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

  window.addEventListener("online", () => startAllPollers(true));
  startAllPollers(true);
});
