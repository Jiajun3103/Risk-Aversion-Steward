import os
import sqlite3
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取当前脚本文件所在的目录 (即 backend 文件夹)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 从 .env 读取数据库文件名，如果没有配置则默认使用 steward.db
DB_NAME = os.getenv("DATABASE_NAME", "steward.db")
db_path = os.path.join(BASE_DIR, DB_NAME)


def init_database():
    # 连接到数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 创建仓库物件表 (Inventory)
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
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # 2. 创建交易流水表 (Transactions)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,   
        type TEXT CHECK(type IN ('IN', 'OUT')), 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # 3. 创建供应商表 (Suppliers)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        contact_email TEXT,
        lead_time INTEGER,       
        risk_score INTEGER       
    )
    """
    )

    # 4. 创建用户账号表 (Users)
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

    # --- 清理旧数据（可选，方便调试看新效果） ---
    cursor.execute("DELETE FROM inventory")
    cursor.execute("DELETE FROM suppliers")
    cursor.execute("DELETE FROM transactions")

    # --- 插入初始测试数据 ---

    # 1. 插入库存 (包含 Location)
    inventory_data = [
        ('SKU-1024', 'Wireless Earbuds Pro', 15, 4.2, 'Shelf-A1'),
        ('SKU-2048', 'Mechanical Keyboard', 80, 1.2, 'Shelf-B2'),
        ('SKU-3099', 'USB-C Fast Charger', 5, 10.5, 'Bin-04'),
        ('SKU-7044', 'Legacy Speaker', 120, 0.1, 'Warehouse-Back')
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO inventory (sku, name, stock, daily_sales, location) VALUES (?, ?, ?, ?, ?)",
        inventory_data
    )

    # 2. 插入多个供应商 (Supply Chain Health 的数据源)
    suppliers_data = [
        ('Xinda Tech', 'order@xinda.com', 7, 85),          # 高风险
        ('Global Logistics Co.', 'support@global.com', 14, 25), # 低风险
        ('Fast Chip Solutions', 'sales@fastchip.com', 3, 15),  # 极安全
        ('Budget Components', 'info@budget.com', 21, 92)      # 极高风险
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES (?, ?, ?, ?)",
        suppliers_data
    )

    # 3. 插入交易流水 (用于 Report 和 AI)
    transactions_data = [
        ('SKU-1024', -30, 'OUT'),
        ('SKU-1024', -20, 'OUT'),
        ('SKU-2048', 50, 'IN'),
        ('SKU-3099', -100, 'OUT'), # 模拟爆款出货
        ('SKU-3099', -50, 'OUT')
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO transactions (sku, quantity, type) VALUES (?, ?, ?)",
        transactions_data
    )

    conn.commit()
    conn.close()
    print(f"Database '{DB_NAME}' enriched with supplier and location data!")


if __name__ == "__main__":
    init_database()