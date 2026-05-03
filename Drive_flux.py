import os
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# Scope for full read-only access to Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_creds():
    """Handles OAuth2 token generation and storage"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("Error: 'credentials.json' not found in current directory.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def download_engine(creds, file_info, max_retries=3):
    """
    Core download engine:
    - Creates unique service instance per thread to prevent SSL handshake conflicts.
    - Implements exponential backoff retry logic.
    """
    file_id = file_info['id']
    file_name = file_info['name']
    local_dir = file_info['path']
    
    # Independent service for each thread to avoid 'SSL: WRONG_VERSION_NUMBER' errors
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    
    os.makedirs(local_dir, exist_ok=True)
    file_path = os.path.join(local_dir, file_name)

    for attempt in range(max_retries):
        try:
            request = service.files().get_media(fileId=file_id)
            with io.FileIO(file_path, 'wb') as fh:
                # 2MB chunksize for optimized data transfer
                downloader = MediaIoBaseDownload(fh, request, chunksize=1024*1024*2)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return True, file_name
        except Exception as e:
            if attempt < max_retries - 1:
                # Wait 2, 4, 8 seconds before retrying
                time.sleep(2 ** (attempt + 1))
            else:
                return False, f"{file_name} (Final Error: {e})"

def scan_files(service, folder_id, local_path, tasks):
    """Recursively scans folders and collects file metadata"""
    page_token = None
    while True:
        try:
            # Query files in current folder, excluding trashed ones
            results = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token
            ).execute()
            
            for item in results.get('files', []):
                # If item is a folder, recurse into it
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    scan_files(service, item['id'], os.path.join(local_path, item['name']), tasks)
                # If item is a file, add to task list (Skips Google native docs without size)
                elif 'size' in item and 'vnd.google-apps' not in item['mimeType']:
                    tasks.append({
                        'id': item['id'],
                        'name': item['name'],
                        'path': local_path,
                        'size': int(item['size'])
                    })
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            print(f"Scan Error: {e}")
            break

if __name__ == '__main__':
    # ================= CONFIGURATION =================
    # Replace with your actual Folder ID
    TARGET_ID = ''
    # Base local folder for saving files
    LOCAL_ROOT = ''
    # File size threshold (10MB) for adaptive concurrency
    THRESHOLD = 10 * 1024 * 1024 
    # =================================================

    credentials = get_creds()
    scan_srv = build('drive', 'v3', credentials=credentials)
    
    all_tasks = []
    print("🔍 Initializing Cloud Scan...")
    scan_files(scan_srv, TARGET_ID, LOCAL_ROOT, all_tasks)
    
    if not all_tasks:
        print("❌ No files found to download.")
    else:
        # Split tasks based on size
        smalls = [t for t in all_tasks if t['size'] < THRESHOLD]
        larges = [t for t in all_tasks if t['size'] >= THRESHOLD]
        
        print(f"📦 Scan results: {len(all_tasks)} files found.")
        print(f"  - Light tasks (<10MB): {len(smalls)} files")
        print(f"  - Heavy tasks (>=10MB): {len(larges)} files")
        
        fail_list = []
        
        with tqdm(total=len(all_tasks), desc="Overall Progress", unit="file") as pbar:
            # Phase 1: High concurrency for small files (10 threads)
            if smalls:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(download_engine, credentials, t): t for t in smalls}
                    for f in as_completed(futures):
                        success, info = f.result()
                        if not success: fail_list.append(info)
                        pbar.update(1)
            
            # Phase 2: Lower concurrency for large files (3 threads) for connection stability
            if larges:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {executor.submit(download_engine, credentials, t): t for t in larges}
                    for f in as_completed(futures):
                        success, info = f.result()
                        if not success: fail_list.append(info)
                        pbar.update(1)

        print("\n" + "="*40)
        print(f"🏁 Sync Summary: Success: {len(all_tasks) - len(fail_list)} | Failed: {len(fail_list)}")
        if fail_list:
            print("\n❌ Failed Items:")
            for item in fail_list:
                print(f"  - {item}")
        print("="*40)