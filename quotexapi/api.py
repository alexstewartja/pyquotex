"""Module for Quotex websocket."""
import json
import logging
import os
import platform
import ssl
import sys
import threading
import time
import uuid
from collections import defaultdict
from random import randint
from typing import Optional

import certifi
import requests
import urllib3
from setuptools.command.alias import alias
from typing_extensions import deprecated

from . import expiration
from . import global_value
from .expiration import get_expiration_time_quotex
from .http.login import Login
from .http.logout import Logout
from .http.navigator import Browser
from .http.settings import Settings
from .ws.channels.buy import Buy
from .ws.channels.candles import GetCandles
from .ws.channels.sell_option import SellOption
from .ws.channels.ssid import Ssid
from .ws.client import WebsocketClient
from .ws.objects.candles import Candles
from .ws.objects.listinfodata import ListInfoData
from .ws.objects.profile import Profile
from .ws.objects.timesync import TimeSync

urllib3.disable_warnings()
logger = logging.getLogger(__name__)

# cert_path = certifi.where()
cert_path = os.path.join("../", "quotex.pem")
os.environ["SSL_CERT_FILE"] = cert_path
os.environ["WEBSOCKET_CLIENT_CA_BUNDLE"] = cert_path
cacert = os.environ.get("WEBSOCKET_CLIENT_CA_BUNDLE")

# Configuração do contexto SSL para usar TLS 1.3
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
# Desativar versões TLS mais antigas
ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3  # Garantir o uso de TLS 1.3

ssl_context.load_verify_locations(certifi.where())


def nested_dict(n, type):
    """

    :param n:
    :param type:

    """
    if n == 1:
        return defaultdict(type)
    else:
        return defaultdict(lambda: nested_dict(n - 1, type))


class QuotexAPI(object):
    """Class for communication with Quotex API."""

    socket_option_opened = {}
    buy_id = None
    orders = {}
    trace_ws = False
    buy_expiration = None
    current_asset = None
    current_period = None
    buy_successful = None
    account_balance = None
    account_type = None
    instruments = None
    training_balance_edit_request = None
    profit_in_operation = None
    sold_options_respond = None
    sold_digital_options_respond = None
    listinfodata = ListInfoData()
    timesync = TimeSync()
    candles = Candles()
    profile = Profile()

    def __init__(
        self,
        host,
        username,
        password,
        lang,
        email_pass=None,
        imap_username=None,
        imap_server_host=None,
        imap_server_port=None,
        proxies=None,
        resource_path=None,
        user_data_dir=".",
    ):
        """
        :param str host: The hostname or ip address of a Quotex server.
        :param str username: The username of a Quotex server.
        :param str password: The password of a Quotex server.
        :param str lang: The lang of a Quotex platform.
        :param str email_pass: The password of a Email.
        :param str imap_username:
        :param str imap_server_host:
        :param int imap_server_port:
        :param proxies: The proxies of a Quotex server.
        :param str|Path resource_path:
        :param user_data_dir: The path browser user data dir.
        """
        self.host = host
        self.https_url = f"https://{host}"
        self.wss_url = f"wss://ws2.{host}/socket.io/?EIO=3&transport=websocket"
        self.wss_message = None
        self.websocket_thread = None
        self.websocket_client = None
        self.set_ssid = None
        self.object_id = None
        self.token_login2fa = None
        self.is_logged = False
        self._temp_status = ""
        self.username = username
        self.password = password
        self.email_pass = email_pass
        self.imap_username = imap_username
        self.imap_server_host = imap_server_host
        self.imap_server_port = imap_server_port
        self.resource_path = resource_path
        self.user_data_dir = user_data_dir
        self.proxies = proxies
        self.lang = lang
        self.timezone_offset = 0000
        self.settings_list = {}
        self.signal_data = {}
        self.get_candle_data = {}
        self.candle_v2_data = {}
        self.realtime_price = {}
        self.realtime_sentiment = {}
        self.session_data = {}
        self.browser = Browser()
        self.browser.set_headers()

    @property
    def websocket(self):
        """Property to get websocket.


        :returns: The instance of :class:`WebSocket <websocket.WebSocket>`.

        """
        return self.websocket_client.wss

    def tick(self):
        """ """
        self.send_wss_payload("tick")

    def subscribe_realtime_candle(self, asset, period: int = 60):
        """

        :param asset:
        :param period: int:  (Default value = 60)

        """
        self.realtime_price[asset] = []
        return self.send_wss_payload(
            "instruments/update", {"asset": asset, "period": period}
        )

    def follow_asset(self, asset):
        """

        :param asset:

        """
        return self.send_wss_payload("instruments/follow", asset)

    def follow_candle(self, asset):
        """

        :param asset:

        """
        return self.send_wss_payload("depth/follow", asset)

    def unfollow_candle(self, asset):
        """

        :param asset:

        """
        return self.send_wss_payload("depth/unfollow", asset)

    def unsubscribe_realtime_candle(self, asset):
        """

        :param asset:

        """
        return self.send_wss_payload("subfor", asset)

    def get_chart_notifications(self, asset, version: str = "1.0.0"):
        """

        :param asset:
        :param version: str:  (Default value = "1.0.0")

        """
        self.send_wss_payload(
            "chart_notification/get", {"asset": asset, "version": version}
        )

    def switch_to_asset(self, asset: str, duration: int = 60):
        """

        :param asset: str:
        :param duration: int:  (Default value = 60)

        """
        exp_time = (
            get_expiration_time_quotex(int(self.timesync.server_timestamp), duration)
            if "_otc" not in asset
            else duration
        )
        payload = {
            "chartId": "graph",
            "settings": {
                "chartId": "graph",
                "chartType": 2,
                "currentExpirationTime": exp_time,
                "isFastOption": False,
                "isFastAmountOption": False,
                "isIndicatorsMinimized": False,
                "isIndicatorsShowing": True,
                "isShortBetElement": False,
                "chartPeriod": 4,
                "currentAsset": {"symbol": asset},
                "dealValue": 1,
                "dealPercentValue": 1,
                "isVisible": True,
                "timePeriod": duration,
                "gridOpacity": 8,
                "isAutoScrolling": 1,
                "isOneClickTrade": True,
                "upColor": "#0FAF59",
                "downColor": "#FF6251",
            },
        }

        self.send_wss_payload("settings/store", payload)

    @deprecated("Use `refill_demo_balance(...)` instead")
    def edit_training_balance(self, amount):
        """

        :param amount:

        """
        self.refill_demo_balance(amount)

    def refill_demo_balance(self, amount):
        """

        :param amount:

        """
        self.send_wss_payload("demo/refill", amount)

    def signals_subscribe(self):
        """ """
        self.send_wss_payload("signal/subscribe")

    @deprecated("Use `change_account_type(...)` instead")
    def change_account(self, account_type):
        """

        :param account_type:

        """
        self.change_account_type(account_type)

    def change_account_type(self, account_type):
        """

        :param account_type:

        """
        self.account_type = account_type
        self.send_wss_payload(
            "account/change", {"demo": self.account_type, "tournamentId": 0}
        )

    def indicators(self):
        """ """
        # 42["indicator/change",{"id":"Y5zYtYaUtjI6eUz06YlGF","settings":{"lines":{"main":{"lineWidth":1,"color":"#db4635"}},"ma":"SMA","period":10}}]
        # 42["indicator/delete", {"id": "23507dc2-05ca-4aec-9aef-55939735b3e0"}]
        pass

    def simulate_asset_switch(self, asset: str, duration: int = 60, version="1.0.0"):
        """

        :param asset: str:
        :param duration: int:  (Default value = 60)
        :param version:  (Default value = "1.0.0")

        """
        self.tick()
        self.subscribe_realtime_candle(asset, duration)
        self.get_chart_notifications(asset, version)
        self.unfollow_candle(asset)
        self.follow_candle(asset)
        self.switch_to_asset(asset, duration)

    @property
    def logout(self):
        """Property for get Quotex http login resource.


        :returns: The instance of :class:`Login
            <quotexapi.http.login.Login>`.

        """
        return Logout(self)

    @property
    def login(self):
        """Property for get Quotex http login resource.


        :returns: The instance of :class:`Login
            <quotexapi.http.login.Login>`.

        """
        return Login(self)

    @property
    def ssid(self):
        """Property for get Quotex websocket ssid channel.


        :returns: The instance of :class:`Ssid
            <Quotex.ws.channels.ssid.Ssid>`.

        """
        return Ssid(self)

    @property
    def buy(self):
        """Property for get Quotex websocket ssid channel.


        :returns: The instance of :class:`Buy
            <Quotex.ws.channels.buy.Buy>`.

        """
        return Buy(self)

    @property
    def sell_option(self):
        """ """
        return SellOption(self)

    @property
    def get_candles(self):
        """Property for get Quotex websocket candles channel.


        :returns: The instance of :class:`GetCandles
            <quotexapi.ws.channels.candles.GetCandles>`.

        """
        return GetCandles(self)

    def send_http_request_v1(
        self, resource, method, data=None, params=None, headers=None
    ):
        """Send http request to Quotex server.

        :param resource: The instance of
        :class:`Resource <quotexapi.http.resource.Resource>`.
        :param str: method: The http request method.
        :param dict: data: (optional) The http request data.
        :param dict: params: (optional) The http request params.
        :param dict: headers: (optional) The http request headers.
        :param method:
        :param data:  (Default value = None)
        :param params:  (Default value = None)
        :param headers:  (Default value = None)
        :returns: The instance of :class:`Response <requests.Response>`.

        """
        url = resource.url
        logger.debug(url)
        cookies = self.session_data.get("cookies")
        user_agent = self.session_data.get("user_agent")
        if cookies:
            self.browser.headers["Cookie"] = cookies
        if user_agent:
            self.browser.headers["User-Agent"] = user_agent
        self.browser.headers["Connection"] = "keep-alive"
        self.browser.headers["Accept-Encoding"] = "gzip, deflate, br"
        self.browser.headers["Accept-Language"] = "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3"
        self.browser.headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        )
        self.browser.headers["Referer"] = headers.get("referer")
        self.browser.headers["Upgrade-Insecure-Requests"] = "1"
        self.browser.headers["Sec-Ch-Ua"] = (
            '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        )
        self.browser.headers["Sec-Ch-Ua-Mobile"] = "?0"
        self.browser.headers["Sec-Ch-Ua-Platform"] = '"Linux"'
        self.browser.headers["Sec-Fetch-Site"] = "same-origin"
        self.browser.headers["Sec-Fetch-User"] = "?1"
        self.browser.headers["Sec-Fetch-Dest"] = "document"
        self.browser.headers["Sec-Fetch-Mode"] = "navigate"
        self.browser.headers["Dnt"] = "1"
        response = self.browser.send_request(
            method=method, url=url, data=data, params=params
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return None
        return response

    def get_profile(self, force=True) -> Profile:
        """

        :param force:  (Default value = True)

        """
        if not self.profile.profile_id or force:
            profile_data = Settings(self).get_settings().get("data")
            self.profile.nick_name = profile_data["nickname"]
            self.profile.profile_id = profile_data["id"]
            self.profile.demo_balance = profile_data["demoBalance"]
            self.profile.live_balance = profile_data["liveBalance"]
            self.profile.avatar = profile_data["avatar"]
            self.profile.country = profile_data["country"]
            self.profile.country_name = profile_data["countryName"]
            self.profile.country_ip = profile_data["countryIp"]
            self.profile.lang = profile_data["lang"]
            self.profile.time_offset = profile_data["timeOffset"]
            self.timezone_offset = profile_data["timeOffset"]
            self.profile.minimum_amount = profile_data["minDealAmount"]
            self.profile.currency_code = profile_data["currencyCode"]
            self.profile.currency_symbol = profile_data["currencySymbol"]
            self.profile.profile_level = profile_data["profileLevel"]
        return self.profile

    def send_websocket_request(self, data, no_force_send=True):
        """Send websocket request to Quotex server.

        :param str: data: The websocket request data.
        :param bool: no_force_send: Default True.
        :param data:
        :param no_force_send:  (Default value = True)

        """
        while (
            global_value.ssl_Mutual_exclusion or global_value.ssl_Mutual_exclusion_write
        ) and no_force_send:
            pass
        global_value.ssl_Mutual_exclusion_write = True
        self.websocket.send(data)
        logger.debug(data)
        global_value.ssl_Mutual_exclusion_write = False

    def send_wss_payload(
        self, action: str, payload: Optional[str | dict] = None, no_force_send=True
    ):
        """Convenience method to send a payload over websocket to Quotex server.

        :param str: action: wss action being performed, ex. "tick"
        :param Any: payload: json/dict payload to send with specified action
        :param bool: no_force_send: Specify whether to wait for write lock
        :param action: str:
        :param payload: Optional[str | dict]:  (Default value = None)
        :param no_force_send:  (Default value = True)

        """
        data = f'42["{action}"%payload%]'

        if payload is not None:
            if not isinstance(payload, str):
                payload = json.dumps(payload)
            data.replace("%payload%", f",{payload}")
        else:
            data.replace("%payload%", "")

        return self.send_websocket_request(data, no_force_send)

    @deprecated("Use `authenticate(...)` instead")
    async def autenticate(self):
        await self.authenticate()

    async def authenticate(self):
        print("Authenticating user...")
        logger.info("Authenticating user...")
        status, message = await self.login(
            self.username,
            self.password,
            self.email_pass,
            self.imap_username,
            self.imap_server_host,
            self.imap_server_port,
            self.user_data_dir,
        )
        print(message)
        if not status:
            print("Authentication failed. Exiting...")
            logger.info("Authentication failed. Exiting...")
            sys.exit(1)
        global_value.SSID = self.session_data.get("token")
        self.is_logged = True

    async def start_websocket(self):
        global_value.check_websocket_if_connect = None
        global_value.check_websocket_if_error = False
        global_value.websocket_error_reason = None
        if not global_value.SSID:
            await self.authenticate()
        self.websocket_client = WebsocketClient(self)
        payload = {
            "ping_interval": 24,
            "ping_timeout": 20,
            "ping_payload": "2",
            "origin": self.https_url,
            "host": f"ws2.{self.host}",
            "sslopt": {
                "check_hostname": False,
                "cert_reqs": ssl.CERT_NONE,
                "ca_certs": cacert,
                "context": ssl_context,
            },
        }
        payload["sslopt"]["ssl_version"] = ssl.PROTOCOL_TLSv1_2
        self.websocket_thread = threading.Thread(
            target=self.websocket.run_forever, kwargs=payload
        )
        self.websocket_thread.daemon = True
        self.websocket_thread.start()
        while True:
            if global_value.check_websocket_if_error:
                return False, global_value.websocket_error_reason
            elif global_value.check_websocket_if_connect == 0:
                logger.debug("Websocket connection failed.")
                return False, "Websocket connection failed."
            elif global_value.check_websocket_if_connect == 1:
                logger.debug("Websocket connection successful!")
                return True, "Websocket connection successful!"
            elif global_value.check_rejected_connection == 1:
                global_value.SSID = None
                logger.debug("Websocket token rejected.")
                return True, "Websocket token rejected."

    def send_ssid(self, timeout=10):
        """

        :param timeout:  (Default value = 10)

        """
        self.wss_message = None
        if not global_value.SSID:
            return False
        self.ssid(global_value.SSID)
        start_time = time.time()
        while self.wss_message is None:
            if time.time() - start_time > timeout:
                return False
            time.sleep(0.5)
        return True

    async def connect(self, is_demo):
        """Method for connection to Quotex API."""
        self.account_type = is_demo
        global_value.ssl_Mutual_exclusion = False
        global_value.ssl_Mutual_exclusion_write = False
        if global_value.check_websocket_if_connect:
            logger.info("Closing websocket connection...")
            self.close()
        check_websocket, websocket_reason = await self.start_websocket()
        if not check_websocket:
            return check_websocket, websocket_reason
        check_ssid = self.send_ssid()
        if not check_ssid:
            await self.authenticate()
            if self.is_logged:
                self.send_ssid()
        return check_websocket, websocket_reason

    async def reconnect(self):
        """Method for connection to Quotex API."""
        logger.info("Reconnecting websocket...")
        await self.start_websocket()

    def close(self):
        """ """
        if self.websocket_client:
            self.websocket.close()
            self.websocket_thread.join()
        return True

    def websocket_alive(self):
        """ """
        return self.websocket_thread.is_alive()

    def generate_request_id(self):
        """ """
        def generate_pseudo_random_id():
            """ """
            return expiration.get_timestamp() + randint(1, 100)

        request_id = generate_pseudo_random_id()
        while request_id in self.orders:
            request_id = generate_pseudo_random_id()
        return request_id

    def get_order_by_id(self, order_id=None, request_id=None) -> Optional[dict]:
        """

        :param order_id:  (Default value = None)
        :param request_id:  (Default value = None)

        """
        if order_id is not None:
            for request_id, order in self.orders:
                if "id" in order and order["id"] == order_id:
                    return order
        elif request_id is not None:
            return self.orders[request_id] if request_id in self.orders else None

        return None

    def get_request_id_from_order_id(self, order_id) -> Optional[str]:
        """

        :param order_id:

        """
        order = self.get_order_by_id(order_id=order_id)

        if order is not None:
            return order["request"]["requestId"]

        return None
