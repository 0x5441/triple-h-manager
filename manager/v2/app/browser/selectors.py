"""Single source of truth for Haraj element locators."""

from selenium.webdriver.common.by import By


class HarajSelectors:
    LOGIN_LINK = (By.CSS_SELECTOR, '[data-testid="login-link"]')
    USERNAME_INPUT = (By.CSS_SELECTOR, '[data-testid="auth_username"]')
    USERNAME_CONTINUE = (By.CSS_SELECTOR, '[data-testid="auth_submit_username"]')
    PASSWORD_INPUT = (By.CSS_SELECTOR, '[data-testid="auth_password"]')
    LOGIN_SUBMIT = (By.CSS_SELECTOR, '[data-testid="auth_submit_login"]')
    USER_MENU = (By.CSS_SELECTOR, '[data-testid="user-menu"]')
    UPDATE_BUTTON = (By.CSS_SELECTOR, '[data-testid="update-button"]')
