import discord
from discord.ext import tasks
import asyncio
import os
from aiohttp import web
import logging
from aiohttp import ClientSession
from datetime import datetime
import time

# 環境変数からトークンを取得
token = os.getenv("DISCORD_TOKEN")

# トークンのチェック
if not token:
    print("Error: DISCORD_TOKEN is not set.")
    exit(1)
else:
    print(f"Token successfully loaded: {token[:5]}****")  # トークンの一部のみ表示で安全性を確保

# Discord botの設定
intents = discord.Intents.default()
intents.members = True  # 新しいメンバーの参加を検知するために必要
client = discord.Client(intents=intents)

# ウェルカムメッセージとロール設定
welcome_channel_id = 1165799413558542446  # ウェルカムメッセージを送信するチャンネルID
role_id = 1165785520593436764  # メンションしたいロールのID

# 管理者のDiscordユーザーIDリスト
admin_user_ids = [1073863060843937812, 1175571621025689661]  # 管理者のDiscordユーザーID

# DM送信対象のユーザーIDリスト
target_user_ids = [1175571621025689661, 1073863060843937812]  # DMを送信する対象ユーザーのID

# 状態管理
welcome_sent = False
wait_time = 50  # 秒単位の待機時間

# ロガーを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aiohttp.server")

# ロックの導入
lock = asyncio.Lock()

# 管理者に通知を送信する関数
async def notify_admins(message):
    """管理者にメッセージをDMで送信する"""
    for admin_user_id in admin_user_ids:
        try:
            admin_user = await client.fetch_user(admin_user_id)
            if admin_user:
                async with lock:  # ロックを使用してリソース競合を防止
                    await admin_user.send(message)
                print(f"管理者 {admin_user_id} にメッセージを送信しました。")
            else:
                print(f"管理者ユーザーID {admin_user_id} が見つかりませんでした。")
        except Exception as e:
            print(f"管理者 {admin_user_id} への通知に失敗しました: {e}")

# リクエストログを記録するミドルウェア（`/health`リクエストを除外）
@web.middleware
async def log_requests(request, handler):
    response = await handler(request)
    if request.path != "/health":
        peername = request.transport.get_extra_info("peername")
        client_ip = peername[0] if peername else "Unknown IP"
        client_port = peername[1] if peername else "Unknown Port"
        logger.info(f"{client_ip}:{client_port} - {request.method} {request.path}")
    return response

# ヘルスチェック用のエンドポイント
async def health_check(request):
    current_time = time.time()
    logger.info("Health check received")
    return web.json_response({"status": "ok"})

# aiohttpサーバーを起動
async def start_web_server():
    app = web.Application(middlewares=[log_requests])
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# 定期PingをRenderに送信してアイドル状態を防ぐ
async def keep_alive():
    async with ClientSession() as session:
        while True:
            try:
                async with session.get("https://bot-2ptf.onrender.com/health") as resp:
                    print(f"Pinged Render: {resp.status}")
            except Exception as e:
                print(f"Failed to ping Render: {e}")
            await asyncio.sleep(300)

# 複数ユーザーに1時間ごとにDMを送信するタスク
@tasks.loop(hours=1)
async def send_dm():
    """1時間ごとにユーザーにDMを送信し、結果を管理者に報告する"""
    no_errors = True
    for user_id in target_user_ids:
        try:
            user = await client.fetch_user(user_id)
            if user:
                async with lock:  # ロックを使用してリソース競合を防止
                    await user.send("これは1時間ごとのDMテストメッセージです。")
                print(f"DMを送信しました: {user.name}")
            else:
                print(f"指定されたユーザーが見つかりませんでした（ID: {user_id}）。")
        except Exception as e:
            no_errors = False
            error_message = f"ユーザーID {user_id} へのDM送信中にエラーが発生しました: {e}"
            print(error_message)
            await notify_admins(f"⚠️エラーが発生しました:\n{error_message}")

    if no_errors:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await notify_admins(f"✅ 過去1時間でエラーは発生しませんでした。\n実行時間: {current_time}")

# Bot起動時にタスクを確認し、開始
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    if not send_dm.is_running():
        print("send_dmタスクを開始します...")
        send_dm.start()
    else:
        print("send_dmタスクは既に実行中です。")

# 新しいメンバーが参加した際の処理
@client.event
async def on_member_join(member):
    global welcome_sent
    try:
        channel = client.get_channel(welcome_channel_id)
        role = member.guild.get_role(role_id)

        if not welcome_sent and channel and role:
            welcome_sent = True
            await channel.send(
                f"こんにちは！{role.mention}の皆さん。「おしゃべりを始める前に、もういくつかステップが残っています。」"
                f"と出ていると思うので、「了解」を押してルールに同意しましょう。その後に"
                f"https://discord.com/channels/1165775639798878288/1165775640918773843で"
                f"認証をして、みんなとお喋りをしましょう！"
            )
            await asyncio.sleep(wait_time)
            welcome_sent = False
        elif not channel:
            print("チャンネルが見つかりません。`welcome_channel_id`を正しい値に設定してください。")
        elif not role:
            print("ロールが見つかりません。`role_id`を正しい値に設定してください。")
    except Exception as e:
        error_message = f"新規メンバー参加時のエラー: {e}"
        print(error_message)
        await notify_admins(f"⚠️新規メンバー参加時のエラー:\n{error_message}")

# WebSocket切断時の再接続
@client.event
async def on_disconnect():
    print("Disconnected from Discord. Automatic reconnection will be handled.")  # 自動再接続に任せる

# メイン関数でBotとWebサーバーを並行実行
async def main():
    await asyncio.gather(
        client.start(token),   # Discord Botを起動
        start_web_server(),    # Webサーバーを起動
        keep_alive()           # RenderへのPingを実行
    )

# 実行
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down...")
