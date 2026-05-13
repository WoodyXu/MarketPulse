# 大A成交金额与沪深300点位绘图脚本产品设计文档

## 1. 项目背景

本项目旨在开发一个 Python 脚本，用于绘制自指定起始日期以来的：

1. 每日沪深两市股票合计成交金额；
2. 当日沪深300收盘点位。

脚本需要优先使用本地数据库中的历史数据；如果某一交易日数据缺失，则从 AKShare 数据源拉取并写入本地数据库。最终输出一张折线图，保存到 `pics/` 目录下。

---

## 2. 产品目标

### 2.1 核心目标

构建一个可重复运行的本地数据更新与绘图脚本，实现：

- 自动读取起始日期；
- 自动识别可获取数据的最新交易日；
- 自动补齐缺失的交易日数据；
- 优先从本地 SQLite 数据库读取已有数据；
- 对最近 3 个交易日允许自动重刷；
- 生成沪深两市股票合计成交金额与沪深300收盘点位的双轴折线图；
- 在图片右侧标注最后一个有效日期、当日成交金额、沪深300点位；
- 将图片保存到 `pics/` 目录下。

### 2.2 非目标

第一版暂不实现以下能力：

- 不做实时盘中成交额展示；
- 不做交互式图表；
- 不接入 Web 服务或 Dashboard；
- 不做定时任务调度；
- 不做多指数对比；
- 不统计 ETF、基金、债券、期权等非股票品种；
- 不将功能拆分到多个业务模块文件中。

---

## 3. 已确认需求

| 需求项 | 确认口径 |
|---|---|
| 成交金额统计范围 | 只统计股票成交金额 |
| 成交金额数据源 | 沪市：`akshare.stock_sse_deal_daily`；深市：`akshare.stock_szse_summary` |
| 沪深300数据源 | 主用 `akshare.stock_zh_index_daily`；备选 `akshare.stock_zh_index_daily_tx` |
| 沪深300指数代码 | 从 `config/index_code.py` 中读取 |
| 起始日期 | 使用 `config/consts.py` 中的 `START_DATE` |
| 起始边界 | 程序自动取 `START_DATE` 与数据源可用最早日期中的较晚者 |
| 数据库金额单位 | 统一存储为“元” |
| 图表金额单位 | 绘图时转换为“亿元” |
| 数据库缓存策略 | 如果数据已存在，优先从数据库查询 |
| 最近数据刷新 | 最近 3 个交易日允许自动重刷 |
| 强制刷新 | 预留 `--force-refresh` 参数 |
| 数据完整性 | 允许部分字段为空，并标记状态 |
| 绘图有效日期 | 取沪市成交额、深市成交额、沪深300收盘点位三项数据都存在的最后一个有效日期 |
| 图上展示线条 | 只画沪深合计成交金额和沪深300收盘点位 |
| 绘图库 | `matplotlib` |
| 图片保存目录 | `pics/` |
| 图片文件名 | `大A成交金额_{日期}.png` |
| 日期格式 | 图片注释和文件名均使用 `YYYY-MM-DD` |
| 右侧文字标注 | 三行：日期、成交金额、沪深300点位 |
| 代码组织方式 | `src/plot_market_turnover.py` |
| 配置文件变更原则 | `consts.py` 和 `index_code.py` 中已有变量不变更、不删除；如有需要，仅新增变量 |

---

## 4. 项目目录结构

项目目录结构如下：

```text
project_root/
├── config/
│   ├── __init__.py
│   ├── consts.py
│   └── index_code.py
├── data/
│   └── market_data.sqlite
├── pics/
│   └── 大A成交金额_2026-05-07.png
├── src/
│   ├── plot_market_turnover.py
└── design-document.md
```

说明：

1. `config/consts.py`：存放项目级配置，例如 `START_DATE`、数据库路径、图片输出目录等。
2. `config/index_code.py`：存放指数代码，例如沪深300指数代码。
3. `data/market_data.sqlite`：本地 SQLite 数据库文件。
4. `pics/`：图片输出目录。
5. `src/plot_market_turnover.py`：主程序文件，包含数据库、数据拉取、数据更新、绘图、命令行入口等全部核心逻辑。
6. `design-document.md`：当前产品设计文档。

---

## 5. 配置文件设计

### 5.1 `config/consts.py`

`consts.py` 中已有变量不需要变更或删除。

如项目需要新增配置，只新增变量，不改动已有变量。

建议新增变量：

```python
DB_PATH = "data/market_data.sqlite"
DEFAULT_OUTPUT_DIR = "pics"
RECENT_REFRESH_DAYS = 3
```

字段说明：

| 变量 | 含义 |
|---|---|
| `START_DATE` | 数据起始日期，已存在则直接使用 |
| `DB_PATH` | SQLite 数据库路径 |
| `DEFAULT_OUTPUT_DIR` | 图片默认输出目录 |
| `RECENT_REFRESH_DAYS` | 最近允许自动重刷的交易日数量，默认 3 |

注意：

- 不在 `consts.py` 中新增或维护指数代码；
- 指数代码统一从 `config/index_code.py` 中读取。

### 5.2 `config/index_code.py`

`index_code.py` 中已有变量不需要变更或删除。

如文件中已经存在沪深300指数代码变量，则直接使用已有变量。

---

## 6. 数据源设计

### 6.1 沪市股票成交金额

使用 AKShare：

```python
akshare.stock_sse_deal_daily(date="YYYYMMDD")
```

数据处理逻辑：

1. 按日期逐日请求；
2. 仅提取股票相关成交金额；
3. 将成交金额转换为“元”后入库；
4. 如果接口无数据、非交易日、字段缺失，则该日沪市成交额记为 `NULL`。

注意：

- 该接口存在数据可用起始边界；
- 若 `START_DATE` 早于接口可用最早日期，程序应自动使用可用最早日期，并打印 warning；
- 沪市成交金额最终入库单位必须统一为“元”。

### 6.2 深市股票成交金额

使用 AKShare：

```python
akshare.stock_szse_summary(date="YYYYMMDD")
```

数据处理逻辑：

1. 按日期逐日请求；
2. 仅提取股票类别的成交金额；
3. 字段单位统一转换为“元”；
4. 如果接口无数据、非交易日、字段缺失，则该日深市成交额记为 `NULL`。

### 6.3 沪深300收盘点位

主数据源：

```python
akshare.stock_zh_index_daily(symbol="sh000300")
```

备选数据源：

```python
akshare.stock_zh_index_daily_tx(symbol="sh000300")
```

实际指数代码从：

```python
config/index_code.py
```

中读取。

数据处理逻辑：

1. 一次性拉取沪深300历史日线数据；
2. 取 `date` 和 `close` 字段；
3. 用指数行情返回的最新日期辅助判断当前可获取的最新交易日；
4. 若主数据源失败，则切换到备选数据源；
5. 入库字段为 `hs300_close`。

---

## 7. 本地数据库设计

### 7.1 数据库类型

使用 SQLite。

默认数据库路径：

```text
data/market_data.sqlite
```

路径优先从 `config/consts.py` 中读取：

```python
DB_PATH = "data/market_data.sqlite"
```

如果 `DB_PATH` 未配置，则程序使用默认值：

```text
data/market_data.sqlite
```

### 7.2 主表：`daily_market_data`

表名：

```sql
daily_market_data
```

建表语句建议如下：

```sql
CREATE TABLE IF NOT EXISTS daily_market_data (
    trade_date TEXT PRIMARY KEY,

    sse_amount_yuan REAL,
    szse_amount_yuan REAL,
    total_amount_yuan REAL,
    hs300_close REAL,

    data_status TEXT NOT NULL DEFAULT 'partial',

    sse_updated_at TEXT,
    szse_updated_at TEXT,
    hs300_updated_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 7.3 字段说明

| 字段 | 类型 | 含义 |
|---|---:|---|
| `trade_date` | TEXT | 交易日期，格式为 `YYYY-MM-DD` |
| `sse_amount_yuan` | REAL | 沪市股票成交金额，单位：元 |
| `szse_amount_yuan` | REAL | 深市股票成交金额，单位：元 |
| `total_amount_yuan` | REAL | 沪深股票合计成交金额，单位：元 |
| `hs300_close` | REAL | 沪深300收盘点位 |
| `data_status` | TEXT | 数据状态：`complete` 或 `partial` |
| `sse_updated_at` | TEXT | 沪市成交额最近更新时间 |
| `szse_updated_at` | TEXT | 深市成交额最近更新时间 |
| `hs300_updated_at` | TEXT | 沪深300数据最近更新时间 |
| `created_at` | TEXT | 记录创建时间 |
| `updated_at` | TEXT | 记录最近更新时间 |

### 7.4 数据状态规则

当以下三个字段均不为空时：

- `sse_amount_yuan`
- `szse_amount_yuan`
- `hs300_close`

则：

```text
data_status = complete
```

否则：

```text
data_status = partial
```

`total_amount_yuan` 的计算规则：

```text
total_amount_yuan = sse_amount_yuan + szse_amount_yuan
```

仅当沪市和深市成交额均存在时，才计算 `total_amount_yuan`。

否则：

```text
total_amount_yuan = NULL
```

---

## 8. 日期与交易日处理逻辑

### 8.1 起始日期

从 `config/consts.py` 中读取：

```python
START_DATE
```

程序实际使用的起始日期为：

```text
effective_start_date = max(START_DATE, 数据源可用最早日期)
```

如果 `START_DATE` 早于数据源可用最早日期，需要输出 warning，例如：

```text
START_DATE 早于数据源可用最早日期，已自动从 YYYY-MM-DD 开始。
```

### 8.2 最新可用交易日

数据库更新时，分别尽可能拉取最新数据。

最终绘图时不直接使用程序运行当天，而是从数据库中筛选：

```sql
SELECT MAX(trade_date)
FROM daily_market_data
WHERE sse_amount_yuan IS NOT NULL
  AND szse_amount_yuan IS NOT NULL
  AND total_amount_yuan IS NOT NULL
  AND hs300_close IS NOT NULL;
```

该日期作为：

```text
last_valid_date
```

最终图片文件名和右侧文字注释均使用该日期。

### 8.3 非交易日处理

由于沪市、深市接口按日期请求，遇到周末、节假日或无数据日期时：

- 不强制写入完整记录；
- 可跳过；
- 若已有指数日期作为交易日基准，但成交额未获取到，则允许写入 `partial`；
- 最终绘图仅使用 `complete` 数据。

---

## 9. 数据更新策略

### 9.1 基本原则

对于每个日期：

1. 先查询本地数据库；
2. 如果数据完整且不属于最近 3 个交易日，则直接使用本地数据；
3. 如果数据缺失、数据不完整，或属于最近 3 个交易日，则尝试从 AKShare 更新；
4. 更新后重新计算 `total_amount_yuan` 和 `data_status`。

### 9.2 最近 3 个交易日重刷

最近 3 个交易日允许自动重刷，原因：

- 当日数据可能存在延迟；
- 部分交易所接口可能晚于指数行情更新；
- 数据源可能出现短暂缺失或修正。

实现建议：

1. 从沪深300历史行情中获取最近 N 个交易日；
2. 默认 `N = 3`；
3. 对这 3 个交易日，即使数据库已有数据，也允许重新请求数据源；
4. 成功获取后覆盖更新；
5. 获取失败时保留数据库已有数据，不删除旧数据。

### 9.3 强制刷新参数

预留命令行参数：

```bash
python src/plot_market_turnover.py --force-refresh
```

开启后：

- 忽略本地数据库命中；
- 在指定日期范围内重新拉取数据；
- 成功拉取的数据覆盖旧数据；
- 失败日期保留原数据或标记为 `partial`，具体以实现中的安全策略为准。

### 9.4 建议命令行参数

默认运行：

```bash
python src/plot_market_turnover.py
```

可选参数：

```bash
python src/plot_market_turnover.py --force-refresh
python src/plot_market_turnover.py --start-date 2024-01-01
python src/plot_market_turnover.py --output-dir pics
```

说明：

| 参数 | 含义 |
|---|---|
| `--force-refresh` | 强制刷新指定范围内数据 |
| `--start-date` | 临时覆盖 `config/consts.py` 中的 `START_DATE` |
| `--output-dir` | 临时覆盖图片输出目录，默认 `pics/` |

---

## 10. 绘图设计

### 10.1 图表类型

使用 `matplotlib` 绘制双轴折线图：

- 左轴：沪深合计成交金额，单位为“亿元”；
- 右轴：沪深300收盘点位。

### 10.2 数据筛选

仅使用完整数据：

```sql
SELECT trade_date, total_amount_yuan, hs300_close
FROM daily_market_data
WHERE total_amount_yuan IS NOT NULL
  AND hs300_close IS NOT NULL
  AND data_status = 'complete'
ORDER BY trade_date;
```

绘图前转换：

```text
total_amount_100m = total_amount_yuan / 100000000
```

### 10.3 图上线条

图中只绘制两条线：

1. `沪深合计成交金额`
2. `沪深300收盘点位`

不单独绘制沪市成交额和深市成交额。

### 10.4 右侧文字标注

在图表最右端点旁边添加三行文字。

格式：

```text
2026-05-07
成交金额：12345.67亿元
沪深300：3650.28
```

其中：

- 第一行：最后一个有效日期，格式 `YYYY-MM-DD`；
- 第二行：最后一个有效日期对应的沪深合计成交金额，单位“亿元”，保留两位小数；
- 第三行：最后一个有效日期对应的沪深300收盘点位，保留两位小数。

### 10.5 标注位置

标注应放在最右端点旁边的合适位置。

建议实现：

- 横坐标向右偏移少量距离；
- 使用 `annotate` 或 `text`；
- 为右侧标注预留图表边距；
- 避免文字超出画布；
- 若成交金额和指数右轴高度差异较大，可将标注放在图表右上角或使用相对坐标定位。

推荐方案：

```python
ax1.text(
    1.01,
    0.95,
    label_text,
    transform=ax1.transAxes,
    va="top",
    ha="left"
)
```

同时调整：

```python
plt.subplots_adjust(right=0.78)
```

这样右侧有足够空间展示标注。

### 10.6 图片输出

保存目录：

```text
pics/
```

文件名格式：

```text
大A成交金额_{last_valid_date}.png
```

示例：

```text
pics/大A成交金额_2026-05-07.png
```

如果目录不存在，程序需要自动创建：

```python
Path("pics").mkdir(parents=True, exist_ok=True)
```

---

## 11. 单文件实现设计

### 11.1 实现原则

第一版将以下功能统一放到：

```text
src/plot_market_turnover.py
```

中实现：

- 数据库初始化；
- 数据库读写；
- AKShare 数据拉取；
- 数据清洗；
- 单位转换；
- 数据更新；
- 最近 3 个交易日重刷；
- 强制刷新；
- 绘图；
- 图片保存；
- 命令行参数解析；
- 日志输出。

### 11.2 `src/plot_market_turnover.py` 职责

`src/plot_market_turnover.py` 是第一版唯一核心业务脚本。

职责包括：

1. 读取配置；
2. 初始化数据库；
3. 创建数据表；
4. 获取沪深300历史行情；
5. 获取沪市股票成交金额；
6. 获取深市股票成交金额；
7. 判断哪些日期需要更新；
8. 写入或更新 SQLite 数据；
9. 查询完整数据；
10. 绘制双轴折线图；
11. 添加右侧三行文字；
12. 保存图片；
13. 输出日志。

### 11.3 建议函数清单

虽然功能放在一个文件中，但仍建议用函数组织代码，避免全部写在主流程里。

建议函数如下：

```python
def parse_args():
    pass
```

职责：

- 解析命令行参数；
- 支持 `--force-refresh`、`--start-date`、`--output-dir`。

---

```python
def setup_logging():
    pass
```

职责：

- 初始化日志格式；
- 设置日志级别。

---

```python
def get_config(args):
    pass
```

职责：

- 从 `config/consts.py` 读取 `START_DATE`；
- 从 `config/consts.py` 读取或设置默认 `DB_PATH`；
- 从 `config/consts.py` 读取或设置默认 `DEFAULT_OUTPUT_DIR`；
- 从 `config/consts.py` 读取或设置默认 `RECENT_REFRESH_DAYS`；
- 从 `config/index_code.py` 读取沪深300指数代码；
- 命令行参数优先级高于配置文件。

---

```python
def init_db(db_path: str) -> None:
    pass
```

职责：

- 创建 `data/` 目录；
- 连接 SQLite；
- 创建 `daily_market_data` 表。

---

```python
def get_daily_record(conn, trade_date: str) -> dict | None:
    pass
```

职责：

- 从数据库中查询单个交易日数据。

---

```python
def upsert_daily_record(conn, record: dict) -> None:
    pass
```

职责：

- 插入或更新单日数据；
- 维护 `created_at` 和 `updated_at`；
- 维护各数据源更新时间字段。

---

```python
def fetch_hs300_daily(index_code: str) -> list[dict]:
    pass
```

职责：

- 调用 `akshare.stock_zh_index_daily` 获取沪深300数据；
- 主数据源失败时，调用 `akshare.stock_zh_index_daily_tx`；
- 返回标准化后的日期和收盘点位列表。

返回示例：

```python
[
    {
        "trade_date": "2026-05-07",
        "hs300_close": 3650.28
    }
]
```

---

```python
def fetch_sse_stock_amount(trade_date: str) -> float | None:
    pass
```

职责：

- 调用 `akshare.stock_sse_deal_daily`；
- 提取沪市股票成交金额；
- 转换为“元”；
- 失败或无数据时返回 `None`。

---

```python
def fetch_szse_stock_amount(trade_date: str) -> float | None:
    pass
```

职责：

- 调用 `akshare.stock_szse_summary`；
- 提取深市股票成交金额；
- 转换为“元”；
- 失败或无数据时返回 `None`。

---

```python
def calculate_data_status(sse_amount_yuan, szse_amount_yuan, hs300_close) -> str:
    pass
```

职责：

- 判断数据完整性；
- 返回 `complete` 或 `partial`。

---

```python
def should_refresh(trade_date, record, recent_trade_dates, force_refresh: bool) -> bool:
    pass
```

职责：

- 判断某一交易日是否需要重新拉取数据。

规则：

```text
如果 force_refresh=True，则刷新；
如果数据库没有该日记录，则刷新；
如果记录不是 complete，则刷新；
如果该日属于最近 3 个交易日，则刷新；
其他情况不刷新。
```

---

```python
def update_market_data(
    conn,
    start_date: str,
    index_code: str,
    force_refresh: bool,
    recent_refresh_days: int,
) -> None:
    pass
```

职责：

- 获取沪深300历史行情；
- 确定有效起始日期；
- 确定需要处理的交易日列表；
- 判断哪些日期需要刷新；
- 拉取沪市、深市、沪深300数据；
- 写入数据库。

---

```python
def get_complete_market_data(conn, start_date: str) -> list[dict]:
    pass
```

职责：

- 从数据库查询完整数据；
- 返回绘图所需数据。

---

```python
def plot_market_turnover_and_hs300(data: list[dict], output_dir: str) -> Path:
    pass
```

职责：

- 将成交金额从“元”转换为“亿元”；
- 绘制沪深合计成交金额；
- 绘制沪深300收盘点位；
- 添加右侧三行文字；
- 保存图片到 `pics/` 目录；
- 返回图片路径。

---

```python
def main():
    pass
```

职责：

- 组织完整流程；
- 作为脚本入口。

---

## 12. 核心流程设计

### 12.1 主流程

```text
开始
  ↓
解析命令行参数
  ↓
读取 config/consts.py 中的 START_DATE、DB_PATH、DEFAULT_OUTPUT_DIR、RECENT_REFRESH_DAYS
  ↓
读取 config/index_code.py 中的沪深300指数代码
  ↓
初始化 SQLite 数据库
  ↓
拉取沪深300历史行情，确定可用交易日列表和最新指数日期
  ↓
根据 START_DATE 和数据源可用起始日期确定 effective_start_date
  ↓
遍历 effective_start_date 至最新指数日期之间的交易日
  ↓
对每个交易日判断是否需要刷新
  ↓
需要刷新则分别拉取：
    - 沪市股票成交金额
    - 深市股票成交金额
    - 沪深300收盘点位
  ↓
写入或更新数据库
  ↓
从数据库查询 complete 数据
  ↓
取最后一个有效日期
  ↓
绘制双轴折线图
  ↓
添加右侧三行文字说明
  ↓
保存到 pics/大A成交金额_{last_valid_date}.png
  ↓
打印图片路径
  ↓
结束
```

### 12.2 是否刷新单日数据的判断逻辑

伪代码：

```python
def should_refresh(trade_date, record, recent_trade_dates, force_refresh):
    if force_refresh:
        return True

    if record is None:
        return True

    if record["data_status"] != "complete":
        return True

    if trade_date in recent_trade_dates:
        return True

    return False
```

### 12.3 单日数据更新逻辑

伪代码：

```python
def update_one_day(trade_date):
    sse_amount = fetch_sse_stock_amount(trade_date)
    szse_amount = fetch_szse_stock_amount(trade_date)
    hs300_close = get_hs300_close_from_cached_index_data(trade_date)

    if sse_amount is not None and szse_amount is not None:
        total_amount = sse_amount + szse_amount
    else:
        total_amount = None

    if sse_amount is not None and szse_amount is not None and hs300_close is not None:
        data_status = "complete"
    else:
        data_status = "partial"

    upsert_daily_record({
        "trade_date": trade_date,
        "sse_amount_yuan": sse_amount,
        "szse_amount_yuan": szse_amount,
        "total_amount_yuan": total_amount,
        "hs300_close": hs300_close,
        "data_status": data_status,
    })
```

---

## 13. 数据清洗与单位转换

### 13.1 沪市成交金额

要求：

- 只取股票成交金额；
- 最终入库单位为“元”。

如果 AKShare 返回字段单位为“亿元”，则转换：

```text
sse_amount_yuan = sse_amount_100m * 100000000
```

如果接口实际返回已为“元”，则不转换。

实现时必须根据 AKShare 返回字段和接口说明进行一次显式校验，并在代码中用注释说明转换依据。

### 13.2 深市成交金额

要求：

- 只取股票成交金额；
- 最终入库单位为“元”。

如果 AKShare 返回字段单位为“元”，则：

```text
szse_amount_yuan = szse_amount
```

### 13.3 合计成交金额

计算规则：

```text
total_amount_yuan = sse_amount_yuan + szse_amount_yuan
```

前提：

- `sse_amount_yuan` 不为空；
- `szse_amount_yuan` 不为空。

如任一字段为空：

```text
total_amount_yuan = NULL
```

### 13.4 绘图单位

绘图时将合计成交金额转换为“亿元”：

```text
total_amount_100m = total_amount_yuan / 100000000
```

右侧文字展示：

```text
成交金额：{total_amount_100m:.2f}亿元
```

沪深300展示：

```text
沪深300：{hs300_close:.2f}
```

---

## 14. 异常处理设计

### 14.1 AKShare 接口失败

如果某个接口请求失败：

- 捕获异常；
- 打印 warning；
- 不终止整个程序；
- 该字段写入 `NULL` 或保留旧值；
- 当前日期状态标记为 `partial`。

### 14.2 单日部分数据缺失

例如：

- 沪深300有数据；
- 沪市成交额缺失；
- 深市成交额正常。

处理方式：

- 允许入库；
- 缺失字段为 `NULL`；
- `data_status = partial`；
- 不参与最终绘图。

### 14.3 无完整数据

如果数据库中没有任何完整记录：

程序应报错并退出：

```text
未找到可用于绘图的完整数据，请检查数据源或起始日期配置。
```

### 14.4 图片保存失败

如果 `pics/` 目录无法创建或图片保存失败：

- 抛出明确异常；
- 输出失败路径；
- 提示检查目录权限。

---

## 15. 日志设计

使用 Python 标准库 `logging`。

日志级别建议：

| 级别 | 使用场景 |
|---|---|
| `INFO` | 程序开始、结束、更新日期范围、图片保存路径 |
| `WARNING` | 某日数据缺失、接口无数据、起始日期被自动调整 |
| `ERROR` | 数据库初始化失败、无完整数据、图片保存失败 |

示例日志：

```text
INFO - 初始化数据库：data/market_data.sqlite
INFO - 数据更新范围：2021-12-27 至 2026-05-07
WARNING - 2026-05-07 深市成交额暂未获取到，已标记为 partial
INFO - 最后有效日期：2026-05-06
INFO - 图片已保存：pics/大A成交金额_2026-05-06.png
```

---

## 16. 验收标准

### 16.1 数据库验收

运行脚本后，应满足：

- 自动创建 `data/market_data.sqlite`；
- 自动创建 `daily_market_data` 表；
- 表中包含从有效起始日期开始的交易日数据；
- 成交金额统一以“元”为单位存储；
- `total_amount_yuan` 等于 `sse_amount_yuan + szse_amount_yuan`；
- 完整数据记录的 `data_status = complete`；
- 缺失数据记录的 `data_status = partial`；
- 最近 3 个交易日允许重新刷新。

### 16.2 绘图验收

运行脚本后，应满足：

- 自动创建 `pics/` 目录；
- 生成 PNG 图片；
- 文件名格式为 `大A成交金额_{YYYY-MM-DD}.png`；
- 文件名日期等于图表最后一个有效日期；
- 图中只包含两条线：
  - 沪深合计成交金额；
  - 沪深300收盘点位；
- 左轴为成交金额，单位“亿元”；
- 右轴为沪深300点位；
- 图片右侧包含三行文字：
  - `YYYY-MM-DD`
  - `成交金额：12345.67亿元`
  - `沪深300：3650.28`

### 16.3 缓存验收

重复运行脚本时，应满足：

- 历史完整数据优先使用本地数据库；
- 最近 3 个交易日允许自动重刷；
- 若数据源失败，不应删除已有有效数据；
- 程序不因单日失败而整体中断。

### 16.4 代码组织验收

第一版代码组织应满足：

- 核心功能统一实现在 `src/plot_market_turnover.py`；
=- `config/consts.py` 中已有变量不变更、不删除；
- `config/index_code.py` 中已有变量不变更、不删除；
- 如需增加配置，仅新增变量。

---

## 17. 测试用例设计

### 17.1 首次运行

条件：

- 本地无数据库；
- `pics/` 目录不存在。

预期：

- 自动创建数据库；
- 自动创建数据表；
- 自动拉取数据；
- 自动创建 `pics/`；
- 成功输出图片。

### 17.2 重复运行

条件：

- 数据库已有完整历史数据。

预期：

- 大部分历史日期直接使用本地缓存；
- 最近 3 个交易日尝试重新拉取；
- 成功输出最新图片。

### 17.3 起始日期早于数据源可用日期

条件：

- `START_DATE` 早于数据源可用最早日期。

预期：

- 程序自动调整起始日期；
- 输出 warning；
- 不报错中断。

### 17.4 某日部分数据缺失

条件：

- 某日沪市、深市或沪深300任一字段缺失。

预期：

- 该日允许入库；
- `data_status = partial`；
- 不参与最终绘图。

### 17.5 强制刷新

条件：

- 使用参数：

```bash
python src/plot_market_turnover.py --force-refresh
```

预期：

- 指定范围内数据重新请求；
- 成功数据覆盖旧数据；
- 失败数据不影响已有完整历史数据。

### 17.6 配置文件保护

条件：

- `config/consts.py` 和 `config/index_code.py` 中已经存在多个变量。

预期：

- 实现代码不得删除已有变量；
- 实现代码不得重命名已有变量；
- 实现代码不得强行修改已有变量值；
- 如需新增配置，只能新增变量。

---

## 18. 后续可扩展能力

后续可考虑扩展：

1. 增加成交金额移动平均线；
2. 增加成交金额与沪深300的相关性分析；
3. 增加万亿成交额阈值线；
4. 增加成交金额分位数背景区间；
5. 输出 HTML 交互式图表；
6. 支持中证500、创业板指、上证指数等其他指数；
7. 增加定时任务；
8. 增加数据源健康检查；
9. 增加 CSV 导出；
10. 增加历史数据回补报告；
11. 后续如代码复杂度提升，可再将 `plot_market_turnover.py` 拆分为多个模块。

---

## 19. 第一版实现优先级

### P0：必须实现

- SQLite 数据库；
- AKShare 数据拉取；
- 沪市股票成交金额；
- 深市股票成交金额；
- 沪深300收盘点位；
- 本地缓存优先；
- 最近 3 个交易日重刷；
- `partial` / `complete` 状态；
- Matplotlib 双轴图；
- 图片右侧三行文字；
- 保存到 `pics/大A成交金额_{日期}.png`；
- 所有核心业务逻辑统一放到 `src/plot_market_turnover.py`。

### P1：建议实现

- `--force-refresh`；
- `--start-date`；
- `--output-dir`；
- 更完整日志；
- 主数据源失败后自动切换备选指数数据源；
- 配置项缺失时提供合理默认值。

### P2：后续扩展

- 交互图；
- 多指数；
- 分位数分析；
- 定时运行；
- 数据质量报告；
- 多文件模块化拆分。

---

## 20. 最终交付物

第一版建议交付以下文件：

```text
design-document.md
src/plot_market_turnover.py
```

同时项目中保留以下目录和文件：

```text
config/
config/consts.py
config/index_code.py
data/
pics/
src/
```

其中：

- `design-document.md` 用作后续编码实现的需求与设计依据；
- `src/plot_market_turnover.py` 是第一版唯一核心业务实现文件。