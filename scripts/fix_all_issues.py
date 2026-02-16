"""
Fix all identified issues:
1. Update cron service TRIGGER_URL to use POST /sync/async
2. Provide code for local processing if Railway fails
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_env = ROOT / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_env)
except ImportError:
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip():
                    os.environ.setdefault(k.strip(), v.strip())

RAILWAY_APP_URL = os.environ.get("RAILWAY_APP_URL", "https://superb-smile-production.up.railway.app").rstrip("/")


def fix_cron_service():
    """Fix cron service TRIGGER_URL."""
    print("Fixing cron service TRIGGER_URL...")
    
    # Use POST /sync/async instead of GET /trigger-sync (more reliable)
    trigger_url = f"{RAILWAY_APP_URL}/sync/async"
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/update_railway_cron_service.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("  [OK] Cron service updated")
            print(f"       TRIGGER_URL set to: {trigger_url}")
        else:
            print("  [ERROR] Failed to update cron service")
            print(f"          {result.stderr}")
            print("\n  Manual fix:")
            print(f"  1. Railway Dashboard -> vault-sync-cron -> Variables")
            print(f"  2. Set TRIGGER_URL = {trigger_url}")
            print(f"  3. Update start command to: curl -X POST \"$TRIGGER_URL\"")
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")


def create_local_processor():
    """Create a local processing script."""
    script_content = '''"""
Local video processor - run this on your machine to process videos.
This bypasses YouTube IP blocking issues on Railway.

Usage:
    python local_process_videos.py

Requirements:
    - DATABASE_URL in .env (pointing to your Supabase database)
    - DEEPGRAM_API_KEY in .env
    - ANTHROPIC_API_KEY in .env
    - yt-dlp installed: pip install yt-dlp
    - ffmpeg installed (for audio extraction)
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load environment
_env = ROOT / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_env)
except ImportError:
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip():
                    os.environ.setdefault(k.strip(), v.strip())

if __name__ == "__main__":
    from pipeline import main
    sys.exit(main())
'''
    
    script_path = ROOT / "local_process_videos.py"
    script_path.write_text(script_content)
    print(f"\nCreated local processor: {script_path}")
    print("\nTo process videos locally:")
    print("  1. Ensure DATABASE_URL, DEEPGRAM_API_KEY, ANTHROPIC_API_KEY are in .env")
    print("  2. Install dependencies: pip install yt-dlp")
    print("  3. Install ffmpeg (system dependency)")
    print("  4. Run: python local_process_videos.py --process-new")


def main():
    print("="*60)
    print("FIXING ALL IDENTIFIED ISSUES")
    print("="*60)
    
    fix_cron_service()
    create_local_processor()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("\n1. Cron Service:")
    print("   - TRIGGER_URL should now point to POST /sync/async")
    print("   - If still failing, check Railway Dashboard -> vault-sync-cron -> Logs")
    
    print("\n2. Video Processing:")
    print("   - If Railway processing fails (YouTube blocking), use local processor")
    print("   - Run: python local_process_videos.py --process-new")
    print("   - This uses your local IP instead of Railway's cloud IP")
    
    print("\n3. Next Steps:")
    print("   - Wait for cron to run (every 3 hours) or trigger manually")
    print("   - Check Railway logs for detailed error messages")
    print("   - If all videos fail, process locally as workaround")


if __name__ == "__main__":
    main()
