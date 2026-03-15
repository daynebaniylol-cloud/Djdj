import asyncio
import os
from pywebio import start_server
from pywebio.input import input, TEXT, select
from pywebio.output import put_text, put_scrollable, put_markdown, output, put_buttons
from pywebio.session import run_async, run_js, info as session_info

# Храним пользователей: {никнейм: {'msg_box': объект_вывода, 'queue': очередь_сообщений}}
users = {}

async def main():
    put_markdown("## 🧊 Telegram-style Chat")
    
    nickname = await input("Твой ник:", required=True)
    if nickname in users:
        put_text("Этот ник занят!")
        return

    # Создаем область для вывода сообщений конкретно для этого юзера
    user_msg_box = output()
    users[nickname] = {'msg_box': user_msg_box, 'queue': asyncio.Queue()}
    
    put_scrollable(user_msg_box, height=300, keep_bottom=True)
    put_text(f"Привет, {nickname}! Выбери, кому писать.")

    # Фоновая задача для проверки новых сообщений
    run_async(listen_to_queue(nickname, user_msg_box))

    while True:
        target = await select("Кому:", options=["Общий чат", *[n for n in users if n != nickname]])
        msg = await input("Сообщение:")

        if target == "Общий чат":
            for n, data in users.items():
                await data['queue'].put(f"[{nickname} -> Всем]: {msg}")
        else:
            await users[target]['queue'].put(f"[{nickname} (ЛИЧКА)]: {msg}")

async def listen_to_queue(nickname, user_msg_box):
    """Слушает очередь сообщений пользователя"""
    while True:
        msg = await users[nickname]['queue'].get()
        user_msg_box.append(put_text(msg))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    start_server(main, port=port, host='0.0.0.0', cdn=False)
    
