"""选股器过滤规则。"""

from app.schemas.market_data import DailyBarResponse


def is_special_treatment_name(name: str) -> bool:
    """判断名称是否包含 ST 或 *ST。"""
    normalized_name = name.upper().replace(" ", "")
    return "ST" in normalized_name


def is_common_a_share_symbol(symbol: str) -> bool:
    """判断是否为常见 A 股代码格式。"""
    if not symbol.endswith((".SH", ".SZ")):
        return False
    code = symbol.split(".")[0]
    if len(code) != 6 or not code.isdigit():
        return False
    return code.startswith(("0", "1", "2", "3", "5", "6", "9"))


def has_sufficient_daily_bars(
    daily_bars: DailyBarResponse,
    min_count: int = 30,
) -> bool:
    """判断日线数据是否足够。"""
    return daily_bars.count >= min_count and len(daily_bars.bars) >= min_count


def has_acceptable_liquidity(
    daily_bars: DailyBarResponse,
    min_average_amount: float = 20_000_000.0,
) -> bool:
    """判断近期流动性是否过低。"""
    if not daily_bars.bars:
        return False

    recent_bars = daily_bars.bars[-5:]
    amounts = [bar.amount for bar in recent_bars if bar.amount is not None and bar.amount > 0]
    if len(amounts) >= 3:
        return sum(amounts) / len(amounts) >= min_average_amount

    estimated_amounts = []
    for bar in recent_bars:
        if bar.close is None or bar.volume is None:
            continue
        estimated_amount = float(bar.close) * float(bar.volume)
        if estimated_amount > 0:
            estimated_amounts.append(estimated_amount)
    if not estimated_amounts:
        return False
    return sum(estimated_amounts) / len(estimated_amounts) >= min_average_amount


def has_abnormal_price_data(daily_bars: DailyBarResponse) -> bool:
    """判断是否存在明显异常价格数据。"""
    if not daily_bars.bars:
        return True

    latest_bar = daily_bars.bars[-1]
    if latest_bar.close is None or latest_bar.close <= 0:
        return True
    if latest_bar.high is None or latest_bar.low is None:
        return True
    if latest_bar.high < latest_bar.low:
        return True
    if latest_bar.open is not None and latest_bar.open <= 0:
        return True
    if latest_bar.volume is not None and latest_bar.volume < 0:
        return True
    return False
