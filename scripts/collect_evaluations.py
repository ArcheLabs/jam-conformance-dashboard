"""Collect JAM Prize evaluations from a Notion page, extract report ZIP URLs
from Jamtoaster attestation pages, download ZIPs, and verify SHA-256.

The script is intentionally idempotent:
- Notion results are accumulated and de-duplicated by attestation hash.
- Report ZIPs are cached in data/raw/reports/{attestation}.zip.
- Failures are written to data/raw/reports/failures.json instead of being hidden.

Usage:
    python scripts/collect_evaluations.py --refresh-notion
    python scripts/collect_evaluations.py --refresh-notion --expect-count 24
    python scripts/collect_evaluations.py --notion-url 'https://...'
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import tempfile
import time
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests
import yaml

DEFAULT_NOTION_URL = (
    "https://polkadottechnicalfellowship.notion.site/"
    "2ef96f88d0a78051b94ef4a6d6c9be8c"
    "?v=2ef96f88d0a78036b33a000c2cb9a0b1"
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_FILE = REPO_ROOT / "data" / "evaluations.json"
REPORTS_FILE = REPO_ROOT / "data" / "reports.yaml"
REPORTS_DIR = REPO_ROOT / "data" / "raw" / "reports"
META_FILE = REPORTS_DIR / "metadata.json"
FAILURES_FILE = REPORTS_DIR / "failures.json"

ATTESTATION_RE = re.compile(
    r"https?://fuzz\.jamtoaster\.network/attestation/(0x[a-fA-F0-9]{64})"
)
HASH_RE = re.compile(r"0x[a-fA-F0-9]{64}")
ZIP_RE = re.compile(r"https?://[^\s<'\")]+\.zip(?:\?[^\s<'\")]+)?")
SHA_RE = re.compile(r"(?:EXPECTED\s+SHA-256|SHA-256|sha256)[^0-9a-fA-F]*(0x)?([a-fA-F0-9]{64})", re.I)

DEFAULT_BROWSER_CONCURRENCY = 4
DEFAULT_DOWNLOAD_CONCURRENCY = 3
NOTION_STABLE_ROUNDS = 6
NOTION_MAX_SCROLL_ROUNDS = 80


@dataclass
class Evaluation:
    attestation: str
    team_name: str = "unknown"
    attestation_url: str = ""
    source: str = "notion"
    row_text: str = ""
    report_url: str | None = None
    sha256: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dirs() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EVALS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def load_report_entries() -> list[dict[str, Any]]:
    if not REPORTS_FILE.exists():
        return []
    try:
        raw = yaml.safe_load(REPORTS_FILE.read_text()) or {}
    except Exception:
        return []
    reports = raw.get("reports", []) if isinstance(raw, dict) else []
    return reports if isinstance(reports, list) else []


def write_report_entries(reports: list[dict[str, Any]]) -> None:
    REPORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "reports": sorted(
            reports,
            key=lambda r: ((r.get("team_name") or "").lower(), r.get("attestation") or ""),
        )
    }
    tmp = REPORTS_FILE.with_suffix(REPORTS_FILE.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    tmp.replace(REPORTS_FILE)


def normalize_hash(value: str) -> str | None:
    if not value:
        return None
    m = HASH_RE.search(value)
    return m.group(0).lower() if m else None


def normalize_report_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    h = normalize_hash(str(entry.get("attestation", "")))
    if not h:
        parsed = normalize_attestation_url(str(entry.get("attestation_url", "") or entry.get("url", "")))
        if parsed:
            h = parsed[0]
    if not h:
        return None

    report_url = entry.get("report_url") or entry.get("url") or ""
    sha256 = entry.get("sha256") or entry.get("expected_sha256") or ""
    source = entry.get("source") or "manual"
    source = "manual" if source == "manual" else "notion"
    return {
        "attestation": h,
        "team_name": entry.get("team_name") or entry.get("client_name") or "unknown",
        "language": entry.get("language") or "",
        "status": entry.get("status") or "",
        "attestation_url": entry.get("attestation_url") or f"https://fuzz.jamtoaster.network/attestation/{h}",
        "report_url": report_url,
        "sha256": sha256,
        "source": source,
    }


def merge_report_entries(existing: list[dict[str, Any]], discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}

    for entry in existing:
        normalized = normalize_report_entry(entry)
        if normalized:
            by_hash[normalized["attestation"]] = normalized

    for entry in discovered:
        normalized = normalize_report_entry({**entry, "source": entry.get("source") or "notion"})
        if not normalized:
            continue

        h = normalized["attestation"]
        old = by_hash.get(h)
        if not old:
            by_hash[h] = normalized
            continue

        manual_override = old.get("source") == "manual"
        merged = {**old}
        for key in ("team_name", "language", "status", "attestation_url"):
            if normalized.get(key):
                merged[key] = normalized[key]

        if manual_override:
            # Manual report URLs are the fallback path for broken Jamtoaster links.
            merged["source"] = "manual"
            if not merged.get("sha256") and normalized.get("sha256"):
                merged["sha256"] = normalized["sha256"]
        else:
            merged["report_url"] = normalized.get("report_url") or merged.get("report_url", "")
            merged["sha256"] = normalized.get("sha256") or merged.get("sha256", "")
            merged["source"] = normalized.get("source") or merged.get("source") or "notion"

        by_hash[h] = merged

    return list(by_hash.values())


def normalize_attestation_url(url: str) -> tuple[str, str] | None:
    m = ATTESTATION_RE.search(url or "")
    if not m:
        return None
    h = m.group(1).lower()
    return h, f"https://fuzz.jamtoaster.network/attestation/{h}"


def clean_team_name(row_text: str, attestation: str) -> str:
    """Best-effort team/client display name from a Notion row.

    The stable identity should still be teamId from manifest.json later. This only
    prevents the collector from losing human-readable context.
    """
    if not row_text:
        return "unknown"

    text = row_text.replace("\u00a0", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace(attestation, " ")
    text = re.sub(r"0x[a-fA-F0-9]{8,}", " ", text)
    text = re.sub(r"\b(report|attestation|url|completed|failed|pending)\b", " ", text, flags=re.I)

    candidates = []
    for part in re.split(r"[\n|\t]+", text):
        part = re.sub(r"\s+", " ", part).strip(" -–—,:;")
        if not part:
            continue
        if len(part) < 2 or len(part) > 80:
            continue
        if part.lower() in {"jam prize evaluations", "evaluations", "name", "team", "client"}:
            continue
        candidates.append(part)

    return candidates[0] if candidates else "unknown"


async def collect_visible_attestations(page) -> list[dict[str, str]]:
    """Extract all currently visible attestation links/text from a Notion page."""
    return await page.evaluate(
        r"""
        () => {
          const out = [];
          const rx = /https?:\/\/fuzz\.jamtoaster\.network\/attestation\/0x[a-fA-F0-9]{64}/g;

          function rowTextFor(el) {
            let cur = el;
            for (let i = 0; cur && i < 8; i++, cur = cur.parentElement) {
              const role = cur.getAttribute && cur.getAttribute('role');
              const cls = cur.className ? String(cur.className) : '';
              if (role === 'row' || cls.includes('notion-collection-item') || cls.includes('notion-table-view-row')) {
                return cur.innerText || '';
              }
            }
            return (el.closest('[role="row"]') || el.parentElement || el).innerText || '';
          }

          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const href = new URL(a.getAttribute('href'), location.href).href;
            const matches = href.match(rx);
            if (!matches) continue;
            for (const url of matches) {
              out.push({href: url, row_text: rowTextFor(a), source: 'anchor'});
            }
          }

          const bodyText = document.body ? document.body.innerText || '' : '';
          for (const url of bodyText.match(rx) || []) {
            out.push({href: url, row_text: bodyText.slice(Math.max(0, bodyText.indexOf(url) - 300), bodyText.indexOf(url) + 300), source: 'body_text'});
          }

          return out;
        }
        """
    )


async def scroll_notion_once(page) -> dict[str, Any]:
    """Scroll both the mouse viewport and likely scrollable containers.

    Notion often uses nested scroll containers/virtualized rows. Relying only on
    window.scrollTo can miss database rows.
    """
    await page.mouse.wheel(0, 2600)
    return await page.evaluate(
        r"""
        () => {
          const candidates = [document.scrollingElement, document.documentElement, document.body]
            .concat(Array.from(document.querySelectorAll('div')))
            .filter(Boolean)
            .filter(el => el.scrollHeight > el.clientHeight + 80);

          candidates.sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
          const touched = [];
          for (const el of candidates.slice(0, 8)) {
            const before = el.scrollTop || 0;
            el.scrollTop = Math.min(before + 2600, el.scrollHeight);
            touched.push({before, after: el.scrollTop || 0, max: el.scrollHeight - el.clientHeight});
          }
          return {y: window.scrollY, height: document.body ? document.body.scrollHeight : 0, touched};
        }
        """
    )


async def collect_evaluations_from_notion(
    notion_url: str,
    *,
    expect_count: int | None = None,
    headless: bool = True,
) -> list[Evaluation]:
    from playwright.async_api import async_playwright

    seen: dict[str, Evaluation] = {}
    response_tasks: set[asyncio.Task] = set()

    async def inspect_response(response) -> None:
        # Notion embeds database rows in JSON responses. Capturing these responses
        # makes the collector less dependent on what is currently mounted in the DOM.
        try:
            url = response.url
            ctype = (response.headers.get("content-type") or "").lower()
            if "notion" not in url and "jamtoaster" not in url:
                return
            if not any(t in ctype for t in ("json", "text", "javascript")):
                return
            text = await response.text()
            if "fuzz.jamtoaster.network/attestation" not in text:
                return
            for url_match in ATTESTATION_RE.finditer(text):
                h = url_match.group(1).lower()
                if h not in seen:
                    att_url = f"https://fuzz.jamtoaster.network/attestation/{h}"
                    seen[h] = Evaluation(
                        attestation=h,
                        attestation_url=att_url,
                        team_name="unknown",
                        row_text="",
                        source="notion_response",
                    )
        except Exception:
            # Response parsing is opportunistic; DOM extraction below remains primary.
            return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1400},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        def on_response(response):
            task = asyncio.create_task(inspect_response(response))
            response_tasks.add(task)
            task.add_done_callback(response_tasks.discard)

        page.on("response", on_response)

        print(f"Opening Notion evaluations page: {notion_url}")
        await page.goto(notion_url, wait_until="domcontentloaded", timeout=60_000)

        # Give Notion time to mount the database shell, but do not rely on this alone.
        try:
            await page.wait_for_selector("text=Evaluation", timeout=12_000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)

        stable_rounds = 0
        last_count = 0

        for round_no in range(1, NOTION_MAX_SCROLL_ROUNDS + 1):
            visible = await collect_visible_attestations(page)
            added = 0
            for item in visible:
                parsed = normalize_attestation_url(item.get("href", ""))
                if not parsed:
                    continue
                h, att_url = parsed
                row_text = item.get("row_text") or ""
                team_name = clean_team_name(row_text, h)

                if h not in seen:
                    seen[h] = Evaluation(
                        attestation=h,
                        attestation_url=att_url,
                        team_name=team_name,
                        row_text=row_text[:1000],
                        source=item.get("source", "notion_dom"),
                    )
                    added += 1
                elif seen[h].team_name == "unknown" and team_name != "unknown":
                    seen[h].team_name = team_name
                    seen[h].row_text = row_text[:1000]

            if response_tasks:
                await asyncio.wait(response_tasks, timeout=1.5)

            current_count = len(seen)
            print(f"  Notion round {round_no:02d}: {current_count} evaluations (+{added})")

            if expect_count and current_count >= expect_count:
                break

            if current_count == last_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                last_count = current_count

            if stable_rounds >= NOTION_STABLE_ROUNDS:
                break

            await scroll_notion_once(page)
            await page.wait_for_timeout(1200)

        if response_tasks:
            await asyncio.wait(response_tasks, timeout=5)
        await context.close()
        await browser.close()

    evals = sorted(seen.values(), key=lambda e: (e.team_name.lower(), e.attestation))
    if expect_count and len(evals) < expect_count:
        print(f"WARNING: expected {expect_count} evaluations, collected {len(evals)}")
    return evals


def read_evaluations() -> list[dict[str, Any]]:
    raw = load_json(EVALS_FILE, [])
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for ev in raw:
        h = normalize_hash(str(ev.get("attestation", "")))
        if not h:
            # Also accept entries that only have an attestation URL.
            parsed = normalize_attestation_url(str(ev.get("attestation_url", "") or ev.get("url", "")))
            if parsed:
                h = parsed[0]
        if not h:
            continue
        out.append({
            **ev,
            "attestation": h,
            "attestation_url": ev.get("attestation_url") or f"https://fuzz.jamtoaster.network/attestation/{h}",
            "team_name": ev.get("team_name") or ev.get("client_name") or "unknown",
        })
    return out


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


async def extract_attestation_data(context, sem: asyncio.Semaphore, ev: dict[str, Any]) -> dict[str, Any]:
    """Open one Jamtoaster attestation page and extract report URL/SHA."""
    h = ev["attestation"]
    url = ev.get("attestation_url") or f"https://fuzz.jamtoaster.network/attestation/{h}"

    async with sem:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            # Wait for either the ZIP URL to appear or for the app to finish a reasonable render pass.
            for _ in range(6):
                result = await page.evaluate(
                    r"""
                    () => {
                      const text = document.body ? document.body.innerText || '' : '';
                      const html = document.documentElement ? document.documentElement.innerHTML || '' : '';
                      const src = text + '\n' + html;
                      const zip = src.match(/https?:\/\/[^\s<'")]+\.zip(?:\?[^\s<'")]+)?/);
                      const sha = src.match(/(?:EXPECTED\s+SHA-256|SHA-256|sha256)[^0-9a-fA-F]*(0x)?([a-fA-F0-9]{64})/i);
                      return {
                        report_url: zip ? zip[0] : null,
                        sha256: sha ? ('0x' + sha[2].toLowerCase()) : null,
                        text_len: text.length
                      };
                    }
                    """
                )
                if result.get("report_url"):
                    return {**result, "attestation": h, "error": None}
                await page.wait_for_timeout(2500)

            return {"attestation": h, "report_url": None, "sha256": None, "error": "report URL not found"}
        except Exception as exc:
            return {"attestation": h, "report_url": None, "sha256": None, "error": repr(exc)[:300]}
        finally:
            await page.close()


def download_zip_sync(ev: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    h = ev["attestation"]
    url = ev.get("report_url")
    expected_sha = ev.get("sha256")
    team_name = ev.get("team_name", "unknown")
    zip_path = REPORTS_DIR / f"{h}.zip"

    def failure(reason: str) -> tuple[None, dict[str, Any]]:
        return None, {"attestation": h, "team_name": team_name, "report_url": url, "error": reason, "time": now_iso()}

    if not url:
        return failure("missing report URL")

    if is_zip_valid(zip_path, expected_sha):
        meta = inspect_zip(zip_path)
        return {
            "attestation": h,
            "team_name": team_name,
            "report_url": url,
            "expected_sha256": expected_sha,
            "downloaded_at": ev.get("downloaded_at") or now_iso(),
            **meta,
        }, None

    if expected_sha:
        other = REPORTS_DIR / f"0x{expected_sha.removeprefix('0x')}.zip"
        if other.exists() and other != zip_path and is_zip_valid(other, expected_sha):
            other.replace(zip_path)
            meta = inspect_zip(zip_path)
            return {
                "attestation": h,
                "team_name": team_name,
                "report_url": url,
                "expected_sha256": expected_sha,
                "downloaded_at": now_iso(),
                **meta,
            }, None

    headers = {"User-Agent": "jam-m1-conformance-dashboard/1.0"}
    last_error = "unknown download error"

    for retry in range(1, 4):
        tmp_name = None
        try:
            with requests.get(url, timeout=(20, 600), stream=True, headers=headers) as r:
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code}"
                    time.sleep(3 * retry)
                    continue

                hsh = hashlib.sha256()
                with tempfile.NamedTemporaryFile(delete=False, dir=str(REPORTS_DIR), suffix=".download") as tmp:
                    tmp_name = tmp.name
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        hsh.update(chunk)
                        tmp.write(chunk)

                actual_sha = "0x" + hsh.hexdigest()
                if expected_sha and actual_sha.lower() != expected_sha.lower():
                    Path(tmp_name).unlink(missing_ok=True)
                    return failure(f"SHA256 mismatch: expected {expected_sha}, actual {actual_sha}")

                Path(tmp_name).replace(zip_path)
                if not is_zip_valid(zip_path, expected_sha):
                    zip_path.unlink(missing_ok=True)
                    return failure("invalid ZIP: manifest.json or report.json missing")

                meta = inspect_zip(zip_path)
                return {
                    "attestation": h,
                    "team_name": team_name,
                    "report_url": url,
                    "expected_sha256": expected_sha,
                    "downloaded_at": now_iso(),
                    **meta,
                }, None
        except Exception as exc:
            last_error = repr(exc)[:300]
            if tmp_name:
                Path(tmp_name).unlink(missing_ok=True)
            time.sleep(3 * retry)

    return failure(last_error)


async def download_and_verify_all(evals: list[dict[str, Any]], concurrency: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sem = asyncio.Semaphore(concurrency)

    async def run_one(ev: dict[str, Any]):
        async with sem:
            h = ev["attestation"]
            print(f"  [{h[:16]}] downloading/checking...")
            return await asyncio.to_thread(download_zip_sync, ev)

    results = await asyncio.gather(*(run_one(ev) for ev in evals))
    metadata: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for meta, fail in results:
        if meta:
            metadata.append(meta)
            print(f"  [{meta['attestation'][:16]}] OK ({len(meta.get('lane_dirs', []))} lanes)")
        if fail:
            failures.append(fail)
            print(f"  [{fail['attestation'][:16]}] FAIL: {fail['error']}")
    return metadata, failures


def merge_cached_metadata(evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reuse valid ZIPs already on disk and preserve metadata where possible."""
    old_meta = load_json(META_FILE, [])
    old_by_hash = {m.get("attestation"): m for m in old_meta if m.get("attestation")}
    merged: list[dict[str, Any]] = []

    for ev in evals:
        h = ev["attestation"]
        expected_sha = ev.get("sha256")
        zip_path = REPORTS_DIR / f"{h}.zip"
        if is_zip_valid(zip_path, expected_sha):
            meta = inspect_zip(zip_path)
            old = old_by_hash.get(h, {})
            merged.append({
                **old,
                "attestation": h,
                "team_name": ev.get("team_name") or old.get("team_name") or "unknown",
                "report_url": ev.get("report_url") or old.get("report_url") or "",
                "expected_sha256": expected_sha or old.get("expected_sha256"),
                "downloaded_at": old.get("downloaded_at") or now_iso(),
                **meta,
            })

    # Also keep valid orphan zips, but mark them as manual.
    known = {m["attestation"] for m in merged}
    for zp in REPORTS_DIR.glob("0x*.zip"):
        h = normalize_hash(zp.stem)
        if not h or h in known:
            continue
        if is_zip_valid(zp):
            merged.append({
                "attestation": h,
                "team_name": old_by_hash.get(h, {}).get("team_name", "manual"),
                "report_url": old_by_hash.get(h, {}).get("report_url", ""),
                "expected_sha256": old_by_hash.get(h, {}).get("expected_sha256"),
                "downloaded_at": old_by_hash.get(h, {}).get("downloaded_at", now_iso()),
                **inspect_zip(zp),
            })
    return merged


async def enrich_attestations(evals: list[dict[str, Any]], browser_concurrency: int, headless: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pending = [ev for ev in evals if not ev.get("report_url")]
    if not pending:
        return evals, []

    from playwright.async_api import async_playwright

    print(f"Extracting report URLs from {len(pending)} attestation pages...")
    failures: list[dict[str, Any]] = []
    by_hash = {ev["attestation"]: ev for ev in evals}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        sem = asyncio.Semaphore(browser_concurrency)
        results = await asyncio.gather(*(extract_attestation_data(context, sem, ev) for ev in pending))
        await context.close()
        await browser.close()

    for res in results:
        h = res["attestation"]
        ev = by_hash[h]
        if res.get("report_url"):
            ev["report_url"] = res["report_url"]
            ev["sha256"] = res.get("sha256")
        else:
            failures.append({
                "attestation": h,
                "team_name": ev.get("team_name", "unknown"),
                "error": res.get("error") or "report URL not found",
                "time": now_iso(),
            })

    found = sum(1 for ev in evals if ev.get("report_url"))
    print(f"  Got {found}/{len(evals)} report URLs")
    return list(by_hash.values()), failures


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notion-url", default=os.environ.get("NOTION_URL", DEFAULT_NOTION_URL))
    parser.add_argument("--refresh-notion", action="store_true", help="crawl Notion and overwrite data/evaluations.json")
    parser.add_argument("--expect-count", type=int, default=None, help="warn until at least this many Notion evaluations are found")
    parser.add_argument("--headful", action="store_true", help="run browser with UI for debugging")
    parser.add_argument("--browser-concurrency", type=int, default=DEFAULT_BROWSER_CONCURRENCY)
    parser.add_argument("--download-concurrency", type=int, default=DEFAULT_DOWNLOAD_CONCURRENCY)
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    headless = not args.headful

    if args.refresh_notion or not EVALS_FILE.exists():
        eval_objs = await collect_evaluations_from_notion(
            args.notion_url,
            expect_count=args.expect_count,
            headless=headless,
        )
        evals = [e.to_json() for e in eval_objs]
        if evals or not EVALS_FILE.exists():
            write_json(EVALS_FILE, evals)
            print(f"Saved {len(evals)} evaluations to {EVALS_FILE}")
        else:
            evals = read_evaluations()
            print(f"Notion returned 0 — keeping existing {len(evals)} evaluations")
    else:
        evals = read_evaluations()
        print(f"Loaded {len(evals)} evaluations from {EVALS_FILE}")

    # Attach cached report_url/sha256 from previous metadata when evaluations.json lacks them.
    old_meta = load_json(META_FILE, [])
    old_by_hash = {m.get("attestation"): m for m in old_meta if m.get("attestation")}
    for ev in evals:
        old = old_by_hash.get(ev["attestation"], {})
        ev.setdefault("report_url", old.get("report_url"))
        ev.setdefault("sha256", old.get("expected_sha256") or old.get("sha256"))

    evals, url_failures = await enrich_attestations(evals, args.browser_concurrency, headless=headless)
    reports = merge_report_entries(load_report_entries(), evals)
    write_report_entries(reports)
    write_json(EVALS_FILE, reports)
    print(f"Saved {len(reports)} report entries to {REPORTS_FILE}")

    if args.no_download:
        write_json(FAILURES_FILE, url_failures)
        return

    cached = merge_cached_metadata(reports)
    cached_hashes = {m["attestation"] for m in cached}
    print(f"  {len(cached_hashes)} valid cached ZIPs")

    to_download = [ev for ev in reports if ev.get("report_url") and ev["attestation"] not in cached_hashes]
    print(f"Downloading {len(to_download)} missing report ZIPs...")
    downloaded_meta, download_failures = await download_and_verify_all(to_download, args.download_concurrency)

    meta_by_hash = {m["attestation"]: m for m in cached}
    for m in downloaded_meta:
        meta_by_hash[m["attestation"]] = m

    metadata = sorted(meta_by_hash.values(), key=lambda m: (m.get("team_name", "").lower(), m["attestation"]))
    failures = url_failures + download_failures
    write_json(META_FILE, metadata)
    write_json(FAILURES_FILE, failures)

    valid = sum(1 for m in metadata if m.get("has_manifest"))
    verified = sum(
        1 for m in metadata
        if m.get("expected_sha256") and m.get("sha256", "").lower() == m.get("expected_sha256", "").lower()
    )
    total_mb = sum(m.get("zip_size", 0) for m in metadata) / 1024 / 1024
    print("\n" + "=" * 50)
    print(f"Evaluations: {len(evals)}")
    print(f"Reports:     {len(metadata)} cached/downloaded ({valid} valid, {verified} SHA-256 verified)")
    print(f"Size:        {total_mb:.0f} MB")
    print(f"Failures:    {len(failures)} -> {FAILURES_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
