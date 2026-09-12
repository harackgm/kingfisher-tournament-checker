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
MAX_NOTIFY_LIMIT = 5 # 大量通知ストッパー（安全装置）

LOGO_URL = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/kinglogo.png"

# 画像URLの基本セット（全8種類）
POKOASITA_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokoasita.jpg"
POKOCAN_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokocan.jpg"
POKOENTRY_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokoentry.jpg"
POKOSTOP_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokostop.jpg"
POKOSINGLE_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokosingle.jpg"
POKOSTEAM_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokosteam.jpg"
POKOLIST_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokolist.jpg"
POKOLISTCAN_BASE = "https://raw.githubusercontent.com/harackgm/kingfisher-tournament-checker/main/pokolistcan.jpg"

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

# 日本時間 (JST) 基準設定
JST = timezone(timedelta(hours=9), 'JST')
CURRENT_TIME = datetime.now(JST)
TOMORROW = CURRENT_TIME + timedelta(days=1)

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
# LINE通知処理（登録者全員への一斉送信版）
# ==========================================
def send_line_carousel(notify_items, all_articles):
    if not LINE_ACCESS_TOKEN:
        print("エラー: LINE_ACCESS_TOKEN が設定されていません。")
        return
    
    # タイムスタンプ生成（LINEアプリ側キャッシュ回避用）
    ts = int(time.time())
    
    pokoasita_url = f"{POKOASITA_BASE}?t={ts}"
    pokocan_url = f"{POKOCAN_BASE}?t={ts}"
    pokoentry_url = f"{POKOENTRY_BASE}?t={ts}"
    pokostop_url = f"{POKOSTOP_BASE}?t={ts}"
    pokosingle_url = f"{POKOSINGLE_BASE}?t={ts}"
    pokosteam_url = f"{POKOSTEAM_BASE}?t={ts}"
    pokolist_url = f"{POKOLIST_BASE}?t={ts}"
    pokolistcan_url = f"{POKOLISTCAN_BASE}?t={ts}"
    
    has_global_cancel_wait = any(
        art['section'] == "大会エントリー" and "キャンセル待ち" in art['title']
        for art in all_articles
    )
    
    bubbles = []
    for item in notify_items:
        notify_type = item.get("notify_type", "new")
        is_updated = item.get("is_updated", False)
        
        # 全セクション対応：バッジテキストと色の動的判定
        if notify_type == "alert":
            badge_color = "#FF0000"
            badge_text = "⚠️中止・延期のお知らせ"
            header_color = "#4A0000"
        elif notify_type == "remind":
            badge_color = "#FF8C00"
            badge_text = "📣明日開催！"
            header_color = "#222222"
        else:
            if is_updated:
                badge_color = "#FF8C00"  # 更新時共通オレンジ
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
            "第1戦", "第2戦", "第3戦", "第4戦", "第5戦", "最終戦", 
            "1st戦", "2nd戦", "3rd戦", "4th戦", "1st season", "2nd season",
            "チーム戦", "マスターズ", "鉄板王", "シリーズ"
        ]
        
        title_lower = item['title'].lower()
        title_lower = title_lower.replace("１", "1").replace("２", "2").replace("３", "3").replace("４", "4").replace("５", "5")
        
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
            elif notify_type == "cancel_wait":
                hero_image_url = pokocan_url
                show_hero = True
            elif notify_type == "alert":
                hero_image_url = pokostop_url
                show_hero = True
            elif notify_type == "new":
                if item.get("section") == "大会エントリー":
                    hero_image_url = pokoentry_url
                    show_hero = True
                elif item.get("section") == "大会結果":
                    if "チーム戦" in title_lower:
                        hero_image_url = pokosteam_url
                    else:
                        hero_image_url = pokosingle_url
                    show_hero = True
                elif item.get("section") == "大会エントリーリスト":
                    if "キャンセル待ち" in title_lower or has_global_cancel_wait:
                        hero_image_url = pokolistcan_url
                    else:
                        hero_image_url = pokolist_url
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
                            "uri": item['url']
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

    # 本番用：LINE登録者全員へ一斉送信（Broadcast API）
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    data = {
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
        print("LINEに一斉送信メッセージを送信しました！")
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
# メイン処理（公開本番用）
# ==========================================
def main():
    print("--- 監視処理開始（公開本番モード） ---")
    
    current_articles = fetch_articles()
    history = load_history()
    
    history_dict = {item["url"]: item for item in history}
    notify_list = []

    for article in current_articles:
        url = article["url"]
        title = article["title"]
        
        is_new_or_updated = False
        
        # ① 完全新規の検知
        if url not in history_dict:
            article_copy = article.copy()
            article_copy["is_updated"] = False # 初回作成フラグ
            if "キャンセル待ち" in title:
                article_copy["notify_type"] = "cancel_wait"
            else:
                article_copy["notify_type"] = "new"
            notify_list.append(article_copy)
            history_dict[url] = {"section": article["section"], "title": title, "url": url, "reminded": False}
            is_new_or_updated = True
        else:
            past_article = history_dict[url]
            # ② タイトル変更（中止・延期・キャンセル待ち等の変更）の検知
            if past_article.get("title") != title:
                article_copy = article.copy()
                article_copy["is_updated"] = True # 更新フラグ
                if "中止" in title or "延期" in title:
                    article_copy["notify_type"] = "alert"
                    notify_list.append(article_copy)
                    is_new_or_updated = True
                elif "キャンセル待ち" in title and "キャンセル待ち" not in past_article.get("title"):
                    article_copy["notify_type"] = "cancel_wait"
                    notify_list.append(article_copy)
                    is_new_or_updated = True
                elif "キャンセル待ち" not in title and "キャンセル待ち" in past_article.get("title"):
                    article_copy["notify_type"] = "new"
                    notify_list.append(article_copy)
                    is_new_or_updated = True
                else:
                    article_copy["notify_type"] = "new"
                    notify_list.append(article_copy)
                    is_new_or_updated = True
                past_article["title"] = title
        
        # ③ 明日開催の自動検知＆リマインド
        past_article = history_dict[url]
        if not is_new_or_updated and not past_article.get("reminded", False):
            match = re.search(r'(\d{1,2})月(\d{1,2})日', title)
            if match:
                m = int(match.group(1))
                d = int(match.group(2))
                if m == TOMORROW.month and d == TOMORROW.day:
                    # 日本時間で18時〜21時台（18:00〜21:59）にのみリマインドを発動させる制御
                    if 18 <= CURRENT_TIME.hour <= 21:
                        article_copy = article.copy()
                        article_copy["notify_type"] = "remind"
                        weather = get_tomorrow_weather()
                        article_copy["remind_msg"] = f"明日の大田原市の予報です🐟\n\n{weather}\n\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"
                        notify_list.append(article_copy)
                        past_article["reminded"] = True

    if not notify_list:
        print("新規更新、日程変更、前日リマインドはありません。")
    else:
        new_count = len(notify_list)
        if new_count > MAX_NOTIFY_LIMIT:
            print(f"【安全装置作動】{new_count}件の通知を検知しましたが上限を超えたためスキップします。")
        else:
            print(f"【通知送信】{new_count}件の情報をLINEの登録者全員へ一斉送信します。")
            send_line_carousel(notify_list, current_articles)
            
    updated_history = list(history_dict.values())
    save_history(updated_history)
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
