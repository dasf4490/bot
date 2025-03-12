import discord
from discord.ext import tasks
import asyncio
import os
from aiohttp import web  # ヘルスチェック用ライブラリ

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

welcome_channel_id = 1165799413558542446  # ウェルカムメッセージを送信するチャンネルID
role_id = 1165785520593436764  # メンションしたいロールのID
welcome_sent = False  # フラグで送信状況を管理
wait_time = 20  # 秒単位の待機時間

# ヘルスチェック用のエンドポイント
async def health_check(request):
    return web.json_response({"status": "ok"})

# aiohttpサーバーを起動
async def start_web_server():
    app = web.Application()
    app.router.add_get("/health", health_check)  # ヘルスチェックパスを追加
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # ポート8080で起動
    await site.start()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_member_join(member):
    global welcome_sent
    channel = client.get_channel(welcome_channel_id)  # 特定のチャンネルを取得
    role = member.guild.get_role(role_id)  # サーバーからロールオブジェクトを取得

    if not welcome_sent and channel and role:
        welcome_sent = True
        await channel.send(f"こんにちは！{role.mention}の皆さん。「おしゃべりを始める前に、もういくつかステップが残っています。」と出ていると思うので、「了解」を押してルールに同意しましょう。その後にhttps://discord.com/channels/1165775639798878288/1165775640918773843で認証をして、みんなとお喋りをしましょう！ ")
        
        # 一定時間後にフラグをリセット
        await asyncio.sleep(wait_time)
        welcome_sent = False
    elif not channel:
        print("チャンネルが見つかりません。`welcome_channel_id`を正しい値に設定してください。")
    elif not role:
        print("ロールが見つかりません。`role_id`を正しい値に設定してください。")

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
