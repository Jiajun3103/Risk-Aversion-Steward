import os
import sqlite3
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get the directory of the current script (i.e., the backend folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.getenv("DATABASE_NAME", "steward.db")
db_path = os.path.join(BASE_DIR, DB_NAME)

def init_database():
    print(f"Initializing database at path: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- 1. Hard reset: Drop old tables (to ensure schema updates) ---
    tables =[
        "inventory", "transactions", "suppliers", 
        "users", "action_queue", "orders", "notification_logs"
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    # --- 2. Create table schemas ---

    # Warehouse Inventory Table
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

    # Transaction Log Table (Core of the Report function)
    cursor.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,   -- Positive for IN (restock), Negative for OUT (sales/deduction)
        type TEXT CHECK(type IN ('IN', 'OUT')), 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # Suppliers Table
    cursor.execute("""
    CREATE TABLE suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        contact_email TEXT,
        lead_time INTEGER,       
        risk_score INTEGER       
    )""")

    # Users Table
    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # Automated Action Queue Table
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

    # Demo Orders Table (Used for Return Guard)
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

    # Email/Notification Logs Table
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

    # --- 3. Insert Initial Test Data ---

    # Insert inventory (Note the exact SKU formatting)
    inventory_data =[
        ('SKU-1024', 'Wireless Earbuds Pro', 15, 4.2, 35.0, 'Shelf-A1', 1),
        ('SKU-2048', 'Mechanical Keyboard', 80, 1.2, 120.0, 'Shelf-B2', 2),
        ('SKU-3099', 'USB-C Fast Charger', 5, 10.5, 15.0, 'Bin-04', 1),
        ('SKU-7044', 'Legacy Speaker', 120, 0.1, 55.0, 'Warehouse-Back', 2)
    ]
    cursor.executemany(
        "INSERT INTO inventory (sku, name, stock, daily_sales, cost_price, location, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        inventory_data
    )

    # Insert transaction data (SKUs must perfectly match those above)
    transactions_data =[
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

    # Insert suppliers
    suppliers_data =[
        ('Xinda Tech', 'order@xinda.com', 7, 85),
        ('Global Logistics Co.', 'support@global.com', 14, 25),
        ('Fast Chip Solutions', 'sales@fastchip.com', 3, 15),
        ('Budget Components', 'info@budget.com', 21, 92)
    ]
    cursor.executemany(
        "INSERT INTO suppliers (supplier_name, contact_email, lead_time, risk_score) VALUES (?, ?, ?, ?)",
        suppliers_data
    )

    # Insert demo orders
    cursor.execute("INSERT INTO orders (order_no, customer_name, sku, item_name) VALUES ('ORD-88421', 'Mr. Zhang', 'SKU-1024', 'Wireless Earbuds Pro')")
    cursor.execute("INSERT INTO orders (order_no, customer_name, sku, item_name) VALUES ('ORD-88435', 'Ms. Li', 'SKU-3099', 'USB-C Fast Charger')")

    conn.commit()
    conn.close()
    
    print(f"✅ Database '{DB_NAME}' initialized successfully!")
    print(f"   - Created {len(tables)} tables")
    print(f"   - Pre-filled inventory, suppliers, and transaction report data.")

if __name__ == "__main__":
    init_database()