"""BaoStock provider 的容错测试。"""

from app.services.data_service.providers.baostock_provider import _result_to_rows


class StubBaoResult:
    """测试用 BaoStock 结果对象。"""

    def __init__(self, fields):
        self.error_code = "0"
        self.fields = fields

    def next(self) -> bool:
        return False

    def get_row_data(self):
        return None


def test_result_to_rows_handles_none_fields_gracefully() -> None:
    """当 BaoStock 返回 fields=None 时，不应抛出 NoneType 错误。"""
    rows = _result_to_rows(StubBaoResult(fields=None))

    assert rows == []
