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
MAX_NOTIFY_LIMIT = 5

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
        
        # 本文の組み立て
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
        
        # リマインドの場合は天気と応援メッセージを追加
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
# メイン処理（新機能デザインテスト用）
# ==========================================
def main():
    print("--- 監視処理開始（新機能デザインテスト） ---")
    
    weather = get_tomorrow_weather()
    
    # 🌟強制的にダミーデータを送ってデザインを確認する🌟
    dummy_articles = [
        {
            "section": "大会エントリーリスト",
            "notify_type": "remind",
            "date": "2026年9月6日",
            "title": "【テスト】「全日本ジュニア・釣り女子・ファミリーエリアトラウト選手権大会」エントリーリスト",
            "url": "https://kingfisher-tochigi.com/",
            "img_url": LOGO_URL,
            "remind_msg": f"明日の天気（栃木北部）: {weather}\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"
        },
        {
            "section": "大会エントリーリスト",
            "notify_type": "remind",
            "date": "2026年9月6日",
            "title": "【テスト】WEEKDAY TROUT Tournament 2026 2nd season 第2戦 エントリーリスト",
            "url": "https://kingfisher-tochigi.com/",
            "img_url": LOGO_URL,
            "remind_msg": f"明日の天気（栃木北部）: {weather}\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"
        },
        {
            "section": "大会エントリー",
            "notify_type": "alert",
            "date": "2026年9月6日",
            "title": "【中止】9月13日開催 シリーズ第5戦",
            "url": "https://kingfisher-tochigi.com/",
            "img_url": LOGO_URL
        }
    ]
    
    send_line_carousel(dummy_articles)
    
    print("--- テスト実行のため、history.jsonの更新は行いません ---")
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
