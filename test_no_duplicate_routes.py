import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import api


class TestNoDuplicateRoutes(unittest.TestCase):
    """Guards against the /topic-guide and /visual-moments class of bug: a
    second handler registered on the same method+path that FastAPI silently
    shadows forever, with no runtime error to surface it. See
    api._check_duplicate_routes and CLAUDE.md's resolved-bugs section.
    """

    def test_every_method_path_pair_is_unique(self):
        seen: dict[tuple[str, str], int] = {}
        for route in api.app.routes:
            methods = getattr(route, "methods", None)
            path = getattr(route, "path", None)
            if not methods or not path:
                continue
            for method in methods:
                key = (method, path)
                seen[key] = seen.get(key, 0) + 1

        dupes = {k: v for k, v in seen.items() if v > 1}
        self.assertEqual(
            dupes,
            {},
            f"Duplicate route registrations found (later ones are dead code, "
            f"silently shadowed by FastAPI): {dupes}",
        )


if __name__ == "__main__":
    unittest.main()
