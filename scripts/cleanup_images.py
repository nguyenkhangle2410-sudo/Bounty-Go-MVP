#!/usr/bin/env python3
"""Cleanup script for static/images.

Deletes files older than a given number of days and enforces a total size limit.
Run manually or schedule via cron/Task Scheduler.
"""
import os
import time
from pathlib import Path

IMAGES_DIR = Path(os.path.join(os.getcwd(), 'static', 'images'))
MAX_AGE_DAYS = int(os.environ.get('CLEANUP_MAX_AGE_DAYS', '30'))
MAX_TOTAL_BYTES = int(os.environ.get('CLEANUP_MAX_TOTAL_BYTES', str(200 * 1024 * 1024)))  # 200 MB


def cleanup():
    if not IMAGES_DIR.exists():
        print('No images directory found, nothing to do.')
        return

    now = time.time()
    files = [p for p in IMAGES_DIR.iterdir() if p.is_file()]

    # Delete old files
    cutoff = now - (MAX_AGE_DAYS * 86400)
    for f in files:
        try:
            if f.stat().st_mtime < cutoff:
                print(f'Removing old file: {f.name}')
                f.unlink()
        except Exception as e:
            print(f'Error removing {f}: {e}')

    # Recalculate and enforce total size
    files = sorted([p for p in IMAGES_DIR.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    while total > MAX_TOTAL_BYTES and files:
        oldest = files.pop(0)
        try:
            print(f'Removing to reduce size: {oldest.name}')
            total -= oldest.stat().st_size
            oldest.unlink()
        except Exception as e:
            print(f'Error removing {oldest}: {e}')


if __name__ == '__main__':
    cleanup()
