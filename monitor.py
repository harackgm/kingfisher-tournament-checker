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
# LINE通知処理（ダークモード＆日付付き カルーセル）
# ==========================================
def send_line_carousel(articles):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return
    
    bubbles = []
    for article in articles:
        bubble = {
            "type": "bubble",
            "size": "micro",
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#222222", # 背景をダークグレーに
                "contents": [
                    {
                        "type": "text",
                        "text": article['section'],
                        "weight": "bold",
                        "color": "#1DB446", # カテゴリ名はアクセントの緑
                        "size": "xs"
                    },
                    {
                        "type": "text",
                        "text": article.get('date', '日付不明'), # 取得した日付を表示
                        "color": "#AAAAAA", # 日付は薄いグレー
                        "size": "xxs",
                        "margin": "sm"
                    },
                    {
                        "type": "text",
                        "text": article['title'],
                        "weight": "bold",
                        "color": "#FFFFFF", # タイトルは白文字
                        "size": "sm",
                        "margin": "md",
                        "wrap": True,
                        "maxLines": 3
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "backgroundColor": "#222222", # フッターの背景も統一
                "contents": [
                    {
                        "type": "button",
                        "style": "secondary", # セカンダリスタイルで落ち着いたボタンに
                        "color": "#444444", 
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "詳細を見る",
                            "uri": article['url']
                        }
                    }
                ]
            }
        }
        bubbles.append(bubble)

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    data = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "キングフィッシャーの最新情報が更新されました",
                "contents": {
                    "type": "carousel",
                    "contents": bubbles
                }
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print("LINEにカルーセルメッセージを送信しました！")
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
                
                # HTML構造から日付部分のタグを探して取得
                date_tag = article.find("span", class_="elementor-post-date")
                date_text = date_tag.get_text(strip=True) if date_tag else ""
                
                results.append({
                    "section": section_title,
                    "date": date_text, # 日付データを追加
                    "title": a_tag.get_text(strip=True),
                    "url": a_tag.get("href")
                })
    return results

# ==========================================
# メイン処理（テストモード）
# ==========================================
def main():
    print("--- 監視処理開始（ダークデザインテストモード） ---")
    
    print("LINEへ新しいデザインのカルーセル通信テストを実行します...")
    dummy_articles = [
        {
            "section": "大会エントリー",
            "date": "2026年9月4日",
            "title": "【テスト】全日本ジュニア・釣り女子・ファミリーエリアトラウト選手権大会",
            "url": "https://kingfisher-tochigi.com/"
        },
        {
            "section": "大会結果",
            "date": "2026年8月18日",
            "title": "【テスト】「平日大会1ST戦」大会結果",
            "url": "https://kingfisher-tochigi.com/"
        }
    ]
    send_line_carousel(dummy_articles)
    
    # 差分チェック処理（エラーチェック用）
    history = load_history()
    history_urls = {item["url"] for item in history}
    
    current_articles = fetch_articles()
    new_articles = [item for item in current_articles if item["url"] not in history_urls]

    if not new_articles:
        print("新規の更新はありません（正常）。")
    else:
        new_count = len(new_articles)
        if new_count > MAX_NOTIFY_LIMIT:
            print(f"【安全装置作動】{new_count}件の新規記事を検知しました。")
        else:
            print(f"{new_count}件の更新を検知しました。")
    
    updated_history = history + new_articles
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
