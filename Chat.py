import asyncio
import time
from pywebio import start_server
from pywebio.input import *
from pywebio.output import *
from pywebio.session import run_async, run_js, info as session_info

# ─── ГЛОБАЛЬНОЕ СОСТОЯНИЕ ───────────────────────────────────────────────────
chat_msgs   = {}   # { channel_id: [(nick, text, ts), ...] }
online_users = {}  # { nick: { color, channel } }
dm_msgs     = {}   # { "nick1::nick2": [(nick, text, ts), ...] }

CHANNELS = [
    {"id": "general",   "name": "general",   "icon": "#"},
    {"id": "offtopic",  "name": "offtopic",  "icon": "#"},
    {"id": "random",    "name": "random",    "icon": "#"},
    {"id": "voice1",    "name": "Голосовой", "icon": "🔊"},
]
MAX_MSGS = 200
COLORS = ["#5865f2","#23a55a","#f0b132","#e67e22","#e91e63","#00bcd4","#ff5722","#9c27b0"]

def get_color(nick):
    return COLORS[sum(ord(c) for c in nick) % len(COLORS)]

def ts():
    return time.strftime("%H:%M")

def dm_key(a, b):
    return "::".join(sorted([a, b]))

# ─── СТИЛИ ──────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #1e1f22 !important;
    color: #f2f3f5 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    height: 100vh; overflow: hidden;
}
#pywebio { padding: 0 !important; max-width: 100% !important; height: 100vh; overflow: hidden; }

/* Layout */
.chord-app {
    display: flex; height: 100vh; overflow: hidden;
}
.chord-sidebar {
    width: 68px; background: #1e1f22;
    display: flex; flex-direction: column; align-items: center;
    padding: 8px 0; gap: 4px; border-right: 1px solid #3f4147;
    overflow-y: auto; flex-shrink: 0;
}
.chord-channels {
    width: 220px; background: #2b2d31;
    display: flex; flex-direction: column;
    border-right: 1px solid #3f4147; flex-shrink: 0;
}
.chord-main {
    flex: 1; display: flex; flex-direction: column;
    background: #313338; overflow: hidden; min-width: 0;
}

/* Server icons */
.srv-icon {
    width: 48px; height: 48px; border-radius: 24px;
    background: #2b2d31; display: flex; align-items: center;
    justify-content: center; cursor: pointer; font-weight: 800;
    font-size: 16px; color: #b5bac1; flex-shrink: 0;
    transition: border-radius .2s, background .15s;
    position: relative;
}
.srv-icon:hover { border-radius: 14px; background: #5865f2; color: white; }
.srv-icon.active { border-radius: 14px; background: #5865f2; color: white; }
.srv-divider { width: 32px; height: 2px; background: #3f4147; border-radius: 1px; margin: 4px 0; }

/* Channel header */
.ch-header {
    height: 48px; background: #2b2d31;
    border-bottom: 1px solid #3f4147;
    display: flex; align-items: center;
    padding: 0 16px; font-weight: 700; font-size: 15px;
    box-shadow: 0 1px 8px rgba(0,0,0,.3); flex-shrink: 0;
    cursor: pointer; gap: 6px;
}
.ch-header svg { fill: #80848e; width: 16px; height: 16px; flex-shrink: 0; }

/* Online list */
.online-section { padding: 12px 8px 4px; font-size: 11px; font-weight: 700;
    letter-spacing: .7px; text-transform: uppercase; color: #80848e; }
.online-item {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 8px; border-radius: 6px; cursor: pointer;
    transition: background .1s; margin: 1px 4px;
}
.online-item:hover { background: #35373c; }
.online-dot { width: 10px; height: 10px; border-radius: 50%; background: #23a55a; flex-shrink: 0; }
.online-name { font-size: 14px; font-weight: 500; color: #b5bac1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Channel list */
.ch-item {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 8px 6px 16px; border-radius: 6px;
    cursor: pointer; color: #80848e; margin: 1px 8px;
    transition: background .1s, color .1s; font-size: 15px; font-weight: 500;
}
.ch-item:hover { background: #35373c; color: #b5bac1; }
.ch-item.active { background: #404249; color: #f2f3f5; }
.ch-prefix { font-size: 18px; font-weight: 600; color: #4e5058; margin-right: 2px; }

/* Chat header */
.chat-header {
    height: 48px; background: #313338;
    border-bottom: 1px solid #3f4147;
    display: flex; align-items: center; padding: 0 16px; gap: 8px;
    font-weight: 700; font-size: 15px;
    box-shadow: 0 1px 8px rgba(0,0,0,.25); flex-shrink: 0;
}
.chat-header-prefix { color: #80848e; font-size: 20px; }

/* Messages */
.messages-area {
    flex: 1; overflow-y: auto; padding: 16px 0 8px;
    display: flex; flex-direction: column;
}
.msg-group { padding: 2px 16px; animation: msgIn .14s ease; }
@keyframes msgIn { from { opacity:0; transform:translateY(3px); } to { opacity:1; } }
.msg-group.first { margin-top: 14px; }
.msg-hdr { display: flex; align-items: baseline; gap: 8px; margin-bottom: 2px; }
.msg-author { font-size: 15px; font-weight: 600; }
.msg-time { font-size: 11px; color: #80848e; }
.msg-body { font-size: 15px; line-height: 1.5; color: #dcddde; word-break: break-word; }
.msg-system { padding: 4px 16px; font-size: 13px; color: #80848e; font-style: italic; }

/* Input area */
.input-area {
    padding: 8px 16px 12px; background: #313338; flex-shrink: 0;
}
.input-box {
    display: flex; align-items: center; gap: 10px;
    background: #383a40; border-radius: 8px; padding: 11px 14px;
    border: 1.5px solid #3f4147;
    transition: border-color .15s;
}
.input-box:focus-within { border-color: #5865f2; }
.input-box input {
    flex: 1; background: none; border: none; outline: none;
    font-size: 15px; color: #f2f3f5; font-family: inherit;
}
.input-box input::placeholder { color: #80848e; }
.send-btn {
    background: #5865f2; color: white; border: none;
    border-radius: 6px; padding: 6px 14px; font-size: 14px;
    font-weight: 700; cursor: pointer; flex-shrink: 0;
    transition: background .15s, transform .1s;
    box-shadow: 0 2px 8px rgba(88,101,242,.4);
}
.send-btn:hover { background: #4752c4; }
.send-btn:active { transform: scale(.97); }

/* Auth screen */
.auth-screen {
    height: 100vh; display: flex; align-items: center; justify-content: center;
    background: #1e1f22;
}
.auth-card {
    background: #2b2d31; border-radius: 16px; padding: 36px 28px;
    width: 100%; max-width: 400px;
    box-shadow: 0 8px 32px rgba(0,0,0,.7);
}
.auth-logo {
    display: flex; flex-direction: column; align-items: center;
    gap: 10px; margin-bottom: 28px;
}
.auth-logo-icon {
    width: 64px; height: 64px; background: #5865f2;
    border-radius: 20px; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 20px rgba(88,101,242,.5);
    font-size: 32px;
}
.auth-logo h1 { font-size: 24px; font-weight: 800; }
.auth-logo p  { font-size: 14px; color: #b5bac1; }

/* DM panel */
.dm-panel {
    flex: 1; overflow-y: auto; padding: 8px 0;
}
.dm-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; border-radius: 8px; cursor: pointer;
    margin: 1px 6px; transition: background .1s;
}
.dm-item:hover { background: #35373c; }
.dm-ava {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 15px; color: white; flex-shrink: 0;
}
.dm-name { font-size: 15px; font-weight: 600; color: #b5bac1; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #3f4147; border-radius: 2px; }

/* Mobile */
@media (max-width: 600px) {
    .chord-sidebar { width: 56px; }
    .chord-channels { width: 180px; }
    .auth-card { margin: 16px; }
}
@media (max-width: 480px) {
    .chord-channels { display: none; }
}
</style>
"""

JS_SOUNDS = """
<script>
const _ac = new (window.AudioContext||window.webkitAudioContext)();
function _beep(f,t,v=0.12){
    try{
        const o=_ac.createOscillator(),g=_ac.createGain();
        o.connect(g);g.connect(_ac.destination);
        o.type='sine';o.frequency.value=f;
        g.gain.setValueAtTime(v,_ac.currentTime);
        g.gain.exponentialRampToValueAtTime(.001,_ac.currentTime+t);
        o.start();o.stop(_ac.currentTime+t);
    }catch(e){}
}
function sndSend(){ _beep(880,.1); }
function sndRecv(){ _beep(660,.18,.09); setTimeout(()=>_beep(880,.12,.07),80); }
function sndJoin(){ _beep(440,.12,.08); setTimeout(()=>_beep(660,.15,.08),100); }
</script>
"""

# ─── РЕНДЕР СООБЩЕНИЙ ────────────────────────────────────────────────────────
def render_msgs(msgs, my_nick, box):
    """Добавляет все сообщения в box"""
    prev_author = None
    for nick, text, t in msgs:
        is_system = nick == "📢"
        is_first  = nick != prev_author
        prev_author = nick

        if is_system:
            box.append(put_html(f'<div class="msg-system">{text}</div>'))
        else:
            color = get_color(nick)
            name_html = f'<span class="msg-author" style="color:{color}">{nick}</span>'
            time_html  = f'<span class="msg-time">{t}</span>'
            body_html  = f'<div class="msg-body">{text}</div>'
            cls = "msg-group first" if is_first else "msg-group"
            hdr = f'<div class="msg-hdr">{name_html}{time_html}</div>' if is_first else ""
            box.append(put_html(f'<div class="{cls}">{hdr}{body_html}</div>'))

# ─── ГЛАВНАЯ ФУНКЦИЯ ─────────────────────────────────────────────────────────
async def main():
    global chat_msgs, online_users, dm_msgs

    # Инжектим CSS + звуки
    put_html(CSS + JS_SOUNDS)

    # ── АВТОРИЗАЦИЯ ──────────────────────────────────────────────────────────
    put_html('<div class="auth-screen"><div class="auth-card">')
    put_html('''
        <div class="auth-logo">
            <div class="auth-logo-icon">💬</div>
            <h1>Chord</h1>
            <p>Добро пожаловать!</p>
        </div>
    ''')

    nickname = await input(
        "Введи никнейм",
        required=True,
        placeholder="cooluser",
        validate=lambda n: "Ник занят!" if n in online_users else
                           "Минимум 2 символа" if len(n.strip()) < 2 else None
    )
    nickname = nickname.strip()

    put_html('</div></div>')
    clear()  # убираем auth screen

    # Регистрируем юзера
    my_color = get_color(nickname)
    online_users[nickname] = {"color": my_color, "channel": "general"}

    # Инициализируем каналы
    for ch in CHANNELS:
        if ch["id"] not in chat_msgs:
            chat_msgs[ch["id"]] = []

    # Системное сообщение о входе
    join_text = f"**{nickname}** присоединился к чату"
    for ch in CHANNELS:
        if ch["icon"] == "#":
            chat_msgs[ch["id"]].append(("📢", join_text, ts()))
    run_js("sndJoin()")

    # При выходе
    async def on_close():
        if nickname in online_users:
            del online_users[nickname]
        leave_text = f"**{nickname}** покинул чат"
        for ch in CHANNELS:
            if ch["icon"] == "#":
                chat_msgs[ch["id"]].append(("📢", leave_text, ts()))
    from pywebio.session import defer_call
    defer_call(on_close)

    # ── ГЛАВНЫЙ LAYOUT ───────────────────────────────────────────────────────
    current_channel = "general"
    current_view    = "channel"  # channel | dm
    current_dm_peer = None

    put_html('<div class="chord-app" id="chord-app">')

    # Сайдбар серверов
    put_html('''
    <div class="chord-sidebar">
        <div class="srv-icon active" title="Chord Global" onclick="switchView('global')">C</div>
        <div class="srv-divider"></div>
        <div class="srv-icon" title="Добавить сервер" style="color:#23a55a;font-size:24px;">+</div>
    </div>
    ''')

    # Панель каналов
    channels_html = '<div class="chord-channels">'
    channels_html += '<div class="ch-header">💬 Chord<svg viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z"/></svg></div>'
    channels_html += '<div style="padding:8px 0">'
    channels_html += '<div class="online-section">Текстовые каналы</div>'
    for ch in CHANNELS:
        active = "active" if ch["id"] == current_channel else ""
        channels_html += f'''
        <div class="ch-item {active}" id="ch-{ch["id"]}"
             onclick="document.getElementById('ch-input').focus()">
            <span class="ch-prefix">{ch["icon"]}</span>{ch["name"]}
        </div>'''
    channels_html += '</div>'
    channels_html += '<div class="online-section" style="margin-top:8px;">В сети</div>'
    channels_html += '<div id="online-list">'
    for u in list(online_users.keys()):
        c = get_color(u)
        channels_html += f'''<div class="online-item">
            <div class="online-dot"></div>
            <span class="online-name" style="color:{c}">{u}</span>
        </div>'''
    channels_html += '</div></div>'
    put_html(channels_html)

    # Главная область
    put_html('<div class="chord-main">')
    put_html(f'<div class="chat-header"><span class="chat-header-prefix">#</span>{current_channel}</div>')

    # Область сообщений
    msg_box = output()
    put_html('<div class="messages-area" id="messages-area">')
    put_scrollable(msg_box, height=None, keep_bottom=True)
    put_html('</div>')

    # Рендерим историю
    render_msgs(chat_msgs.get(current_channel, []), nickname, msg_box)

    # Поле ввода
    put_html('</div></div>')  # close chord-main, chord-app

    # ── ЧАТ LOOP ─────────────────────────────────────────────────────────────
    # Фоновая задача — опрос новых сообщений
    last_idx = {ch["id"]: len(chat_msgs.get(ch["id"], [])) for ch in CHANNELS}

    async def poll_messages():
        while True:
            await asyncio.sleep(0.8)
            msgs = chat_msgs.get(current_channel, [])
            new = msgs[last_idx.get(current_channel, 0):]
            if new:
                for nick, text, t in new:
                    is_system = nick == "📢"
                    is_first  = True  # упрощённо
                    color = get_color(nick)
                    if is_system:
                        msg_box.append(put_html(f'<div class="msg-system">{text}</div>'))
                    else:
                        name_html = f'<span class="msg-author" style="color:{color}">{nick}</span>'
                        body_html = f'<div class="msg-body">{text}</div>'
                        hdr = f'<div class="msg-hdr">{name_html}<span class="msg-time">{t}</span></div>'
                        msg_box.append(put_html(f'<div class="msg-group first">{hdr}{body_html}</div>'))
                        if nick != nickname:
                            run_js("sndRecv()")
                last_idx[current_channel] = len(msgs)

            # Чистим старые сообщения
            for ch_id in list(chat_msgs.keys()):
                if len(chat_msgs[ch_id]) > MAX_MSGS:
                    chat_msgs[ch_id] = chat_msgs[ch_id][MAX_MSGS // 2:]

    poll_task = run_async(poll_messages())

    # Основной input loop
    while True:
        data = await input_group("", [
            input(
                placeholder=f"Написать в #{current_channel}",
                name="msg",
                help_text="",
            ),
            actions(name="cmd", buttons=[
                {"label": "Отправить", "value": "send", "color": "primary"},
                *[{"label": f"#{ch['name']}", "value": f"ch:{ch['id']}"} for ch in CHANNELS if ch["icon"] == "#"],
                {"label": "Выйти", "value": "exit", "type": "cancel"},
            ])
        ], validate=lambda d: ("msg", "Пустое сообщение!") if d["cmd"] == "send" and not d["msg"].strip() else None)

        if data is None or data["cmd"] == "exit":
            break

        cmd = data["cmd"]

        # Переключение канала
        if cmd.startswith("ch:"):
            new_ch = cmd[3:]
            current_channel = new_ch
            online_users[nickname]["channel"] = new_ch
            # Показываем историю нового канала
            msg_box.append(put_html(f'<div class="msg-system">── Переключился на #{new_ch} ──</div>'))
            render_msgs(chat_msgs.get(new_ch, [])[-20:], nickname, msg_box)
            last_idx[new_ch] = len(chat_msgs.get(new_ch, []))
            continue

        # Отправка сообщения
        text = data["msg"].strip()
        if not text:
            continue

        chat_msgs[current_channel].append((nickname, text, ts()))
        run_js("sndSend()")

    poll_task.close()
    toast("Вы вышли из Chord")
    clear()
    put_html('''
        <div style="height:100vh;display:flex;align-items:center;justify-content:center;background:#1e1f22;flex-direction:column;gap:16px;">
            <div style="font-size:48px;">👋</div>
            <div style="font-size:20px;font-weight:700;color:#f2f3f5;">До встречи!</div>
            <button onclick="location.reload()" style="background:#5865f2;color:white;border:none;padding:12px 24px;border-radius:8px;font-size:16px;font-weight:700;cursor:pointer;">Войти снова</button>
        </div>
    ''')


if __name__ == "__main__":
    print("╔══════════════════════════════════════╗")
    print("║         Chord Chat Server            ║")
    print("╠══════════════════════════════════════╣")
    print("║  Локальный:  http://localhost:8080   ║")
    print("║  Для друзей: http://ВАШ_IP:8080      ║")
    print("║  (друзья должны быть в одной сети)   ║")
    print("╚══════════════════════════════════════╝")
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"\n  Твой IP: http://{local_ip}:8080\n")
    except:
        pass

    import os
    port = int(os.environ.get('PORT', 8080))
    start_server(main, debug=False, port=port, cdn=False)
                   
