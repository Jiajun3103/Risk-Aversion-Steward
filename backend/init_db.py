import os
import sqlite3

# 获取当前脚本文件所在的目录 (即 backend 文件夹)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "steward.db")


def init_database():
    # 连接到数据库（如果不存在则自动创建文件）
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建仓库物件表 (Inventory)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        stock INTEGER DEFAULT 0,
        daily_sales REAL DEFAULT 0,
        cost_price REAL,
        location TEXT,           -- 仓库位置
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # 创建供应商表 (Suppliers)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        contact_email TEXT,
        lead_time INTEGER,       -- 交货周期（天）
        risk_score INTEGER       -- 风险评分 0-100
    )
    """
    )

    # 创建客户账号表 (Customers)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT NOT NULL,
        email TEXT UNIQUE,
        total_orders INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active'  -- 账号状态：active/blocked
    )
    """
    )

    # 客户注册和登录
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # 插入一些初始测试数据（可选）
    cursor.execute(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales) VALUES ('SKU-1024', 'Wireless Earbuds Pro', 45, 4.2)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES ('Xinda Tech', 'order@xinda.com', 7, 85)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO customers (account_name, email) VALUES ('John Doe', 'john@example.com')"
    )

    conn.commit()
    conn.close()
    print("Database 'steward.db' initialized successfully!")


if __name__ == "__main__":
    init_database()
