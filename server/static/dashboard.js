function refreshStatus() {
    fetch("/api/status")
        .then(r => r.json())
        .then(d => {
            document.getElementById("service").innerText = d.service;
            document.getElementById("cpu").innerText = d.cpu;
            document.getElementById("memory").innerText = d.memory;
            document.getElementById("proxy").innerText = d.proxy_mode;
        });
}

function refreshLogs() {
    fetch("/api/logs")
        .then(r => r.json())
        .then(d => {
            document.getElementById("logs").innerText = d.logs;
        });
}

function ctrl(action) {
    fetch("/api/control", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action})
    }).then(refreshStatus);
}

async function loadRequests() {
  try {
    const res = await fetch('/api/requests');

    if (!res.ok) {
      const text = await res.text();
      console.error("API error:", text);
      return;
    }

    const data = await res.json();

    const el = document.getElementById('logs');
    el.textContent = data.rows.map(r =>
      `${r.time} | ${r.ip} | ${r.model} | ${r.status} | ${r.latency}ms`
    ).join('\n');

  } catch (e) {
    console.error("Fetch failed:", e);
  }
}

setInterval(loadRequests, 2000);
setInterval(refreshStatus, 3000);

refreshStatus();
loadRequests();

