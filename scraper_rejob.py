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

                # 求人カード全体（外枠）を確実に取得する
                # 直近の小さなdivで止まらず、情報がまとまっている親要素まで遡る
                card = link.evaluate_handle("""el => {
                    let container = el.closest('article') || el.closest('li');
                    if (container) return container;
                    let cur = el;
                    while (cur && cur.parentElement && cur.parentElement !== document.body) {
                        cur = cur.parentElement;
                        if (cur.tagName === 'DIV' && cur.innerText && cur.innerText.length > 80) {
                            return cur;
                        }
                    }
                    return el.parentElement;
                }""")

                # PR求人（広告枠）の検知
                is_pr = card.evaluate("""el => {
                    // 1. 広告枠・PR枠専用のコンテナに属しているか
                    if (el.closest('[class*="pr-"], [class*="--pr"], [class*="is-pr"], [class*="pickup"], [class*="sponsor"]')) {
                        return true;
                    }
                    // 2. カード内に単独で「PR」「ＰＲ」「PR求人」と書かれたラベルがあるか
                    const tags = Array.from(el.querySelectorAll('span, div, p, em, strong, i, b'));
                    return tags.some(t => {
                        const txt = t.innerText ? t.innerText.trim() : '';
                        return txt === 'PR' || txt === 'ＰＲ' || txt === 'PR求人';
                    });
                }""")

                text = card.inner_text().strip() if card else ""
                lines = [line.strip() for line in text.split('\n') if line.strip()]

                # テキスト全体からも念のため判定
                if not is_pr and any(line in ["PR", "PR求人", "ＰＲ"] for line in lines):
                    is_pr = True

                if is_pr:
                    print(f"【PR除外】スキップしました: {full_url}")
                    continue

                # テキストが短すぎるものは除外
                if len(text) < 15:
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
