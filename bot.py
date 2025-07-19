import discord
import os
from dotenv import load_dotenv
import json
import requests
from utils import update_item_data

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

BOT_ADMIN = {"ian0822", "1an0822"}

@client.event
async def on_ready():
    print(f'🤖 機器人已登入：{client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!find '):
        itemsToFind = message.content[len("!find"):].strip()
        await message.channel.send('🔍 正在搜尋 ' + str(itemsToFind) + "...")

    if message.content.startswith("!updateAPI"):
        username = message.author.name
        if username not in BOT_ADMIN:
            await message.channel.send(f"⛔ {username} 沒有權限更新資料。")
            return

        await message.channel.send(f"🔄 開始更新道具資料...")

        success = update_item_data()
        if success:
            await message.channel.send("✅ 成功更新道具資料！")
        else:
            await message.channel.send("❌ 更新失敗，請稍後再試。")

client.run(TOKEN)