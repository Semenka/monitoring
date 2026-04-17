"""Optional helper to fetch an .mdb from Google Drive with gdown.

Large files stored in private Drive folders cannot be fetched anonymously; in
that case, download manually through the Drive UI and drop the file into
`data/raw/`.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def fetch_mdb(file_id: str, dest: str | Path) -> Path:
    import gdown

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, str(dest), quiet=False)
    return dest


def fetch_from_env(env_var: str, dest: str | Path) -> Path:
    load_dotenv()
    file_id = os.environ.get(env_var)
    if not file_id:
        raise KeyError(f"{env_var} not set in environment or .env file")
    return fetch_mdb(file_id, dest)
