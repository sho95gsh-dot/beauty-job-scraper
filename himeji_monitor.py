import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os

# --- 設定項目 ---
# 読み込むExcelファイル名（GitHubにアップロードするファイル名と一致させる）
EXCEL_FILE = "himeji.xlsx" 

# スプレッドシート設定
SPREADSHEET_KEY = "1eT8wkSY5qVRi0fnaPP_AUx2_aed-KhfRjqRUM4a9i7o"
SHEET_NAME = "姫路市保健所"
CREDENTIALS_FILE = "service_account.json"
# ----------------

def import_local_excel():
    """ローカル（リポジトリ内）のExcelファイルを読み込んでデータ化する"""
    if not os.path.exists(EXCEL_FILE):
        print(f"エラー: {EXCEL_FILE} が見つかりません。GitHubにアップロードされているか確認してください。")
        return []

    print(f"{EXCEL_FILE} を読み込み中...")
    
    # openpyxlを使ってExcelを読み込む
    try:
        df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    except Exception as e:
        print(f"Excelの読み込みに失敗しました: {e}")
        return []

    # 列名の自動判別（表記揺れ対応）
    date_col = next((c for c in df.columns if any(k in str(c) for k in ["開設", "届出", "許可年月日"])), None)
    name_col = next((c for c in df.columns if any(k in str(c) for k in ["施設名", "名称", "屋号"])), None)
    addr_col = next((c for c in df.columns if any(k in str(c) for k in ["所在地", "住所"])), None)
    tel_col = next((c for c in df.columns if "電話" in str(c)), None)

    if not all([date_col, name_col]):
        print("エラー: Excel内に「開設日」または「施設名」に該当する列が見つかりません。")
        return []

    salons = []
    for _, row in df.iterrows():
        # 日付やサロン名が空欄の行はスキップ
        if pd.isna(row[date_col]) or pd.isna(row[name_col]):
            continue

        # 日付フォーマットの整形 (YYYY/MM/DD -> YYYY-MM-DD など)
        raw_date = str(row[date_col]).replace("/", "-").replace(" 00:00:00", "")[:10]
        
        salons.append({
            "開設日": raw_date,
            "施設名": str(row[name_col]).strip(),
            "所在地": str(row[addr_col]).strip() if addr_col else "",
            "電話番号": str(row[tel_col]).strip() if tel_col else ""
        })
        
    return salons


def save_to_spreadsheet(salons):
    """スプレッドシートに未登録の店舗だけを追記する"""
    if not salons:
        print("追加するデータがありませんでした。")
        return

    # 認証情報の準備
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)
    except Exception as e:
        print(f"スプレッドシートへの接続に失敗しました: {e}")
        return

    # 重複防止のため、既存のサロン名（B列）を取得
    existing_names = sheet.col_values(2)
    
    add_count = 0
    # スプレッドシートに追加する用のリストを作成
    rows_to_add = []
    
    for salon in salons:
        name = salon["施設名"]
        # シートに名前がない場合のみ追加リストに入れる
        if name not in existing_names and name != "" and name != "nan":
            rows_to_add.append([
                salon["開設日"],
                name,
                salon["所在地"],
                salon["電話番号"]
            ])
            print(f"新規追加準備: {name} ({salon['開設日']})")
            add_count += 1
            # 今回のループ内での重複（Excel内で同じ店舗が2回出た場合）を防ぐために既存リストにも追加
            existing_names.append(name)

    if rows_to_add:
        # 1行ずつ追加するとAPI制限（429エラー）に引っかかりやすいため、一括で追加する
        try:
            sheet.append_rows(rows_to_add)
            print(f"完了: {add_count}件をシートに一括で流し込みました。")
        except Exception as e:
            print(f"書き込み中にエラーが発生しました: {e}")
    else:
        print("新しいサロン（シートに存在しないサロン）はありませんでした。")


if __name__ == "__main__":
    salons_list = import_local_excel()
    save_to_spreadsheet(salons_list)
