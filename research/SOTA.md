# SOTA 追踪（State of the Art）

> **规则：所有新策略必须先经过回测验证，才能挑战当前 SOTA。**
> 继承自 A02 cbBTC 项目标准。

---

## 当前 SOTA

| 属性 | 值 |
|------|-----|
| **策略名** | VnpyMaCrossStrategy |
| **版本** | v1.0.0 |
| **描述** | 双均线交叉 (MA5/MA20)，日级，long-only |
| **标的** | US.NVDA (消融实验主资产) |
| **Sharpe** | 1.058 (全周期回测) |
| **MaxDD** | -11.8% |
| **Ann.Ret** | +9.2% |
| **胜率** | 50% (40B/40S) |
| **IC (20d)** | -0.035 (MA), +0.081 (MACD) |
| **活跃状态** | Research (WF Holdout 失效，不推荐上线) |
| **上线日期** | 2026-06-02 |

---

## 候选策略池

| 策略 | 状态 | Sharpe | MaxDD | 说明 |
|------|------|--------|-------|------|
| VnpyMaCrossStrategy | Research | 1.058 | -11.8% | NVDA 全周期最好，但 WF Holdout -0.63 |
| VnpyRsiStrategy | Rejected | 0.196 | -14.8% | NVDA 极少超卖，信号稀疏 |
| MACD | Research | 0.980 | -12.1% | IC 最强 (+0.081)，动量效应 |
| ma_rsi_combo | Rejected | nan | 0% | 无信号产生 |

---

## 演化史

### 2026-06-02
- **迁移到 vnpy CtaTemplate** — 保留研究层，执行层交给 vnpy
- **创建 _archived/** — 旧自建引擎归档
- **NVDA 消融实验完成** — 结论：NVDA 不适合择时，所有策略跑输 B&H
- **关键发现**: MACD IC (+0.081) 远优于 MA/RSI，NVDA 是动量股
- **下一步**: 换标的 SPY/QQQ，修复 backtest.py 参数搜索 bug

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
