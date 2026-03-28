const configuredBaseUrl =
    (window.WEBHOOK_CONSOLE_CONFIG && window.WEBHOOK_CONSOLE_CONFIG.apiBaseUrl) || "";
const savedBaseUrl = localStorage.getItem("webhook-console-api-base-url") || configuredBaseUrl;

const state = {
    apiBaseUrl: savedBaseUrl,
    selectedEventId: null,
    events: []
};

const sampleWebhook = {
    type: "order.paid",
    providerEventId: "evt_shopify_120045",
    correlationId: "corr-demo-001",
    simulateFailure: true,
    order: {
        orderId: "SO-240501",
        currency: "USD",
        amount: 245.5,
        customerEmail: "ops-demo@example.com"
    }
};

function byId(id) {
    return document.getElementById(id);
}

function normalizedBaseUrl() {
    return (state.apiBaseUrl || "").replace(/\/$/, "");
}

function renderEvents() {
    const list = byId("eventList");
    const count = byId("eventCount");
    list.innerHTML = "";
    count.textContent = `${state.events.length} loaded`;

    if (state.events.length === 0) {
        list.innerHTML = '<p class="empty">No events loaded yet.</p>';
        return;
    }

    state.events.forEach((event) => {
        const row = document.createElement("article");
        row.className = "event-row";
        row.innerHTML = `
            <div class="event-title">${event.eventType || "unknown"} <span class="pill">${event.status}</span></div>
            <div class="event-meta">${event.source} | ${event.receivedAt} | replayed ${event.replayCount || 0} times</div>
            <button class="secondary" data-event-id="${event.eventId}">Inspect</button>
        `;
        row.querySelector("button").addEventListener("click", () => loadEvent(event.eventId));
        list.appendChild(row);
    });
}

function renderDetail(payload) {
    const event = payload.event;
    state.selectedEventId = event.eventId;

    byId("detailStatus").textContent = event.status || "UNKNOWN";
    byId("detailEventId").textContent = event.eventId || "-";
    byId("detailSource").textContent = event.source || "-";
    byId("detailType").textContent = event.eventType || "-";
    byId("detailReplayCount").textContent = String(event.replayCount || 0);
    byId("payloadView").textContent = JSON.stringify(payload.payload || {}, null, 2);
}

async function apiFetch(path, options = {}) {
    const baseUrl = normalizedBaseUrl();
    if (!baseUrl) {
        throw new Error("Set an API base URL first.");
    }

    const response = await fetch(`${baseUrl}${path}`, {
        headers: {
            "content-type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.message || `Request failed with ${response.status}`);
    }
    return data;
}

async function loadEvents() {
    try {
        const status = byId("statusFilter").value.trim();
        const source = byId("sourceFilter").value.trim();
        const params = new URLSearchParams();
        if (status) {
            params.set("status", status);
        }
        if (source) {
            params.set("source", source);
        }

        const suffix = params.toString() ? `?${params.toString()}` : "";
        const data = await apiFetch(`/events${suffix}`);
        state.events = data.items || [];
        renderEvents();
    } catch (error) {
        alert(error.message);
    }
}

async function loadEvent(eventId) {
    try {
        const data = await apiFetch(`/events/${eventId}`);
        renderDetail(data);
    } catch (error) {
        alert(error.message);
    }
}

async function ingestSampleEvent() {
    try {
        await apiFetch("/webhooks/shopify", {
            method: "POST",
            body: JSON.stringify(sampleWebhook)
        });
        await loadEvents();
    } catch (error) {
        alert(error.message);
    }
}

async function replaySelectedEvent() {
    if (!state.selectedEventId) {
        alert("Select an event first.");
        return;
    }

    try {
        const reason = byId("replayReason").value.trim() || "manual replay requested";
        await apiFetch(`/events/${state.selectedEventId}/replay`, {
            method: "POST",
            body: JSON.stringify({ reason })
        });
        await loadEvent(state.selectedEventId);
        await loadEvents();
    } catch (error) {
        alert(error.message);
    }
}

function saveBaseUrl() {
    state.apiBaseUrl = byId("apiBaseUrl").value.trim();
    localStorage.setItem("webhook-console-api-base-url", state.apiBaseUrl);
}

function boot() {
    byId("apiBaseUrl").value = state.apiBaseUrl;
    byId("saveBaseUrl").addEventListener("click", saveBaseUrl);
    byId("refreshEvents").addEventListener("click", loadEvents);
    byId("ingestSample").addEventListener("click", ingestSampleEvent);
    byId("applyFilters").addEventListener("click", loadEvents);
    byId("replayEvent").addEventListener("click", replaySelectedEvent);
}

boot();
