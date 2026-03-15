import asyncio
import os
from pywebio import start_server
from pywebio.input import input, TEXT
from pywebio.output import put_text, put_scrollable, put_markdown, output, put_buttons
from pywebio.session import run_async, run_js

chat_msgs = []

async def main():
    put_markdown("## 🧊 Чат запущен")
    msg_box = output()
    put_scrollable(msg_box, height=300, keep_bottom=True)

    # ОБЯЗАТЕЛЬНО await перед input
    nickname = await input("Введите ник:", type=TEXT, required=True)
    msg_box.append(put_markdown(f'📢 **{nickname}** зашел в чат'))

    refresh_task = run_async(refresh_msg(nickname, msg_box))

    while True:
        # ОБЯЗАТЕЛЬНО await перед input
        data = await input("Сообщение:", type=TEXT)
        msg_box.append(put_markdown(f"**{nickname}**: {data}"))
        chat_msgs.append((nickname, data))

async def refresh_msg(nickname, msg_box):
    last_idx = len(chat_msgs)
    while True:
        await asyncio.sleep(1)
        for m in chat_msgs[last_idx:]:
            if m[0] != nickname:
                msg_box.append(put_markdown(f"**{m[0]}**: {m[1]}"))
        last_idx = len(chat_msgs)

if __name__ == "__main__":
    # Порт для Render
    port = int(os.environ.get("PORT", 8080))
    start_server(main, port=port, host='0.0.0.0', cdn=False)
    
