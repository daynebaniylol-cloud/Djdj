import os
import asyncio
import uuid
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# ── Состояние ─────────────────────────────────────────────────────────────────
history: list[dict] = []
clients: dict[str, dict] = {}   # {ws_id: {ws, nickname}}
reactions: dict[str, dict] = {} # {msg_id: {emoji: [nicks]}}

def ts():
    return datetime.now().strftime("%H:%M")

def new_id():
    return str(uuid.uuid4())[:8]

async def send_all(msg: dict, skip_id=None, save=True):
    if save:
        history.append(msg)
        if len(history) > 300:
            history.pop(0)
    dead = []
    for wid, c in list(clients.items()):
        if wid == skip_id:
            continue
        try:
            await c["ws"].send_json(msg)
        except Exception:
            dead.append(wid)
    for d in dead:
        clients.pop(d, None)

async def send_one(wid: str, msg: dict):
    try:
        await clients[wid]["ws"].send_json(msg)
    except Exception:
        pass

async def update_online():
    nicks = [c["nickname"] for c in clients.values()]
    await send_all({"t": "online", "count": len(nicks), "nicks": nicks}, save=False)

# ── HTML (всё в одном питон-файле) ────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>PyChat</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
html,body{margin:0;padding:0;background:#17212b;font-family:'Inter',sans-serif;height:100%;overflow:hidden;color:#e8edf2;}
#header{background:#1c2b3a;border-bottom:1px solid #232e3c;padding:10px 14px;display:flex;align-items:center;gap:12px;height:56px;position:fixed;top:0;left:0;right:0;z-index:50;}
#avatar{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#5288c1,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}
#hname{font-size:15px;font-weight:600;}
#honline{font-size:12px;color:#64b5f6;margin-top:1px;}
#messages{position:fixed;top:56px;bottom:56px;left:0;right:0;overflow-y:auto;padding:8px 10px;display:flex;flex-direction:column;gap:3px;}
#messages::-webkit-scrollbar{width:3px;}
#messages::-webkit-scrollbar-thumb{background:#2b3f56;border-radius:2px;}
#reply-bar{display:none;position:fixed;background:#162230;border-left:3px solid #5288c1;padding:5px 12px 5px 10px;left:0;right:0;z-index:40;align-items:center;gap:8px;}
#reply-bar .rb-info{flex:1;overflow:hidden;}
#reply-bar .rb-nick{font-size:11px;font-weight:600;color:#64b5f6;}
#reply-bar .rb-text{font-size:12px;color:#aab8c8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#reply-bar button{background:none;border:none;color:#708499;font-size:18px;cursor:pointer;padding:0;}
#input-bar{background:#1c2b3a;border-top:1px solid #232e3c;padding:8px 10px;display:flex;align-items:center;gap:8px;height:56px;position:fixed;bottom:0;left:0;right:0;z-index:50;}
#target-sel{background:#0e1621;border:1px solid #232e3c;border-radius:10px;color:#e8edf2;font-family:'Inter',sans-serif;font-size:13px;padding:6px 8px;height:38px;max-width:110px;outline:none;cursor:pointer;}
#msg-inp{flex:1;background:#0e1621;border:1px solid #232e3c;border-radius:22px;color:#e8edf2;font-family:'Inter',sans-serif;font-size:14px;padding:8px 16px;outline:none;height:38px;}
#msg-inp:focus{border-color:#5288c1;}
#msg-inp::placeholder{color:#708499;}
#send-btn{width:38px;height:38px;border-radius:50%;background:#5288c1;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background .15s;}
#send-btn:active{background:#3f6fa0;}
#send-btn svg{fill:white;width:18px;height:18px;}

.bw{display:flex;flex-direction:column;animation:pop .15s ease;}
@keyframes pop{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:none;}}
.bw.out{align-items:flex-end;}
.bw.in{align-items:flex-start;}
.bw.priv{align-items:center;}
.bw.sys{align-items:center;margin:3px 0;}

.msg-row{display:flex;align-items:flex-end;gap:5px;}
.bw.out .msg-row{flex-direction:row-reverse;}

.bb{max-width:75%;padding:7px 11px 5px;font-size:14px;line-height:1.45;word-break:break-word;position:relative;}
.bb.out{background:#2b5278;border-radius:14px 14px 3px 14px;}
.bb.in{background:#182533;border:1px solid #232e3c;border-radius:14px 14px 14px 3px;}
.bb.priv{background:#1a3a2a;border:1px solid #2d6b45;border-radius:14px;max-width:90%;}
.bb.sys{background:rgba(255,255,255,.05);border-radius:10px;padding:4px 14px;font-size:12px;color:#708499;max-width:90%;text-align:center;}

.bsender{font-size:12px;font-weight:600;margin-bottom:2px;display:block;}
.bsender.in{color:#64b5f6;}.bsender.priv{color:#4caf76;}
.btext{color:#e8edf2;white-space:pre-wrap;}
.btime{font-size:11px;color:#708499;text-align:right;margin-top:3px;display:block;}

.reply-quote{background:rgba(255,255,255,.07);border-left:3px solid #5288c1;border-radius:4px;padding:4px 8px;margin-bottom:5px;}
.rq-nick{font-size:11px;font-weight:600;color:#64b5f6;display:block;}
.rq-text{font-size:12px;color:#aab8c8;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

.actions{display:flex;flex-direction:column;gap:3px;opacity:0;transition:opacity .15s;}
.bw:hover .actions{opacity:1;}
.act-btn{background:rgba(255,255,255,.08);border:none;border-radius:50%;width:26px;height:26px;cursor:pointer;font-size:13px;color:#aab8c8;padding:0;display:flex;align-items:center;justify-content:center;}
.act-btn:hover{background:rgba(255,255,255,.15);}

.react-row{display:flex;flex-wrap:wrap;gap:3px;margin-top:3px;min-height:0;}
.react-chip{background:#1c2b3a;border:1px solid #2b3f56;border-radius:20px;padding:2px 8px;font-size:13px;cursor:pointer;color:#e8edf2;transition:background .1s;}
.react-chip:active{background:#263445;}

#epicker{display:none;position:fixed;background:#1c2b3a;border:1px solid #2d3f55;border-radius:14px;padding:10px;gap:6px;flex-wrap:wrap;z-index:200;box-shadow:0 8px 32px rgba(0,0,0,.6);}
#epicker button{background:none;border:none;font-size:24px;cursor:pointer;padding:4px;border-radius:8px;line-height:1;}
#epicker button:hover{background:rgba(255,255,255,.1);}

/* Login */
#login-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:300;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);}
#login-box{background:#1c2b3a;border:1px solid #232e3c;border-radius:16px;padding:28px 24px;width:min(320px,90vw);}
#login-box h2{margin:0 0 16px;font-size:18px;color:#e8edf2;}
#login-inp{width:100%;background:#0e1621;border:1px solid #232e3c;border-radius:10px;color:#e8edf2;font-family:'Inter',sans-serif;font-size:15px;padding:10px 14px;outline:none;margin-bottom:8px;}
#login-inp:focus{border-color:#5288c1;}
#login-inp::placeholder{color:#708499;}
#login-err{color:#ef5350;font-size:12px;min-height:16px;margin-bottom:8px;}
#login-btn{width:100%;background:#5288c1;border:none;border-radius:10px;color:#fff;font-family:'Inter',sans-serif;font-size:15px;font-weight:600;padding:11px;cursor:pointer;transition:background .15s;}
#login-btn:active{background:#3f6fa0;}
</style>
</head>
<body>

<div id="header">
  <div id="avatar">💬</div>
  <div>
    <div id="hname">PyChat</div>
    <div id="honline">0 онлайн</div>
  </div>
</div>

<div id="messages"></div>

<div id="reply-bar">
  <div class="rb-info">
    <span class="rb-nick" id="rb-nick"></span>
    <span class="rb-text" id="rb-text"></span>
  </div>
  <button onclick="clearReply()">✕</button>
</div>

<div id="input-bar">
  <select id="target-sel"><option value="__all__">Всем</option></select>
  <input id="msg-inp" placeholder="Сообщение..." autocomplete="off">
  <button id="send-btn" onclick="sendMsg()">
    <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
  </button>
</div>

<div id="epicker">
  <button onclick="pickEmoji('👍')">👍</button>
  <button onclick="pickEmoji('❤️')">❤️</button>
  <button onclick="pickEmoji('😂')">😂</button>
  <button onclick="pickEmoji('😮')">😮</button>
  <button onclick="pickEmoji('😢')">😢</button>
  <button onclick="pickEmoji('🔥')">🔥</button>
</div>

<div id="login-overlay">
  <div id="login-box">
    <h2>👋 Войти в чат</h2>
    <input id="login-inp" placeholder="Введи ник..." maxlength="20" autofocus>
    <div id="login-err"></div>
    <button id="login-btn" onclick="doLogin()">Войти →</button>
  </div>
</div>

<script>
var ws = null;
var myNick = null;
var replyTo = null;
var pickerMsgId = null;
var inputBarBottom = 56;

// ── WebSocket ──
function connect() {
  var proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws');

  ws.onmessage = function(e) {
    var msg = JSON.parse(e.data);
    if      (msg.t === 'bubble')   addBubble(msg);
    else if (msg.t === 'online')   updateOnline(msg);
    else if (msg.t === 'reaction') updateReaction(msg);
    else if (msg.t === 'error')    showErr(msg.text);
    else if (msg.t === 'history')  msg.items.forEach(function(m){ addBubble(m, true); });
  };

  ws.onclose = function() {
    setTimeout(connect, 2000); // авто-реконнект
  };
}
connect();

// ── Логин ──
document.getElementById('login-inp').addEventListener('keydown', function(e){ if(e.key==='Enter') doLogin(); });

function doLogin() {
  if (!ws || ws.readyState !== WebSocket.OPEN) { document.getElementById("login-err").textContent = "Подключение..."; setTimeout(doLogin, 300); return; }
  var nick = document.getElementById('login-inp').value.trim();
  if (!nick) return;
  ws.send(JSON.stringify({t:'login', nick:nick}));
}

function showErr(txt) {
  document.getElementById('login-err').textContent = txt;
}

// ── Онлайн ──
function updateOnline(msg) {
  document.getElementById('honline').textContent = msg.count + ' онлайн';
  var sel = document.getElementById('target-sel');
  var cur = sel.value;
  while(sel.options.length > 1) sel.remove(1);
  msg.nicks.forEach(function(n){
    if(n !== myNick){
      var o = new Option(n, n);
      sel.add(o);
    }
  });
  sel.value = cur;
}

// ── Отправка ──
document.getElementById('msg-inp').addEventListener('keydown', function(e){
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendMsg(); }
});

function sendMsg() {
  var text = document.getElementById('msg-inp').value.trim();
  if (!text || !myNick) return;
  document.getElementById('msg-inp').value = '';
  var target = document.getElementById('target-sel').value;
  var payload = {t:'msg', text:text, target:target};
  if (replyTo) { payload.reply = replyTo; clearReply(); }
  ws.send(JSON.stringify(payload));
}

// ── Reply ──
function setReply(mid, nick, text) {
  replyTo = {id:mid, sender:nick, text:text};
  document.getElementById('rb-nick').textContent = nick;
  document.getElementById('rb-text').textContent = text;
  var bar = document.getElementById('reply-bar');
  bar.style.display = 'flex';
  var h = bar.offsetHeight;
  document.getElementById('messages').style.bottom = (56+h) + 'px';
  document.getElementById('msg-inp').focus();
}
function clearReply() {
  replyTo = null;
  document.getElementById('reply-bar').style.display = 'none';
  document.getElementById('messages').style.bottom = '56px';
}

// ── Emoji picker ──
function togglePicker(mid, el) {
  pickerMsgId = mid;
  var p = document.getElementById('epicker');
  if (p.style.display === 'flex') { p.style.display='none'; return; }
  var r = el.getBoundingClientRect();
  p.style.bottom = (window.innerHeight - r.top + 4) + 'px';
  p.style.left = Math.min(r.left, window.innerWidth-220) + 'px';
  p.style.display = 'flex';
}
function pickEmoji(emoji) {
  document.getElementById('epicker').style.display = 'none';
  if (!pickerMsgId) return;
  ws.send(JSON.stringify({t:'react', msg_id:pickerMsgId, emoji:emoji}));
}
document.addEventListener('click', function(e){
  var p = document.getElementById('epicker');
  if (!p.contains(e.target) && !e.target.closest('.act-btn')) p.style.display='none';
});

// ── Пузырьки ──
function addBubble(msg, prepend) {
  var m = document.getElementById('messages');

  if (msg.type === 'auth_ok') {
    myNick = msg.nick;
    document.getElementById('login-overlay').style.display = 'none';
    return;
  }

  var bw = document.createElement('div');
  bw.className = 'bw ' + (msg.type || 'sys');
  if (msg.id) bw.id = 'msg-' + msg.id;

  if (msg.type === 'sys') {
    bw.innerHTML = '<div class="bb sys">' + esc(msg.text) + '</div>';
  } else {
    var isOut = msg.type === 'out';
    var isPriv = msg.type === 'priv';
    var bbCls = isOut ? 'out' : (isPriv ? 'priv' : 'in');
    var senderCls = isPriv ? 'priv' : 'in';

    var replyHtml = '';
    if (msg.reply) {
      replyHtml = '<div class="reply-quote"><span class="rq-nick">'+esc(msg.reply.sender)+'</span><span class="rq-text">'+esc(msg.reply.text)+'</span></div>';
    }
    var senderHtml = (!isOut && msg.sender) ? '<span class="bsender '+senderCls+'">'+esc(msg.sender)+'</span>' : '';

    var mid = msg.id || '';
    var actBtns = mid ? (
      '<button class="act-btn" onclick="setReply(\''+mid+'\',\''+esc(msg.sender||myNick)+'\',\''+esc(msg.text)+'\')" title="Ответить">↩</button>' +
      '<button class="act-btn" onclick="togglePicker(\''+mid+'\',this)" title="Реакция">😊</button>'
    ) : '';
    var actions = '<div class="actions">' + actBtns + '</div>';

    var bubble = '<div class="bb '+bbCls+'">'+replyHtml+senderHtml+'<span class="btext">'+esc(msg.text)+'</span><span class="btime">'+esc(msg.time||'')+'</span></div>';
    var rowOrder = isOut ? actions+bubble : bubble+actions;
    bw.innerHTML = '<div class="msg-row">'+rowOrder+'</div><div class="react-row" id="react-'+mid+'"></div>';
  }

  if (prepend) m.insertBefore(bw, m.firstChild);
  else {
    m.appendChild(bw);
    m.scrollTop = m.scrollHeight;
  }
}

function updateReaction(msg) {
  var row = document.getElementById('react-' + msg.msg_id);
  if (!row) return;
  var chips = '';
  for (var em in msg.data) {
    var nicks = msg.data[em];
    if (nicks.length) {
      chips += '<button class="react-chip" title="'+nicks.join(', ')+'" onclick="pickEmojiDirect(\''+msg.msg_id+'\',\''+em+'\')">'+em+' '+nicks.length+'</button>';
    }
  }
  row.innerHTML = chips;
}
function pickEmojiDirect(mid, emoji) {
  ws.send(JSON.stringify({t:'react', msg_id:mid, emoji:emoji}));
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>"""


# ── HTTP ──────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return HTMLResponse(HTML)


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    wid = new_id()
    clients[wid] = {"ws": websocket, "nickname": None}

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            t = msg.get("t")

            # ── Логин ──
            if t == "login":
                nick = msg.get("nick", "").strip()[:20]
                if not nick:
                    await websocket.send_json({"t":"error","text":"Ник не может быть пустым"})
                    continue
                taken = [c["nickname"] for c in clients.values() if c["nickname"]]
                if nick in taken:
                    await websocket.send_json({"t":"error","text":f"Ник «{nick}» уже занят"})
                    continue

                clients[wid]["nickname"] = nick
                await websocket.send_json({"t":"bubble","type":"auth_ok","nick":nick})

                # История
                if history:
                    await websocket.send_json({"t":"history","items":history[-50:]})

                await update_online()
                await send_all({"t":"bubble","type":"sys","text":f"{nick} присоединился 👋","time":ts()}, skip_id=wid)
                await websocket.send_json({"t":"bubble","type":"sys","text":f"Привет, {nick}! 🎉","time":ts()})

            # ── Сообщение ──
            elif t == "msg":
                nick = clients[wid]["nickname"]
                if not nick:
                    continue
                text = msg.get("text","").strip()
                if not text:
                    continue
                target = msg.get("target","__all__")
                reply  = msg.get("reply")
                mid    = new_id()
                now    = ts()

                if target == "__all__":
                    bubble_out = {"t":"bubble","id":mid,"type":"out","sender":nick,"text":text,"time":now}
                    bubble_in  = {"t":"bubble","id":mid,"type":"in", "sender":nick,"text":text,"time":now}
                    if reply:
                        bubble_out["reply"] = reply
                        bubble_in["reply"]  = reply
                    await websocket.send_json(bubble_out)
                    await send_all(bubble_in, skip_id=wid)
                else:
                    # Личка
                    tid = next((c for c,s in clients.items() if s["nickname"]==target), None)
                    out = {"t":"bubble","id":mid,"type":"priv","sender":f"🔒 ты → {target}","text":text,"time":now}
                    inp = {"t":"bubble","id":mid,"type":"priv","sender":f"🔒 {nick} → тебе","text":text,"time":now}
                    if reply:
                        out["reply"] = inp["reply"] = reply
                    await websocket.send_json(out)
                    if tid:
                        await send_one(tid, inp)

            # ── Реакция ──
            elif t == "react":
                nick = clients[wid]["nickname"]
                if not nick:
                    continue
                mid   = msg.get("msg_id","")
                emoji = msg.get("emoji","")
                if not mid or not emoji:
                    continue
                if mid not in reactions:
                    reactions[mid] = {}
                lst = reactions[mid].setdefault(emoji, [])
                if nick in lst:
                    lst.remove(nick)
                else:
                    lst.append(nick)
                react_msg = {"t":"reaction","msg_id":mid,"data":reactions[mid]}
                await send_all(react_msg, save=False)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        nick = clients.pop(wid, {}).get("nickname")
        if nick:
            await send_all({"t":"bubble","type":"sys","text":f"{nick} вышел из чата","time":ts()})
            await update_online()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
