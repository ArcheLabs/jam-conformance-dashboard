"""Print a summary of report processing status after the pipeline completes."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "raw" / "reports"
META_FILE = REPORTS_DIR / "metadata.json"
FAILURES_FILE = REPORTS_DIR / "failures.json"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


metadata = load_json(META_FILE, [])
failures = load_json(FAILURES_FILE, [])

valid = [m for m in metadata if m.get("has_manifest")]
invalid = [m for m in metadata if not m.get("has_manifest")]

print("\nReport processing summary")
print(f"  Valid reports:   {len(valid)}")
print(f"  Invalid reports: {len(invalid)}")
print(f"  Failures:        {len(failures)}")

if invalid:
    print("\nInvalid cached reports:")
    for item in invalid:
        print(f"  {item.get('attestation', '')[:18]:<20} {item.get('team_name', '?')}")

if failures:
    print("\nDownload/normalization failures:")
    for item in failures:
        print(f"  {item.get('attestation', '')[:18]:<20} {item.get('team_name', '?'):<25} {item.get('error', 'unknown')}")
