#!/usr/bin/env python3
# =============================================================================
# OpenD 连接测试脚本
# =============================================================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from futu import OpenQuoteContext, KLType, SubType
from config.settings import get_app_config

def test_opend_connection():
    """测试 OpenD 基本连接和行情订阅。"""
    config = get_app_config()
    opend = config.futu.get("opend", {})
    host = opend.get("host", "127.0.0.1")
    port = opend.get("port", 11111)

    print(f"[Test] 连接 OpenD: {host}:{port}")

    quote_ctx = OpenQuoteContext(host=host, port=port)

    # 测试获取市场状态
    ret, data = quote_ctx.get_global_state()
    if ret == 0:
        print(f"[Test] 全局状态获取成功: {data}")
    else:
        print(f"[Test] 全局状态获取失败: {ret}")

    # 订阅 AAPL 实时 K 线
    print("[Test] 订阅 US.AAPL 1分钟 K 线...")
    ret_sub, err_message = quote_ctx.subscribe(["US.AAPL"], [SubType.K_1M], subscribe_push=True)
    if ret_sub == 0:
        print("[Test] 订阅成功")
    else:
        print(f"[Test] 订阅失败: {err_message}")

    # 获取历史 K 线验证
    ret, data, page_req_key = quote_ctx.request_history_kline("US.AAPL", ktype=KLType.K_1M, num=5)
    if ret == 0:
        print(f"[Test] 历史 K 线获取成功 ({len(data)} 条):")
        print(data[["time_key", "open", "high", "low", "close", "volume"]].to_string(index=False))
    else:
        print(f"[Test] 历史 K 线获取失败: {data}")

    quote_ctx.close()
    print("[Test] 连接测试完成，OpenD 工作正常")

if __name__ == "__main__":
    test_opend_connection()
