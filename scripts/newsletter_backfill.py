"""
Backfill script to process newsletters that are currently marked processed=False.
Uses the patched newsletter_ingestor logic to ensure clean DTC insight extraction.
"""
import os
from dotenv import load_dotenv
from supabase_utils import query_supabase
from newsletter_ingestor import ingest_email
from structured_logger import get_logger

_log = get_logger("newsletter_backfill")

def run_newsletter_backfill(limit: int = 100):
    load_dotenv()
    
    # 1. Fetch newsletters waiting for processing
    # Filter for processed=false
    pending = query_supabase("newsletters", {"processed": "eq.false", "limit": limit})
    
    if not pending:
        _log.info("No pending newsletters found.")
        return

    _log.info(f"Starting backfill for {len(pending)} newsletters...")
    
    success_count = 0
    for i, nl in enumerate(pending):
        try:
            _log.info(f"[{i+1}/{len(pending)}] Processing: {nl.get('subject')} (Source: {nl.get('source')})")
            
            # Re-ingest (the patched store_newsletter_insights will handle the DELETE/INSERT)
            res = ingest_email(
                email_id=nl['email_id'],
                source=nl['source'],
                author=nl.get('author', ''),
                subject=nl.get('subject', ''),
                published_at=nl.get('published_at'),
                body_text=nl.get('body_text', '')
            )
            
            if res.get('status') == 'processed':
                success_count += 1
                _log.info(f"  - Extracted {res.get('insights_count')} insights.")
            else:
                _log.warning(f"  - Status: {res.get('status')} Reason: {res.get('reason', 'N/A')}")
                
        except Exception as e:
            _log.error(f"  - Failed to process newsletter {nl.get('id')}: {e}")

    _log.info(f"Backfill complete. Successfully processed {success_count} newsletters.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    
    run_newsletter_backfill(limit=args.limit)
