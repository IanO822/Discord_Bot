import json
import requests

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