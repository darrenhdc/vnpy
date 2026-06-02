# 美股量化交易系统 — AI Agent 规则

> **硬性规则：所有回复使用简体中文。**
> **项目路径：`/Users/darrencui/tradFi/vnpy`**
> **交易标的：US 股票（AAPL, SPY, QQQ 等）**
> **API：Futu OpenAPI（OpenD 网关）**

## 🎯 项目定位

基于 Futu API 的美股现货量化交易系统。沿用 A02 cbBTC 项目成熟的 8 阶段研究流水线（Idea → Research → Parameter Search → Walk-Forward → Candidate Report → Paper Trading → Small Live → Monitor）。

## 当前状态（2026-06-02）

**P1 阶段完成。** 框架骨架 + 研究流水线 + 策略插件架构 + SOTA 追踪 + Heartbeat 监控 + CLI 工具全部就绪。等待 OpenD 首次登录后即可接入实时行情跑模拟盘。

## 项目进度锚点

### ✅ 已完成

| # | 项目 | 位置 | 说明 |
|---|------|------|------|
| 1 | 配置管理 | `config/settings.py` | YAML 统一配置 + SIMULATE 强制检查 |
| 2 | 数据库 | `data/database.py` | SQLite 7 表（bars/signals/orders/trades/positions/snapshots/risk） |
| 3 | 数据下载 | `data/yahoo_feeder.py` | Yahoo Finance 历史数据（1m~1mo） |
| 4 | 实时行情 | `data/live_engine.py` | vn.py EventEngine 封装，自动降级 mock |
| 5 | 风控引擎 | `risk/risk_engine.py` | 8 项检查规则，回测冷却兼容 bar_time |
| 6 | 策略基类 | `strategies/base_strategy.py` | ABC 抽象框架，按金额下单 |
| 7 | MA 交叉策略 | `strategies/moving_average_cross.py` | 金叉买死叉卖，已注册到 registry |
| 8 | RSI 策略 | `strategies/rsi_strategy.py` | 超买超卖，已注册到 registry |
| 9 | 回测脚本 | `scripts/backtest.py` | Yahoo 数据回放 + PnL / 胜率 / MaxDD 分析 |
| 10 | 健康检查 | `monitor/healthcheck.py` | OpenD 端口可达性检查 |
| 11 | 单元测试 | `tests/` | 4 个 pytest 测试文件，13/13 通过 |
| 12 | 研究流水线 | `research/data_loader.py` + `research/backtest.py` | 向量化特征工程 + 回测引擎 |
| 13 | Paper Trading | `scripts/run_headless.py` | dry_run 模式 + 实时引擎占位 |
| 14 | **策略插件架构** | `strategies/registry.py` + `strategies/core.py` | `@register` 装饰器 + FeatureEngine/SignalBuffer/StateTracker |
| 15 | **SOTA 追踪** | `research/SOTA.md` + `research/TEMPLATE.md` | 当前 SOTA / 候选池 / 演化史 / 8 阶段报告模板 |
| 16 | **Heartbeat 监控** | `monitor/heartbeat.py` | CLI/JSON/HTTP 三种输出模式 |
| 17 | **CLI 工具** | `scripts/sota.py` + `scripts/performance.py` + `scripts/archived.py` | SOTA 管理 / 绩效查询 / 归档清理 |

### 🚧 P0 剩余

| # | 项目 | 估时 | 说明 |
|---|------|------|------|
| 1 | **接入真实 Futu 下单** | ~2h | 等待 OpenD 登录完成，替换 `_send_order()` 为 Gateway 真实下单 |

### 🟢 P2 待办

| # | 项目 | 估时 | 说明 |
|---|------|------|------|
| 9 | **多因子 IC 验证** | ~2h | 对 MA/RSI/MACD 等做 rolling IC |
| 10 | **Telegram 通知** | ~1h | 下单/风控事件推送 |
| 11 | **Regime 归因** | ~2h | 牛熊震荡分 regime 分析 |

## 研究 SOP（继承自 A02）

1. **Idea** — 写清楚假设、预期盈利 regime、预期失败 regime
2. **Research** — 用 `research/backtest.py` + `research/data_loader.py` 验证信号 IC
3. **Parameter Search** — 小范围、假设驱动的网格搜索
4. **Walk-Forward** — 18m train / 3m test / 3m step / 12m holdout
5. **Candidate Report** — 使用 `research/TEMPLATE.md` 标准格式产出到 `research/reports/`
6. **Paper** — dry_run paper trading
7. **Small Live** — 小资金上线（仅限 SIMULATE）
8. **Monitor** — 日检/周检，用 `scripts/sota.py` 和 `scripts/performance.py`

## 硬性约束

- Futu 环境必须是 SIMULATE（模拟盘），除非用户明确确认
- 禁止修改 `.env` 中的 OpenD 连接密码、Futu 账户信息
- 不要在 strategy.yaml 中硬编码金额——用风控参数
- 所有新策略必须先过回测，再过 paper trading，最后才干实盘（模拟盘）
- Git 提交保持小粒度

## 关键路径

| 路径 | 说明 |
|------|------|
| `config/settings.py` | 统一配置入口 |
| `config/futu.yaml` | OpenD 连接参数 |
| `config/risk.yaml` | 风控参数 |
| `config/strategy.yaml` | 策略参数 |
| `data/database.py` | SQLite 封装 |
| `data/yahoo_feeder.py` | 历史数据 |
| `strategies/base_strategy.py` | 策略基类 |
| `strategies/registry.py` | 策略注册表 |
| `strategies/core.py` | 共享决策核心（FeatureEngine / SignalBuffer / StateTracker） |
| `risk/risk_engine.py` | 风控引擎 |
| `scripts/backtest.py` | 回测脚本 |
| `scripts/run_headless.py` | 无头运行 |
| `scripts/sota.py` | SOTA 管理 CLI |
| `scripts/performance.py` | 绩效查询 CLI |
| `scripts/archived.py` | 归档管理 CLI |
| `monitor/heartbeat.py` | Heartbeat 健康检查 |
| `research/SOTA.md` | SOTA 追踪 |
| `research/TEMPLATE.md` | 候选报告模板 |
