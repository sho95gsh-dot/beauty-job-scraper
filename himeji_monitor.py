import os
import urllib.parse
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- 設定項目 ---
EXCEL_FILE = "himeji.xlsx" 
SPREADSHEET_KEY = "1eT8wkSY5qVRi0fnaPP_AUx2_aed-KhfRjqRUM4a9i7o"
SHEET_NAME = "姫路市保健所"
CREDENTIALS_FILE = "service_account.json"
# ----------------

def import_local_excel():
    if not os.path.exists(EXCEL_FILE):
        print(f"エラー: {EXCEL_FILE} が見つかりません。")
        return []

    print(f"{EXCEL_FILE} を読み込み中...")
    
    try:
        df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    except Exception as e:
        print(f"Excelの読み込みに失敗しました: {e}")
        return []

    date_col = "確認日"
    name_col = "施設名称"
    addr_col = "施設所在地"
    sub_addr_col = "方書"
    tel_col = "電話番号"
    
    if date_col not in df.columns or name_col not in df.columns:
        print(f"エラー: 必須列（'{date_col}'または'{name_col}'）が見つかりません。")
        return []

    salons = []
    for _, row in df.iterrows():
        if pd.isna(row[date_col]) or pd.isna(row[name_col]):
            continue

        raw_val = row[date_col]
        if isinstance(raw_val, pd.Timestamp):
            raw_date = raw_val.strftime("%Y-%m-%d")
        else:
            raw_date = str(raw_val).replace("/", "-").replace(" 00:00:00", "")[:10]

        base_addr = str(row.get(addr_col, "")).strip()
        sub_addr = str(row.get(sub_addr_col, "")).strip() if sub_addr_col in df.columns else ""
        
        if sub_addr and sub_addr != "nan":
            full_address = f"{base_addr} {sub_addr}"
        else:
            full_address = base_addr

        if full_address == "nan": full_address = ""
        
        tel = str(row.get(tel_col, "")).strip()
        if tel == "nan": tel = ""
            
        salons.append({
            "開設日": raw_date,
            "施設名": str(row[name_col]).strip(),
            "所在地": full_address,
            "電話番号": tel
        })
        
    return salons


def save_to_spreadsheet(salons):
    if not salons:
        print("追加するデータがありませんでした。")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)
    except Exception as e:
        print(f"スプレッドシートへの接続に失敗しました: {e}")
        return

    existing_names = sheet.col_values(2)
    
    add_count = 0
    rows_to_add = []
    
    for salon in salons:
        name = salon["施設名"]
        if name not in existing_names and name != "" and name != "nan":
            
            # ★追加機能：Google検索用のリンクを作成★
            # 検索キーワードを「店舗名 姫路」にして精度を上げる
            search_query = f"{name} 姫路"
            # URLで使える文字に変換
            encoded_query = urllib.parse.quote(search_query)
            # スプレッドシートのHYPERLINK関数を組み立てる
            google_link = f'=HYPERLINK("https://www.google.com/search?q={encoded_query}", "🔍Google検索")'

            rows_to_add.append([
                salon["開設日"],    # A列
                name,             # B列
                salon["所在地"],    # C列
                salon["電話番号"],   # D列
                google_link       # E列：Google検索リンク
            ])
            print(f"新規追加準備: {name} ({salon['開設日']})")
            add_count += 1
            existing_names.append(name)

    if rows_to_add:
        try:
            # ★ value_input_option="USER_ENTERED" を指定することで、関数（=HYPERLINK）が数式として正しく認識・反映されます
            sheet.append_rows(rows_to_add, value_input_option="USER_ENTERED")
            print(f"完了: {add_count}件をシートに書き込みました。")
        except Exception as e:
            print(f"書き込み中にエラーが発生しました: {e}")
    else:
        print("新しいサロン（シートに未登録のサロン）はありませんでした。")


if __name__ == "__main__":
    salons_list = import_local_excel()
    save_to_spreadsheet(salons_list)
