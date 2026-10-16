import datetime
import io
import urllib.parse
import pandas as pd
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# --- 設定項目 ---
# 1. 姫路市の美容所データセットの親ページURL
DATASET_PAGE_URL = "https://city.himeji.gkan.jp/gkan/dataset/77e05f08-cefc-4a8d-8749-e4e239256059"
BASE_URL = "https://city.himeji.gkan.jp"

# 2. スプレッドシート設定
SPREADSHEET_KEY = "1eT8wkSY5qVRi0fnaPP_AUx2_aed-KhfRjqRUM4a9i7o"
SHEET_NAME = "姫路市保健所"
CREDENTIALS_FILE = "service_account.json"
# ----------------

def get_latest_excel_url():
    """親ページから最新のExcelダウンロードURLを自動抽出する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        res = requests.get(DATASET_PAGE_URL, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # ページ内から「.xlsx」が含まれるリンクを探す
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".xlsx" in href and "download" in href:
                return urllib.parse.urljoin(BASE_URL, href)
                
    except Exception as e:
        print(f"最新Excelリンクの自動取得に失敗しました: {e}")
        return None
        
    return None

def fetch_recent_himeji_salons():
    """最新のExcelをダウンロードして新着サロンを抽出する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # 1. 最新のダウンロードリンクを自動特定
    latest_excel_url = get_latest_excel_url()
    if not latest_excel_url:
        print("ExcelファイルのURLが見つかりませんでした。")
        return []

    print(f"最新データを発見: {latest_excel_url}")

    # 2. Excelファイルをダウンロード
    try:
        res = requests.get(latest_excel_url, headers=headers, timeout=20)
        res.raise_for_status()
        df = pd.read_excel(io.BytesIO(res.content))
    except Exception as e:
        print(f"Excelの読み込みに失敗しました: {e}")
        return []

    # 3. 直近35日以内のデータを抽出
    filter_date = (datetime.date.today() - datetime.timedelta(days=35)).strftime("%Y-%m-%d")

    # 列名の自動判別
    date_col = next((c for c in df.columns if any(k in str(c) for k in ["開設", "届出", "許可年月日"])), None)
    name_col = next((c for c in df.columns if any(k in str(c) for k in ["施設名", "名称", "屋号"])), None)
    addr_col = next((c for c in df.columns if any(k in str(c) for k in ["所在地", "住所"])), None)
    tel_col = next((c for c in df.columns if "電話" in str(c)), None)

    if not all([date_col, name_col]):
        print("Excel内に必要な列が見つかりません。")
        return []

    recent_salons = []
    for _, row in df.iterrows():
        if pd.isna(row[date_col]) or pd.isna(row[name_col]):
            continue

        raw_date = str(row[date_col]).replace("/", "-")[:10]
        
        if raw_date >= filter_date:
            recent_salons.append({
                "開設日": raw_date,
                "施設名": str(row[name_col]).strip(),
                "所在地": str(row[addr_col]).strip() if addr_col else "",
                "電話番号": str(row[tel_col]).strip() if tel_col else ""
            })

    return recent_salons

def save_to_spreadsheet(salons):
    if not salons:
        print("新着サロンはありませんでした。")
        return

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)

    existing_names = sheet.col_values(2)

    add_count = 0
    for salon in salons:
        name = salon["施設名"]
        if name not in existing_names and name != "" and name != "nan":
            sheet.append_row([
                salon["開設日"],
                name,
                salon["所在地"],
                salon["電話番号"]
            ])
            print(f"追加: {name} ({salon['所在地']})")
            add_count += 1

    print(f"完了: {add_count}件をシートに新しく追加しました。")

if __name__ == "__main__":
    print("姫路市のデータをチェック中...")
    new_salons = fetch_recent_himeji_salons()
    save_to_spreadsheet(new_salons)
