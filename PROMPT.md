你在 /Users/darrencui/tradFi/vnpy 工作，美股量化交易系统。

## 会话初始化

读取：
1. `AGENTS.md` — 项目规则 + 进度
2. `specs/SPEC_001_VNPY_MIGRATION.md` — 本次任务的详细规格
3. `research/backtest.py` + `research/data_loader.py` — 当前研究管线

## 本次任务：从自建执行层迁移到 vnpy 开源框架

核心理念：和 A02 选 Hummingbot 的逻辑完全一致——策略是你的，框架是人家的。
保留研究层（research/），执行层交给 vnpy 的 CtaEngine。

### Phase 2（立即开始）— 策略迁移

把现有的 MA 交叉策略和 RSI 策略改写为 vnpy CtaTemplate 子类：
- 创建 `strategies/vnpy_ma_cross.py`
- 创建 `strategies/vnpy_rsi.py`
- 信号逻辑不变，下单改用 `self.buy()` / `self.sell()`

### Phase 4（迁移后）— 研究设施补全
- `research/walk_forward.py`
- `research/reports/SOTA.md` + `TEMPLATE.md`
- `research/factor_ic.py`
- 对 NVDA 做单资产消融实验

### 硬性约束
- SIMULATE 模式（模拟盘）绝对不做真实交易
- research/ 一个文件都不删
- 旧代码移入 `_archived/` 而非删除
