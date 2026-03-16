const http = require("http");
const crypto = require("crypto");

const PORT = process.env.PORT || 3000;
const BOT_TOKEN = process.env.BOT_TOKEN || "8799455642:AAE2U-tBn2xsI46n9YkOZIBtf3l7J3iR8R4";
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;
const PUBLIC_URL = process.env.RENDER_EXTERNAL_URL || "";

const players = new Map();
const sockets = new Set();

function rnd(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function clamp(v, a, b) {
  return Math.max(a, Math.min(b, v));
}

function randomColor(id) {
  const colors = [
    "#ff4d4f",
    "#40a9ff",
    "#73d13d",
    "#faad14",
    "#9254de",
    "#13c2c2",
    "#eb2f96",
    "#a0d911"
  ];
  return colors[Math.abs(Number(id) || 0) % colors.length];
}

async function tg(method, data = {}) {
  const res = await fetch(`${API}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(data)
  });
  return res.json();
}

function sendJson(res, code, obj) {
  res.writeHead(code, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(obj));
}

function sendHtml(res, html) {
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(html);
}

function alivePlayers() {
  const now = Date.now();
  const arr = [];
  for (const p of players.values()) {
    if (now - p.last < 30000) arr.push(p);
  }
  return arr;
}

function getState() {
  return { players: alivePlayers(), t: Date.now() };
}

function broadcast() {
  const payload = `data: ${JSON.stringify(getState())}\n\n`;
  for (const s of sockets) {
    try {
      s.write(payload);
    } catch {}
  }
}

function upsertPlayer(id, name) {
  id = String(id);
  let p = players.get(id);
  if (!p) {
    p = {
      id,
      name: String(name || "Player").slice(0, 16),
      x: rnd(80, 520),
      y: rnd(80, 520),
      color: randomColor(id),
      last: Date.now()
    };
    players.set(id, p);
  } else {
    p.name = String(name || p.name).slice(0, 16);
    p.last = Date.now();
  }
  return p;
}

function parseInitDataUnsafe(initData) {
  const params = new URLSearchParams(initData || "");
  const userRaw = params.get("user");
  if (!userRaw) return null;

  try {
    const user = JSON.parse(userRaw);
    return {
      id: String(user.id),
      name: String(user.username || user.first_name || "Player")
    };
  } catch {
    return null;
  }
}

async function handleTelegramUpdate(update) {
  const msg = update.message;

  if (msg && msg.text === "/start") {
    const chatId = msg.chat.id;

    const url = PUBLIC_URL || "https://example.onrender.com";

    await tg("sendMessage", {
      chat_id: chatId,
      text: "Жми кнопку ниже.",
      reply_markup: {
        inline_keyboard: [
          [
            {
              text: "Играть",
              web_app: { url }
            }
          ]
        ]
      }
    });
  }
}

const html = `<!doctype html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no" />
  <title>Mini Game</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      background: #111;
      color: white;
      font-family: Arial, sans-serif;
      overflow: hidden;
      touch-action: none;
    }

    #top {
      position: fixed;
      left: 0;
      top: 0;
      right: 0;
      z-index: 10;
      padding: 10px 12px;
      background: rgba(0,0,0,0.4);
      font-size: 14px;
      backdrop-filter: blur(6px);
    }

    #c {
      display: block;
      width: 100vw;
      height: 100vh;
      background: #1b1b1b;
    }

    #joyWrap {
      position: fixed;
      left: 18px;
      bottom: 22px;
      width: 140px;
      height: 140px;
      border-radius: 50%;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
      z-index: 20;
      touch-action: none;
    }

    #joy {
      position: absolute;
      width: 64px;
      height: 64px;
      left: 38px;
      top: 38px;
      border-radius: 50%;
      background: rgba(255,255,255,0.28);
    }

    #hint {
      position: fixed;
      right: 14px;
      bottom: 24px;
      z-index: 20;
      font-size: 13px;
      opacity: 0.85;
      background: rgba(0,0,0,0.35);
      padding: 8px 10px;
      border-radius: 12px;
    }
  </style>
</head>
<body>
  <div id="top">Загрузка...</div>
  <canvas id="c"></canvas>
  <div id="joyWrap"><div id="joy"></div></div>
  <div id="hint">Двигай кружок слева</div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.expand();

    const topEl = document.getElementById("top");
    const canvas = document.getElementById("c");
    const ctx = canvas.getContext("2d");
    const joyWrap = document.getElementById("joyWrap");
    const joy = document.getElementById("joy");

    const world = { w: 2000, h: 2000 };
    let state = { players: [] };

    const me = (() => {
      const unsafe = tg.initDataUnsafe || {};
      const u = unsafe.user || { id: "guest_" + Math.random(), first_name: "Guest" };
      return {
        id: String(u.id),
        name: String(u.username || u.first_name || "Player").slice(0, 16)
      };
    })();

    function resize() {
      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    addEventListener("resize", resize);

    const es = new EventSource("/events");
    es.onmessage = (ev) => {
      state = JSON.parse(ev.data);
      topEl.textContent = "Онлайн: " + state.players.length + " | Ты: " + me.name;
      draw();
    };

    let vx = 0;
    let vy = 0;

    function sendMove() {
      fetch("/move", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          id: me.id,
          name: me.name,
          dx: vx,
          dy: vy
        })
      }).catch(() => {});
    }

    setInterval(sendMove, 50);

    function getMeState() {
      return state.players.find(p => String(p.id) === String(me.id)) || {
        id: me.id,
        name: me.name,
        x: world.w / 2,
        y: world.h / 2,
        color: "#40a9ff"
      };
    }

    function drawGrid(camX, camY) {
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.lineWidth = 1;
      const step = 80;
      const startX = - (camX % step);
      const startY = - (camY % step);

      for (let x = startX; x < innerWidth; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, innerHeight);
        ctx.stroke();
      }

      for (let y = startY; y < innerHeight; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(innerWidth, y);
        ctx.stroke();
      }
    }

    function draw() {
      ctx.clearRect(0, 0, innerWidth, innerHeight);

      const meState = getMeState();
      const camX = meState.x - innerWidth / 2;
      const camY = meState.y - innerHeight / 2;

      drawGrid(camX, camY);

      for (const p of state.players) {
        const sx = p.x - camX;
        const sy = p.y - camY;

        if (sx < -100 || sy < -100 || sx > innerWidth + 100 || sy > innerHeight + 100) continue;

        ctx.beginPath();
        ctx.arc(sx, sy, 24, 0, Math.PI * 2);
        ctx.fillStyle = p.color || "#999";
        ctx.fill();

        ctx.lineWidth = 3;
        ctx.strokeStyle = String(p.id) === String(me.id) ? "#fff" : "rgba(255,255,255,0.45)";
        ctx.stroke();

        ctx.font = "bold 14px Arial";
        ctx.textAlign = "center";
        ctx.fillStyle = "#fff";
        ctx.fillText(p.name || "Player", sx, sy - 34);
      }
    }

    let dragging = false;
    let baseX = 70;
    let baseY = 70;

    function setKnob(x, y) {
      const dx = x - baseX;
      const dy = y - baseY;
      const dist = Math.hypot(dx, dy);
      const max = 42;

      let kx = dx;
      let ky = dy;
      if (dist > max) {
        kx = dx / dist * max;
        ky = dy / dist * max;
      }

      joy.style.left = (38 + kx) + "px";
      joy.style.top = (38 + ky) + "px";

      vx = kx / max;
      vy = ky / max;
    }

    function resetKnob() {
      joy.style.left = "38px";
      joy.style.top = "38px";
      vx = 0;
      vy = 0;
    }

    joyWrap.addEventListener("pointerdown", (e) => {
      dragging = true;
      joyWrap.setPointerCapture(e.pointerId);
      const r = joyWrap.getBoundingClientRect();
      baseX = r.width / 2;
      baseY = r.height / 2;
      setKnob(e.clientX - r.left, e.clientY - r.top);
    });

    joyWrap.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const r = joyWrap.getBoundingClientRect();
      setKnob(e.clientX - r.left, e.clientY - r.top);
    });

    function endDrag() {
      dragging = false;
      resetKnob();
    }

    joyWrap.addEventListener("pointerup", endDrag);
    joyWrap.addEventListener("pointercancel", endDrag);
    joyWrap.addEventListener("pointerleave", () => {});

    draw();
  </script>
</body>
</html>`;

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");

  if (req.method === "GET" && url.pathname === "/") {
    return sendHtml(res, html);
  }

  if (req.method === "GET" && url.pathname === "/health") {
    return sendJson(res, 200, { ok: true });
  }

  if (req.method === "GET" && url.pathname === "/setwebhook") {
    if (!PUBLIC_URL) {
      return sendJson(res, 400, {
        ok: false,
        error: "No RENDER_EXTERNAL_URL found"
      });
    }

    const hook = await tg("setWebhook", {
      url: PUBLIC_URL + "/telegram"
    });

    return sendJson(res, 200, hook);
  }

  if (req.method === "POST" && url.pathname === "/telegram") {
    let body = "";
    req.on("data", chunk => body += chunk);
    req.on("end", async () => {
      try {
        const update = JSON.parse(body || "{}");
        await handleTelegramUpdate(update);
      } catch {}
      sendJson(res, 200, { ok: true });
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/events") {
    res.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "connection": "keep-alive",
      "access-control-allow-origin": "*"
    });
    res.write(`data: ${JSON.stringify(getState())}\n\n`);
    sockets.add(res);

    const timer = setInterval(() => {
      try {
        res.write(`: ping\n\n`);
      } catch {}
    }, 15000);

    req.on("close", () => {
      clearInterval(timer);
      sockets.delete(res);
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/move") {
    let body = "";
    req.on("data", chunk => body += chunk);
    req.on("end", () => {
      try {
        const data = JSON.parse(body || "{}");
        const p = upsertPlayer(data.id, data.name);

        const speed = 8;
        const dx = Number(data.dx) || 0;
        const dy = Number(data.dy) || 0;

        p.x = clamp(p.x + dx * speed, 24, worldMax().w - 24);
        p.y = clamp(p.y + dy * speed, 24, worldMax().h - 24);
        p.last = Date.now();

        broadcast();
        sendJson(res, 200, { ok: true, player: p });
      } catch {
        sendJson(res, 400, { ok: false });
      }
    });
    return;
  }

  sendJson(res, 404, { ok: false, error: "Not found" });
});

function worldMax() {
  return { w: 2000, h: 2000 };
}

setInterval(() => {
  const now = Date.now();
  for (const [id, p] of players) {
    if (now - p.last > 60000) players.delete(id);
  }
  broadcast();
}, 5000);

server.listen(PORT, () => {
  console.log("Server started on port", PORT);
});
