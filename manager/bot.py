import platform
import random
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class HarajBot:
    BASE_URL = "https://haraj.com.sa/"

    def __init__(self, headless=False, logger=print):
        self.headless = headless
        self.log = logger
        self.driver = None
        self.wait = None

    def _open_browser(self, account):
        # Use same profile path logic as create_profile.py / test_profile.py
        try:
            from create_profile import get_profile_path
        except Exception:
            # fallback: build safe numeric-only folder
            def get_profile_path(username):
                return (
                    Path(__file__).resolve().parent
                    / "data"
                    / "profiles"
                    / "".join(c for c in str(username) if c.isdigit())
                )

        profile_dir = get_profile_path(account.get("username", ""))
        profile_dir.mkdir(parents=True, exist_ok=True)

        options = webdriver.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_dir.resolve()}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--lang=ar")
        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1000")

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 25)

    def _pause(self, low=0.7, high=1.8):
        time.sleep(random.uniform(low, high))

    def _click(self, testid):
        element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'[data-testid="{testid}"]')))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        self._pause(0.3, 0.8)
        element.click()
        self._pause()
        return element

    def _type(self, element, value):
        element.click()
        element.clear()
        position = 0
        while position < len(value):
            chunk_size = random.randint(2, 5)
            element.send_keys(value[position:position + chunk_size])
            position += chunk_size
            time.sleep(random.uniform(0.04, 0.13))

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

    def ensure_login(self, account):
        """Ensure the profile has an active session. If not, perform login.

        Returns True on success, raises on failure.
        """
        try:
            self.driver.get(self.BASE_URL)
        except WebDriverException as exc:
            raise RuntimeError("فشل فتح نافذة المتصفح أو أنها أغلقت مبكرًا") from exc
        # quick check if already logged in
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="user-menu"]'))
            )
            self.log("الجلسة محفوظة وصالحة، تم تجاوز تسجيل الدخول")
            return True
        except TimeoutException:
            pass

        # not logged in yet — attempt normal login
        username = account.get("username")
        password = account.get("password")
        if not username or not password:
            raise RuntimeError("بيانات الدخول ناقصة للبروفايل")

        try:
            self.login(username, password)
        except WebDriverException as exc:
            raise RuntimeError("خطأ في المتصفح أثناء محاولة تسجيل الدخول") from exc
        except Exception:
            raise

        # after login attempt, ensure user-menu appears (allow manual verification)
        try:
            WebDriverWait(self.driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="user-menu"]'))
            )
            self.log("الجلسة محفوظة وصالحة، تم تجاوز تسجيل الدخول")
            return True
        except TimeoutException:
            # allow user to complete verification manually if not headless
            if self.headless:
                raise RuntimeError("التحقق الإضافي لم يتم خلال المهلة (وعدم إمكانية التفاعل في الوضع الصامت)")
            # give user extra time to complete manual verification
            self.log("يرجى إكمال أي تحقق يدوي في المتصفح المفتوح. الانتظار لمدة 5 دقائق...")
            try:
                WebDriverWait(self.driver, 300).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="user-menu"]'))
                )
                self.log("الجلسة محفوظة وصالحة، تم تجاوز تسجيل الدخول")
                return True
            except TimeoutException:
                raise RuntimeError("لم يتم التأكد من نجاح تسجيل الدخول بعد انتظار التحقق اليدوي")
        except WebDriverException as exc:
            raise RuntimeError("نافذة المتصفح أغلقت أو حدث خطأ في WebDriver أثناء التأكد من الجلسة") from exc

    def refresh_profile_session(self, account):
        """Open profile, ensure login, and return structured result."""
        try:
            self._open_browser(account)
        except Exception as exc:
            msg = str(exc)
            if "user data directory is already in use" in msg.lower():
                return {"success": False, "message": "خطأ: بروفايل الحساب مفتوح بالفعل في متصفح آخر"}
            return {"success": False, "message": f"فشل فتح المتصفح: {msg}"}

        try:
            try:
                ok = self.ensure_login(account)
            except Exception as exc:
                return {"success": False, "message": str(exc)}
            if ok:
                return {"success": True, "message": "تم تجديد الجلسة بنجاح"}
            return {"success": False, "message": "فشل التأكد من الجلسة"}
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass

    def _fill_phone_field(self, phone):
        selector = '[data-testid="step-five-mobile-input"]'
        field = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))

        for attempt in range(2):
            field.click()
            if platform.system() == "Darwin":
                field.send_keys(Keys.COMMAND, "a")
            else:
                field.send_keys(Keys.CONTROL, "a")
            field.send_keys(Keys.BACKSPACE)
            field.clear()
            self.driver.execute_script(
                """
                const el = arguments[0];
                el.value = '';
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                field,
            )
            field.send_keys(phone)
            actual = self.driver.execute_script("return arguments[0].value;", field)
            if actual == phone:
                return
            self.log(f"قيمة حقل رقم الجوال غير صحيحة، إعادة المحاولة {attempt + 1}/2")

        raise RuntimeError("فشل التحقق من حقل رقم الجوال بعد المحاولة الثانية")

    def publish_ad(self, ad, dry_run=False):
        title = str(ad.get("title", "")).strip()
        body = str(ad.get("body", "")).strip()
        phone = str(ad.get("phone", "96659209962")).strip()
        if not title or not body:
            raise ValueError("العنوان أو نص الإعلان فارغ في Google Sheets")

        self.driver.get(self.BASE_URL)
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        self._pause(1.0, 2.2)
        self._click("add-post-button")
        self._click("post-type-458-label")

        agreement = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="step-two-agreement-checkbox"]')))
        if not agreement.is_selected():
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", agreement)
            agreement.click()
        self._pause()
        self._click("step-two-resume")
        self._click("step-four-resume")

        title_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="new-post-title"]')))
        self._type(title_input, title)
        self._pause()

        self._fill_phone_field(phone)
        self._pause()

        body_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="add-post-bodyText"]')))
        self._type(body_input, body)
        self._pause(1.0, 2.0)

        image = str(ad.get("image", "")).strip()
        if image:
            raise RuntimeError("يوجد مسار صورة في الشيت لكن محدد رفع الصور لم يُضف بعد")
        if dry_run:
            self.log("وضع التجربة: عُبئت البيانات ولم يُضغط زر إنشاء الإعلان")
            return
        self._click("post-submit")
        WebDriverWait(self.driver, 20).until(
            EC.any_of(
                EC.url_changes(self.driver.current_url),
                EC.invisibility_of_element_located((By.CSS_SELECTOR, '[data-testid="post-submit"]')),
            )
        )

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
            self._open_browser(account)
            self.ensure_login(account)
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

    def run_publish(self, account, ad, dry_run=False):
        try:
            self._open_browser(account)
            self.ensure_login(account)
            self.publish_ad(ad, dry_run=dry_run)
            return {"success": 1, "failed": 0}
        except Exception:
            try:
                self.log(f"حُفظت صورة الخطأ: {self._screenshot(account['name'])}")
            except Exception:
                pass
            raise
        finally:
            if self.driver:
                self.driver.quit()
