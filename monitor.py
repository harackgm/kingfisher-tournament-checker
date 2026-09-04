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
# メイン処理（差分検知と通知制御）
# ==========================================
def main():
    print("--- 監視処理開始 ---")
    history = load_history()
    history_urls = {item["url"] for item in history} # URLをキーにしてゆらぎ対策
    
    current_articles = fetch_articles()
    
    # 未保存のURLのみを抽出
    new_articles = [item for item in current_articles if item["url"] not in history_urls]

    if not new_articles:
        print("新規の更新はありません。")
        return

    new_count = len(new_articles)
    
    # 【絶対ルール】大量通知ストッパー
    if new_count > MAX_NOTIFY_LIMIT:
        print(f"【安全装置作動】{new_count}件の新規記事を検知しました（上限{MAX_NOTIFY_LIMIT}件超過）。")
        print("LINE通知はスキップし、全件既読化（JSON保存）のみ行います。")
    else:
        print(f"【通知対象】{new_count}件の新規更新が見つかりました。")
        for article in new_articles:
            print(f"[{article['section']}] {article['title']}\n{article['url']}\n")
            # TODO: ここにLINE BOTへのPOSTリクエストを追加予定

    # 取得した最新データを履歴に追記して保存
    updated_history = history + new_articles
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
