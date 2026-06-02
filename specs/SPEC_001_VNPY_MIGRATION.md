# vnpy 项目迁移规格：自建引擎 → vnpy 开源框架

> 决策：保留研究层（data_loader / backtest / 特征工程），执行层交给 vnpy 框架。
> 理由：和 A02 选 Hummingbot 的逻辑完全一致——策略是你的，框架是人家的。

## 目标架构

```
┌─────────────────────────────────────────────────────┐
│ research/           ← 你的，不动                      │
│ ├── data_loader.py   Yahoo 数据 + 14 特征            │
│ ├── backtest.py      向量化回测 + 4 信号策略          │
│ ├── walk_forward.py  18m/3m WF（待建）               │
│ └── reports/         SOTA.md + 候选报告（待建）       │
├─────────────────────────────────────────────────────┤
│ strategies/         ← 你的策略逻辑，改编接口           │
│ ├── ma_cross_strategy.py    继承 vnpy CtaTemplate    │
│ └── rsi_strategy.py         继承 vnpy CtaTemplate    │
├─────────────────────────────────────────────────────┤
│ vnpy 框架 (pip install) ← 人家的，不动                │
│ ├── CtaEngine           策略引擎 + 订单管理           │
│ ├── CtaBacktester       内置回测（你的 backtest.py    │
│ │                       保留做消融验证用）             │
│ ├── FutuGateway         Futu 连接器                  │
│ └── EventEngine         事件驱动核心                  │
├─────────────────────────────────────────────────────┤
│ Futu OpenD                                          │
├─────────────────────────────────────────────────────┤
│ Futu 云                                             │
└─────────────────────────────────────────────────────┘
```

## 迁移步骤

### Phase 1 — 环境准备（30 分钟）

1. 安装 vnpy 框架
```bash
pip install vnpy vnpy_futu
```

2. 验证安装
```bash
python -c "from vnpy.app.cta_strategy import CtaStrategyApp; print('OK')"
```

3. OpenD 连接测试（已有 `scripts/test_opend.py`）

### Phase 2 — 策略迁移（2 小时）

**当前策略**：`strategies/base_strategy.py`（你的 ABC）+ `moving_average_cross.py` / `rsi_strategy.py`

**迁移后**：继承 vnpy 的 `CtaTemplate`，重写 `on_bar()` 和信号逻辑。

```python
# strategies/vnpy_ma_cross.py  ← 新的
from vnpy.app.cta_strategy import CtaTemplate, StopOrder, TickData, BarData
from vnpy.trader.constant import Direction, Offset

class VnpyMaCrossStrategy(CtaTemplate):
    author = "darren"
    fast_window = 5
    slow_window = 20

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.fast_ma = []
        self.slow_ma = []

    def on_bar(self, bar: BarData):
        # 同样的逻辑，但用 BarData 而不是 dict
        self.fast_ma.append(bar.close_price)
        self.slow_ma.append(bar.close_price)
        if len(self.fast_ma) > self.fast_window:
            self.fast_ma.pop(0)
            self.slow_ma.pop(0)

        fast_val = sum(self.fast_ma) / len(self.fast_ma)
        slow_val = sum(self.slow_ma) / len(self.slow_ma)

        if fast_val > slow_val and self.pos == 0:
            self.buy(bar.close_price, 1)       # vnpy 的内置方法——有完整的订单管理
        elif fast_val < slow_val and self.pos > 0:
            self.sell(bar.close_price, abs(self.pos))
```

**关键对比**：

| | 你的 BaseStrategy | vnpy CtaTemplate |
|---|---|---|
| 下单 | `self._send_order(symbol, dir, price, qty)` | `self.buy(price, volume)` / `self.sell(price, volume)` |
| 撤单 | 没有 | `self.cancel_all()` |
| 成交回调 | 没有 | `self.on_trade(trade)` 自动触发 |
| 订单回调 | 没有 | `self.on_order(order)` 自动触发 |
| 持仓查询 | `self._positions` 手动维护 | `self.pos` 自动更新 |
| 风控 | 自己写的 RiskEngine | vnpy 内置 RiskManager |
| 回测 | 自己写的 backtest.py | vnpy 内置 CtaBacktester |

**迁移清单**：
- [ ] `strategies/vnpy_ma_cross.py` — MA 交叉策略，继承 CtaTemplate
- [ ] `strategies/vnpy_rsi.py` — RSI 策略，继承 CtaTemplate
- [ ] `strategies/vnpy_macd.py` — MACD 策略，继承 CtaTemplate

### Phase 3 — 删除自建执行层（30 分钟）

**保留**：
- `research/` 全部（data_loader, backtest, walk_forward）
- `config/` 配置（settings.py + YAML）
- `data/database.py`（SQLite 日志——vnpy 不带这个）
- `monitor/` 健康检查 + 通知
- `AGENTS.md`

**删除**：
- `strategies/base_strategy.py`（被 vnpy CtaTemplate 替代）
- `data/live_engine.py`（被 vnpy EventEngine 替代）
- `risk/risk_engine.py`（被 vnpy RiskManager 替代——保留规则，映射到 vnpy 接口）
- `scripts/run_headless.py`（被 vnpy 的 `run.py` 替代）

### Phase 4 — 研究流水线补全（6 小时）

和 A02 的标准完全对齐：

- [ ] `research/walk_forward.py` — WF 验证框架
- [ ] `research/reports/SOTA.md` — SOTA 注册表
- [ ] `research/reports/TEMPLATE.md` — 候选报告模板
- [ ] `research/factor_ic.py` — 因子滚动 IC
- [ ] 对 MA/RSI/MACD 做消融实验，产出第一份候选报告

### Phase 5 — 运营基础设施（3 小时）

- [ ] `monitor/heartbeat.py` — CLI/JSON/HTTP 健康检查
- [ ] `./sota` / `./archived` / `./performance` — CLI 工具
- [ ] `strategies/registry.py` — 策略插件注册

## 迁移后的启动方式

```bash
# 1. OpenD 已登录

# 2. 启动 vnpy 主程序
python run.py

# 3. 在 vnpy GUI 中：点击 CTA 策略 → 添加策略 → 选择 VnpyMaCrossStrategy
#    或者用无头模式：
python run.py --no-ui --strategy VnpyMaCrossStrategy --symbol US.NVDA

# 4. 另一个终端看表现
python monitor/heartbeat.py
./performance
```

## 硬性约束

- 迁移阶段所有交易设为 SIMULATE（模拟盘），不做真实交易
- `research/` 目录一个文件都不删——这是你的护城河
- 旧代码不删——移入 `_archived/` 作为参考
- vnpy 的 CtaBacktester 保留不删，但你的 backtest.py 作为**消融验证专用引擎**继续使用
- Git 保持小粒度提交，每个 Phase 一个 commit

## 风险

| 风险 | 缓解 |
|------|------|
| vnpy 版本兼容性 | 锁定 vnpy==2.9.x 版本在 requirements.txt |
| CtaTemplate API 变化 | 策略只使用 `on_bar`, `buy`, `sell`, `pos` 四个最稳定的 API |
| 你的 backtest.py 和 vnpy CtaBacktester 结果不一致 | 双引擎交叉验证——差异超过 5% 暂停迁移 |
| Futu 模拟盘限量 | 美股模拟盘每天有限额，超了会自动拒绝——不是 bug |
