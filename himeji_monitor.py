import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials

# --- 設定項目 ---
# 姫路市の美容所一覧API（CKAN）のリソースID
HIMEJI_RESOURCE_ID = "24b58d2a-8a80-4704-a04f-cab1199f6438" 

# スプレッドシートのID（URLの https://docs.google.com/spreadsheets/d/ ここの文字列 /edit の間）
SPREADSHEET_KEY = "1eT8wkSY5qVRi0fnaPP_AUx2_aed-KhfRjqRUM4a9i7o"

# ★書き込み先のシート（タブ）名を指定★
SHEET_NAME = "姫路市保健所" 

# 認証情報ファイルへのパス
CREDENTIALS_FILE = "service_account.json"
# ---------------

def fetch_recent_himeji_salons():
    """姫路市のAPIから直近30日以内に開設された美容所を取得する"""
    ckan_api_url = "https://city.himeji.gkan.jp/gkan/api/3/action/datastore_search"
    params = {
        "resource_id": HIMEJI_RESOURCE_ID,
        "limit": 100,           
        "sort": "開設日 desc"   
    }

    try:
        res = requests.get(ckan_api_url, params=params)
        res.raise_for_status() 
        data = res.json()
    except Exception as e:
        print(f"姫路市APIの取得に失敗しました: {e}")
        return []

    records = data.get("result", {}).get("records", [])
    
    # 30日前の日付を計算
    one_month_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    
    recent_salons = []
    for row in records:
        open_date = str(row.get("開設日", ""))[:10] 
        
        # 開設日が30日以内のものだけを抽出
        if open_date >= one_month_ago:
            recent_salons.append({
                "開設日": open_date,
                "施設名": row.get("施設名", ""),
                "所在地": row.get("施設所在地", ""),
                "電話番号": row.get("施設電話番号", "")
            })
            
    return recent_salons

def save_to_spreadsheet(salons):
    """取得したリストを「姫路市保健所」タブに追記する"""
    if not salons:
        print("新規のサロンはありませんでした。")
        return

    # スプレッドシートへの接続準備
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    
    # ★「AI探客プログラム」スプレッドシートの「姫路市保健所」タブを開く★
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)
    
    # 重複書き込みを防ぐため、すでに書き込まれているサロン名（B列）を取得
    existing_names = sheet.col_values(2) 

    add_count = 0
    for salon in salons:
        name = salon["施設名"]
        # シートに存在しないサロン名の場合だけ追記する
        if name not in existing_names and name != "":
            # 新規行として追加 (A列: 開設日, B列: 施設名, C列: 所在地, D列: 電話番号)
            sheet.append_row([
                salon["開設日"],
                name,
                salon["所在地"],
                salon["電話番号"]
            ])
            print(f"追加: {name} ({salon['所在地']})")
            add_count += 1
            
    print(f"処理完了: {add_count}件追加しました。")

if __name__ == "__main__":
    print("姫路市のデータを取得中...")
    new_salons = fetch_recent_himeji_salons()
    save_to_spreadsheet(new_salons)
