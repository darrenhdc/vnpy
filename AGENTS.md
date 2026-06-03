# 美股量化交易系统 — AI Agent 规则

> **硬性规则：所有回复使用简体中文。**
> **项目路径：`/Users/darrencui/tradFi/vnpy`**
> **交易标的：US 股票（AAPL, SPY, QQQ 等）**
> **API：Futu OpenAPI（OpenD 网关）**

## 🎯 项目定位

基于 Futu API 的美股现货量化交易系统。沿用 A02 cbBTC 项目成熟的 8 阶段研究流水线（Idea → Research → Parameter Search → Walk-Forward → Candidate Report → Paper Trading → Small Live → Monitor）。

## 当前状态（2026-06-04）

**SOTA 已迭代到 v1.2.0 —— MA+RSI 非对称卖出过滤器。** 对称 RSI 过滤（买+卖都过滤）被证伪。关键突破：只过滤卖出端（死叉+RSI>40才卖），Sharpe 1.456 (+8.9% vs 旧 SOTA)，WF Holdout 2.096。策略代码已就绪，等待明晚 OpenD 实时验证。

## 项目进度锚点

### ✅ 已完成

| # | 项目 | 位置 | 说明 |
|---|------|------|------|
| 1 | 配置管理 | `config/settings.py` | YAML 统一配置 + SIMULATE 强制检查 |
| 2 | 数据库 | `data/database.py` | SQLite 7 表 |
| 3 | 数据下载 | `data/yahoo_feeder.py` | Yahoo Finance 历史数据 |
| 4 | 实时行情 | `scripts/run_live.py` | **futu-api 直接连接 OpenD**，预热 + 实时订阅 |
| 5 | 策略基类 | `strategies/vnpy_compat.py` | **vnpy CtaTemplate 轻量兼容层**，支持 buy/sell/pos/on_trade |
| 6 | MA 交叉策略 | `strategies/vnpy_ma_cross.py` | 继承 CtaTemplate，fast/slow 可配置 |
| 7 | RSI 策略 | `strategies/vnpy_rsi.py` | 继承 CtaTemplate，oversold/overbought 可配置 |
| 8 | MACD 策略 | `strategies/vnpy_macd.py` | 继承 CtaTemplate，fast/slow/signal 可配置 |
| 9 | **MA+RSI SellFilter** | `strategies/vnpy_ma_rsi_confirm.py` | 非对称 RSI 卖出过滤，Sharpe 1.46，**新 SOTA** |
| 10 | 回测引擎 | `research/backtest.py` | **参数搜索 bug 已修复**，generate_signals 支持 kwargs |
| 11 | Walk-Forward | `research/walk_forward.py` | 18m/3m WF + holdout 验证 |
| 12 | 因子 IC | `research/factor_ic.py` | 滚动 Spearman IC / IR / 正相关占比 |
| 13 | 消融实验 | `research/reports/` | NVDA / SPY / QQQ 三份候选报告 |
| 14 | SOTA 追踪 | `research/SOTA.md` | 当前 SOTA / 候选池 / 演化史 |
| 15 | CLI 工具 | `scripts/sota.py` + `performance.py` + `archived.py` | SOTA 管理 / 绩效查询 / 归档清理 |
| 16 | 单元测试 | `tests/` | 8/8 通过（配置 + 数据库 + 3 个策略信号） |

### 🟡 P2 待办

| # | 项目 | 估时 | 说明 |
|---|------|------|------|
| 9 | **多资产组合** | ~2h | SPY+QQQ+AAPL 组合策略，分散单一标的风险 |
| 10 | **波动率过滤** | ~1h | ATR/RVOL 过滤器，只在高波动时段交易 |
| 11 | **Regime 归因** | ~2h | 牛熊震荡分 regime 分析 |

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
