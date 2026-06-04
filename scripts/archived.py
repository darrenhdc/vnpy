#!/usr/bin/env python3
"""
CLI: archived —— 归档旧策略报告
"""
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_DIR = PROJECT_ROOT / "research" / "reports"
ARCHIVED_DIR = REPORTS_DIR / "archived"

# ANSI
BOLD = "\033[1m"; DIM = "\033[2m"; RST = "\033[0m"
GREEN = "\033[32m"; YELLOW = "\033[33m"; CYAN = "\033[36m"; RED = "\033[31m"; WHITE = "\033[37m"


def c(text, *codes):
    return "".join(codes) + text + RST


def _color_report(name):
    if "ABLATION" in name:
        return c(name, YELLOW)
    elif "CANDIDATE" in name:
        return c(name, GREEN)
    elif "IDEA" in name:
        return c(name, CYAN)
    return c(name, WHITE)


def cmd_list():
    print()
    print(c("▐  Reports", BOLD, CYAN))

    active = [f for f in sorted(REPORTS_DIR.glob("*.md")) if f.name != "archived"]
    if active:
        print(c(f"  Active ({len(active)})", BOLD))
        for f in active:
            print(f"    {_color_report(f.name)}")
    else:
        print(c("  (no active reports)", DIM))

    if ARCHIVED_DIR.exists():
        archived = sorted(ARCHIVED_DIR.glob("*.md"))
        if archived:
            print()
            print(c(f"  Archived ({len(archived)})", DIM))
            for f in archived:
                print(c(f"    {f.name}", DIM))
        else:
            print()
            print(c("  (no archived reports)", DIM))
    else:
        print()
        print(c("  (no archived reports)", DIM))
    print()


def cmd_archive(strategy_name: str):
    ARCHIVED_DIR.mkdir(exist_ok=True)
    pattern = f"*{strategy_name}*"
    matched = list(REPORTS_DIR.glob(pattern))
    if not matched:
        print(c(f"[Error] No report matching '{strategy_name}'", RED))
        return

    for src in matched:
        if src.name.startswith("archived"):
            continue
        ts = datetime.now().strftime("%Y%m%d")
        dst = ARCHIVED_DIR / f"{ts}_{src.name}"
        shutil.copy2(src, dst)
        print(c(f"[Archived] {src.name} -> {dst.name}", GREEN))


def cmd_clean(days: int):
    if not ARCHIVED_DIR.exists():
        print(c("(archive dir not found)", DIM))
        return
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for f in ARCHIVED_DIR.glob("*.md"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            f.unlink()
            removed += 1
    print(c(f"[Clean] removed {removed} reports older than {days} days", YELLOW))


def main():
    parser = argparse.ArgumentParser(description="归档管理工具")
    parser.add_argument("--list", nargs="?", const="all", default=None,
                        help="列出报告")
    parser.add_argument("--archive", help="归档指定策略的报告")
    parser.add_argument("--clean", type=int, help="清理 N 天前的归档")
    args = parser.parse_args()

    if args.list is not None:
        cmd_list()
    elif args.archive:
        cmd_archive(args.archive)
    elif args.clean is not None:
        cmd_clean(args.clean)
    else:
        cmd_list()


if __name__ == "__main__":
    main()
