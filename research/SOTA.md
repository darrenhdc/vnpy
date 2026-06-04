# SOTA 追踪（State of the Art）

> **规则：所有新策略必须先经过 15 年数据回测验证 + WF，才能挑战当前 SOTA。**
> 继承自 A02 cbBTC 项目标准。
> **v1.2.0/v1.3.0 教训：5 年窗口的优化是过拟合。15 年验证为硬性要求。**

---

## 当前 SOTA

| 属性 | 值 |
|------|-----|
| **策略名** | VnpyMaCrossStrategy |
| **版本** | v2.0.0 — 15 年校准 |
| **描述** | 纯双均线交叉 (MA5/MA15)，日级，long-only，无附加过滤器 |
| **标的** | US.SPY |
| **Sharpe** | 0.888 (15 年回测) |
| **MaxDD** | -6.4% |
| **Ann.Ret** | +50.4% |
| **Trades** | 265 (15 年) |
| **B&H** | +662.8% (15 年) |
| **活跃状态** | **Paper Trading** — 等待 OpenD 实时验证 |
| **上线日期** | 2026-06-04 |

---

## 候选策略池

| 策略 | 状态 | 15y Sharpe | 说明 |
|------|------|-----------|------|
| **VnpyMaCrossStrategy (SPY)** | **Paper** | **0.888** | 纯 MA Cross，15 年唯一跨周期成立，**当前 SOTA** |
| VnpyMaRsiConfirmStrategy | Rejected | 0.838 | RSI+ATR 在 5y 上有效，15y 上**反噬**（过拟合） |
| VnpyMaCrossStrategy (NVDA) | Rejected | — | WF Holdout -0.63，标的本身不适合择时 |
| Long-Short MA Cross | Rejected | — | SPY 做空系统性亏损 |
| MACD + RSI | Rejected | — | MACD 太慢 |

---

## 演化史

### 2026-06-02
- **迁移到 vnpy CtaTemplate** — 保留研究层，执行层交给 vnpy
- **NVDA/SPY/QQQ 消融完成** — NVDA 不适合择时，SPY MA Cross 最好
- **修复 backtest.py** — `generate_signals` 支持 `strategy_params` kwargs
- **OpenD 实时接入验证** — futu-api 连接成功

### 2026-06-04 — 打榜 #1~#4
- **#1 RSI 双确认 → 非对称突破** — 只过滤卖出端，5y Sharpe 1.456，升级 v1.2.0
- **#2 ATR 仓位管理** — 5y Sharpe 1.626，升级 v1.3.0
- **#3 Long-Short** — 全线失败
- **#4 MACD+RSI** — 不敌 SOTA

### 2026-06-04 — **15 年验证：5 年 SOTA 全部过拟合，大重置**

- **15 年数据测试（2011-2026, 3771 天, 265 笔交易）**
- Pure MA Cross: 5y Sharpe 1.337 → **15y Sharpe 0.888** ✅
- v1.2.0 (+RSI): 5y Sharpe 1.456 → **15y Sharpe 0.819** ❌ **RSI 过滤反噬**
- v1.3.0 (+ATR): 5y Sharpe 1.626 → **15y Sharpe 0.838** ❌ **ATR 也反噬**
- **关键原因**: 5 年窗口（2021-2026）是极特殊的牛市，无真熊市。RSI/ATR 优化是对这段行情的过拟合
- **15 年参数重搜**: sell_min=0（不用 RSI 过滤）才是最优；纯 MA Cross 是唯一跨周期策略
- **SOTA 重置为 v2.0.0** — VnpyMaCrossStrategy, pure MA Cross (5/15)
- **新规则**: 所有候选策略必须通过 15 年数据验证，否则不能挑战 SOTA
- **样本量**: 65 笔 → 265 笔，统计显著性 4x 提升

---

## SOP

1. **Idea** → `research/reports/` 下创建 IDEA 文档
2. **Research** → backtest.py + factor_ic.py 验证
3. **Parameter Search** → 网格搜索，仅用在 train 期
4. **15 年验证** → **必须**在 15 年数据上验证，5 年优化不足以升级
5. **Walk-Forward** → 18m/3m/step + holdout
6. **Candidate Report** → 使用 TEMPLATE.md
7. **Paper Trading** — `./run-live` 模拟盘
8. **Small Live** — 小资金上线（仅限 SIMULATE）
9. **Monitor** — 日检/周检，`./sota`, `./archived`
