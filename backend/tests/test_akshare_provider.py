"""AKShare provider 重试逻辑测试。"""

from app.services.data_service.exceptions import ProviderError
from app.services.data_service.providers.akshare_provider import (
    AkshareProvider,
    _is_transient_akshare_error,
)


class _TransientFailThenSuccessAk:
    def __init__(self) -> None:
        self.calls = 0

    def stock_zh_a_hist(self, **kwargs):
        self.calls += 1
        if self.calls < 3:
            raise ConnectionError("Connection aborted by peer")
        return {"ok": True}


class _NonTransientFailAk:
    def __init__(self) -> None:
        self.calls = 0

    def stock_zh_a_hist(self, **kwargs):
        self.calls += 1
        raise ValueError("bad request parameter")


def test_akshare_provider_retries_transient_daily_error() -> None:
    """网络抖动错误应触发重试。"""
    provider = AkshareProvider(
        daily_bars_max_retries=4,
        daily_bars_retry_backoff_seconds=0.0,
        daily_bars_retry_jitter_seconds=0.0,
    )
    fake_ak = _TransientFailThenSuccessAk()

    frame = provider._load_daily_frame_with_retry(
        ak=fake_ak,
        ak_symbol="000001",
        start_date=None,
        end_date=None,
    )

    assert frame == {"ok": True}
    assert fake_ak.calls == 3


def test_akshare_provider_stops_on_non_transient_error() -> None:
    """非网络错误不应无意义重试。"""
    provider = AkshareProvider(
        daily_bars_max_retries=4,
        daily_bars_retry_backoff_seconds=0.0,
        daily_bars_retry_jitter_seconds=0.0,
    )
    fake_ak = _NonTransientFailAk()

    try:
        provider._load_daily_frame_with_retry(
            ak=fake_ak,
            ak_symbol="000001",
            start_date=None,
            end_date=None,
        )
    except ProviderError as exc:
        assert "after 1 attempts" in str(exc)
    else:
        raise AssertionError("Expected ProviderError was not raised.")

    assert fake_ak.calls == 1


def test_is_transient_akshare_error() -> None:
    """应正确识别可重试网络错误。"""
    assert _is_transient_akshare_error(ConnectionError("RemoteDisconnected")) is True
    assert _is_transient_akshare_error(ValueError("bad request")) is False
