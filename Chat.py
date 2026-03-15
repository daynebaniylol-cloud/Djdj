import asyncio
import os
from pywebio import start_server
from pywebio.input import *
from pywebio.output import *
from pywebio.session import run_async, run_js

chat_msgs = []
online_users = set()

async def main():
    put_markdown("## Чат работает")
    msg_box = output()
    put_scrollable(msg_box, height=300, keep_bottom=True)

    nickname = await input("Имя:", required=True)
    online_users.add(nickname)
    msg_box.append(put_markdown(f'📢 {nickname} зашел'))

    refresh_task = run_async(refresh_msg(nickname, msg_box))

    while True:
        data = await input("Сообщение:", name="msg")
        msg_box.append(put_markdown(f"{nickname}: {data}"))
        chat_msgs.append((nickname, data))

async def refresh_msg(nickname, msg_box):
    last_idx = len(chat_msgs)
    while True:
        await asyncio.sleep(1)
        for m in chat_msgs[last_idx:]:
            if m[0] != nickname:
                msg_box.append(put_markdown(f"{m[0]}: {m[1]}"))
        last_idx = len(chat_msgs)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    start_server(main, port=port, host='0.0.0.0', cdn=False)

