import requests
from bs4 import BeautifulSoup
import json
import os

# ==========================================
# 設定値
# ==========================================
TARGET_URL = "https://kingfisher-tochigi.com/"
HISTORY_FILE = "history.json"
MAX_NOTIFY_LIMIT = 5 # 大量通知ストッパー（安全装置）

TARGET_SECTIONS = ["大会エントリー", "大会エントリーリスト", "大会結果"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# GitHub SecretsからLINEのキーを取得
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# ==========================================
# データ管理処理
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history_list):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_list, f, ensure_ascii=False, indent=2)

# ==========================================
# LINE通知処理
# ==========================================
def send_line_message(message_text):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が読み込めませんでした。Secretsの設定を確認してください。")
        return
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message_text}]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print("LINEにメッセージを送信しました！")
    except Exception as e:
        print(f"LINE通知エラー: {e}")
        if response is not None:
            print(f"エラー詳細: {response.text}")

# ==========================================
# スクレイピング処理
# ==========================================
def fetch_articles():
    try:
        response = requests.get(TARGET_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"取得エラー: {e}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    results = []

    for h1 in soup.find_all("h1", class_="elementor-heading-title"):
        section_title = h1.get_text(strip=True)
        if section_title in TARGET_SECTIONS:
            posts_container = h1.find_next("div", class_="elementor-posts-container")
            if not posts_container:
                continue
            
            articles = posts_container.find_all("article", class_="elementor-post")
            for article in articles:
                title_tag = article.find("h6", class_="elementor-post__title")
                if not title_tag:
                    continue
                
                a_tag = title_tag.find("a")
                if not a_tag:
                    continue
                
                results.append({
                    "section": section_title,
                    "title": a_tag.get_text(strip=True),
                    "url": a_tag.get("href")
                })
    return results

# ==========================================
# メイン処理（テストモード）
# ==========================================
def main():
    print("--- 監視処理開始（LINEテストモード） ---")
    
    # 🌟必ず1件テストメッセージを送る🌟
    print("LINEへの通信テストを実行します...")
    send_line_message("【テスト】LINE BOTへの通信が正常に完了しました！\nこのメッセージが届けばGitHub Secretsの設定は成功です。")
    
    # 以降は通常の差分チェック処理（エラーが出ないかどうかの確認用）
    history = load_history()
    history_urls = {item["url"] for item in history}
    
    current_articles = fetch_articles()
    new_articles = [item for item in current_articles if item["url"] not in history_urls]

    if not new_articles:
        print("新規の更新はありません（正常）。")
    else:
        new_count = len(new_articles)
        if new_count > MAX_NOTIFY_LIMIT:
            print(f"【安全装置作動】{new_count}件の新規記事を検知しました（上限{MAX_NOTIFY_LIMIT}件超過）。")
        else:
            print(f"{new_count}件の更新を検知しました。")
    
    # 履歴を保存
    updated_history = history + new_articles
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
