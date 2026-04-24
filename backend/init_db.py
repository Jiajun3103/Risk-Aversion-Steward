import os
import sqlite3
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取当前脚本文件所在的目录 (即 backend 文件夹)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.getenv("DATABASE_NAME", "steward.db")
db_path = os.path.join(BASE_DIR, DB_NAME)

def init_database():
    print(f"正在初始化数据库，路径: {db_path}")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- 1. 强力重置：删除旧表 (确保结构更新) ---
    tables = [
        "inventory", "transactions", "suppliers", 
        "users", "action_queue", "orders", "notification_logs"
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    # --- 2. 创建表结构 ---

    # 仓库库存表
    cursor.execute("""
    CREATE TABLE inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        stock INTEGER DEFAULT 0,
        daily_sales REAL DEFAULT 0,
        cost_price REAL DEFAULT 0.0,
        location TEXT,
        supplier_id INTEGER,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # 交易流水表 (Report 功能的核心)
    cursor.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,   -- 正数进货，负数出货
        type TEXT CHECK(type IN ('IN', 'OUT')), 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # 供应商表
    cursor.execute("""
    CREATE TABLE suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        contact_email TEXT,
        lead_time INTEGER,       
        risk_score INTEGER       
    )""")

    # 用户表
    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # 自动化任务队列表
    cursor.execute("""
    CREATE TABLE action_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER NOT NULL,
        supplier_id INTEGER,
        issue_type TEXT NOT NULL,
        recommended_action TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        recommendation TEXT,
        priority_score INTEGER,
        priority_level TEXT,
        explanation TEXT,
        estimated_impact TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        reviewed_at DATETIME,
        reviewed_by TEXT,
        remarks TEXT
    )""")

    # 演示订单表 (用于 Return Guard)
    cursor.execute("""
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        sku TEXT,
        item_name TEXT,
        order_status TEXT DEFAULT 'delivered',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # 邮件/通知日志表
    cursor.execute("""
    CREATE TABLE notification_logs (
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
    )""")

    # --- 3. 插入初始测试数据 ---

    # 插入库存 (注意 SKU 的格式)
    inventory_data = [
        ('SKU-1024', 'Wireless Earbuds Pro', 15, 4.2, 35.0, 'Shelf-A1', 1),
        ('SKU-2048', 'Mechanical Keyboard', 80, 1.2, 120.0, 'Shelf-B2', 2),
        ('SKU-3099', 'USB-C Fast Charger', 5, 10.5, 15.0, 'Bin-04', 1),
        ('SKU-7044', 'Legacy Speaker', 120, 0.1, 55.0, 'Warehouse-Back', 2)
    ]
    cursor.executemany(
        "INSERT INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        inventory_data
    )

    # 插入流水数据 (SKU 必须与上面完全对应)
    transactions_data = [
        ('SKU-1024', -30, 'OUT'),
        ('SKU-1024', -20, 'OUT'),
        ('SKU-2048', 50, 'IN'),
        ('SKU-3099', -100, 'OUT'),
        ('SKU-3099', -50, 'OUT')
    ]
    cursor.executemany(
        "INSERT INTO transactions (sku, quantity, type) VALUES (?, ?, ?)",
        transactions_data
    )

    # 插入供应商
    suppliers_data = [
        ('Xinda Tech', 'order@xinda.com', 7, 85),
        ('Global Logistics Co.', 'support@global.com', 14, 25),
        ('Fast Chip Solutions', 'sales@fastchip.com', 3, 15),
        ('Budget Components', 'info@budget.com', 21, 92)
    ]
    cursor.executemany(
        "INSERT INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES (?, ?, ?, ?)",
        suppliers_data
    )

    # 插入演示订单
    cursor.execute("INSERT INTO orders (order_no, customer_name, sku, item_name) VALUES ('ORD-88421', 'Mr. Zhang', 'SKU-1024', 'Wireless Earbuds Pro')")
    cursor.execute("INSERT INTO orders (order_no, customer_name, sku, item_name) VALUES ('ORD-88435', 'Ms. Li', 'SKU-3099', 'USB-C Fast Charger')")

    conn.commit()
    conn.close()
    print(f"✅ 数据库 '{DB_NAME}' 已成功初始化！")
    print(f"   - 建立了 {len(tables)} 张表")
    print(f"   - 预填了库存、供应商和交易报表数据。")

if __name__ == "__main__":
    init_database()