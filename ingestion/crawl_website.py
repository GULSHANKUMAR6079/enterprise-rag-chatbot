"""
CLI Tool: Recursive Website Crawler & Incremental Knowledge Updater.
Usage:
    python ingestion/crawl_website.py https://mycompany.com
    python ingestion/crawl_website.py https://mycompany.com --max-pages 25
    python ingestion/crawl_website.py https://mycompany.com/pricing --single-page
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.app.rag.website_crawler import website_crawler


async def main():
    parser = argparse.ArgumentParser(
        description="Recursively crawl and index your company website into the local chatbot."
    )
    parser.add_argument(
        "url",
        help="Target company website root URL (e.g., https://mycompany.com)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum number of internal pages to discover and crawl (default: 50)"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum link traversal depth (default: 3)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-indexing even if page content is unchanged"
    )
    parser.add_argument(
        "--single-page",
        action="store_true",
        help="Crawl only the specific URL without discovering other pages"
    )

    args = parser.parse_args()

    website_crawler.max_pages = 1 if args.single_page else args.max_pages
    website_crawler.max_depth = 0 if args.single_page else args.max_depth

    print("\n" + "=" * 60)
    print("[WEB] INCERRO COMPANY WEBSITE CRAWLER & SMART SYNC")
    print("=" * 60)
    print(f"Target URL:        {args.url}")
    print(f"Max Pages Limit:   {website_crawler.max_pages}")
    print(f"Traverse Depth:    {website_crawler.max_depth}")
    print(f"Force Re-index:    {args.force}")
    print("=" * 60 + "\n")
    print("[*] Starting crawl and incremental change detection...\n")

    report = await website_crawler.crawl_and_sync(
        root_url=args.url,
        force_reindex=args.force
    )

    print("\n" + "=" * 60)
    print("[REPORT] CRAWL & SYNCHRONIZATION REPORT")
    print("=" * 60)
    print(f"Total Pages Scanned:           {report['total_pages_scanned']}")
    print(f"New Pages Ingested:            {report['new_pages_ingested']}")
    print(f"Pages Updated (Changed):       {report['pages_updated']}")
    print(f"Pages Unchanged (Skipped):     {report['pages_unchanged']}")
    print(f"Total Chunks Active in RAG:    {report['total_chunks_indexed']}")
    print(f"Quarantined Injections:        {report['quarantined_instructions']}")
    print("=" * 60)

    print("\nPage Details:")
    for p in report["scanned_pages"]:
        status_icon = "[NEW]" if p["status"] == "new" else ("[UPDATED]" if p["status"] == "updated" else "[UNCHANGED]")
        print(f"  {status_icon} {p['title']}")
        print(f"         URL: {p['url']}")

    print("\n[OK] Website synchronization complete! Chatbot is ready to answer questions.\n")


if __name__ == "__main__":
    asyncio.run(main())
