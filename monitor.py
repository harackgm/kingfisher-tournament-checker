import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timedelta, timezone

# ==========================================
# 設定値
# ==========================================
TARGET_URL = "https://kingfisher-tochigi.com/"
HISTORY_FILE = "history.json"
MAX_NOTIFY_LIMIT = 5 # 大量通知ストッパー（安全装置）

LOGO_URL = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/kinglogo.png"
TARGET_SECTIONS = ["大会エントリー", "大会エントリーリスト", "大会結果"]

CATEGORY_COLORS = {
    "大会エントリー": "#FF4B4B",
    "大会エントリーリスト": "#0367D3",
    "大会結果": "#F4B400"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# 日本時間の「明日」を取得
JST = timezone(timedelta(hours=9), 'JST')
TOMORROW = datetime.now(JST) + timedelta(days=1)

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
# 気象庁APIからの天気取得（栃木県北部）
# ==========================================
def get_tomorrow_weather():
    try:
        url = "https://www.jma.go.jp/bosai/forecast/data/forecast/090000.json"
        res = requests.get(url, timeout=10)
        data = res.json()
        for area in data[0]["timeSeries"][0]["areas"]:
            if area["area"]["name"] == "北部":
                weathers = area["weathers"]
                # 簡易的に明日の天気を取得（インデックス1付近）
                if len(weathers) > 1:
                    return weathers[1].replace(" ", " ")
                else:
                    return weathers[0].replace(" ", " ")
        return "確認できませんでした"
    except Exception:
        return "確認できませんでした"

# ==========================================
# LINE通知処理（種別ごとのデザイン出し分け）
# ==========================================
def send_line_carousel(notify_items):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return
    
    bubbles = []
    for item in notify_items:
        notify_type = item.get("notify_type", "new")
        
        # 通知の種類によってバッジの色と文字を変更
        if notify_type == "alert":
            badge_color = "#FF0000" # 緊急の赤
            badge_text = "⚠️中止・延期のお知らせ"
            header_color = "#4A0000"
        elif notify_type == "remind":
            badge_color = "#FF8C00" # リマインドのオレンジ
            badge_text = "📣明日開催！"
            header_color = "#222222"
        else:
            badge_color = CATEGORY_COLORS.get(item['section'], "#1DB446")
            badge_text = item['section']
            header_color = "#000000"
            
        hero_image_url = item.get('img_url') if item.get('img_url') else LOGO_URL
        
        # 本文の組み立て（リマインドの場合は天気と応援メッセージを追加）
        body_contents = [
            {
                "type": "box",
                "layout": "horizontal",
                "margin": "none",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": badge_color,
                        "cornerRadius": "md",
                        "paddingTop": "4px",
                        "paddingBottom": "4px",
                        "paddingStart": "10px",
                        "paddingEnd": "10px",
                        "flex": 0,
                        "contents": [
                            {
                                "type": "text",
                                "text": badge_text,
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
                "text": item.get('date', '日付不明'),
                "color": "#AAAAAA",
                "size": "xs",
                "margin": "md"
            },
            {
                "type": "text",
                "text": item['title'],
                "weight": "bold",
                "color": "#FFFFFF",
                "size": "md",
                "margin": "md",
                "wrap": True,
                "maxLines": 3
            }
        ]
        
        if notify_type == "remind" and "remind_msg" in item:
            body_contents.append({
                "type": "text",
                "text": item["remind_msg"],
                "color": "#F4B400",
                "size": "sm",
                "margin": "md",
                "wrap": True
            })

        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
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
                "contents": body_contents
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
                            "uri": item['url']
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
                "altText": "キングフィッシャーからのお知らせ",
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
        print("LINEにメッセージを送信しました！")
    except Exception as e:
        print(f"LINE通知エラー: {e}")

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
                img_url = img_tag.get("data-src") or img_tag.get("src", "") if img_tag else ""
                
                results.append({
                    "section": section_title,
                    "date": date_text,
                    "title": a_tag.get_text(strip=True),
                    "url": a_tag.get("href"),
                    "img_url": img_url
                })
    return results

# ==========================================
# メイン処理（スマート検知搭載）
# ==========================================
def main():
    print("--- 監視処理開始 ---")
    
    current_articles = fetch_articles()
    history = load_history()
    
    # 履歴をURLキーの辞書に変換して扱いやすくする
    history_dict = {item["url"]: item for item in history}
    notify_list = []

    for article in current_articles:
        url = article["url"]
        title = article["title"]
        
        # ① 完全新規の検知
        if url not in history_dict:
            article_copy = article.copy()
            article_copy["notify_type"] = "new"
            notify_list.append(article_copy)
            # 履歴に追加（前日通知フラグを初期化）
            history_dict[url] = {"section": article["section"], "title": title, "url": url, "reminded": False}
        else:
            past_article = history_dict[url]
            # ② タイトル変更（中止・延期）の検知
            if past_article.get("title") != title:
                if "中止" in title or "延期" in title:
                    article_copy = article.copy()
                    article_copy["notify_type"] = "alert"
                    notify_list.append(article_copy)
                past_article["title"] = title
        
        # ③ 明日開催の自動検知＆リマインド
        past_article = history_dict[url]
        if not past_article.get("reminded", False):
            # タイトルから「○月○日」を抽出
            match = re.search(r'(\d{1,2})月(\d{1,2})日', title)
            if match:
                m = int(match.group(1))
                d = int(match.group(2))
                # 日本時間の明日と一致するか確認
                if m == TOMORROW.month and d == TOMORROW.day:
                    article_copy = article.copy()
                    article_copy["notify_type"] = "remind"
                    weather = get_tomorrow_weather()
                    article_copy["remind_msg"] = f"明日の天気（栃木北部）: {weather}\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"
                    notify_list.append(article_copy)
                    # 通知済みフラグを立てて二重送信を防止
                    past_article["reminded"] = True

    # 通知対象がある場合
    if not notify_list:
        print("新規更新、日程変更、前日リマインドはありません。")
    else:
        new_count = len(notify_list)
        if new_count > MAX_NOTIFY_LIMIT:
            print(f"【安全装置作動】{new_count}件の通知を検知しましたが上限を超えたためスキップします。")
        else:
            print(f"【通知送信】{new_count}件の情報をLINEへ送信します。")
            send_line_carousel(notify_list)
            
    # 履歴をリストに戻して保存
    updated_history = list(history_dict.values())
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
