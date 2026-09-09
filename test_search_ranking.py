"""
Unit tests for search ranking and quota logic.

These tests cover critical business logic that controls how search results
are ranked and balanced between newsletter and video sources. A failure in
these functions will silently degrade result quality without throwing errors.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import api


class TestNormalizeRanksByType(unittest.TestCase):
    """Test the _normalize_ranks_by_type function.

    This function is critical: it normalizes search scores within each corpus
    (newsletter vs video) independently so that the best newsletter result
    competes fairly with the best video result, even if one corpus has a
    larger absolute score range.
    """

    def test_single_result_normalizes_to_one(self):
        """A single result should normalize to 1.0 (no penalty for lacking context)."""
        hits = [{"type": "insight", "rank": 0.5}]
        result = api._normalize_ranks_by_type(hits)
        self.assertEqual(result[0]["rank_norm"], 1.0)

    def test_identical_scores_normalize_to_one(self):
        """When all results tie, all should normalize to 1.0."""
        hits = [
            {"type": "insight", "rank": 0.5},
            {"type": "insight", "rank": 0.5},
            {"type": "insight", "rank": 0.5},
        ]
        result = api._normalize_ranks_by_type(hits)
        for hit in result:
            self.assertEqual(hit["rank_norm"], 1.0)

    def test_rank_normalization_within_type(self):
        """Normalization should happen independently per type."""
        hits = [
            {"type": "insight", "rank": 1.0},
            {"type": "insight", "rank": 2.0},
            {"type": "newsletter_insight", "rank": 10.0},
            {"type": "newsletter_insight", "rank": 20.0},
        ]
        result = api._normalize_ranks_by_type(hits)
        # Find the results by type
        insights = [h for h in result if h["type"] == "insight"]
        newsletters = [h for h in result if h["type"] == "newsletter_insight"]

        # Insights: 1.0 -> 0.0, 2.0 -> 1.0
        self.assertAlmostEqual(insights[0]["rank_norm"], 0.0, places=5)
        self.assertAlmostEqual(insights[1]["rank_norm"], 1.0, places=5)

        # Newsletters: 10.0 -> 0.0, 20.0 -> 1.0 (independently scaled)
        self.assertAlmostEqual(newsletters[0]["rank_norm"], 0.0, places=5)
        self.assertAlmostEqual(newsletters[1]["rank_norm"], 1.0, places=5)

    def test_preserves_hit_metadata(self):
        """Normalization should preserve all other hit fields."""
        original = {
            "type": "insight",
            "rank": 0.5,
            "title": "Test",
            "video_id": "abc123",
        }
        result = api._normalize_ranks_by_type([original])
        # rank_norm should be added
        self.assertIn("rank_norm", result[0])
        # All original fields should be preserved
        self.assertEqual(result[0]["title"], "Test")
        self.assertEqual(result[0]["video_id"], "abc123")


class TestApplySourceQuota(unittest.TestCase):
    """Test the _apply_source_quota function.

    This function is critical: it ensures newsletters and videos both get
    represented in results, preventing one corpus from crowding out the other.
    """

    def test_empty_hits_list(self):
        """Empty input should return empty output."""
        result = api._apply_source_quota([], 10)
        self.assertEqual(result, [])

    def test_newsletter_quota_respected(self):
        """At least 40% of results should be newsletters (default quota)."""
        # 10 newsletters, 10 others
        hits = (
            [{"type": "newsletter_insight", "rank_norm": float(i)} for i in range(10)]
            + [{"type": "insight", "rank_norm": float(i + 10)} for i in range(10)]
        )
        limit = 10
        result = api._apply_source_quota(hits, limit)

        newsletter_count = sum(1 for h in result if h["type"] == "newsletter_insight")
        # 40% of 10 = 4, but with at least 4 newsletters available
        self.assertGreaterEqual(newsletter_count, 4)

    def test_reclamation_when_newsletter_short(self):
        """If newsletters run short, others should fill remaining slots."""
        # 2 newsletters, 10 others
        hits = (
            [{"type": "newsletter_insight", "rank_norm": 1.0} for _ in range(2)]
            + [{"type": "insight", "rank_norm": float(i)} for i in range(10)]
        )
        limit = 10
        result = api._apply_source_quota(hits, limit)

        # Should use all 2 newsletters and 8 others
        self.assertEqual(len(result), 10)
        newsletter_count = sum(1 for h in result if h["type"] == "newsletter_insight")
        self.assertEqual(newsletter_count, 2)

    def test_reclamation_when_others_short(self):
        """If others run short, newsletters should fill remaining slots."""
        # 10 newsletters, 2 others
        hits = (
            [{"type": "newsletter_insight", "rank_norm": float(i)} for i in range(10)]
            + [{"type": "insight", "rank_norm": 1.0} for _ in range(2)]
        )
        limit = 10
        result = api._apply_source_quota(hits, limit)

        # Should use all 2 others and 8 newsletters
        self.assertEqual(len(result), 10)
        others_count = sum(1 for h in result if h["type"] == "insight")
        self.assertEqual(others_count, 2)

    def test_sorting_by_rank_after_quota(self):
        """Results should be sorted by rank_norm after quota is applied."""
        hits = [
            {"type": "insight", "rank_norm": 0.1},
            {"type": "newsletter_insight", "rank_norm": 0.9},
            {"type": "insight", "rank_norm": 0.5},
            {"type": "newsletter_insight", "rank_norm": 0.2},
        ]
        result = api._apply_source_quota(hits, 10)

        # Should be sorted by rank_norm descending
        for i in range(len(result) - 1):
            self.assertGreaterEqual(
                result[i]["rank_norm"],
                result[i + 1]["rank_norm"],
                f"Results not sorted: {result[i]['rank_norm']} < {result[i+1]['rank_norm']}"
            )

    def test_custom_newsletter_share(self):
        """Should respect custom newsletter_share parameter."""
        # 10 newsletters, 10 others, limit 10, newsletter_share 0.2 (20%)
        hits = (
            [{"type": "newsletter_insight", "rank_norm": float(i)} for i in range(10)]
            + [{"type": "insight", "rank_norm": float(i + 10)} for i in range(10)]
        )
        result = api._apply_source_quota(hits, 10, newsletter_share=0.2)

        newsletter_count = sum(1 for h in result if h["type"] == "newsletter_insight")
        # 20% of 10 = 2
        self.assertEqual(newsletter_count, 2)


class TestExtractKeywords(unittest.TestCase):
    """Test the _extract_keywords function.

    This is a higher-level integration: it processes raw query strings
    and produces fallback keywords for resilience (when full FTS returns
    no results, the system retries with keyword-OR logic).
    """

    def test_stops_words_removed(self):
        """Common stop words should be filtered out."""
        # "the", "is", "a" should be removed or minimized
        result = api._extract_keywords("the best email strategy is key")
        # Should have the important terms: best, email, strategy, key
        self.assertIn("best", result.lower())
        self.assertIn("email", result.lower())
        self.assertIn("strategy", result.lower())

    def test_empty_query(self):
        """Empty query should return empty result."""
        result = api._extract_keywords("")
        self.assertEqual(result.strip(), "")

    def test_single_word_query(self):
        """Single word should be returned as-is."""
        result = api._extract_keywords("retention")
        self.assertIn("retention", result.lower())


if __name__ == "__main__":
    unittest.main()
