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
    sheet = spreadsheet.worksheet("求人ボックス")
    return sheet

def scrape_kyujinbox():
    new_jobs = []
    # 検索したい求人ボックスのURL（新着順）
    target_url = "https://xn--pckua2a7gp15o89zb.com/adv/?keyword=%E7%BE%8E%E5%AE%B9%E5%B8%AB%20or:%E7%90%86%E5%AE%B9%E5%B8%AB&area=%E5%85%B5%E5%BA%AB%E7%9C%8C%E5%A7%AB%E8%B7%AF%E5%B8%82%20or:%E5%85%B5%E5%BA%AB%E7%9C%8C%E5%8A%A0%E5%8F%A4%E5%B7%9D%E5%B8%82%20or:%E5%85%B5%E5%BA%AB%E7%9C%8C%E3%81%9F%E3%81%A4%E3%81%AE%E5%B8%82%20or:%E5%85%B5%E5%BA%AB%E7%9C%8C%E6%92%AD%E7%A3%A8%E7%94%BA%20or:%E5%85%B5%E5%BA%AB%E7%9C%8C%E5%A4%AA%E5%AD%90%E7%94%BA&e=1,2,5,3,4,6&u=2"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        print(f"Accessing: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded")
        
        print("ページの読み込みを待機しています...")
        page.wait_for_timeout(8000)

        links = page.query_selector_all("a")
        
        # 日本時間 (UTC+9) で日付取得
        JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
        today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        
        seen_urls = set()

        for link in links:
            try:
                href = link.get_attribute("href")
                if not href or "/jb/" not in href:
                    continue

                full_url = f"https://xn--pckua2a7gp15o89zb.com{href}" if href.startswith("/") else href
                # URLのパラメータ（?以降）を消して重複防止
                clean_url = full_url.split("?")[0]
                
                if clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)

                parent = link.evaluate_handle("el => el.closest('section') || el.closest('li') || el.closest('div')")
                text = parent.inner_text().strip() if parent else ""
                
                if len(text) < 15:
                    continue

                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                link_text = link.inner_text().strip()
                title = link_text if link_text else (lines[0] if len(lines) > 0 else "不明")
                company = lines[1] if len(lines) > 1 else "不明"

                new_jobs.append([today, company, title, "求人ボックス", clean_url])

            except Exception as e:
                continue

        print(f"画面から {len(new_jobs)} 件の求人リンクを発見しました。")
        browser.close()

    return new_jobs

def main():
    sheet = setup_gspread()
    existing_urls = sheet.col_values(5)

    jobs = scrape_kyujinbox()
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
