import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

# ==========================================
# 設定値
# ==========================================
TARGET_URL = "https://kingfisher-tochigi.com/"
HISTORY_FILE = "history.json"
MAX_NOTIFY_LIMIT = 15 # テスト用に上限を一時解放

LOGO_URL = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/kinglogo.png"

# 画像URLの基本セット（全10種類）
POKOASITA_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokoasita.jpg"
POKOCAN_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokocan.jpg"
POKOENTRY_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokoentry.jpg"
POKOSTOP_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokostop.jpg"
POKOSINGLE_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokosingle.jpg"
POKOSTEAM_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokosteam.jpg"
POKOLIST_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokolist.jpg"
POKOLISTCAN_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokolistcan.jpg"
POKOLISTTEAM_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokolistteam.jpg"
POKOCANTEAM_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokocanteam.jpg"

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
# 🌟 テスト確認用：USER_ID宛て個別送信
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# 日本時間 (JST) 基準設定
JST = timezone(timedelta(hours=9), 'JST')
CURRENT_TIME = datetime.now(JST)
TOMORROW = CURRENT_TIME + timedelta(days=1)

# ==========================================
# 大田原市の詳細な明日の天気取得
# ==========================================
def get_tomorrow_weather():
    weather_text = "確認できませんでした"
    wind_text = "-"
    
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
        
    temp_max = "-"
    temp_min = "-"
    wind_speed = "-"
    try:
        url_om = "https://api.open-meteo.com/v1/forecast?latitude=36.87&longitude=140.01&daily=temperature_2m_max,temperature_2m_min,windspeed_10m_max&timezone=Asia%2FTokyo&wind_speed_unit=ms"
        res_om = requests.get(url_om, timeout=10).json()
        temp_max = round(res_om["daily"]["temperature_2m_max"][1])
        temp_min = round(res_om["daily"]["temperature_2m_min"][1])
        wind_speed = round(res_om["daily"]["windspeed_10m_max"][1], 1)
    except Exception as e:
        print(f"Open-Meteo APIエラー: {e}")

    msg = f"🌤️ 【天気】{weather_text}\n"
    msg += f"🌡️ 【気温】最高 {temp_max}℃ / 最低 {temp_min}℃\n"
    msg += f"🍃 【風向】{wind_text}\n"
    msg += f"💨 【最大風速】約 {wind_speed} m/s"
    return msg

# ==========================================
# LINE通知処理（テスト個別送信版）
# ==========================================
def send_line_carousel(notify_items, all_articles):
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("エラー: LINE_ACCESS_TOKEN または LINE_USER_ID が設定されていません。")
        return
    
    ts = int(time.time())
    
    pokoasita_url = f"{POKOASITA_BASE}?t={ts}"
    pokocan_url = f"{POKOCAN_BASE}?t={ts}"
    pokoentry_url = f"{POKOENTRY_BASE}?t={ts}"
    pokostop_url = f"{POKOSTOP_BASE}?t={ts}"
    pokosingle_url = f"{POKOSINGLE_BASE}?t={ts}"
    pokosteam_url = f"{POKOSTEAM_BASE}?t={ts}"
    pokolist_url = f"{POKOLIST_BASE}?t={ts}"
    pokolistcan_url = f"{POKOLISTCAN_BASE}?t={ts}"
    pokolistteam_url = f"{POKOLISTTEAM_BASE}?t={ts}"
    pokocanteam_url = f"{POKOCANTEAM_BASE}?t={ts}"
    
    bubbles = []
    for item in notify_items:
        notify_type = item.get("notify_type", "new")
        is_updated = item.get("is_updated", False)
        
        display_title = item['title']
        if notify_type == "remind":
            display_title = display_title.replace("【現在キャンセル待ち：", "【")
            display_title = display_title.replace("現在キャンセル待ち：", "").replace("現在キャンセル待ち", "")
            display_title = display_title.replace("【キャンセル待ち】", "").replace("キャンセル待ち", "")
        
        if notify_type == "alert":
            badge_color = "#FF0000"
            badge_text = "⚠️中止・延期のお知らせ"
            header_color = "#4A0000"
        elif notify_type == "remind":
            badge_color = "#FF8C00"
            badge_text = "📣明日開催！"
            header_color = "#222222"
        elif notify_type == "cancel_wait":
            badge_color = CATEGORY_COLORS.get(item['section'], "#1DB446")
            badge_text = item['section']
            header_color = "#000000"
        else:
            if is_updated:
                badge_color = "#FF8C00"
                if item['section'] == "大会エントリーリスト":
                    badge_text = "🔄エントリーリスト更新"
                elif item['section'] == "大会エントリー":
                    badge_text = "🔄エントリー情報更新"
                elif item['section'] == "大会結果":
                    badge_text = "🔄大会結果更新"
                else:
                    badge_text = f"🔄{item['section']}更新"
            else:
                badge_color = CATEGORY_COLORS.get(item['section'], "#1DB446")
                badge_text = item['section']
            header_color = "#000000"

        normal_keywords = [
            "weekday", "平日", 
            "第1戦", "第2戦", "第3戦", "第4戦", "第5戦", "第6戦", "最終戦", 
            "1st戦", "2nd戦", "3rd戦", "4th戦", "1st season", "2nd season",
            "チーム戦", "マスターズ", "鉄板王", "シリーズ"
        ]
        
        title_lower = item['title'].lower()
        title_lower = title_lower.replace("１", "1").replace("２", "2").replace("３", "3").replace("４", "4").replace("５", "5").replace("６", "6")
        
        is_normal = any(kw in title_lower for kw in normal_keywords)
        is_special = not is_normal

        show_hero = False
        hero_image_url = ""
        
        if is_special and item.get('img_url'):
            hero_image_url = item['img_url']
            show_hero = True
        else:
            if notify_type == "remind":
                hero_image_url = pokoasita_url
                show_hero = True
            
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
                "text": display_title,
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
                "color": "#FFE600",
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
                            "uri": item.get('url', TARGET_URL)
                        }
                    }
                ]
            }
        }
        
        if show_hero:
            bubble["hero"] = {
                "type": "image",
                "url": hero_image_url,
                "size": "full",
                "aspectRatio": "1.51:1",
                "aspectMode": "fit",
                "backgroundColor": "#000000"
            }
            
        bubbles.append(bubble)

    # 🌟 テスト用：LINE個人宛てへPush送信
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
        print("LINEにテストメッセージ（リマインドURLテスト）を送信しました！")
    except Exception as e:
        print(f"LINE通知エラー: {e}")

# ==========================================
# メイン処理（テストモード）
# ==========================================
def main():
    print("--- 監視処理開始（リマインドURL変更テストモード） ---")
    
    # 疑似的な history.json データ（DBに保存されている状態を再現）
    history_dict = {
        "https://kingfisher-tochigi.com/entry2": {"section": "大会エントリー", "title": f"【{TOMORROW.month}月{TOMORROW.day}日開催！】平日大会2nd 第2戦エントリー", "url": "https://kingfisher-tochigi.com/entry2", "reminded": False},
        "https://kingfisher-tochigi.com/list2": {"section": "大会エントリーリスト", "title": "【9月29日開催！】「平日大会2nd 第2戦」エントリーリスト", "url": "https://kingfisher-tochigi.com/list2", "reminded": False}
    }
    
    notify_list = []

    # テスト対象として「大会エントリー」の疑似データを1つ抽出
    test_article = {
        "section": "大会エントリー", 
        "date": "2026年8月18日", 
        "title": f"【現在キャンセル待ち：{TOMORROW.month}月{TOMORROW.day}日開催！】WEEKDAY TROUT Tournament 2026 2nd season 第2戦エントリー", 
        "url": "https://kingfisher-tochigi.com/entry2"
    }

    url = test_article["url"]
    title = test_article["title"]
    past_article = history_dict[url]

    # ③ 明日開催の自動検知＆リマインド
    match = re.search(r'(\d{1,2})月(\d{1,2})日', title)
    if match:
        m = int(match.group(1))
        d = int(match.group(2))
        if m == TOMORROW.month and d == TOMORROW.day:
            article_copy = test_article.copy()
            article_copy["notify_type"] = "remind"
            weather = get_tomorrow_weather()
            
            # 🌟 文末のメッセージを「エントリーリストをご確認ください」に修正
            article_copy["remind_msg"] = f"明日の大田原市の予報です🐟\n\n{weather}\n\n参加者の皆様はリンク先のエントリーリストをご確認ください。明日は頑張ってください🎣✨"
            
            # 🌟 リンク先を「大会エントリーリスト」に変更する処理
            # 第〇戦などの固有キーワードを先に判定させるため順番を調整
            match_keywords = ["第1戦", "第2戦", "第3戦", "第4戦", "第5戦", "第6戦", "最終戦", "1st", "2nd", "3rd", "4th", "チーム戦", "マスターズ", "鉄板王", "平日"]
            for kw in match_keywords:
                if kw in title:
                    for hist_url, hist_item in history_dict.items():
                        if hist_item.get("section") == "大会エントリーリスト" and kw in hist_item.get("title", ""):
                            # 対応するリストのURLを発見したら上書き
                            article_copy["url"] = hist_url
                            break
                    break
            
            notify_list.append(article_copy)

    print("【通知送信】リマインド通知（リンク先リスト変更）を個人宛てに送信します。")
    send_line_carousel(notify_list, [])
            
    print("--- テスト実行のため、history.jsonの更新は行いません ---")
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
