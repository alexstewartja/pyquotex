import json
from quotexapi.ws.channels.base import Base


class Ssid(Base):
    """Class for Quotex API ssid websocket channel."""

    name = "ssid"

    def __call__(self, ssid):
        """Method to send message to ssid websocket channel.

        :param ssid: The session identifier.
        """
        self.send_wss_payload('authorization', {
            "session": ssid,
            "isDemo": self.api.account_type,
            "tournamentId": 0
        })
