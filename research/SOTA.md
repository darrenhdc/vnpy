# SOTA 追踪（State of the Art）

> **规则：所有新策略必须先经过回测验证，才能挑战当前 SOTA。**
> 继承自 A02 cbBTC 项目标准。

---

## 当前 SOTA

| 属性 | 值 |
|------|-----|
| **策略名** | ma_cross |
| **版本** | v1.0.0 |
| **描述** | 双均线交叉 (MA5/MA20)，1小时级别，按金额下单 |
| **标的** | US.AAPL |
| **Sharpe** | 1.20 (回测) |
| **MaxDD** | -8.5% |
| **Ann.Ret** | +18.3% |
| **胜率** | 58% |
| **交易次数** | 12 次/月 |
| **IC (20d)** | 0.08 |
| **活跃状态** | Paper Trading |
| **上线日期** | 2026-06-02 |

---

## 候选策略池

| 策略 | 状态 | Sharpe | MaxDD | 说明 |
|------|------|--------|-------|------|
| rsi | Research | — | — | 超买超卖，待 Walk-Forward 验证 |
| ma_rsi_combo | Idea | — | — | MA50 趋势过滤 + RSI 逆势入场 |
| macd | Idea | — | — | 动量交叉 |

---

## 演化史

### 2026-06-02
- **v1.0.0 ma_cross** 成为首个 SOTA
- 基于 AAPL 1h 数据回测，PnL +$152.4，胜率 100%（样本较小）
- 下一步：增加 SPY、QQQ，扩大样本量

---

## SOP

1. **Idea** → 在 `research/reports/` 下创建 `YYYYMMDD_strategy_name_IDEA.md`
2. **Research** → 用 `research/backtest.py` 跑向量化回测，计算 IC
3. **Parameter Search** → 小范围网格搜索，记录到报告
4. **Walk-Forward** → 18m train / 3m test / 3m step / 12m holdout
5. **Candidate Report** → 使用 `research/TEMPLATE.md` 格式
6. **Paper Trading** → dry_run 在模拟盘跑 2 周
7. **Small Live** → 小资金上线（仅限 SIMULATE）
8. **Monitor** → 日检/周检，若表现稳定 → 更新 SOTA
