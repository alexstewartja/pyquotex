from typing import Optional


class Base(object):
    """Class for base Quotex websocket channel."""

    def __init__(self, api):
        """
        :param api: The instance of :class:`QuotexAPI
            <quotexapi.api.QuotexAPI>`.
        """
        from quotexapi.api import QuotexAPI

        self.api: QuotexAPI = api

    def send_websocket_request(self, data):
        """Send request to Quotex server websocket.

        :param str: data: The websocket channel data.
        :param data:
        :returns: The instance of :class:`requests.Response`.

        """
        return self.api.send_websocket_request(data)

    def send_wss_payload(
        self, action: str, payload: Optional[str | dict] = None, no_force_send=True
    ):
        """

        :param action: str:
        :param payload: Optional[str | dict]:  (Default value = None)
        :param no_force_send:  (Default value = True)

        """
        return self.api.send_wss_payload(action, payload, no_force_send)
