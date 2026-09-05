import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in (ROOT / "scripts", ROOT / "scripts" / "video"):
    sys.path.insert(0, str(p))
