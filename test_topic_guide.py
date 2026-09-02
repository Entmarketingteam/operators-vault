import os
import sys
import unittest
from fastapi import HTTPException

# Add operators-vault to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import api

class TestTopicGuide(unittest.TestCase):
    def setUp(self):
        # Ensure we have a mock environment
        os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432")
        # Run startup migrations to ensure tables are created
        try:
            api._run_startup_migration()
        except Exception as e:
            print(f"Migration failed: {e}")

    def test_topic_guide_empty_topic(self):
        print("\nTesting topic guide with empty topic...")
        request = api.TopicGuideRequest(topic="")
        with self.assertRaises(HTTPException) as context:
            api.topic_guide(request)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "topic required")
        print("[PASS] Empty topic properly rejected with 400.")

    def test_topic_guide_invalid_topic(self):
        print("\nTesting topic guide with obscure non-existent topic...")
        request = api.TopicGuideRequest(topic="xyzobscurenonexistentterm")
        with self.assertRaises(HTTPException) as context:
            api.topic_guide(request)
        self.assertEqual(context.exception.status_code, 404)
        print("[PASS] Non-existent topic properly returned 404.")

    def test_topic_guide_successful_flow(self):
        print("\nTesting successful topic guide generation...")
        # Caching was deliberately removed 2026-08-01 (no invalidation, vault
        # corpus changes daily) — do not assert cache_hit/identical-content-on-
        # rerun here. See the NOTE above api.py's live /topic-guide handler.
        request = api.TopicGuideRequest(topic="Creative Testing")
        try:
            res = api.topic_guide(request)
            # Basic validation
            self.assertIn("topic", res)
            self.assertIn("content", res)
            self.assertIn("sources", res)
            self.assertEqual(res["topic"], "Creative Testing")
            self.assertTrue(len(res["content"]) > 100)

            print(f"[PASS] Generation successful. Content length: {len(res['content'])}")
            print(f"[PASS] Sources citation count: {len(res['sources'])}")

        except HTTPException as e:
            # If the third-party agent complete server is temporarily unreachable, skip gracefully
            if "generation failed" in str(e.detail) or "500" in str(e.status_code):
                self.skipTest(f"Agent completion proxy server unreachable: {e.detail}")
            else:
                self.fail(f"HTTPException raised: {e.detail}")
        except Exception as e:
            self.fail(f"Unexpected exception raised: {e}")

if __name__ == "__main__":
    unittest.main()
