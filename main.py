#!/usr/bin/env python3
"""CLI entry point for the PH HMO PDF scraper.

Usage:
    python main.py --all                 # scrape all providers
    python main.py --provider maxicare   # scrape a single provider
    python main.py --all --dry-run       # list PDFs without downloading
"""

import argparse
import sys

from config import PROVIDERS, setup_logging
from scrapers import SCRAPER_MAP


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape PDF brochures and policy documents from Philippine HMO websites."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--provider",
        choices=sorted(SCRAPER_MAP.keys()),
        help="Scrape a single HMO provider.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Scrape all HMO providers.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover PDFs and print URLs without downloading.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging.",
    )

    args = parser.parse_args()

    import logging
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    providers = sorted(SCRAPER_MAP.keys()) if args.all else [args.provider]

    summaries = []
    for key in providers:
        scraper_cls = SCRAPER_MAP[key]
        provider_config = PROVIDERS[key]
        scraper = scraper_cls(provider_config, dry_run=args.dry_run)
        summary = scraper.run()
        summaries.append(summary)

    print("\n" + "=" * 60)
    print("SCRAPE SUMMARY")
    print("=" * 60)
    total_downloaded = 0
    total_failed = 0
    for s in summaries:
        status = "DRY RUN" if args.dry_run else "OK"
        if s["failed"] > 0:
            status = f"{s['failed']} FAILED"
        print(f"  {s['provider']:<40} {s['discovered']:>3} found | {s['downloaded']:>3} saved | {status}")
        total_downloaded += s["downloaded"]
        total_failed += s["failed"]

    print("-" * 60)
    print(f"  {'TOTAL':<40} {total_downloaded:>3} downloaded | {total_failed:>3} failed")
    print("=" * 60)

    if total_failed > 0:
        print("\nFailed URLs:")
        for s in summaries:
            for url in s["failed_urls"]:
                print(f"  - {url}")

    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
