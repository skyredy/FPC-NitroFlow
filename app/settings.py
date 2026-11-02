import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import dotenv_values
from .products import load_products

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    root: Path
    token: str
    api_key: str
    live: bool
    products: dict
    interval: float = 3
    reconcile_seconds: int = 86400
    auto_resume: bool = False

    @property
    def configured(self):
        return bool(self.live and self.token and self.api_key and all(p.verified for p in self.products.values()))

    @classmethod
    def load(cls, root=ROOT):
        root = Path(root).resolve()
        values = dotenv_values(root / ".env")
        def value(key, default=""):
            return os.environ.get(key, values.get(key) or default)
        return cls(root, value("FUNPAY_TOKEN"), value("LZT_TOKEN"),
                   value("ALLOW_PURCHASES", "false").lower() == "true", load_products(root / "products.json"),
                   auto_resume=value("AUTO_RESUME_LOTS", "false").lower() == "true")
