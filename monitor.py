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

LOGO_URL = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/kinglogo.png"

TARGET_SECTIONS = ["大会エントリー", "大会エントリーリスト", "大会結果"]

# カテゴリごとの背景色設定（バッジ用）
CATEGORY_COLORS = {
    "大会エントリー": "#FF4B4B",       # 赤
    "大会エントリーリスト": "#0367D3", # 青
    "大会結果": "#F4B400"              # 黄
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
# LINE通知処理（カテゴリのバッジ化）
# ==========================================
def send_line_carousel(articles):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return
    
    bubbles = []
    for article in articles:
        # カテゴリに応じた色を取得
        section_color = CATEGORY_COLORS.get(article['section'], "#1DB446")
        
        hero_image_url = article.get('img_url') if article.get('img_url') else LOGO_URL
        
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#000000",
                "paddingTop": "15px",
                "paddingBottom": "10px",
                "paddingStart": "15px",
                "paddingEnd": "15px",
                "contents": [
                    {
                        "type": "image",
                        "url": LOGO_URL,
                        "size": "full",
                        "aspectMode": "fit",
                        "aspectRatio": "3:1",
                        "align": "center"
                    }
                ]
            },
            "hero": {
                "type": "image",
                "url": hero_image_url,
                "size": "full",
                "aspectRatio": "1.51:1",
                "aspectMode": "fit",
                "backgroundColor": "#000000"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#222222",
                "contents": [
                    # カテゴリ名をバッジ（ラベル）風に装飾
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "none",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": section_color,
                                "cornerRadius": "md",
                                "paddingTop": "4px",
                                "paddingBottom": "4px",
                                "paddingStart": "10px",
                                "paddingEnd": "10px",
                                "flex": 0, # テキストの幅に合わせる
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": article['section'],
                                        "weight": "bold",
                                        "color": "#FFFFFF",
                                        "size": "sm",
                                        "align": "center"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "type": "text",
                        "text": article.get('date', '日付不明'),
                        "color": "#AAAAAA",
                        "size": "xs",
                        "margin": "md"
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
                
                img_tag = article.find("img")
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("src", "")
                
                results.append({
                    "section": section_title,
                    "date": date_text,
                    "title": a_tag.get_text(strip=True),
                    "url": a_tag.get("href"),
                    "img_url": img_url
                })
    return results

# ==========================================
# メイン処理（本番稼働用）
# ==========================================
def main():
    print("--- 監視処理開始（本番モード） ---")
    
    current_articles = fetch_articles()
    
    # 通常のスクレイピング・差分チェック
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
            print(f"【通知対象】{new_count}件の新規更新が見つかりました。LINEへ通知します。")
            send_line_carousel(new_articles)
            
    updated_history = history + new_articles
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
