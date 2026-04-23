from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import sqlite3
import os
import json
import math
from datetime import datetime, timezone
import requests as req
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from decision_engine import build_decision, analyse_return_text

# Load environment variables from backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

ZAI_API_KEY = os.getenv("ZAI_API_KEY")
ILMU_API_KEY = os.getenv("ILMU_API_KEY")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


AUTO_SEND_ON_APPROVAL = _env_bool("AUTO_SEND_ON_APPROVAL", False)

# Detection thresholds are configurable via env for easy tuning
LOW_STOCK_DAYS_THRESHOLD = int(os.getenv("LOW_STOCK_DAYS_THRESHOLD", "15"))
SLOW_MOVING_DAILY_SALES_THRESHOLD = float(os.getenv("SLOW_MOVING_DAILY_SALES_THRESHOLD", "1.0"))
SLOW_MOVING_STOCK_THRESHOLD = int(os.getenv("SLOW_MOVING_STOCK_THRESHOLD", "40"))
SLOW_MOVING_DAYS_LEFT_THRESHOLD = int(os.getenv("SLOW_MOVING_DAYS_LEFT_THRESHOLD", "45"))

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


def ensure_automation_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
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
            remarks TEXT
        )
        """
    )
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
    # Safe migration: add decision intelligence columns to existing action_queue tables
    new_columns = [
        ("recommendation", "TEXT"),
        ("priority_score", "INTEGER"),
        ("priority_level", "TEXT"),
        ("explanation", "TEXT"),
        ("estimated_impact", "TEXT"),
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE action_queue ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass  # column already exists

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

    # Lightweight demo seeds so Return Guard can always select an order
    cursor.execute(
        "INSERT OR IGNORE INTO orders (order_no, customer_name, sku, item_name, order_status) VALUES ('ORD-88421', 'Mr. Zhang', 'SKU-1024', 'Wireless Earbuds Pro', 'delivered')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO orders (order_no, customer_name, sku, item_name, order_status) VALUES ('ORD-88435', 'Ms. Li', 'SKU-2033', 'USB-C Hub 7-Port', 'delivered')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO orders (order_no, customer_name, sku, item_name, order_status) VALUES ('ORD-88457', 'Alex Chen', 'SKU-4015', 'Phone Stand Adjustable', 'delivered')"
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    ensure_automation_tables()


def _safe_num(value, default=0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def calc_days_left(stock: float, daily_sales: float) -> float:
    stock_v = max(0.0, _safe_num(stock, 0))
    sales_v = _safe_num(daily_sales, 0)
    return (stock_v / sales_v) if sales_v > 0 else float("inf")


def _low_stock_metrics(item: dict):
    """
    Low-stock rule:
      days_left = stock / daily_sales
      qualify when daily_sales > 0 and days_left <= 15
      reorder_qty = ceil(max(0, daily_sales*30 - stock))
    """
    stock = max(0.0, _safe_num(item.get("stock"), 0))
    daily_sales = _safe_num(item.get("daily_sales"), 0)
    price = max(0.0, _safe_num(item.get("cost_price"), 0))

    if daily_sales <= 0:
        return None

    days_left = calc_days_left(stock, daily_sales)
    if days_left > LOW_STOCK_DAYS_THRESHOLD:
        return None

    target_days = 30
    target_stock = daily_sales * target_days
    reorder_qty = max(0, math.ceil(target_stock - stock))
    if reorder_qty <= 0:
        return None

    # Consistent missed-sales rule across all low-stock actions.
    shortage_window = max(0.0, LOW_STOCK_DAYS_THRESHOLD - days_left)
    missed_units = max(0.0, shortage_window * daily_sales)
    revenue_at_risk = missed_units * price

    if days_left <= 3:
        severity = "HIGH"
    elif days_left <= 7:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "issue_type": "low_stock",
        "stock": stock,
        "daily_sales": daily_sales,
        "days_left": days_left,
        "reorder_qty": reorder_qty,
        "severity": severity,
        "missed_units": round(missed_units, 2),
        "revenue_at_risk": round(revenue_at_risk, 2),
    }


def _slow_moving_metrics(item: dict):
    """
    Slow-moving rule:
      days_to_clear = stock / daily_sales (or inf if daily_sales == 0)
      qualify when stock > 0 and (days_to_clear >= 45 or daily_sales == 0)
    """
    stock = max(0.0, _safe_num(item.get("stock"), 0))
    daily_sales = _safe_num(item.get("daily_sales"), 0)

    if stock <= 0:
        return None

    days_to_clear = (stock / daily_sales) if daily_sales > 0 else float("inf")
    qualifies = (daily_sales == 0 and stock > 0) or (days_to_clear >= SLOW_MOVING_DAYS_LEFT_THRESHOLD)
    if not qualifies:
        return None

    if (daily_sales == 0 and stock > 0) or (days_to_clear >= 90):
        severity = "HIGH"
    elif days_to_clear >= 60:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "issue_type": "slow_moving",
        "stock": stock,
        "daily_sales": daily_sales,
        "days_to_clear": days_to_clear,
        "severity": severity,
    }


def detect_issue_types(item: dict) -> list:
    """
    Generate at most one action type to avoid contradictory recommendations.
    Priority rule:
      - if sales are zero/stagnant -> prefer slow_moving
      - if only low_stock qualifies -> low_stock
      - if only slow_moving qualifies -> slow_moving
    """
    low = _low_stock_metrics(item)
    slow = _slow_moving_metrics(item)

    if low and slow:
        # When both happen, prioritize the more relevant operational signal.
        if _safe_num(item.get("daily_sales"), 0) <= 0:
            return ["slow_moving"]
        if slow["severity"] == "HIGH" and low["severity"] != "HIGH":
            return ["slow_moving"]
        return ["low_stock"]

    if low:
        return ["low_stock"]
    if slow:
        return ["slow_moving"]
    return []


def build_recommended_action(item: dict, issue_type: str) -> str:
    low = _low_stock_metrics(item)
    slow = _slow_moving_metrics(item)
    if issue_type == "low_stock":
        if not low:
            return "No reorder needed because current stock already covers target demand."
        return (
            f"Reorder {low['reorder_qty']} units immediately to cover 30 days of demand. "
            f"Current stock covers {low['days_left']:.2f} days; estimated missed units over shortage window: {low['missed_units']:.2f}."
        )
    if not slow:
        return "No slow-moving action needed at current velocity."
    if not math.isfinite(slow["days_to_clear"]):
        return "Run flash clearance or pause restocking. At current velocity, stock is stagnant (no sales)."
    return (
        f"Run flash clearance or pause restocking. At current velocity, full stock clearance takes {slow['days_to_clear']:.2f} days."
    )


def build_email_content(issue_type: str, supplier_name: str, item: dict, recommended_action: str):
    if issue_type == "low_stock":
        subject = f"Restock Request - {item['sku']} ({item['name']})"
        message = (
            f"Dear {supplier_name},\n\n"
            f"Our system detected a low-stock risk for {item['name']} ({item['sku']}).\n"
            f"Current stock: {item['stock']}\n"
            f"Daily sales: {item['daily_sales']}\n"
            f"Projected days left: {calc_days_left(item['stock'], item['daily_sales'])}\n\n"
            f"Requested action:\n{recommended_action}\n\n"
            "Please confirm the earliest restock schedule.\n\n"
            "Best regards,\nInventory Automation System"
        )
        return subject, message

    subject = f"Supply Review Notice - {item['sku']} ({item['name']})"
    message = (
        f"Dear {supplier_name},\n\n"
        f"Our system detected this item as slow-moving: {item['name']} ({item['sku']}).\n"
        f"Current stock: {item['stock']}\n"
        f"Daily sales: {item['daily_sales']}\n\n"
        f"Requested action:\n{recommended_action}\n\n"
        "Please review future supply planning for this item.\n\n"
        "Best regards,\nInventory Automation System"
    )
    return subject, message


def send_email_or_fallback(to_email: str, subject: str, message: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not to_email:
        return "skipped", "Missing supplier email"

    # Safe fallback for demo/runtime without email config
    if not smtp_host or not smtp_from:
        return "skipped", "SMTP not configured"

    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_email

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        if smtp_use_tls:
            server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, [to_email], msg.as_string())
        server.quit()
        return "sent", None
    except Exception as e:
        return "failed", str(e)


def log_notification(conn, supplier_id, inventory_id, action_queue_id, issue_type, subject, message, status, error_message=None):
    conn.execute(
        """
        INSERT INTO notification_logs
        (supplier_id, inventory_id, action_queue_id, type, subject, message, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (supplier_id, inventory_id, action_queue_id, issue_type, subject, message, status, error_message),
    )


def send_action_email_internal(action_id: int):
    conn = get_db_connection()
    try:
        action = conn.execute(
            """
            SELECT aq.*, i.sku, i.name, i.stock, i.daily_sales,
                   s.supplier_name, s.contact_email
            FROM action_queue aq
            LEFT JOIN inventory i ON aq.inventory_id = i.id
            LEFT JOIN suppliers s ON aq.supplier_id = s.id
            WHERE aq.id = ?
            """,
            (action_id,),
        ).fetchone()

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        a = dict(action)
        if a["status"] == "sent":
            # Guard against duplicate sends when action has already been sent.
            return {
                "action_id": a["id"],
                "notification_status": "already_sent",
                "error": None,
            }

        if a["status"] == "rejected":
            raise HTTPException(status_code=400, detail="Rejected action cannot send email")

        item = {
            "sku": a["sku"],
            "name": a["name"],
            "stock": a["stock"],
            "daily_sales": a["daily_sales"],
        }
        subject, message = build_email_content(
            a["issue_type"],
            a["supplier_name"] or "Supplier",
            item,
            a["recommended_action"],
        )

        send_status, send_error = send_email_or_fallback(a["contact_email"], subject, message)

        log_notification(
            conn,
            a["supplier_id"],
            a["inventory_id"],
            a["id"],
            a["issue_type"],
            subject,
            message,
            send_status,
            send_error,
        )

        if send_status == "sent":
            conn.execute(
                "UPDATE action_queue SET status = 'sent', reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (a["id"],),
            )

        conn.commit()
        return {
            "action_id": a["id"],
            "notification_status": send_status,
            "error": send_error,
        }
    finally:
        conn.close()

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


class ActionApproveRequest(BaseModel):
    reviewed_by: Optional[str] = "admin"
    remarks: Optional[str] = None
    send_email: bool = False


class ActionRejectRequest(BaseModel):
    reviewed_by: Optional[str] = "admin"
    remarks: Optional[str] = None

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


# ─── Local fallback: rule-based strategy generator ───────────────────────────
def _local_strategies(inventory_data: list) -> list:
    """Generate 2 strategies from inventory data without AI."""
    # Sort by days_left ascending (most urgent first)
    sorted_items = sorted(inventory_data, key=lambda x: x['days_left'])

    strategies = []
    strategy_pool = [
        ("BOGO", "Buy 1 Get 1 offer to accelerate sell-through and free up warehouse space quickly.", "HIGH", 0.85),
        ("Flash Bundle", "Bundle slow-moving units with top sellers to piggyback on high demand.", "MEDIUM", 0.78),
        ("Deep Discount", "Apply a 30-40% markdown to trigger immediate cash recovery before stock expires.", "HIGH", 0.91),
        ("Flash Sale", "48-hour limited-time sale to create urgency and clear excess units fast.", "MEDIUM", 0.82),
    ]

    used_skus = set()
    pool_index = 0
    for item in sorted_items:
        if item['sku'] in used_skus:
            continue
        s_name, s_desc, s_urgency, s_prob = strategy_pool[pool_index % len(strategy_pool)]
        estimated_recovery = round(item['stock'] * item['cost_price'] * 0.55, 2)
        strategies.append({
            "strategy_name": s_name,
            "target_sku": item['sku'],
            "target_name": item['name'],
            "description": f"{item['name']} has only {item['days_left']} days of stock left at current sales velocity. {s_desc}",
            "expected_recovery": f"${estimated_recovery:,.0f}",
            "success_probability": f"{int(s_prob * 100)}%",
            "urgency": s_urgency,
        })
        used_skus.add(item['sku'])
        pool_index += 1
        if len(strategies) == 2:
            break

    # Pad with generic entries if fewer than 2 items in DB
    while len(strategies) < 2:
        strategies.append({
            "strategy_name": "Review Needed",
            "target_sku": "N/A",
            "target_name": "No items found",
            "description": "Add more inventory items to receive AI-powered recommendations.",
            "expected_recovery": "$0",
            "success_probability": "N/A",
            "urgency": "LOW",
        })

    return strategies


# ─── Zhipu AI (GLM-4) Clearance Strategy Endpoint ────────────────────────────
@app.post("/api/ai/recommend")
def ai_recommend():
    # 1. 从数据库获取库存数据
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()

    inventory_data = [dict(row) for row in items]
    for item in inventory_data:
        item['days_left'] = (
            int(item['stock'] / item['daily_sales'])
            if item['daily_sales'] > 0 else 999
        )

    # 2. 构建 AI Prompt
    prompt = f"""You are an expert inventory liquidation analyst. Analyze this inventory and suggest exactly 2 clearance strategies to recover cash and reduce dead stock.

Inventory data:
{json.dumps(inventory_data, indent=2)}

Return ONLY a valid JSON array with exactly 2 strategy objects. Each object must have these exact keys:
- "strategy_name": short name like "BOGO", "Flash Bundle", "Deep Discount", "Bundle Deal", "Flash Sale"
- "target_sku": the SKU code to target
- "target_name": the product name
- "description": 1-2 sentences explaining why this strategy works for this item
- "expected_recovery": estimated dollar recovery (e.g. "$8,500")
- "success_probability": confidence percentage (e.g. "87%")
- "urgency": one of "HIGH", "MEDIUM", or "LOW"

Return ONLY the JSON array. No markdown, no explanation, no code blocks."""

    # 3. 调用 AI API（优先 ILMU，备选 Z.ai），失败时降级到本地算法
    ai_source = "ilmu-nemo"
    try:
        if ILMU_API_KEY:
            # ILMU OpenAI-compatible endpoint (hackathon key)
            api_key = ILMU_API_KEY
            api_url = "https://api.ilmu.ai/v1/chat/completions"
            model = "ilmu-glm-5.1"
            ai_source = "ilmu-glm-5.1"
        elif ZAI_API_KEY:
            # Z.ai fallback
            api_key = ZAI_API_KEY
            api_url = "https://api.z.ai/api/paas/v4/chat/completions"
            model = "glm-4-flash"
            ai_source = "z.ai-glm"
        else:
            raise RuntimeError("No AI key configured")

        response = req.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        ai_text = response.json()["choices"][0]["message"]["content"].strip()

        # 清理 AI 返回的 Markdown 代码块（如果有）
        if ai_text.startswith("```"):
            lines = ai_text.split("\n")
            ai_text = "\n".join(lines[1:-1])

        strategies = json.loads(ai_text)

    except Exception:
        # AI unavailable — fall back to rule-based engine
        strategies = _local_strategies(inventory_data)
        ai_source = "local-rules"

    return {"strategies": strategies, "source": ai_source}


# ─── Automation scan endpoint ─────────────────────────────────────────────────
@app.post("/api/actions/scan")
def scan_actions(trigger_source: str = "manual"):
    trigger_source = (trigger_source or "manual").lower()
    if trigger_source not in {"auto", "manual"}:
        trigger_source = "manual"

    conn = get_db_connection()
    created = 0
    duplicates = 0
    details = []
    scanned_at = datetime.now(timezone.utc).isoformat()

    print(f"[scan_actions] trigger_source={trigger_source} scanned_at={scanned_at}")
    try:
        items = conn.execute("SELECT * FROM inventory").fetchall()
        for row in items:
            item = dict(row)
            issue_types = detect_issue_types(item)
            for issue_type in issue_types:
                exists = conn.execute(
                    """
                    SELECT id FROM action_queue
                    WHERE inventory_id = ? AND issue_type = ? AND status = 'pending'
                    """,
                    (item["id"], issue_type),
                ).fetchone()

                if exists:
                    duplicates += 1
                    continue

                recommended_action = build_recommended_action(item, issue_type)
                # Build enriched decision record using the rule-based decision engine
                decision = build_decision(item, issue_type)
                conn.execute(
                    """
                    INSERT INTO action_queue
                        (inventory_id, supplier_id, issue_type, recommended_action, status,
                         recommendation, priority_score, priority_level, explanation, estimated_impact)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"], item.get("supplier_id"), issue_type, recommended_action,
                        decision["recommendation"], decision["priority_score"],
                        decision["priority_level"], decision["explanation"], decision["estimated_impact"],
                    ),
                )
                created += 1
                details.append({
                    "inventory_id": item["id"], "sku": item["sku"],
                    "issue_type": issue_type, "priority_level": decision["priority_level"],
                })

        conn.commit()
        return {
            "created": created,
            "actions_created": created,
            "duplicates_skipped": duplicates,
            "scanned_at": scanned_at,
            "trigger_source": trigger_source,
            "thresholds": {
                "low_stock_days": LOW_STOCK_DAYS_THRESHOLD,
                "slow_moving_daily_sales": SLOW_MOVING_DAILY_SALES_THRESHOLD,
                "slow_moving_stock": SLOW_MOVING_STOCK_THRESHOLD,
                "slow_moving_days_left": SLOW_MOVING_DAYS_LEFT_THRESHOLD,
            },
            "items": details,
        }
    finally:
        conn.close()


# ─── Action queue admin workflow endpoints ───────────────────────────────────
@app.get("/api/actions/pending")
def get_pending_actions():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT aq.*, i.sku, i.name, i.stock, i.daily_sales,
                   s.supplier_name, s.contact_email
            FROM action_queue aq
            LEFT JOIN inventory i ON aq.inventory_id = i.id
            LEFT JOIN suppliers s ON aq.supplier_id = s.id
            WHERE aq.status = 'pending'
            ORDER BY aq.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/actions/{action_id}/approve")
def approve_action(action_id: int, payload: ActionApproveRequest):
    conn = get_db_connection()
    try:
        action = conn.execute("SELECT * FROM action_queue WHERE id = ?", (action_id,)).fetchone()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        if action["status"] in ["rejected", "sent"]:
            raise HTTPException(status_code=400, detail=f"Action already {action['status']}")

        conn.execute(
            """
            UPDATE action_queue
            SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?, remarks = ?
            WHERE id = ?
            """,
            (payload.reviewed_by, payload.remarks, action_id),
        )
        conn.commit()

        send_result = None
        should_send = payload.send_email or AUTO_SEND_ON_APPROVAL
        if should_send:
            send_result = send_action_email_internal(action_id)
            print(
                f"[approve_action] action_id={action_id} auto_send_enabled={AUTO_SEND_ON_APPROVAL} "
                f"requested_send={payload.send_email} send_status={send_result.get('notification_status') if send_result else None}"
            )

        return {
            "message": "Action approved",
            "action_id": action_id,
            "send_result": send_result,
            "auto_send_on_approval": AUTO_SEND_ON_APPROVAL,
        }
    finally:
        conn.close()


@app.post("/api/actions/{action_id}/reject")
def reject_action(action_id: int, payload: ActionRejectRequest):
    conn = get_db_connection()
    try:
        action = conn.execute("SELECT * FROM action_queue WHERE id = ?", (action_id,)).fetchone()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        if action["status"] == "sent":
            raise HTTPException(status_code=400, detail="Sent action cannot be rejected")

        conn.execute(
            """
            UPDATE action_queue
            SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?, remarks = ?
            WHERE id = ?
            """,
            (payload.reviewed_by, payload.remarks, action_id),
        )
        conn.commit()
        return {"message": "Action rejected", "action_id": action_id}
    finally:
        conn.close()


@app.post("/api/actions/{action_id}/send-email")
def send_action_email(action_id: int):
    conn = get_db_connection()
    try:
        action = conn.execute("SELECT status FROM action_queue WHERE id = ?", (action_id,)).fetchone()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        if action["status"] == "rejected":
            raise HTTPException(status_code=400, detail="Rejected action cannot send email")
        if action["status"] == "pending":
            raise HTTPException(status_code=400, detail="Approve action before sending email")
    finally:
        conn.close()

    return send_action_email_internal(action_id)


@app.get("/api/orders")
def get_orders():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, order_no, customer_name, sku, item_name, order_status, created_at
            FROM orders
            ORDER BY datetime(created_at) DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Suppliers endpoint ───────────────────────────────────────────────────────
@app.get("/api/suppliers")
def get_suppliers():
    conn = get_db_connection()
    suppliers = conn.execute('SELECT * FROM suppliers').fetchall()
    grouped = {}
    for s in suppliers:
        s_dict = dict(s)
        count = conn.execute(
            'SELECT COUNT(*) as cnt FROM inventory WHERE supplier_id = ?', (s_dict['id'],)
        ).fetchone()
        key = (s_dict['supplier_name'], s_dict['contact_email'])
        if key not in grouped:
            grouped[key] = {
                'id': s_dict['id'],
                'supplier_name': s_dict['supplier_name'],
                'contact_email': s_dict['contact_email'],
                'lead_time': s_dict['lead_time'],
                'risk_score': s_dict['risk_score'],
                'item_count': 0,
                'pending_alerts': 0,
            }
        grouped[key]['item_count'] += count['cnt'] if count else 0
        pending_alerts = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM action_queue
            WHERE supplier_id = ? AND status IN ('pending', 'approved')
            """,
            (s_dict['id'],),
        ).fetchone()
        grouped[key]['pending_alerts'] += pending_alerts['cnt'] if pending_alerts else 0
    conn.close()
    return list(grouped.values())


@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    conn = get_db_connection()
    try:
        items = conn.execute("SELECT * FROM inventory").fetchall()
        inventory_data = [dict(row) for row in items]
        for item in inventory_data:
            item['days_left'] = calc_days_left(item['stock'], item['daily_sales'])

        active_skus = len(inventory_data)
        low_stock_items = sum(1 for i in inventory_data if i['days_left'] <= LOW_STOCK_DAYS_THRESHOLD)
        slow_moving_items = sum(
            1
            for i in inventory_data
            if (
                i['stock'] >= SLOW_MOVING_STOCK_THRESHOLD
                and i['daily_sales'] <= SLOW_MOVING_DAILY_SALES_THRESHOLD
                and i['days_left'] >= SLOW_MOVING_DAYS_LEFT_THRESHOLD
            )
        )
        supplier_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM (SELECT supplier_name, contact_email FROM suppliers GROUP BY supplier_name, contact_email)"
        ).fetchone()['cnt']
        at_risk_capital = sum((i['stock'] or 0) * (i['cost_price'] or 0) for i in inventory_data if i['days_left'] <= LOW_STOCK_DAYS_THRESHOLD)
        pending_actions = conn.execute("SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'pending'").fetchone()['cnt']

        return {
            'active_skus': active_skus,
            'low_stock_items': low_stock_items,
            'slow_moving_items': slow_moving_items,
            'supplier_count': supplier_count,
            'at_risk_capital': round(at_risk_capital, 2),
            'pending_actions': pending_actions,
        }
    finally:
        conn.close()


# ─── Reports summary endpoint ─────────────────────────────────────────────────
@app.get("/api/reports/summary")
def get_report_summary():
    conn = get_db_connection()
    try:
        items = conn.execute('SELECT * FROM inventory').fetchall()
        supplier_count = conn.execute(
            'SELECT COUNT(*) as cnt FROM (SELECT supplier_name, contact_email FROM suppliers GROUP BY supplier_name, contact_email)'
        ).fetchone()['cnt']

        inventory_data = [dict(row) for row in items]
        for item in inventory_data:
            item['days_left'] = (
                int(item['stock'] / item['daily_sales'])
                if item['daily_sales'] > 0 else 999
            )

        pending_actions = conn.execute("SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'pending'").fetchone()['cnt']
        approved_actions = conn.execute("SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'approved'").fetchone()['cnt']
        rejected_actions = conn.execute("SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'rejected'").fetchone()['cnt']
        sent_actions = conn.execute("SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'sent'").fetchone()['cnt']
        sent_notifications = conn.execute("SELECT COUNT(*) as cnt FROM notification_logs WHERE status = 'sent'").fetchone()['cnt']
        failed_notifications = conn.execute("SELECT COUNT(*) as cnt FROM notification_logs WHERE status IN ('failed', 'skipped')").fetchone()['cnt']
    finally:
        conn.close()

    return {
        'total_skus': len(inventory_data),
        'low_stock': sum(1 for i in inventory_data if i['days_left'] <= LOW_STOCK_DAYS_THRESHOLD),
        'slow_moving': sum(
            1
            for i in inventory_data
            if (
                i['stock'] >= SLOW_MOVING_STOCK_THRESHOLD
                and i['daily_sales'] <= SLOW_MOVING_DAILY_SALES_THRESHOLD
                and i['days_left'] >= SLOW_MOVING_DAYS_LEFT_THRESHOLD
            )
        ),
        'supplier_count': supplier_count,
        'pending_actions': pending_actions,
        'approved_actions': approved_actions,
        'rejected_actions': rejected_actions,
        'sent_actions': sent_actions,
        'sent_notifications': sent_notifications,
        'failed_notifications': failed_notifications,
        'chart_data': [{'sku': i['sku'], 'name': i['name'], 'stock': i['stock']} for i in inventory_data],
    }


# ─── Decision impact metrics endpoint ────────────────────────────────────────
@app.get("/api/impact-metrics")
def get_impact_metrics():
    """
    Returns quantifiable decision-support metrics for dashboard / reports.
    Values are rule-derived estimates — suitable for prototype / hackathon demo.
    """
    conn = get_db_connection()
    try:
        items = conn.execute("SELECT * FROM inventory").fetchall()
        inventory_data = [dict(r) for r in items]
        for it in inventory_data:
            it["days_left"] = calc_days_left(it["stock"], it["daily_sales"])

        # Count high-priority pending actions (priority_level column may not exist on old rows)
        high_priority = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'pending' AND priority_level = 'HIGH'"
        ).fetchone()["cnt"]

        total_pending = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_queue WHERE status = 'pending'"
        ).fetchone()["cnt"]

        approved_actions = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_queue WHERE status IN ('approved', 'sent')"
        ).fetchone()["cnt"]

        # Notifications automated = those logged (sent + skipped both demonstrate automation)
        notifications_automated = conn.execute(
            "SELECT COUNT(*) as cnt FROM notification_logs"
        ).fetchone()["cnt"]

        # Stockouts prevented = approved low_stock actions that had email sent / approved
        stockouts_prevented = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_queue WHERE issue_type = 'low_stock' AND status IN ('approved', 'sent')"
        ).fetchone()["cnt"]

        # Slow-moving items flagged (any status)
        slow_moving_flagged = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_queue WHERE issue_type = 'slow_moving'"
        ).fetchone()["cnt"]

        # Capital at risk: stock * cost_price for low-stock items
        capital_at_risk = sum(
            (it["stock"] or 0) * (it.get("cost_price") or 0)
            for it in inventory_data
            if it["days_left"] <= LOW_STOCK_DAYS_THRESHOLD
        )

        # Estimated time saved: assume 0.5 hr manual effort per processed action
        time_saved_hours = round(approved_actions * 0.5, 1)

        return {
            "high_priority_actions": high_priority,
            "total_pending_actions": total_pending,
            "notifications_automated": notifications_automated,
            "stockouts_prevented": stockouts_prevented,
            "slow_moving_flagged": slow_moving_flagged,
            "capital_at_risk": round(capital_at_risk, 2),
            "estimated_time_saved_hours": time_saved_hours,
        }
    finally:
        conn.close()


# ─── Return Guard text analysis endpoint ─────────────────────────────────────
class ReturnAnalyzeRequest(BaseModel):
    customer: str
    order_ref: Optional[str] = ""
    reason_text: str
    staff_note: Optional[str] = ""


@app.post("/api/return-guard/analyze")
def analyze_return(payload: ReturnAnalyzeRequest):
    """
    Lightweight return/complaint analysis pipeline.
    Step 1: keyword-based categorisation (decision_engine.analyse_return_text)
    Step 2: optional GLM natural-language summary if ILMU key is configured
    """
    # Step 1 — rule-based categorisation (always runs, no LLM dependency)
    result = analyse_return_text(payload.reason_text, payload.staff_note or "")

    ai_summary = None
    ai_source = "rule-based"

    # Step 2 — optional GLM summary for natural-language explanation
    if ILMU_API_KEY and payload.reason_text.strip():
        try:
            prompt = (
                f"You are an inventory returns analyst. A customer submitted the following return request.\n\n"
                f"Customer: {payload.customer}\n"
                f"Order: {payload.order_ref or 'N/A'}\n"
                f"Reason: {payload.reason_text}\n"
                f"Staff note: {payload.staff_note or 'None'}\n\n"
                f"Issue category detected: {result['issue_category'].replace('_', ' ').title()}\n"
                f"Severity: {result['severity']}\n\n"
                f"Write a 2-sentence professional summary of this return case and the recommended resolution. "
                f"Be concise and business-appropriate."
            )
            resp = req.post(
                "https://api.ilmu.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {ILMU_API_KEY}", "Content-Type": "application/json"},
                json={"model": "ilmu-glm-5.1", "messages": [{"role": "user", "content": prompt}], "temperature": 0.4},
                timeout=15,
            )
            resp.raise_for_status()
            ai_summary = resp.json()["choices"][0]["message"]["content"].strip()
            ai_source = "ilmu-glm-5.1"
        except Exception:
            pass  # GLM unavailable — proceed with rule-based result only

    return {
        "customer": payload.customer,
        "order_ref": payload.order_ref,
        "issue_category": result["issue_category"],
        "severity": result["severity"],
        "suggested_action": result["suggested_action"],
        "confidence": result["confidence"],
        "matched_keywords": result["matched_keywords"],
        "ai_summary": ai_summary,
        "ai_source": ai_source,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)