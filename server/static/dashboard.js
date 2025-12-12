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

setInterval(refreshStatus, 3000);
setInterval(refreshLogs, 5000);

refreshStatus();
refreshLogs();