import discord
from discord.ext import tasks
import asyncio
import os
from aiohttp import web  # ヘルスチェック用ライブラリ
import logging  # ログ用のライブラリ

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

# 管理者のDiscordユーザーIDリスト（複数登録）
admin_user_ids = [1073863060843937812, 1175571621025689661]  # 管理者のDiscordユーザーID

# 状態管理
welcome_sent = False  # フラグで送信状況を管理
wait_time = 50  # 秒単位の待機時間

# ロガーを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aiohttp.server")

# リクエストログを記録するミドルウェア
@web.middleware
async def log_requests(request, handler):
    peername = request.transport.get_extra_info("peername")  # クライアントIPとポート情報を取得
    client_ip = peername[0] if peername else "Unknown IP"   # IPアドレスを取得
    client_port = peername[1] if peername else "Unknown Port"  # ポート番号を取得
    logger.info(f"{client_ip}:{client_port} - {request.method} {request.path}")  # 詳細ログ出力
    response = await handler(request)  # ハンドラーでリクエストを処理
    return response

# ヘルスチェック用のエンドポイント
async def health_check(request):
    return web.json_response({"status": "ok"})

# aiohttpサーバーを起動
async def start_web_server():
    app = web.Application(middlewares=[log_requests])  # ミドルウェアをアプリに追加
    app.router.add_get("/health", health_check)  # ヘルスチェックパスを追加
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # ポート8080で起動
    await site.start()

# 管理者にエラーメッセージを送信
async def notify_admins(error_message):
    for admin_user_id in admin_user_ids:
        try:
            admin_user = await client.fetch_user(admin_user_id)  # 管理者ユーザーを取得
            if admin_user:
                await admin_user.send(f"⚠️エラーが発生しました: {error_message}")
                print(f"Admin {admin_user_id} notified about the error.")
            else:
                print(f"Admin user with ID {admin_user_id} not found.")
        except Exception as e:
            print(f"Failed to notify admin {admin_user_id}: {e}")

# WebSocket接続の切断時の対処
@client.event
async def on_disconnect():
    print("Disconnected from Discord. Reconnecting...")
    while True:
        try:
            await client.connect()  # 再接続を試みる
            print("Reconnected successfully.")
            break
        except Exception as e:
            print(f"Reconnection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)  # 再接続待機時間

# プログラムのクラッシュを防ぐための対処と管理者通知
@client.event
async def on_error(event, *args, **kwargs):
    error_message = f"An error occurred in event '{event}': {args}, {kwargs}"
    print(error_message)
    await notify_admins(error_message)  # エラーを管理者に通知

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

# 新しいメンバーが参加した際の処理
@client.event
async def on_member_join(member):
    global welcome_sent
    try:
        channel = client.get_channel(welcome_channel_id)  # 特定のチャンネルを取得
        role = member.guild.get_role(role_id)  # サーバーからロールオブジェクトを取得

        if not welcome_sent and channel and role:
            welcome_sent = True
            await channel.send(
                f"こんにちは！{role.mention}の皆さん。「おしゃべりを始める前に、もういくつかステップが残っています。」"
                f"と出ていると思うので、「了解」を押してルールに同意しましょう。その後に"
                f"https://discord.com/channels/1165775639798878288/1165775640918773843で"
                f"認証をして、みんなとお喋りをしましょう！"
            )
            # 一定時間後にフラグをリセット
            await asyncio.sleep(wait_time)
            welcome_sent = False
        elif not channel:
            print("チャンネルが見つかりません。`welcome_channel_id`を正しい値に設定してください。")
        elif not role:
            print("ロールが見つかりません。`role_id`を正しい値に設定してください。")
    except Exception as e:
        error_message = f"Error in on_member_join: {e}"
        print(error_message)
        await notify_admins(error_message)  # エラーを管理者に通知

# メイン関数でBotとWebサーバーを並行実行
async def main():
    await asyncio.gather(
        client.start(token),  # Discord Botを起動
        start_web_server()    # ヘルスチェック用のWebサーバーを起動
    )

# 実行
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down...")
