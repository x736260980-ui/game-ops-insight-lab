"""Local FastAPI adapter built on MediaCrawler's internal clients.

MediaCrawler currently resolves ``libs/douyin.js`` relative to the process
working directory. Reproduce its official entrypoint environment before any
platform package is imported, without changing the downloaded source.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
os.chdir(SOURCE_ROOT)
