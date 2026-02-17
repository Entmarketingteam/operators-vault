"""
End-to-end verification script for Operators Vault.
Tests: Database, Deepgram, Anthropic, YouTube API, Supabase Auth, Frontend-Backend connection.
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


def test_database():
    """Test Supabase database connection."""
    print("\n1. Testing Database Connection...")
    try:
        import psycopg2
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("   [ERROR] DATABASE_URL not set")
            return False
        
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM videos")
        video_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM transcriptions")
        trans_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM insights")
        insight_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print(f"   [OK] Database connected")
        print(f"        Videos: {video_count}")
        print(f"        Transcriptions: {trans_count}")
        print(f"        Insights: {insight_count}")
        return True
    except Exception as e:
        print(f"   [ERROR] Database connection failed: {e}")
        return False


def test_deepgram():
    """Test Deepgram API."""
    print("\n2. Testing Deepgram API...")
    try:
        from deepgram import DeepgramClient, PrerecordedOptions
        
        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            print("   [ERROR] DEEPGRAM_API_KEY not set")
            return False
        
        # Test client creation
        client = DeepgramClient(api_key)
        print("   [OK] DeepgramClient created successfully")
        
        # Test PrerecordedOptions
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            punctuate=True,
            utterances=True,
            diarize=True,
        )
        print("   [OK] PrerecordedOptions created successfully")
        print(f"        Model: {options.model}")
        return True
    except ImportError as e:
        print(f"   [ERROR] Deepgram SDK not installed: {e}")
        print("        Run: pip install deepgram-sdk>=5.0.0")
        return False
    except Exception as e:
        print(f"   [ERROR] Deepgram setup failed: {e}")
        return False


def test_anthropic():
    """Test Anthropic API."""
    print("\n3. Testing Anthropic API...")
    try:
        import anthropic
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("   [ERROR] ANTHROPIC_API_KEY not set")
            return False
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Test a simple API call
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'OK'"}],
        )
        
        if response.content and len(response.content) > 0:
            text = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])
            print(f"   [OK] Anthropic API working")
            print(f"        Response: {text[:50]}")
            return True
        else:
            print("   [ERROR] Empty response from Anthropic")
            return False
    except ImportError:
        print("   [ERROR] Anthropic SDK not installed")
        print("        Run: pip install anthropic>=0.18.0")
        return False
    except Exception as e:
        print(f"   [ERROR] Anthropic API test failed: {e}")
        # Check if it's a model name issue
        if "model" in str(e).lower():
            print("        Note: Model name might be incorrect. Check Anthropic docs for latest model names.")
        return False


def test_youtube_api():
    """Test YouTube API."""
    print("\n4. Testing YouTube API...")
    try:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            print("   [WARN] YOUTUBE_API_KEY not set (optional for processing)")
            return True  # Not required for processing
        
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=api_key)
        
        # Test API with a simple request
        request = youtube.channels().list(part="snippet", forUsername="Operators9")
        response = request.execute()
        
        if response.get("items"):
            print("   [OK] YouTube API working")
            return True
        else:
            print("   [WARN] YouTube API connected but no results (might be rate limited)")
            return True
    except ImportError:
        print("   [WARN] google-api-python-client not installed (optional)")
        return True
    except Exception as e:
        print(f"   [WARN] YouTube API test failed: {e} (optional for processing)")
        return True  # Not critical


def test_supabase_auth():
    """Test Supabase Auth configuration."""
    print("\n5. Testing Supabase Auth Configuration...")
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
        supabase_jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")
        
        if not supabase_url:
            print("   [WARN] SUPABASE_URL not set (needed for frontend)")
        else:
            print(f"   [OK] SUPABASE_URL set: {supabase_url[:30]}...")
        
        if not supabase_anon_key:
            print("   [WARN] SUPABASE_ANON_KEY not set (needed for frontend auth)")
        else:
            print(f"   [OK] SUPABASE_ANON_KEY set")
        
        if not supabase_jwt_secret:
            print("   [WARN] SUPABASE_JWT_SECRET not set (needed for /search endpoint)")
        else:
            print(f"   [OK] SUPABASE_JWT_SECRET set")
        
        return True
    except Exception as e:
        print(f"   [ERROR] Supabase Auth test failed: {e}")
        return False


def test_railway_api():
    """Test Railway API endpoints."""
    print("\n6. Testing Railway API Endpoints...")
    try:
        import httpx
        
        # Test health endpoint
        r = httpx.get(f"{RAILWAY_APP_URL}/health", timeout=10.0, verify=False)
        if r.status_code == 200:
            data = r.json()
            print(f"   [OK] Health endpoint working")
            checks = data.get("checks", {})
            for check, status in checks.items():
                if status == "ok":
                    print(f"        {check}: OK")
                else:
                    print(f"        {check}: {status}")
            
            # Test config endpoint
            r2 = httpx.get(f"{RAILWAY_APP_URL}/config", timeout=10.0, verify=False)
            if r2.status_code == 200:
                config = r2.json()
                print(f"   [OK] Config endpoint working")
                print(f"        API Base: {config.get('apiBase', 'N/A')}")
                print(f"        Supabase URL: {config.get('supabaseUrl', 'N/A')[:30]}...")
            else:
                print(f"   [WARN] Config endpoint returned {r2.status_code}")
            
            return True
        else:
            print(f"   [ERROR] Health endpoint returned {r.status_code}")
            return False
    except ImportError:
        print("   [ERROR] httpx not installed: pip install httpx")
        return False
    except Exception as e:
        print(f"   [ERROR] Railway API test failed: {e}")
        return False


def test_processing_pipeline():
    """Test that processing pipeline components are importable."""
    print("\n7. Testing Processing Pipeline Components...")
    try:
        from audio_extractor import download_audio
        from deepgram_client import transcribe, get_raw_text, get_utterances
        from insight_extractor import extract_insights, generate_title, extract_timestamps
        from pipeline import _process_one
        
        print("   [OK] All pipeline components importable")
        print("        - audio_extractor")
        print("        - deepgram_client")
        print("        - insight_extractor")
        print("        - pipeline")
        return True
    except ImportError as e:
        print(f"   [ERROR] Pipeline component import failed: {e}")
        return False
    except Exception as e:
        print(f"   [ERROR] Pipeline test failed: {e}")
        return False


def main():
    print("="*70)
    print("OPERATORS VAULT - END-TO-END VERIFICATION")
    print("="*70)
    
    results = []
    
    # Run all tests
    results.append(("Database", test_database()))
    results.append(("Deepgram", test_deepgram()))
    results.append(("Anthropic", test_anthropic()))
    results.append(("YouTube API", test_youtube_api()))
    results.append(("Supabase Auth", test_supabase_auth()))
    results.append(("Railway API", test_railway_api()))
    results.append(("Processing Pipeline", test_processing_pipeline()))
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[SUCCESS] All systems operational!")
        print("\nNext steps:")
        print("1. Trigger sync: POST /sync/async or GET /trigger-sync")
        print("2. Check job status: GET /jobs/{job_id}")
        print("3. Process 36 videos: The sync will automatically process unprocessed videos")
        return 0
    else:
        print("\n[WARNING] Some checks failed. Fix the issues above before processing videos.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
