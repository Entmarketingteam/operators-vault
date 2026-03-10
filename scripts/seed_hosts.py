"""
Seed confirmed podcast hosts into speaker_profiles.
Run after deploying the add_host_fields migration.

Usage:
    python3 scripts/seed_hosts.py [--base-url https://superb-smile-production.up.railway.app]
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
import argparse

HOSTS = [
    # ── 9operators ──────────────────────────────────────────────────────────
    {
        "slug": "sean-frank",
        "name": "Sean Frank",
        "company": "The Ridge",
        "title": "CEO",
        "bio": (
            "CEO of The Ridge, a 9-figure accessories brand known for slim wallets and EDC gear. "
            "Built Ridge from a $30k investment into one of the most recognizable DTC brands in the US. "
            "Co-host of the 9 Operators podcast."
        ),
        "twitter_handle": "SeanEcom",
        "linkedin_url": "https://www.linkedin.com/in/seandavidfrank/",
        "photo_url": "https://cdn.theorg.com/b9ae4b33-2d46-42f9-b450-91b37e340e6d_medium.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "9operators",
    },
    {
        "slug": "matt-bertulli",
        "name": "Matt Bertulli",
        "company": "Pela Case & Lomi",
        "title": "Co-Founder & CEO",
        "bio": (
            "Co-founder & CEO of Pela Case (the world's first compostable phone case) and Lomi (home food recycler). "
            "Serial DTC operator who has scaled multiple brands to 9 figures with a sustainability-first approach. "
            "Co-host of the 9 Operators podcast."
        ),
        "twitter_handle": "mbertulli",
        "linkedin_url": "https://www.linkedin.com/in/mbertulli/",
        "photo_url": "https://kajabi-storefronts-production.kajabi-cdn.com/kajabi-storefronts-production/file-uploads/themes/2154272516/settings_images/6670e73-041e-8-3fa3-67d32210c080_Matt-March-234.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "9operators",
    },
    {
        "slug": "jason-panzer",
        "name": "Jason Panzer",
        "company": "HexClad Cookware",
        "title": "President",
        "bio": (
            "President of HexClad Cookware, the premium cookware brand partnered with Gordon Ramsay. "
            "Former investment banker turned operator, scaled HexClad to a globally recognized $300M+ brand. "
            "Co-host of the 9 Operators podcast."
        ),
        "twitter_handle": "JasonPanzer",
        "linkedin_url": "https://www.linkedin.com/in/jasonpanzer/",
        "photo_url": "https://cdn.theorg.com/297d7e2b-ee58-49c5-86d4-90e73d1b4fe1_medium.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "9operators",
    },
    {
        "slug": "mike-beckham",
        "name": "Mike Beckham",
        "company": "Simple Modern",
        "title": "Co-Founder & CEO",
        "bio": (
            "Co-founder & CEO of Simple Modern, a values-driven drinkware brand doing 9 figures on Amazon and DTC. "
            "Built one of the most profitable consumer brands in the US while donating 10% of profits to charity. "
            "Co-host of the 9 Operators podcast."
        ),
        "twitter_handle": "mikebeckhamsm",
        "linkedin_url": "https://www.linkedin.com/in/mike-beckham-93a3b99/",
        "photo_url": "https://cdn.theorg.com/92ee8b9d-ec73-4589-8748-e50d273cffcf_medium.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "9operators",
    },
    # ── marketing_operator ──────────────────────────────────────────────────
    {
        "slug": "cody-plofker",
        "name": "Cody Plofker",
        "company": "Jones Road Beauty",
        "title": "CEO",
        "bio": (
            "CEO of Jones Road Beauty, Bobbi Brown's clean beauty brand. "
            "Took the brand from launch to 9 figures using radical transparency, community-first growth, and data-driven marketing. "
            "Co-host of the Marketing Operators podcast."
        ),
        "twitter_handle": "codyplof",
        "linkedin_url": "https://www.linkedin.com/in/cody-plofker-47a29b120",
        "photo_url": "https://cdn.theorg.com/7374ab5c-35e8-43b9-9404-4bdb2f69850d_medium.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "marketing_operator",
    },
    {
        "slug": "connor-macdonald",
        "name": "Connor MacDonald",
        "company": "The Ridge",
        "title": "CMO",
        "bio": (
            "CMO of The Ridge. One of the most respected performance marketers in DTC, "
            "known for creative testing frameworks, paid social mastery, and building scalable acquisition systems. "
            "Co-host of the Marketing Operators podcast."
        ),
        "twitter_handle": "couuor",
        "linkedin_url": "https://www.linkedin.com/in/theconnormacdonald",
        "photo_url": "https://cdn.theorg.com/1e50f4ed-7c2b-4c4d-85ed-ea67936e0022_medium.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "marketing_operator",
    },
    {
        "slug": "connor-rolain",
        "name": "Connor Rolain",
        "company": "HexClad Cookware",
        "title": "Global Head of Growth Marketing",
        "bio": (
            "Global Head of Growth Marketing at HexClad Cookware. "
            "Expert in scaling paid acquisition, retention, and lifecycle marketing for premium consumer brands. "
            "Co-host of the Marketing Operators podcast."
        ),
        "twitter_handle": "connorrolain",
        "linkedin_url": "https://www.linkedin.com/in/connor-rolain-b190ab148/",
        "photo_url": "https://cdn.theorg.com/2eb5680f-2acc-4beb-8106-9c33812f433e_medium.jpg",
        "source": "manual",
        "is_host": True,
        "host_podcast": "marketing_operator",
    },
]


def upsert(base_url: str, host: dict) -> bool:
    url = f"{base_url}/speakers"
    data = json.dumps(host).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            print(f"  ✓ {host['name']} ({host['host_podcast']}) → slug={resp.get('slug')}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ✗ {host['name']}: HTTP {e.code} — {body[:120]}")
        return False
    except Exception as e:
        print(f"  ✗ {host['name']}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://superb-smile-production.up.railway.app")
    args = parser.parse_args()

    print(f"Seeding {len(HOSTS)} hosts → {args.base_url}\n")
    ok = sum(upsert(args.base_url, h) for h in HOSTS)
    print(f"\nDone: {ok}/{len(HOSTS)} upserted")


if __name__ == "__main__":
    main()
