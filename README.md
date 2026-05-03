# Google Drive Transfer Tools

A comprehensive suite of Python scripts for efficient batch downloading of files from Google Drive. Provides three versions tailored for different use cases.

## 📋 Project Overview

This project offers three file download solutions:

| Script | Functionality | Use Case |
|--------|---------------|----------|
| `drive_transfer.py` | Recursively list Google Drive folder structure | View file directory only, no download |
| `drive_transfer_muti_cores.py` | Multi-threaded concurrent download of all files | General batch file downloads |
| `drive_transfer_max.py` | Adaptive concurrency (differentiates large/small files) | Mixed file sizes with optimal performance |

## 🚀 Quick Start

### Prerequisites

- Python 3.7+
- Google Drive API Credentials (`credentials.json`)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Obtain Google Drive API Credentials

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Google Drive API
4. Create OAuth 2.0 Credentials (Desktop Application)
5. Download the credentials JSON file, rename it to `credentials.json`, and place in the project directory

### 3. Configure the Script

Edit your chosen script and modify the configuration section:

```python
TARGET_ID = 'YOUR_FOLDER_ID'      # Google Drive folder ID
LOCAL_ROOT = 'LOCAL_PATH'          # Local save path
```

**How to get Google Drive Folder ID?**
- Open the folder in Google Drive
- The URL format: `https://drive.google.com/drive/folders/FOLDER_ID`

### 4. Run the Script

```bash

python Drive_flux.py

```

## 📝 Detailed Script Documentation

### drive_transfer.py (Basic Version)

**Features**
- Recursively scan Google Drive folders
- Print hierarchical file and folder structure
- Display ID and location for each item

**Output Example**
```
[Root] -> Folder1 (ID: 1abc...)
[Root/Folder1] -> subfile.txt (ID: 2def...)
[Root/Folder1] -> SubFolder (ID: 3ghi...)
```

**Characteristics**
- ✅ No download required, fast scanning
- ✅ Ideal for browsing and verifying file structure

---

### drive_transfer_muti_cores.py (Multi-threaded Version)

**Features**
- Recursively download all regular files from folders
- Multi-threaded concurrency for acceleration
- Supports retry on failure (max 3 attempts)
- Real-time progress bar display

**Configuration Parameters**
```python
TARGET_ID = 'FOLDER_ID'       # Target folder ID
LOCAL_ROOT = 'LOCAL_PATH'     # Local save root directory
```

**Characteristics**
- ✅ Auto-creates local folder structure
- ✅ Smart retry mechanism (2-second delay)
- ✅ Colorful progress bar with real-time feedback
- ✅ Detailed statistics (success/failure count)
- ⚠️ High MAX_WORKERS values may trigger API rate limiting

---

### drive_transfer_max.py (Advanced Version - Recommended)

**Features**
- Adaptive concurrency strategy based on file size
- Small files (<10MB): 10 threads high concurrency
- Large files (≥10MB): 3 threads low concurrency for connection stability
- Intelligent exponential backoff retry (2, 4, 8 seconds)
- 2MB chunk download optimization

**Configuration Parameters**
```python
TARGET_ID = 'FOLDER_ID'       # Target folder ID
LOCAL_ROOT = 'LOCAL_PATH'     # Local save root directory
THRESHOLD = 10 * 1024 * 1024  # File size threshold (10MB)
```

**Characteristics**
- ✅ Adaptive concurrency strategy for optimal performance
- ✅ Exponential backoff retry for greater stability
- ✅ 2MB chunked transfer, large-file friendly
- ✅ Detailed scan result statistics
- ✅ SSL error handling (independent service instance per thread)

**Output Example**
```
🔍 Initializing Cloud Scan...
📦 Scan results: 100 files found.
  - Light tasks (<10MB): 85 files
  - Heavy tasks (>=10MB): 15 files
Overall Progress: 100%|████████| 100/100 [05:32<00:00, 3.31file/s]
🏁 Sync Summary: Success: 98 | Failed: 2
```

## 🔐 Authentication

On first run:
1. Script automatically opens your browser
2. Complete Google account authorization
3. Automatically generates `token.json` (used for subsequent runs)

On subsequent runs:
- Automatically reads token from `token.json`
- Auto-refreshes if expired
- No re-authorization needed

## ⚙️ Advanced Configuration

### Concurrent Thread Count Recommendations

| Network Environment | MAX_WORKERS | Notes |
|------------------|-----------|-------|
| Home Internet | 3-5 | Avoid excessive connections |
| Office Network | 5-8 | Balance speed and stability |
| High-speed Server | 10+ | Can disregard API rate limiting risks |

### Common Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `FileNotFoundError: credentials.json` | Credentials file not found | Download credentials and place in project directory |
| `SSL: WRONG_VERSION_NUMBER` | Thread SSL conflict | Use `drive_transfer_max.py` or reduce MAX_WORKERS |
| `API quota exceeded` | API requests too frequent | Reduce MAX_WORKERS or wait for quota reset |
| `Rate Limited (403)` | Request frequency too high | Increase retry delay, reduce concurrency |

## 📊 Dependencies

Main packages:
- `google-api-python-client`: Google Drive API client
- `google-auth-oauthlib`: OAuth 2.0 authentication
- `google-auth-httplib2`: HTTP 2.0 support
- `tqdm`: Progress bar display

See `requirements.txt` for complete dependencies

## 📝 License

MIT License

## 🐛 Feedback & Improvements

Encountered issues or have suggestions? Submit an issue or pull request!

---

**Last Updated**: May 3, 2026  
**Python Version**: 3.7+  
**Google API Version**: v3
