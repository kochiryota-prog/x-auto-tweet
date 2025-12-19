import tweepy
import requests
import tempfile
import os
import csv
from datetime import datetime, timedelta, timezone

# ========= 環境変数 =========
API_KEY = os.environ.get('X_API_KEY')
API_SECRET = os.environ.get('X_API_SECRET')
ACCESS_TOKEN = os.environ.get('X_ACCESS_TOKEN')
ACCESS_SECRET = os.environ.get('X_ACCESS_SECRET')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# ========= X 認証 =========
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# ========= Sheet =========
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1XVucwTYjGeZOsqMSS1o6vm10XZ0wOBOH-TQIUFgpSHE/export?format=csv'

JST = timezone(timedelta(hours=9))

def now_jst():
    return datetime.now(JST)

def should_post(time_str):
    scheduled = datetime.strptime(time_str.strip(), '%Y-%m-%d %H:%M').replace(tzinfo=JST)
    diff = (now_jst() - scheduled).total_seconds()
    return 0 <= diff <= 300  # 5分以内

def download_image(url):
    if not url: return None
    r = requests.get(url)
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    f.write(r.content)
    f.close()
    return f.name

def post_thread(parent, reply1, reply2, image_url):
    media_ids = []
    if image_url:
        img = download_image(image_url)
        media = api.media_upload(img)
        media_ids.append(media.media_id)
        os.unlink(img)

    res_parent = client.create_tweet(text=parent, media_ids=media_ids if media_ids else None)
    parent_id = res_parent.data['id']

    reply1_id = reply2_id = None

    if reply1:
        import time; time.sleep(60)
        res1 = client.create_tweet(text=reply1, in_reply_to_tweet_id=parent_id)
        reply1_id = res1.data['id']

    if reply2:
        import time; time.sleep(60)
        res2 = client.create_tweet(text=reply2, in_reply_to_tweet_id=reply1_id or parent_id)
        reply2_id = res2.data['id']

    return parent_id, reply1_id, reply2_id

def main():
    print("🚀 チェック開始")
    r = requests.get(SHEET_URL)
    rows = list(csv.reader(r.text.splitlines()))

    for i, row in enumerate(rows[1:], start=2):
        date, parent, r1, r2, img, posted = row[1:7]

        if posted.lower() == 'yes':
            continue

        if not should_post(date):
            continue

        print(f"📤 投稿: {parent[:20]}")

        p_id, r1_id, r2_id = post_thread(parent, r1, r2, img)

        print(f"✅ 完了 ID={p_id}")
        break  # 1回1スレッド

if __name__ == "__main__":
    main()
