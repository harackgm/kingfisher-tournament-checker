import requests
from bs4 import BeautifulSoup
import json
import os

# ==========================================
# 設定値
# ==========================================
TARGET_URL = "https://kingfisher-tochigi.com/"
HISTORY_FILE = "history.json"
MAX_NOTIFY_LIMIT = 5 # 大量通知ストッパー

LOGO_URL = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/kinglogo.png"

TARGET_SECTIONS = ["大会エントリー", "大会エントリーリスト", "大会結果"]

# カテゴリごとの文字色設定（ダークモードに映える色）
CATEGORY_COLORS = {
    "大会エントリー": "#FF4B4B",       # 赤（受付開始などの目立つ色）
    "大会エントリーリスト": "#0367D3", # 青（落ち着いた情報確認）
    "大会結果": "#F4B400"              # 黄/ゴールド（結果発表）
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

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
# LINE通知処理（カテゴリ色分け対応版）
# ==========================================
def send_line_carousel(articles):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return
    
    bubbles = []
    for article in articles:
        # カテゴリ名から色を取得（設定がない場合はデフォルトの緑色）
        section_color = CATEGORY_COLORS.get(article['section'], "#1DB446")
        
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "hero": {
                "type": "image",
                "url": LOGO_URL,
                "size": "full",
                "aspectRatio": "3:1",
                "aspectMode": "fit",
                "backgroundColor": "#000000"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#222222",
                "contents": [
                    {
                        "type": "text",
                        "text": article['section'],
                        "weight": "bold",
                        "color": section_color, # 動的に色を変更
                        "size": "sm"
                    },
                    {
                        "type": "text",
                        "text": article.get('date', '日付不明'),
                        "color": "#AAAAAA",
                        "size": "xs",
                        "margin": "sm"
                    },
                    {
                        "type": "text",
                        "text": article['title'],
                        "weight": "bold",
                        "color": "#FFFFFF",
                        "size": "md",
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
                "backgroundColor": "#222222",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#555555",
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
                
                date_tag = article.find("span", class_="elementor-post-date")
                date_text = date_tag.get_text(strip=True) if date_tag else ""
                
                results.append({
                    "section": section_title,
                    "date": date_text,
                    "title": a_tag.get_text(strip=True),
                    "url": a_tag.get("href")
                })
    return results

# ==========================================
# メイン処理
# ==========================================
def main():
    print("--- 監視処理開始 ---")
    
    # 🌟【色確認用】3色すべてのダミーテスト通知を送信する🌟
    print("デザイン確認用（3色）のテスト通知を送信します...")
    color_test_articles = [
        {
            "section": "大会エントリー",
            "date": "2026年9月4日",
            "title": "【テスト・赤色】エントリー受付開始のお知らせ",
            "url": "https://kingfisher-tochigi.com/"
        },
        {
            "section": "大会エントリーリスト",
            "date": "2026年9月4日",
            "title": "【テスト・青色】参加者リストを更新しました",
            "url": "https://kingfisher-tochigi.com/"
        },
        {
            "section": "大会結果",
            "date": "2026年9月4日",
            "title": "【テスト・黄色】第1戦 大会結果発表",
            "url": "https://kingfisher-tochigi.com/"
        }
    ]
    send_line_carousel(color_test_articles)
    
    # 通常のスクレイピング・差分チェック（エラーが出ないかの確認のみ）
    current_articles = fetch_articles()
    history = load_history()
    history_urls = {item["url"] for item in history}
    new_articles = [item for item in current_articles if item["url"] not in history_urls]

    if not new_articles:
        print("新規の更新はありません。")
    else:
        new_count = len(new_articles)
        if new_count > MAX_NOTIFY_LIMIT:
            print(f"【安全装置作動】{new_count}件の新規記事を検知しました（上限超過）。LINE通知はスキップします。")
        else:
            print(f"【通知対象】{new_count}件の新規更新が見つかりました。（今回はテストコードのため本番通知は行いません）")
            
    updated_history = history + new_articles
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
