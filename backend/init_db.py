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
        location TEXT,
        supplier_id INTEGER,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # Add supplier_id to existing inventory table if upgrading an old DB
    try:
        cursor.execute('ALTER TABLE inventory ADD COLUMN supplier_id INTEGER')
    except Exception:
        pass  # column already exists

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
    """)
    # 订单表（用于 Return Guard 选择真实订单号）
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        sku TEXT,
        item_name TEXT,
        order_status TEXT DEFAULT 'delivered',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # 自动化动作队列表
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS action_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER NOT NULL,
        supplier_id INTEGER,
        issue_type TEXT NOT NULL,
        recommended_action TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        reviewed_at DATETIME,
        reviewed_by TEXT,
        remarks TEXT,
        recommendation TEXT,
        priority_score INTEGER,
        priority_level TEXT,
        explanation TEXT,
        estimated_impact TEXT
    )
    """
    )

    # 通知发送记录表
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS notification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        inventory_id INTEGER,
        action_queue_id INTEGER,
        type TEXT NOT NULL,
        subject TEXT,
        message TEXT,
        status TEXT NOT NULL,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        error_message TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_action_pending
    ON action_queue (inventory_id, issue_type)
    WHERE status = 'pending'
    """
    )

    # 插入一些初始测试数据（可选）
    cursor.execute(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES ('SKU-1024', 'Wireless Earbuds Pro', 45, 4.2, 35.00, 'A-01', 1)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES ('SKU-2033', 'USB-C Hub 7-Port', 12, 2.1, 18.50, 'B-12', 1)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES ('SKU-3071', 'Mechanical Keyboard', 67, 0.8, 45.00, 'A-03', 2)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES ('SKU-4015', 'Phone Stand Adjustable', 5, 1.5, 8.00, 'C-22', 1)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES ('SKU-5088', 'Noise Cancelling Headphones', 30, 3.5, 120.00, 'A-15', 2)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES ('Xinda Tech', 'order@xinda.com', 7, 85)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES ('TechMart Global', 'supply@techmart.com', 14, 45)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES ('QuickShip Asia', 'ops@quickship.asia', 3, 20)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO customers (account_name, email) VALUES ('John Doe', 'john@example.com')"
    )

    # Return Guard demo order seeds
    cursor.execute(
        "INSERT OR IGNORE INTO orders (order_no, customer_name, sku, item_name, order_status) VALUES ('ORD-88421', 'Mr. Zhang', 'SKU-1024', 'Wireless Earbuds Pro', 'delivered')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO orders (order_no, customer_name, sku, item_name, order_status) VALUES ('ORD-88435', 'Ms. Li', 'SKU-2033', 'USB-C Hub 7-Port', 'delivered')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO orders (order_no, customer_name, sku, item_name, order_status) VALUES ('ORD-88457', 'Alex Chen', 'SKU-4015', 'Phone Stand Adjustable', 'delivered')"
    )

    # 回填历史数据：若旧库已有这些 SKU，确保 supplier_id 和关键字段被更新
    cursor.execute("UPDATE inventory SET supplier_id=1, cost_price=35.00, location='A-01' WHERE sku='SKU-1024'")
    cursor.execute("UPDATE inventory SET supplier_id=1, cost_price=18.50, location='B-12' WHERE sku='SKU-2033'")
    cursor.execute("UPDATE inventory SET supplier_id=2, cost_price=45.00, location='A-03' WHERE sku='SKU-3071'")
    cursor.execute("UPDATE inventory SET supplier_id=1, cost_price=8.00, location='C-22' WHERE sku='SKU-4015'")
    cursor.execute("UPDATE inventory SET supplier_id=2, cost_price=120.00, location='A-15' WHERE sku='SKU-5088'")

    conn.commit()
    conn.close()
    print("Database 'steward.db' initialized successfully!")


if __name__ == "__main__":
    init_database()
