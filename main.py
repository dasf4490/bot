import discord
from discord.ext import tasks
import asyncio
import os
from flask import Flask
from threading import Thread

# Flaskウェブサーバーの設定
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

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
wait_time = 50  # 秒単位の待機時間

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

# ウェブサーバーを起動して稼働状態を維持
keep_alive()

# ボットを起動
client.run(token)
