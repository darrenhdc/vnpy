# 美股量化交易系统 — AI Agent 规则

> **硬性规则：所有回复使用简体中文。**
> **项目路径：`/Users/darrencui/tradFi/vnpy`**
> **交易标的：US 股票（AAPL, SPY, QQQ 等）**
> **API：Futu OpenAPI（OpenD 网关）**

## 🎯 项目定位

基于 Futu API 的美股现货量化交易系统。沿用 A02 cbBTC 项目成熟的 8 阶段研究流水线（Idea → Research → Parameter Search → Walk-Forward → Candidate Report → Paper Trading → Small Live → Monitor）。

## 当前状态（2026-06-04）

**SOTA v2.1.0 — Train/Test 无 peeking 校准。** 发现 v2.0.0 的 0.888 Sharpe 仍有参数搜索 peeking。修正为 10y train/5y test split，真 OOS Sharpe 0.597。策略为纯 MA Cross (10/15)，85 笔 OOS 交易。准备 OpenD 实时验证。

## 项目进度锚点

### ✅ 已完成

| # | 项目 | 位置 | 说明 |
|---|------|------|------|
| 1 | 配置管理 | `config/settings.py` | YAML 统一配置 + SIMULATE 强制检查 |
| 2 | 数据库 | `data/database.py` | SQLite 7 表 |
| 3 | 数据下载 | `data/yahoo_feeder.py` | Yahoo Finance 历史数据 |
| 4 | 实时行情 | `scripts/run_live.py` | **futu-api 直接连接 OpenD**，预热 + 实时订阅 |
| 5 | 策略基类 | `strategies/vnpy_compat.py` | **vnpy CtaTemplate 轻量兼容层**，支持 buy/sell/pos/on_trade |
| 6 | MA 交叉策略 | `strategies/vnpy_ma_cross.py` | **SOTA v2.1.0**，OOS Sharpe 0.597 |
| 7 | MA+RSI+ATR | `strategies/vnpy_ma_rsi_confirm.py` | v1.2.0/v1.3.0 已过拟合，保留作为参考 |
| 8 | 回测引擎 | `research/backtest.py` | 15 年数据支持，多策略类型 |
| 9 | Walk-Forward | `research/walk_forward.py` | 18m/3m WF + holdout |
| 10 | 因子 IC | `research/factor_ic.py` | 滚动 Spearman IC/IR |
| 11 | 消融实验 | `research/reports/` | NVDA/SPY/QQQ + 打榜全记录 |
| 12 | 15 年验证 | `research/validate_15y.py` | 发现 v1.2.0/v1.3.0 过拟合，触发大重置 |
| 13 | SOTA 追踪 | `research/SOTA.md` | v1.0.0 → v2.0.0，4 次迭代 |
| 14 | Ops 设施 | `./sota` `./archived` `./performance` `./run-live` | 4 个快捷命令 |

### 🟡 P1 待办

| # | 项目 | 估时 | 说明 |
|---|------|------|------|
| 1 | **OpenD 实盘验证** | 今晚 21:30 | `./run-live` 跑 SPY MA Cross v2.0.0 |
| 2 | **多资产 15 年验证** | ~2h | QQQ + AAPL 15 年回测，增加样本量 |
| 3 | **Regime 归因** | ~2h | 牛熊震荡分 regime 分析 |

## 研究 SOP（继承自 A02）

1. **Idea** — 写清楚假设、预期盈利 regime、预期失败 regime
2. **Research** — 用 `research/backtest.py` + `research/factor_ic.py` 验证信号 IC
3. **Parameter Search** — 小范围网格搜索，记录到报告
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
| `strategies/vnpy_compat.py` | **vnpy CtaTemplate 兼容层** |
| `strategies/vnpy_ma_cross.py` | MA 交叉策略（vnpy 接口） |
| `strategies/vnpy_macd.py` | MACD 策略（vnpy 接口） |
| `strategies/vnpy_rsi.py` | RSI 策略（vnpy 接口） |
| `strategies/vnpy_ma_rsi_confirm.py` | MA+RSI 双确认策略（vnpy 接口） |
| `research/data_loader.py` | 向量化特征工程 |
| `research/backtest.py` | 向量化回测引擎 |
| `research/walk_forward.py` | Walk-Forward 验证 |
| `research/factor_ic.py` | 因子滚动 IC |
| `research/SOTA.md` | SOTA 追踪 |
| `research/TEMPLATE.md` | 候选报告模板 |
| `scripts/run_live.py` | **实时运行（OpenD）** |
| `scripts/sota.py` | SOTA 管理 CLI |
| `scripts/performance.py` | 绩效查询 CLI |
| `scripts/archived.py` | 归档管理 CLI |
| `monitor/heartbeat.py` | Heartbeat 健康检查 |
| `_archived/` | 旧自建引擎归档 |
