import tweepy
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import requests
import tempfile
from datetime import timedelta, timezone
import json
# 環境変数から取得
API_KEY = os.environ.get('X_API_KEY')
API_SECRET = os.environ.get('X_API_SECRET')
ACCESS_TOKEN = os.environ.get('X_ACCESS_TOKEN')
ACCESS_SECRET = os.environ.get('X_ACCESS_SECRET')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
# Discord通知関数
def send_discord_notify(message, is_error=False):
    if not DISCORD_WEBHOOK_URL:
        return
    
    color = 0xFF0000 if is_error else 0x00FF00 # 赤 or 緑
    data = {
        "embeds": [{
            "title": "❌ エラー" if is_error else "✅ 投稿成功",
            "description": message,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Discord通知エラー: {e}")
# X API認証
try:
    auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    api = tweepy.API(auth)
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET
    )
except Exception as e:
    send_discord_notify(f"API認証エラー: {e}", True)
    print(f"認証エラー: {e}")
# Google Sheets認証
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1XVucwTYjGeZOsqMSS1o6vm10XZ0wOBOH-TQIUFgpSHE/edit?gid=1702486208#gid=1702486208'
def get_sheet_data():
    """Google Sheetsからデータ取得（公開シート）"""
    try:
        if '/d/' not in SHEET_URL:
            return []
            
        sheet_id = SHEET_URL.split('/d/')[1].split('/')[0]
        csv_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv'
        
        response = requests.get(csv_url)
        response.encoding = 'utf-8'
        lines = response.text.split('\n')
        
        data = []
        for i, line in enumerate(lines[1:], start=2):
            if line.strip():
                import csv
                reader = csv.reader([line])
                cols = list(reader)[0]
                
                if len(cols) >= 3:
                    data.append({
                        'row': i,
                        'date': cols[1] if len(cols) > 1 else '',
                        'text': cols[2] if len(cols) > 2 else '',
                        'image_url': cols[3] if len(cols) > 3 else '',
                        'posted': cols[4] if len(cols) > 4 else 'No'
                    })
        return data
    except Exception as e:
        send_discord_notify(f"シート取得エラー: {e}", True)
        return []
def should_post(scheduled_time_str):
    """投稿時刻かどうか判定"""
    try:
        if not scheduled_time_str:
            return False
        scheduled_time_str = scheduled_time_str.strip()
        try:
            scheduled = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M')
        except ValueError:
             scheduled = datetime.strptime(scheduled_time_str, '%Y/%m/%d %H:%M')
        # JSTに変換 (UTC+9)
        JST = timezone(timedelta(hours=9))
        now = datetime.now(JST)
        
        # シート日時をJST扱いにする
        scheduled = scheduled.replace(tzinfo=JST)
        
        diff = abs((now - scheduled).total_seconds())
        if diff < 1800: # 30分
            return True
        else:
            return False
            
    except Exception:
        return False
def download_image(url):
    if not url or url.strip() == '': return None
    try:
        if 'drive.google.com' in url:
            file_id = url.split('/d/')[1].split('/')[0] if '/d/' in url else url.split('id=')[1]
            download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        else:
            download_url = url
        response = requests.get(download_url)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_file.write(response.content)
        temp_file.close()
        return temp_file.name
    except Exception:
        return None
def post_tweet():
    print("🔍 投稿チェック開始 (JST対応版)...")
    data = get_sheet_data()
    if not data: return
    for row in data:
        if row['posted'].strip().lower() != 'yes' and should_post(row['date']):
            try:
                text = row['text']
                image_url = row['image_url']
                print(f"\n📤 投稿実行: {text[:30]}...")
                
                ids = []
                if image_url and image_url.strip() != '':
                    image_path = download_image(image_url)
                    if image_path:
                        media = api.media_upload(image_path)
                        ids.append(media.media_id)
                        os.unlink(image_path)
                
                if ids:
                    response = client.create_tweet(text=text, media_ids=ids)
                else:
                    response = client.create_tweet(text=text)
                
                success_msg = f"投稿しました！\n内容: {text[:50]}..."
                print(f"✅ {success_msg} ID: {response.data['id']}")
                send_discord_notify(success_msg, False)
                return
            except Exception as e:
                error_msg = f"投稿失敗: {e}"
                print(f"❌ {error_msg}")
                send_discord_notify(error_msg, True)
    
    print("⏰ 投稿なし")
if __name__ == "__main__":
    post_tweet()
