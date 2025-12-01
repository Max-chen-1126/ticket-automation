from playwright.sync_api import sync_playwright


def run():
    with sync_playwright() as p:
        # headless=False 代表看得到視窗
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("正在前往 Google...")
        page.goto("https://www.google.com")

        print(f"網頁標題是: {page.title()}")
        page.screenshot(path="google_screenshot.png")

        browser.close()
        print("完成！")


if __name__ == "__main__":
    run()
