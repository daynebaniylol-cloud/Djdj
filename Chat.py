import os
import asyncio
from datetime import datetime
from nicegui import ui, app, Client

# ── Состояние ──────────────────────────────────────────────────────────────────
history: list[dict] = []
sessions: dict = {}   # {client_id: {nickname, notify_fn, refresh_select}}


def ts():
    return datetime.now().strftime("%H:%M")


async def broadcast(msg: dict, skip_id=None, save=True):
    if save:
        history.append(msg)
        if len(history) > 200:
            history.pop(0)
    dead = []
    for cid, s in list(sessions.items()):
        if cid == skip_id:
            continue
        try:
            await s["notify_fn"](msg)
        except Exception:
            dead.append(cid)
    for d in dead:
        sessions.pop(d, None)


async def refresh_all_selects():
    nicks = [s["nickname"] for s in sessions.values()]
    for s in sessions.values():
        try:
            await s["refresh_select"](nicks)
        except Exception:
            pass


# ── CSS ────────────────────────────────────────────────────────────────────────
STYLES = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body, html {
    margin: 0; padding: 0;
    background: #17212b !important;
    font-family: 'Inter', sans-serif !important;
    height: 100%; overflow: hidden;
  }
  .nicegui-content { padding: 0 !important; background: #17212b !important; }
  .q-page { background: #17212b !important; }

  #tg-header {
    background: #1c2b3a; border-bottom: 1px solid #232e3c;
    padding: 10px 16px; display: flex; align-items: center;
    gap: 12px; height: 58px;
    position: fixed; top: 0; left: 0; right: 0; z-index: 50;
  }
  #tg-avatar {
    width: 40px; height: 40px; border-radius: 50%;
    background: linear-gradient(135deg, #5288c1, #3b82f6);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
  }
  #tg-messages {
    position: fixed; top: 58px; bottom: 64px;
    left: 0; right: 0; overflow-y: auto;
    padding: 10px 12px;
    background: #17212b;
  }
  #tg-messages::-webkit-scrollbar { width: 4px; }
  #tg-messages::-webkit-scrollbar-thumb { background: #2b3f56; border-radius: 2px; }
  #tg-input-bar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #1c2b3a; border-top: 1px solid #232e3c;
    padding: 8px 10px; display: flex; align-items: center;
    gap: 8px; height: 64px; z-index: 50;
  }

  .bw { display: flex; margin-bottom: 4px; animation: pop .15s ease; }
  @keyframes pop { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:none; } }
  .bw.out  { justify-content: flex-end; }
  .bw.in   { justify-content: flex-start; }
  .bw.priv { justify-content: center; }
  .bw.sys  { justify-content: center; }

  .bb {
    max-width: 72%; padding: 7px 11px 5px;
    font-size: 14px; line-height: 1.45; word-break: break-word;
  }
  .bb.out  { background: #2b5278; border-radius: 14px 14px 3px 14px; }
  .bb.in   { background: #182533; border: 1px solid #232e3c; border-radius: 14px 14px 14px 3px; }
  .bb.priv { background: #1a3a2a; border: 1px solid #2d6b45; border-radius: 14px; max-width: 88%; }
  .bb.sys  { background: rgba(255,255,255,.05); border-radius: 10px; padding: 3px 14px;
             font-size: 12px; color: #708499; max-width: 90%; text-align: center; }

  .bs { font-size: 12px; font-weight: 600; margin-bottom: 2px; display: block; }
  .bs.in   { color: #64b5f6; }
  .bs.priv { color: #4caf76; }
  .bt { color: #e8edf2; }
  .btime { font-size: 11px; color: #708499; text-align: right; margin-top: 3px; display: block; }

  .tg-input .q-field__control {
    background: #0e1621 !important; border: 1px solid #232e3c !important;
    border-radius: 22px !important; color: #e8edf2 !important;
  }
  .tg-input .q-field__control:focus-within { border-color: #5288c1 !important; }
  .tg-input input { color: #e8edf2 !important; font-family: 'Inter',sans-serif !important; }
  .tg-input .q-field__native::placeholder { color: #708499 !important; }

  .tg-select .q-field__control {
    background: #0e1621 !important; border: 1px solid #232e3c !important;
    border-radius: 10px !important;
  }
  .tg-select .q-field__native,
  .tg-select .q-field__label { color: #e8edf2 !important; }
  .tg-select .q-icon { color: #708499 !important; }

  .q-menu { background: #1c2b3a !important; border: 1px solid #232e3c !important; border-radius: 10px !important; }
  .q-item { color: #e8edf2 !important; }
  .q-item:hover { background: #263445 !important; }

  .login-wrap {
    background: #1c2b3a; border: 1px solid #232e3c;
    border-radius: 14px; padding: 24px; min-width: 300px;
  }
  .login-wrap .q-field__control {
    background: #0e1621 !important; border: 1px solid #232e3c !important;
    border-radius: 10px !important;
  }
  .login-wrap input { color: #e8edf2 !important; }
  .login-wrap input::placeholder { color: #708499 !important; }
</style>
"""


def make_bubble_html(msg: dict) -> str:
    mtype = msg.get("type", "in")
    text = msg.get("text", "").replace("<", "&lt;").replace(">", "&gt;")
    sender = msg.get("sender", "").replace("<", "&lt;")
    time = msg.get("time", "")

    if mtype == "system":
        return f'<div class="bw sys"><div class="bb sys">{text}</div></div>'
    if mtype == "outgoing":
        return f'<div class="bw out"><div class="bb out"><span class="bt">{text}</span><span class="btime">{time}</span></div></div>'
    if mtype == "private":
        return f'<div class="bw priv"><div class="bb priv"><span class="bs priv">{sender}</span><span class="bt">{text}</span><span class="btime">{time}</span></div></div>'
    # incoming
    return f'<div class="bw in"><div class="bb in"><span class="bs in">{sender}</span><span class="bt">{text}</span><span class="btime">{time}</span></div></div>'


# ── Страница ───────────────────────────────────────────────────────────────────
@ui.page("/")
async def index(client: Client):
    cid = str(client.id)
    nick_box = {"v": None}

    ui.add_head_html(STYLES)

    # Шапка
    ui.html('''
      <div id="tg-header">
        <div id="tg-avatar">💬</div>
        <div>
          <div style="color:#e8edf2;font-size:15px;font-weight:600;">PyChat</div>
          <div id="online-lbl" style="color:#64b5f6;font-size:12px;">0 онлайн</div>
        </div>
      </div>
      <div id="tg-messages"></div>
    ''')

    def push_bubble(msg: dict):
        raw = make_bubble_html(msg)
        # Экранируем для JS-строки
        escaped = raw.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        ui.run_javascript(f"""
            (function(){{
                var m = document.getElementById('tg-messages');
                if (!m) return;
                m.insertAdjacentHTML('beforeend', `{escaped}`);
                m.scrollTop = m.scrollHeight;
            }})();
        """)

    async def notify_fn(msg: dict):
        push_bubble(msg)

    # Панель ввода
    with ui.element("div").style(
        "position:fixed;bottom:0;left:0;right:0;"
        "background:#1c2b3a;border-top:1px solid #232e3c;"
        "padding:8px 10px;display:flex;align-items:center;gap:8px;height:64px;z-index:50;"
    ):
        target_sel = ui.select(options=["Всем"], value="Всем") \
            .props("outlined dense dark") \
            .classes("tg-select") \
            .style("width:110px;")

        msg_inp = ui.input(placeholder="Сообщение...") \
            .props("outlined dense") \
            .classes("tg-input") \
            .style("flex:1;")

        async def send():
            if not nick_box["v"]:
                return
            text = msg_inp.value.strip()
            if not text:
                return
            msg_inp.value = ""
            nick = nick_box["v"]
            target = target_sel.value
            now = ts()

            if target == "Всем":
                push_bubble({"type": "outgoing", "sender": nick, "text": text, "time": now})
                await broadcast({"type": "incoming", "sender": nick, "text": text, "time": now}, skip_id=cid)
            else:
                push_bubble({"type": "private", "sender": f"🔒 ты → {target}", "text": text, "time": now})
                tid = next((c for c, s in sessions.items() if s["nickname"] == target), None)
                if tid:
                    await sessions[tid]["notify_fn"](
                        {"type": "private", "sender": f"🔒 {nick} → тебе", "text": text, "time": now}
                    )

        msg_inp.on("keydown.enter", send)
        ui.button(icon="send", on_click=send) \
            .props("round unelevated") \
            .style("background:#5288c1;color:#fff;min-width:42px;height:42px;")

    async def refresh_select(all_nicks):
        opts = ["Всем"] + [n for n in all_nicks if n != nick_box["v"]]
        target_sel.options = opts
        if target_sel.value not in opts:
            target_sel.value = "Всем"

    # Логин диалог
    with ui.dialog().props("persistent").style("z-index:200") as dlg:
        with ui.element("div").classes("login-wrap"):
            ui.label("👋 Войти в чат").style(
                "color:#e8edf2;font-size:17px;font-weight:600;margin-bottom:14px;display:block;"
            )
            nick_inp = ui.input(placeholder="Введи ник...") \
                .props("outlined dense") \
                .style("width:100%;")
            err_lbl = ui.label("").style("color:#ef5350;font-size:12px;min-height:18px;")

            async def login():
                nick = nick_inp.value.strip()
                if not nick:
                    err_lbl.text = "Введи ник"
                    return
                taken = [s["nickname"] for s in sessions.values()]
                if nick in taken:
                    err_lbl.text = f"Ник «{nick}» уже занят"
                    return

                nick_box["v"] = nick
                sessions[cid] = {
                    "nickname": nick,
                    "notify_fn": notify_fn,
                    "refresh_select": refresh_select,
                }
                dlg.close()

                # Показываем историю
                for m in history[-50:]:
                    push_bubble(m)

                # Обновляем онлайн/список
                await _update_online_all()
                await refresh_all_selects()

                await broadcast(
                    {"type": "system", "text": f"{nick} присоединился 👋", "time": ts()},
                    skip_id=cid,
                )
                push_bubble({"type": "system", "text": f"Привет, {nick}! 🎉", "time": ts()})

            nick_inp.on("keydown.enter", login)
            ui.button("Войти →", on_click=login).style(
                "background:#5288c1;color:#fff;border-radius:8px;"
                "font-weight:600;width:100%;margin-top:8px;"
            ).props("unelevated")

    dlg.open()

    # Отключение
    async def on_disconnect():
        nick = nick_box.get("v")
        sessions.pop(cid, None)
        if nick:
            await broadcast({"type": "system", "text": f"{nick} вышел из чата", "time": ts()})
            await _update_online_all()
            await refresh_all_selects()

    client.on_disconnect(on_disconnect)


async def _update_online_all():
    count = len(sessions)
    # NiceGUI run_javascript без клиента обновляет все открытые страницы
    await ui.run_javascript(
        f"var el=document.getElementById('online-lbl'); if(el) el.textContent='{count} онлайн';"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ui.run(
        host="0.0.0.0",
        port=port,
        title="PyChat",
        dark=True,
        reload=False,
        storage_secret="pychat-secret-777",
        favicon="💬",
    )
  
