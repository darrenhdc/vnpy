#!/usr/bin/env python3
# =============================================================================
# Heartbeat 监控 —— CLI/JSON/HTTP 健康检查
# =============================================================================
"""
支持三种输出模式:
- cli:    终端表格 (默认)
- json:   JSON 结构化输出，供外部系统消费
- http:   启动微型 HTTP 服务器 (端口可配)

使用示例:
    python monitor/heartbeat.py --mode cli
    python monitor/heartbeat.py --mode json
    python monitor/heartbeat.py --mode http --port 8080
"""
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from monitor.healthcheck import HealthChecker
from monitor.notifier import ConsoleNotifier

logger = logging.getLogger("heartbeat")


def heartbeat_cli(checker: HealthChecker) -> str:
    """终端表格输出。"""
    status = checker.run_full_check(gateway_connected=False)
    lines = [
        "╔══════════════════════════════════════════════════╗",
        "║           VNPY Heartbeat Report                  ║",
        f"║  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                         ║",
        "╠══════════════════════════════════════════════════╣",
        f"║  OpenD Reachable     {'✅ YES' if status.opend_reachable else '❌ NO ':>18}    ║",
        f"║  Gateway Connected   {'✅ YES' if status.gateway_connected else '❌ NO ':>18}    ║",
        f"║  Last Bar Time       {str(status.last_bar_time or 'N/A'):>18}    ║",
        f"║  Last Order Time     {str(status.last_order_update_time or 'N/A'):>18}    ║",
        f"║  Errors              {len(status.errors):>18}    ║",
        "╚══════════════════════════════════════════════════╝",
    ]
    if status.errors:
        lines.append("Errors:")
        for e in status.errors:
            lines.append(f"  - {e}")
    return "\n".join(lines)


def heartbeat_json(checker: HealthChecker) -> Dict[str, Any]:
    """JSON 结构化输出。"""
    status = checker.run_full_check(gateway_connected=False)
    return {
        "timestamp": datetime.now().isoformat(),
        "healthy": status.is_healthy(),
        "opend_reachable": status.opend_reachable,
        "gateway_connected": status.gateway_connected,
        "last_bar_time": status.last_bar_time.isoformat() if status.last_bar_time else None,
        "last_order_time": status.last_order_update_time.isoformat() if status.last_order_update_time else None,
        "errors": status.errors,
    }


def heartbeat_http(checker: HealthChecker, port: int):
    """启动 HTTP 服务器提供健康检查端点。"""
    try:
        from http.server import BaseHTTPRequestHandler, HTTPServer
    except ImportError:
        print("[Error] HTTP server not available")
        sys.exit(1)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                data = heartbeat_json(checker)
                body = json.dumps(data, ensure_ascii=False, indent=2).encode()
                self.send_response(200 if data["healthy"] else 503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"vnpy heartbeat server\nendpoints: /health\n")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            logger.info(format % args)

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Heartbeat] HTTP server started on http://0.0.0.0:{port}/health")
    print("  Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Heartbeat] Shutting down...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Heartbeat 健康检查")
    parser.add_argument("--mode", choices=["cli", "json", "http"], default="cli",
                        help="输出模式: cli(终端), json(JSON), http(HTTP 服务器)")
    parser.add_argument("--port", type=int, default=8080,
                        help="HTTP 模式监听端口 (默认 8080)")
    parser.add_argument("--opend-host", default="127.0.0.1")
    parser.add_argument("--opend-port", type=int, default=11111)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    checker = HealthChecker(
        opend_host=args.opend_host,
        opend_port=args.opend_port,
        notifier=ConsoleNotifier(),
    )

    if args.mode == "cli":
        print(heartbeat_cli(checker))
    elif args.mode == "json":
        print(json.dumps(heartbeat_json(checker), ensure_ascii=False, indent=2))
    elif args.mode == "http":
        heartbeat_http(checker, args.port)


if __name__ == "__main__":
    main()
