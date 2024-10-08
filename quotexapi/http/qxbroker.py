import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from random import randint

import requests
from bs4 import BeautifulSoup
from seleniumbase import BaseCase
from seleniumbase import SB

from ..http.automail import get_pin


def fill_form(sb: SB, email, password):
    email_selector = 'form.auth__form input[name="email"]'
    password_selector = 'form.auth__form input[name="password"]'
    sign_in_button_selector = 'form.auth__form .auth__submit button[type="submit"]'

    sb.wait_for_element(email_selector)
    sb.focus(email_selector)
    sb.uc_gui_write(email)
    sb.wait(1)
    sb.wait_for_element(password_selector)
    sb.focus(password_selector)
    sb.uc_gui_write(password)
    sb.wait(1)
    sb.wait_for_element(sign_in_button_selector)
    sb.uc_click(sign_in_button_selector)
    pass


def fill_code_form(sb, code):
    """

    :param sb:
    :param code:

    """
    pin_code_selector = 'form.auth__form input[name="code"]'
    submit_button_selector = 'form.auth__form .auth__submit button[type="submit"]'

    sb.wait_for_element(pin_code_selector)
    sb.focus(pin_code_selector)
    sb.uc_gui_write(code)
    sb.wait(1)
    sb.wait_for_element(submit_button_selector)
    sb.uc_click(submit_button_selector)
    pass


class Browser(object):
    """ """
    user_data_dir = None
    base_url = "qxbroker.com"
    https_base_url = f"https://{base_url}"
    email = None
    password = None
    email_pass = None
    imap_username = (None, )
    imap_server_host = (None, )
    imap_server_port = None

    def __init__(self, api):
        self.api = api
        self.html = None

    async def run(self, sb: BaseCase) -> None:
        sb.uc_open_with_reconnect(f"{self.https_base_url}/{self.api.lang}")
        sb.wait_for_ready_state_complete()
        sb.uc_gui_handle_captcha()

        demo_acc_href = f"{self.https_base_url}/{self.api.lang}/sign-up/fast/"
        demo_acc_button_selector = f'#top .header__list--item a[href="{demo_acc_href}"]'
        sb.wait_for_element(demo_acc_button_selector)
        sb.uc_click(demo_acc_button_selector)
        sb.wait_for_ready_state_complete()
        sb.uc_gui_handle_captcha()

        deposit_btn_selector = (
            ".header__sidebar .button.button--success.header__sidebar-button.deposit"
        )
        sb.wait_for_element(deposit_btn_selector, timeout=30)
        sb.uc_click(deposit_btn_selector)
        sb.wait_for_ready_state_complete()
        sb.uc_gui_handle_captcha()

        sign_up_url = f"{self.https_base_url}/{self.api.lang}/sign-up/modal"
        if sb.get_current_url() == sign_up_url:
            sign_in_url = f"{self.https_base_url}/{self.api.lang}/sign-in/modal/"
            sign_in_tab_selector = f'a.tabs__tab[href="{sign_in_url}"]'
            sb.wait_for_element(sign_in_tab_selector)
            sb.uc_click(sign_in_tab_selector)
            sb.wait_for_ready_state_complete()

            if sb.get_current_url() == sign_in_url:
                fill_form(sb, self.email, self.password)
                check_codes_since = datetime.now()
                sb.wait_for_ready_state_complete()
                soup = sb.get_beautiful_soup()
                required_keep_code = soup.find("input", {"name": "keep_code"})
                if required_keep_code:
                    auth_body = soup.find("main", {"class": "auth__body"})
                    input_message = (
                        f'{auth_body.find("p").text}: '
                        if auth_body.find("p") else
                        f"Enter the authentication PIN that was sent to: {self.email}"
                    )
                    pin_code = None
                    if self.email_pass:
                        pin_code = await get_pin(
                            self.email,
                            self.email_pass,
                            self.imap_username,
                            self.imap_server_host,
                            self.imap_server_port,
                            sent_since=check_codes_since
                        )
                    code = pin_code or input(input_message)
                    fill_code_form(sb, code)
                    sb.wait_for_ready_state_complete()

            cookies = sb.get_cookies()
            print(f"Cookies: {cookies}")
            self.html = sb.get_beautiful_soup()
            user_agent = sb.get_user_agent()
            self.api.session_data["user_agent"] = user_agent
            script = self.html.find_all("script", {"type": "text/javascript"})
            status, message = self.success_login()
            if not status:
                return
            settings = script[1].get_text().strip().replace(";", "")
            print(f"Settings: {settings}")
            match = re.sub("window.settings = ", "", settings)
            print(f"Match: {match}")
            token = json.loads(match).get("token")
            self.api.session_data["token"] = token
            output_file = Path(os.path.join(self.api.resource_path,
                                            "session.json"))
            output_file.parent.mkdir(exist_ok=True, parents=True)
            cookiejar = requests.utils.cookiejar_from_dict(
                {c["name"]: c["value"]
                 for c in cookies})
            cookies_string = "; ".join([f"{c.name}={c.value}" for c in cookiejar])
            self.api.session_data["cookies"] = cookies_string
            output_file.write_text(
                json.dumps(
                    {
                        "cookies": cookies_string,
                        "token": token,
                        "user_agent": user_agent,
                        "headers": sb.get_user_agent()
                    },
                    indent=4,
                ))
            print(f'Session data written to: {os.path.join(self.api.resource_path, "session.json")}')
        else:
            input('Press any key...')
            self.html = sb.get_beautiful_soup()

    def success_login(self):
        """ """
        match = self.html.find("div",
                               {"class": "hint -danger"}) or self.html.find(
                                   "div", {"class": "hint hint--danger"})
        if match is None:
            return True, "Login successful."

        return False, f"Login failed. {match.text.strip()}"

    async def main(self) -> None:
        with SB(uc=True,
                      user_data_dir=self.user_data_dir,
                      test=True,
                      headless=False) as sb:
            await self.run(sb)

    async def get_cookies_and_ssid(self):
        await self.main()
        return self.success_login()
