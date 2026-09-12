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
# 🌟 テスト確認用：USER_ID宛て個別送信
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# 日本時間 (JST) 基準設定
JST = timezone(timedelta(hours=9), 'JST')
CURRENT_TIME = datetime.now(JST)

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
    
    has_global_cancel_wait = any(
        art['section'] == "大会エントリー" and "キャンセル待ち" in art['title']
        for art in all_articles
    )
    
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

    # 🌟 テスト用：LINE個人宛てへPush送信
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    # 10個のバブルがあると一度に送れる上限（10カルーセル）に達するため、そのまま送信
    data = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "キングフィッシャーからのお知らせ（全パターンテスト）",
                "contents": {
                    "type": "carousel",
                    "contents": bubbles[:10]
                }
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print("LINEにテストメッセージ（全パターン）を送信しました！")
    except Exception as e:
        print(f"LINE通知エラー: {e}")

# ==========================================
# メイン処理（全パターンテストモード）
# ==========================================
def main():
    print("--- 監視処理開始（全通知パターンテストモード） ---")
    
    # 🌟 全10パターンのテストデータを生成
    test_notify_list = [
        {"section": "大会エントリー", "notify_type": "new", "is_updated": False, "date": "2026年9月13日", "title": "【1. 新規】第5戦エントリー開始", "url": "https://kingfisher-tochigi.com/t1"},
        {"section": "大会エントリー", "notify_type": "new", "is_updated": True, "date": "2026年9月13日", "title": "【2. 更新】第5戦エントリー情報（定員増など）", "url": "https://kingfisher-tochigi.com/t2"},
        {"section": "大会エントリーリスト", "notify_type": "new", "is_updated": False, "date": "2026年9月13日", "title": "【3. 新規】第5戦エントリーリスト", "url": "https://kingfisher-tochigi.com/t3"},
        {"section": "大会エントリーリスト", "notify_type": "new", "is_updated": True, "date": "2026年9月13日", "title": "【4. 更新】第5戦エントリーリスト（通常更新）", "url": "https://kingfisher-tochigi.com/t4"},
        {"section": "大会エントリーリスト", "notify_type": "new", "is_updated": True, "date": "2026年9月13日", "title": "【5. キャン待ち更新】第5戦エントリーリスト（キャンセル待ち）", "url": "https://kingfisher-tochigi.com/t5"},
        {"section": "大会結果", "notify_type": "new", "is_updated": False, "date": "2026年9月13日", "title": "【6. 新規】第5戦大会結果", "url": "https://kingfisher-tochigi.com/t6"},
        {"section": "大会結果", "notify_type": "new", "is_updated": True, "date": "2026年9月13日", "title": "【7. 更新】第5戦大会結果（修正等）", "url": "https://kingfisher-tochigi.com/t7"},
        {"section": "大会エントリー", "notify_type": "cancel_wait", "is_updated": True, "date": "2026年9月13日", "title": "【8. キャン待ち】第5戦（現在キャンセル待ち）", "url": "https://kingfisher-tochigi.com/t8"},
        {"section": "大会エントリー", "notify_type": "alert", "is_updated": True, "date": "2026年9月13日", "title": "【9. アラート】第5戦 中止のお知らせ", "url": "https://kingfisher-tochigi.com/t9"},
        {"section": "大会エントリー", "notify_type": "remind", "is_updated": False, "date": "2026年9月13日", "title": "【10. リマインド】現在キャンセル待ち：第5戦エントリー（※タイトル整形テスト）", "url": "https://kingfisher-tochigi.com/t10", 
         "remind_msg": "明日の大田原市の予報です🐟\n\n🌤️ 【天気】くもり\n🌡️ 【気温】最高 25℃ / 最低 20℃\n🍃 【風向】北の風\n💨 【最大風速】約 2.4 m/s\n\n受付時間や費用の詳細はリンク先をご確認ください。明日は頑張ってください🎣✨"}
    ]
    
    print("【通知送信】全10パターンのカルーセルを個人宛てに送信します。")
    # 全体を渡して連携用ロジック（has_global_cancel_wait等）も同時に走らせます
    send_line_carousel(test_notify_list, test_notify_list)
            
    print("--- テスト実行のため、history.jsonの更新は行いません ---")
    print("--- 監視処理終了 ---")

if __name__ == "__main__":
    main()
