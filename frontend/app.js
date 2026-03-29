const configuredBaseUrl =
    (window.LEAK_GUARD_CONFIG && window.LEAK_GUARD_CONFIG.apiBaseUrl) || "";
const savedBaseUrl = localStorage.getItem("leak-guard-api-base-url") || configuredBaseUrl;

const state = {
    apiBaseUrl: savedBaseUrl,
    selectedFindingId: null,
    selectedFinding: null,
    findings: []
};
const sampleDeliveryId = (window.crypto && window.crypto.randomUUID)
    ? `sample-${window.crypto.randomUUID()}`
    : `sample-${Date.now()}`;

const samplePush = {
    ref: "refs/heads/main",
    before: "1111111111111111111111111111111111111111",
    after: "2222222222222222222222222222222222222222",
    compare: "https://github.com/acme/demo-repo/compare/1111111...2222222",
    repository: {
        full_name: "acme/demo-repo"
    },
    inlineDiff: [
        "diff --git a/app.py b/app.py",
        "index 123..456 100644",
        "--- a/app.py",
        "+++ b/app.py",
        "@@ -1,3 +1,5 @@",
        "+AWS_ACCESS_KEY_ID = \"AKIAIOSFODNN7EXAMPLE\""
    ].join("\n")
};

function byId(id) {
    return document.getElementById(id);
}

function normalizedBaseUrl() {
    return (state.apiBaseUrl || "").replace(/\/$/, "");
}

function renderFindings() {
    const list = byId("findingList");
    const count = byId("findingCount");
    list.innerHTML = "";
    count.textContent = `${state.findings.length} loaded`;

    if (state.findings.length === 0) {
        list.innerHTML = '<p class="empty">No leaked key findings loaded yet.</p>';
        return;
    }

    state.findings.forEach((item) => {
        const row = document.createElement("article");
        row.className = "event-row";
        row.innerHTML = `
            <div class="event-title">${item.matchedKeyIdRedacted || "unknown key"} <span class="pill">${item.status}</span></div>
            <div class="event-meta">${item.repoFullName || "unknown repo"} | ${item.secretType || "unknown"} | ${item.severity || "UNKNOWN"} | alert ${item.alertStatus || "UNKNOWN"} | ${item.iamUserName || "unresolved user"} | ${item.receivedAt}</div>
            <button class="secondary" data-finding-id="${item.findingId}">Inspect</button>
        `;
        row.querySelector("button").addEventListener("click", () => loadFinding(item.findingId));
        list.appendChild(row);
    });
}

function renderDetail(payload) {
    const item = payload.finding;
    state.selectedFindingId = item.findingId;
    state.selectedFinding = item;

    byId("detailStatus").textContent = item.status || "UNKNOWN";
    byId("detailFindingId").textContent = item.findingId || "-";
    byId("detailRepo").textContent = item.repoFullName || "-";
    byId("detailBranch").textContent = item.branch || "-";
    byId("detailSecretType").textContent = item.secretType || "-";
    byId("detailSeverity").textContent = item.severity || "-";
    byId("detailConfidence").textContent = item.confidence || "-";
    byId("detailKeyId").textContent = item.matchedKeyIdRedacted || "-";
    byId("detailUser").textContent = item.iamUserName || "not resolved";
    byId("detailCompareUrl").textContent = item.compareUrl || "-";
    byId("detailLastUsedService").textContent = item.lastUsedService || "unknown";
    byId("detailDeliveryId").textContent = item.deliveryId || "-";
    byId("detailDisableEligibility").textContent = item.disableEligible ? "ELIGIBLE" : "BLOCKED";
    byId("detailAlertStatus").textContent = item.alertStatus || "-";
    byId("detailAlertChannel").textContent = item.alertChannel || "-";
    byId("payloadView").textContent = JSON.stringify(payload.payload || {}, null, 2);
    byId("historyView").textContent = JSON.stringify(item.actionHistory || [], null, 2);
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

async function loadFindings() {
    try {
        const status = byId("statusFilter").value.trim();
        const repo = byId("repoFilter").value.trim();
        const secretType = byId("secretTypeFilter").value.trim();
        const params = new URLSearchParams();
        if (status) {
            params.set("status", status);
        }
        if (repo) {
            params.set("repo", repo);
        }
        if (secretType) {
            params.set("secretType", secretType);
        }

        const suffix = params.toString() ? `?${params.toString()}` : "";
        const data = await apiFetch(`/findings${suffix}`);
        state.findings = data.items || [];
        renderFindings();
    } catch (error) {
        alert(error.message);
    }
}

async function loadFinding(findingId) {
    try {
        const data = await apiFetch(`/findings/${findingId}`);
        renderDetail(data);
    } catch (error) {
        alert(error.message);
    }
}

async function ingestSamplePush() {
    try {
        await apiFetch("/github/webhook", {
            method: "POST",
            headers: {
                "x-github-delivery": sampleDeliveryId,
                "x-github-event": "push"
            },
            body: JSON.stringify(samplePush)
        });
        await loadFindings();
    } catch (error) {
        alert(error.message);
    }
}

async function takeAction(action) {
    if (!state.selectedFindingId) {
        alert("Select a finding first.");
        return;
    }
    if (action === "DISABLE_KEY" && state.selectedFinding && !state.selectedFinding.disableEligible) {
        alert("This finding is currently blocked by the disable policy.");
        return;
    }

    try {
        const note = byId("actionNote").value.trim() || "Manual response action.";
        const confirmed = byId("disableConfirm").value.trim() === "DISABLE_KEY";
        await apiFetch(`/findings/${state.selectedFindingId}/action`, {
            method: "POST",
            body: JSON.stringify({ action, note, confirmed })
        });
        await loadFinding(state.selectedFindingId);
        await loadFindings();
    } catch (error) {
        alert(error.message);
    }
}

function saveBaseUrl() {
    state.apiBaseUrl = byId("apiBaseUrl").value.trim();
    localStorage.setItem("leak-guard-api-base-url", state.apiBaseUrl);
}

function boot() {
    byId("apiBaseUrl").value = state.apiBaseUrl;
    byId("saveBaseUrl").addEventListener("click", saveBaseUrl);
    byId("refreshFindings").addEventListener("click", loadFindings);
    byId("ingestSample").addEventListener("click", ingestSamplePush);
    byId("applyFilters").addEventListener("click", loadFindings);
    byId("disableKey").addEventListener("click", () => takeAction("DISABLE_KEY"));
    byId("dismissFinding").addEventListener("click", () => takeAction("DISMISS"));
}

boot();
