# SOTA 追踪（State of the Art）

> **规则：所有新策略必须先经过回测验证，才能挑战当前 SOTA。**
> 继承自 A02 cbBTC 项目标准。

---

## 当前 SOTA

| 属性 | 值 |
|------|-----|
| **策略名** | VnpyMaRsiConfirmStrategy |
| **版本** | v1.2.0 — MA+RSI 非对称卖出过滤 |
| **描述** | 金叉即买 + 死叉+RSI>40才卖，日级，long-only |
| **标的** | US.SPY |
| **Sharpe** | 1.46 (全周期回测) |
| **WF Holdout** | 2.10 (12m holdout) |
| **MaxDD** | -4.4% |
| **Ann.Ret** | +27.0% |
| **胜率** | 32B/33S |
| **策略逻辑** | 对称 RSI 过滤器无效（Sharpe 低于纯 MA）。关键突破：只过滤卖出端 |
| **活跃状态** | **Paper Trading** — 等待明晚 OpenD 实时验证 |
| **上线日期** | 2026-06-04 |

---

## 候选策略池

| 策略 | 状态 | Sharpe | MaxDD | 说明 |
|------|------|--------|-------|------|
| **VnpyMaRsiConfirmStrategy** | **Paper** | **1.46** | **-4.4%** | 非对称卖出过滤，WF 2.10，**升级为 SOTA** |
| VnpyMaCrossStrategy | Archived | 1.34 | -10.2% | SPY MA Cross (5/15)，被 v1.2.0 取代 |
| VnpyMaCrossStrategy | Research | 1.058 | -11.8% | NVDA 全周期最好，但 WF Holdout -0.63 |
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

### 2026-06-04 — MA+RSI 非对称过滤器突破

- **双确认对称过滤（买+卖都过滤）无效** — Sharpe 1.206 < SOTA 1.337
- **参数搜索 25 组合** — 最优 buy_max=60/sell_min=40 仍不敌 SOTA
- **关键发现**：RSI 在 SPY 上的价值**不是过滤买入，而是延迟卖出**
- **非对称测试**：
  - 只过滤买入 → 全部低于 SOTA
  - **只过滤卖出（sell_min=40）→ Sharpe 1.456，+8.9% 击败 SOTA**
- **逻辑**：上升趋势中金叉应无条件入场。死叉常发生在超卖回调，此时不应卖
- **WF Holdout: Sharpe 2.096**（1.57x SOTA），12 个月 out-of-sample 验证通过
- **VnpyMaRsiConfirmStrategy v1.2.0 升级为 SOTA**

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
