import os
import sqlite3

# 获取当前脚本文件所在的目录 (即 backend 文件夹)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "steward.db")


def column_exists(cursor, table_name, column_name):
    columns = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(column[1] == column_name for column in columns)


def get_or_create_supplier(cursor, supplier_name, contact_email, lead_time, risk_score):
    existing = cursor.execute(
        """
        SELECT id FROM suppliers
        WHERE supplier_name = ? AND COALESCE(contact_email, '') = COALESCE(?, '')
        ORDER BY id ASC
        LIMIT 1
        """,
        (supplier_name, contact_email),
    ).fetchone()
    if existing:
        return existing[0]

    cursor.execute(
        """
        INSERT INTO suppliers (supplier_name, contact_email, lead_time, risk_score)
        VALUES (?, ?, ?, ?)
        """,
        (supplier_name, contact_email, lead_time, risk_score),
    )
    return cursor.lastrowid


def deduplicate_suppliers(cursor):
    duplicate_groups = cursor.execute(
        """
        SELECT supplier_name, COALESCE(contact_email, '') AS contact_email
        FROM suppliers
        GROUP BY supplier_name, COALESCE(contact_email, '')
        HAVING COUNT(*) > 1
        """
    ).fetchall()

    for supplier_name, contact_email in duplicate_groups:
        supplier_rows = cursor.execute(
            """
            SELECT id FROM suppliers
            WHERE supplier_name = ? AND COALESCE(contact_email, '') = ?
            ORDER BY id ASC
            """,
            (supplier_name, contact_email),
        ).fetchall()
        canonical_id = supplier_rows[0][0]
        duplicate_ids = [row[0] for row in supplier_rows[1:]]

        for duplicate_id in duplicate_ids:
            cursor.execute(
                "UPDATE inventory SET supplier_id = ? WHERE supplier_id = ?",
                (canonical_id, duplicate_id),
            )
            cursor.execute("DELETE FROM suppliers WHERE id = ?", (duplicate_id,))


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
        supplier_id INTEGER,
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

    if not column_exists(cursor, "inventory", "supplier_id"):
        cursor.execute("ALTER TABLE inventory ADD COLUMN supplier_id INTEGER")

    deduplicate_suppliers(cursor)

    supplier_map = {}
    suppliers = [
        ("Xinda Tech", "order@xinda.com", 7, 85),
        ("Nova Mobile Parts", "supply@novamobile.com", 10, 62),
        ("Horizon Audio", "sales@horizonaudio.com", 14, 48),
    ]
    for supplier in suppliers:
        supplier_id = get_or_create_supplier(cursor, *supplier)
        supplier_map[supplier[0]] = supplier_id

    deduplicate_suppliers(cursor)

    # 插入一些初始测试数据（可选）
    inventory_items = [
        (
            "SKU-1024",
            "Wireless Earbuds Pro",
            45,
            4.2,
            32.5,
            supplier_map.get("Xinda Tech"),
            "A-01",
        ),
        (
            "SKU-2088",
            "Portable Charger Max",
            18,
            1.2,
            21.0,
            supplier_map.get("Nova Mobile Parts"),
            "B-14",
        ),
        (
            "SKU-7044",
            "Legacy Speaker",
            120,
            0.4,
            48.0,
            supplier_map.get("Horizon Audio"),
            "C-03",
        ),
        (
            "SKU-5501",
            "Phone Case Red",
            9,
            0.8,
            4.5,
            supplier_map.get("Nova Mobile Parts"),
            "B-02",
        ),
    ]
    for item in inventory_items:
        cursor.execute(
            """
            INSERT OR IGNORE INTO inventory (
                sku,
                name,
                stock,
                daily_sales,
                cost_price,
                supplier_id,
                location
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            item,
        )

    cursor.execute(
        """
        UPDATE inventory
        SET supplier_id = COALESCE(supplier_id, ?)
        WHERE sku = 'SKU-1024'
        """,
        (supplier_map.get("Xinda Tech"),),
    )

    cursor.execute(
        "INSERT OR IGNORE INTO customers (account_name, email) VALUES ('John Doe', 'john@example.com')"
    )

    conn.commit()
    conn.close()
    print("Database 'steward.db' initialized successfully!")


if __name__ == "__main__":
    init_database()
