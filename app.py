# app.py - 包含后台管理系统的云端服务器
from flask import Flask, request, jsonify, render_template_string
import json
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
DATABASE = 'netcafe_users.db'

# 【核心】后台管理员密码 (请务必修改为你自己的密码！)
ADMIN_PASSWORD = "15092085416z" 

# ================= 数据库初始化 =================
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON') # 开启外键支持
    
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saves (
            user_id INTEGER PRIMARY KEY,
            money INTEGER DEFAULT 500,
            hygiene INTEGER DEFAULT 100,
            has_cleaner INTEGER DEFAULT 0,
            has_repairman INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ================= 工具函数 =================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    return secrets.token_urlsafe(32)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def verify_token(token):
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

def check_admin_auth():
    """检查是否是管理员"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header == f'Bearer {ADMIN_PASSWORD}':
        return True
    return False

# ================= 网页后台管理界面 (HTML) =================
ADMIN_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>网吧模拟器 - 后台管理</title>
    <style>
        body { font-family: 'Microsoft YaHei', sans-serif; background: #2c3e50; color: #ecf0f1; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { text-align: center; color: #3498db; }
        .login-box { background: #34495e; padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
        input { padding: 8px; border-radius: 4px; border: none; margin: 5px; }
        button { padding: 8px 15px; border-radius: 4px; border: none; cursor: pointer; font-weight: bold; }
        .btn-primary { background: #3498db; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #2ecc71; color: white; }
        table { width: 100%; border-collapse: collapse; background: #34495e; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #2c3e50; }
        th { background: #2980b9; }
        .hidden { display: none; }
        #message { color: #e74c3c; text-align: center; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 网吧模拟器 - GM 后台管理</h1>
        
        <div id="login-section" class="login-box">
            <h3>管理员登录</h3>
            <input type="password" id="admin-pwd" placeholder="输入管理员密码">
            <button class="btn-primary" onclick="adminLogin()">登录</button>
            <p id="login-msg"></p>
        </div>

        <div id="admin-panel" class="hidden">
            <div style="text-align: right; margin-bottom: 10px;">
                <button class="btn-danger" onclick="logout()">退出登录</button>
            </div>

            <div class="login-box" style="text-align: left;">
                <h3>➕ 添加新用户</h3>
                <input type="text" id="new-username" placeholder="用户名">
                <input type="password" id="new-password" placeholder="密码">
                <input type="number" id="new-money" placeholder="初始金钱" value="500">
                <button class="btn-success" onclick="addUser()">添加用户</button>
            </div>

            <h3>👥 用户列表</h3>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>用户名</th>
                        <th>金钱</th>
                        <th>卫生度</th>
                        <th>保洁阿姨</th>
                        <th>修理工</th>
                        <th>注册时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="user-list">
                    <!-- 数据将通过 JS 加载 -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const API_URL = window.location.origin; // 自动获取当前域名
        let adminToken = localStorage.getItem('admin_token') || '';

        if (adminToken) {
            document.getElementById('login-section').classList.add('hidden');
            document.getElementById('admin-panel').classList.remove('hidden');
            loadUsers();
        }

        async function adminLogin() {
            const pwd = document.getElementById('admin-pwd').value;
            // 简单验证：直接检查密码是否匹配后端设定的密码
            // 实际项目中应该通过 API 验证，这里为了简单直接前端判断（安全性要求不高）
            if (pwd === 'ADMIN_PASSWORD_PLACEHOLDER') { 
                adminToken = pwd;
                localStorage.setItem('admin_token', adminToken);
                document.getElementById('login-section').classList.add('hidden');
                document.getElementById('admin-panel').classList.remove('hidden');
                loadUsers();
            } else {
                document.getElementById('login-msg').innerText = "密码错误！";
            }
        }

        function logout() {
            localStorage.removeItem('admin_token');
            location.reload();
        }

        async function loadUsers() {
            const res = await fetch(`${API_URL}/api/admin/users`, {
                headers: { 'Authorization': `Bearer ${adminToken}` }
            });
            const data = await res.json();
            const tbody = document.getElementById('user-list');
            tbody.innerHTML = '';
            
            if (data.status === 'success') {
                data.users.forEach(u => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${u.id}</td>
                        <td>${u.username}</td>
                        <td>$${u.money} <button class="btn-primary" style="font-size:12px; padding:2px 5px;" onclick="updateMoney(${u.id}, ${u.money})">改钱</button></td>
                        <td>${u.hygiene}%</td>
                        <td>${u.has_cleaner ? '✅' : '❌'}</td>
                        <td>${u.has_repairman ? '✅' : '❌'}</td>
                        <td>${u.created_at.split('T')[0]}</td>
                        <td><button class="btn-danger" style="font-size:12px; padding:2px 5px;" onclick="deleteUser(${u.id}, '${u.username}')">删除</button></td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                alert('加载失败，请检查密码或网络');
                logout();
            }
        }

        async function updateMoney(userId, currentMoney) {
            const newMoney = prompt(`请输入用户 ID ${userId} 的新金额 (当前: $${currentMoney}):`, currentMoney);
            if (newMoney !== null && !isNaN(newMoney)) {
                await fetch(`${API_URL}/api/admin/update_money`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` },
                    body: JSON.stringify({ user_id: userId, money: parseInt(newMoney) })
                });
                loadUsers();
            }
        }

        async function deleteUser(userId, username) {
            if (confirm(`确定要删除用户 "${username}" 及其所有存档吗？此操作不可恢复！`)) {
                await fetch(`${API_URL}/api/admin/delete_user`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` },
                    body: JSON.stringify({ user_id: userId })
                });
                loadUsers();
            }
        }

        async function addUser() {
            const username = document.getElementById('new-username').value;
            const password = document.getElementById('new-password').value;
            const money = parseInt(document.getElementById('new-money').value) || 500;

            if (!username || !password) {
                alert('请输入用户名和密码');
                return;
            }

            const res = await fetch(`${API_URL}/api/admin/add_user`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` },
                body: JSON.stringify({ username, password, money })
            });
            const data = await res.json();
            alert(data.message);
            if (data.status === 'success') {
                document.getElementById('new-username').value = '';
                document.getElementById('new-password').value = '';
                loadUsers();
            }
        }
    </script>
</body>
</html>
"""

# ================= API 接口 =================

@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "网吧模拟器云端服务器运行中", "admin_panel": "/admin"})

# 将 HTML 模板中的密码占位符替换为真实密码
@app.route('/admin')
def admin_page():
    safe_html = ADMIN_HTML_TEMPLATE.replace('ADMIN_PASSWORD_PLACEHOLDER', ADMIN_PASSWORD)
    return render_template_string(safe_html)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    if len(username) < 3 or len(password) < 6:
        return jsonify({"status": "error", "message": "用户名至少3位，密码至少6位"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat()
        created_at = datetime.now().isoformat()
        
        cursor.execute('INSERT INTO users (username, password_hash, token, token_expires, created_at) VALUES (?, ?, ?, ?, ?)',
                       (username, password_hash, token, expires, created_at))
        user_id = cursor.lastrowid
        cursor.execute('INSERT INTO saves (user_id) VALUES (?)', (user_id,))
        conn.commit()
        return jsonify({"status": "success", "message": "注册成功！", "token": token, "username": username})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "用户名已存在"}), 409
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
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
    
    token = generate_token()
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET token = ?, token_expires = ? WHERE id = ?', (token, expires, user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "登录成功！", "token": token, "username": username})

@app.route('/api/load', methods=['GET'])
def load_save():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    if not user:
        return jsonify({"status": "error", "message": "token 无效"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM saves WHERE user_id = ?', (user['id'],))
    save = cursor.fetchone()
    conn.close()
    
    if save:
        return jsonify({"status": "success", "data": {
            "money": save['money'], "hygiene": save['hygiene'],
            "has_cleaner": bool(save['has_cleaner']), "has_repairman": bool(save['has_repairman'])
        }})
    return jsonify({"status": "error", "message": "存档不存在"}), 404

@app.route('/api/save', methods=['POST'])
def save_data():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    if not user:
        return jsonify({"status": "error", "message": "token 无效"}), 401
    
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO saves (user_id, money, hygiene, has_cleaner, has_repairman)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET money=excluded.money, hygiene=excluded.hygiene, has_cleaner=excluded.has_cleaner, has_repairman=excluded.has_repairman
    ''', (user['id'], data.get('money', 500), data.get('hygiene', 100), 
          1 if data.get('has_cleaner') else 0, 1 if data.get('has_repairman') else 0))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "存档已保存"})

# ================= 后台管理 API =================

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    if not check_admin_auth():
        return jsonify({"status": "error", "message": "未授权"}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.created_at, s.money, s.hygiene, s.has_cleaner, s.has_repairman 
        FROM users u 
        LEFT JOIN saves s ON u.id = s.user_id 
        ORDER BY u.id DESC
    ''')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"status": "success", "users": users})

@app.route('/api/admin/update_money', methods=['POST'])
def admin_update_money():
    if not check_admin_auth():
        return jsonify({"status": "error", "message": "未授权"}), 403
    
    data = request.json
    user_id = data.get('user_id')
    new_money = data.get('money')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE saves SET money = ? WHERE user_id = ?', (new_money, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "金额已修改"})

@app.route('/api/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not check_admin_auth():
        return jsonify({"status": "error", "message": "未授权"}), 403
    
    data = request.json
    user_id = data.get('user_id')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM saves WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "用户已删除"})

@app.route('/api/admin/add_user', methods=['POST'])
def admin_add_user():
    if not check_admin_auth():
        return jsonify({"status": "error", "message": "未授权"}), 403
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    money = data.get('money', 500)
    
    if not username or not password:
        return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat()
        created_at = datetime.now().isoformat()
        
        cursor.execute('INSERT INTO users (username, password_hash, token, token_expires, created_at) VALUES (?, ?, ?, ?, ?)',
                       (username, password_hash, token, expires, created_at))
        user_id = cursor.lastrowid
        cursor.execute('INSERT INTO saves (user_id, money) VALUES (?, ?)', (user_id, money))
        conn.commit()
        return jsonify({"status": "success", "message": f"用户 {username} 添加成功！"})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "用户名已存在"}), 409
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
