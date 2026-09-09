import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import api


class TestNewsletterSearchNoIndexError(unittest.TestCase):
    """Regression test for a real bug (found 2026-09-08): a bare `%` inside a SQL
    comment in _do_newsletter_search's query (e.g. "~13-25% of recent CTC") broke
    psycopg2's %s-style positional parameter substitution with `IndexError: list
    index out of range`. The exception was swallowed by _search_postgres's
    try/except and only logged as `search_newsletter_failed` — newsletter search
    silently returned zero hits on every /search, /chat, and /topic-guide call for
    over a month (landed 2026-08-03) with no crash to surface it.

    psycopg2 scans the ENTIRE query string for `%`-style placeholders, including
    inside SQL comments — a bare `%` not part of `%s`/`%%` anywhere in the text
    breaks it. Don't put a literal `%` in any SQL string passed to cur.execute();
    write out "percent" or use a ratio instead.
    """

    @unittest.skipUnless(os.environ.get("DATABASE_URL"), "requires live DATABASE_URL")
    def test_newsletter_search_returns_hits_without_error(self):

        errors_logged = []
        orig_error = api._log.error

        def capture_error(msg, *args, **kwargs):
            errors_logged.append(msg)
            return orig_error(msg, *args, **kwargs)

        api._log.error = capture_error
        try:
            result = api._search_postgres("marketing", type_="newsletters", limit=20)
        finally:
            api._log.error = orig_error

        self.assertNotIn(
            "search_newsletter_failed",
            errors_logged,
            "_do_newsletter_search raised and was silently swallowed — check for a "
            "bare % in the query's SQL text (comments included).",
        )
        self.assertGreater(
            len(result.get("hits") or []),
            0,
            "newsletter search returned zero hits for a common term — likely "
            "silently broken again.",
        )


if __name__ == "__main__":
    unittest.main()
