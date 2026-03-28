const configuredBaseUrl =
    (window.SPEND_INBOX_CONFIG && window.SPEND_INBOX_CONFIG.apiBaseUrl) || "";
const savedBaseUrl = localStorage.getItem("spend-inbox-api-base-url") || configuredBaseUrl;

const state = {
    apiBaseUrl: savedBaseUrl,
    selectedCaseId: null,
    cases: []
};

const sampleAlert = {
    title: "EC2 spend jumped outside the normal daily range",
    service: "Amazon EC2",
    severity: "HIGH",
    estimatedImpactUsd: 182.4,
    alertType: "ANOMALY",
    likelyCause: "A batch worker fleet appears to have stayed on after the nightly job completed.",
    suggestedAction: "Check newly launched EC2 instances in us-east-1 and stop the idle worker group first.",
    owner: "platform",
    resourceHints: [
        "AutoScalingGroup/batch-workers",
        "i-0abc123def4567890"
    ]
};

function byId(id) {
    return document.getElementById(id);
}

function normalizedBaseUrl() {
    return (state.apiBaseUrl || "").replace(/\/$/, "");
}

function renderCases() {
    const list = byId("caseList");
    const count = byId("caseCount");
    list.innerHTML = "";
    count.textContent = `${state.cases.length} loaded`;

    if (state.cases.length === 0) {
        list.innerHTML = '<p class="empty">No cost review cases loaded yet.</p>';
        return;
    }

    state.cases.forEach((item) => {
        const row = document.createElement("article");
        row.className = "event-row";
        row.innerHTML = `
            <div class="event-title">${item.title || "untitled case"} <span class="pill">${item.status}</span></div>
            <div class="event-meta">${item.service || "Unknown service"} | ${item.severity || "UNKNOWN"} | +$${Number(item.estimatedImpactUsd || 0).toFixed(2)} | ${item.receivedAt}</div>
            <button class="secondary" data-case-id="${item.caseId}">Inspect</button>
        `;
        row.querySelector("button").addEventListener("click", () => loadCase(item.caseId));
        list.appendChild(row);
    });
}

function renderDetail(payload) {
    const item = payload.case;
    state.selectedCaseId = item.caseId;

    byId("detailStatus").textContent = item.status || "UNKNOWN";
    byId("detailCaseId").textContent = item.caseId || "-";
    byId("detailSource").textContent = item.sourceLabel || item.source || "-";
    byId("detailService").textContent = item.service || "-";
    byId("detailSeverity").textContent = item.severity || "-";
    byId("detailImpact").textContent = `$${Number(item.estimatedImpactUsd || 0).toFixed(2)}`;
    byId("detailOwner").textContent = item.owner || "unassigned";
    byId("detailLikelyCause").textContent = item.likelyCause || "-";
    byId("detailSuggestedAction").textContent = item.suggestedAction || "-";
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

async function loadCases() {
    try {
        const status = byId("statusFilter").value.trim();
        const source = byId("sourceFilter").value.trim();
        const service = byId("serviceFilter").value.trim();
        const severity = byId("severityFilter").value.trim();
        const params = new URLSearchParams();
        if (status) {
            params.set("status", status);
        }
        if (source) {
            params.set("source", source);
        }
        if (service) {
            params.set("service", service);
        }
        if (severity) {
            params.set("severity", severity);
        }

        const suffix = params.toString() ? `?${params.toString()}` : "";
        const data = await apiFetch(`/cases${suffix}`);
        state.cases = data.items || [];
        renderCases();
    } catch (error) {
        alert(error.message);
    }
}

async function loadCase(caseId) {
    try {
        const data = await apiFetch(`/cases/${caseId}`);
        renderDetail(data);
    } catch (error) {
        alert(error.message);
    }
}

async function ingestSampleAlert() {
    try {
        await apiFetch("/alerts/anomaly-detection", {
            method: "POST",
            body: JSON.stringify(sampleAlert)
        });
        await loadCases();
    } catch (error) {
        alert(error.message);
    }
}

async function reviewSelectedCase(status) {
    if (!state.selectedCaseId) {
        alert("Select a case first.");
        return;
    }

    try {
        const note = byId("reviewNote").value.trim() || "Manual cost review update.";
        await apiFetch(`/cases/${state.selectedCaseId}/review`, {
            method: "POST",
            body: JSON.stringify({ status, note })
        });
        await loadCase(state.selectedCaseId);
        await loadCases();
    } catch (error) {
        alert(error.message);
    }
}

function saveBaseUrl() {
    state.apiBaseUrl = byId("apiBaseUrl").value.trim();
    localStorage.setItem("spend-inbox-api-base-url", state.apiBaseUrl);
}

function boot() {
    byId("apiBaseUrl").value = state.apiBaseUrl;
    byId("saveBaseUrl").addEventListener("click", saveBaseUrl);
    byId("refreshCases").addEventListener("click", loadCases);
    byId("ingestSample").addEventListener("click", ingestSampleAlert);
    byId("applyFilters").addEventListener("click", loadCases);
    byId("acknowledgeCase").addEventListener("click", () => reviewSelectedCase("ACKNOWLEDGED"));
    byId("resolveCase").addEventListener("click", () => reviewSelectedCase("RESOLVED"));
}

boot();
