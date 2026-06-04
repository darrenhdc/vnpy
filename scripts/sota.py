#!/usr/bin/env python3
# =============================================================================
# CLI: sota —— 查看和更新 SOTA 状态
# =============================================================================
"""
使用示例:
    ./scripts/sota.py status           # 查看当前 SOTA
    ./scripts/sota.py list             # 列出所有候选策略
    ./scripts/sota.py promote ma_cross  # 将候选提升为 SOTA (手动)
    ./scripts/sota.py history          # 查看演化史
"""
import sys
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SOTA_PATH = PROJECT_ROOT / "research" / "SOTA.md"


def _read_sota() -> str:
    if not SOTA_PATH.exists():
        return "SOTA.md not found"
    return SOTA_PATH.read_text(encoding="utf-8")


def cmd_status():
    content = _read_sota()
    lines = content.split("\n")
    # Print rules
    for line in lines:
        if line.startswith("> "):
            print(line)
        if "## 当前 SOTA" in line:
            break

    # Print SOTA header + table
    in_table = False
    seen_table = False
    for line in lines:
        if "## 当前 SOTA" in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("|"):
                seen_table = True
                print(line)
            elif seen_table and line.strip() == "":
                break
            elif not seen_table:
                continue
            else:
                break


def cmd_list():
    content = _read_sota()
    # 提取候选策略池区域
    lines = content.split("\n")
    in_pool = False
    print("候选策略池:")
    for line in lines:
        if "候选策略池" in line:
            in_pool = True
            continue
        if in_pool and line.startswith("|") and "状态" not in line and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6 and parts[1]:
                print(f"  {parts[1]:20s} {parts[2]:12s} {parts[3]:8s} {parts[4]}")
        elif in_pool and line.startswith("##"):
            break


def cmd_history():
    content = _read_sota()
    print("演化史:")
    in_history = False
    for line in content.split("\n"):
        if "演化史" in line:
            in_history = True
            continue
        if in_history and line.startswith("###"):
            print(f"\n{line}")
        elif in_history and line.strip():
            print(f"  {line}")
        elif in_history and not line.strip():
            break


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SOTA 管理工具")
    parser.add_argument("command", choices=["status", "list", "history"],
                        help="status: 查看当前 SOTA; list: 候选池; history: 演化史")
    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "list":
        cmd_list()
    elif args.command == "history":
        cmd_history()


if __name__ == "__main__":
    main()
