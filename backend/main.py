from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import sqlite3
import os

app = FastAPI()

# 必须添加这个，否则浏览器会因为安全原因拦截你的数据（CORS问题）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取当前脚本文件所在的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'steward.db')

def get_db_connection():
    # 确保连接的是 backend 文件夹里的那个 db
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/inventory")
async def get_inventory():
    conn = get_db_connection()
    # 查询库存小于 50 的风险产品（模拟断货预警）
    items = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    
    # 将数据库行转换为 JSON 格式
    return [dict(row) for row in items]


@app.get("/api/suppliers")
async def get_suppliers():
    conn = get_db_connection()
    try:
        suppliers = conn.execute(
            '''
            SELECT
                MIN(suppliers.id) AS id,
                suppliers.supplier_name,
                suppliers.contact_email,
                COUNT(inventory.id) AS supplied_item_count
            FROM suppliers
            LEFT JOIN inventory ON inventory.supplier_id = suppliers.id
            GROUP BY suppliers.supplier_name, suppliers.contact_email
            ORDER BY suppliers.supplier_name ASC
            '''
        ).fetchall()
        return [dict(row) for row in suppliers]
    finally:
        conn.close()


@app.get("/api/reports/summary")
async def get_reports_summary():
    conn = get_db_connection()
    try:
        summary = conn.execute(
            '''
            SELECT
                COUNT(*) AS total_skus,
                SUM(CASE WHEN stock <= 50 THEN 1 ELSE 0 END) AS low_stock_count,
                SUM(CASE WHEN daily_sales <= 1 THEN 1 ELSE 0 END) AS slow_moving_count,
                SUM(
                    CASE
                        WHEN daily_sales > 0 AND (stock / daily_sales) <= 15 THEN 1
                        ELSE 0
                    END
                ) AS urgent_risk_count
            FROM inventory
            '''
        ).fetchone()
        supplier_count = conn.execute(
            '''
            SELECT COUNT(*) AS supplier_count
            FROM (
                SELECT supplier_name, COALESCE(contact_email, '')
                FROM suppliers
                GROUP BY supplier_name, COALESCE(contact_email, '')
            )
            '''
        ).fetchone()

        total_skus = summary['total_skus'] or 0
        urgent_risk_count = summary['urgent_risk_count'] or 0

        return {
            'total_skus': total_skus,
            'low_stock_count': summary['low_stock_count'] or 0,
            'slow_moving_count': summary['slow_moving_count'] or 0,
            'supplier_count': supplier_count['supplier_count'] or 0,
            'risk_breakdown': {
                'urgent': urgent_risk_count,
                'stable': max(total_skus - urgent_risk_count, 0),
            },
        }
    finally:
        conn.close()

# 1. 定义接收的数据格式
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

# 2. 注册接口
@app.post("/api/register")
async def register_user(user: UserRegister):
    conn = get_db_connection()
    try:
        # 检查是否重复
        if conn.execute('SELECT 1 FROM users WHERE email=?', (user.email,)).fetchone():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        conn.execute('INSERT INTO users (username, email, password) VALUES (?,?,?)',
                     (user.username, user.email, user.password))
        conn.commit()
        return {"message": "Success"}
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# 在 main.py 中增加登录数据模型
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# 增加登录接口
@app.post("/api/login")
async def login_user(user: UserLogin):
    conn = get_db_connection()
    try:
        db_user = conn.execute('SELECT * FROM users WHERE email=? AND password=?',
                               (user.email, user.password)).fetchone()
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"username": db_user["username"]}
    finally:
        conn.close()




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)