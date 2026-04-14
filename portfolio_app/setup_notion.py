"""
一鍵建立 Notion 交易紀錄 Database
執行方式：
    cd portfolio_app
    python setup_notion.py
"""

import sys
import os

try:
    from notion_client import Client
except ImportError:
    print("請先安裝套件：pip install notion-client")
    sys.exit(1)

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback
    except ImportError:
        tomllib = None


def load_secrets() -> dict:
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if tomllib and os.path.exists(secrets_path):
        with open(secrets_path, "rb") as f:
            return tomllib.load(f)
    return {}


def main():
    secrets = load_secrets()

    print("=" * 50)
    print("  Notion Database 自動建立工具")
    print("=" * 50)

    # 取得 token
    token = secrets.get("NOTION_TOKEN", "")
    if not token or token == "secret_xxxxxxxxxx":
        token = input("\n請貼上你的 Notion Integration Token (secret_...): ").strip()
    else:
        print(f"\n已從 secrets.toml 讀取 Token：{token[:12]}...")

    # 取得父頁面 ID
    print("\n請在 Notion 建立一個空白頁面（例如「Portfolio」），")
    print("並將它分享給你的 Integration（頁面右上角 ··· → Connections）。")
    print("然後從頁面 URL 複製 Page ID（32 碼英數字）。")
    parent_id = input("\n請貼上父頁面 ID: ").strip().replace("-", "")

    if len(parent_id) != 32:
        print(f"❌ Page ID 格式不正確（應為 32 碼，你輸入了 {len(parent_id)} 碼）")
        sys.exit(1)

    client = Client(auth=token)

    print("\n⏳ 建立 Database 中...")

    try:
        response = client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "交易紀錄"}}],
            properties={
                "Name": {"title": {}},
                "date": {"date": {}},
                "ticker": {
                    "select": {
                        "options": [
                            {"name": "2330.TW", "color": "blue"},
                            {"name": "2308.TW", "color": "green"},
                            {"name": "2383.TW", "color": "yellow"},
                            {"name": "3715.TW", "color": "orange"},
                            {"name": "NVDA", "color": "purple"},
                        ]
                    }
                },
                "action": {
                    "select": {
                        "options": [
                            {"name": "buy", "color": "red"},
                            {"name": "sell", "color": "green"},
                        ]
                    }
                },
                "term": {
                    "select": {
                        "options": [
                            {"name": "long", "color": "blue"},
                            {"name": "mid", "color": "yellow"},
                            {"name": "short", "color": "orange"},
                        ]
                    }
                },
                "shares": {"number": {"format": "number"}},
                "price": {"number": {"format": "number"}},
                "fee": {"number": {"format": "number"}},
                "reason": {"rich_text": {}},
                "note": {"rich_text": {}},
            },
        )

        db_id = response["id"].replace("-", "")
        db_url = response["url"]

        print("\n✅ Database 建立成功！")
        print(f"\n📋 Database URL：{db_url}")
        print(f"\n🔑 NOTION_DATABASE_ID：{db_id}")
        print("\n請將以下內容更新到 .streamlit/secrets.toml：")
        print("-" * 40)
        print(f'NOTION_TOKEN = "{token}"')
        print(f'NOTION_DATABASE_ID = "{db_id}"')
        print(f'CASH_BALANCE = 0  # 請填入你的現金部位（NTD）')
        print("-" * 40)

        # 自動更新 secrets.toml
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        try:
            with open(secrets_path, "w", encoding="utf-8") as f:
                f.write(f'# 本地開發用，不進 git\n')
                f.write(f'NOTION_TOKEN = "{token}"\n')
                f.write(f'NOTION_DATABASE_ID = "{db_id}"\n')
                f.write(f'CASH_BALANCE = 0\n')
            print(f"\n✅ 已自動寫入 secrets.toml")
        except Exception as e:
            print(f"\n⚠️  無法自動寫入 secrets.toml：{e}，請手動更新。")

        print("\n🚀 現在可以執行：streamlit run app.py")

    except Exception as e:
        print(f"\n❌ 建立失敗：{e}")
        print("\n常見原因：")
        print("  1. Token 錯誤或過期")
        print("  2. 父頁面沒有分享給 Integration")
        print("  3. 父頁面 ID 不正確")
        sys.exit(1)


if __name__ == "__main__":
    main()
