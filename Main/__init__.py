# logger.py
"""
Execution logger — appends a record to execution_log.csv in the GitHub repo.
"""

import csv
import io
import base64
import requests
from datetime import datetime

REPO = "nashathur/Create-Map-IDW"
FILE_PATH = "execution_log.csv"
BRANCH = "main"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

FIELDNAMES = [
    "timestamp",
    "jenis_peta",
    "tipe_peta",
    "skala_peta",
    "wilayah",
    "year",
    "month",
    "dasarian",
    "year_ver",
    "month_ver",
    "dasarian_ver",
    "png_only",
    "hgt",
    "output_file",
    "duration_seconds",
]


def _get_token():
    try:
        from google.colab import userdata
        return userdata.get('GITHUB_TOKEN')
    except Exception:
        return None


def log_execution(cfg, output_filename, duration):
    token = _get_token()
    if not token:
        print("GITHUB_TOKEN not found in Colab Secrets. Skipping log.")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    # build new row
    row = {
        "timestamp": datetime.now().isoformat(),
        "jenis_peta": cfg.peta,
        "tipe_peta": cfg.tipe,
        "skala_peta": cfg.skala,
        "wilayah": cfg.wilayah,
        "year": cfg.year,
        "month": cfg.month,
        "dasarian": cfg.dasarian,
        "year_ver": cfg.year_ver,
        "month_ver": cfg.month_ver,
        "dasarian_ver": cfg.dasarian_ver,
        "png_only": cfg.png_only,
        "hgt": cfg.hgt,
        "output_file": output_filename,
        "duration_seconds": round(duration, 2),
    }

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDNAMES)

    # try to fetch existing file
    sha = None
    resp = requests.get(API_URL, headers=headers, params={"ref": BRANCH})

    if resp.status_code == 200:
        # file exists — decode existing content, append
        file_data = resp.json()
        sha = file_data["sha"]
        existing = base64.b64decode(file_data["content"]).decode("utf-8")
        buf.write(existing)
        if not existing.endswith("\n"):
            buf.write("\n")
        writer.writerow(row)
    else:
        # file doesn't exist — write header + first row
        writer.writeheader()
        writer.writerow(row)

    # commit
    new_content = base64.b64encode(buf.getvalue().encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"log: {cfg.peta} - {cfg.tipe} - {cfg.skala} ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        "content": new_content,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(API_URL, headers=headers, json=payload)
    if put_resp.status_code in (200, 201):
        print("Log saved to GitHub.")
    else:
        print(f"Failed to save log: {put_resp.status_code} {put_resp.text}")
