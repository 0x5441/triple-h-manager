from getpass import getpass
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://haraj.com.sa/"


def clean_username(username):
    return "".join(character for character in username if character.isdigit())


def get_profile_path(username):
    profile_path = (
        Path(__file__).resolve().parent
        / "data"
        / "profiles"
        / clean_username(username)
    )

    profile_path.mkdir(parents=True, exist_ok=True)
    return profile_path


def open_browser(username):
    profile_path = get_profile_path(username)

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--lang=ar")

    driver = webdriver.Chrome(options=options)

    print(f"تم فتح البروفايل:")
    print(profile_path)

    return driver


def main():
    username = input("أدخل رقم حساب حراج: ").strip()
    password = getpass("أدخل كلمة المرور: ").strip()

    if not username or not password:
        print("رقم الحساب أو كلمة المرور فارغة")
        return

    driver = None

    try:
        driver = open_browser(username)
        wait = WebDriverWait(driver, 25)

        driver.get(BASE_URL)

        # إذا كان البروفايل مسجلًا مسبقًا
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="user-menu"]')
                )
            )

            print("البروفايل مسجل دخول مسبقًا")
            input("اضغط Enter لإغلاق المتصفح...")
            return

        except TimeoutException:
            pass

        login_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="login-link"]')
            )
        )
        login_button.click()

        username_input = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="auth_username"]')
            )
        )
        username_input.click()
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
        password_input.click()
        password_input.clear()
        password_input.send_keys(password)

        wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="auth_submit_login"]')
            )
        ).click()

        print("تم إرسال بيانات الدخول")
        print("إذا ظهر رمز تحقق أكمله يدويًا داخل المتصفح")

        try:
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="user-menu"]')
                )
            )

            print("نجح تسجيل الدخول")
            print("تم حفظ الجلسة تلقائيًا داخل البروفايل")

        except TimeoutException:
            print("لم يتم التأكد من نجاح تسجيل الدخول خلال دقيقتين")
            driver.save_screenshot("create_profile_failed.png")

        input("اضغط Enter بعد التأكد من دخول الحساب لإغلاق المتصفح...")

    except Exception as error:
        print(f"حدث خطأ: {error}")

        if driver:
            driver.save_screenshot("create_profile_error.png")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()