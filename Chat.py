import asyncio
import os
from datetime import datetime
from pywebio import start_server
from pywebio.input import input, select, textarea
from pywebio.output import put_html, put_scrollable, output, toast, put_markdown
from pywebio.session import run_async, run_js

# ─── Глобальное состояние ──────────────────────────────────────────────────────
users = {}           # {nickname: {'box': output(), 'queue': asyncio.Queue()}}
chat_history = []    # Список всех публичных сообщений (для истории новых юзеров)

TELEGRAM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

:root {
  --tg-bg:        #17212b;
  --tg-sidebar:   #0e1621;
  --tg-header:    #1c2b3a;
  --tg-bubble-in: #182533;
  --tg-bubble-out:#2b5278;
  --tg-accent:    #5288c1;
  --tg-accent2:   #64b5f6;
  --tg-text:      #e8edf2;
  --tg-sub:       #708499;
  --tg-border:    #232e3c;
  --tg-private:   #1a3a2a;
  --tg-private-border: #2d6b45;
  --radius:       12px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body, #pywebio {
  background: var(--tg-bg) !important;
  font-family: 'Inter', sans-serif !important;
  color: var(--tg-text) !important;
  min-height: 100vh;
}

/* Скрыть стандартные элементы PyWebIO */
#footer, .pywebio-logo { display: none !important; }

#pywebio-scope-ROOT {
  max-width: 780px;
  margin: 0 auto;
  padding: 0 !important;
}

/* ── Шапка чата ── */
.tg-header {
  background: var(--tg-header);
  border-bottom: 1px solid var(--tg-border);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.tg-header-avatar {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tg-accent), #3b82f6);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 600; color: #fff;
  flex-shrink: 0;
}
.tg-header-info { flex: 1; }
.tg-header-title { font-size: 15px; font-weight: 600; color: var(--tg-text); }
.tg-header-status { font-size: 12px; color: var(--tg-accent2); margin-top: 1px; }

/* ── Область сообщений ── */
.tg-messages-wrap {
  padding: 10px 12px;
  min-height: 60px;
}

/* ── Пузырьки ── */
.msg-row {
  display: flex;
  margin-bottom: 4px;
  animation: fadeIn .2s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.msg-row.outgoing { justify-content: flex-end; }
.msg-row.incoming { justify-content: flex-start; }
.msg-row.private  { justify-content: center; }

.msg-bubble {
  max-width: 72%;
  padding: 8px 12px 6px;
  border-radius: var(--radius);
  font-size: 14px;
  line-height: 1.45;
  word-break: break-word;
  position: relative;
}
.msg-row.outgoing .msg-bubble {
  background: var(--tg-bubble-out);
  border-bottom-right-radius: 4px;
}
.msg-row.incoming .msg-bubble {
  background: var(--tg-bubble-in);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--tg-border);
}
.msg-row.private .msg-bubble {
  background: var(--tg-private);
  border: 1px solid var(--tg-private-border);
  border-radius: var(--radius);
  font-size: 13px;
  max-width: 88%;
}

.msg-sender {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--tg-accent2);
  margin-bottom: 3px;
}
.msg-row.private .msg-sender { color: #4caf76; }

.msg-text { color: var(--tg-text); }

.msg-time {
  display: block;
  font-size: 11px;
  color: var(--tg-sub);
  text-align: right;
  margin-top: 4px;
}

/* ── Системное сообщение ── */
.msg-system {
  text-align: center;
  font-size: 12px;
  color: var(--tg-sub);
  margin: 8px 0;
  padding: 4px 12px;
  background: rgba(255,255,255,.04);
  border-radius: 10px;
  display: inline-block;
  margin-left: 50%;
  transform: translateX(-50%);
}

/* ── Форма ввода ── */
.card { background: transparent !important; border: none !important; box-shadow: none !important; }

.form-group label { color: var(--tg-sub) !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: .5px; }

input.form-control, select.form-control, textarea.form-control {
  background: var(--tg-header) !important;
  border: 1px solid var(--tg-border) !important;
  border-radius: 8px !important;
  color: var(--tg-text) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 14px !important;
  padding: 10px 14px !important;
  transition: border-color .2s;
}
input.form-control:focus, select.form-control:focus, textarea.form-control:focus {
  border-color: var(--tg-accent) !important;
  box-shadow: 0 0 0 3px rgba(82,136,193,.2) !important;
  outline: none !important;
}

.btn-primary {
  background: var(--tg-accent) !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  padding: 9px 20px !important;
  transition: background .2s, transform .1s;
}
.btn-primary:hover { background: #4a7ab0 !important; transform: translateY(-1px); }
.btn-primary:active { transform: translateY(0); }

/* scrollable override */
.pywebio-scrollable { background: transparent !important; border: none !important; }
</style>
"""

HEADER_HTML = """
<div class="tg-header">
  <div class="tg-header-avatar">💬</div>
  <div class="tg-header-info">
    <div class="tg-header-title">PyWebIO Chat</div>
    <div class="tg-header-status" id="online-count">онлайн</div>
  </div>
</div>
"""


def make_bubble(sender, text, msg_type="incoming", time_str=None):
    """msg_type: incoming | outgoing | private | system"""
    if time_str is None:
        time_str = datetime.now().strftime("%H:%M")
    if msg_type == "system":
        return f'<div class="msg-system">{text}</div>'
    sender_html = f'<span class="msg-sender">{sender}</span>' if sender else ""
    return f"""
<div class="msg-row {msg_type}">
  <div class="msg-bubble">
    {sender_html}
    <span class="msg-text">{text}</span>
    <span class="msg-time">{time_str}</span>
  </div>
</div>"""


def update_online_count():
    count = len(users)
    run_js(f"""
        var el = document.getElementById('online-count');
        if(el) el.textContent = '{count} онлайн';
    """)


async def broadcast(html_bubble, skip=None, save_to_history=True):
    """Рассылает HTML-пузырёк всем (кроме skip). Сохраняет в историю."""
    if save_to_history:
        chat_history.append(html_bubble)
        # Ограничиваем историю до 200 сообщений
        if len(chat_history) > 200:
            chat_history.pop(0)
    for nick, data in users.items():
        if nick != skip:
            await data['queue'].put(html_bubble)


async def main():
    run_js("document.title = 'TG Chat';")
    put_html(TELEGRAM_CSS)
    put_html(HEADER_HTML)

    # ── Логин ──
    nickname = await input("Твой никнейм:", type="text", required=True,
                           placeholder="например: Андрей")
    nickname = nickname.strip()
    if not nickname:
        put_html(make_bubble("", "Ник не может быть пустым", "system"))
        return
    if nickname in users:
        put_html(make_bubble("", f"Ник «{nickname}» уже занят!", "system"))
        return

    # ── Очередь и блок вывода сообщений ──
    user_box = output()
    users[nickname] = {'box': user_box, 'queue': asyncio.Queue()}

    # ── Показываем историю чата ──
    scrollable_area = put_scrollable(user_box, height=400, keep_bottom=True)

    if chat_history:
        # Загружаем историю в блок
        for hist_html in chat_history[-50:]:   # последние 50
            user_box.append(put_html(hist_html))

    # ── Приветствие ──
    join_html = make_bubble("", f"{nickname} присоединился(-ась) к чату 👋", "system")
    await broadcast(join_html, skip=nickname, save_to_history=True)
    user_box.append(put_html(make_bubble("", f"Привет, {nickname}! Это общий чат 🎉", "system")))

    update_online_count()

    # ── Фоновое получение сообщений ──
    run_async(_receive_loop(nickname, user_box))

    # ── Главный цикл отправки ──
    try:
        while True:
            opts = ["Всем в общий чат"] + [n for n in users if n != nickname]
            target = await select("Кому:", options=opts)
            msg = await input("Сообщение:", placeholder="Напиши что-нибудь…", required=True)
            if not msg.strip():
                continue

            now = datetime.now().strftime("%H:%M")

            if target == "Всем в общий чат":
                # Себе — outgoing, остальным — incoming
                out_html = make_bubble(nickname, msg, "outgoing", now)
                in_html  = make_bubble(nickname, msg, "incoming", now)
                user_box.append(put_html(out_html))
                await broadcast(in_html, skip=nickname, save_to_history=True)
                # Также добавляем outgoing версию в историю
                chat_history.append(in_html)
            else:
                # Личное сообщение
                priv_to_me   = make_bubble(f"🔒 {nickname} → тебе", msg, "private", now)
                priv_to_them = make_bubble(f"🔒 {nickname} → {target}", msg, "private", now)
                user_box.append(put_html(priv_to_them))
                if target in users:
                    await users[target]['queue'].put(priv_to_me)

    finally:
        # Пользователь отключился
        users.pop(nickname, None)
        leave_html = make_bubble("", f"{nickname} покинул(-а) чат", "system")
        await broadcast(leave_html, save_to_history=True)
        update_online_count()


async def _receive_loop(nickname, user_box):
    """Слушает очередь и рисует входящие пузырьки. asyncio.sleep(0) освобождает loop."""
    while nickname in users:
        try:
            msg_html = await asyncio.wait_for(
                users[nickname]['queue'].get(), timeout=0.5
            )
            user_box.append(put_html(msg_html))
        except asyncio.TimeoutError:
            await asyncio.sleep(0)   # ← отпускаем event loop, нет лага на фоне
        except Exception:
            break


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    start_server(main, port=port, host="0.0.0.0", cdn=False, debug=False)
    
