import os
import asyncio
import uuid
from datetime import datetime
from nicegui import ui, Client

# ── Состояние ─────────────────────────────────────────────────────────────────
history: list[dict] = []          # [{id, type, sender, text, time, reply_to}]
sessions: dict = {}               # {cid: {nickname, queue, client}}
reactions: dict = {}              # {msg_id: {'👍': ['nick1'], '❤️': []}}

REACTION_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥"]

def ts():
    return datetime.now().strftime("%H:%M")

def new_id():
    return str(uuid.uuid4())[:8]


# ── Broadcast ─────────────────────────────────────────────────────────────────
async def broadcast(msg: dict, skip_id=None, save=True):
    if save:
        history.append(msg)
        if len(history) > 300:
            history.pop(0)
    for cid, s in list(sessions.items()):
        if cid == skip_id:
            continue
        try:
            await s["queue"].put(("bubble", msg))
        except Exception:
            pass

async def broadcast_reaction(msg_id: str, skip_id=None):
    data = reactions.get(msg_id, {})
    for cid, s in list(sessions.items()):
        if cid == skip_id:
            continue
        try:
            await s["queue"].put(("reaction", msg_id, data))
        except Exception:
            pass

async def broadcast_js(js: str, skip_id=None):
    for cid, s in list(sessions.items()):
        if cid == skip_id:
            continue
        try:
            await s["queue"].put(("js", js))
        except Exception:
            pass


# ── HTML пузырьков ─────────────────────────────────────────────────────────────
def bubble_html(msg: dict, my_nick: str) -> str:
    mtype  = msg.get("type", "in")
    text   = msg.get("text", "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    sender = msg.get("sender","").replace("<","&lt;")
    time   = msg.get("time","")
    mid    = msg.get("id","")
    reply  = msg.get("reply_to")

    if mtype == "system":
        return f'<div class="bw sys"><div class="bb sys">{text}</div></div>'

    reply_html = ""
    if reply:
        rtext = reply.get("text","").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rsender = reply.get("sender","").replace("<","&lt;")
        reply_html = f'<div class="reply-bar"><span class="reply-sender">{rsender}</span><span class="reply-text">{rtext[:60]}{"…" if len(rtext)>60 else ""}</span></div>'

    react_html = f'<div class="react-row" id="react-{mid}"></div>'
    react_btn  = f'<button class="react-pick-btn" onclick="togglePicker(\'{mid}\')" title="Реакция">😊</button>'
    reply_btn  = f'<button class="reply-btn" onclick="setReply(\'{mid}\',`{sender}`,`{text[:60]}`)" title="Ответить">↩</button>'
    actions    = f'<div class="msg-actions">{reply_btn}{react_btn}</div>'

    if mtype == "outgoing":
        return f'''<div class="bw out" id="msg-{mid}">
  <div class="msg-wrap">
    {actions}
    <div class="bb out">{reply_html}<span class="bt">{text}</span><span class="btime">{time}</span></div>
  </div>
  {react_html}
</div>'''

    if mtype == "private":
        return f'''<div class="bw priv" id="msg-{mid}">
  <div class="msg-wrap">
    <div class="bb priv">{reply_html}<span class="bs priv">{sender}</span><span class="bt">{text}</span><span class="btime">{time}</span></div>
    {actions}
  </div>
  {react_html}
</div>'''

    # incoming
    return f'''<div class="bw in" id="msg-{mid}">
  <div class="msg-wrap">
    <div class="bb in">{reply_html}<span class="bs in">{sender}</span><span class="bt">{text}</span><span class="btime">{time}</span></div>
    {actions}
  </div>
  {react_html}
</div>'''


def reaction_js(msg_id: str, data: dict) -> str:
    parts = []
    for emoji, nicks in data.items():
        if nicks:
            title = ", ".join(nicks)
            parts.append(f'<button class="react-chip" title="{title}" onclick="sendReaction(\'{msg_id}\',\'{emoji}\')">{emoji} {len(nicks)}</button>')
    inner = "".join(parts)
    escaped = inner.replace("`","\\`").replace("${","\\${")
    return f"""(function(){{var el=document.getElementById('react-{msg_id}');if(el)el.innerHTML=`{escaped}`;}})();"""


# ── CSS + JS ───────────────────────────────────────────────────────────────────
STYLES = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:#17212b!important;font-family:'Inter',sans-serif!important;height:100%;overflow:hidden;}
.nicegui-content{padding:0!important;background:#17212b!important;}
.q-page{background:#17212b!important;}

#tg-header{background:#1c2b3a;border-bottom:1px solid #232e3c;padding:10px 16px;display:flex;align-items:center;gap:12px;height:58px;position:fixed;top:0;left:0;right:0;z-index:50;}
#tg-avatar{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#5288c1,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}

#tg-messages{position:fixed;top:58px;bottom:64px;left:0;right:0;overflow-y:auto;padding:10px 12px 4px;background:#17212b;}
#tg-messages::-webkit-scrollbar{width:3px;}
#tg-messages::-webkit-scrollbar-thumb{background:#2b3f56;border-radius:2px;}

#reply-preview{display:none;background:#162230;border-left:3px solid #5288c1;padding:6px 10px;font-size:12px;color:#aab8c8;position:fixed;bottom:64px;left:0;right:0;z-index:40;display:none;align-items:center;justify-content:space-between;}
#reply-preview span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#reply-preview button{background:none;border:none;color:#708499;font-size:16px;cursor:pointer;padding:0 4px;}

.bw{display:flex;flex-direction:column;margin-bottom:6px;animation:pop .15s ease;}
@keyframes pop{from{opacity:0;transform:translateY(5px);}to{opacity:1;transform:none;}}
.bw.out{align-items:flex-end;}
.bw.in{align-items:flex-start;}
.bw.priv{align-items:center;}
.bw.sys{align-items:center;}

.msg-wrap{display:flex;align-items:flex-end;gap:4px;}
.bw.out .msg-wrap{flex-direction:row-reverse;}

.bb{max-width:72%;padding:7px 11px 5px;font-size:14px;line-height:1.45;word-break:break-word;position:relative;}
.bb.out{background:#2b5278;border-radius:14px 14px 3px 14px;}
.bb.in{background:#182533;border:1px solid #232e3c;border-radius:14px 14px 14px 3px;}
.bb.priv{background:#1a3a2a;border:1px solid #2d6b45;border-radius:14px;max-width:88%;}
.bb.sys{background:rgba(255,255,255,.05);border-radius:10px;padding:3px 14px;font-size:12px;color:#708499;max-width:90%;text-align:center;}

.bs{font-size:12px;font-weight:600;margin-bottom:2px;display:block;}
.bs.in{color:#64b5f6;}.bs.priv{color:#4caf76;}
.bt{color:#e8edf2;}
.btime{font-size:11px;color:#708499;text-align:right;margin-top:3px;display:block;}

.reply-bar{background:rgba(255,255,255,.07);border-left:3px solid #5288c1;border-radius:4px;padding:4px 8px;margin-bottom:5px;}
.reply-sender{font-size:11px;font-weight:600;color:#64b5f6;display:block;}
.reply-text{font-size:12px;color:#aab8c8;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px;}

.msg-actions{display:flex;flex-direction:column;gap:3px;opacity:0;transition:opacity .15s;}
.bw:hover .msg-actions{opacity:1;}
.react-pick-btn,.reply-btn{background:rgba(255,255,255,.08);border:none;border-radius:50%;width:26px;height:26px;cursor:pointer;font-size:13px;display:flex;align-items:center;justify-content:center;color:#aab8c8;padding:0;}
.react-pick-btn:hover,.reply-btn:hover{background:rgba(255,255,255,.15);}

.react-row{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px;padding:0 2px;}
.react-chip{background:#1c2b3a;border:1px solid #2b3f56;border-radius:20px;padding:2px 8px;font-size:13px;cursor:pointer;color:#e8edf2;transition:background .1s;}
.react-chip:hover{background:#263445;}

/* Emoji picker */
#emoji-picker{display:none;position:fixed;background:#1c2b3a;border:1px solid #232e3c;border-radius:12px;padding:8px;gap:6px;flex-wrap:wrap;z-index:100;box-shadow:0 4px 20px rgba(0,0,0,.5);}
#emoji-picker button{background:none;border:none;font-size:22px;cursor:pointer;padding:3px;border-radius:6px;}
#emoji-picker button:hover{background:rgba(255,255,255,.1);}

/* Инпут-бар */
#tg-input-bar{position:fixed;bottom:0;left:0;right:0;background:#1c2b3a;border-top:1px solid #232e3c;padding:8px 10px;display:flex;align-items:center;gap:8px;height:64px;z-index:50;}
.tg-input .q-field__control{background:#0e1621!important;border:1px solid #232e3c!important;border-radius:22px!important;color:#e8edf2!important;}
.tg-input .q-field__control:focus-within{border-color:#5288c1!important;}
.tg-input input{color:#e8edf2!important;font-family:'Inter',sans-serif!important;}
.tg-input .q-field__native::placeholder{color:#708499!important;}
.tg-select .q-field__control{background:#0e1621!important;border:1px solid #232e3c!important;border-radius:10px!important;}
.tg-select .q-field__native,.tg-select .q-field__label{color:#e8edf2!important;}
.tg-select .q-icon{color:#708499!important;}
.q-menu{background:#1c2b3a!important;border:1px solid #232e3c!important;border-radius:10px!important;}
.q-item{color:#e8edf2!important;}.q-item:hover{background:#263445!important;}
.login-wrap{background:#1c2b3a;border:1px solid #232e3c;border-radius:14px;padding:24px;min-width:300px;}
.login-wrap .q-field__control{background:#0e1621!important;border:1px solid #232e3c!important;border-radius:10px!important;}
.login-wrap input{color:#e8edf2!important;}
.login-wrap input::placeholder{color:#708499!important;}
</style>
<script>
var _replyTo = null;

function setReply(mid, sender, text) {
    _replyTo = {id: mid, sender: sender, text: text};
    var bar = document.getElementById('reply-preview');
    if (bar) {
        bar.style.display = 'flex';
        document.getElementById('reply-sender-lbl').textContent = sender;
        document.getElementById('reply-text-lbl').textContent = text;
        // Сдвигаем чат вверх
        document.getElementById('tg-messages').style.bottom = '104px';
    }
}
function clearReply() {
    _replyTo = null;
    var bar = document.getElementById('reply-preview');
    if (bar) bar.style.display = 'none';
    document.getElementById('tg-messages').style.bottom = '64px';
}
function getReply() { return _replyTo; }

var _pickerTarget = null;
function togglePicker(mid) {
    _pickerTarget = mid;
    var p = document.getElementById('emoji-picker');
    if (!p) return;
    if (p.style.display === 'flex') { p.style.display = 'none'; return; }
    p.style.display = 'flex';
}
function sendReaction(mid, emoji) {
    document.getElementById('emoji-picker').style.display = 'none';
    if (window._sendReactionPy) window._sendReactionPy(mid + '|' + emoji);
}

document.addEventListener('click', function(e) {
    var p = document.getElementById('emoji-picker');
    if (p && !p.contains(e.target) && !e.target.classList.contains('react-pick-btn')) {
        p.style.display = 'none';
    }
});
</script>
"""

EMOJI_PICKER_HTML = """
<div id="emoji-picker">
""" + "".join([f'<button onclick="sendReaction(_pickerTarget,\'{e}\')">{e}</button>' for e in REACTION_EMOJIS]) + """
</div>
<div id="reply-preview" style="display:none;background:#162230;border-left:3px solid #5288c1;padding:6px 12px;position:fixed;bottom:64px;left:0;right:0;z-index:40;align-items:center;justify-content:space-between;">
  <div style="overflow:hidden;">
    <span id="reply-sender-lbl" style="font-size:12px;font-weight:600;color:#64b5f6;display:block;"></span>
    <span id="reply-text-lbl" style="font-size:12px;color:#aab8c8;"></span>
  </div>
  <button onclick="clearReply()" style="background:none;border:none;color:#708499;font-size:18px;cursor:pointer;">✕</button>
</div>
"""


# ── Страница ───────────────────────────────────────────────────────────────────
@ui.page("/")
async def index(client: Client):
    cid = str(client.id)
    nick_box = {"v": None}
    queue: asyncio.Queue = asyncio.Queue()

    ui.add_head_html(STYLES)

    ui.html(f'''
      <div id="tg-header">
        <div id="tg-avatar">💬</div>
        <div>
          <div style="color:#e8edf2;font-size:15px;font-weight:600;">PyChat</div>
          <div id="online-lbl" style="color:#64b5f6;font-size:12px;">0 онлайн</div>
        </div>
      </div>
      <div id="tg-messages"></div>
      {EMOJI_PICKER_HTML}
    ''')

    def push_bubble(msg: dict):
        my_nick = nick_box["v"] or ""
        raw = bubble_html(msg, my_nick)
        esc = raw.replace("\\","\\\\").replace("`","\\`").replace("${","\\${")
        ui.run_javascript(f"""(function(){{
            var m=document.getElementById('tg-messages');
            if(!m)return;
            m.insertAdjacentHTML('beforeend',`{esc}`);
            m.scrollTop=m.scrollHeight;
        }})();""")

    def push_reaction(msg_id, data):
        js = reaction_js(msg_id, data)
        ui.run_javascript(js)

    # Слушатель очереди — работает в контексте этого клиента
    # Слушатель очереди — все JS вызовы внутри контекста клиента
    async def queue_worker():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=25)
                async with client:
                    kind = item[0]
                    if kind == "bubble":
                        push_bubble(item[1])
                    elif kind == "reaction":
                        push_reaction(item[1], item[2])
                    elif kind == "js":
                        ui.run_javascript(item[1])
            except asyncio.TimeoutError:
                async with client:
                    ui.run_javascript("void 0;")
            except Exception:
                break

    asyncio.ensure_future(queue_worker())

    # ── Панель ввода ──
    with ui.element("div").style(
        "position:fixed;bottom:0;left:0;right:0;"
        "background:#1c2b3a;border-top:1px solid #232e3c;"
        "padding:8px 10px;display:flex;align-items:center;gap:8px;height:64px;z-index:50;"
    ):
        target_sel = ui.select(options=["Всем"], value="Всем") \
            .props("outlined dense dark").classes("tg-select").style("width:110px;")
        msg_inp = ui.input(placeholder="Сообщение...") \
            .props("outlined dense").classes("tg-input").style("flex:1;")

        async def send():
            if not nick_box["v"]:
                return
            text = msg_inp.value.strip()
            if not text:
                return
            msg_inp.value = ""
            nick   = nick_box["v"]
            target = target_sel.value
            now    = ts()
            m_id   = new_id()

            # Получаем reply из JS
            reply_data = await ui.run_javascript("return getReply();")
            await ui.run_javascript("clearReply();")

            msg_out = {"id": m_id, "type": "outgoing", "sender": nick, "text": text, "time": now}
            msg_in  = {"id": m_id, "type": "incoming", "sender": nick, "text": text, "time": now}
            if reply_data:
                msg_out["reply_to"] = reply_data
                msg_in["reply_to"]  = reply_data

            if target == "Всем":
                push_bubble(msg_out)
                await broadcast(msg_in, skip_id=cid)
            else:
                push_bubble(msg_out)
                tid = next((c for c,s in sessions.items() if s["nickname"]==target), None)
                priv_in  = {**msg_in, "type":"private","sender":f"🔒 {nick} → тебе"}
                priv_out = {**msg_out,"type":"private","sender":f"🔒 ты → {target}","id":m_id}
                push_bubble(priv_out)
                if tid:
                    await sessions[tid]["queue"].put(("bubble", priv_in))

        msg_inp.on("keydown.enter", send)
        ui.button(icon="send", on_click=send).props("round unelevated") \
            .style("background:#5288c1;color:#fff;min-width:42px;height:42px;")

    async def refresh_select(all_nicks):
        opts = ["Всем"] + [n for n in all_nicks if n != nick_box["v"]]
        target_sel.options = opts
        if target_sel.value not in opts:
            target_sel.value = "Всем"

    # ── Реакции через JS callback ──
    async def handle_reaction(e):
        val = e.args
        if not val or "|" not in val:
            return
        msg_id, emoji = val.split("|", 1)
        nick = nick_box["v"]
        if not nick:
            return
        if msg_id not in reactions:
            reactions[msg_id] = {em: [] for em in REACTION_EMOJIS}
        lst = reactions[msg_id].setdefault(emoji, [])
        if nick in lst:
            lst.remove(nick)
        else:
            lst.append(nick)
        data = reactions[msg_id]
        push_reaction(msg_id, data)
        await broadcast_reaction(msg_id, skip_id=cid)

    ui.run_javascript("window._sendReactionPy = function(v){ emitEvent('reaction', v); };")
    ui.on("reaction", handle_reaction)

    # ── Логин ──
    with ui.dialog().props("persistent").style("z-index:200") as dlg:
        with ui.element("div").classes("login-wrap"):
            ui.label("👋 Войти в чат").style(
                "color:#e8edf2;font-size:17px;font-weight:600;margin-bottom:14px;display:block;"
            )
            nick_inp = ui.input(placeholder="Введи ник...") \
                .props("outlined dense").style("width:100%;")
            err_lbl = ui.label("").style("color:#ef5350;font-size:12px;min-height:18px;")

            async def login():
                nick = nick_inp.value.strip()
                if not nick:
                    err_lbl.text = "Введи ник"; return
                if nick in [s["nickname"] for s in sessions.values()]:
                    err_lbl.text = f"Ник «{nick}» занят"; return

                nick_box["v"] = nick
                sessions[cid] = {"nickname": nick, "queue": queue, "client": client}
                dlg.close()

                for m in history[-50:]:
                    push_bubble(m)
                    if m.get("id") in reactions:
                        push_reaction(m["id"], reactions[m["id"]])

                await _update_online()
                await _refresh_all_selects()
                await broadcast({"id":new_id(),"type":"system","text":f"{nick} присоединился 👋","time":ts()}, skip_id=cid)
                push_bubble({"id":new_id(),"type":"system","text":f"Привет, {nick}! 🎉","time":ts()})

            nick_inp.on("keydown.enter", login)
            ui.button("Войти →", on_click=login).style(
                "background:#5288c1;color:#fff;border-radius:8px;font-weight:600;width:100%;margin-top:8px;"
            ).props("unelevated")

    dlg.open()

    async def on_disconnect():
        nick = nick_box.get("v")
        sessions.pop(cid, None)
        if nick:
            await broadcast({"id":new_id(),"type":"system","text":f"{nick} вышел из чата","time":ts()})
            await _update_online()
            await _refresh_all_selects()

    client.on_disconnect(on_disconnect)


async def _update_online():
    count = len(sessions)
    js = f"var el=document.getElementById('online-lbl');if(el)el.textContent='{count} онлайн';"
    await broadcast_js(js)

async def _refresh_all_selects():
    nicks = [s["nickname"] for s in sessions.values()]
    for s in sessions.values():
        try:
            await s["queue"].put(("js", "void 0;"))  # wake up
        except Exception:
            pass
    # Обновляем через очередь — каждый сам обновит свой select
    # (select обновляется через refresh_select при следующем login/disconnect)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ui.run(
        host="0.0.0.0",
        port=port,
        title="PyChat",
        dark=True,
        reload=False,
        storage_secret="pychat-777",
        favicon="💬",
                    )
    
