from types import SimpleNamespace

from app.services.data_service.providers.tushare_provider import TushareProvider


class _FakeFrame:
    def __init__(self, rows):
        self._rows = rows
        self.empty = len(rows) == 0

    def to_dict(self, orient: str):
        assert orient == "records"
        return self._rows


class _FakePro:
    def income(self, **kwargs):
        return _FakeFrame(
            [
                {"end_date": "20241231", "total_revenue": "1000", "n_income_attr_p": "200"},
                {"end_date": "20250930", "total_revenue": "1200", "n_income_attr_p": "260"},
            ]
        )

    def fina_indicator(self, **kwargs):
        return _FakeFrame(
            [
                {"end_date": "20241231", "roe": "10.2"},
                {"end_date": "20250930", "roe": "11.5", "debt_to_assets": "42.0"},
            ]
        )


class _FakeTushareModule:
    def __init__(self):
        self.token = None

    def set_token(self, token: str):
        self.token = token

    def pro_api(self):
        return _FakePro()


def test_tushare_provider_returns_latest_raw_payload(monkeypatch) -> None:
    fake_module = _FakeTushareModule()
    monkeypatch.setattr(
        "app.services.data_service.providers.tushare_provider.importlib.util.find_spec",
        lambda name: SimpleNamespace(name=name),
    )
    monkeypatch.setattr(
        "app.services.data_service.providers.tushare_provider._get_tushare_module",
        lambda: fake_module,
    )

    provider = TushareProvider(token="demo-token")
    payload = provider.get_stock_financial_summary_raw("600519.SH")

    assert payload is not None
    assert fake_module.token == "demo-token"
    assert payload["source"] == "tushare"
    assert payload["income"]["end_date"] == "20250930"
    assert payload["fina_indicator"]["roe"] == "11.5"
