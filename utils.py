import json
import os
import requests
import re
#import google.generativeai as genai
from urllib.parse import urlparse, parse_qs


def update_item_data():
    url = "https://api.playmonumenta.com/items"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        with open("item_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("✅ 成功更新 item_data.json！")
        return True

    except requests.RequestException as e:
        print(f"❌ 無法連線 API：{e}")
        return False
    
def build_index(data):
    #將資料名稱轉成小寫後儲存
    index = []
    for item_key, item in data.items():
        masterwork = int(item.get("masterwork", -1))
        if masterwork == -1 or masterwork >= 4:
            name = item.get("name", item_key).lower()
            index.append((item, name))
    return index

def search_items(query, index):
    #查詢時直接比對是否為子字串
    query_string = query.lower().strip()
    results = []
    for item, name in index:
        if query_string in name:
            results.append(item)
    return results

def format_stat_key(key: str) -> str:
    # 移除 _percent 或 _flat
    for suffix in ["_percent", "_flat"]:
        if key.endswith(suffix):
            key = key[:-len(suffix)]
            break
    # 每個詞首字母大寫
    return " ".join(word.capitalize() for word in key.split("_"))

def format_stat_value(value, locked: bool, is_percent: bool) -> str:
    if isinstance(value, float):
        value = round(value, 2)
    result = f"+ {value}" if value > 0 else  f"- {-value}"
    if is_percent:
        result += "%"
    if locked:
        result += "🔒"
    return result

def format_item_short(item):
    lines = []

    # 第一行：名稱
    name = item.get("name", "")
    masterwork = item.get("masterwork", -1)
    lines.append(name + " " + (masterwork + "★") if masterwork != -1 else name)

    # 第二行：類型與基底物品
    item_type = item.get("type")
    base_item = item.get("base_item")
    if item_type and base_item:
        lines.append(f"{item_type} - {base_item}")
    elif item_type:
        lines.append(item_type)

    # 第三行：Charm Power + Class
    if item_type and "charm" in item_type.lower():
        power = item.get("power")
        class_name = item.get("class_name")
        power_str = f"Charm Power: {'★' * power}" if power else None
        class_str = f"{class_name}" if class_name else None
        if power_str or class_str:
            lines.append(" - ".join(filter(None, [power_str, class_str])))

    # 第四行：stat
    stats = item.get("stats", {})
    for key, stat_value in stats.items():
        # 是否為 dict 結構（有 locked / value）
        if isinstance(stat_value, dict):
            value = stat_value.get("value")
            locked = stat_value.get("locked", False)
        else:
            value = stat_value
            locked = False

        is_percent = key.endswith("_percent")
        stat_name = format_stat_key(key)
        value_str = format_stat_value(value, locked, is_percent)
        lines.append(f"└ {stat_name} {value_str}")

    # 最後一行 : 地區、稀有度、類型、位置
    region = item.get("region")
    tier = item.get("tier")
    location = item.get("location")
    meta = " ".join(filter(None, [region, location, tier]))
    if meta:
        lines.append(meta)

    return "\n".join(lines)



    # 嘗試頁碼
    match = page_pattern.search(log_line)
    if match:
        current_page = int(match.group(1))
        total_pages = int(match.group(2))
        return (current_page, total_pages)

    return False

def strip_minecraft_color_codes(text):
    return re.sub(r'§.', '', text)

def regular_expression(log_line):
    # 含色碼版本
    color_action_pattern = re.compile(
        r'^\[\d{2}:\d{2}:\d{2}\] \[Render thread/INFO\]: \[System\] \[CHAT\] '
        r'(\d+\.\d+)/(h|d|m) ago §[0-9a-fk-or][+-] (\w+)§f (added|removed) x(\d+) (\w+)§f\.$'
    )

    # 無色碼版本
    plain_action_pattern = re.compile(
        r'^\[\d{2}:\d{2}:\d{2}\] \[Render thread/INFO\]: \[System\] \[CHAT\] '
        r'(\d+\.\d+)/(h|d|m) ago\s+[ac][+-]\s+(\w+)\s+f\s+(added|removed) x(\d+) (\w+)\s+f\.$'
    )

    # 頁碼（不受色碼影響）
    page_pattern = re.compile(r'f(\d+)/(\d+)')

    # 嘗試含色碼版本
    match = color_action_pattern.match(log_line)
    if match:
        _, _, username, action, count, item = match.groups()
        return {
            "user": username,
            "action": 1 if action == "added" else -1,
            "item": item,
            "count": int(count)
        }

    # 若不成功，轉成無色碼再匹配
    cleaned_line = strip_minecraft_color_codes(log_line)
    match = plain_action_pattern.match(cleaned_line)
    if match:
        _, _, username, action, count, item = match.groups()
        return {
            "user": username,
            "action": 1 if action == "added" else -1,
            "item": item,
            "count": int(count)
        }

    # 頁碼檢查
    match = page_pattern.search(log_line)
    if match:
        return (int(match.group(1)), int(match.group(2)))

    return False

#忽略名單
IGNORELIST = {}

def check_changed_item(filtered, playerLog, ignore, nbt):
    if ignore:
        IGNORELIST = {"XmasTiramisu", "pxpxpx6666"}
    else:
        IGNORELIST = {}

    amountChange = {
        "experience_bottle": 0,
        "dragon_breath": 0,
        "sunflower": 0,
        "prismarine_crystals": 0,
        "prismarine_shard": 0,
        "nether_star": 0,
        "gray_dye": 0,
        "firework_star": 0
    }

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

    result = ""
    updatedLog = {}

    for action in filtered:
        user = action["user"]
        item = action["item"]
        count = int(action["count"]) * action["action"]

        if user in IGNORELIST:
            continue

        if item in amountChange:
            amountChange[item] += count

        if user not in playerLog:
            playerLog[user] = {}

        if item not in playerLog[user]:
            playerLog[user][item] = 0
        playerLog[user][item] += count

    if nbt != "":
        for user, items in playerLog.items():
            if nbt in items:
                updatedLog[user] = items
        playerLog = updatedLog

    for currency, amount in amountChange.items():
        if amount != 0:
            result += " └ " + CURRENCYMAP[currency] + " " + str(amount) + "\n"

    return (result, playerLog) if result else ("貨幣數量無變動\n", playerLog)

def check_parameter(parameter):
    pattern = r"(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(XP|CXP|HXP|CS|CCS|HCS|AR|HAR)(?:\s+(0|1))?(?:\s+(0|1))?(?:\s+(.+))?"

    match = re.fullmatch(pattern, parameter, re.IGNORECASE)
    if match:
        buy_price = float(match.group(1))
        sell_price = float(match.group(2))
        unit = match.group(3)
        ignore_owner = bool(int(match.group(4) if match.group(4) is not None else "0"))
        ignore_correct_trade = bool(int(match.group(5) if match.group(5) is not None else "0"))
        nbt = match.group(6) if match.group(6) is not None else ""
        return {"buyPrice": buy_price, "sellPrice": sell_price, "unit": unit, "ignore_owner": ignore_owner, "ignore_correct_trade":ignore_correct_trade, "nbt":nbt}
    else:
        return False

def mistrade_calculator(userData, target, buyPrice, sellPrice):
    from decimal import Decimal, getcontext
    getcontext().prec = 10

    CURRENCYMAP = {
        "experience_bottle": "XP",
        "dragon_breath": "CXP",
        "sunflower": "HXP",
        "prismarine_shard": "CS",
        "prismarine_crystals": "CCS",
        "nether_star": "HCS",
        "gray_dye": "AR",
        "firework_star": "HAR"
    }
    CURRENCYMULTIPLIER = {
        "XP": 1, "CXP": 8, "HXP": 512,
        "CS": 1, "CCS": 8, "HCS": 512,
        "AR": 1, "HAR": 64
    }
    REGIONMAP = {"XP": 1, "CS": 2, "AR": 3}

    wrong_currency_usage = {}
    wrong_payment = {}

    target = target.upper()
    target_base_currency = target[-2:]
    target_region = REGIONMAP.get(target_base_currency)
    target_multiplier = Decimal(CURRENCYMULTIPLIER[target])

    for userName, changedItems in userData.items():
        changedProductCount = 0
        total_base_value = Decimal(0)
        wrong_items = []

        for itemName, itemCount in changedItems.items():
            if itemName not in CURRENCYMAP:
                changedProductCount += itemCount
                continue

            currency_name = CURRENCYMAP[itemName]
            base_currency = currency_name[-2:]
            currency_region = REGIONMAP.get(base_currency)

            if currency_region != target_region:
                wrong_items.append(currency_name)
                continue

            multiplier = Decimal(CURRENCYMULTIPLIER[currency_name])
            total_base_value += Decimal(itemCount) * multiplier

        paid_value = total_base_value / target_multiplier
        wrong_payment_value = Decimal(0)
        #玩家購買
        if changedProductCount < 0:
            totalBuyPrice = abs(Decimal(changedProductCount)) * Decimal(buyPrice)
            wrong_payment_value = paid_value - totalBuyPrice
        #玩家販售
        elif changedProductCount > 0:
            totalSellPrice = Decimal(changedProductCount) * Decimal(-sellPrice)
            wrong_payment_value = paid_value - totalSellPrice
        else:
            wrong_payment_value = paid_value

        if wrong_payment_value != 0:
            wrong_payment[userName] = float(wrong_payment_value)

        if wrong_items:
            wrong_currency_usage[userName] = wrong_items
    
    return wrong_payment, wrong_currency_usage

def split_log_result(log_result: str, limit: int = 2000):
    lines = log_result.split('\n')
    messages = []
    current_message = ""

    for line in lines:

        if len(current_message) + len(line) + 1 > limit:
            messages.append(current_message)
            current_message = line
        else:
            if current_message:
                current_message += '\n' + line
            else:
                current_message = line

    # 加入最後一段訊息
    if current_message:
        messages.append(current_message)

    return messages

# def ai_calculate_mistrade(user_input: str):
#     api_key = os.getenv('GOOGLE_TOKEN')
#     genai.configure(api_key=api_key)

#     # 指定模型為 gemini-2.0-flash-001
#     model = genai.GenerativeModel(model_name="gemini-2.0-flash-001")

#     prompt = f"""
#     你是一個專門解析 Minecraft CoreProtect 外掛訊息的分析工具。

#     請依據以下規則分析用戶輸入的聊天記錄，輸出格式為：
#     {{玩家1: {{"物品名稱1": 數量, "物品名稱2": 數量}}, 玩家2: {{...}}}}

#     ### 分析任務：
#     1. 僅分析 CoreProtect 插件輸出的訊息，忽略非插件訊息。
#     2. 辨識交易雙方的玩家名稱與物品變動數量。
#     3. 統計每位玩家持有物品的最終變動數量（只記錄不為 0 的項目）。

#     ### 替代詞規則（NBT → 名稱）：
#     - experience_bottle → XP
#     - dragon_breath → CXP
#     - sunflower → HXP
#     - prismarine_shard → CS
#     - prismarine_crystals → CCS
#     - nether_star → HCS
#     - gray_dye → AR
#     - firework_star → HAR
#     - 若為其他 NBT，使用原始 NBT 名稱。


#     ### 現在請依據以上規則，分析以下聊天紀錄：

#     {user_input}
#     """

#     # 使用模型生成回應
#     response = model.generate_content(prompt)

#     return response.text

def get_full_class_name(class_name: str) -> str:
    class_tree = {
        "Alchemist": ["Harbinger", "Apothecary"],
        "Cleric": ["Paladin", "Hierophant"],
        "Mage": ["Arcanist", "Elementalist"],
        "Rogue": ["Swordsage", "Assassin"],
        "Scout": ["Ranger", "Hunter"],
        "Warlock": ["Reaper", "Tenebrist"],
        "Warrior": ["Berserker", "Guardian"],
    }

    # 去除前後空白與統一大小寫
    input_clean = class_name.strip()

    for base_class, subclasses in class_tree.items():
        if input_clean == base_class:
            return base_class
        elif input_clean in subclasses:
            return f"{base_class} ({input_clean})"

    return False

def display_skill_grid(skillpoint):
    skill_map = {
    '0': '⬜⬜⬛',
    '1': '🟧⬜⬛',
    '2': '🟧🟧⬛',
    '3': '🟧⬜⭐',
    '4': '🟧🟧⭐'
}
    first_job = skillpoint[0]
    second_job = skillpoint[1]
    
    first_job = list(skillpoint[0])
    second_job = list(skillpoint[1])
    first_job_icons = [skill_map[pt] for pt in first_job]

    second_job_icons = []
    for pt in second_job:
        icon = skill_map[pt]
        if icon.endswith('⬛'):
            icon = icon[:-1]
        second_job_icons.append(icon)

    result = "└⚔️技能點配置 : \n"

    num_rows = 4
    for i in range(num_rows):
        row = "    "
        left1 = first_job_icons[i]
        left2 = first_job_icons[i + 4]
        row += f"{left1}        {left2}"
    
        if i < len(second_job_icons):
            spaces = " " * (10 + i * 6)
            row += f"{spaces}{second_job_icons[i]}"
    
        result += row + "\n"
    return result

def manage_build(buildCommand, sender):
    # 解析名稱與連結
    if len(buildCommand) >= 3:
        build_name = buildCommand[2]
    op = ""
    if buildCommand[1] == "add" and len(buildCommand) >= 4:
        build_link = " ".join(buildCommand[3:])
        #檢查連結是否合法
        parsed = urlparse(build_link)
        if not parsed.netloc in ["odetomisery.vercel.app", "ohthemisery-psi.vercel.app"] or parsed.scheme != "https":
            return "build連結錯誤"
        
        # 建立新的 build 資料
        new_build = {
            build_name: {
                "連結": build_link,
                "作者": sender,
                "資訊": ""
            }
        }
    
        # 嘗試讀取已存在的 JSON 資料
        if os.path.exists("build.json"):
            with open("build.json", "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        else:
            data = {}
        # 更新資料
        if build_name not in data:
            data.update(new_build)
            op = "儲存"
        else:
            return "存在相同名稱build!"

    # 刪除舊的 build 資料
    elif buildCommand[1] == "remove":
        with open("build.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if not os.path.exists("build.json"):
            return "❌ 找不到 build.json 檔案。"
        if build_name in data:
            if data[build_name]["作者"] == sender:
                del data[build_name]
                op = "刪除"
            else:
                return f"⛔ {sender} 不是作者。"
        else:
            return f"⚠️ 沒有找到名稱為「{build_name}」的 build。"
    
    #搜尋已存在build
    elif (buildCommand[1] == "find" and len(buildCommand) >= 3) or buildCommand[1] == "own":
        if buildCommand[1] == "find":
            keyword = buildCommand[2].lower()
        
        with open("build.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        matched = []
        for name, info in data.items():
            if buildCommand[1] == "find" and keyword in name.lower():
                matched.append((name, info))
            elif buildCommand[1] == "own" and info["作者"] == sender:
                matched.append((name, info))
        if not matched:
            return "🔍 沒有找到符合的 build 。"
        else:
            top_results = matched[:5]
            # 建立結果訊息
            result_lines = ["🔎 找到以下符合的 build："]
            hasClass = False
            for name, info in top_results:
                for a, b in info.items():
                    if bool(re.fullmatch(r"[A-Za-z]", a[0])):
                        hasClass = True
                        className = f"└🗡️ 職業：{a} \n"
                        if b != []: skillPoints = display_skill_grid(b) + "\n"
                if not hasClass:
                    skillPoints = ""
                    className = ""

                result_lines.append(
                    f"# **{name}**\n"
                    f"└🔗 連結：[{name}]({info['連結']})\n"
                    f"└👤 作者：{info['作者']}\n"
                    f"{className}"
                    f"{skillPoints}"
                    f"└🗒️ 資訊：{info.get('資訊', '（無）')}"
                )

            return "\n".join(result_lines)

    #修改職業/技能點
    elif buildCommand[1] == "setclass" and len(buildCommand) >= 4:
        setClass = get_full_class_name(buildCommand[3].capitalize())
        if not setClass:
            return f"⚠️ 職業名稱錯誤!"
        if len(buildCommand) >= 5:
            skillPoints = buildCommand[4]
            classSkillPoints = skillPoints[:8]
            specSkillPoints = skillPoints[8:11]
            #判斷書入點數是否合法
            if len(skillPoints) != 8 and len(skillPoints) != 11:
                return f"⚠️ 技能點數量錯誤!"
            for pt in classSkillPoints:
                if pt not in ["0", "1", "2", "3", "4"]:
                    return f"⚠️ 一般技能點只能為 0/1/2/3"
            for pt in specSkillPoints:
                if pt not in ["0", "1", "2"]:
                    return f"⚠️ 二轉技能點只能為 0/1/2"
        else:
            classSkillPoints = "00000000"
            specSkillPoints = "000"
        with open("build.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            #確認build是否存在
            buildName = buildCommand[2]
            if data.get(buildName, False):
                if data[buildName].get("作者") == sender:
                    data[buildName][setClass] = [classSkillPoints, specSkillPoints]
                    op = "修改"
                    data[buildName] = {k: v for k, v in data[buildName].items() if k in ["連結", "作者", "資訊", setClass]}
                else:
                    return f"⛔ {sender} 不是作者。"
            else:
                return f"⚠️ 沒有找到名稱為「{buildName}」的 build。"

    else:
        return f"<:ghost_technology_4:1293185676086481039> 指令格式錯誤!"
    # 寫回 JSON 檔案
    with open("build.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    if op == "儲存":
        return f"✅ 已成功{op}Build「 [{build_name}]({build_link}) 」！"
    elif op == "刪除":
        return f"✅ 已成功{op}Build「 {build_name} 」！"
    elif op == "修改":
        return f"✅ 已成功{op}Build「 {build_name} 」的職業！"