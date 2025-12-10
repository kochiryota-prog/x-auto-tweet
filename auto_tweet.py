import tweepy
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import requests
import tempfile
# 環境変数から取得
API_KEY = os.environ.get('X_API_KEY')
API_SECRET = os.environ.get('X_API_SECRET')
ACCESS_TOKEN = os.environ.get('X_ACCESS_TOKEN')
ACCESS_SECRET = os.environ.get('X_ACCESS_SECRET')
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
    print(f"認証エラー: {e}")
    print("APIキーが正しく設定されているか確認してください。")
# Google Sheets認証（認証情報なしで公開シートを読む）
# 【重要】ここにあなたのGoogle SheetsのURLを入力してください
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1XVucwTYjGeZOsqMSS1o6vm10XZ0wOBOH-TQIUFgpSHE/edit?gid=1702486208#gid=1702486208' 
def get_sheet_data():
    """Google Sheetsからデータ取得（公開シート）"""
    try:
        # URLからスプレッドシートIDを抽出
        if '/d/' not in SHEET_URL:
            print("エラー: SHEET_URLが正しく設定されていません。")
            return []
            
        sheet_id = SHEET_URL.split('/d/')[1].split('/')[0]
        
        # CSV形式で取得
        csv_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv'
        
        response = requests.get(csv_url)
        response.encoding = 'utf-8' # 日本語文字化け対策
        lines = response.text.split('\n')
        
        data = []
        # ヘッダー行をスキップしてデータ処理
        for i, line in enumerate(lines[1:], start=2):
            if line.strip():
                # カンマ区切りだが、引用符内のカンマを考慮しない簡易実装
                # 必要に応じてcsvモジュールを使用することを推奨しますが、今回は元のコードに準拠します
                import csv
                reader = csv.reader([line])
                cols = list(reader)[0]
                
                if len(cols) >= 3: # 最低限必要な列数
                    data.append({
                        'row': i,
                        'date': cols[1] if len(cols) > 1 else '',
                        'text': cols[2] if len(cols) > 2 else '',
                        'image_url': cols[3] if len(cols) > 3 else '',
                        'posted': cols[4] if len(cols) > 4 else 'No'
                    })
        return data
    except Exception as e:
        print(f"シート取得エラー: {e}")
        return []
def should_post(scheduled_time_str):
    """投稿時刻かどうか判定"""
    try:
        if not scheduled_time_str:
            return False
        # 日時フォーマットの揺れに対応（秒がある場合など）
        scheduled_time_str = scheduled_time_str.strip()
        try:
            scheduled = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M')
        except ValueError:
             scheduled = datetime.strptime(scheduled_time_str, '%Y/%m/%d %H:%M')
        now = datetime.now()
        
        # 投稿時刻の±30分以内なら投稿OK
        diff = abs((now - scheduled).total_seconds())
        return diff < 1800  # 30分
    except Exception as e:
        # print(f"日付解析エラー: {e} (値: {scheduled_time_str})") 
        return False
def download_image(url):
    """画像をダウンロード"""
    if not url or url.strip() == '':
        return None
    
    try:
        # Google Driveの共有リンクをダウンロードURLに変換
        if 'drive.google.com' in url:
            file_id = url.split('/d/')[1].split('/')[0] if '/d/' in url else url.split('id=')[1]
            download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        else:
            download_url = url
        
        response = requests.get(download_url)
        
        # 一時ファイルに保存
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        print(f"画像ダウンロードエラー: {e}")
        return None
def post_tweet():
    """メイン処理"""
    print("🔍 投稿チェック開始...")
    print(f"現在時刻: {datetime.now()}")
    
    # Google Sheetsからデータ取得
    data = get_sheet_data()
    
    if not data:
        print("データが取得できませんでした。シートURLや公開設定を確認してください。")
        return
    posted_count = 0
    
    for row in data:
        # 既に投稿済み(Yes)でなく、かつ投稿すべき時間の場合
        # 注: CSV取得方式のため、'posted'列の更新は反映されません。
        # 実際には時刻だけで判定するか、運用で工夫が必要です。
        if row['posted'].strip().lower() != 'yes' and should_post(row['date']):
            try:
                text = row['text']
                image_url = row['image_url']
                
                print(f"\n📤 投稿実行: {text[:30]}...")
                
                ids = []
                # 画像がある場合
                if image_url and image_url.strip() != '':
                    image_path = download_image(image_url)
                    
                    if image_path:
                        # 画像アップロード
                        media = api.media_upload(image_path)
                        ids.append(media.media_id)
                        
                        # 一時ファイル削除
                        os.unlink(image_path)
                        print("画像アップロード完了")
                    else:
                        print("画像ダウンロード失敗、テキストのみ投稿します")
                
                # 投稿
                if ids:
                    response = client.create_tweet(text=text, media_ids=ids)
                else:
                    response = client.create_tweet(text=text)
                
                print(f"✅ 投稿成功！")
                print(f"投稿ID: {response.data['id']}")
                
                # 公開シートは読み取り専用のため、書き込み不可
                print("※注意: Google Sheetsの「投稿済み」列を手動で 'Yes' に変更してください。")
                
                return  # 重複投稿防止のため、1回の実行で1件のみ投稿して終了
                
            except Exception as e:
                print(f"❌ 投稿エラー: {e}")
    
    print("⏰ 投稿条件に一致する行はありませんでした")
if __name__ == "__main__":
    post_tweet()
