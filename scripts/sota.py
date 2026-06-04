#!/usr/bin/env python3
"""
CLI: sota —— 查看和更新 SOTA 状态
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SOTA_PATH = PROJECT_ROOT / "research" / "SOTA.md"

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
RST = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"


def c(text, *codes):
    prefix = "".join(codes)
    return f"{prefix}{text}{RST}"


def _read_sota() -> str:
    if not SOTA_PATH.exists():
        return "SOTA.md not found"
    return SOTA_PATH.read_text(encoding="utf-8")


def cmd_status():
    content = _read_sota()
    lines = content.split("\n")

    print()
    print(c("▐  SOTA", BOLD, CYAN))

    # Rules
    for line in lines:
        if line.startswith("> "):
            print(c(line, DIM))
        if "## 当前 SOTA" in line:
            break
    print()

    # Parse 2-column table (属性 | 值)
    in_table = False
    seen_rows = False
    for line in lines:
        if "## 当前 SOTA" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|") and "---" not in line and "属性" not in line:
            parts = [p.strip().replace("*", "") for p in line.split("|")]
            vals = [p for p in parts if p]
            if len(vals) >= 2:
                seen_rows = True
                k, v = vals[0], vals[1]
                val_color = WHITE
                if "Sharpe" in k and v:
                    try:
                        sv = float(v.split()[0])
                        if sv >= 1.5: val_color = GREEN
                        elif sv >= 1.0: val_color = YELLOW
                    except ValueError:
                        pass
                if "活跃状态" in k:
                    if "Paper" in v: val_color = GREEN
                    elif "Rejected" in v: val_color = RED
                if "ATR" in k: val_color = MAGENTA
                print(f"  {c(k, BOLD):<18}{c(v, val_color)}")
        elif seen_rows and line.strip() == "":
            break
    print()


def cmd_list():
    content = _read_sota()
    lines = content.split("\n")

    # Extract pool rows
    in_pool = False
    rows = []
    for line in lines:
        if "候选策略池" in line:
            in_pool = True
            continue
        if in_pool and line.startswith("|") and "状态" not in line and "---" not in line:
            parts = [p.strip().replace("*", "") for p in line.split("|")]
            vals = [p for p in parts if p]
            if len(vals) >= 4:
                rows.append({"name": vals[0], "status": vals[1], "sharpe": vals[2], "info": vals[3]})
        elif in_pool and rows and line.strip() == "":
            break

    print()
    print(c("▐  Candidate Pool", BOLD, CYAN))
    print(c(f"  {'Strategy':<24} {'Status':<12} {'Sharpe':<8} {'Note':<20}", DIM))
    print(f"  {'─' * 60}")

    for r in rows:
        status_color = GREEN if "Paper" in r["status"] or "SOTA" in r["status"] else \
                       YELLOW if "Research" in r["status"] else \
                       RED if "Reject" in r["status"] else WHITE
        sharpe_color = WHITE
        try:
            sv = float(r["sharpe"])
            if sv >= 1.5: sharpe_color = GREEN
            elif sv >= 1.0: sharpe_color = YELLOW
            elif sv > 0: sharpe_color = DIM
        except ValueError:
            pass

        name_s = r['name']
        status_s = r['status']
        sharpe_s = r['sharpe']
        print(f"  {c(name_s, BOLD):<30}{c(status_s, status_color):<15}{c(sharpe_s, sharpe_color):<12}{r['info']}")
    print()


def cmd_history():
    content = _read_sota()
    print()
    print(c("▐  Evolution", BOLD, CYAN))
    in_history = False
    for line in content.split("\n"):
        if "## 演化史" in line:
            in_history = True
            continue
        if in_history and line.startswith("###"):
            print(f"\n  {c(line, BOLD, YELLOW)}")
        elif in_history and line.strip() and line.startswith("- "):
            # Color key patterns
            line_colored = line
            if "升级" in line or "SOTA" in line: line_colored = c(line, GREEN)
            elif "失败" in line or "无效" in line or "不敌" in line: line_colored = c(line, RED, DIM)
            elif "突破" in line or "best" in line.lower() or "关键" in line: line_colored = c(line, YELLOW)
            print(f"    {line_colored}")
        elif in_history and not line.strip():
            break
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SOTA 管理工具")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "list", "history"],
                        help="status: 当前 SOTA; list: 候选池; history: 演化史")
    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "list":
        cmd_list()
    elif args.command == "history":
        cmd_history()


if __name__ == "__main__":
    main()
