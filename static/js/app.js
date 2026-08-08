const root = document.documentElement;
const storageKey = "skraft-theme";
const sessionStorageKey = "skraft-session-id";
let sessionHeartbeatTimer = null;

function getSessionId() {
  const existing = window.sessionStorage.getItem(sessionStorageKey);
  if (existing) {
    return existing;
  }

  const sessionId = window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  window.sessionStorage.setItem(sessionStorageKey, sessionId);
  return sessionId;
}

function formatMetricValue(node, value) {
  const format = node.dataset.format;

  if (format === "percent") {
    return `${value}%`;
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
  Object.entries(data).forEach(([key, value]) => {
    document.querySelectorAll(`[data-metric="${key}"]`).forEach((node) => {
      node.textContent = formatMetricValue(node, value);
    });

    document.querySelectorAll(`[data-meter="${key}"]`).forEach((node) => {
      node.style.width = `${value}%`;
    });
  });
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

  refreshMetrics();
  window.setInterval(refreshMetrics, 3000);
});
