import json
from _datetime import datetime

from quotexapi.ws.channels.base import Base
from quotexapi.expiration import get_expiration_time_quotex, timestamp_to_date, get_timestamp


class PendingCreate(Base):
    """Class for Quotex pending trade websocket channel."""

    name = "pending_create"
    action = "pending/create"

    def __call__(self, asset, direction='call', duration=60, trade_amount=1, open_time=None, open_price=None):
        if open_price is not None:
            open_type = 1
        else:
            open_type = 0

        if open_time is None:
            tzo = self.api.get_profile().time_offset
            open_time = timestamp_to_date(
                get_timestamp() + 65).strftime('%Y-%m-%dT%H:%M:%S')

        self.api.simulate_asset_switch(asset, duration)

        payload = {
            "openType": open_type,
            "asset": asset,
            "timeframe": duration,
            "command": direction,
            "amount": trade_amount
        }

        if open_type == 0:
            payload["openTime"] = open_time
        else:
            payload["openPrice"] = open_price

        self.send_wss_payload(self.action, payload)
