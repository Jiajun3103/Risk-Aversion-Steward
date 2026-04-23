import os
import sqlite3
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from zhipuai import ZhipuAI
from dotenv import load_dotenv

# 1. 加载 .env 配置文件
load_dotenv()

app = FastAPI()

# 2. CORS 配置：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 从 .env 获取配置
ZHIPU_AI_KEY = os.getenv("ZHIPU_AI_KEY")
DB_NAME = os.getenv("DATABASE_NAME", "steward.db")

# 强制指定模型名称
AI_MODEL = "ilmu-glm-5.1"

# 4. 初始化 Z.AI 客户端
client = ZhipuAI(api_key=ZHIPU_AI_KEY)

# 5. 获取数据库路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, DB_NAME)

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- 数据模型 (Pydantic Models) ---
class StockUpdate(BaseModel):
    sku: str
    quantity: int  # 正数进货，负数出货
    type: str      # "IN" 或 "OUT"

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# --- 核心业务接口 ---

# A. 获取库存列表 (Dashboard 数据源)
@app.get("/api/inventory")
async def get_inventory():
    conn = get_db_connection()
    try:
        items = conn.execute('SELECT * FROM inventory').fetchall()
        return [dict(row) for row in items]
    finally:
        conn.close()

# B. 进出货记录 (支持 "Fix Stock Now" 和 "Record Sale")
@app.post("/api/stock-move")
async def stock_movement(data: StockUpdate):
    conn = get_db_connection()
    try:
        # 1. 更新 inventory 表中的 stock 数量
        cursor = conn.execute(
            'UPDATE inventory SET stock = stock + ? WHERE sku = ?', 
            (data.quantity, data.sku)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product SKU not found")
        
        # 2. 在 transactions 表中记录流水
        conn.execute(
            'INSERT INTO transactions (sku, quantity, type) VALUES (?, ?, ?)', 
            (data.sku, data.quantity, data.type)
        )
        conn.commit()
        return {"status": "success", "message": f"Recorded {data.type} for {data.sku}"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# C. 供应商健康看板 (修复“Supply Chain Health 为空”的问题)
@app.get("/api/suppliers")
async def get_suppliers():
    conn = get_db_connection()
    try:
        # 从数据库中抓取所有供应商信息
        items = conn.execute('SELECT * FROM suppliers').fetchall()
        return [dict(row) for row in items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# D. 进出货历史报表
@app.get("/api/reports")
async def get_reports():
    conn = get_db_connection()
    try:
        # 联表查询，获取产品名称
        query = '''
            SELECT t.*, i.name 
            FROM transactions t 
            JOIN inventory i ON t.sku = i.sku 
            ORDER BY t.timestamp DESC LIMIT 50
        '''
        items = conn.execute(query).fetchall()
        return [dict(row) for row in items]
    finally:
        conn.close()

# E. 删除单条流水记录 (Audit Cleanup)
@app.delete("/api/transactions/{log_id}")
async def delete_log(log_id: int):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM transactions WHERE id = ?', (log_id,))
        conn.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- AI 决策支持接口 (ILMU-GLM-5.1) ---

# F. 全局销量预测
@app.get("/api/predict")
async def predict_sales():
    if not ZHIPU_AI_KEY:
        return {"prediction": "AI Error: API Key missing in .env"}
    
    conn = get_db_connection()
    inventory = conn.execute('SELECT sku, name, stock, daily_sales FROM inventory').fetchall()
    sales = conn.execute('SELECT sku, SUM(ABS(quantity)) as total_sold FROM transactions WHERE type="OUT" GROUP BY sku').fetchall()
    conn.close()

    context = {
        "current_inventory": [dict(r) for r in inventory],
        "sales_history": [dict(r) for r in sales]
    }

    prompt = f"你是一个库存风控专家。分析以下库存和销售流水数据，告诉我哪些SKU是抢手货，并给出具体的补货或清仓建议：{json.dumps(context, ensure_ascii=False)}"

    try:
        response = client.chat.completions.create(
            model=AI_MODEL, 
            messages=[{"role": "user", "content": prompt}]
        )
        return {"prediction": response.choices[0].message.content}
    except Exception as e:
        return {"prediction": f"AI Prediction Failed: {str(e)}"}

# G. 单个产品风险分析 (View Risk)
@app.get("/api/risk-analysis/{sku}")
async def get_sku_risk_analysis(sku: str):
    if not ZHIPU_AI_KEY:
        raise HTTPException(status_code=500, detail="API Key missing")
    
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM inventory WHERE sku = ?', (sku,)).fetchone()
    # 模拟获取关联供应商
    supplier = conn.execute('SELECT * FROM suppliers LIMIT 1').fetchone()
    history = conn.execute('SELECT * FROM transactions WHERE sku = ? ORDER BY timestamp DESC LIMIT 5', (sku,)).fetchall()
    conn.close()

    if not item:
        raise HTTPException(status_code=404, detail="Product not found")

    diagnosis_data = {
        "product": dict(item),
        "supplier": dict(supplier) if supplier else "No supplier info",
        "recent_history": [dict(h) for h in history]
    }

    prompt = f"请深度诊断该SKU的风险（包含供应风险、断货风险及行动建议）：{json.dumps(diagnosis_data, ensure_ascii=False)}"

    try:
        response = client.chat.completions.create(
            model=AI_MODEL, 
            messages=[{"role": "user", "content": prompt}]
        )
        return {"sku": sku, "analysis": response.choices[0].message.content}
    except Exception as e:
        return {"analysis": f"AI Diagnosis Failed: {str(e)}"}

# --- 用户管理 ---

@app.post("/api/register")
async def register_user(user: UserRegister):
    conn = get_db_connection()
    try:
        if conn.execute('SELECT 1 FROM users WHERE email=?', (user.email,)).fetchone():
            raise HTTPException(status_code=400, detail="Email already exists")
        conn.execute('INSERT INTO users (username, email, password) VALUES (?,?,?)', 
                     (user.username, user.email, user.password))
        conn.commit()
        return {"message": "Success"}
    finally:
        conn.close()

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