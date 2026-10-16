import io
import urllib.parse
import pandas as pd
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# --- 設定項目 ---
DATASET_PAGE_URL = "https://city.himeji.gkan.jp/gkan/dataset/77e05f08-cefc-4a8d-8749-e4e239256059"
BASE_URL = "https://city.himeji.gkan.jp"

SPREADSHEET_KEY = "1eT8wkSY5qVRi0fnaPP_AUx2_aed-KhfRjqRUM4a9i7o"
SHEET_NAME = "姫路市保健所"
CREDENTIALS_FILE = "service_account.json"
# ----------------

def get_previous_excel_url():
    """親ページから「2番目（1個前）」のExcelダウンロードURLを取得する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        res = requests.get(DATASET_PAGE_URL, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # ページ内から「.xlsx」が含まれるリンクをすべてリストアップ
        excel_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".xlsx" in href and "download" in href:
                full_url = urllib.parse.urljoin(BASE_URL, href)
                # 重複を排除してリストに追加
                if full_url not in excel_links:
                    excel_links.append(full_url)
        
        # ファイルが2つ以上ある場合、2番目（インデックス1）を取得
        if len(excel_links) >= 2:
            print("見つかったExcelファイル一覧:")
            for i, link in enumerate(excel_links):
                print(f"[{i}] {link}")
            return excel_links[1] # ★ 1個前のファイルを選択
        elif len(excel_links) == 1:
            print("※ ページにExcelファイルが1つしかありませんでした。それを読み込みます。")
            return excel_links[0]
        else:
            return None
                
    except Exception as e:
        print(f"Excelリンクの取得に失敗しました: {e}")
        return None


def fetch_all_salons():
    """指定したExcelファイルをダウンロードして「全件」を抽出する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    target_excel_url = get_previous_excel_url()
    if not target_excel_url:
        print("処理を終了します。")
        return []

    print(f"★ 読み込み対象: {target_excel_url}")

    try:
        res = requests.get(target_excel_url, headers=headers, timeout=20)
        res.raise_for_status()
        df = pd.read_excel(io.BytesIO(res.content))
    except Exception as e:
        print(f"Excelの読み込みに失敗しました: {e}")
        return []

    date_col = next((c for c in df.columns if any(k in str(c) for k in ["開設", "届出", "許可年月日"])), None)
    name_col = next((c for c in df.columns if any(k in str(c) for k in ["施設名", "名称", "屋号"])), None)
    addr_col = next((c for c in df.columns if any(k in str(c) for k in ["所在地", "住所"])), None)
    tel_col = next((c for c in df.columns if "電話" in str(c)), None)

    if not all([date_col, name_col]):
        print("Excel内に必要な列が見つかりません。")
        return []

    salons = []
    for _, row in df.iterrows():
        if pd.isna(row[date_col]) or pd.isna(row[name_col]):
            continue

        raw_date = str(row[date_col]).replace("/", "-")[:10]
        
        # 今回は日付フィルタ（過去35日等）をかけず、全件を取り込む
        salons.append({
            "開設日": raw_date,
            "施設名": str(row[name_col]).strip(),
            "所在地": str(row[addr_col]).strip() if addr_col else "",
            "電話番号": str(row[tel_col]).strip() if tel_col else ""
        })

    return salons


def save_to_spreadsheet(salons):
    if not salons:
        print("サロンデータが見つかりませんでした。")
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
            print(f"追加: {name} ({salon['開設日']})")
            add_count += 1

    print(f"完了: {add_count}件をシートに新しく追加しました。")


if __name__ == "__main__":
    print("【スポット実行】姫路市の1個前のデータを全件読み込み中...")
    all_salons = fetch_all_salons()
    save_to_spreadsheet(all_salons)
