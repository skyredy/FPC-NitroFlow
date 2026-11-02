import hashlib
import re
from urllib.parse import urlsplit
from .errors import ProviderError

def normalize(value):
    if not isinstance(value, str) or len(value) > 300 or value != value.strip():
        raise ProviderError("INVALID_GIFT_LINK")
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.username or url.password or url.port or url.query or url.fragment:
            raise ValueError()
        if url.netloc == "discord.gift":
            code = url.path.removeprefix("/")
        elif url.netloc == "discord.com" and url.path.startswith("/gifts/"):
            code = url.path[len("/gifts/"):]
        else:
            raise ValueError()
        if not re.fullmatch(r"[A-Za-z0-9]{16,64}", code):
            raise ValueError()
    except ValueError:
        raise ProviderError("INVALID_GIFT_LINK") from None
    return "https://discord.gift/" + code

def extract(item):
    values = []
    login = item.get("loginData")
    if isinstance(login, dict) and login.get("raw"):
        values.append(normalize(login["raw"]))
    if item.get("accountLink"):
        values.append(normalize(item["accountLink"]))
    if not values or len(set(values)) != 1:
        raise ProviderError("AMBIGUOUS_GIFT_DATA")
    return values[0]

def fingerprint(link):
    return hashlib.sha256(normalize(link).encode()).hexdigest()
