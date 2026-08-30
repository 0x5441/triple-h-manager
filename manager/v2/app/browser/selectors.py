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
    ADD_POST_BUTTON = (By.CSS_SELECTOR, '[data-testid="add-post-button"]')
    INCOMPLETE_POST_DISCARD = (By.CSS_SELECTOR, '[data-testid="old-exist-clear"]')
    SERVICE_POST_TYPE = (By.CSS_SELECTOR, '[data-testid="post-type-458-label"]')
    AGREEMENT_CHECKBOX = (By.CSS_SELECTOR, '[data-testid="step-two-agreement-checkbox"]')
    STEP_TWO_CONTINUE = (By.CSS_SELECTOR, '[data-testid="step-two-resume"]')
    STEP_FOUR_CONTINUE = (By.CSS_SELECTOR, '[data-testid="step-four-resume"]')
    POST_TITLE_INPUT = (By.CSS_SELECTOR, '[data-testid="new-post-title"]')
    POST_MOBILE_INPUT = (By.CSS_SELECTOR, '[data-testid="step-five-mobile-input"]')
    POST_BODY_INPUT = (By.CSS_SELECTOR, '[data-testid="add-post-bodyText"]')
    POST_SUBMIT = (By.CSS_SELECTOR, '[data-testid="post-submit"]')
