"""
Test audio download directly to see the actual error.
This will help diagnose why Railway processing is failing.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# Test with a known video ID
TEST_VIDEO_ID = "TzyOKA6EhqI"  # From the logs


def main():
    print("="*60)
    print("TESTING AUDIO DOWNLOAD DIRECTLY")
    print("="*60)
    print(f"\nVideo ID: {TEST_VIDEO_ID}")
    print(f"URL: https://www.youtube.com/watch?v={TEST_VIDEO_ID}\n")
    
    # Check yt-dlp
    print("1. Checking yt-dlp...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"   [OK] yt-dlp version: {result.stdout.strip()}")
        else:
            print(f"   [ERROR] yt-dlp check failed: {result.stderr}")
            return 1
    except Exception as e:
        print(f"   [ERROR] {e}")
        return 1
    
    # Try download
    print("\n2. Attempting download...")
    work_dir = Path(tempfile.mkdtemp())
    url = f"https://www.youtube.com/watch?v={TEST_VIDEO_ID}"
    out_tpl = str(work_dir / f"{TEST_VIDEO_ID}.audio.%(ext)s")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "--extract-audio",
        "--audio-format", "m4a",
        "-o", out_tpl,
        "--no-playlist",
        "--no-warnings",
        url,
    ]
    
    print(f"   Command: {' '.join(cmd[:5])} ... {url}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        print(f"\n   Exit code: {result.returncode}")
        
        if result.stdout:
            print(f"\n   STDOUT:")
            print(result.stdout[:500])
        
        if result.stderr:
            print(f"\n   STDERR:")
            print(result.stderr[:500])
        
        if result.returncode == 0:
            # Check for file
            found = False
            for ext in (".webm", ".m4a", ".mp3"):
                p = work_dir / f"{TEST_VIDEO_ID}.audio{ext}"
                if p.exists():
                    size_mb = p.stat().st_size / (1024 * 1024)
                    print(f"\n   [SUCCESS] File created: {p.name} ({size_mb:.2f} MB)")
                    found = True
                    # Cleanup
                    p.unlink()
                    break
            
            if not found:
                print(f"\n   [ERROR] yt-dlp succeeded but no file created")
        else:
            print(f"\n   [ERROR] Download failed")
            # Check for common errors
            combined = (result.stderr or "") + (result.stdout or "")
            if "403" in combined or "Forbidden" in combined:
                print(f"\n   [DIAGNOSIS] YouTube blocking detected (HTTP 403)")
            elif "429" in combined or "rate limit" in combined.lower():
                print(f"\n   [DIAGNOSIS] YouTube rate limiting (HTTP 429)")
            elif "ffmpeg" in combined.lower() and "not found" in combined.lower():
                print(f"\n   [DIAGNOSIS] ffmpeg missing")
            elif "unavailable" in combined.lower():
                print(f"\n   [DIAGNOSIS] Video unavailable")
        
        # Cleanup
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
        
        return 0 if result.returncode == 0 else 1
        
    except subprocess.TimeoutExpired:
        print(f"\n   [ERROR] Download timed out")
        return 1
    except Exception as e:
        print(f"\n   [ERROR] Exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
