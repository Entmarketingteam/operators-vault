"""
Comprehensive diagnostic script to identify all issues with video processing.
Tests: cron service, audio downloads, Railway connectivity, and provides solutions.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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
CRON_SERVICE_ID = "77f276eb-0792-42bf-80fc-a536e0b1a2a6"


def test_cron_service():
    """Test cron service configuration."""
    print("\n" + "="*60)
    print("1. TESTING CRON SERVICE CONFIGURATION")
    print("="*60)
    
    try:
        import httpx
        token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
        if not token:
            print("  [SKIP] RAILWAY_API_TOKEN not set - cannot check cron service")
            return
        
        # Load Railway IDs
        cfg = Path.home() / ".railway" / "config.json"
        if not cfg.exists():
            print("  [SKIP] Railway config not found - run 'railway link' first")
            return
        
        data = json.loads(cfg.read_text(encoding="utf-8"))
        projs = data.get("projects") or {}
        project_id = None
        environment_id = None
        for k, v in projs.items():
            if "operators-vault" in k.replace("\\", "/") or "operators-vault" in str(k):
                project_id = v["project"]
                environment_id = v["environment"]
                break
        
        if not project_id:
            print("  [SKIP] Could not find project ID")
            return
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Check cron service - use variables query instead
        r = httpx.post(
            "https://backboard.railway.com/graphql/v2",
            json={
                "query": """
                query variables($projectId: String!, $environmentId: String!, $serviceId: String!) {
                  variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId)
                }
                """,
                "variables": {
                    "projectId": project_id,
                    "environmentId": environment_id,
                    "serviceId": CRON_SERVICE_ID,
                },
            },
            headers=headers,
            timeout=30.0,
        )
        
        if r.status_code == 200:
            out = r.json()
            if not out.get("errors"):
                service = out.get("data", {}).get("service", {})
                vars_list = service.get("variables", [])
                trigger_url = None
                for var in vars_list:
                    if var.get("name") == "TRIGGER_URL":
                        trigger_url = var.get("value")
                        break
                
                print(f"  [OK] Cron service found: {service.get('name')}")
                if trigger_url:
                    print(f"  [OK] TRIGGER_URL: {trigger_url}")
                    # Validate URL
                    if not trigger_url.startswith(("http://", "https://")):
                        print(f"  [ERROR] TRIGGER_URL is malformed - must start with http:// or https://")
                        print(f"          Current value: {trigger_url}")
                    else:
                        print(f"  [OK] TRIGGER_URL format is valid")
                else:
                    print(f"  [ERROR] TRIGGER_URL not set in cron service!")
            else:
                print(f"  [ERROR] GraphQL errors: {out['errors']}")
        else:
            print(f"  [ERROR] HTTP {r.status_code}: {r.text}")
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")


def test_audio_download():
    """Test audio download locally."""
    print("\n" + "="*60)
    print("2. TESTING AUDIO DOWNLOAD (LOCAL)")
    print("="*60)
    
    # Test video ID (use a known working video)
    test_video_id = "jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video, should always work
    
    print(f"  Testing with video ID: {test_video_id}")
    print(f"  URL: https://www.youtube.com/watch?v={test_video_id}")
    
    # Check if yt-dlp is installed
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  [OK] yt-dlp installed: {version}")
        else:
            print(f"  [ERROR] yt-dlp not working: {result.stderr}")
            return
    except FileNotFoundError:
        print(f"  [ERROR] yt-dlp not found in PATH")
        print(f"          Install with: pip install yt-dlp")
        return
    except Exception as e:
        print(f"  [ERROR] Could not check yt-dlp: {e}")
        return
    
    # Check if ffmpeg is installed
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"  [OK] ffmpeg installed: {version_line[:50]}...")
        else:
            print(f"  [WARN] ffmpeg check failed (may still work)")
    except FileNotFoundError:
        print(f"  [WARN] ffmpeg not found - may cause issues with audio extraction")
        print(f"          Install ffmpeg for your system")
    except Exception as e:
        print(f"  [WARN] Could not check ffmpeg: {e}")
    
    # Try actual download
    print(f"\n  Attempting download...")
    work_dir = Path(tempfile.mkdtemp())
    url = f"https://www.youtube.com/watch?v={test_video_id}"
    out_tpl = str(work_dir / f"{test_video_id}.audio.%(ext)s")
    
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "--extract-audio",
        "--audio-format", "webm",
        "-o", out_tpl,
        "--no-playlist",
        "--no-warnings",
        url,
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode == 0:
            # Check if file was created
            found_file = None
            for ext in (".webm", ".m4a", ".mp3"):
                p = work_dir / f"{test_video_id}.audio{ext}"
                if p.exists():
                    found_file = p
                    size_mb = p.stat().st_size / (1024 * 1024)
                    print(f"  [OK] Download successful!")
                    print(f"       File: {found_file.name}")
                    print(f"       Size: {size_mb:.2f} MB")
                    # Cleanup
                    found_file.unlink()
                    break
            
            if not found_file:
                print(f"  [ERROR] yt-dlp succeeded but no file created")
                print(f"          stdout: {result.stdout[:200]}")
        else:
            print(f"  [ERROR] Download failed!")
            print(f"          Exit code: {result.returncode}")
            if result.stderr:
                error_lines = [l.strip() for l in result.stderr.split("\n") if l.strip()][:5]
                print(f"          Error: {error_lines[0] if error_lines else 'No error message'}")
                for line in error_lines[1:]:
                    print(f"                 {line}")
            if result.stdout:
                stdout_lines = [l.strip() for l in result.stdout.split("\n") if l.strip()][:5]
                if stdout_lines:
                    print(f"          Output: {stdout_lines[0]}")
            
            # Check for common errors
            combined = (result.stderr or "") + (result.stdout or "")
            if "HTTP 403" in combined or "Forbidden" in combined:
                print(f"\n  [DIAGNOSIS] YouTube is blocking the request (HTTP 403)")
                print(f"             This is likely IP-based blocking (common with cloud providers)")
            elif "HTTP 429" in combined or "rate limit" in combined.lower():
                print(f"\n  [DIAGNOSIS] YouTube rate limiting detected")
            elif "unavailable" in combined.lower():
                print(f"\n  [DIAGNOSIS] Video unavailable (may be region-locked or deleted)")
            elif "ffmpeg" in combined.lower() and "not found" in combined.lower():
                print(f"\n  [DIAGNOSIS] ffmpeg is missing - required for audio extraction")
                
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] Download timed out after 60 seconds")
    except Exception as e:
        print(f"  [ERROR] Exception during download: {e}")
    finally:
        # Cleanup
        try:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
        except:
            pass


def test_railway_endpoint():
    """Test Railway endpoint connectivity."""
    print("\n" + "="*60)
    print("3. TESTING RAILWAY ENDPOINT")
    print("="*60)
    
    try:
        import httpx
        
        # Test health endpoint
        print(f"  Testing health endpoint: {RAILWAY_APP_URL}/health")
        r = httpx.get(f"{RAILWAY_APP_URL}/health", timeout=10.0, verify=False)
        if r.status_code == 200:
            data = r.json()
            print(f"  [OK] Health check passed")
            checks = data.get("checks", {})
            for check, status in checks.items():
                status_icon = "[OK]" if status == "ok" else "[WARN]"
                print(f"         {status_icon} {check}: {status}")
        else:
            print(f"  [ERROR] Health check failed: HTTP {r.status_code}")
        
        # Test sync endpoint
        print(f"\n  Testing sync endpoint: {RAILWAY_APP_URL}/sync/async")
        r = httpx.post(f"{RAILWAY_APP_URL}/sync/async", timeout=10.0, verify=False)
        if r.status_code == 202:
            data = r.json()
            job_id = data.get("job_id")
            print(f"  [OK] Sync endpoint working")
            print(f"       Job ID: {job_id}")
        elif r.status_code == 404:
            print(f"  [ERROR] Sync endpoint not found (404)")
            print(f"          The service may not be deployed or route is wrong")
        else:
            print(f"  [ERROR] Sync endpoint returned: HTTP {r.status_code}")
            print(f"          Response: {r.text[:200]}")
            
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")


def provide_solutions():
    """Provide solutions based on findings."""
    print("\n" + "="*60)
    print("4. RECOMMENDED SOLUTIONS")
    print("="*60)
    
    print("\n  If YouTube is blocking Railway IPs:")
    print("  -> Process videos locally:")
    print("    1. Set DATABASE_URL in .env to your Supabase connection string")
    print("    2. Run: python pipeline.py --process-new")
    print("    3. Keep sync job on Railway to fetch new videos automatically")
    
    print("\n  If cron service is failing:")
    print("  -> Fix TRIGGER_URL:")
    print("    1. Go to Railway Dashboard -> vault-sync-cron -> Variables")
    print("    2. Set TRIGGER_URL to: https://superb-smile-production.up.railway.app/sync/async")
    print("    3. Or use: python scripts/update_railway_cron_service.py")
    
    print("\n  Alternative: Use Railway's built-in cron")
    print("  -> Railway Dashboard -> New -> Cron Job")
    print("    Schedule: 0 */3 * * *")
    print("    Command: curl -X POST https://superb-smile-production.up.railway.app/sync/async")


def main():
    print("\n" + "="*60)
    print("OPERATORS VAULT - COMPREHENSIVE DIAGNOSTICS")
    print("="*60)
    
    test_cron_service()
    test_audio_download()
    test_railway_endpoint()
    provide_solutions()
    
    print("\n" + "="*60)
    print("DIAGNOSTICS COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
