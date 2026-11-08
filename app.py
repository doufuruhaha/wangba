# app.py - 网吧模拟器后端 (MongoDB 永久免费版)
from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
import hashlib
import secrets
from datetime import datetime, timedelta
from bson import ObjectId

app = Flask(__name__)

# 【核心】请在这里粘贴你刚才复制的完整 MongoDB 链接
# 格式类似：mongodb+srv://353170383_db_user:你的密码@cluster0.pvyazes.mongodb.net/?retryWrites=true&w=majority
MONGODB_URI = "mongodb+srv://353170383_db_user:V1GyH0elG2H6cZqE@cluster0.pvyazes.mongodb.net/?retryWrites=true&w=majority"

ADMIN_PASSWORD = "15092085416z" # 后台管理员密码

# ================= 数据库连接 =================
client = MongoClient(MONGODB_URI)
db = client['netcafe_db']
users_col = db['users']
saves_col = db['saves']

# 创建唯一索引
users_col.create_index("username", unique=True)
users_col.create_index("token", unique=True)

# ================= 工具函数 =================
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()
def generate_token(): return secrets.token_urlsafe(32)
def verify_token(token):
    user = users_col.find_one({"token": token})
    if user:
        expires = datetime.fromisoformat(user['token_expires'])
        if datetime.now() < expires: return user
    return None
def check_admin_auth(): return request.headers.get('Authorization', '') == f'Bearer {ADMIN_PASSWORD}'

# ================= 网页后台管理界面 =================
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
                    tr.innerHTML = `<td>${u['_id'].substring(0,8)}...</td><td>${u.username}</td><td>$${u.money} <button class="btn-primary" style="font-size:12px; padding:2px 5px;" onclick="updateMoney('${u['_id']}', ${u.money})">改钱</button></td><td>${u.hygiene}%</td><td>${u.has_cleaner ? '✅' : '❌'}</td><td>${u.has_repairman ? '✅' : '❌'}</td><td>${u.created_at.split('T')[0]}</td><td><button class="btn-danger" style="font-size:12px; padding:2px 5px;" onclick="deleteUser('${u['_id']}', '${u.username}')">删除</button></td>`;
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
def index(): return jsonify({"message": "网吧模拟器云端服务器 (MongoDB永久版)", "admin_panel": "/admin"})

@app.route('/admin')
def admin_page(): return render_template_string(ADMIN_HTML_TEMPLATE.replace('ADMIN_PASSWORD_PLACEHOLDER', ADMIN_PASSWORD))

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json; username = data.get('username', '').strip(); password = data.get('password', '')
    if not username or not password: return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    if len(username) < 3 or len(password) < 6: return jsonify({"status": "error", "message": "用户名至少3位，密码至少6位"}), 400
    try:
        password_hash = hash_password(password); token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat(); created_at = datetime.now().isoformat()
        users_col.insert_one({"username": username, "password_hash": password_hash, "token": token, "token_expires": expires, "created_at": created_at})
        saves_col.insert_one({"username": username, "money": 500, "hygiene": 100, "has_cleaner": False, "has_repairman": False, "socket_states": [0, 0, 0]})
        return jsonify({"status": "success", "message": "注册成功！", "token": token, "username": username})
    except Exception as e:
        if "duplicate key" in str(e): return jsonify({"status": "error", "message": "用户名已存在"}), 409
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json; username = data.get('username', '').strip(); password = data.get('password', '')
    user = users_col.find_one({"username": username})
    if not user or user['password_hash'] != hash_password(password): return jsonify({"status": "error", "message": "用户名或密码错误"}), 401
    token = generate_token(); expires = (datetime.now() + timedelta(days=30)).isoformat()
    users_col.update_one({"_id": user['_id']}, {"$set": {"token": token, "token_expires": expires}})
    return jsonify({"status": "success", "message": "登录成功！", "token": token, "username": username})

@app.route('/api/load', methods=['GET'])
def load_save():
    token = request.headers.get('Authorization', '').replace('Bearer ', ''); user = verify_token(token)
    if not user: return jsonify({"status": "error", "message": "token 无效"}), 401
    save = saves_col.find_one({"username": user['username']})
    if save:
        save.pop('_id', None)
        return jsonify({"status": "success", "data": save})
    return jsonify({"status": "error", "message": "存档不存在"}), 404

@app.route('/api/save', methods=['POST'])
def save_data():
    token = request.headers.get('Authorization', '').replace('Bearer ', ''); user = verify_token(token)
    if not user: return jsonify({"status": "error", "message": "token 无效"}), 401
    data = request.json
    saves_col.update_one({"username": user['username']}, {"$set": {"money": data.get('money', 500), "hygiene": data.get('hygiene', 100), "has_cleaner": data.get('has_cleaner', False), "has_repairman": data.get('has_repairman', False), "socket_states": data.get('socket_states', [0,0,0])}}, upsert=True)
    return jsonify({"status": "success", "message": "存档已保存"})

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    pipeline = [{"$lookup": {"from": "saves", "localField": "username", "foreignField": "username", "as": "save_info"}}, {"$unwind": {"path": "$save_info", "preserveNullAndEmptyArrays": True}}, {"$project": {"_id": 1, "username": 1, "created_at": 1, "money": "$save_info.money", "hygiene": "$save_info.hygiene", "has_cleaner": "$save_info.has_cleaner", "has_repairman": "$save_info.has_repairman"}}]
    users = list(users_col.aggregate(pipeline))
    for u in users: u['_id'] = str(u['_id'])
    return jsonify({"status": "success", "users": users})

@app.route('/api/admin/update_money', methods=['POST'])
def admin_update_money():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    data = request.json
    user = users_col.find_one({"_id": ObjectId(data.get('user_id'))})
    if user: saves_col.update_one({"username": user['username']}, {"$set": {"money": data.get('money')}})
    return jsonify({"status": "success", "message": "金额已修改"})

@app.route('/api/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    data = request.json
    user = users_col.find_one({"_id": ObjectId(data.get('user_id'))})
    if user:
        users_col.delete_one({"_id": ObjectId(data.get('user_id'))})
        saves_col.delete_one({"username": user['username']})
    return jsonify({"status": "success", "message": "用户已删除"})

@app.route('/api/admin/add_user', methods=['POST'])
def admin_add_user():
    if not check_admin_auth(): return jsonify({"status": "error", "message": "未授权"}), 403
    data = request.json; username = data.get('username', '').strip(); password = data.get('password', ''); money = data.get('money', 500)
    if not username or not password: return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    try:
        password_hash = hash_password(password); token = generate_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat(); created_at = datetime.now().isoformat()
        users_col.insert_one({"username": username, "password_hash": password_hash, "token": token, "token_expires": expires, "created_at": created_at})
        saves_col.insert_one({"username": username, "money": money, "hygiene": 100, "has_cleaner": False, "has_repairman": False, "socket_states": [0,0,0]})
        return jsonify({"status": "success", "message": f"用户 {username} 添加成功！"})
    except Exception as e:
        if "duplicate key" in str(e): return jsonify({"status": "error", "message": "用户名已存在"}), 409
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__': app.run(host='0.0.0.0', port=10000)
