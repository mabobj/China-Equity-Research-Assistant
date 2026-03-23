"""External data provider package."""

from app.services.data_service.providers.akshare_provider import AkshareProvider
from app.services.data_service.providers.baostock_provider import BaostockProvider

__all__ = ["AkshareProvider", "BaostockProvider"]
