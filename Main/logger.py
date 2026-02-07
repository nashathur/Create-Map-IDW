# logger.py
"""
Execution logger — appends a record to execution_log.csv on every run.
"""

import os
import csv
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "execution_log.csv")

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


def log_execution(cfg, output_filename, duration):
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        writer.writerow({
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
        })
