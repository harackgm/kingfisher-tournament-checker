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
MAX_NOTIFY_LIMIT = 5 # 大量通知ストッパー

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
# 大田原市の詳細な明日の天気取得（気象庁＋Open-Meteo併用）
# ==========================================
def get_tomorrow_weather():
    weather_text = "確認できませんでした"
    wind_text = "-"
    
    # ① 気象庁APIから天気と風向テキストを取得
    try:
        url_jma = "https://www.jma.go.jp/bosai/forecast/data/forecast/090000.json"
        res_jma = requests.get(url_jma, timeout=10).json()
        for area in res_jma[0]["timeSeries"][0]["areas"]:
            if area["area"]["name"] == "北部":
                weathers = area["weathers"]
                winds = area.get("winds", [])
                idx = 1 if len(weathers) > 1 else 0
                weather_text = weathers[idx].replace(" ", " ")
                if len(winds) > idx:
                    wind_text = winds[idx].replace(" ", " ")
    except Exception as e:
        print(f"気象庁APIエラー: {e}")
        
    # ② Open-Meteo APIから大田原市の気温と最大風速を取得（キー不要）
    temp_max = "-"
    temp_min = "-"
    wind_speed = "-"
    try:
        # 大田原市周辺の緯度経度を指定、風速をm/sで取得
        url_om = "https://api.open-meteo.com/v1/forecast?latitude=36.87&longitude=140.01&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max&timezone=Asia%2FTokyo&wind_speed_unit=ms"
        res_om = requests.get(url_om, timeout=10).json()
        # インデックス1が明日
        temp_max = round(res_om["daily"]["temperature_2m_max"][1])
        temp_min = round(res_om["daily"]["temperature_2m_min"][1])
        wind_speed = round(res_om["daily"]["windspeed_10m_max"][1], 1)
    except Exception as e:
        print(f"Open-Meteo APIエラー: {e}")

    # メッセージの組み立て
    msg = f"🌤️ 【天気】{weather_text}\n"
    msg += f"🌡️ 【気温】最高 {temp_max}℃ / 最低 {temp_min}℃\n"
    msg += f"🍃 【風向】{wind_text}\n"
    msg += f"💨 【最大風速】約 {wind_speed} m/s"
    return msg

# ==========================================
# LINE通知処理（二重ロゴ回避版）
# ==========================================
def send_line_carousel(notify_items):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return
    
    bubbles = []
    for item in notify_items:
        notify_type = item.get("notify_type", "new")
        
        if notify_type == "alert":
            badge_color = "#FF0000"
            badge_text = "⚠️中止・延期のお知らせ"
            header_color = "#4A0000"
        elif notify_type == "remind":
            badge_color = "#FF8C00"
            badge_text = "📣明日開催！"
            header_color = "#222222"
        else:
            badge_color = CATEGORY_COLORS.get(item['section'], "#1DB446")
            badge_text = item['section']
            header_color = "#000000"
            
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
                "size": "xs",
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
        
        # 記事固有の画像URLが存在する場合のみ、heroブロック（メイン画像）を追加する
        if item.get('img_url'):
            bubble["hero"] = {
                "type": "image",
                "url": item['img_url'],
                "size": "full",
                "aspectRatio": "1.51:1",
                "aspectMode": "fit",
                "backgroundColor": "#000000"
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
# メイン処理（テストモード）
# ==========================================
def main():
    print("--- 監視処理開始（新機能デザインテスト） ---")
    
    weather = get_tomorrow_weather()
    
    # 🌟強制的にダミーデータを送ってデザインを確認する🌟
    # 今回は img_url を設定しないため、二重ロゴは発生せずヘッダーのみになります。
    dummy_articles = [
        {
            "section": "大会エントリーリスト",
            "notify_type": "remind",
            "date": "2026年9月6日",
            "title": "【テスト】「全日本ジュニア・釣り女子・ファミリーエリアトラウト選手権大会」エントリーリスト",
            "url": "https://kingfisher-tochigi.com/",
            "remind_msg": f"明日の大田原市の予報です🐟\n\n{weather}\n\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"
        },
        {
            "section": "大会エントリーリスト",
            "notify_type": "remind",
            "date": "2026年9月6日",
            "title": "【テスト】WEEKDAY TROUT Tournament 2026 2nd season 第2戦 エントリーリスト",
            "url": "https://kingfisher-tochigi.com/",
            "remind_msg": f"明日の大田原市の予報です🐟\n\n{weather}\n\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"
        },
        {
            "section": "大会エントリー",
            "notify_type": "alert",
            "date": "2026年9月6日",
            "title": "【中止】9月13日開催 シリーズ第5戦",
            "url": "https://kingfisher-tochigi.com/"
        }
    ]
    
    send_line_carousel(dummy_articles)
    
    print("--- テスト実行のため、history.jsonの更新は行いません ---")
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
