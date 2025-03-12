import discord
from discord.ext import tasks
import asyncio
import os
from aiohttp import web
import logging
from aiohttp import ClientSession
import re  # ログ内のエラー検出のために使用
from datetime import datetime, timedelta  # 時間操作のために使用

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
    client_ip = peername[0] if peername else "Unknown IP"
    client_port = peername[1] if peername else "Unknown Port"
    logger.info(f"{client_ip}:{client_port} - {request.method} {request.path}")
    response = await handler(request)
    return response

# ヘルスチェック用のエンドポイント
async def health_check(request):
    return web.json_response({"status": "ok"})

# aiohttpサーバーを起動
async def start_web_server():
    app = web.Application(middlewares=[log_requests])
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # ポート8080で起動
    await site.start()

# 定期PingをRenderに送信してアイドル状態を防ぐ
async def keep_alive():
    async with ClientSession() as session:
        while True:
            try:
                async with session.get("https://<your-app-url>.onrender.com/health") as resp:
                    print(f"Pinged Render: {resp.status}")
            except Exception as e:
                print(f"Failed to ping Render: {e}")
            await asyncio.sleep(300)  # 300秒（5分）ごとにPing

# 管理者にエラーメッセージを日本語で送信
async def notify_admins(error_message):
    for admin_user_id in admin_user_ids:
        try:
            admin_user = await client.fetch_user(admin_user_id)
            if admin_user:
                # 日本語でエラーメッセージを送信
                await admin_user.send(f"⚠️エラーが発生しました:\n{error_message}\n詳細を確認してください。")
                print(f"Admin {admin_user_id} に通知を送りました。")
            else:
                print(f"管理者ユーザーID {admin_user_id} が見つかりませんでした。")
        except Exception as e:
            print(f"管理者 {admin_user_id} への通知に失敗しました: {e}")

# WebSocket接続の切断時の自動再接続
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
    error_message = f"エラーが発生しました。イベント名: {event}, 引数: {args}, キーワード引数: {kwargs}"
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
            # 一定時間後にフラグをリセット
            await asyncio.sleep(wait_time)
            welcome_sent = False
        elif not channel:
            print("チャンネルが見つかりません。`welcome_channel_id`を正しい値に設定してください。")
        elif not role:
            print("ロールが見つかりません。`role_id`を正しい値に設定してください。")
    except Exception as e:
        error_message = f"新規メンバー参加時のエラー: {e}"
        print(error_message)
        await notify_admins(error_message)  # エラーを管理者に通知

# ログ監視タスクを追加
async def monitor_logs():
    log_file_path = "app.log"  # ログファイルのパスを指定
    last_report_time = datetime.now()  # 最後に正常性を報告した時間
    last_error_report_time = None
    error_detected = False
    error_count = 0

    while True:
        try:
            with open(log_file_path, "r") as log_file:
                lines = log_file.readlines()
                for line in lines:
                    # エラーパターンを検索
                    if re.search(r"ERROR|Exception", line, re.IGNORECASE):
                        error_detected = True
                        error_count += 1
                        print(f"エラー検出: {line.strip()}")  # コンソールにエラー出力

            now = datetime.now()

            # エラーが発生している場合は即座に通知
            if error_detected:
                if not last_error_report_time or (now - last_error_report_time).seconds >= 300:  # 5分間隔でエラー通知
                    await notify_admins(f"現在のログでエラーが {error_count} 件検出されました。ログを確認してください。")
                    last_error_report_time = now
                # 状態リセット
                error_detected = False
                error_count = 0

            # エラーがなく、1時間経過した場合に正常通知を送信
            if (now - last_report_time) >= timedelta(hours=1):
                await notify_admins("現在エラーは検出されていません。すべて正常です！")
                last_report_time = now

        except FileNotFoundError:
            print("ログファイルが見つかりません。ファイルパスを確認してください。")
        except Exception as e:
            print(f"ログ監視中にエラーが発生しました: {e}")

        await asyncio.sleep(60)  # 60秒ごとにログをチェック

# メイン関数でBotとWebサーバーを並行実行
async def main():
    await asyncio.gather(
        client.start(token),   # Discord Botを起動
        start_web_server(),    # ヘルスチェック用のWebサーバーを起動
        keep_alive(),          # 定期Pingタスクを実行
        monitor_logs()         # ログ監視タスクを実行
    )

# 実行
if __name__ == "__main__":
    try:
        asyncio.run(main())  # メイン関数を非同期で実行
    except KeyboardInterrupt:
        print("Bot shutting down...")
