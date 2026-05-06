#!/usr/bin/env python3
# Timestamp: "2025-08-21 14:44:29 (ywatanabe)"
# File: /home/ywatanabe/proj/SciTeX-Code/src/scitex/scholar/auth/sso_automation/_UniversityOfMelbourneSSOAutomator.py
# ----------------------------------------
from __future__ import annotations

import os

__FILE__ = __file__
__DIR__ = os.path.dirname(__FILE__)
# ----------------------------------------

"""University of Melbourne SSO automation."""

from typing import Optional

from playwright.async_api import Page, TimeoutError

# from scitex_scholar.browser import BrowserUtils
from scitex_browser.interaction import (
    click_with_fallbacks_async,
    fill_with_fallbacks_async,
)

from scitex_scholar.config import ScholarConfig

from .BaseSSOAutomator import BaseSSOAutomator


class UniversityOfMelbourneSSOAutomator(BaseSSOAutomator):
    """SSO automator for University of Melbourne."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        config: Optional[ScholarConfig] = None,
        **kwargs,
    ):
        """Initialize UniMelb SSO automator.

        Args:
            username: UniMelb username (defaults to UNIMELB_SSO_USERNAME env var)
            password: UniMelb password (defaults to UNIMELB_SSO_PASSWORD env var)
            config: ScholarConfig
            **kwargs: Additional arguments for BaseSSOAutomator
        """
        # Get credentials from environment if not provided
        if config is None:
            config = ScholarConfig()

        _u = config.resolve("sso_username", username, default="")
        _p = config.resolve("sso_password", password, default="")
        username = _u if isinstance(_u, str) else ""
        password = _p if isinstance(_p, str) else ""

        super().__init__(username=username, password=password, **kwargs)

    def get_institution_name(self) -> str:
        """Get human-readable institution name."""
        return "University of Melbourne"

    def get_institution_id(self) -> str:
        """Get machine-readable institution ID."""
        return "unimelb"

    def is_sso_page(self, url: str) -> bool:
        """Check if URL is UniMelb SSO page."""
        sso_domains = [
            "login.unimelb.edu.au",
            "okta.unimelb.edu.au",
            "authenticate_async.unimelb.edu.au",
            "sso.unimelb.edu.au",
        ]
        return any(domain in url.lower() for domain in sso_domains)

    async def perform_login_async(self, page: Page) -> bool:
        """Perform UniMelb login flow using proven working patterns."""
        try:
            self.logger.info("Starting UniMelb SSO login with proven patterns")

            # Step 1: Handle username entry (first step - proven working pattern)
            username_success = await self._handle_username_step_async(page)
            if not username_success:
                # Try generic login as fallback
                self.logger.info("Trying generic login form detection as fallback")
                username_success = await self._handle_generic_login_async(page)
                if not username_success:
                    return False

            # Step 2: Handle password entry (second step)
            password_success = await self._handle_password_step_async(page)
            if not password_success:
                return False

            # Step 3: Handle 2FA if needed (click push button)
            await self._handle_duo_authentication_async(page)

            # Return immediately after filling forms
            # BrowserAuthenticator will handle monitoring and notifications
            self.logger.info(
                "Form filling complete - returning to caller for monitoring"
            )
            return True

        except Exception as e:
            self.logger.error(f"UniMelb SSO login failed: {e}")
            await self._take_debug_screenshot_async(page)

            # Send failure notification
            await self.notify_user_async("authentication_failed", error=str(e))

            return False

    async def _handle_username_step_async(self, page: Page) -> bool:
        """Handle username entry using proven working selector."""
        try:
            # Use the proven working selector from your implementation
            username_selector = "input[name='identifier']"

            success = await fill_with_fallbacks_async(
                page, username_selector, self.username
            )
            if not success:
                self.logger.error("Failed to fill username field")
                return False

            self.logger.info(f"Filled username: {self.username}")

            # Click Next button using proven working selector and JavaScript click
            next_selector = "input.button-primary[value='Next']"
            success = await click_with_fallbacks_async(page, next_selector)
            if not success:
                self.logger.error("Failed to click Next button")
                return False

            self.logger.info("Next button clicked successfully")

            # Small delay for page transition
            await page.wait_for_timeout(1000)
            return True

        except Exception as e:
            self.logger.error(f"Username step failed: {e}")
            return False

    async def _handle_password_step_async(self, page: Page) -> bool:
        """Handle password entry — Okta UI refresh 2026-05-06.

        The Verify button is now a `<button type='submit'>` with text
        'Verify' (was `<input type='submit' value='Verify'>` pre-2026-05).
        Try the legacy selector first for backward compat, then fall
        back to the new shape.
        """
        try:
            password_selector = "input[name='credentials.passcode']"
            success = await fill_with_fallbacks_async(
                page, password_selector, self.password
            )
            if not success:
                self.logger.error("Failed to fill password field")
                return False

            self.logger.info("Password filled successfully")

            for verify_selector in (
                "input[type='submit'][value='Verify']",
                "button[type='submit']:has-text('Verify')",
                "button.button-primary:has-text('Verify')",
                "form button[type='submit']",
            ):
                if await click_with_fallbacks_async(page, verify_selector):
                    self.logger.info(
                        f"Verify button clicked successfully "
                        f"(selector={verify_selector!r})"
                    )
                    # Okta sometimes shows a new MFA-method picker after
                    # password. Handle if present.
                    await page.wait_for_timeout(1500)
                    await self._handle_mfa_select_step_async(page)
                    return True

            self.logger.error("Failed to click Verify button — all selectors failed")
            return False

        except Exception as e:
            self.logger.error(f"Password step failed: {e}")
            return False

    async def _save_debug_screenshot_async(self, page: Page, label: str) -> None:
        """Capture screenshot + page HTML via the shared scitex-browser helper.

        Writes both artifacts to
        `~/.scitex/scholar/cache/engine/screenshots/sso_<label>_<ts>.{png,html}`.

        Browser automation is fundamentally unreliable; HTML alongside
        the screenshot is what makes "the locator picked the wrong row"
        post-mortem actually possible.
        """
        from pathlib import Path

        from scitex_browser.debugging import capture_debug_artifacts_async

        await capture_debug_artifacts_async(
            page,
            label=f"sso_{label}",
            base_dir=Path.home()
            / ".scitex"
            / "scholar"
            / "cache"
            / "engine"
            / "screenshots",
        )

    async def _handle_mfa_select_step_async(self, page: Page) -> bool:
        """Pick an MFA method on the post-password 'Verify it's you with a
        security method' page (Okta UI refresh 2026-05-06).

        Page typically shows two 'Select' buttons — one for Okta Verify
        push notification, one for Okta Verify code entry. Push is the
        cleanest hand-off (user just taps phone), so prefer that.

        Implementation note: a CSS chain `div:has-text('X') >> button` is
        ambiguous on Okta's layout — any ancestor container that *also*
        contains the other row's text matches, and the first-DOM Select
        (top row, 'Enter a code') gets clicked regardless of preference.
        Use Playwright `Locator.filter(has_text=...)` to scope by ROW.

        No-op if the page isn't a method picker.
        """
        try:
            # Heuristic: only fire on the picker page.
            heading = await page.query_selector(
                "h2:has-text('security method'), h2:has-text('Verify it')"
            )
            if heading is None:
                return False

            await self._save_debug_screenshot_async(page, "mfa_picker_before")
            self.logger.info("MFA method picker detected — preferring Okta Verify push")

            # Use Playwright Locator API with row-scoped filtering AND
            # negative filtering. `.filter(has_text='X')` alone matches
            # any ancestor whose subtree contains 'X' — including the
            # outer container that contains BOTH options. The first-DOM
            # Select inside that container is 'Enter a code' (top row),
            # so push always lost. Add `has_not_text` to exclude rows
            # that *also* contain the other option's text — the leaf
            # row passes (only its own text), the outer container fails
            # (has both).
            row_candidates = (
                (
                    "push",
                    page.locator("li, div")
                    .filter(has_text="Get a push notification")
                    .filter(has_not_text="Enter a code")
                    .get_by_text("Select", exact=True)
                    .first,
                ),
                (
                    "code",
                    page.locator("li, div")
                    .filter(has_text="Enter a code")
                    .filter(has_not_text="Get a push notification")
                    .get_by_text("Select", exact=True)
                    .first,
                ),
            )

            for kind, locator in row_candidates:
                try:
                    count = await locator.count()
                except Exception:
                    count = 0
                if not count:
                    self.logger.debug(f"No row-scoped Select for kind={kind}")
                    continue
                try:
                    await locator.click(timeout=5000)
                except Exception as e:
                    self.logger.debug(f"Row-scoped click failed (kind={kind}): {e}")
                    continue
                await self._save_debug_screenshot_async(
                    page, f"mfa_picker_after_{kind}"
                )
                self.logger.info(f"MFA Select clicked (kind={kind})")
                if kind == "push":
                    bar = "=" * 60
                    self.logger.info(bar)
                    self.logger.info(
                        "  ACTION REQUIRED: tap the Okta Verify push "
                        "notification on your phone now"
                    )
                    self.logger.info(
                        "  (the 'Waiting for login...' polling below is "
                        "expected — not a hang)"
                    )
                    self.logger.info(bar)
                elif kind == "code":
                    self.logger.info(
                        "ACTION REQUIRED: open Okta Verify on your phone, "
                        "read the 6-digit code, type it into the browser window"
                    )
                await page.wait_for_timeout(2000)
                return True

            self.logger.warning(
                "MFA Select button not clicked — neither row matched. "
                "Manual completion required (see screenshot)."
            )
            await self._save_debug_screenshot_async(page, "mfa_picker_no_match")
            return False
        except Exception as e:
            self.logger.warning(f"MFA select step skipped: {e}")
            return False

    async def _handle_generic_login_async(self, page: Page) -> bool:
        """Handle generic login form as fallback."""
        try:
            # Find any username/email input field
            username_elements = await page.query_selector_all(
                'input[type="text"], input[type="email"], input[name*="user"], input[id*="user"]'
            )

            if username_elements:
                await page.evaluate(
                    '(args) => { args.element.value = args.value; args.element.dispatchEvent(new Event("input", { bubbles: true })); }',
                    {"element": username_elements[0], "value": self.username},
                )
                self.logger.info("Filled generic username field")

            # Find any password field
            password_elements = await page.query_selector_all('input[type="password"]')
            if password_elements:
                await page.evaluate(
                    '(args) => { args.element.value = args.value; args.element.dispatchEvent(new Event("input", { bubbles: true })); }',
                    {"element": password_elements[0], "value": self.password},
                )
                self.logger.info("Filled generic password field")

            # Find and click submit button
            login_buttons = await page.query_selector_all(
                'button:has-text("Log"), button:has-text("Sign"), button[type="submit"], input[type="submit"]'
            )

            if login_buttons:
                await login_buttons[0].click()
                self.logger.info("Generic login button clicked")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Generic login failed: {e}")
            return False

    async def _handle_duo_authentication_async(self, page: Page) -> bool:
        """Handle Duo 2FA using proven working patterns."""
        try:
            # Quick check for Duo auth elements
            duo_elements = await page.query_selector_all(".authenticator-verify-list")

            if not duo_elements:
                try:
                    await page.wait_for_selector(
                        ".authenticator-verify-list", timeout=3000
                    )
                except TimeoutError:
                    return True  # No 2FA required

            self.logger.info("Duo 2FA detected, handling...")

            # Try push notification first (proven working pattern)
            push_buttons = await page.query_selector_all(
                'xpath=//h3[contains(text(), "Get a push notification")]/../..//a[contains(@class, "button")]'
            )

            if push_buttons:
                await push_buttons[0].click()
                self.logger.info("Push notification requested - check your device")

                # Send notification to user - USER INTERVENTION REQUIRED
                await self.notify_user_async(
                    "2fa_required",
                    timeout=60,
                    method="Duo Push Notification",
                    device="Registered mobile device",
                    action="Tap 'Approve' on your device",
                )

            else:
                # Fallback to any auth method
                auth_buttons = await page.query_selector_all(
                    ".authenticator-button a.button"
                )
                if auth_buttons:
                    await auth_buttons[0].click()
                    self.logger.info("Alternative authentication method selected")

                    # Send notification for alternative auth - USER INTERVENTION REQUIRED
                    await self.notify_user_async(
                        "2fa_required",
                        timeout=60,
                        method="Alternative 2FA method",
                        device="Follow instructions on screen",
                        action="Complete authentication on your device",
                    )

            return True

        except Exception as e:
            self.logger.error(f"Duo authentication handling failed: {e}")
            return False

    async def _wait_for_completion_async(self, page: Page) -> bool:
        """Wait for login completion using proven success detection."""
        try:
            self.logger.info("Waiting for login completion...")

            for ii in range(60):
                await page.wait_for_timeout(1000)

                try:
                    # Check if moved away from SSO
                    if not self.is_sso_page(page.url):
                        self.logger.info("Login successful - redirected away from SSO")
                        return True

                    # Check for success indicators only if context is still valid
                    success_elements = await page.query_selector_all(
                        'input[name="prompt"], .chat-interface, .dashboard, .main-content'
                    )
                    if success_elements:
                        self.logger.info("Login successful - found success elements")
                        return True

                except Exception as context_error:
                    # Context destroyed likely means navigation happened (success)
                    if "Execution context was destroyed" in str(context_error):
                        await page.wait_for_timeout(2000)
                        if not self.is_sso_page(page.url):
                            self.logger.info(
                                "Login successful - context destroyed due to navigation"
                            )
                            return True

                if ii > 0 and ii % 10 == 0:
                    self.logger.info(f"Still waiting... ({60 - ii}s remaining)")

            return False

        except Exception as e:
            self.logger.error(f"Error waiting for completion: {e}")
            return False

    async def _take_debug_screenshot_async(self, page: Page):
        """Take debug screenshot."""
        try:
            import time
            from pathlib import Path

            screenshot_path = (
                Path.home()
                / ".scitex"
                / "scholar"
                / f"unimelb_debug_{int(time.time())}.png"
            )
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(screenshot_path))
            self.logger.debug(f"Debug screenshot: {screenshot_path}")
        except Exception as e:
            self.logger.debug(f"Screenshot failed: {e}")


if __name__ == "__main__":
    import asyncio

    def main():
        """Test UniMelb SSO automator."""
        from playwright.async_api import async_playwright

        async def test_automator():
            automator = UniversityOfMelbourneSSOAutomator()

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()

                try:
                    await page.goto("https://sso.unimelb.edu.au/")
                    success = await automator.perform_login_async(page)
                    print(f"Login success: {success}")

                    await page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"Error: {e}")
                finally:
                    await browser.close()

        asyncio.run(test_automator())

    main()


# python -m scitex_scholar.auth.sso_automation._UniversityOfMelbourneSSOAutomator

# EOF
