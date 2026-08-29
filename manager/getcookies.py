import json
import time
from getpass import getpass
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://haraj.com.sa/"
COOKIES_DIR = Path(__file__).resolve().parent / "data" / "cookies"


def cookie_path(username):
    safe_username = "".join(char for char in username if char.isdigit())
    return COOKIES_DIR / f"{safe_username}.json"


def main():
    username = input("أدخل رقم الحساب: ").strip()
    password = getpass("أدخل كلمة المرور: ").strip()

    if not username or not password:
        print("رقم الحساب أو كلمة المرور فارغة")
        return

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=ar")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get(BASE_URL)

        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="login-link"]')
            )
        ).click()

        username_input = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="auth_username"]')
            )
        )
        username_input.clear()
        username_input.send_keys(username)

        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="auth_submit_username"]')
            )
        ).click()

        password_input = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="auth_password"]')
            )
        )
        password_input.clear()
        password_input.send_keys(password)

        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="auth_submit_login"]')
            )
        ).click()

        wait.until(
            EC.any_of(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="user-menu"]')
                ),
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="auth_password"]')
                ),
            )
        )

        time.sleep(3)

        cookies = driver.get_cookies()

        if not cookies:
            raise RuntimeError("لم يتم العثور على كوكيز بعد تسجيل الدخول")

        COOKIES_DIR.mkdir(parents=True, exist_ok=True)
        path = cookie_path(username)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(cookies, file, ensure_ascii=False, indent=2)

        print(f"تم حفظ {len(cookies)} كوكيز")
        print(f"المسار: {path}")

    except Exception as error:
        print(f"فشل تسجيل الدخول أو حفظ الكوكيز: {error}")
        driver.save_screenshot("getcookies_error.png")

    finally:
        input("اضغط Enter لإغلاق المتصفح...")
        driver.quit()


if __name__ == "__main__":
    main()