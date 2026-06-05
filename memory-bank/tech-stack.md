# MarketPulse 微信小程序技术栈建议

## 1. 选型结论

推荐使用“微信原生小程序 + 微信云开发 + ECharts for 微信 + 现有 Python 数据流水线”的技术栈。

这个组合最适合当前项目：功能范围清晰、页面数量少、数据只读、图表为核心、后端逻辑轻，且需要尽量复用现有 Python 和 HTML payload 能力。它不引入跨端框架和额外服务端框架，简单但足够健壮。

## 2. 推荐技术栈

| 层级 | 推荐技术 | 用途 |
|---|---|---|
| 小程序前端 | 微信原生小程序 | 页面、路由、登录、分享、缓存、下拉刷新 |
| 图表 | ECharts for 微信 `ec-canvas` | 折线图、双轴图、参考线、tooltip |
| 后端 | 微信云开发云函数 Node.js | 登录态校验、读取云存储 JSON、按 section 裁剪返回 |
| 文件存储 | 微信云存储 | 保存本地 Python 上传的 dashboard JSON |
| 数据生成 | 现有 Python 脚本 | 继续生成 SQLite 数据和 dashboard payload |
| 上传脚本 | Python 标准库 + 云开发/腾讯云上传能力 | 将 payload JSON 上传到云存储 |
| 本地数据库 | SQLite | 沿用当前数据存储 |
| 测试 | pytest + 云函数轻量测试 + 微信开发者工具手工验收 | 验证 payload、section 裁剪和页面表现 |

## 3. 小程序前端

### 3.1 框架

使用微信原生小程序，不使用 Taro、uni-app、React 或 Vue 封装层。

理由：

- 当前只需要微信小程序单端，不需要跨端。
- 页面结构简单：总览首页、资本市场看板、北京楼市看板。
- 原生能力覆盖登录、分享、缓存、下拉刷新和云函数调用。
- 少一层构建链路，后续维护和调试更直接。
- 小程序审核和运行时行为更可控。

### 3.2 页面组织

建议页面：

```text
miniprogram/pages/
├── home/index
├── ashare/index
└── beijing/index
```

资本市场和北京楼市的子 tab 不建议拆成独立页面，第一版可在同一页面内用组件或模块函数渲染。这样路由更简单，section 缓存和下拉刷新也更容易管理。

### 3.3 状态管理

不引入 Redux、MobX 或第三方状态库。

使用页面级 `data` 和少量 `utils/request.js`、`utils/cache.js` 即可：

- 当前 tab。
- 当前 section 加载状态。
- 当前 section 数据。
- section 级缓存。
- 错误态与重试状态。

## 4. 图表方案

### 4.1 推荐

使用 ECharts for 微信 `ec-canvas`。

理由：

- 能覆盖折线图、双 Y 轴、markLine、markPoint、tooltip。
- 与现有网页图表语义容易对齐。
- 微信小程序生态成熟，风险低。
- 比手写 canvas/SVG 更稳，也更容易维护。

### 4.2 使用方式

建议集中维护图表 option 构造函数：

```text
miniprogram/utils/echarts-option.js
```

职责：

- 将 section 数据转换为 ECharts option。
- 统一颜色、坐标轴、tooltip、数值格式。
- 统一参考线、最新点、百分比和金额格式。

不建议在页面 JS 中直接拼复杂 option，避免页面逻辑和图表细节混在一起。

## 5. 云函数与数据访问

### 5.1 云函数

推荐云函数名称：

```text
getDashboardSection
```

运行时：

```text
Node.js
```

职责：

- 校验用户登录态。
- 接收 `type` 和 `section` 参数。
- 从云存储读取对应 dashboard JSON。
- 按当前 tab 裁剪 section 数据。
- 返回裁剪后的 JSON。
- 不返回完整 dashboard payload。
- 不返回云存储 `fileID` 或可直接下载 JSON 的信息。

### 5.2 请求协议

请求参数建议：

```json
{
  "type": "ashare",
  "section": "turnover"
}
```

返回结构建议：

```json
{
  "type": "ashare",
  "section": "turnover",
  "data": {}
}
```

对于一个 tab 需要多个字段的情况，`data` 可以返回组合对象。例如北京楼市“网签量”：

```json
{
  "type": "beijing",
  "section": "onlineSignings",
  "data": {
    "dailyOnlineSignings": [],
    "monthlyOnlineSignings": []
  }
}
```

### 5.3 Section 映射

建议在云函数内维护白名单映射，不允许客户端传任意字段名直接读取。

```text
ashare.indexDeviation      -> payload.indexDeviation
ashare.margin              -> payload.margin
ashare.turnover            -> payload.turnover
ashare.topConcentration    -> payload.topConcentration
beijing.houseViewPeople    -> payload.houseViewPeopleByWeekday
beijing.decreaseRatio      -> payload.decreaseRatio
beijing.lianjiaDeals       -> payload.lianjiaDealsByWeekday
beijing.onlineSignings     -> payload.dailyOnlineSignings + payload.monthlyOnlineSignings
beijing.credit             -> payload.creditYoy + payload.loanNetIncreaseByMonth + payload.totalLoanNetIncreaseByMonth
```

## 6. 云存储

使用微信云存储保存 Python 上传的 JSON 文件。

文件命名建议：

```text
marketpulse-payload/ashare_YYYY-MM-DD.json
marketpulse-payload/beijing_YYYY-MM-DD.json
```

权限要求：

- JSON 文件不公开。
- 小程序端不直接拿 `fileID`。
- 小程序端不直接调用云存储下载 JSON。
- 只允许云函数读取 JSON 文件。
- 云函数返回前必须做 section 裁剪。

## 7. 数据生成与上传

### 7.1 保留现有 Python

继续使用现有脚本：

```text
src/security_market_pulse.py
src/beijing_real_estate_market_pulse.py
```

原则：

- 不修改当前 HTML 生成行为。
- 不迁移 Python 数据处理到云函数。
- 不改变现有 SQLite 数据库作为本地数据源的定位。

### 7.2 新增上传脚本

新增：

```text
api/upload_payload.py
```

职责：

- 复用两个 `build_dashboard_payload()`。
- 生成 `ashare` 和 `beijing` JSON。
- 上传到微信云存储固定目录。
- 不影响现有 HTML 生成流程。

建议参数：

```text
--env-id
--start-date
--date
--db-path
```

## 8. 缓存策略

小程序端按 section 缓存，不缓存整包 dashboard payload。

缓存 key 建议：

```text
marketpulse:{type}:{section}
```

缓存内容：

```json
{
  "cachedAt": 1780590000000,
  "type": "ashare",
  "section": "turnover",
  "data": {}
}
```

建议缓存有效期：

```text
24 小时
```

策略：

- 首次进入 tab：请求云函数。
- 请求成功：写入 section 缓存。
- 切换回已加载 tab：优先使用内存数据。
- 网络失败：尝试读取有效缓存。
- 无缓存：展示错误态和重试入口。

## 9. 登录与分享

### 9.1 登录

使用微信原生登录能力和云开发登录态。

第一版只做身份识别：

- 不做角色区分。
- 不做数据权限控制。
- 不做私有名单。

云函数应检查调用上下文中的用户身份，避免完全匿名访问。

### 9.2 分享

使用原生 `onShareAppMessage`。

推荐分享路径：

```text
/pages/home/index
/pages/ashare/index
/pages/beijing/index
```

第一版分享到看板页即可，不必分享到具体子 tab。后续可以通过 query 参数支持分享到指定 section。

## 10. 工程与依赖

### 10.1 依赖控制

建议只引入：

- ECharts for 微信。
- 微信云开发 SDK。
- Python 侧沿用现有依赖。

不建议引入：

- Taro、uni-app、mpvue 等跨端框架。
- 大型 UI 组件库。
- 前端状态管理库。
- 服务端 Web 框架。
- 云数据库，除非后续要保存用户偏好或权限配置。

### 10.2 目录建议

```text
api/
├── upload_payload.py
└── cloudfunctions/
    └── getDashboardSection/
        ├── index.js
        └── package.json

miniprogram/
├── app.js
├── app.json
├── app.wxss
├── pages/
│   ├── home/
│   ├── ashare/
│   └── beijing/
├── components/
│   ├── chart-card/
│   └── ec-canvas/
└── utils/
    ├── auth.js
    ├── cache.js
    ├── request.js
    ├── format.js
    └── echarts-option.js
```

## 11. 测试方案

### 11.1 Python

使用 `pytest`。

重点验证：

- `upload_payload.py` 能正常生成 JSON。
- 生成 JSON 与 `build_dashboard_payload()` 输出一致。
- 上传前 JSON 可被 `json.dumps(..., allow_nan=False)` 序列化。

### 11.2 云函数

使用轻量单元测试或本地调用脚本。

重点验证：

- 只能请求白名单 section。
- 返回数据不包含完整 dashboard payload。
- 返回数据不包含云存储 `fileID`。
- 找不到当天 JSON 时能回退到最近版本。
- JSON 不存在或结构异常时返回可处理错误。

### 11.3 小程序

使用微信开发者工具和真机手工验收。

重点验证：

- 登录流程。
- 首页入口。
- tab 切换按 section 请求。
- 下拉刷新刷新当前 section。
- 网络失败时使用 section 缓存。
- 无缓存时展示错误态。
- 分享首页和看板页可打开。
- 关键图表数值与网页一致。

## 12. 为什么不选其他方案

### 12.1 不选 Taro 或 uni-app

当前没有跨端需求，页面和状态复杂度也不高。跨端框架会增加构建、调试、升级和小程序兼容成本，不符合“简单但健壮”的目标。

### 12.2 不选自建后端

当前后端只需要读取 JSON、裁剪 section 并返回。微信云函数已经足够，自建 FastAPI、Flask 或 Node 服务会增加部署、域名、证书、鉴权和运维成本。

### 12.3 不选云数据库

当前数据已经由 SQLite 和 JSON payload 承载，小程序只读展示即可。云数据库适合用户偏好、权限名单、订阅记录等动态数据，第一版没有必要引入。

### 12.4 不选手写 Canvas 图表

图表种类虽然主要是折线，但包含双轴、参考线、tooltip、百分比格式等细节。手写 Canvas 成本高、验收难，ECharts 更稳。

## 13. 风险与控制

| 风险 | 控制方式 |
|---|---|
| 用户获取完整底层 JSON | 云存储不公开，小程序不拿 `fileID`，云函数按 section 裁剪返回 |
| ECharts 包体偏大 | 只引入必要图表能力，必要时按需构建 |
| 云函数冷启动 | section 缓存兜底，页面保留加载态 |
| Payload 字段变化导致小程序崩溃 | 云函数做 section schema 检查，小程序做空态和错误态 |
| 图表与网页不一致 | 集中维护 option 构造函数，按网页 payload 做逐项验收 |
| 上传流程失败 | 上传脚本输出明确日志，保留最近版本回退 |

## 14. 最终建议

第一版采用以下最小闭环：

1. 微信原生小程序。
2. ECharts for 微信 `ec-canvas`。
3. 微信云开发云函数 `getDashboardSection`。
4. 微信云存储保存非公开 JSON。
5. Python `upload_payload.py` 复用现有 payload 生成能力。
6. 小程序按当前 tab 请求 section 数据并缓存。

这套技术栈实现成本低，和现有仓库耦合可控，同时满足移动端展示、登录、分享、缓存、错误态和数据访问约束。
