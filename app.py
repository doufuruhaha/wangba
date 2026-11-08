# app.py (这是要部署到 Render 上的后端代码)
from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)
SAVE_FILE = "cloud_save_data.json"

# 接收游戏发来的存档数据
@app.route('/api/save', methods=['POST'])
def save_data():
    try:
        data = request.json
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return jsonify({"status": "success", "message": "云端保存成功"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# 游戏启动时，来读取存档数据
@app.route('/api/load', methods=['GET'])
def load_data():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return jsonify(data)
    return jsonify({}) # 没存档就返回空

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
