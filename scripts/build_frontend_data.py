"""Build frontend leaderboard JSON from normalized evaluation data."""

import json
import math
import os
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
DATA_DIR = REPO_ROOT / "src" / "data"

LANES = ["L2a", "L2b", "L3a", "L3b"]

LANE_WEIGHTS = {
    "p50": 0.50,
    "p90": 0.30,
    "p99": 0.15,
    "max": 0.05,
}


def lane_score(stats):
    """Compute a single lane's score from latency stats."""
    if not stats:
        return None
    p50 = stats.get("p50") or 0
    p90 = stats.get("p90") or 0
    p99 = stats.get("p99") or 0
    max_val = stats.get("max") or 0
    return (
        LANE_WEIGHTS["p50"] * p50
        + LANE_WEIGHTS["p90"] * p90
        + LANE_WEIGHTS["p99"] * p99
        + LANE_WEIGHTS["max"] * min(max_val, p99 * 5)
    )


def geometric_mean(values):
    """Compute geometric mean of a list of positive values."""
    filtered = [v for v in values if v is not None and v > 0]
    if not filtered:
        return None
    log_sum = sum(math.log(v) for v in filtered)
    return math.exp(log_sum / len(filtered))


def build_leaderboard(evaluations):
    """Build leaderboard from normalized evaluations."""
    team_data = defaultdict(lambda: {
        "team_id": "",
        "team_name": "",
        "client_name": "",
        "client_version": "",
        "jam_version": "",
        "language": "",
        "language_color": "",
        "latest_attestation": "",
        "completed_lanes": [],
        "error_lanes": [],
        "lanes": {},
    })

    for ev in evaluations:
        tid = ev["team_id"]
        entry = team_data[tid]
        entry["team_id"] = tid
        entry["team_h160"] = ev.get("team_h160", "")
        entry["target"] = ev.get("target", "")

        for lane in ev["lanes"]:
            preset = lane["preset"]
            if not entry["team_name"]:
                entry["team_name"] = lane["team_name"]
                entry["client_name"] = lane["client_name"]
                entry["language"] = lane.get("language", "")
                entry["language_color"] = lane.get("language_color", "")
                entry["client_version"] = lane["client_version"]
                entry["jam_version"] = lane["jam_version"]
                entry["latest_attestation"] = ev["attestation_hash"]

            if lane["status"] == "completed" and not lane["error"]:
                entry["completed_lanes"].append(preset)
                entry["lanes"][preset] = {
                    "p50": lane["latency"]["p50"],
                    "p90": lane["latency"]["p90"],
                    "p99": lane["latency"]["p99"],
                    "max": lane["latency"]["max"],
                    "mean": lane["latency"]["mean"],
                    "std_dev": lane["latency"]["std_dev"],
                    "imported": lane["imported"],
                    "steps": lane["steps"],
                    "import_ratio": lane["import_ratio"],
                    "client_version": lane["client_version"],
                    "jam_version": lane["jam_version"],
                }
            else:
                entry["error_lanes"].append({
                    "preset": preset,
                    "error": lane.get("error", "unknown error"),
                })

    teams = []
    for tid, data in team_data.items():
        lane_scores = []
        for lane_name in LANES:
            lane_stats = data["lanes"].get(lane_name)
            if lane_stats:
                score = lane_score(lane_stats)
                lane_scores.append(score)
            else:
                lane_scores.append(None)

        overall_score = geometric_mean(lane_scores)

        metrics = {"geo_p50": None, "geo_p90": None, "geo_p99": None, "total_imported": 0}
        p50s = []
        p90s = []
        p99s = []
        total_imported = 0
        for lane_name in LANES:
            lane_stats = data["lanes"].get(lane_name)
            if lane_stats:
                p50s.append(lane_stats["p50"])
                p90s.append(lane_stats["p90"])
                p99s.append(lane_stats["p99"])
                total_imported += lane_stats["imported"]
        if p50s:
            metrics["geo_p50"] = geometric_mean(p50s)
            metrics["geo_p90"] = geometric_mean(p90s)
            metrics["geo_p99"] = geometric_mean(p99s)
            metrics["total_imported"] = total_imported

        lanes_display = {}
        for lane_name in LANES:
            lane_stats = data["lanes"].get(lane_name)
            if lane_stats:
                lanes_display[lane_name] = {
                    "p50": lane_stats["p50"],
                    "p90": lane_stats["p90"],
                    "p99": lane_stats["p99"],
                    "imported": lane_stats["imported"],
                    "import_ratio": lane_stats["import_ratio"],
                }

        teams.append({
            "team_id": tid,
            "team_name": data["team_name"],
            "client_name": data["client_name"],
            "client_version": data["client_version"],
            "jam_version": data["jam_version"],
            "language": data["language"],
            "language_color": data["language_color"],
            "latest_attestation": data["latest_attestation"],
            "completed_count": len(data["completed_lanes"]),
            "total_lanes": len(LANES),
            "score": round(overall_score, 4) if overall_score else None,
            "metrics": {
                "geo_p50": round(metrics["geo_p50"], 2) if metrics["geo_p50"] else None,
                "geo_p90": round(metrics["geo_p90"], 2) if metrics["geo_p90"] else None,
                "geo_p99": round(metrics["geo_p99"], 2) if metrics["geo_p99"] else None,
                "total_imported": metrics["total_imported"],
            },
            "lanes": lanes_display,
            "error_lanes": data["error_lanes"],
        })

    teams.sort(key=lambda t: (t["score"] if t["score"] else float("inf")))

    ranked = []
    for i, team in enumerate(teams, 1):
        team["rank"] = i
        ranked.append(team)

    complete = [t for t in ranked if t["completed_count"] == len(LANES)]
    partial = [t for t in ranked if t["completed_count"] < len(LANES) and t["completed_count"] > 0]
    failed = [t for t in ranked if t["completed_count"] == 0]

    return {
        "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "methodology_version": 1,
        "lanes": LANES,
        "scoring": {
            "description": "Geometric mean of lane scores. Each lane score = 0.50*p50 + 0.30*p90 + 0.15*p99 + 0.05*max_capped",
            "lane_weights": LANE_WEIGHTS,
            "aggregation": "geometric_mean",
        },
        "teams": ranked,
        "complete_teams": complete,
        "partial_teams": partial,
        "failed_teams": failed,
    }


def build_sources(evaluations):
    """Build source info from evaluations."""
    attestations = []
    for ev in evaluations:
        attestations.append({
            "attestation_hash": ev["attestation_hash"],
            "team_id": ev["team_id"],
            "suite_id": ev.get("suite_id", ""),
            "target": ev.get("target", ""),
            "lanes": [l["preset"] for l in ev.get("lanes", [])],
        })
    return {
        "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "attestations": attestations,
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    eval_path = NORMALIZED_DIR / "evaluations.json"
    if not eval_path.exists():
        print("No normalized evaluations found. Run normalize_reports.py first.")
        return

    with open(eval_path, "r") as f:
        data = json.load(f)

    evaluations = data.get("evaluations", [])
    print(f"Loaded {len(evaluations)} evaluations")

    leaderboard = build_leaderboard(evaluations)

    lb_path = DATA_DIR / "leaderboard.json"
    with open(lb_path, "w") as f:
        json.dump(leaderboard, f, indent=2)
    print(f"Saved leaderboard ({len(leaderboard['teams'])} teams) to {lb_path}")

    sources = build_sources(evaluations)
    src_path = DATA_DIR / "source-info.json"
    with open(src_path, "w") as f:
        json.dump(sources, f, indent=2)
    print(f"Saved source info to {src_path}")

    full_eval_path = DATA_DIR / "evaluations.json"
    with open(full_eval_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved full evaluations to {full_eval_path}")


if __name__ == "__main__":
    main()
