import discord
import os
from dotenv import load_dotenv
import json
import aiohttp
import asyncio
from utils import update_item_data
from utils import build_index
from utils import search_items
from utils import format_item_short
from utils import mistrade_calculator
from utils import manage_build
from utils import regular_expression

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

BOT_ADMIN = {
    "ian0822", "1an0822", #擁有者
    ".ssusus.", "curtis_5566", "xmas__" #管理員
            } 

# ----------------- 載入資料並建立索引 -----------------
ITEM_DATA_PATH = "item_data.json"
item_data = {}
search_index = []

def load_and_index_data():
    global item_data, search_index
    with open(ITEM_DATA_PATH, "r", encoding="utf-8") as f:
        item_data = json.load(f)
    search_index = build_index(item_data)
    print("📦 物品資料載入完成，共載入", len(item_data), "筆資料")

load_and_index_data()

# ----------------- 主程式 -----------------
@client.event
async def on_ready():
    print(f'🤖 機器人已登入：{client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # ----------------- 查詢指令 -----------------
    if message.content.startswith('!find '):
        itemsToFind = message.content[len("!find"):].strip()
        if not itemsToFind:
            await message.channel.send("❌ 請提供要查詢的名稱。")
            return
        await message.channel.send('🔍 正在搜尋 ' + str(itemsToFind) + "...")

        results = search_items(itemsToFind, search_index)

        if not results:
            await message.channel.send("找不到符合物品。")
            return
        
        msg_lines = []
        for item in results[:5]:
            msg_lines.append( "\n ----------------------------------"  + "\n" + format_item_short(item))

        if len(results) > 5:
            msg_lines.append(f"...以及其他 {len(results)-5} 筆結果，請嘗試更精確的關鍵字。")

        await message.channel.send("\n".join(msg_lines))

    # ----------------- 尋找錯誤交易 -----------------
    #filtered = [match for log_line in message.content.split("\n") if (match := regular_expression(log_line))]
    if message.content.startswith('!mistrade'):
        originMessage = None
        # 1. 檢查附件
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.filename.endswith('.txt'):
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            with open(f'tradelog.txt', 'wb') as f:
                                f.write(data)
                            originMessage = "DONE"
        # 2. 沒有附件的情況：取 !mistrade 後面的文字
        else:
            originMessage = message.content[len("!mistrade "):].strip()
            with open("tradelog.txt", "w", encoding="utf-8") as f:
                f.write(originMessage)
        if not originMessage:
            await message.reply("❗請提供有效的內容或 .txt 附件。")
            return
        filtered = {}
        pageDataTemp = []
        originMessage = ""
        with open("tradelog.txt", mode="r", encoding="utf-8") as file:
            lines = file.readlines()
            for i in range(len(lines)):
                regexResult = regular_expression(lines[i])
                if isinstance(regexResult, dict):
                    pageDataTemp.append(regexResult)
                elif isinstance(regexResult, int) and regexResult > 0:
                    pageNumber = regexResult
                    filtered.update({pageNumber:pageDataTemp})
                    pageDataTemp = []
        
        if filtered:
            await message.reply('🧮 正在計算交易結果...')
            #清除tradelog.txt
            with open("tradelog.txt", "w", encoding="utf-8") as f:
                f.write("")
            for pageNumber, pageData in filtered.items():
                result = mistrade_calculator(pageData)
                await message.channel.send("以下是第" + str(pageNumber) + "頁的結果:" + "\n" + result)
        else:
            await message.reply('❌ 格式錯誤')

    # ----------------- Menta職業建構者 -----------------
    if message.content.startswith('!build '):
        buildCommand = [word for word in message.content.split()]
        if len(buildCommand) >= 2:
            result = manage_build(buildCommand, message.author.name)
            await message.channel.send(result)
        else:
            await message.channel.send('❌ 格式錯誤')
            

    # ----------------- 管理員功能 -----------------
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