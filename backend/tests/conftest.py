import sys
from pathlib import Path

# oracle lives in /data (mounted in the container, ../data on host)
for candidate in (Path("/data"), Path(__file__).resolve().parents[2] / "data"):
    if (candidate / "ground_truth.py").exists():
        sys.path.insert(0, str(candidate))
        break
else:
    raise RuntimeError("ground_truth.py not found — mount or check /data")
