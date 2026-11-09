# app.py - 网吧模拟器后端 (强制 IPv4 + SSL 稳定版)
from flask import Flask, request, jsonify, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import secrets
from datetime import datetime, timedelta
import socket
import urllib.parse

app = Flask(__name__)

# 【核心】你的 Supabase 连接字符串
DATABASE_URL = "postgresql://postgres:15092085416z@db.uncxcsezvofdqxayadjs.supabase.co:5432/postgres"

ADMIN_PASSWORD = "admin123" # 后台管理员密码

# ================= 数据库工具 =================
def get_db():
    """获取数据库连接，强制使用 IPv4 和 SSL 以避免 Render 网络问题"""
    try:
        parsed = urllib.parse.urlparse(DATABASE_URL)
        host = parsed.hostname
        
        # 强制解析为 IPv4 地址
        ipv4_host = socket.gethostbyname(host)
        
        # 重建包含 IPv4 地址和强制 SSL 的连接字符串
        new_netloc = f"{parsed.username}:{parsed.password}@{ipv4_host}:{parsed.port}"
        query = "sslmode=require"
        new_url = urllib.parse.urlunparse((parsed.scheme, new_netloc, parsed.path, parsed.params, query, parsed.fragment))
        
        conn = psycopg2.connect(new_url)
        return conn
    except Exception as e:
        print(f"IPv4 解析失败，尝试直连: {e}")
        # 降级方案：直接连接，但强制加上 sslmode=require
        fallback_url = DATABASE_URL + ("&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require")
        return psycopg2.connect(fallback_url)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            token TEXT UNIQUE,
            token_expires TEXT,
            created_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saves (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            money INTEGER DEFAULT 500,
            hygiene INTEGER DEFAULT 100,
            has_cleaner INTEGER DEFAULT 0,
            has_repairman INTEGER DEFAULT 0,
            socket_states TEXT DEFAULT '0,0,0',
            total_earned INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]'
        )
    ''')
    conn.commit()
    conn.close()

# 启动时初始化表
init_db()

# ================= 工具函数 =================
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()
def generate_token(): return secrets.token_urlsafe(32)

def verify_token(token):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM users WHERE token = %s', (token,))
    user = cursor.fetchone()
    conn.close()
    if user:
        expires = datetime.fromisoformat(user['token_expires'])
        if datetime.now() < expires: return dict(user)
    return None

def check_admin_auth(): 
    return request.headers.get('Authorization', '') == f'Bearer {ADMIN_PASSWORD}'

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
        .btn-primary { background: #3498db; color: white; } .btn-danger { background: #e74c3c; color: white; } .btn-success { background: #2ecc71; color: white; }
        table { width: 100%; border-collapse: collapse; background: #34495e; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #2c3e50; } th { background: #2980b9; }
        .hidden { display: none; }
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
            <div style="text-align: right; margin-bottom: 10px;"><button class="btn-danger" onclick="logout()">退出登录</button></div>
            <div class="login-box" style="text-align: left;">
                <h3>➕ 添加新用户</h3>
                <input type="text" id="new-username" placeholder="用户名">
                <input type="password" id="new-password" placeholder="密码">
                <input type="number" id="new-money" placeholder="初始金钱" value="500">
                <button class="btn-success" onclick="addUser()">添加用户</button>
            </div>
            <h3>👥 用户列表</h3>
            <table>
                <thead><tr><th>ID</th><th>用户名</th><th>金钱</th><th>卫生度</th><th>阿姨</th><th>修理工</th><th>注册时间</th><th>操作</th></tr></thead>
                <tbody id="user-list"></tbody>
            </table>
        </div>
    </div>
    <script>
        const API_URL = window.location.origin;
        let adminToken = localStorage.getItem('admin_token') || '';
        if (adminToken) { document.getElementById('login-section').classList.add('hidden'); document.getElementById('admin-panel').classList.remove('hidden'); loadUsers(); }
        async function adminLogin() {
            const pwd = document.getElementById('admin-pwd').value;
            if (pwd === 'ADMIN_PASSWORD_PLACEHOLDER') { 
                adminToken = pwd; localStorage.setItem('admin_token', adminToken);
                document.getElementById('login-section').classList.add('hidden'); document.getElementById('admin-panel').classList.remove('hidden'); loadUsers();
            } else { document.getElementById('login-msg').innerText = "密码错误！"; }
        }
        function logout() { localStorage.removeItem('admin_token'); location.reload(); }
        async function loadUsers() {
            const res = await fetch(`${API_URL}/api/admin/users`, { headers: { 'Authorization': `Bearer ${adminToken}` } });
            const data = await res.json(); const tbody = document.getElementById('user-list'); tbody.innerHTML = '';
            if (data.status === 'success') {
                data.users.forEach(u => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${u['id']}</td><td>${u.username}</td><td>$${u.money} <button class="btn-primary" style="font-size:12px; padding:2px 5px;" onclick="updateMoney(${u['id']}, ${u.money})">改钱</button></td><td>${u.hygiene}%</td><td>${u.has_cleaner ? '✅' : '❌'}</td><td>${u.has_repairman ? '✅' : '❌'}</td><td>${u.created_at.split('T')[0]}</td><td><button class="btn-danger" style="font-size:12px; padding:2px 5px;" onclick="deleteUser(${u['id']}, '${u.username}')">删除</button></td>`;
                    tbody.appendChild(tr);
                });
            } else { alert('加载失败'); logout(); }
        }
        async function updateMoney(userId, currentMoney) {
            const newMoney = prompt(`请输入新金额 (当前: $${currentMoney}):`, currentMoney);
            if (newMoney !== null && !isNaN(newMoney)) {
                await fetch(`${API_URL}/api/admin/update_money`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` }, body: JSON.stringify({ user_id: userId, money: parseInt(newMoney) }) });
                loadUsers();
            }
        }
        async function deleteUser(userId, username) {
            if (confirm(`确定要删除用户 "${username}" 吗？`)) {
                await fetch(`${API_URL}/api/admin/delete_user`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` }, body: JSON.stringify({ user_id: userId }) });
                loadUsers();
            }
        }
        async function addUser() {
            const username = document.getElementById('new-username').value;
            const password = document.getElementById('new-password').value;
            const money = parseInt(document.getElementById('new-money').value) || 500;
            if (!username || !password) { alert('请输入用户名和密码'); return; }
            const res = await fetch(`${API_URL}/api/admin/add_user`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` }, body: JSON.stringify({ username, password, money }) });
            const data = await res.json(); alert(data.message);
            if (data.status === 'success') { document.getElementById('new-username').value = ''; document.getElementById('new-password').value = ''; loadUsers(); }
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index(): return jsonify({"message": "网吧模拟器云端服务器 (IPv4 稳定版)", "admin_panel": "/admin"})

@app.route('/admin')
def admin_page(): return render_template_string(ADMIN_HTML_TEMPLATE.replace('ADMIN_PASSWORD_PLACEHOLDER', ADMIN_PASSWORD))

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json; username = data.get('username', '').strip(); password = data.get('password', '')
    if not username or not password: return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    if len(username) < 3 or len(password) < 6: return jsonify({"status": "error", "message": "用户名至少3位，密码至少6位"}), 400
    conn = get_db(); cursor = conn.cursor()
    try:
        password_hash = hash_password(password); token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat(); created_at = datetime.now().isoformat()
        cursor.execute('INSERT INTO users (username, password_hash, token, token_expires, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id', (username, password_hash, token, expires, created_at))
        user_id = cursor.fetchone()[0]
        cursor.execute('INSERT INTO saves (user_id) VALUES (%s)', (user_id,))
        conn.commit()
        return jsonify({"status": "success", "message": "注册成功！", "token": token, "username": username})
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"status": "error", "message": "用户名已存在"}), 409
    finally: conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json; username = data.get('username', '').strip(); password = data.get('password', '')
    conn = get_db(); cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,)); user = cursor.fetchone(); conn.close()
    if not user or user['password_hash'] != hash_password(password): return jsonify({"status": "error", "message": "用户名或密码错误"}), 401
    token = generate_token(); expires = (datetime.now() + timedelta(days=30)).isoformat()
    conn = get_db(); cursor = conn.cursor()
    cursor.execute('UPDATE users SET token = %s, token_expires = %s WHERE id = %s', (token, expires, user['id'])); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "登录成功！", "token": token, "username": username})

@app.route('/api/load', methods=['GET'])
def load_save():
    token = request.headers.get('Authorization', '').replace('Bearer ', ''); user = verify_token(token)
    if not user: return jsonify({"status": "error", "message": "token 无效"}), 401
    conn = get_db(); cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM saves WHERE user_id = %s', (user['id'],)); save = cursor.fetchone(); conn.close()
    if save:
        import json
        return jsonify({"status": "success", "data": {
            "money": save['money'], "hygiene": save['hygiene'],
            "has_cleaner": bool(save['has_cleaner']), "has_repairman": bool(save['has_repairman']),
            "socket_states": json.loads(save['socket_states']),
            "total_earned": save['total_earned'],
            "achievements": json.loads(save['achievements'])
        }})
    return jsonify({"status": "error", "message": "存档不存在"}), 404

@app.route('/api/save', methods=['POST'])
def save_data():
    token = request.headers.get('Authorization', '').replace('Bearer ', ''); user = verify_token(token)
    if not user: return jsonify({"status": "error", "message": "token 无效"}), 401
    data = request.json
    import json
    socket_states_str = json.dumps(data.get('socket_states', [0,0,0]))
    achievements_str = json.dumps(data.get('achievements', []))
    
    conn = get_db(); cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO saves (user_id, money, hygiene, has_cleaner, has_repairman, socket_states, total_earned, achievements)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(user_id) DO UPDATE SET 
            money=EXCLUDED.money, hygiene=EXCLUDED.hygiene, 
            has_cleaner=EXCLUDED.has_cleaner, has_repairman=EXCLUDED.has_repairman,
            socket_states=EXCLUDED.socket_states, total_earned=EXCLUDED.total_earned, achievements=EXCLUDED.achievements
    ''', (user['id'], data.get('money', 500), data.get('hygiene', 100), 
          1 if data.get('has_cleaner') else 0, 1 if data.get('has_repairman') else 0,
          socket_states_str, data.get('total_earned', 0), achievements_str))
    conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "存档已保存"})

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    conn = get_db(); cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT u.id, u.username, u.created_at, s.money, s.hygiene, s.has_cleaner, s.has_repairman 
        FROM users u LEFT JOIN saves s ON u.id = s.user_id ORDER BY u.id DESC
    ''')
    users = [dict(row) for row in cursor.fetchall()]; conn.close()
    return jsonify({"status": "success", "users": users})

@app.route('/api/admin/update_money', methods=['POST'])
def admin_update_money():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    data = request.json; conn = get_db(); cursor = conn.cursor()
    cursor.execute('UPDATE saves SET money = %s WHERE user_id = %s', (data.get('money'), data.get('user_id'))); conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "金额已修改"})

@app.route('/api/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    data = request.json; conn = get_db(); cursor = conn.cursor()
    cursor.execute('DELETE FROM saves WHERE user_id = %s', (data.get('user_id'),))
    cursor.execute('DELETE FROM users WHERE id = %s', (data.get('user_id'),))
    conn.commit(); conn.close()
    return jsonify({"status": "success", "message": "用户已删除"})

@app.route('/api/admin/add_user', methods=['POST'])
def admin_add_user():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    data = request.json; username = data.get('username', '').strip(); password = data.get('password', ''); money = data.get('money', 500)
    if not username or not password: return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    conn = get_db(); cursor = conn.cursor()
    try:
        password_hash = hash_password(password); token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat(); created_at = datetime.now().isoformat()
        cursor.execute('INSERT INTO users (username, password_hash, token, token_expires, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id', (username, password_hash, token, expires, created_at))
        user_id = cursor.fetchone()[0]
        cursor.execute('INSERT INTO saves (user_id, money) VALUES (%s, %s)', (user_id, money))
        conn.commit()
        return jsonify({"status": "success", "message": f"用户 {username} 添加成功！"})
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"status": "error", "message": "用户名已存在"}), 409
    finally: conn.close()

if __name__ == '__main__': app.run(host='0.0.0.0', port=10000)
