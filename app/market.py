import threading
import time
import requests
from .errors import ProviderError

class Market:
    base = "https://api.lzt.market"

    def __init__(self, token, session=None, search_interval=3.1):
        if not token:
            raise ValueError("MissingMarketToken")
        self.session = session or requests.Session()
        self.headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        self.search_interval, self.last_search = search_interval, 0
        self.search_lock = threading.Lock()
        self.profile_id = None

    def request(self, method, path, params=None, payload=None):
        if not path.startswith("/") or path.startswith("//") or "?" in path:
            raise ValueError("InvalidProviderPath")
        try:
            response = self.session.request(method, self.base + path, params=dict(params or {}, i18n="en"),
                                            json=payload, headers=self.headers, timeout=(10, 310), allow_redirects=False)
        except requests.RequestException:
            raise ProviderError("NETWORK_UNKNOWN") from None
        try:
            data = response.json()
        except ValueError:
            raise ProviderError("INVALID_RESPONSE", response.status_code) from None
        if not isinstance(data, dict):
            raise ProviderError("INVALID_RESPONSE", response.status_code)
        if response.status_code != 200 or data.get("errors"):
            errors = data.get("errors")
            code = "RETRY_REQUEST" if isinstance(errors, list) and errors == ["retry_request"] else "PROVIDER_HTTP_ERROR"
            if response.status_code == 429:
                code = "RATE_LIMIT"
            if response.status_code == 401:
                code = "INVALID_MARKET_TOKEN"
            raise ProviderError(code, response.status_code)
        return data

    def profile(self):
        user = self.request("GET", "/me").get("user")
        if not isinstance(user, dict) or type(user.get("user_id")) is not int or user["user_id"] <= 0:
            raise ProviderError("INVALID_PROFILE")
        if str(user.get("currency", "")).lower() != "rub":
            raise ProviderError("RUB_ACCOUNT_REQUIRED")
        self.profile_id = user["user_id"]
        return user

    def search(self, product, seller, after=None):
        with self.search_lock:
            delay = self.search_interval - (time.monotonic() - self.last_search)
            if delay > 0:
                time.sleep(delay)
            self.last_search = time.monotonic()
            params = dict(subscription=product.subscription, subscription_length=product.length,
                          subscription_period=product.period, currency="rub", pmax=str(product.max_unit_cost),
                          order_by="price_to_up", user_id=seller)
            if after:
                params["after"] = after
            data = self.request("GET", "/gifts", params=params)
        if not isinstance(data.get("items"), list):
            raise ProviderError("INVALID_CATALOG")
        return data

    def item(self, item_id):
        if type(item_id) is not int or item_id <= 0:
            raise ValueError("InvalidItemId")
        data = self.request("GET", f"/{item_id}")
        if not isinstance(data.get("item"), dict):
            raise ProviderError("INVALID_ITEM")
        return data

    def buy(self, item_id, price):
        if type(item_id) is not int or item_id <= 0:
            raise ValueError("InvalidItemId")
        return self.request("POST", f"/{item_id}/fast-buy", payload={"price": float(price)})
