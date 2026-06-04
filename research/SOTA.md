# SOTA 追踪（State of the Art）

> **规则：所有新策略必须先经过 10y train / 5y test OOS 验证（无 peeking），才能挑战当前 SOTA。**
> 继承自 A02 cbBTC 项目标准。
> **v1.2.0/v1.3.0 教训：参数搜索在全量数据上做 = peeking。Train/Test Split 为硬性要求。**

---

## 当前 SOTA

| 属性 | 值 |
|------|-----|
| **策略名** | VnpyMaCrossStrategy |
| **版本** | v2.1.0 — Train/Test 无 peeking 校准 |
| **描述** | 纯双均线交叉 (MA10/MA15)，日级，long-only |
| **标的** | US.SPY |
| **Sharpe** | 0.597 (OOS, 无 peeking) |
| **方法** | Train: 2011-2021 网格搜索选参 → Test: 2021-2026 报告 |
| **Train Sharpe** | 0.834 (10y in-sample) |
| **Test MaxDD** | -6.8% |
| **Test Return** | +10.2% vs B&H +91.3% |
| **Test Trades** | 85 (5y OOS) |
| **活跃状态** | **Paper Trading** — 等待 OpenD 实时验证 |
| **上线日期** | 2026-06-04 |

---

## 候选策略池

| 策略 | 状态 | OOS Sharpe | 说明 |
|------|------|-----------|------|
| **VnpyMaCrossStrategy v2.1.0** | **Paper** | **0.597** | Train/Test 无 peeking，**当前 SOTA** |
| VnpyMaCrossStrategy v2.0.0 | Rejected | 0.888 | **有 peeking**（15y 全量搜索），不可信 |
| VnpyMaRsiConfirmStrategy | Rejected | 0.819 | 5y 过拟合，15y 反噬 |
| Long-Short MA Cross | Rejected | — | SPY 做空亏钱 |
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

### 2026-06-04 — peeking 修正：Train/Test Split

- **v2.0.0 的 0.888 仍然有 peeking** — 12 组参数在 15 年全量数据上挑了最好的
- **补丁**: 10 年 train (2011-2021) 选参 → 5 年 test (2021-2026) 报告
- **Train 最优**: fast=10/slow=15（非 5/15）
- **OOS 真 Sharpe: 0.597**（28% train→test 衰减）
- **5 组常见参数中位数**: 0.993（2021-2026 对 MA Cross 友好）
- **真实预期 Sharpe: 0.6~1.0**，取决于 regime
- **SOTA 升级为 v2.1.0**: Train/Test Split 为硬性要求，无 peeking

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
