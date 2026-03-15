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
  --tg-bg:         #17212b;
  --tg-header:     #1c2b3a;
  --tg-bubble-in:  #182533;
  --tg-bubble-out: #2b5278;
  --tg-accent:     #5288c1;
  --tg-accent2:    #64b5f6;
  --tg-text:       #e8edf2;
  --tg-sub:        #708499;
  --tg-border:     #232e3c;
  --tg-private:    #1a3a2a;
  --tg-private-bd: #2d6b45;
  --radius:        12px;
}

*, *::before, *::after { box-sizing: border-box; }

/* ── Глобальный фон — перебиваем Bootstrap/PyWebIO ── */
html, body,
.container, .container-fluid,
#pywebio, #pywebio-body,
[id^="pywebio"] {
  background: var(--tg-bg) !important;
  font-family: 'Inter', sans-serif !important;
  color: var(--tg-text) !important;
}

/* ── Карточки форм ── */
.card, .card-body {
  background: var(--tg-header) !important;
  border: 1px solid var(--tg-border) !important;
  border-radius: var(--radius) !important;
  box-shadow: none !important;
  color: var(--tg-text) !important;
}

#footer, .pywebio-logo { display: none !important; }

#pywebio-scope-ROOT {
  max-width: 780px;
  margin: 0 auto;
  padding: 0 0 20px !important;
}

/* ── Шапка ── */
.tg-header {
  background: var(--tg-header);
  border-bottom: 1px solid var(--tg-border);
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 100;
  margin-bottom: 8px;
}
.tg-header-avatar {
  width: 42px; height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tg-accent), #3b82f6);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
}
.tg-header-title  { font-size: 15px; font-weight: 600; color: var(--tg-text); }
.tg-header-status { font-size: 12px; color: var(--tg-accent2); margin-top: 2px; }

/* ── Scrollable (область сообщений) ── */
.pywebio-scrollable {
  background: var(--tg-bg) !important;
  border: 1px solid var(--tg-border) !important;
  border-radius: var(--radius) !important;
  min-height: 300px !important;
  margin: 0 12px 12px !important;
  padding: 8px 4px !important;
}

/* ── Пузырьки ── */
.msg-row {
  display: flex;
  margin-bottom: 4px;
  animation: fadeIn .18s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to   { opacity: 1; transform: none; }
}
.msg-row.outgoing { justify-content: flex-end; }
.msg-row.incoming { justify-content: flex-start; }
.msg-row.private  { justify-content: center; }

.msg-bubble {
  max-width: 74%;
  padding: 7px 11px 5px;
  border-radius: var(--radius);
  font-size: 14px;
  line-height: 1.45;
  word-break: break-word;
}
.msg-row.outgoing .msg-bubble {
  background: var(--tg-bubble-out);
  border-bottom-right-radius: 3px;
}
.msg-row.incoming .msg-bubble {
  background: var(--tg-bubble-in);
  border: 1px solid var(--tg-border);
  border-bottom-left-radius: 3px;
}
.msg-row.private .msg-bubble {
  background: var(--tg-private);
  border: 1px solid var(--tg-private-bd);
  font-size: 13px;
  max-width: 90%;
}
.msg-sender {
  display: block;
  font-size: 12px; font-weight: 600;
  color: var(--tg-accent2);
  margin-bottom: 3px;
}
.msg-row.private .msg-sender { color: #4caf76; }
.msg-text  { color: var(--tg-text); }
.msg-time  {
  display: block; font-size: 11px;
  color: var(--tg-sub); text-align: right;
  margin-top: 4px;
}
.msg-system {
  text-align: center; font-size: 12px;
  color: var(--tg-sub); margin: 6px auto;
  padding: 3px 14px;
  background: rgba(255,255,255,.04);
  border-radius: 10px; display: table;
}

/* ── Форма: метки ── */
label, .form-group label, .control-label {
  color: var(--tg-sub) !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  text-transform: uppercase;
  letter-spacing: .5px;
}

/* ── Поля ввода ── */
input.form-control,
select.form-control,
textarea.form-control {
  background: #0e1621 !important;
  border: 1px solid var(--tg-border) !important;
  border-radius: 8px !important;
  color: var(--tg-text) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 14px !important;
  padding: 10px 14px !important;
  transition: border-color .2s;
}
input.form-control:focus,
select.form-control:focus,
textarea.form-control:focus {
  border-color: var(--tg-accent) !important;
  box-shadow: 0 0 0 3px rgba(82,136,193,.25) !important;
  background: #0e1621 !important;
}
/* Цвет текста в option-ах (нужен для Firefox) */
select.form-control option { background: #1c2b3a; color: var(--tg-text); }

/* ── Кнопки ── */
.btn-primary, .btn-success {
  background: var(--tg-accent) !important;
  border-color: var(--tg-accent) !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  color: #fff !important;
  padding: 9px 22px !important;
  transition: background .2s, transform .1s;
}
.btn-primary:hover, .btn-success:hover { background: #4175a8 !important; }

/* Жёлтая кнопка "Сброс" — перекрашиваем */
.btn-warning, .btn-secondary, .btn-default {
  background: #263445 !important;
  border-color: var(--tg-border) !important;
  color: var(--tg-sub) !important;
  border-radius: 8px !important;
  padding: 9px 22px !important;
}
.btn-warning:hover, .btn-secondary:hover {
  background: #2e3f55 !important;
  color: var(--tg-text) !important;
}
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
  
