import discord
import os
from dotenv import load_dotenv

load_dotenv()  # 載入.env的變數

TOKEN = os.getenv('DISCORD_TOKEN')  # 從環境變數讀取Token

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'🤖 機器人已登入：{client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!查道具'):
        await message.channel.send('🔍 請問你要查詢哪個道具？')

client.run(TOKEN)