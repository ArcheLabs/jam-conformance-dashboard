"""Incrementally normalize report zips into structured evaluation data."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_FILE = REPO_ROOT / "data" / "reports.yaml"
REPORTS_DIR = REPO_ROOT / "data" / "raw" / "reports"
NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
REGISTRY_FILE = REPO_ROOT / "scripts" / "name_registry.yaml"
META_FILE = REPORTS_DIR / "metadata.json"
FAILURES_FILE = REPORTS_DIR / "failures.json"

LANES = ["L2a", "L2b", "L3a", "L3b"]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_registry() -> dict[str, Any]:
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_report_entries() -> list[dict[str, Any]]:
    if not REPORTS_FILE.exists():
        print(f"No report manifest found at {REPORTS_FILE}")
        return []
    raw = yaml.safe_load(REPORTS_FILE.read_text(encoding="utf-8")) or {}
    reports = raw.get("reports", []) if isinstance(raw, dict) else []
    return reports if isinstance(reports, list) else []


def lookup_client(registry: dict[str, Any], team_id: str, app_name: str) -> dict[str, str]:
    teams = registry.get("teams", {})
    entry = teams.get(team_id)
    if entry:
        return {
            "team_name": entry["team_name"],
            "client_name": entry["client_name"],
            "language": entry.get("language", ""),
            "language_color": entry.get("language_color", ""),
        }
    return {
        "team_name": app_name,
        "client_name": app_name,
        "language": "",
        "language_color": "",
    }


def parse_version(ver: Any) -> str:
    if isinstance(ver, dict):
        return f"{ver.get('major', 0)}.{ver.get('minor', 0)}.{ver.get('patch', 0)}"
    return str(ver)


def normalize_lane_report(zip_file: zipfile.ZipFile, manifest: dict[str, Any], lane_info: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any] | None:
    preset = lane_info["preset"]
    lane_dir = f"{preset}/"

    report_path_in_zip = None
    for name in zip_file.namelist():
        if name.startswith(lane_dir) and name.endswith("report.json"):
            report_path_in_zip = name
            break

    if not report_path_in_zip:
        return None

    try:
        report_data = json.loads(zip_file.read(report_path_in_zip))
    except (json.JSONDecodeError, KeyError) as exc:
        return {"preset": preset, "status": "error", "error": f"Failed to parse report.json: {exc}"}

    target = report_data.get("target", {})
    target_info = target.get("info", {})
    target_stats = target.get("stats", {})
    error = report_data.get("error")
    status = "error" if error is not None else lane_info.get("status", "unknown")

    app_name = target_info.get("app_name", "unknown")
    team_id = manifest.get("teamId", "")
    client_meta = lookup_client(registry, team_id, app_name)

    return {
        "preset": preset,
        "status": status,
        "error": str(error) if error is not None else None,
        "team_id": team_id,
        "team_h160": manifest.get("teamH160", ""),
        "target": manifest.get("target", ""),
        "suite_id": manifest.get("suiteId", ""),
        "client_name_raw": app_name,
        "client_name": client_meta["client_name"],
        "team_name": client_meta["team_name"],
        "language": client_meta["language"],
        "language_color": client_meta["language_color"],
        "client_version": parse_version(target_info.get("app_version", {})),
        "jam_version": parse_version(target_info.get("jam_version", {})),
        "steps": target_stats.get("steps", 0),
        "imported": target_stats.get("imported", 0),
        "import_ratio": round(
            target_stats.get("imported", 0) / max(target_stats.get("steps", 1), 1), 6
        ),
        "latency": {
            "min": target_stats.get("import_min"),
            "p50": target_stats.get("import_p50"),
            "p75": target_stats.get("import_p75"),
            "p90": target_stats.get("import_p90"),
            "p99": target_stats.get("import_p99"),
            "max": target_stats.get("import_max"),
            "mean": target_stats.get("import_mean"),
            "std_dev": target_stats.get("import_std_dev"),
        },
    }


def inspect_zip(zip_path: Path) -> dict[str, Any]:
    content = zip_path.read_bytes()
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        lane_dirs = sorted({n.split("/")[0] for n in names if "/" in n and n.endswith("report.json")})
        has_manifest = "manifest.json" in names
    return {
        "sha256": "0x" + hashlib.sha256(content).hexdigest(),
        "zip_size": len(content),
        "file_count": len(names),
        "lane_dirs": lane_dirs,
        "has_manifest": has_manifest,
    }


def is_zip_valid(zip_path: Path, expected_sha: str | None = None) -> bool:
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        return False
    if expected_sha:
        actual = "0x" + hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if actual.lower() != expected_sha.lower():
            return False
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())
            return "manifest.json" in names and any(n.endswith("report.json") for n in names)
    except Exception:
        return False


def normalize_zip_file(attestation_hash: str, zip_path: Path, registry: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                print("  No manifest.json in zip")
                return None

            manifest = json.loads(zf.read("manifest.json"))
            print(f"  Manifest: team={manifest.get('teamId', '')[:16]}... target={manifest.get('target', '')[:20]}...")

            lanes_in_manifest = manifest.get("lanes", [])
            if not lanes_in_manifest:
                print("  No lanes in manifest")
                return None

            results = []
            for lane in lanes_in_manifest:
                result = normalize_lane_report(zf, manifest, lane, registry)
                if result:
                    results.append(result)
                    print(f"    Lane {lane['preset']}: {result['status']}")

            return {
                "attestation_hash": attestation_hash,
                "suite_id": manifest.get("suiteId", ""),
                "team_id": manifest.get("teamId", ""),
                "team_h160": manifest.get("teamH160", ""),
                "target": manifest.get("target", ""),
                "lanes": results,
            }
    except (zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(f"  Error processing zip: {exc}")
        return None


def download_report(report: dict[str, Any], target_path: Path) -> tuple[Path | None, dict[str, Any] | None]:
    attestation = report["attestation"]
    url = report.get("report_url")
    expected_sha = report.get("sha256") or None

    def failure(reason: str) -> tuple[None, dict[str, Any]]:
        return None, {
            "attestation": attestation,
            "team_name": report.get("team_name", "unknown"),
            "report_url": url,
            "error": reason,
            "time": now_iso(),
        }

    if not url:
        return failure("missing report URL")

    headers = {"User-Agent": "jam-m1-conformance-dashboard/1.0"}
    tmp_name = None
    try:
        with requests.get(url, timeout=(20, 900), stream=True, headers=headers) as response:
            if response.status_code != 200:
                return failure(f"HTTP {response.status_code}")

            hsh = hashlib.sha256()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(target_path.parent), suffix=".download") as tmp:
                tmp_name = tmp.name
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    hsh.update(chunk)
                    tmp.write(chunk)

            actual_sha = "0x" + hsh.hexdigest()
            if expected_sha and actual_sha.lower() != expected_sha.lower():
                Path(tmp_name).unlink(missing_ok=True)
                return failure(f"SHA256 mismatch: expected {expected_sha}, actual {actual_sha}")

            Path(tmp_name).replace(target_path)
            if not is_zip_valid(target_path, expected_sha):
                target_path.unlink(missing_ok=True)
                return failure("invalid ZIP: manifest.json or report.json missing")
            return target_path, None
    except Exception as exc:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        return failure(repr(exc)[:300])


def load_existing_evaluations() -> list[dict[str, Any]]:
    raw = load_json(NORMALIZED_DIR / "evaluations.json", {})
    evaluations = raw.get("evaluations", []) if isinstance(raw, dict) else []
    return evaluations if isinstance(evaluations, list) else []


def write_clients(evaluations: list[dict[str, Any]]) -> None:
    clients: dict[str, dict[str, Any]] = {}
    for ev in evaluations:
        for lane in ev.get("lanes", []):
            tid = ev["team_id"]
            if tid not in clients:
                clients[tid] = {
                    "team_id": tid,
                    "team_h160": ev["team_h160"],
                    "team_name": lane["team_name"],
                    "client_name": lane["client_name"],
                    "language": lane["language"],
                    "language_color": lane["language_color"],
                }

    write_json(NORMALIZED_DIR / "clients.json", list(clients.values()))
    print(f"Saved {len(clients)} client entries to {NORMALIZED_DIR / 'clients.json'}")


def main() -> None:
    registry = load_registry()
    reports = load_report_entries()
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    existing = load_existing_evaluations()
    evaluations_by_hash = {
        ev["attestation_hash"]: ev
        for ev in existing
        if ev.get("attestation_hash")
    }
    print(f"Loaded {len(evaluations_by_hash)} previously normalized evaluations")

    old_meta = load_json(META_FILE, [])
    metadata_by_hash = {
        meta["attestation"]: meta
        for meta in old_meta
        if isinstance(meta, dict) and meta.get("attestation")
    }
    failures: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="jam-reports-") as tmpdir:
        temp_reports_dir = Path(tmpdir)

        for report in reports:
            attestation = report.get("attestation")
            if not attestation:
                continue
            if attestation in evaluations_by_hash:
                print(f"Skipping {attestation[:16]}... already normalized")
                continue

            print(f"Processing {attestation[:16]}...")
            expected_sha = report.get("sha256") or None
            local_zip = REPORTS_DIR / f"{attestation}.zip"
            zip_path: Path | None = None

            if is_zip_valid(local_zip, expected_sha):
                zip_path = local_zip
                print("  Using local cached ZIP")
            else:
                temp_zip = temp_reports_dir / f"{attestation}.zip"
                zip_path, failure = download_report(report, temp_zip)
                if failure:
                    failures.append(failure)
                    print(f"  FAIL: {failure['error']}")
                    continue

            evaluation = normalize_zip_file(attestation, zip_path, registry)
            if not evaluation:
                failures.append({
                    "attestation": attestation,
                    "team_name": report.get("team_name", "unknown"),
                    "report_url": report.get("report_url", ""),
                    "error": "normalization failed",
                    "time": now_iso(),
                })
                continue

            evaluations_by_hash[attestation] = evaluation
            metadata_by_hash[attestation] = {
                "attestation": attestation,
                "team_name": report.get("team_name", "unknown"),
                "report_url": report.get("report_url", ""),
                "expected_sha256": expected_sha,
                "downloaded_at": now_iso(),
                "source": report.get("source", "notion"),
                **inspect_zip(zip_path),
            }
            print(f"  -> {len(evaluation['lanes'])} lanes normalized")

    ordered_evaluations = sorted(
        evaluations_by_hash.values(),
        key=lambda ev: (ev.get("team_id", ""), ev.get("attestation_hash", "")),
    )
    write_json(NORMALIZED_DIR / "evaluations.json", {
        "generated_at": now_iso(),
        "count": len(ordered_evaluations),
        "evaluations": ordered_evaluations,
    })
    print(f"\nSaved {len(ordered_evaluations)} evaluations to {NORMALIZED_DIR / 'evaluations.json'}")

    metadata = sorted(
        metadata_by_hash.values(),
        key=lambda meta: ((meta.get("team_name") or "").lower(), meta.get("attestation") or ""),
    )
    write_json(META_FILE, metadata)
    write_json(FAILURES_FILE, failures)
    write_clients(ordered_evaluations)
    print(f"Failures: {len(failures)} -> {FAILURES_FILE}")


if __name__ == "__main__":
    main()
