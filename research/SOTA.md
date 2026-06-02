# SOTA 追踪（State of the Art）

> **规则：所有新策略必须先经过回测验证，才能挑战当前 SOTA。**
> 继承自 A02 cbBTC 项目标准。

---

## 当前 SOTA

| 属性 | 值 |
|------|-----|
| **策略名** | VnpyMaCrossStrategy |
| **版本** | v1.1.0-SPY |
| **描述** | 双均线交叉 (MA5/MA15)，日级，long-only |
| **标的** | US.SPY |
| **Sharpe** | 1.34 (全周期回测) |
| **MaxDD** | -10.2% |
| **Ann.Ret** | +14.6% |
| **胜率** | 47% (18B/17S) |
| **IC (20d)** | +0.103 (RSI), +0.081 (MACD) |
| **活跃状态** | **Paper Trading** — 等待明晚 OpenD 实时验证 |
| **上线日期** | 2026-06-02 (SPY 候选报告) |

---

## 候选策略池

| 策略 | 状态 | Sharpe | MaxDD | 说明 |
|------|------|--------|-------|------|
| VnpyMaCrossStrategy | Paper | 1.34 | -10.2% | **SPY** 全周期最好，WF Holdout +1.62 |
| VnpyMaCrossStrategy | Research | 1.058 | -11.8% | **NVDA** 全周期最好，但 WF Holdout -0.63 |
| VnpyMaRsiConfirmStrategy | Research | — | — | MA+RSI 双确认，交易数减少 80%，回报持平 |
| VnpyRsiStrategy | Rejected | 0.196 | -14.8% | NVDA 极少超卖，信号稀疏 |
| MACD | Research | 0.980 | -12.1% | NVDA IC 最强 (+0.081)，动量效应 |
| ma_rsi_combo | Rejected | nan | 0% | 无信号产生 |

---

## 演化史

### 2026-06-02
- **迁移到 vnpy CtaTemplate** — 保留研究层，执行层交给 vnpy
- **创建 _archived/** — 旧自建引擎归档
- **NVDA 消融实验完成** — 结论：NVDA 不适合择时，所有策略跑输 B&H
- **关键发现**: MACD IC (+0.081) 远优于 MA/RSI，NVDA 是动量股
- **下一步**: 换标的 SPY/QQQ，修复 backtest.py 参数搜索 bug

### 2026-06-02
- **SPY + QQQ 消融实验完成** — SPY 最优参数 fast=5 slow=15, Sharpe=1.34
- **修复 backtest.py 硬编码 bug** — `generate_signals` 支持 `strategy_params` kwargs
- **OpenD 实时接入验证** — futu-api 直接连接，预热 + 实时订阅成功
- **MA+RSI 双确认策略创建** — 利用 SPY RSI IC +0.103，入场增加 RSI 过滤器
- **当前 SOTA** 切换为 **SPY MA Cross (5/15)**，等待明晚 OpenD 实盘验证
- **顺序**: OpenD 实时验证 → RSI 双确认 → 实盘校准 → 再加新标的

---

## SOP

1. **Idea** → 在 `research/reports/` 下创建 `YYYYMMDD_strategy_name_IDEA.md`
2. **Research** → 用 `research/backtest.py` + `research/factor_ic.py` 验证信号 IC
3. **Parameter Search** → 小范围网格搜索，记录到报告
4. **Walk-Forward** → 18m train / 3m test / 3m step / 12m holdout
5. **Candidate Report** → 使用 `research/TEMPLATE.md` 标准格式
6. **Paper** — dry_run paper trading
7. **Small Live** — 小资金上线（仅限 SIMULATE）
8. **Monitor** — 日检/周检
