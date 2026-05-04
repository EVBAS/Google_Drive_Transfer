import os
import io
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# 全局状态字典，用于前端轮询获取进度
progress_state = {
    "is_running": False,
    "status_msg": "等待中...",
    "total_files": 0,
    "completed_files": 0,
    "failed_files": [],
    "progress_percent": 0
}

def get_creds():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("未找到 credentials.json 文件。")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def download_engine(creds, file_info, max_retries=3):
    file_id, file_name, local_dir = file_info['id'], file_info['name'], file_info['path']
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    os.makedirs(local_dir, exist_ok=True)
    file_path = os.path.join(local_dir, file_name)

    for attempt in range(max_retries):
        try:
            request = service.files().get_media(fileId=file_id)
            with io.FileIO(file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request, chunksize=1024*1024*2)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return True, file_name
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                return False, f"{file_name} (最终错误: {e})"

def scan_files(service, folder_id, local_path, tasks):
    page_token = None
    while True:
        try:
            results = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token
            ).execute()
            
            for item in results.get('files', []):
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    scan_files(service, item['id'], os.path.join(local_path, item['name']), tasks)
                elif 'size' in item and 'vnd.google-apps' not in item['mimeType']:
                    tasks.append({
                        'id': item['id'], 'name': item['name'],
                        'path': local_path, 'size': int(item['size'])
                    })
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            break

def run_download_task(target_id, local_root):
    global progress_state
    try:
        progress_state["status_msg"] = "正在初始化凭证并扫描云端文件..."
        creds = get_creds()
        scan_srv = build('drive', 'v3', credentials=creds)
        
        all_tasks = []
        scan_files(scan_srv, target_id, local_root, all_tasks)
        
        total = len(all_tasks)
        progress_state["total_files"] = total
        
        if total == 0:
            progress_state["status_msg"] = "❌ 未找到可下载的文件。"
            progress_state["is_running"] = False
            return
            
        progress_state["status_msg"] = f"扫描完成，共 {total} 个文件。开始自适应下载..."
        THRESHOLD = 10 * 1024 * 1024 
        smalls = [t for t in all_tasks if t['size'] < THRESHOLD]
        larges = [t for t in all_tasks if t['size'] >= THRESHOLD]
        
        fail_list = []
        
        # 内部函数更新进度
        def update_progress(future):
            global progress_state
            success, info = future.result()
            if not success:
                fail_list.append(info)
            progress_state["completed_files"] += 1
            progress_state["progress_percent"] = int((progress_state["completed_files"] / progress_state["total_files"]) * 100)

        # 阶段 1：小文件高并发
        if smalls:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(download_engine, creds, t): t for t in smalls}
                for f in as_completed(futures):
                    update_progress(f)
                    
        # 阶段 2：大文件低并发
        if larges:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(download_engine, creds, t): t for t in larges}
                for f in as_completed(futures):
                    update_progress(f)

        progress_state["status_msg"] = "🏁 下载完成！"
        progress_state["failed_files"] = fail_list
    except Exception as e:
        progress_state["status_msg"] = f"发生严重错误: {str(e)}"
    finally:
        progress_state["is_running"] = False

# ================= Flask 路由 =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_download():
    global progress_state
    if progress_state["is_running"]:
        return jsonify({"error": "当前已有下载任务正在运行"}), 400
        
    data = request.json
    target_id = data.get('target_id')
    local_root = data.get('local_root', './Drive_Downloads')
    
    if not target_id:
        return jsonify({"error": "请提供 Folder ID"}), 400

    # 重置状态
    progress_state = {
        "is_running": True,
        "status_msg": "正在启动任务...",
        "total_files": 0,
        "completed_files": 0,
        "failed_files": [],
        "progress_percent": 0
    }
    
    # 在后台线程启动下载，防止阻塞 Flask 服务器
    thread = threading.Thread(target=run_download_task, args=(target_id, local_root))
    thread.start()
    
    return jsonify({"message": "下载已启动"})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(progress_state)

if __name__ == '__main__':
    # 启动 Web 服务器
    print("Web UI 已启动，请在浏览器中打开 http://127.0.0.1:5000")
    app.run(port=5000, debug=False)