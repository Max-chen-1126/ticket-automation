import os
import random
import re
import time

import ddddocr
from dotenv import load_dotenv
from playwright.sync_api import TimeoutError, sync_playwright

load_dotenv()

# ================= 配置讀取 =================
FB_EMAIL = os.getenv("FB_EMAIL")
FB_PASSWORD = os.getenv("FB_PASSWORD")
TARGET_URL = os.getenv("TARGET_URL")
TARGET_DATE = os.getenv("TARGET_DATE")
TARGET_AREA_REGEX = os.getenv("TARGET_AREA_REGEX")
TARGET_QTY = os.getenv("TARGET_QTY")
COOKIES_STRING = os.getenv("COOKIES_STRING")
# ===========================================


def apply_stealth(page):
    """
    手動注入 JavaScript 以隱藏自動化特徵，繞過 WAF 防火牆
    """
    # 1. 移除 navigator.webdriver 屬性 (這是最主要的機器人特徵)
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # 2. 偽造 window.chrome 屬性 (讓你看起來像真的 Chrome)
    page.add_init_script("""
        window.chrome = {
            runtime: {}
        };
    """)

    # 3. 偽造 navigator.plugins (無頭瀏覽器通常是空的)
    page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)

    # 4. 偽造 navigator.languages (設定為台灣繁體中文)
    page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-TW', 'zh', 'en-US', 'en']
        });
    """)

    # 5. 偽造權限查詢行為
    page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'prompt', onchange: null }) :
            originalQuery(parameters)
        );
    """)


def parse_cookie_string(cookie_str):
    cookies = []
    if not cookie_str:
        return cookies
    items = cookie_str.split(';')
    for item in items:
        if '=' in item:
            name, value = item.strip().split('=', 1)
            cookies.append({
                "name": name,
                "value": value,
                "domain": ".tixcraft.com",
                "path": "/"
            })
    return cookies


def run():
    print("🧠 正在載入 OCR 模型...")
    ocr = ddddocr.DdddOcr(show_ad=False)
    print("✅ OCR 模型載入完成")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
        )

        context = browser.new_context(viewport={"width": 1280, "height": 800})

        page = context.new_page()
        apply_stealth(page)

        if COOKIES_STRING:
            print("🍪 偵測到 Cookie 字串，正在解析並注入...")
            cookies = parse_cookie_string(COOKIES_STRING)
            if cookies:
                context.add_cookies(cookies)
                print(f"✅ 已注入 {len(cookies)} 個 Cookie！")

        page.set_default_timeout(30000)

        # ==========================================
        # STEP 0: 檢查登入
        # ==========================================
        try:
            print("🕵️ 檢查登入狀態...")
            page.goto("https://tixcraft.com")

            if "Browsing Activity Has Been Paused" in page.title() or "Incapsula" in page.content():
                print("🚨 警告：目前 IP 被暫時封鎖！請手動在瀏覽器解決驗證碼...")
                page.pause()

            try:
                # 檢查是否存在登入按鈕，若存在代表 Cookie 失效
                login_btn = page.locator("a[href*='/login']").first
                if login_btn.is_visible():
                    print("⚠️ 偵測到登入按鈕，Cookie 可能失效，嘗試自動登入...")
                    page.goto("https://tixcraft.com/login/facebook")

                    try:
                        page.wait_for_selector("#email", timeout=5000)
                        page.locator("#email").fill(FB_EMAIL)
                        page.locator("#pass").fill(FB_PASSWORD)
                        page.locator("#loginbutton").click()
                        page.wait_for_url(
                            "https://tixcraft.com**", timeout=15000)
                    except Exception:  # [修正] 使用 Exception 而非 bare except
                        pass
                else:
                    print("🎉 似乎已是登入狀態")
            except Exception:  # [修正] 忽略檢查過程中的錯誤
                print("ℹ️ 登入檢查遭遇例外，假設已登入，繼續執行...")

        except Exception as e:
            print(f"⚠️ 登入流程發生錯誤: {e}")

        # ==========================================
        # STEP 1: 進入活動頁面 & 等待開賣
        # ==========================================
        print(f"🎯 前往目標活動頁面: {TARGET_URL}")
        page.goto(TARGET_URL)

        # [修正] 移除了未使用的 retry_count 變數
        while True:
            try:
                if "Paused" in page.title() or "unusual behavior" in page.content():
                    print("\n" + "=" * 40)
                    print("🚨🚨🚨 被防火牆擋住了！請手動解鎖 🚨🚨🚨")
                    print("=" * 40 + "\n")
                    time.sleep(10)
                    page.reload()
                    continue

                row = page.locator(f"tr:has-text('{TARGET_DATE}')")
                buy_btn = row.locator("button", has_text="立即訂購")

                if buy_btn.is_visible() and buy_btn.is_enabled():
                    print("✅ 按鈕亮起！點擊中...")
                    buy_btn.click()
                    break
                else:
                    sleep_time = random.uniform(1.5, 3.0)
                    print(f"⏳ 等待開賣... (下次刷新: {sleep_time:.2f}s 後)")
                    time.sleep(sleep_time)
                    page.reload()

            except Exception as e:
                print(f"⚠️ 刷新錯誤: {e}")
                time.sleep(2)
                page.reload()

        # ==========================================
        # STEP 2: 選擇區域
        # ==========================================
        try:
            page.wait_for_selector(".area-list", timeout=10000)
        except TimeoutError:
            print("⚠️ 載入區域頁面緩慢")

        # 電腦配位
        try:
            auto_select_radio = page.locator("#select_form_auto")
            if auto_select_radio.count() > 0:
                if not auto_select_radio.is_checked():
                    auto_select_radio.check()
        except Exception:  # [修正] 使用 Exception
            pass

        available_areas = page.locator(
            "ul.area-list > li:not(:has-text('已售完')) > a")
        count = available_areas.count()
        print(f"🔍 掃描到 {count} 個可選區域...")

        matched_elements = []
        for i in range(count):
            element = available_areas.nth(i)
            area_text = element.inner_text()
            if re.search(TARGET_AREA_REGEX, area_text):
                matched_elements.append(element)

        if matched_elements:
            target = random.choice(matched_elements)
            print(f"🎯 鎖定區域: {target.inner_text()}")
            target.click()
        else:
            print("❌ 無符合區域，嘗試點擊第一個...")
            if count > 0:
                available_areas.first.click()
            else:
                print("💀 全面售罄")
                return

        # ==========================================
        # STEP 3: 選擇張數 & 驗證碼
        # ==========================================
        try:
            page.wait_for_selector(
                "select[id^='TicketForm_ticketPrice_']", timeout=15000)
        except Exception:  # [修正] 使用 Exception
            print("❌ 載入票價頁面失敗")
            return

        # 選擇張數
        try:
            select_box = page.locator(
                "select[id^='TicketForm_ticketPrice_']").first
            select_box.select_option(TARGET_QTY)
            print(f"✅ 已選擇張數: {TARGET_QTY}")
        except Exception:  # [修正] 使用 Exception
            print("⚠️ 無法選擇目標張數，嘗試選 1...")
            try:
                page.locator(
                    "select[id^='TicketForm_ticketPrice_']").first.select_option("1")
            except Exception:  # [修正] 使用 Exception
                pass

        page.locator("#TicketForm_agree").check()

        verify_img_locator = page.locator("#TicketForm_verifyCode-image")
        verify_input = page.locator("#TicketForm_verifyCode")

        max_ocr_retries = 3
        for attempt in range(max_ocr_retries):
            try:
                print(f"👀 識別驗證碼 (嘗試 {attempt+1}/{max_ocr_retries})...")

                verify_img_locator.wait_for(state="visible", timeout=3000)
                time.sleep(0.5)

                img_bytes = verify_img_locator.screenshot()
                res_code = ocr.classification(img_bytes)
                print(f"🤖 辨識結果: '{res_code}'")

                if res_code and len(res_code) >= 4:
                    verify_input.fill(res_code)
                    print("🚀 發送！")
                    verify_input.press("Enter")
                    break
                else:
                    print("⚠️ 結果異常，點擊圖片刷新...")
                    verify_img_locator.click()
                    time.sleep(1.5)
            except Exception as e:
                print(f"❌ OCR 錯誤: {e}")
                if attempt == max_ocr_retries - 1:
                    print("🚨 自動識別失敗，請手動輸入！")
                    verify_input.focus()

        try:
            page.wait_for_url("**/checkout/**", timeout=20000)
            print("\n🎉🎉🎉 成功進入結帳頁面！\n")
        except Exception:  # [修正] 使用 Exception
            print("ℹ️ 等待跳轉超時，請檢查瀏覽器狀態。")

        time.sleep(600)


if __name__ == "__main__":
    run()
