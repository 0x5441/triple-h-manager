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
    return (
        Path(__file__).resolve().parent
        / "data"
        / "profiles"
        / clean_username(username)
    )


def main():
    username = input("أدخل رقم الحساب المراد اختبار بروفايله: ").strip()
    profile_path = get_profile_path(username)

    if not profile_path.exists():
        print("لا يوجد بروفايل لهذا الحساب")
        print("شغّل create_profile.py أولًا")
        return

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--lang=ar")

    driver = None

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(BASE_URL)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[data-testid="user-menu"]')
                )
            )

            print("نجح الاختبار")
            print("البروفايل حفظ الجلسة والحساب مفتوح بدون تسجيل دخول")

        except TimeoutException:
            print("فشل الاختبار")
            print("البروفايل موجود لكن جلسة حراج غير محفوظة أو منتهية")
            driver.save_screenshot("test_profile_failed.png")

        input("اضغط Enter لإغلاق المتصفح...")

    except Exception as error:
        print(f"حدث خطأ أثناء فتح البروفايل: {error}")

        if "user data directory is already in use" in str(error).lower():
            print("البروفايل مفتوح في متصفح آخر؛ أغلقه ثم أعد الاختبار")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()