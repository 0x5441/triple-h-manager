import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://haraj.com.sa/"
COOKIES_DIR = Path(__file__).resolve().parent / "data" / "cookies"


def cookie_path(username):
    safe_username = "".join(char for char in username if char.isdigit())
    return COOKIES_DIR / f"{safe_username}.json"


def clean_cookie(cookie):
    allowed_keys = {
        "name",
        "value",
        "path",
        "domain",
        "secure",
        "httpOnly",
        "expiry",
        "sameSite",
    }

    cleaned = {
        key: value
        for key, value in cookie.items()
        if key in allowed_keys and value is not None
    }

    if "expiry" in cleaned:
        cleaned["expiry"] = int(cleaned["expiry"])

    if cleaned.get("sameSite") not in ("Strict", "Lax", "None"):
        cleaned.pop("sameSite", None)

    return cleaned


def main():
    username = input("أدخل رقم الحساب المراد فحص كوكيزه: ").strip()
    path = cookie_path(username)

    if not path.exists():
        print("لا يوجد ملف كوكيز لهذا الحساب")
        print("شغّل getcookies.py أولًا")
        return

    with open(path, "r", encoding="utf-8") as file:
        cookies = json.load(file)

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=ar")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # يجب فتح الدومين قبل إضافة الكوكيز
        driver.get(BASE_URL)

        added = 0

        for cookie in cookies:
            try:
                driver.add_cookie(clean_cookie(cookie))
                added += 1
            except Exception as error:
                print(f"تم تخطي كوكي غير صالح: {error}")

        print(f"تمت إضافة {added} من أصل {len(cookies)} كوكيز")

        driver.get(BASE_URL)
        driver.refresh()

        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="user-menu"]')
                )
            )

            print("نجح الاختبار: تم فتح الحساب بدون رقم أو كلمة مرور")

        except TimeoutException:
            print("فشل الاختبار: الكوكيز منتهية أو غير كافية")
            print("شغّل getcookies.py من جديد لتحديثها")
            driver.save_screenshot("testcookies_failed.png")

        time.sleep(5)

    except Exception as error:
        print(f"حدث خطأ أثناء فحص الكوكيز: {error}")
        driver.save_screenshot("testcookies_error.png")

    finally:
        input("اضغط Enter لإغلاق المتصفح...")
        driver.quit()


if __name__ == "__main__":
    main()