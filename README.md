# 美股量化交易系统 (MVP)

基于 **Futu OpenAPI + vn.py / vnpy_futu** 的美股量化交易系统原型。

> ⚠️ **默认仅支持 Futu 模拟盘 (SIMULATE)。本系统不保证盈利，实盘需自行承担风险。**

---

## 项目目标

搭建一个可运行、可扩展、风险可控的交易系统 MVP：
- 支持 Futu 模拟盘交易美股股票/ETF
- 分钟级 K 线策略（双均线交叉示例）
- 严格的独立风控模块
- SQLite 数据持久化 + 标准日志
- pytest 单元测试覆盖

---

## 项目结构

```
.
├── config/                    # 配置文件
│   ├── futu.example.yaml      # Futu/OpenD 配置模板
│   ├── risk.example.yaml      # 风控配置模板
│   ├── strategy.example.yaml  # 策略配置模板
│   └── settings.py            # 配置读取模块
├── data/                      # 数据库
│   └── database.py            # SQLite 封装
├── risk/                      # 风控模块
│   └── risk_engine.py         # 独立风控引擎
├── strategies/                # 策略模块
│   └── moving_average_cross.py
├── monitor/                   # 监控与通知
│   ├── healthcheck.py
│   └── notifier.py
├── scripts/                   # 启动/工具脚本
│   ├── init_db.py             # 初始化数据库
│   ├── run_trader.py          # 启动交易入口 (GUI/最小模式)
│   └── run_headless.py        # 无头运行策略
├── tests/                     # pytest 测试
│   ├── test_config.py
│   ├── test_risk.py
│   ├── test_database.py
│   └── test_strategy.py
├── logs/                      # 运行时日志
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 安装步骤

### 1. 克隆/准备代码

确保您已安装 Python 3.10+：

```bash
python --version  # >= 3.10
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> **vn.py 安装说明**: 由于 `vnpy` 通常通过 whl 或源码安装，未直接写入 `requirements.txt`。如已安装 vn.py 和 `vnpy_futu`，GUI 模式将自动可用；否则系统以最小模式运行。

---

## Futu OpenD 准备步骤

1. **下载并安装 Futu OpenD**
   - 前往 [Futu OpenD 文档中心](https://www.futunn.com/OpenAPI) 下载对应平台的 OpenD。
2. **启动 OpenD 并登录**
   ```bash
   # macOS / Linux 示例
   ./FutuOpenD
   ```
   - 默认监听端口: `11111`
   - 确保您的 Futu 账号已开通美股交易权限。
3. **确认环境为模拟盘**
   - 在 Futu OpenD 配置或客户端中选择 **模拟盘 (Paper Trading)**。
   - 本系统 `config/futu.yaml` 中 `environment: SIMULATE` 为强制默认值。

---

## 复制 Example 配置

所有敏感配置均通过 `.example.yaml` 模板提供，**请勿将真实密码提交到版本控制**。

```bash
cd config
cp futu.example.yaml   futu.yaml
cp risk.example.yaml   risk.yaml
cp strategy.example.yaml strategy.yaml
```

根据您的环境修改：
- `futu.yaml`: OpenD host/port、交易密码（可选）、订阅标的
- `risk.yaml`: 单笔/持仓/日度风控阈值
- `strategy.yaml`: 策略参数（均线周期、交易数量等）

---

## 初始化数据库

```bash
python scripts/init_db.py
```

该命令会在 `data/trading.db` 创建所需的 SQLite 表：
- `market_bars`
- `strategy_signals`
- `orders`
- `trades`
- `positions`
- `account_snapshots`
- `risk_events`

---

## 运行测试

```bash
pytest
```

测试覆盖：
- 配置读取与模拟盘检查
- 风控拒单逻辑（金额、数量、类型、持仓、日度次数、信号冷却）
- SQLite schema 初始化和 CRUD
- 策略在 mock bar 下是否生成预期信号

> 测试无需连接真实 Futu OpenD。

---

## 启动模拟盘

### 最小模式（不依赖 vn.py GUI）

```bash
python scripts/run_trader.py --mode minimal
```

### 无头运行策略（后台运行）

```bash
python scripts/run_headless.py --symbols US.AAPL US.TSLA
```

### vn.py GUI 模式（需安装 vnpy + vnpy_futu）

```bash
python scripts/run_trader.py --mode gui
```

GUI 启动后会尝试连接 `vnpy_futu.FutuGateway`，加载行情和交易接口。

---

## 风控说明

风控模块 (`risk/risk_engine.py`) **完全独立于策略**。策略只能通过 `risk_engine.check_order(...)` 请求批准。

当前支持的风控规则：

| 规则 | 说明 |
|------|------|
| 单笔最大下单金额 | 默认 5,000 USD |
| 单笔最大/最小股数 | 默认最大 100 股 |
| 单标最大持仓金额 | 默认 20,000 USD |
| 总持仓标的上限 | 默认 10 个 |
| 单日最大下单次数 | 默认 50 次 |
| 信号冷却 | 默认 300 秒内同一标的禁止重复信号下单 |
| 必须有行情 | 无最新价格时禁止下单 |
| 订单类型白名单 | 默认仅允许 **LIMIT** 限价单 |
| 单日最大亏损 | 预留接口，MVP 未启用 |

所有风控拒绝都会：
1. 写入 `risk_events` 表
2. 记录到标准日志
3. 通过 `notifier` 输出告警

---

## 实盘前 Checklist

> ⚠️ **强烈建议：在模拟盘稳定运行至少 2 周后再考虑实盘。**

- [ ] 已充分理解策略逻辑和潜在风险
- [ ] 模拟盘交易结果符合预期
- [ ] 已阅读并理解 Futu OpenAPI 的费率、交易规则、限速
- [ ] 已确认 OpenD 运行环境为实盘，且账户有足够资金
- [ ] 已根据资金规模调整 `risk.yaml` 阈值
- [ ] 已配置 Telegram/Email 通知（扩展 notifier）
- [ ] 已备份数据库和日志
- [ ] 已准备紧急停止方案（如脚本中断、OpenD 断开）

---

## 重要警告

1. **默认只支持模拟盘 (SIMULATE)**。如需实盘，必须手动修改代码并确认风险。
2. **不保证盈利**。本系统为技术原型，策略示例仅用于演示框架能力。
3. **实盘需自行承担全部风险**。作者不对任何交易损失负责。
4. **请勿将密码/API Key 提交到 Git**。`config/*.yaml` 已默认忽略（请在 `.gitignore` 中添加）。

---

## 扩展计划

- [ ] 接入真实行情推送 (vn.py `on_tick` / `on_bar`)
- [ ] 支持更多券商网关 (IBKR, Tiger)
- [ ] 策略参数优化与回测模块
- [ ] Telegram / Email / Webhook 通知
- [ ] Web 监控面板
- [ ] 支持更多订单类型（止损、止盈）

---

## License

MIT / 仅供学习参考
