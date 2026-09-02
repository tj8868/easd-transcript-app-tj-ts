import os
import json
import httpx
from typing import Dict, Any, Optional

GDRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GDRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"

def get_or_create_easd_folder(access_token: str, folder_name: str = "EASD - meeting minutes") -> str:
    """Finds or creates the target Google Drive folder."""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. Search for existing folder
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    url = f"{GDRIVE_API_BASE}/files?q={query}"
    
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            files = resp.json().get("files", [])
            if files:
                return files[0]["id"]
                
        # 2. Create folder if not found
        create_payload = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        create_resp = client.post(f"{GDRIVE_API_BASE}/files", headers=headers, json=create_payload)
        create_resp.raise_for_status()
        return create_resp.json()["id"]

def upload_docx_to_gdrive(
    file_bytes: bytes,
    file_name: str,
    access_token: str,
    folder_name: str = "EASD - meeting minutes"
) -> Dict[str, Any]:
    """
    Uploads a .docx file to Google Drive under folder 'EASD - meeting minutes'.
    """
    folder_id = get_or_create_easd_folder(access_token, folder_name)
    headers = {"Authorization": f"Bearer {access_token}"}
    
    metadata = {
        "name": file_name,
        "parents": [folder_id],
        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    
    files = {
        "data": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
        "file": (file_name, file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }
    
    url = f"{GDRIVE_UPLOAD_BASE}/files?uploadType=multipart&fields=id,name,webViewLink,webContentLink"
    
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, files=files)
        resp.raise_for_status()
        return resp.json()
