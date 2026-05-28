#!/usr/bin/env python3
# =============================================================================
# 数据库初始化脚本
# =============================================================================
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import Database

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    print("[init_db] 正在初始化 SQLite 数据库...")
    db = Database()
    db.init_schema()
    print("[init_db] 数据库初始化完成。")
    db.close()

if __name__ == "__main__":
    main()
