# MarketPulse 小程序交付指南

本文档描述从空的微信云开发测试环境开始，完成 payload 生成与上传、云函数部署、云端调用、小程序本地调试和预览的第一版交付流程。

## 1. 交付边界

- 现有两个 Python 看板仍是业务数据和指标计算的唯一来源。
- 不修改 `src/security_market_pulse.py` 和 `src/beijing_real_estate_market_pulse.py` 的 HTML 模板、输出路径或生成行为。
- 小程序只展示现有 payload 中的指标，不新增指标，也不在云函数或小程序端重新计算指标。
- `api/upload_payload.py` 只负责序列化、暂存、维护 manifest 和调用外部上传命令。
- `getDashboardSection` 只负责登录上下文检查、manifest 选档和 section 裁剪。
- `marketpulse-payload/` 必须位于非公开云存储中，小程序不得直接读取完整 JSON。

## 2. 环境准备

本地需要：

- Python 3；
- Node.js，用于本地云函数和小程序 JavaScript 测试；
- 微信开发者工具；
- 可读取目标数据的 `data/market_data.sqlite`；
- Python 依赖：`pandas`、`akshare`、`requests`、`openpyxl`、`tushare`、`pytest`。

微信侧需要：

- 一个与 `project.config.json` 中 AppID 对应的小程序；
- 一个单独的非生产云开发环境；
- 当前微信号已被加入小程序开发成员和云开发环境成员；
- 云存储中 `marketpulse-payload/` 不允许小程序端或公网直接读取。

仓库不提供共享测试账号、环境 ID、token 或数据库快照。测试人员使用自己的受邀微信开发者账号；环境 ID 和本机设置只保存在微信开发者工具或忽略的 `project.private.config.json` 中，不写入版本控制。

## 3. 本地初始化

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas akshare requests openpyxl tushare pytest
python3 -m pytest
```

如需抓取 Tushare 数据，在仓库根目录创建不提交的 `.env`：

```text
TUSHARE_TOKEN=你的本地 token
```

只验证现有 A 股 HTML 渲染时应避免外部抓取：

```bash
python3 src/security_market_pulse.py --skip-fetch
python3 src/beijing_real_estate_market_pulse.py
```

默认 HTML 仍分别输出到：

- `security_market_pulse/index.html`
- `beijing_real_estate_market_pulse/index.html`

## 4. 生成 payload

从现有 SQLite 数据生成两类 JSON 和 manifest：

```bash
python3 api/upload_payload.py \
  --db-path data/market_data.sqlite \
  --start-date 2010-01-01
```

默认输出：

```text
api/payload/marketpulse-payload/
├── ashare_YYYY-MM-DD.json
├── beijing_YYYY-MM-DD.json
└── manifest.json
```

文件名日期取 payload 中最新业务日期，不取脚本运行日期。需要限制类型或校验目标业务日期时可使用：

```bash
python3 api/upload_payload.py --type ashare
python3 api/upload_payload.py --type beijing
python3 api/upload_payload.py --date YYYY-MM-DD
```

`api/payload/` 包含未经 section 裁剪的完整 payload，已被 `.gitignore` 排除，不得提交或公开。

## 5. 上传到云存储

### 5.1 首次交付：开发者工具上传

1. 在微信开发者工具中打开仓库根目录。
2. 选择目标测试云环境。
3. 打开“云开发”控制台和“存储”。
4. 创建或进入 `marketpulse-payload/` 目录。
5. 上传本地生成的两个 payload JSON。
6. 最后上传 `manifest.json`。
7. 确认云端对象路径与 manifest 中的 `latestFile`、`files` 完全一致。
8. 将存储权限配置为仅云函数可读，不允许小程序端或公网直接下载。

manifest 必须最后上传，避免它先指向尚未上传的 payload。

### 5.2 自动上传命令

仓库不绑定特定厂商 CLI。已有上传工具时，可把单文件上传命令作为模板传入：

```bash
python3 api/upload_payload.py \
  --db-path data/market_data.sqlite \
  --env-id YOUR_TEST_ENV_ID \
  --upload-command 'your-uploader --env {env_id} --source {local_path} --target {cloud_path}'
```

模板支持：

- `{local_path}`：本地文件绝对路径；
- `{cloud_path}`：`marketpulse-payload/...` 对象路径；
- `{env_id}`：`--env-id` 的值。

脚本按 payload、manifest 的顺序调用上传工具。接入实际 CLI 前，先用测试环境确认该工具执行的是覆盖式单文件上传，并且不会生成公开 URL。

## 6. 部署云函数

1. 在微信开发者工具中确认当前选择的是目标测试云环境。
2. 在 `api/cloudfunctions/getDashboardSection/` 上选择“上传并部署：云端安装依赖”。
3. 确认云端安装了 `package.json` 中的 `wx-server-sdk`。
4. 确认云函数运行环境能够读取 `marketpulse-payload/manifest.json` 和 manifest 指向的 JSON。
5. 不要把环境 ID、文件 ID、下载凭据或存储路径加入云函数返回值。

云函数输入示例：

```json
{
  "type": "ashare",
  "section": "indexDeviation"
}
```

成功响应顶层字段只能是：

```json
{
  "type": "ashare",
  "section": "indexDeviation",
  "data": []
}
```

建议通过已登录的小程序页面完成真实调用验证，因为云函数需要调用上下文中的 `OPENID`。还应抽查一个复合 section，例如：

```json
{
  "type": "beijing",
  "section": "onlineSignings"
}
```

并确认响应只包含 `dailyOnlineSignings` 和 `monthlyOnlineSignings`。

## 7. 小程序本地调试与预览

1. 用微信开发者工具打开仓库根目录，不要只打开 `miniprogram/`。
2. 确认工具识别：
   - `miniprogramRoot`: `miniprogram/`
   - `cloudfunctionRoot`: `api/cloudfunctions/`
3. 选择与 payload 和云函数相同的测试云环境。
4. 使用受邀开发者微信号编译并登录。
5. 依次验证首页、资本市场、北京楼市。
6. 每个主 tab 至少打开一次，确认只请求当前 section。
7. 验证下拉刷新、错误重试、横向 tab、Top5 表格横向滚动和居民贷款二级 tab。
8. 清除小程序缓存后重新进入，验证首次云函数读取。
9. 断网后重新打开已访问 section，验证 24 小时有效缓存兜底。
10. 使用“预览”生成二维码，在真机上验证登录、图表、分享和刷新。

若错误发生在 `WAServiceMainContext.js` 且早于项目代码执行，优先检查开发者工具版本、基础库版本、调试包和编译设置。仓库当前关闭增强编译、代码压缩、WXML/WXSS 压缩和 source map 上传，以保持已验证的兼容配置。

## 8. 交付验收

交付前执行：

```bash
python3 -m pytest
node -c api/cloudfunctions/getDashboardSection/index.js
node -c miniprogram/pages/home/index.js
node -c miniprogram/pages/ashare/index.js
node -c miniprogram/pages/beijing/index.js
git diff --check
```

验收清单：

- 两个原有 HTML 均可生成，输出路径和行为未改变；
- staged JSON 与对应 `build_dashboard_payload()` 输出一致；
- 云端 manifest 指向已存在的非公开 payload；
- 9 个白名单 section 均可通过登录态调用；
- 响应不包含完整 payload、`fileID`、下载地址、凭据或对象路径；
- 首页不预加载看板数据；
- 两个看板按 tab 请求、缓存、刷新和重试；
- 开发者工具及真机预览通过；
- `.env`、数据库、`project.private.config.json` 和 `api/payload/` 未进入版本控制。

## 9. 已知限制

- 第一版登录只在本地保存头像、昵称和 `wx.login()` 成功状态；未把 login code 交换为自建会话，也没有角色、白名单或权限分层。
- 云函数仅以微信调用上下文中存在 `OPENID` 作为访问条件。
- 仓库不内置具体云存储 CLI；自动上传依赖交付环境提供单文件上传命令。
- 云存储 ACL 需要在目标云环境中人工配置和复核，仓库测试无法证明线上权限设置。
- 小程序不展示 payload 日期、生成时间、缓存命中状态或刷新失败详情。
- 第一版分享落到页面，不保留当前主 tab 或居民贷款二级 tab。
- 小程序请求不传可选业务日期，默认由云函数读取 manifest 最新版本。
- 没有自动化截图或像素级视觉对比；图表验收以数据、轴、单位、参考线和移动端可读性为准。
- 不包含定时生成、定时上传或生产发布流水线。

