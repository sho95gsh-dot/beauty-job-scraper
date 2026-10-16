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
    
    # 既存の行数（次に追加する行の開始位置を把握するため）
    start_row = len(sheet.get_all_values()) + 1
    
    add_count = 0
    rows_to_add = []
    links_to_format = []
    
    for salon in salons:
        name = salon["施設名"]
        if name not in existing_names and name != "" and name != "nan":
            
            # Google検索リンクのURLを作成
            search_query = f"{name} 姫路"
            encoded_query = urllib.parse.quote(search_query)
            google_url = f"https://www.google.com/search?q={encoded_query}"

            # A〜E列のテキストデータを準備（E列はとりあえず文字だけ入れる）
            rows_to_add.append([
                salon["開設日"],    # A列
                name,             # B列
                salon["所在地"],    # C列
                salon["電話番号"],   # D列
                "🔍Google検索"      # E列のテキスト
            ])
            
            # E列に設定するリンク情報を保存しておく
            current_row = start_row + add_count
            links_to_format.append({
                "range": f"E{current_row}",
                "url": google_url
            })
            
            print(f"新規追加準備: {name} ({salon['開設日']})")
            add_count += 1
            existing_names.append(name)

    if rows_to_add:
        try:
            # 1. まずテキストデータを一括で書き込む（関数を使わない）
            sheet.append_rows(rows_to_add, value_input_option="RAW")
            
            # 2. 追加した行のE列に「ハイパーリンク書式」を一括で設定する
            requests = []
            for link_data in links_to_format:
                # セル範囲をオブジェクトに変換
                cell_range = gspread.utils.a1_range_to_grid_range(link_data["range"], sheet.id)
                # ハイパーリンクを設定するリクエストを作成
                requests.append({
                    "updateCells": {
                        "range": cell_range,
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {"stringValue": "🔍Google検索"},
                                        "userEnteredFormat": {
                                            "textFormat": {
                                                "link": {"uri": link_data["url"]},
                                                "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 1.0}, # 青色にする
                                                "underline": True
                                            }
                                        }
                                    }
                                ]
                            }
                        ],
                        "fields": "userEnteredValue,userEnteredFormat.textFormat(link,foregroundColor,underline)"
                    }
                })
            
            # リクエストを実行してリンク書式を反映
            if requests:
                client.open_by_key(SPREADSHEET_KEY).batch_update({"requests": requests})
                
            print(f"完了: {add_count}件をシートに書き込みました。")
        except Exception as e:
            print(f"書き込み中にエラーが発生しました: {e}")
    else:
        print("新しいサロン（シートに未登録のサロン）はありませんでした。")


if __name__ == "__main__":
    salons_list = import_local_excel()
    save_to_spreadsheet(salons_list)
