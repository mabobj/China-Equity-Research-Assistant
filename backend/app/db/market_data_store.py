"""本地市场数据仓储。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import duckdb

from app.schemas.market_data import DailyBar, StockProfile, UniverseItem
from app.schemas.research_inputs import AnnouncementItem, FinancialSummary

DATASET_DAILY_BARS = "daily_bars"
DATASET_ANNOUNCEMENTS = "announcements"
DATASET_UNIVERSE = "universe"

_UNKNOWN_REPORT_PERIOD = date(1900, 1, 1)


class LocalMarketDataStore:
    """基于 DuckDB 的本地市场数据存储。"""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_stock_profile(self, symbol: str) -> Optional[StockProfile]:
        """读取本地股票基础信息。"""
        row = self._fetchone(
            """
            SELECT
                i.symbol,
                i.code,
                i.exchange,
                i.name,
                ps.industry,
                i.list_date,
                ps.status,
                ps.total_market_cap,
                ps.circulating_market_cap,
                COALESCE(ps.source, i.source) AS source
            FROM instruments AS i
            LEFT JOIN instrument_profile_snapshots AS ps
              ON i.symbol = ps.symbol
            WHERE i.symbol = ?
            """,
            [symbol],
        )
        if row is None:
            return None

        return StockProfile(
            symbol=row["symbol"],
            code=row["code"],
            exchange=row["exchange"],
            name=row["name"],
            industry=row["industry"],
            list_date=row["list_date"],
            status=row["status"],
            total_market_cap=row["total_market_cap"],
            circulating_market_cap=row["circulating_market_cap"],
            source=row["source"],
        )

    def upsert_stock_profile(self, profile: StockProfile) -> None:
        """写入本地股票基础信息。"""
        self._upsert_instrument(
            symbol=profile.symbol,
            code=profile.code,
            exchange=profile.exchange,
            name=profile.name,
            list_date=profile.list_date,
            source=profile.source,
        )
        self._execute(
            """
            INSERT OR REPLACE INTO instrument_profile_snapshots (
                symbol, industry, status, total_market_cap,
                circulating_market_cap, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                profile.symbol,
                profile.industry,
                profile.status,
                profile.total_market_cap,
                profile.circulating_market_cap,
                profile.source,
                datetime.utcnow(),
            ],
        )

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[DailyBar]:
        """读取本地日线数据。"""
        query = """
            SELECT symbol, trade_date, open, high, low, close, volume, amount, source
            FROM daily_bars
            WHERE symbol = ?
        """
        params: list[object] = [symbol]

        if start_date is not None:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND trade_date <= ?"
            params.append(end_date)

        query += " ORDER BY trade_date"
        rows = self._fetchall(query, params)
        return [
            DailyBar(
                symbol=row["symbol"],
                trade_date=row["trade_date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                amount=row["amount"],
                source=row["source"],
            )
            for row in rows
        ]

    def get_latest_daily_bar_date(self, symbol: str) -> Optional[date]:
        """读取本地最新一根日线日期。"""
        row = self._fetchone(
            """
            SELECT MAX(trade_date) AS latest_trade_date
            FROM daily_bars
            WHERE symbol = ?
            """,
            [symbol],
        )
        if row is None:
            return None
        return row["latest_trade_date"]

    def upsert_daily_bars(self, bars: list[DailyBar]) -> None:
        """写入本地日线数据。"""
        if not bars:
            return

        first_bar = bars[0]
        symbol_parts = first_bar.symbol.split(".")
        self._upsert_instrument(
            symbol=first_bar.symbol,
            code=symbol_parts[0],
            exchange=symbol_parts[1],
            name=first_bar.symbol,
            list_date=None,
            source=first_bar.source,
        )

        self._executemany(
            """
            INSERT OR REPLACE INTO daily_bars (
                symbol, trade_date, open, high, low, close, volume, amount, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [
                    bar.symbol,
                    bar.trade_date,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.volume,
                    bar.amount,
                    bar.source,
                    datetime.utcnow(),
                ]
                for bar in bars
            ],
        )

    def get_stock_universe(self) -> list[UniverseItem]:
        """读取本地股票池。"""
        rows = self._fetchall(
            """
            SELECT
                i.symbol,
                i.code,
                i.exchange,
                i.name,
                um.membership_status AS status,
                um.source
            FROM universe_memberships AS um
            INNER JOIN instruments AS i
              ON um.symbol = i.symbol
            ORDER BY i.symbol
            """,
            [],
        )
        return [
            UniverseItem(
                symbol=row["symbol"],
                code=row["code"],
                exchange=row["exchange"],
                name=row["name"],
                status=row["status"],
                source=row["source"],
            )
            for row in rows
        ]

    def replace_stock_universe(self, items: list[UniverseItem]) -> None:
        """整体刷新本地股票池成员关系。"""
        with self._connect() as connection:
            connection.execute("DELETE FROM universe_memberships")
            for item in items:
                self._upsert_instrument_with_connection(
                    connection=connection,
                    symbol=item.symbol,
                    code=item.code,
                    exchange=item.exchange,
                    name=item.name,
                    list_date=None,
                    source=item.source,
                )

            if items:
                connection.executemany(
                    """
                    INSERT INTO universe_memberships (
                        symbol, membership_status, source, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        [
                            item.symbol,
                            item.status,
                            item.source,
                            datetime.utcnow(),
                        ]
                        for item in items
                    ],
                )

            connection.execute(
                """
                INSERT OR REPLACE INTO snapshot_sync_state (dataset_type, synced_at)
                VALUES (?, ?)
                """,
                [DATASET_UNIVERSE, datetime.utcnow()],
            )

    def get_stock_announcements(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        limit: int = 20,
    ) -> list[AnnouncementItem]:
        """读取本地公告列表。"""
        rows = self._fetchall(
            """
            SELECT symbol, title, publish_date, announcement_type, source, url
            FROM announcement_events
            WHERE symbol = ? AND publish_date >= ? AND publish_date <= ?
            ORDER BY publish_date DESC, external_id DESC
            LIMIT ?
            """,
            [symbol, start_date, end_date, limit],
        )
        return [
            AnnouncementItem(
                symbol=row["symbol"],
                title=row["title"],
                publish_date=row["publish_date"],
                announcement_type=row["announcement_type"],
                source=row["source"],
                url=row["url"],
            )
            for row in rows
        ]

    def get_latest_announcement_publish_date(self, symbol: str) -> Optional[date]:
        """读取本地最新公告发布日期。"""
        row = self._fetchone(
            """
            SELECT MAX(publish_date) AS latest_publish_date
            FROM announcement_events
            WHERE symbol = ?
            """,
            [symbol],
        )
        if row is None:
            return None
        return row["latest_publish_date"]

    def upsert_stock_announcements(self, items: list[AnnouncementItem]) -> None:
        """写入本地公告列表。"""
        if not items:
            return

        first_item = items[0]
        symbol_parts = first_item.symbol.split(".")
        self._upsert_instrument(
            symbol=first_item.symbol,
            code=symbol_parts[0],
            exchange=symbol_parts[1],
            name=first_item.symbol,
            list_date=None,
            source=first_item.source,
        )

        self._executemany(
            """
            INSERT OR REPLACE INTO announcement_events (
                provider, external_id, symbol, title, publish_date,
                announcement_type, url, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [
                    item.source,
                    _build_announcement_external_id(item),
                    item.symbol,
                    item.title,
                    item.publish_date,
                    item.announcement_type,
                    item.url,
                    item.source,
                    datetime.utcnow(),
                ]
                for item in items
            ],
        )

    def get_stock_financial_summary(self, symbol: str) -> Optional[FinancialSummary]:
        """读取本地最新财务摘要。"""
        row = self._fetchone(
            """
            SELECT
                fr.symbol,
                i.name,
                fr.report_period,
                fr.revenue,
                fr.revenue_yoy,
                fr.net_profit,
                fr.net_profit_yoy,
                fr.roe,
                fr.gross_margin,
                fr.debt_ratio,
                fr.eps,
                fr.bps,
                fr.source,
                fr.report_type,
                fr.quality_status,
                fr.cleaning_warnings_json,
                fr.missing_fields_json,
                fr.coerced_fields_json,
                fr.provider_used,
                fr.fallback_applied,
                fr.fallback_reason,
                fr.source_mode,
                fr.freshness_mode,
                fr.as_of_date
            FROM financial_reports AS fr
            LEFT JOIN instruments AS i
              ON fr.symbol = i.symbol
            WHERE fr.symbol = ?
            ORDER BY fr.report_period_key DESC, fr.updated_at DESC
            LIMIT 1
            """,
            [symbol],
        )
        if row is None:
            return None

        return FinancialSummary(
            symbol=row["symbol"],
            name=row["name"] or symbol,
            report_period=row["report_period"],
            revenue=row["revenue"],
            revenue_yoy=row["revenue_yoy"],
            net_profit=row["net_profit"],
            net_profit_yoy=row["net_profit_yoy"],
            roe=row["roe"],
            gross_margin=row["gross_margin"],
            debt_ratio=row["debt_ratio"],
            eps=row["eps"],
            bps=row["bps"],
            source=row["source"],
            report_type=row["report_type"],
            quality_status=row["quality_status"],
            cleaning_warnings=_load_json_text_list(row["cleaning_warnings_json"]),
            missing_fields=_load_json_text_list(row["missing_fields_json"]),
            coerced_fields=_load_json_text_list(row["coerced_fields_json"]),
            provider_used=row["provider_used"],
            fallback_applied=bool(row["fallback_applied"]) if row["fallback_applied"] is not None else False,
            fallback_reason=row["fallback_reason"],
            source_mode=row["source_mode"],
            freshness_mode=row["freshness_mode"],
            as_of_date=row["as_of_date"],
        )

    def upsert_stock_financial_summary(self, summary: FinancialSummary) -> None:
        """写入本地财务摘要到财务报告事实表。"""
        symbol_parts = summary.symbol.split(".")
        self._upsert_instrument(
            symbol=summary.symbol,
            code=symbol_parts[0],
            exchange=symbol_parts[1],
            name=summary.name,
            list_date=None,
            source=summary.source,
        )

        report_period_key = summary.report_period or _UNKNOWN_REPORT_PERIOD
        self._execute(
            """
            INSERT OR REPLACE INTO financial_reports (
                symbol, report_period_key, report_period, revenue, revenue_yoy,
                net_profit, net_profit_yoy, roe, gross_margin, debt_ratio,
                eps, bps, source, report_type, quality_status,
                cleaning_warnings_json, missing_fields_json, coerced_fields_json,
                provider_used, fallback_applied, fallback_reason,
                source_mode, freshness_mode, as_of_date, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                summary.symbol,
                report_period_key,
                summary.report_period,
                summary.revenue,
                summary.revenue_yoy,
                summary.net_profit,
                summary.net_profit_yoy,
                summary.roe,
                summary.gross_margin,
                summary.debt_ratio,
                summary.eps,
                summary.bps,
                summary.source,
                summary.report_type,
                summary.quality_status,
                _dump_json_text_list(summary.cleaning_warnings),
                _dump_json_text_list(summary.missing_fields),
                _dump_json_text_list(summary.coerced_fields),
                summary.provider_used,
                summary.fallback_applied,
                summary.fallback_reason,
                summary.source_mode,
                summary.freshness_mode,
                summary.as_of_date,
                datetime.now(timezone.utc),
            ],
        )

    def is_range_covered(
        self,
        dataset_type: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> bool:
        """判断某个日期范围是否已在本地完成过同步。"""
        ranges = self._fetchall(
            """
            SELECT start_date, end_date
            FROM range_sync_state
            WHERE dataset_type = ? AND symbol = ?
            ORDER BY start_date, end_date
            """,
            [dataset_type, symbol],
        )
        if not ranges:
            return False

        merged_start: Optional[date] = None
        merged_end: Optional[date] = None
        for item in ranges:
            current_start = item["start_date"]
            current_end = item["end_date"]
            if merged_start is None:
                merged_start = current_start
                merged_end = current_end
            elif current_start <= merged_end + timedelta(days=1):
                if current_end > merged_end:
                    merged_end = current_end
            else:
                if merged_start <= start_date and merged_end >= end_date:
                    return True
                merged_start = current_start
                merged_end = current_end

        if merged_start is None or merged_end is None:
            return False
        return merged_start <= start_date and merged_end >= end_date

    def mark_range_covered(
        self,
        dataset_type: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> None:
        """记录某个日期范围已完成过线上同步，并合并重叠区间。"""
        rows = self._fetchall(
            """
            SELECT start_date, end_date
            FROM range_sync_state
            WHERE dataset_type = ? AND symbol = ?
            ORDER BY start_date, end_date
            """,
            [dataset_type, symbol],
        )

        merged_start = start_date
        merged_end = end_date
        rows_to_keep: list[tuple[date, date]] = []

        for row in rows:
            current_start = row["start_date"]
            current_end = row["end_date"]
            if (
                current_end < merged_start - timedelta(days=1)
                or current_start > merged_end + timedelta(days=1)
            ):
                rows_to_keep.append((current_start, current_end))
                continue

            if current_start < merged_start:
                merged_start = current_start
            if current_end > merged_end:
                merged_end = current_end

        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM range_sync_state
                WHERE dataset_type = ? AND symbol = ?
                """,
                [dataset_type, symbol],
            )

            rows_to_keep.append((merged_start, merged_end))
            connection.executemany(
                """
                INSERT INTO range_sync_state (
                    dataset_type, symbol, start_date, end_date, synced_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    [
                        dataset_type,
                        symbol,
                        item_start,
                        item_end,
                        datetime.utcnow(),
                    ]
                    for item_start, item_end in sorted(rows_to_keep)
                ],
            )

    def _upsert_instrument(
        self,
        symbol: str,
        code: str,
        exchange: str,
        name: str,
        list_date: Optional[date],
        source: str,
    ) -> None:
        """写入或更新股票主实体。"""
        with self._connect() as connection:
            self._upsert_instrument_with_connection(
                connection=connection,
                symbol=symbol,
                code=code,
                exchange=exchange,
                name=name,
                list_date=list_date,
                source=source,
            )

    def _upsert_instrument_with_connection(
        self,
        connection: duckdb.DuckDBPyConnection,
        symbol: str,
        code: str,
        exchange: str,
        name: str,
        list_date: Optional[date],
        source: str,
    ) -> None:
        """在现有连接中写入或更新股票主实体。"""
        existing_row = connection.execute(
            """
            SELECT name, list_date, source
            FROM instruments
            WHERE symbol = ?
            """,
            [symbol],
        ).fetchone()

        resolved_name = name
        resolved_list_date = list_date
        resolved_source = source

        if existing_row is not None:
            if (
                resolved_name == symbol
                and existing_row[0] is not None
                and existing_row[0] != ""
            ):
                resolved_name = existing_row[0]
            if resolved_list_date is None and existing_row[1] is not None:
                resolved_list_date = existing_row[1]
            if resolved_source == "" and existing_row[2] is not None:
                resolved_source = existing_row[2]

        connection.execute(
            """
            INSERT OR REPLACE INTO instruments (
                symbol, code, exchange, name, list_date, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                symbol,
                code,
                exchange,
                resolved_name,
                resolved_list_date,
                resolved_source,
                datetime.utcnow(),
            ],
        )

    def _initialize(self) -> None:
        """初始化 DuckDB 表结构。"""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS instruments (
                    symbol TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    name TEXT NOT NULL,
                    list_date DATE,
                    source TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS instrument_profile_snapshots (
                    symbol TEXT PRIMARY KEY,
                    industry TEXT,
                    status TEXT,
                    total_market_cap DOUBLE,
                    circulating_market_cap DOUBLE,
                    source TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS universe_memberships (
                    symbol TEXT PRIMARY KEY,
                    membership_status TEXT,
                    source TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_bars (
                    symbol TEXT NOT NULL,
                    trade_date DATE NOT NULL,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    amount DOUBLE,
                    source TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY(symbol, trade_date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS announcement_events (
                    provider TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publish_date DATE NOT NULL,
                    announcement_type TEXT,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY(provider, external_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_reports (
                    symbol TEXT NOT NULL,
                    report_period_key DATE NOT NULL,
                    report_period DATE,
                    revenue DOUBLE,
                    revenue_yoy DOUBLE,
                    net_profit DOUBLE,
                    net_profit_yoy DOUBLE,
                    roe DOUBLE,
                    gross_margin DOUBLE,
                    debt_ratio DOUBLE,
                    eps DOUBLE,
                    bps DOUBLE,
                    source TEXT NOT NULL,
                    report_type TEXT,
                    quality_status TEXT,
                    cleaning_warnings_json TEXT,
                    missing_fields_json TEXT,
                    coerced_fields_json TEXT,
                    provider_used TEXT,
                    fallback_applied BOOLEAN,
                    fallback_reason TEXT,
                    source_mode TEXT,
                    freshness_mode TEXT,
                    as_of_date DATE,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY(symbol, report_period_key)
                )
                """
            )
            self._ensure_financial_report_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS range_sync_state (
                    dataset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    synced_at TIMESTAMP NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshot_sync_state (
                    dataset_type TEXT PRIMARY KEY,
                    synced_at TIMESTAMP NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_cursors (
                    cursor_key TEXT PRIMARY KEY,
                    cursor_value TEXT,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
            self._migrate_legacy_tables(connection)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """创建数据库连接。"""
        return duckdb.connect(str(self._database_path))

    def _migrate_legacy_tables(self, connection: duckdb.DuckDBPyConnection) -> None:
        """把旧版缓存表迁移到新的原子化表结构。"""
        if self._table_exists(connection, "stock_profiles"):
            self._migrate_legacy_stock_profiles(connection)
        if self._table_exists(connection, "universe_items"):
            self._migrate_legacy_universe_items(connection)
        if self._table_exists(connection, "financial_summaries"):
            self._migrate_legacy_financial_summaries(connection)
        if self._table_exists(connection, "announcements"):
            self._migrate_legacy_announcements(connection)

    def _ensure_financial_report_columns(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        """确保 financial_reports 具备增量演进所需列。"""
        expected_columns = {
            "report_type": "TEXT",
            "quality_status": "TEXT",
            "cleaning_warnings_json": "TEXT",
            "missing_fields_json": "TEXT",
            "coerced_fields_json": "TEXT",
            "provider_used": "TEXT",
            "fallback_applied": "BOOLEAN",
            "fallback_reason": "TEXT",
            "source_mode": "TEXT",
            "freshness_mode": "TEXT",
            "as_of_date": "DATE",
        }
        existing_columns = self._table_columns(connection, "financial_reports")
        for column_name, column_type in expected_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                "ALTER TABLE financial_reports ADD COLUMN {column_name} {column_type}".format(
                    column_name=column_name,
                    column_type=column_type,
                ),
            )

    def _migrate_legacy_stock_profiles(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        """迁移旧版股票基础信息表。"""
        if self._table_has_rows(connection, "instruments"):
            return

        rows = connection.execute(
            """
            SELECT symbol, code, exchange, name, industry, list_date, status,
                   total_market_cap, circulating_market_cap, source, updated_at
            FROM stock_profiles
            """
        ).fetchall()
        if not rows:
            return

        connection.executemany(
            """
            INSERT OR REPLACE INTO instruments (
                symbol, code, exchange, name, list_date, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [row[0], row[1], row[2], row[3], row[5], row[9], row[10]]
                for row in rows
            ],
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO instrument_profile_snapshots (
                symbol, industry, status, total_market_cap,
                circulating_market_cap, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [row[0], row[4], row[6], row[7], row[8], row[9], row[10]]
                for row in rows
            ],
        )

    def _migrate_legacy_universe_items(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        """迁移旧版股票池表。"""
        if self._table_has_rows(connection, "universe_memberships"):
            return

        rows = connection.execute(
            """
            SELECT symbol, code, exchange, name, status, source, updated_at
            FROM universe_items
            """
        ).fetchall()
        if not rows:
            return

        for row in rows:
            self._upsert_instrument_with_connection(
                connection=connection,
                symbol=row[0],
                code=row[1],
                exchange=row[2],
                name=row[3],
                list_date=None,
                source=row[5],
            )

        connection.executemany(
            """
            INSERT OR REPLACE INTO universe_memberships (
                symbol, membership_status, source, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            [[row[0], row[4], row[5], row[6]] for row in rows],
        )

    def _migrate_legacy_financial_summaries(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        """迁移旧版财务摘要表。"""
        if self._table_has_rows(connection, "financial_reports"):
            return

        rows = connection.execute(
            """
            SELECT symbol, name, report_period, revenue, revenue_yoy, net_profit,
                   net_profit_yoy, roe, gross_margin, debt_ratio, eps, bps, source, updated_at
            FROM financial_summaries
            """
        ).fetchall()
        if not rows:
            return

        for row in rows:
            symbol_parts = str(row[0]).split(".")
            if len(symbol_parts) != 2:
                continue
            self._upsert_instrument_with_connection(
                connection=connection,
                symbol=row[0],
                code=symbol_parts[0],
                exchange=symbol_parts[1],
                name=row[1],
                list_date=None,
                source=row[12],
            )

        connection.executemany(
            """
            INSERT OR REPLACE INTO financial_reports (
                symbol, report_period_key, report_period, revenue, revenue_yoy,
                net_profit, net_profit_yoy, roe, gross_margin, debt_ratio,
                eps, bps, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [
                    row[0],
                    row[2] or _UNKNOWN_REPORT_PERIOD,
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    row[11],
                    row[12],
                    row[13],
                ]
                for row in rows
            ],
        )

    def _migrate_legacy_announcements(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        """迁移旧版公告表。"""
        if self._table_has_rows(connection, "announcement_events"):
            return

        rows = connection.execute(
            """
            SELECT symbol, title, publish_date, announcement_type, source, url, updated_at
            FROM announcements
            """
        ).fetchall()
        if not rows:
            return

        connection.executemany(
            """
            INSERT OR REPLACE INTO announcement_events (
                provider, external_id, symbol, title, publish_date,
                announcement_type, url, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                [
                    row[4],
                    _build_announcement_external_id(
                        AnnouncementItem(
                            symbol=row[0],
                            title=row[1],
                            publish_date=row[2],
                            announcement_type=row[3],
                            source=row[4],
                            url=row[5],
                        )
                    ),
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[5],
                    row[4],
                    row[6],
                ]
                for row in rows
            ],
        )

    def _table_exists(
        self,
        connection: duckdb.DuckDBPyConnection,
        table_name: str,
    ) -> bool:
        """判断某张表是否存在。"""
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchone()
        return row is not None and row[0] > 0

    def _table_columns(
        self,
        connection: duckdb.DuckDBPyConnection,
        table_name: str,
    ) -> set[str]:
        """读取指定表的列名集合。"""
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchall()
        return {str(row[0]) for row in rows}

    def _table_has_rows(
        self,
        connection: duckdb.DuckDBPyConnection,
        table_name: str,
    ) -> bool:
        """判断某张表是否已有数据。"""
        row = connection.execute(
            "SELECT COUNT(*) FROM {table_name}".format(table_name=table_name),
        ).fetchone()
        return row is not None and row[0] > 0

    def _execute(self, query: str, params: list[object]) -> None:
        with self._connect() as connection:
            connection.execute(query, params)

    def _executemany(self, query: str, params: list[list[object]]) -> None:
        if not params:
            return
        with self._connect() as connection:
            connection.executemany(query, params)

    def _fetchone(self, query: str, params: list[object]) -> Optional[dict[str, object]]:
        rows = self._fetchall(query, params)
        if not rows:
            return None
        return rows[0]

    def _fetchall(self, query: str, params: list[object]) -> list[dict[str, object]]:
        with self._connect() as connection:
            cursor = connection.execute(query, params)
            rows = cursor.fetchall()
            columns = [item[0] for item in cursor.description]

        return [dict(zip(columns, row)) for row in rows]

    def get_refresh_cursor(self, cursor_key: str) -> Optional[str]:
        """读取补全游标。"""
        row = self._fetchone(
            """
            SELECT cursor_value
            FROM refresh_cursors
            WHERE cursor_key = ?
            """,
            [cursor_key],
        )
        if row is None:
            return None
        value = row["cursor_value"]
        if value is None:
            return None
        return str(value)

    def set_refresh_cursor(self, cursor_key: str, cursor_value: Optional[str]) -> None:
        """写入补全游标。"""
        if cursor_value is None:
            self._execute(
                """
                DELETE FROM refresh_cursors
                WHERE cursor_key = ?
                """,
                [cursor_key],
            )
            return

        self._execute(
            """
            INSERT OR REPLACE INTO refresh_cursors (
                cursor_key, cursor_value, updated_at
            ) VALUES (?, ?, ?)
            """,
            [cursor_key, cursor_value, datetime.now(timezone.utc)],
        )

    def scale_daily_bar_volume_by_source(
        self,
        *,
        source: str,
        factor: float,
    ) -> int:
        """按来源批量缩放日线成交量并返回影响行数。"""
        if factor <= 0:
            raise ValueError("factor must be greater than 0.")

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS row_count
                FROM daily_bars
                WHERE source = ? AND volume IS NOT NULL
                """,
                [source],
            ).fetchone()
            row_count = int(row[0] or 0) if row is not None else 0
            if row_count <= 0:
                return 0

            connection.execute(
                """
                UPDATE daily_bars
                SET volume = volume * ?, updated_at = ?
                WHERE source = ? AND volume IS NOT NULL
                """,
                [factor, datetime.now(timezone.utc), source],
            )
            return row_count

    def list_queryable_tables(self) -> list[dict[str, object]]:
        """列出当前数据库可查询表及行数。"""
        table_rows = self._fetchall(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """,
            [],
        )
        result: list[dict[str, object]] = []
        for item in table_rows:
            table_name = str(item["table_name"])
            count_row = self._fetchone(
                "SELECT COUNT(*) AS row_count FROM {table_name}".format(
                    table_name=table_name,
                ),
                [],
            )
            row_count = int(count_row["row_count"]) if count_row is not None else 0
            result.append(
                {
                    "table_name": table_name,
                    "row_count": row_count,
                },
            )
        return result

    def execute_readonly_sql(
        self,
        sql: str,
        limit: int = 200,
    ) -> tuple[list[str], list[list[object]]]:
        """执行只读 SQL 查询并返回列名与数据行。"""
        if limit <= 0:
            limit = 200
        safe_limit = min(limit, 2000)
        normalized_sql = sql.strip().rstrip(";")
        lowered = normalized_sql.lower()
        if not lowered.startswith(("select", "with", "pragma", "describe", "show", "explain")):
            raise ValueError("Only read-only SQL is allowed.")
        if ";" in normalized_sql:
            raise ValueError("Only one SQL statement is allowed.")

        with self._connect() as connection:
            cursor = connection.execute(normalized_sql)
            rows = cursor.fetchall()
            columns = [item[0] for item in cursor.description] if cursor.description else []
        if len(rows) > safe_limit:
            rows = rows[:safe_limit]

        serialized_rows = [
            [_serialize_sql_value(value) for value in row]
            for row in rows
        ]
        return columns, serialized_rows


def _build_announcement_external_id(item: AnnouncementItem) -> str:
    """构造稳定的公告外部标识。"""
    parsed_url = urlparse(item.url)
    query = parse_qs(parsed_url.query)

    announcement_id = _pick_first_query_value(query, "announcementId")
    org_id = _pick_first_query_value(query, "orgId")
    if announcement_id is not None:
        if org_id is not None:
            return "{source}:{announcement_id}:{org_id}".format(
                source=item.source,
                announcement_id=announcement_id,
                org_id=org_id,
            )
        return "{source}:{announcement_id}".format(
            source=item.source,
            announcement_id=announcement_id,
        )

    digest = hashlib.sha1(
        (
            "{source}|{symbol}|{publish_date}|{title}|{url}".format(
                source=item.source,
                symbol=item.symbol,
                publish_date=item.publish_date.isoformat(),
                title=item.title,
                url=item.url,
            )
        ).encode("utf-8")
    ).hexdigest()
    return "{source}:{digest}".format(source=item.source, digest=digest)


def _pick_first_query_value(query: dict[str, list[str]], key: str) -> Optional[str]:
    """读取查询字符串中的首个值。"""
    values = query.get(key)
    if not values:
        return None

    value = values[0].strip()
    if value == "":
        return None
    return value


def _serialize_sql_value(value: object) -> object:
    """把数据库值转换为可 JSON 序列化类型。"""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _dump_json_text_list(values: Optional[list[str]]) -> Optional[str]:
    """把字符串列表安全序列化为 JSON 文本。"""
    if not values:
        return None
    normalized = [str(value) for value in values if str(value).strip() != ""]
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def _load_json_text_list(value: object) -> list[str]:
    """把 JSON 文本反序列化为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip() != ""]
    text = str(value).strip()
    if text == "":
        return []
    try:
        loaded = json.loads(text)
    except Exception:
        return [text]
    if not isinstance(loaded, list):
        return [str(loaded)]
    return [str(item) for item in loaded if str(item).strip() != ""]
