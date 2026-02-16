"""
Check Railway logs using Railway CLI or provide instructions.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_via_cli():
    """Try to fetch logs using Railway CLI."""
    print("Attempting to fetch logs via Railway CLI...\n")
    
    try:
        # Check if railway CLI is installed
        result = subprocess.run(
            ["railway", "logs", "--service", "superb-smile"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            output = result.stdout
            if output:
                print("="*60)
                print("RECENT RAILWAY LOGS")
                print("="*60)
                print(output)
                
                # Filter for relevant errors
                lines = output.split("\n")
                audio_errors = [l for l in lines if "[audio]" in l.lower() and ("error" in l.lower() or "failed" in l.lower())]
                processing_errors = [l for l in lines if ("error" in l.lower() or "failed" in l.lower()) and ("process" in l.lower() or "transcribe" in l.lower())]
                
                if audio_errors:
                    print("\n" + "="*60)
                    print("AUDIO DOWNLOAD ERRORS")
                    print("="*60)
                    for err in audio_errors[-10:]:
                        print(err)
                
                if processing_errors:
                    print("\n" + "="*60)
                    print("PROCESSING ERRORS")
                    print("="*60)
                    for err in processing_errors[-10:]:
                        print(err)
                
                return True
            else:
                print("No logs returned")
        else:
            print(f"Railway CLI error: {result.stderr}")
    except FileNotFoundError:
        print("Railway CLI not found")
        return False
    except subprocess.TimeoutExpired:
        print("Railway CLI timed out")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return False


def main():
    print("="*60)
    print("CHECKING RAILWAY LOGS")
    print("="*60)
    print()
    
    # Try CLI first
    if check_via_cli():
        print("\n" + "="*60)
        print("LOG CHECK COMPLETE")
        print("="*60)
        return 0
    
    # If CLI doesn't work, provide instructions
    print("\n" + "="*60)
    print("MANUAL LOG CHECK INSTRUCTIONS")
    print("="*60)
    print("\nOption 1: Railway Dashboard (Easiest)")
    print("1. Go to: https://railway.app")
    print("2. Navigate to your project")
    print("3. Click on 'superb-smile' service")
    print("4. Click on 'Logs' tab")
    print("5. Look for recent entries containing:")
    print("   - [audio] ERROR:")
    print("   - [audio] download failed:")
    print("   - yt-dlp output:")
    print("   - [transcribe]")
    print("   - [insights]")
    
    print("\nOption 2: Install Railway CLI")
    print("1. Install: npm install -g @railway/cli")
    print("2. Login: railway login")
    print("3. Link: railway link")
    print("4. View logs: railway logs --service superb-smile")
    
    print("\nOption 3: Check Recent Job Results")
    print("Recent job IDs from our tests:")
    print("  - 811b31cd-2af6-4d2a-ae03-44941a4d7bc2")
    print("  - 9995ce80-c8db-4929-b654-0a3121763536")
    print("\nCheck job status:")
    print("  python scripts/trigger_process_new_test.py")
    print("  (This will show the job result with any errors)")
    
    print("\n" + "="*60)
    print("WHAT TO LOOK FOR IN LOGS")
    print("="*60)
    print("\nIf YouTube is blocking Railway IPs, you'll see:")
    print("  [audio] ERROR: exit 1: HTTP 403 Forbidden")
    print("  [audio] ERROR: exit 1: HTTP 429 Too Many Requests")
    print("  [audio] ERROR: exit 1: Video unavailable")
    print("\nIf ffmpeg is missing:")
    print("  [audio] ERROR: yt-dlp or ffmpeg not found")
    print("\nIf yt-dlp succeeds but no file:")
    print("  [audio] ERROR: no output file written after yt-dlp succeeded")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
