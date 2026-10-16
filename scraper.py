import datetime
import json
import os
import sys
import gspread
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

def setup_gspread():
    creds_json = os.environ.get("GCP_SA_KEY")
    if not creds_json:
        raise ValueError("Secretsに GCP_SA_KEY が設定されていません")
    creds_dict = json.loads(creds_json)

    client = gspread.service_account_from_dict(creds_dict)
    
    # スプレッドシート名「AI探客プログラム」を開く
    spreadsheet = client.open("AI探客プログラム")
    sheet = spreadsheet.worksheet("リジョブ") 
    return sheet

def scrape_rejob():
    new_jobs = []
    target_url = "https://relax-job.com/search?business_type=biyoshi.riyoshi&city=28201.28210.28216.28229.28381.28382.28464&employment=arbeit.business-consignment.contract-employee.other.regular-member&facility_type=barber-shop.hair-salon.haircolor-shop.haircut-shop.spa&pref=28&sort=new"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Accessing: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded")
        
        print("ページの読み込みを10秒待機しています...")
        page.wait_for_timeout(10000)

        links = page.query_selector_all("a")
        
        # 日本時間 (UTC+9) で日付取得
        JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
        today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        
        seen_urls = set()

        for link in links:
            try:
                href = link.get_attribute("href")
                if not href or "/job/" not in href:
                    continue

                full_url = f"https://relax-job.com{href}" if href.startswith("/") else href
                
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                parent = link.evaluate_handle("el => el.closest('li') || el.closest('div')")
                text = parent.inner_text().strip() if parent else ""
                
                if len(text) < 15:
                    continue

                lines = [line.strip() for line in text.split('\n') if line.strip()]

                # PR求人（広告枠）の除外判定
                if any(line in ["PR", "PR求人"] for line in lines[:5]):
                    print(f"PR求人をスキップしました: {full_url}")
                    continue

                title = lines[0] if len(lines) > 0 else "不明"
                company = lines[1] if len(lines) > 1 else "不明"

                new_jobs.append([today, company, title, "スプレッドシート上で確認", full_url])

            except Exception as e:
                continue

        print(f"画面から {len(new_jobs)} 件の求人リンク（PR除外済）を発見しました。")
        browser.close()

    return new_jobs

def main():
    sheet = setup_gspread()
    existing_urls = sheet.col_values(5)

    jobs = scrape_rejob()
    rows_to_add = []

    for job in jobs:
        url = job[4]
        if url not in existing_urls:
            rows_to_add.append(job)

    if rows_to_add:
        sheet.append_rows(rows_to_add)
        print(f"スプレッドシートに {len(rows_to_add)} 件の新店求人を追加しました。")
    else:
        print("新しい求人は見つかりませんでした。")

if __name__ == "__main__":
    main()
