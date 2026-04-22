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