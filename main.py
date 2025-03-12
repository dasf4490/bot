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
intents.members = True
client = discord.Client(intents=intents)

# ヘルスチェック用のエンドポイント
async def health_check(request):
    return web.json_response({"status": "ok"})  # ヘルスチェック用レスポンス

async def root_health_check(request):
    return web.json_response({"status": "ok"})  # ルートパス用レスポンス

# aiohttpサーバーを起動
async def start_web_server():
    app = web.Application()
    app.router.add_get("/health", health_check)  # `/health` パスを設定
    app.router.add_get("/", root_health_check)  # `/` パスを設定
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # ポート8080で起動
    await site.start()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

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
