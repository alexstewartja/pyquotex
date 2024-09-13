import json
from quotexapi.ws.channels.base import Base
from quotexapi.expiration import get_expiration_time_quotex


class Buy(Base):
    """Class for Quotex buy websocket channel."""

    name = "buy"

    def __call__(self, price, asset, direction, duration, request_id, tournament_id=0):
        _duration = duration
        option_type = 100
        if "_otc" not in asset:
            option_type = 1
            duration = get_expiration_time_quotex(
                int(self.api.timesync.server_timestamp),
                _duration
            )

        self.api.simulate_asset_switch(asset, _duration)

        payload = {
            "asset": asset,
            "amount": price,
            "time": duration,
            "action": direction,
            "isDemo": (0 if tournament_id > 0 else self.api.account_type),
            "tournamentId": tournament_id,
            "requestId": request_id,
            "optionType": option_type
        }

        self.api.tick()
        wss_action = 'orders/tournament/open' if tournament_id > 0 else 'orders/open'
        self.send_wss_payload(wss_action, payload)
        self.api.orders[request_id]['request'] = payload
