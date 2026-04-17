from __future__ import annotations

import sys
from pathlib import Path


SRC_PATH = Path(__file__).resolve().parents[1] / "src"
WORKER_SRC_PATH = Path(__file__).resolve().parents[2] / "worker" / "src"

for path in (SRC_PATH, WORKER_SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
