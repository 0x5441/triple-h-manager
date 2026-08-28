import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class HarajBot:
    BASE_URL = "https://haraj.com.sa/"

    def __init__(self, headless=False, logger=print):
        self.headless = headless
        self.log = logger
        self.driver = None
        self.wait = None

    def _open_browser(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=ar")
        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1000")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 25)

    def login(self, username, password):
        self.driver.get(self.BASE_URL)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="login-link"]'))).click()
        username_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="auth_username"]')))
        username_input.clear()
        username_input.send_keys(username)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="auth_submit_username"]'))).click()
        password_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="auth_password"]')))
        password_input.clear()
        password_input.send_keys(password)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="auth_submit_login"]'))).click()

        try:
            WebDriverWait(self.driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="user-menu"]')),
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, '[data-testid="auth_password"]')),
                )
            )
        except TimeoutException as exc:
            raise RuntimeError("لم ينجح تسجيل الدخول أو ظهرت خطوة تحقق إضافية") from exc
        self.log("تم تسجيل الدخول")

    def update_ad(self, url):
        self.driver.get(url)
        button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="update-button"]')))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", button)
        # لا نفرض رسالة نجاح محددة لأن واجهة حراج قد تغيّر نص التنبيه.
        # نجاح هذه الخطوة يعني أن الزر وُجد وأُرسل له النقر بلا خطأ.
        time.sleep(2)

    def _screenshot(self, account_name):
        folder = Path(__file__).resolve().parent / "data" / "errors"
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in account_name if c.isalnum() or c in "-_ ").strip() or "account"
        path = folder / f"{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.png"
        if self.driver:
            self.driver.save_screenshot(str(path))
        return path

    def run_account(self, account):
        result = {"success": 0, "failed": 0}
        try:
            self._open_browser()
            self.login(account["username"], account["password"])
            for number, url in enumerate(account["ads"], start=1):
                try:
                    self.log(f"تحديث الإعلان {number}/{len(account['ads'])}")
                    self.update_ad(url)
                    result["success"] += 1
                    self.log(f"نجح: {url}")
                except Exception as exc:
                    result["failed"] += 1
                    self.log(f"فشل الإعلان: {url} — {exc}")
                    try:
                        self.log(f"حُفظت صورة الخطأ: {self._screenshot(account['name'])}")
                    except Exception:
                        pass
        finally:
            if self.driver:
                self.driver.quit()
        return result
