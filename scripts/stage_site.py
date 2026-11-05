"""Assemble the folder that GitHub Pages serves (P7). The deploy workflow and local testing use it alike.

    python scripts/stage_site.py _site [--last-scan-ran ISO_TIME]

It copies site/ and the three public data files, writes site_config.json and companies.json, and stamps the service
worker with a hash of the app's files. The stamp changes the cache name whenever the app changes,
so visitors get the new version and old caches are deleted. Data changes don't change the stamp:
data is fetched network-first and never needs a new app version.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_companies  # noqa: E402
import build_site_config  # noqa: E402

DATA_FILES = ["internships.json", "meta.json", "companies_status.json"]
STAMP = "__BUILD_STAMP__"


def stage(out: Path, last_scan_ran=None) -> str:
    site = ROOT / "site"
    if out.resolve() in (ROOT.resolve(), site.resolve()):
        raise SystemExit("refusing to stage into the repo root or site/")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(site, out, ignore=shutil.ignore_patterns(".DS_Store"))

    digest = hashlib.sha256()
    for path in sorted(p for p in site.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        digest.update(path.relative_to(site).as_posix().encode())
        digest.update(path.read_bytes())
    stamp = digest.hexdigest()[:12]
    worker = out / "service-worker.js"
    text = worker.read_text(encoding="utf-8")
    if STAMP not in text:
        raise SystemExit(f"{worker} has no {STAMP} placeholder")
    worker.write_text(text.replace(STAMP, stamp), encoding="utf-8")

    (out / "data").mkdir()
    for name in DATA_FILES:
        shutil.copy2(ROOT / "data" / name, out / "data" / name)
    extra = ["--last-scan-ran", last_scan_ran] if last_scan_ran else []
    if build_site_config.main([str(out / "site_config.json"), *extra]) != 0:
        raise SystemExit("site_config.json could not be written")
    # P8: public company fields (tags, priority, cities, manual link) that companies_status.json lacks.
    if build_companies.main([str(out / "companies.json")]) != 0:
        raise SystemExit("companies.json could not be written")
    return stamp


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    last_scan_ran = None
    if "--last-scan-ran" in argv:
        i = argv.index("--last-scan-ran")
        # An empty value (the lookup failed) is the same as leaving it out.
        last_scan_ran = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i:i + 2]
    if len(argv) != 1:
        print("usage: python scripts/stage_site.py OUT_DIR [--last-scan-ran ISO_TIME]", file=sys.stderr)
        return 2
    stamp = stage(Path(argv[0]), last_scan_ran or None)
    print(f"staged {argv[0]} (app version {stamp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
