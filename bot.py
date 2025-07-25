import discord
import os
from dotenv import load_dotenv
import json
import aiohttp
import asyncio
import socket
import re
from utils import update_item_data
from utils import build_index
from utils import search_items
from utils import format_item_short
from utils import mistrade_calculator
from utils import check_changed_item
from utils import check_parameter
from utils import manage_build
from utils import regular_expression
from utils import split_log_result

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
CURRENCYMAP = {
    "experience_bottle": "<:experience_bottle:1397875984484798475> XP",
    "dragon_breath": "<:concentrated_experience:1397875964796469389> CXP",
    "sunflower": "<:hyperexperience:1397875942000558223> HXP",
    "prismarine_shard": "<:crystalline_shard:1397875907338960986> CS",
    "prismarine_crystals": "<:compressed_crystalline_shard:1397875885146640404> CCS",
    "nether_star": "<:hyper_crystalline_shard:1397875853693554688> HCS",
    "gray_dye": "<:archos_ring:1397875715105624145> AR",
    "firework_star": "<:hyperchromatic_archos_ring:1397875820386848852> HAR"
}

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
    print(f"🟢 Bot 啟動於：{socket.gethostname()} | PID: {os.getpid()}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # ----------------- 查詢指令 -----------------
    if message.content.startswith('!find '):
        itemsToFind = message.content[len("!find"):].strip()
        if not itemsToFind:
            await message.channel.send("<:ghost_technology_4:1293185676086481039> 請提供要查詢的名稱。")
            return
        await message.channel.send('🔍 正在搜尋 ' + str(itemsToFind) + "...")

        results = search_items(itemsToFind, search_index)

        if not results:
            await message.channel.send("<:ghost_technology_4:1293185676086481039> 找不到符合物品。")
            return
        
        msg_lines = []
        for item in results[:5]:
            msg_lines.append( "\n ----------------------------------"  + "\n" + format_item_short(item))

        if len(results) > 5:
            msg_lines.append(f"...以及其他 {len(results)-5} 筆結果，請嘗試更精確的關鍵字。")

        await message.channel.send("\n".join(msg_lines))

    # ----------------- 尋找錯誤交易 -----------------
    if message.content.startswith('!mistrade'):
        doCalculateMistrader = False
        parameter = None
        if bool(re.search(r"b(\d+(?:\.\d+)?)\s+s(\d+(?:\.\d+)?)\s+(XP|CXP|HXP|CS|CCS|HCS|AR|HAR)\s+(0|1)", message.content, re.IGNORECASE)):
            start = message.content.rfind("<") + 1
            end = message.content.rfind(">")
            parameter = check_parameter(message.content[start:end])
            if parameter:
                doCalculateMistrader = True
            else:
                doCalculateMistrader = False
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
            await message.reply("<:ghost_technology_4:1293185676086481039> 請提供有效的內容或 .txt 附件。")
            return
        #過濾訊息
        filtered = {}
        pageDataTemp = []
        originMessage = ""
        with open("tradelog.txt", mode="r", encoding="utf-8") as file:
            lines = file.readlines()
            for i in range(len(lines)):
                regexResult = regular_expression(lines[i])
                if isinstance(regexResult, dict):
                    pageDataTemp.append(regexResult)
                elif isinstance(regexResult, tuple) and regexResult[0] > 0:
                    pageNumber = regexResult[0]
                    maxPageNumber = regexResult[1]
                    filtered.update({pageNumber:pageDataTemp})
                    pageDataTemp = []
        #計算結果
        if filtered:
            await message.reply(("<:ghost_technology_4:1293185676086481039> 參數格式錯誤，將不計算錯誤交易者。\n" if (not doCalculateMistrader and parameter != None) else "") + '<:ghost_technology:1292853415465975849> 正在計算交易結果...')
            #清除tradelog.txt
            with open("tradelog.txt", "w", encoding="utf-8") as f:
                f.write("")
            playerLog = {}
            doIgnoreShopkeeper = parameter.get("ignore", False) if isinstance(parameter, dict) else False
            pageResult = ""
            for pageNumber, pageData in filtered.items():
                result = check_changed_item(pageData, playerLog, doIgnoreShopkeeper)
                playerLog = result[1]
                pageResult += ("📄 以下是第**" + str(pageNumber) + "/" + str(maxPageNumber) + "**頁的結果: \n" + result[0])
            for log in split_log_result(pageResult):
                await message.channel.send(log)
            logResult = ""
            mistradeMessage = ""
            wrongPayment = {}
            wrongUsage = {}
            userMistraded = False
            #建立錯誤交易名單
            if doCalculateMistrader:
                wrongPayment, wrongUsage = mistrade_calculator(playerLog, parameter["target"], parameter["buyPrice"], parameter["sellPrice"])
            
            for playerName, changedItems in playerLog.items():
                fixedName = playerName.replace("_", "\\_")
                userMistraded = False
                mistradeMessage = ""
                if any(value != 0 for value in changedItems.values()):
                    #檢測玩家是否支付錯數量
                    if wrongPayment.get(playerName, False):
                        userMistraded = True
                        if wrongPayment[playerName] > 0:
                            mistradeMessage +=  f"@{fixedName} 多支付了 {wrongPayment[playerName]} 個 {parameter['target']} \n"
                        elif wrongPayment[playerName] < 0:
                            mistradeMessage += f"@{fixedName} 欠了 {-wrongPayment[playerName]} 個 {parameter['target']} \n"
                    #檢測玩家是否支付錯貨幣
                    if wrongUsage.get(playerName, False):
                        userMistraded = True
                        mistradeMessage += f"@{fixedName} 支付了錯誤的貨幣: {wrongUsage[playerName]} \n"
                    logResult += (":warning: <:ghost_technology_5:1293185945461461013> " if userMistraded else "") + "**" + fixedName + "**: \n"
                    for itemName, count in changedItems.items():
                        if count != 0:
                            logResult += " └ " + CURRENCYMAP.get(itemName, " ".join(word.capitalize() for word in itemName.split("_"))) + " " + str(count) + "\n"
                    if userMistraded:
                        logResult += "\n" + mistradeMessage
                    logResult += "\n"
            if logResult == "": logResult = "<:ghost_technology_4:1293185676086481039> 物品無變動"
            for log in split_log_result("# 📜 最終結果:" + "\n" + str(logResult)):
                await message.channel.send(log)
        else:
            await message.reply('<:ghost_technology_4:1293185676086481039> 格式錯誤')

    # ----------------- Menta職業建構者 -----------------
    if message.content.startswith('!build '):
        buildCommand = [word for word in message.content.split()]
        if len(buildCommand) >= 2:
            result = manage_build(buildCommand, message.author.name)
            await message.channel.send(result)
        else:
            await message.channel.send('<:ghost_technology_4:1293185676086481039> 格式錯誤')
            
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
            await message.channel.send("<:ghost_technology_4:1293185676086481039> 更新失敗，請稍後再試。")

client.run(TOKEN)