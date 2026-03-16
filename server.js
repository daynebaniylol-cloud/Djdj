const express = require("express");
const http = require("http");
const { Server } = require("socket.io");

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" }
});

const players = {};
const chatMessages = [];

const html = `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>Brawl Mini</title>
  <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    * { box-sizing: border-box; font-family: Arial, sans-serif; }
    html, body {
      margin: 0;
      padding: 0;
      overflow: hidden;
      background: #111;
      color: white;
    }
    canvas {
      display: block;
      background:
        linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px),
        #151515;
      background-size: 72px 72px;
    }
    #topbar {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 5;
      background: rgba(0,0,0,.55);
      padding: 10px 12px;
      font-size: 18px;
      font-weight: bold;
    }
    #joyBase {
      position: fixed;
      left: 18px;
      bottom: 90px;
      width: 170px;
      height: 170px;
      border-radius: 50%;
      background: rgba(255,255,255,.12);
      z-index: 5;
      touch-action: none;
    }
    #joyStick {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 70px;
      height: 70px;
      margin-left: -35px;
      margin-top: -35px;
      border-radius: 50%;
      background: rgba(255,255,255,.28);
    }
    #chat {
      position: fixed;
      left: 10px;
      right: 10px;
      bottom: 10px;
      z-index: 6;
      background: rgba(0,0,0,.65);
      border-radius: 14px;
      padding: 8px;
    }
    #messages {
      height: 120px;
      overflow-y: auto;
      font-size: 14px;
      margin-bottom: 8px;
      word-break: break-word;
    }
    #row {
      display: flex;
      gap: 8px;
    }
    #input {
      flex: 1;
      padding: 12px;
      border: none;
      border-radius: 10px;
      outline: none;
      font-size: 16px;
    }
    #send {
      padding: 12px 14px;
      border: none;
      border-radius: 10px;
      background: #1ea7ff;
      color: #fff;
      font-size: 16px;
    }
  </style>
</head>
<body>
  <div id="topbar">Онлайн: 0 | Ты: Guest</div>
  <canvas id="game"></canvas>

  <div id="joyBase"><div id="joyStick"></div></div>

  <div id="chat">
    <div id="messages"></div>
    <div id="row">
      <input id="input" placeholder="Сообщение..." maxlength="120">
      <button id="send">➤</button>
    </div>
  </div>

<script>
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const tgUser = tg?.initDataUnsafe?.user;
const myName = tgUser?.username || tgUser?.first_name || "Guest";

const socket = io();
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const topbar = document.getElementById("topbar");
const messages = document.getElementById("messages");
const input = document.getElementById("input");
const send = document.getElementById("send");

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
resize();
window.addEventListener("resize", resize);

let myId = null;
let players = {};
let camera = { x: 0, y: 0 };

function addMsg(m) {
  const d = document.createElement("div");
  d.textContent = m.name + ": " + m.text;
  messages.appendChild(d);
  messages.scrollTop = messages.scrollHeight;
}

send.onclick = () => {
  const text = input.value.trim();
  if (!text) return;
  socket.emit("chatMessage", text);
  input.value = "";
};

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") send.click();
});

socket.on("init", (data) => {
  myId = data.id;
  players = data.players || {};
  if (data.messages) {
    messages.innerHTML = "";
    data.messages.forEach(addMsg);
  }
  socket.emit("setName", myName);
});

socket.on("players", (p) => {
  players = p;
});

socket.on("playerJoined", (p) => {
  players[p.id] = p;
});

socket.on("playerLeft", (id) => {
  delete players[id];
});

socket.on("playerMoved", ({ id, x, y }) => {
  if (players[id]) {
    players[id].x = x;
    players[id].y = y;
  }
});

socket.on("chatMessage", addMsg);

const joyBase = document.getElementById("joyBase");
const joyStick = document.getElementById("joyStick");

let joyActive = false;
let joyDx = 0;
let joyDy = 0;

function setJoy(clientX, clientY) {
  const rect = joyBase.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;

  let dx = clientX - cx;
  let dy = clientY - cy;

  const dist = Math.hypot(dx, dy);
  const max = 50;

  if (dist > max) {
    dx = dx / dist * max;
    dy = dy / dist * max;
  }

  joyDx = dx / max;
  joyDy = dy / max;

  joyStick.style.marginLeft = (-35 + dx) + "px";
  joyStick.style.marginTop = (-35 + dy) + "px";
}

function resetJoy() {
  joyDx = 0;
  joyDy = 0;
  joyStick.style.marginLeft = "-35px";
  joyStick.style.marginTop = "-35px";
}

joyBase.addEventListener("touchstart", (e) => {
  joyActive = true;
  const t = e.touches[0];
  setJoy(t.clientX, t.clientY);
}, { passive: true });

joyBase.addEventListener("touchmove", (e) => {
  if (!joyActive) return;
  const t = e.touches[0];
  setJoy(t.clientX, t.clientY);
}, { passive: true });

joyBase.addEventListener("touchend", () => {
  joyActive = false;
  resetJoy();
}, { passive: true });

joyBase.addEventListener("touchcancel", () => {
  joyActive = false;
  resetJoy();
}, { passive: true });

function loop() {
  requestAnimationFrame(loop);

  const me = players[myId];
  if (me) {
    me.x += joyDx * 4;
    me.y += joyDy * 4;

    socket.emit("move", { x: me.x, y: me.y });

    camera.x = me.x - canvas.width / 2;
    camera.y = me.y - canvas.height / 2;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (const id in players) {
    const p = players[id];
    const sx = p.x - camera.x;
    const sy = p.y - camera.y;

    ctx.beginPath();
    ctx.arc(sx, sy, 34, 0, Math.PI * 2);
    ctx.fillStyle = id === myId ? "#4aa8ff" : "#ff5252";
    ctx.fill();

    ctx.lineWidth = 4;
    ctx.strokeStyle = "rgba(255,255,255,.7)";
    ctx.stroke();

    ctx.fillStyle = "white";
    ctx.font = "bold 18px Arial";
    ctx.textAlign = "center";
    ctx.fillText(p.name || "Guest", sx, sy - 44);
  }

  topbar.textContent = "Онлайн: " + Object.keys(players).length + " | Ты: " + (players[myId]?.name || myName);
}
loop();
</script>
</body>
</html>`;

io.on("connection", (socket) => {
  players[socket.id] = {
    id: socket.id,
    x: 300 + Math.random() * 300,
    y: 300 + Math.random() * 300,
    name: "Guest"
  };

  socket.emit("init", {
    id: socket.id,
    players,
    messages: chatMessages
  });

  socket.broadcast.emit("playerJoined", players[socket.id]);
  io.emit("players", players);

  socket.on("setName", (name) => {
    if (!players[socket.id]) return;
    players[socket.id].name = String(name || "Guest").slice(0, 20);
    io.emit("players", players);
  });

  socket.on("move", ({ x, y }) => {
    if (!players[socket.id]) return;
    players[socket.id].x = x;
    players[socket.id].y = y;
    socket.broadcast.emit("playerMoved", { id: socket.id, x, y });
  });

  socket.on("chatMessage", (text) => {
    if (!players[socket.id]) return;
    const clean = String(text || "").trim().slice(0, 120);
    if (!clean) return;

    const msg = {
      name: players[socket.id].name,
      text: clean
    };

    chatMessages.push(msg);
    if (chatMessages.length > 50) chatMessages.shift();

    io.emit("chatMessage", msg);
  });

  socket.on("disconnect", () => {
    delete players[socket.id];
    io.emit("playerLeft", socket.id);
    io.emit("players", players);
  });
});

app.get("/", (req, res) => {
  res.send(html);
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log("site started on " + PORT);
});
