# app.py - 支持用户注册登录的云端服务器
from flask import Flask, request, jsonify
import json
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
DATABASE = 'netcafe_users.db'
SECRET_KEY = secrets.token_hex(32)  # 生成随机密钥

# ================= 数据库初始化 =================
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            token TEXT UNIQUE,
            token_expires TEXT,
            created_at TEXT
        )
    ''')
    
    # 存档表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saves (
            user_id INTEGER PRIMARY KEY,
            money INTEGER DEFAULT 500,
            hygiene INTEGER DEFAULT 100,
            has_cleaner INTEGER DEFAULT 0,
            has_repairman INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# 启动时初始化数据库
init_db()

# ================= 工具函数 =================
def hash_password(password):
    """密码加密"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    """生成随机 token"""
    return secrets.token_urlsafe(32)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def verify_token(token):
    """验证 token 是否有效"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE token = ?', (token,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        expires = datetime.fromisoformat(user['token_expires'])
        if datetime.now() < expires:
            return user
    return None

# ================= API 接口 =================

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "网吧模拟器云端服务器",
        "endpoints": {
            "register": "POST /api/register",
            "login": "POST /api/login",
            "load": "GET /api/load (需要 token)",
            "save": "POST /api/save (需要 token)"
        }
    })

@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    
    if len(username) < 3 or len(username) > 20:
        return jsonify({"status": "error", "message": "用户名长度 3-20 个字符"}), 400
    
    if len(password) < 6:
        return jsonify({"status": "error", "message": "密码至少 6 位"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # 创建用户
        password_hash = hash_password(password)
        token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat()
        created_at = datetime.now().isoformat()
        
        cursor.execute(
            'INSERT INTO users (username, password_hash, token, token_expires, created_at) VALUES (?, ?, ?, ?, ?)',
            (username, password_hash, token, expires, created_at)
        )
        
        # 创建初始存档
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO saves (user_id) VALUES (?)',
            (user_id,)
        )
        
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": "注册成功！",
            "token": token,
            "username": username
        })
        
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "用户名已存在"}), 409
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or user['password_hash'] != hash_password(password):
        return jsonify({"status": "error", "message": "用户名或密码错误"}), 401
    
    # 更新 token（每次登录生成新 token）
    token = generate_token()
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET token = ?, token_expires = ? WHERE id = ?',
        (token, expires, user['id'])
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "status": "success",
        "message": "登录成功！",
        "token": token,
        "username": username
    })

@app.route('/api/load', methods=['GET'])
def load_save():
    """读取存档（需要 token）"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    
    if not user:
        return jsonify({"status": "error", "message": "token 无效或已过期，请重新登录"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM saves WHERE user_id = ?', (user['id'],))
    save = cursor.fetchone()
    conn.close()
    
    if save:
        return jsonify({
            "status": "success",
            "data": {
                "money": save['money'],
                "hygiene": save['hygiene'],
                "has_cleaner": bool(save['has_cleaner']),
                "has_repairman": bool(save['has_repairman'])
            }
        })
    
    return jsonify({"status": "error", "message": "存档不存在"}), 404

@app.route('/api/save', methods=['POST'])
def save_data():
    """保存存档（需要 token）"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    
    if not user:
        return jsonify({"status": "error", "message": "token 无效或已过期"}), 401
    
    data = request.json
    money = data.get('money', 500)
    hygiene = data.get('hygiene', 100)
    has_cleaner = 1 if data.get('has_cleaner') else 0
    has_repairman = 1 if data.get('has_repairman') else 0
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO saves (user_id, money, hygiene, has_cleaner, has_repairman)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            money = excluded.money,
            hygiene = excluded.hygiene,
            has_cleaner = excluded.has_cleaner,
            has_repairman = excluded.has_repairman
    ''', (user['id'], money, hygiene, has_cleaner, has_repairman))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "存档已保存"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
