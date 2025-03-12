import logging  # ロギングを追加

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 環境変数からトークンを取得
token = os.getenv("DISCORD_TOKEN")

# トークンのチェック
if not token:
    logging.error("DISCORD_TOKEN is not set.")
    exit(1)
else:
    logging.info(f"Token successfully loaded: {token[:5]}****")  # トークンの一部のみ表示で安全性を確保

# Discord botの設定
intents = discord.Intents.default()
intents.members = True  # 新しいメンバーの参加を検知するために必要
client = discord.Client(intents=intents)

welcome_channel_id = 1165799413558542446  # ウェルカムメッセージを送信するチャンネルID
role_id = 1165785520593436764  # メンションしたいロールのID

# 管理者のDiscordユーザーIDリスト（複数登録）
admin_user_ids = [1073863060843937812, 1175571621025689661]  # 管理者のDiscordユーザーIDをリストに追加

welcome_sent = False  # フラグで送信状況を管理
wait_time = 50  # 秒単位の待機時間

# ヘルスチェック用のエンドポイント
async def health_check(request):
    logging.info("Health check endpoint was accessed!")  # ヘルスチェックリクエストのログ
    return web.json_response({"status": "ok"})

# aiohttpサーバーを起動
async def start_web_server():
    app = web.Application()
    app.router.add_get("/health", health_check)  # ヘルスチェックパスを追加
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))  # 環境変数PORTを取得
    logging.info(f"Starting web server on port {port}")  # サーバー起動のログ
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# 管理者にエラーメッセージを送信
async def notify_admins(error_message):
    for admin_user_id in admin_user_ids:
        try:
            admin_user = await client.fetch_user(admin_user_id)  # 管理者ユーザーを取得
            if admin_user:
                await admin_user.send(f"⚠️エラーが発生しました: {error_message}")
                logging.info(f"Admin {admin_user_id} notified about the error.")
            else:
                logging.warning(f"Admin user with ID {admin_user_id} not found.")
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_user_id}: {e}")

# WebSocket接続の切断時の対処
@client.event
async def on_disconnect():
    logging.warning("Disconnected from Discord. Reconnecting...")  # 接続切断時のログ
    while True:
        try:
            await client.connect()  # 再接続を試みる
            logging.info("Reconnected successfully.")
            break
        except Exception as e:
            logging.error(f"Reconnection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)  # 再接続待機時間

# プログラムのクラッシュを防ぐための対処と管理者通知
@client.event
async def on_error(event, *args, **kwargs):
    error_message = f"An error occurred in event '{event}': {args}, {kwargs}"
    logging.error(error_message)  # エラー内容をログに記録
    await notify_admins(error_message)  # エラーを管理者に通知

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')  # Botのログイン状況を記録

@client.event
async def on_member_join(member):
    global welcome_sent
    logging.info(f"New member joined: {member.name}")  # 新しいメンバー参加のログ
    try:
        channel = client.get_channel(welcome_channel_id)  # 特定のチャンネルを取得
        role = member.guild.get_role(role_id)  # サーバーからロールオブジェクトを取得

        if not welcome_sent and channel and role:
            logging.info("Sending welcome message.")  # メッセージ送信のログ
            welcome_sent = True
            await channel.send(f"こんにちは！{role.mention}の皆さん。「おしゃべりを始める前に、もういくつかステップが残っています。」と出ていると思うので、「了解」を押してルールに同意しましょう。その後にhttps://discord.com/channels/1165775639798878288/1165775640918773843で認証をして、みんなとお喋りをしましょう！")
            
            # 一定時間後にフラグをリセット
            await asyncio.sleep(wait_time)
            welcome_sent = False
        elif not channel:
            logging.warning("チャンネルが見つかりません。`welcome_channel_id`を正しい値に設定してください。")
        elif not role:
            logging.warning("ロールが見つかりません。`role_id`を正しい値に設定してください。")
    except Exception as e:
        error_message = f"Error in on_member_join: {e}"
        logging.error(error_message)
        await notify_admins(error_message)  # エラーを管理者に通知

# メイン関数でBotとWebサーバーを並行実行
async def main():
    logging.info("Starting main function.")  # メイン関数の起動ログ
    await asyncio.gather(
        client.start(token),  # Discord Botを起動
        start_web_server()    # ヘルスチェック用のWebサーバーを起動
    )

# 実行
if __name__ == "__main__":
    try:
        logging.info("Bot is starting...")  # スクリプト開始ログ
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutting down...")  # 終了時ログ
