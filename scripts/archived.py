#!/usr/bin/env python3
# =============================================================================
# CLI: archived —— 归档旧策略报告
# =============================================================================
"""
使用示例:
    ./scripts/archived.py --list              # 列出所有报告
    ./scripts/archived.py --archive ma_cross  # 将当前 SOTA 归档
    ./scripts/archived.py --clean 90          # 删除 90 天前的归档
"""
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_DIR = PROJECT_ROOT / "research" / "reports"
ARCHIVED_DIR = PROJECT_ROOT / "research" / "reports" / "archived"


def cmd_list():
    print("\n=== 活跃报告 ===")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.name == "archived":
            continue
        print(f"  {f.name}")

    if ARCHIVED_DIR.exists():
        print("\n=== 归档报告 ===")
        for f in sorted(ARCHIVED_DIR.glob("*.md")):
            print(f"  {f.name}")
    else:
        print("\n(无归档)")


def cmd_archive(strategy_name: str):
    ARCHIVED_DIR.mkdir(exist_ok=True)
    # 查找对应报告
    pattern = f"*{strategy_name}*"
    matched = list(REPORTS_DIR.glob(pattern))
    if not matched:
        print(f"[Error] 未找到策略 '{strategy_name}' 的报告")
        return

    for src in matched:
        if src.name.startswith("archived"):
            continue
        ts = datetime.now().strftime("%Y%m%d")
        dst = ARCHIVED_DIR / f"{ts}_{src.name}"
        shutil.copy2(src, dst)
        print(f"[Archived] {src.name} -> {dst.name}")


def cmd_clean(days: int):
    if not ARCHIVED_DIR.exists():
        print("(归档目录不存在)")
        return
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for f in ARCHIVED_DIR.glob("*.md"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            f.unlink()
            removed += 1
    print(f"[Clean] 删除了 {removed} 个 {days} 天前的归档报告")


def main():
    parser = argparse.ArgumentParser(description="归档管理工具")
    parser.add_argument("--list", action="store_true", help="列出报告")
    parser.add_argument("--archive", help="归档指定策略的报告")
    parser.add_argument("--clean", type=int, help="清理 N 天前的归档")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.archive:
        cmd_archive(args.archive)
    elif args.clean is not None:
        cmd_clean(args.clean)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
