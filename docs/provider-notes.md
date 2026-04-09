# docs/provider-notes.md

# 数据源使用说明与约束（Provider Notes）

## 1. 文档目标

本文档用于约束本项目对 A 股数据源的使用顺序、字段标准化、联调方式、数据质量判断、异常切换与本地落袋策略。

本项目当前采用 **“本地优先、免费优先、可验证优先、官方披露优先”** 的数据策略。

本文档覆盖的主要数据源：

- 本地 `tdx-api`
- 本地 `mootdx`
- `AKShare`
- `CNINFO / 巨潮资讯`
- `BaoStock`

---

## 2. 总体原则

### 2.1 数据源优先级原则

按你当前的项目现状，默认优先级应调整为：

1. **tdx-api**：凡是本地 `tdx-api` 能稳定提供且满足质量要求的数据，优先使用。其 API 文档说明了统一返回格式、股票搜索、股票代码列表、五档盘口、K 线、全量 K 线、分时成交、交易日范围等能力。citeturn841242view2turn429543view0
2. **mootdx（本地离线文件）**：凡是需要高吞吐、低延迟、低依赖外部网站的数据读取，优先评估本地 `mootdx` 读取；但必须通过**新鲜度判断**和**字段契约测试**后才能进入正式链路。mootdx README 明确展示了离线读取日线、分钟线、时间线，以及在线行情和财务文件下载能力。citeturn841242view1
3. **CNINFO / 巨潮资讯**：凡是公告、定期报告、临时公告、正式披露类信息，优先以官方披露源为准。
4. **BaoStock**：作为**稳定兜底行情源**和**基础证券信息补充源**，优先承担日线/分钟线、股票池、基础证券资料等相对稳定数据的 fallback。
5. **AKShare**：作为**广覆盖补充源**和**研究扩展源**，优先用于 tdx-api / mootdx / BaoStock / CNINFO 无法覆盖的场景；但必须做本地落袋、频率控制、异常判断与源切换。AKShare 文档说明其是基于 Python 的财经数据接口库，覆盖从数据采集、清洗到落地的一套工具，数据来自公开源，主要用于学术研究。citeturn841242view0

### 2.2 官方披露优先原则

- **公告、财报、正式披露文本**：以 `CNINFO / 巨潮资讯` 为真相源。
- **门户与聚合结果**：只作为索引、补充和辅助，不作为最终真相源。
- **AI/LLM**：绝不作为事实源，只能做结构化和解释层。

### 2.3 结构化优先原则

所有 provider 输出都必须进入统一 schema。

禁止：

- 在 route 层直接消费第三方原始字段。
- 把 provider 返回的 dataframe / dict 原样透出到 API。
- 在多个文件里重复做 symbol/date/unit 转换。

---

## 3. 数据域与默认来源映射

| 数据域 | 默认首选 | 第二优先 | 第三优先 | 说明 |
|---|---|---|---|---|
| 股票代码搜索 | tdx-api | BaoStock | AKShare | tdx-api 已提供 `/api/search` 与 `/api/stock-codes`。citeturn429543view0 |
| A 股基础股票池 | tdx-api | BaoStock | AKShare | 优先使用本地服务导出的代码列表。citeturn429543view0 |
| 实时五档盘口 | tdx-api | mootdx 在线 quotes | 无 | tdx-api 已提供 `/api/quote`。citeturn841242view2 |
| 日线 / 周线 / 月线 K 线 | tdx-api | mootdx 离线 reader | BaoStock / AKShare | 以本地优先，但必须校验复权口径与单位。citeturn875341view0turn841242view1 |
| 分钟 K 线 | tdx-api | mootdx 离线/在线 | BaoStock | 本地优先；若分钟数据不新鲜则切换。citeturn875341view0turn841242view1 |
| 时间线 / 分时成交 | tdx-api | mootdx | 无 | tdx-api 已提供全天分时成交接口。citeturn429543view0 |
| 全量历史 K 线 | tdx-api | mootdx | BaoStock | tdx-api 已提供 `/api/kline-all` 与源拆分接口。citeturn429543view2turn875341view0 |
| 交易日历 / 区间交易日 | tdx-api | BaoStock | AKShare | tdx-api 已提供交易日范围接口。citeturn429543view0 |
| 正式公告列表 | CNINFO | AKShare | 无 | 官方披露优先 |
| 财务摘要 | AKShare | BaoStock | 无 | 先用结构化摘要，不直接做 PDF/正文解析 |
| 财务原始文件 / 财务下载 | CNINFO | mootdx Affair | 无 | mootdx README 展示了财务文件下载能力。citeturn841242view1 |
| 板块、题材、资金流等扩展研究数据 | AKShare | 东方财富等网页源 | 无 | 只做补充源，必须落袋 |

---

## 4. 各数据源使用约束

## 4.1 tdx-api（本地 HTTP 服务）

### 4.1.1 定位

`tdx-api` 是本项目当前的**本地主数据源**。

优先使用场景：

- 股票搜索与基础代码列表
- 实时五档盘口
- 日/周/月/分钟 K 线
- 全量历史 K 线
- 分时成交
- 交易日范围

其接口文档给出了统一返回格式 `code / message / data`，并提供 `GET /api/quote`、`GET /api/kline`、`GET /api/search`、`GET /api/stock-codes`、`GET /api/kline-all`、`GET /api/kline-all/tdx`、`GET /api/kline-all/ths`、`GET /api/minute-trade-all`、`GET /api/workday/range` 等能力。citeturn841242view2turn429543view0turn875341view0

### 4.1.2 已知契约

根据接口文档：

- 统一响应格式：`code=0` 代表成功，`data` 为有效负载。citeturn841242view2
- `/api/quote` 价格单位为**厘**，成交量单位为**手**，挂单量单位为**股**。citeturn841242view2
- `/api/kline` 与 `/api/kline-all` 也沿用价格/成交量相关单位说明，需要统一换算。citeturn875341view0
- `/api/stock-codes` 默认可返回带交易所前缀的代码，例如 `sh600000`、`sz000001`。citeturn429543view0
- 文档明确区分了 `kline-all/tdx`（通达信原始不复权）与 `kline-all/ths`（同花顺前复权）。citeturn875341view0

### 4.1.3 项目约束

1. 所有 `tdx-api` 输出必须先经过**单位换算**和**字段标准化**。
2. 不得在业务层直接使用“厘”“手”这些原始单位。
3. `kline-all/tdx` 与 `kline-all/ths` 必须显式记录 `adjustment_source`：
   - `none`
   - `forward_adjusted_ths`
4. 如果同一业务链路要求统一复权口径，则不得混用 `tdx` 原始数据与 `ths` 前复权数据。
5. 如果 `tdx-api` 某接口失败，不允许直接把本地 HTTP 原始错误返回给 API。

### 4.1.4 推荐健康检查

项目内应为 `tdx-api` 增加单独 health check，例如：

- 连通性：基础 URL 是否可访问。
- 搜索能力：`/api/search?keyword=000001` 是否返回结果。citeturn429543view0
- 股票池能力：`/api/stock-codes` 是否返回列表。citeturn429543view0
- K 线能力：随机抽一只股票拉取 `/api/kline?code=000001&type=day`。
- 交易日能力：`/api/workday/range` 是否返回交易日列表。citeturn429543view0

### 4.1.5 推荐使用顺序

- 股票池：优先 `tdx-api /api/stock-codes`
- 搜索：优先 `tdx-api /api/search`
- 日线 / 分钟：优先 `tdx-api /api/kline` 或 `kline-all`
- 分时成交：优先 `tdx-api /api/minute-trade-all`
- 五档盘口：优先 `tdx-api /api/quote`

---

## 4.2 mootdx（本地离线文件 + 在线能力）

### 4.2.1 定位

`mootdx` 在本项目中应被定义为：

- **本地高速历史数据读取源**
- **本地文件优先的低频/批量研究源**
- **当 tdx-api 不可用或不适合高频批量拉取时的优先兜底源**

mootdx README 明确展示了：

- `Reader.factory(...).daily()` 读取离线日线
- `Reader.factory(...).minute()` 读取离线分钟线
- `Reader.factory(...).fzline()` 读取时间线
- `Quotes.factory(...).bars()` 读取在线行情
- `Affair.files/fetch/parse` 读取和下载财务相关文件。citeturn841242view1

### 4.2.2 本项目对 mootdx 的判断

优点：

- 读取本地文件，速度快。
- 无明显远程频率限制。
- 对大批量历史行情、分钟线、时间线类读取很有价值。

风险：

- 本地数据需要你先下载，存在**不新鲜**风险。
- README 示例清楚，但很多字段、单位、边界条件在项目侧仍需要自己做契约测试。citeturn841242view1
- GitHub 页面显示最新 release 为 `v0.11.7`，发布日期为 2024-05-05；对 2026 年项目来说应视为**相对陈旧依赖**，必须提高数据契约验证强度。citeturn656047view2

### 4.2.3 项目约束

1. mootdx **默认不能直接当真相源**，必须先通过：
   - 新鲜度检查
   - 字段契约测试
   - 单位与口径样本校验
2. 对 mootdx 读取出的 OHLCV，不得假定字段和单位一定与 tdx-api 完全一致。
3. 对本地离线数据，必须保存：
   - `source_file_date`
   - `ingested_at`
   - `freshness_status`
4. 如果 mootdx 数据已过最新交易日，则只能作为：
   - 回测 / 历史研究源
   - 当日盘前参考
   - 非实时兜底
   不得默认用于“实时最新价”判断。

### 4.2.4 新鲜度判断规则（建议项目级固化）

对本地离线日线与分钟线，建议项目内增加如下判断：

#### 日线数据新鲜度

- 若当前时间在交易日收盘前：允许最新数据日期 = 上一交易日。
- 若当前时间在交易日收盘后且过了数据同步窗口：应期望最新数据日期 = 当日。
- 若落后一整个交易日及以上：标记为 `stale`。

#### 分钟数据新鲜度

- 如果当前是盘中：最新 bar 时间若落后阈值过大，则标记为 `stale_intraday`。
- 如果当前是盘后：允许分钟数据停在收盘时刻。

#### 时间线数据新鲜度

- 使用最近时间戳与当前交易时段对比判断。

### 4.2.5 推荐使用顺序

- 批量日线：优先 mootdx 本地 reader
- 批量分钟线：优先 mootdx 本地 reader
- 时间线：优先 mootdx 本地 reader 或 tdx-api（视联调效果）
- 实时盘口：不优先 mootdx，优先 tdx-api
- 财务下载：仅做补充，不替代 CNINFO 正式披露

---

## 4.3 AKShare

### 4.3.1 定位

AKShare 在本项目中应被定义为：

- **广覆盖补充源**
- **研究扩展源**
- **结构化补全源**
- **当本地链路无对应数据域时的补充源**

AKShare 文档说明其为基于 Python 的财经数据接口库，目标是覆盖多类金融产品的数据采集、清洗与落地，主要用于学术研究，且数据来自公开数据源。citeturn841242view0

### 4.3.2 项目判断

优点：

- 覆盖广，适合公告索引、财务摘要、板块、资金流、情绪近似、宏观扩展等。
- 对快速补齐研究输入很有价值。

风险：

- 接口较依赖公开网页和公开站点结构。
- 项目侧经验上要把它当作**高频限制源/脆弱源**来处理，即便文档未统一给出固定限流数值。
- 不适合做“每次请求都在线现抓”的核心实时链路。

### 4.3.3 项目约束

1. AKShare **必须做本地落袋**：
   - 原始响应缓存
   - 结构化结果缓存
   - 入库时间记录
2. AKShare **必须有频率保护**：
   - 单实例串行或限速
   - 重试带退避
   - 错误预算
3. AKShare **不得作为高频盘中主数据源**。
4. 对 AKShare 输出字段，必须走集中 mapping，不准在多个 service 各自转字段。

### 4.3.4 推荐使用场景

- 财务摘要
- 公告索引补充
- 板块/题材/资金流等扩展研究数据
- 无本地源可用时的低频拉取

### 4.3.5 推荐实现策略

- `cache-first`：先查本地，再决定是否在线抓取
- `write-through`：抓到后立即结构化并落库
- `cooldown`：同一 symbol / endpoint 在冷却时间内不重复抓
- `circuit-breaker`：连续失败时临时熔断切回其他源

---

## 4.4 CNINFO / 巨潮资讯

### 4.4.1 定位

`CNINFO` 是本项目的**正式披露真相源**。

适用范围：

- 公告列表
- 定期报告索引
- 临时公告
- 正式披露 PDF/附件

### 4.4.2 项目约束

1. 正式披露类信息，默认以 CNINFO 为准。
2. 任何来自 AKShare / 门户站的公告信息，若与 CNINFO 冲突，以 CNINFO 为准。
3. 第一版可以只做公告索引；正文解析和 PDF 解析必须单独版本推进。
4. 公告字段至少统一为：
   - `symbol`
   - `title`
   - `publish_date`
   - `announcement_type`
   - `source`
   - `url`

---

## 4.5 BaoStock

### 4.5.1 定位

`BaoStock` 在本项目中应被定义为：

- **稳定兜底行情源**
- **股票池与证券基础信息补充源**
- **当本地源不可用时的结构化 fallback**

BaoStock 官方站点说明 `query_history_k_data_plus()` 可获取 A 股历史日/周/月及 5/15/30/60 分钟 K 线数据。citeturn787417search1

### 4.5.2 项目约束

1. BaoStock 用于 fallback 时，必须在数据中显式标识 `source=baostock`。
2. 代码格式通常采用 `sh.600519` / `sz.000001`，不得把此格式泄漏到 API 层。
3. 与本地源混用时，必须经过统一 symbol / date / numeric schema。
4. 如使用 BaoStock 股票池或基础证券资料，必须统一映射到项目 canonical symbol。

---

## 5. Canonical Schema 与字段标准

## 5.1 统一代码格式

项目内部唯一 canonical symbol：

- `600519.SH`
- `000001.SZ`
- `300750.SZ`

### Provider 映射规则

| Provider | 输入/返回常见格式 | 项目内部格式 |
|---|---|---|
| tdx-api | `000001` / `sh600000` / `sz000001` | `000001.SZ` / `600000.SH` |
| mootdx | `600036` | `600036.SH` |
| BaoStock | `sh.600519` / `sz.000001` | `600519.SH` / `000001.SZ` |
| AKShare | `600519` / `000001` | `600519.SH` / `000001.SZ` |
| CNINFO | `600519` / `000001` | `600519.SH` / `000001.SZ` |

禁止：

- 在 route 层做 symbol 格式转换
- 在不同 provider 文件里各自定义一套 symbol 规则

必须集中在：

- `normalize.py`

## 5.2 日期与时间格式

### API 层输出

- 日期：`YYYY-MM-DD`
- 时间戳：ISO 8601，带时区或明确约定时区
- 交易所本地时间统一视为 `Asia/Shanghai`

### provider 入库前要求

- 原始时间字段保存一份
- 结构化时间字段统一一份
- 对只有日期无时间的数据，时间部分不得胡乱补盘中时间

## 5.3 数值单位标准

### 项目内部统一输出原则

- 价格：统一输出为 **元**
- 成交量：统一输出为 **股**
- 成交额：统一输出为 **元**

### tdx-api 特别注意

文档说明：

- 价格单位：厘
- 成交量单位：手
- 成交额单位：厘。citeturn841242view2turn875341view0

因此项目内换算应明确写死在标准化层：

- `price_yuan = price_li / 1000`
- `volume_shares = volume_hand * 100`
- `amount_yuan = amount_li / 1000`

### mootdx / BaoStock / AKShare

- 不得凭经验硬写单位。
- 先通过**样本对齐测试**与已知可靠源比对，再确认内部单位映射。
- 契约测试通过后，才允许进入正式主链路。

---

## 6. Provider 选择与切换策略

## 6.1 统一选择器原则

项目必须通过统一的 provider router 选择数据源，禁止业务代码直接点名第三方源。

建议实现：

- `select_provider(data_domain, freshness_requirement, frequency_requirement)`
- `fetch_with_fallback()`

## 6.2 推荐路由逻辑

### 股票池

- 首选：`tdx-api`
- 失败：`BaoStock`
- 再失败：`AKShare`

### 日线 / 周线 / 月线

- 首选：`tdx-api`
- 若需高吞吐批量 + 本地文件新鲜：`mootdx`
- 再兜底：`BaoStock`
- 最后补：`AKShare`

### 分钟线 / 时间线

- 首选：`tdx-api`
- 批量离线研究：`mootdx`
- 再兜底：`BaoStock`（如该周期可用）

### 公告

- 首选：`CNINFO`
- 兜底：`AKShare`

### 财务摘要

- 首选：`AKShare`
- 兜底：`BaoStock`

---

## 7. 数据质量与联调规则

## 7.1 所有 provider 必须通过 4 类校验

### 1. 连通性校验

- 服务是否可访问
- 基础请求是否返回成功

### 2. 契约校验

- 字段是否齐全
- 类型是否符合预期
- 时间与数值是否可解析

### 3. 样本对齐校验

同一只股票在同一交易日，对比：

- 开盘价
- 最高价
- 最低价
- 收盘价
- 成交量
- 成交额

要求：

- 若口径一致，应在允许误差范围内一致
- 若不一致，必须记录差异来源（复权口径/单位/源特性）

### 4. 新鲜度校验

- 最新交易日是否到位
- 盘中数据是否过旧
- 是否需要切源

## 7.2 本地联调建议

建议为每个 provider 做单独 smoke test：

- `test_tdx_api_smoke.py`
- `test_mootdx_reader_smoke.py`
- `test_akshare_provider_smoke.py`
- `test_cninfo_provider_smoke.py`
- `test_baostock_provider_smoke.py`

说明：

- CI 不强依赖外网
- 本地手工联调可通过环境变量开启
- 失败只记录，不阻塞单元测试主链

---

## 8. 缓存与本地落袋策略

## 8.1 强制落袋的源

以下源必须落袋：

- AKShare
- CNINFO 公告索引
- 任何网页抓取型源

## 8.2 建议落袋的源

- tdx-api 股票池
- tdx-api 历史 K 线
- mootdx 本地读取后的标准化结果
- BaoStock 历史 K 线

## 8.3 缓存层级建议

### L1：请求级短缓存

适用于：

- 股票池
- 基础资料
- 短时间重复查询

### L2：结构化结果缓存

适用于：

- 日线 bars
- technical snapshot 输入
- announcements list
- financial summary

### L3：研究输入快照

适用于：

- research report
- strategy plan
- screener candidate snapshot

## 8.4 缓存 key 约定（建议）

- `profile:{symbol}`
- `daily_bars:{symbol}:{start}:{end}:{adjust}`
- `technical:{symbol}:{asof}`
- `announcements:{symbol}:{start}:{end}:{limit}`
- `financial_summary:{symbol}:{report_period_or_latest}`

---

## 9. 错误处理规则

## 9.1 禁止原始异常直出

禁止把以下信息直接返回给前端 API：

- 原始 traceback
- 第三方 HTTP 底层异常原文
- 非结构化 provider 错误字符串

## 9.2 推荐错误分层

- `InvalidSymbolError`
- `ProviderUnavailableError`
- `ProviderDataEmptyError`
- `ProviderDataStaleError`
- `ProviderContractError`

## 9.3 局部失败原则

- 单只股票失败：可跳过，不应让全市场扫描整体失败。
- 单个 provider 失败：应尝试切换或降级。
- 正式披露源失败：应明确标记，而不是 silently pretend success。

---

## 10. 当前项目建议的落地优先级

### 10.1 第一优先级

1. `tdx-api` provider 正式接入
2. `normalize.py` 补齐所有 provider symbol/date/unit 映射
3. `tdx-api` 与现有 daily bars / universe / search 能力对接
4. 为 `mootdx` 增加 freshness 与 contract test

### 10.2 第二优先级

1. `AKShare` 本地落袋层
2. `CNINFO` 公告索引稳定化
3. `BaoStock` 作为日线与股票池兜底源标准化

### 10.3 第三优先级

1. `mootdx` 财务下载能力评估
2. `tdx-api` 分时成交与全量历史 K 线进入因子研究链
3. 更细的 provider quality scoring

---

## 11. 建议写入项目的硬规则

建议把下面这些规则同步写进项目 AGENTS.md 或 `docs/current-phase.md`：

1. **凡是 tdx-api 能稳定提供的数据，优先走 tdx-api。**
2. **凡是 mootdx 本地文件能提供且 freshness 合格的数据，优先用于批量历史读取。**
3. **AKShare 一律按高频限制源处理，必须本地落袋。**
4. **公告与正式披露以 CNINFO 为准。**
5. **所有 provider 都必须经过统一标准化层。**
6. **任何数据源切换都必须保留 source 与 adjustment metadata。**

---

## 12. 当前推荐的项目内 provider 顺序（可直接作为实现备注）

### 股票池 / 搜索

- `tdx-api` → `BaoStock` → `AKShare`

### 日线 / 周线 / 月线

- `tdx-api` → `mootdx(local)` → `BaoStock` → `AKShare`

### 分钟 / 时间线 / 分时成交

- `tdx-api` → `mootdx(local)` → `BaoStock`

### 公告

- `CNINFO` → `AKShare`

### 财务摘要

- `AKShare` → `BaoStock`

---

## 13. 结论

本项目当前最重要的数据源策略，不是“接更多源”，而是：

- **把 tdx-api 真正接成主链**
- **把 mootdx 真正接成高速本地历史源**
- **把 AKShare 约束成低频补充源并强制落袋**
- **把 CNINFO 固定成正式披露真相源**
- **把 BaoStock 固定成稳定兜底源**

只要这五层关系理顺，后面的研究、策略、选股和因子系统才会稳定。
