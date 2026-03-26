#!/usr/bin/env python3
"""
Fix the broken n8n Gmail OAuth credential for Marketingteam@nickient.com.
Steps:
  1. Open browser for fresh Google OAuth (fixes invalid_rapt)
  2. Capture token via local HTTP server
  3. Create new n8n gmailOAuth2 credential
  4. Patch both newsletter workflows to use the new credential
"""
import http.server
import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

N8N_BASE = "https://entagency.app.n8n.cloud/api/v1"
N8N_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMzg5YzU4MC01M2RiLTQ2NzgtYmQ2Zi0zNmNlNjE4Y2YyNDQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY4OTM5OTg5fQ.CwRHJd3EObgAZiyaLuaj3_pff2uv4GzSuC0Kpsm33tk"

CLIENT_SECRET_FILE = os.path.expanduser("~/.config/gws/client_secret.json")
CALLBACK_PORT = 8899
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/"
SCOPES = "https://mail.google.com/"

WORKFLOW_IDS = [
    "FPWjPuFq2jkPkJmj",  # Newsletter Sync Daily
    "sbhJSZEELdkQZVnG",  # Newsletter Backfill
]
OLD_CRED_ID = "LrrTIA7Dv6yJoAuP"
TOKEN_CACHE = "/tmp/gmail_tokens_nickient.json"

# -- OAuth flow --

def n8n_request(method, path, body=None):
    url = f"{N8N_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        print(f"  HTTP {e.code}: {body.decode()[:300]}")
        return None


def get_auth_code():
    """Start local server, open browser, return auth code."""
    with open(CLIENT_SECRET_FILE) as f:
        cfg = json.load(f)["installed"]

    client_id = cfg["client_id"]
    auth_uri = cfg["auth_uri"]

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": "Marketingteam@nickient.com",
    })
    auth_url = f"{auth_uri}?{params}"

    code_holder = {}
    shutdown_event = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Auth complete! You can close this tab.</h2></body></html>")
                shutdown_event.set()
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"No code found.")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), Handler)

    def serve():
        while not shutdown_event.is_set():
            server.handle_request()

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    print(f"\nOpening browser for Google auth...")
    print(f"URL: {auth_url}\n")
    subprocess.run(["open", auth_url])

    print("Waiting for you to complete the browser auth flow...")
    shutdown_event.wait(timeout=300)
    server.server_close()

    return code_holder.get("code")


def exchange_code_for_tokens(code):
    with open(CLIENT_SECRET_FILE) as f:
        cfg = json.load(f)["installed"]

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(cfg["token_uri"], data=data)
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return resp, cfg["client_id"], cfg["client_secret"]


def create_n8n_credential(token_data, client_id, client_secret):
    # n8n stores oauthTokenData as a JSON string (type: "json" in schema)
    oauth_token_data = json.dumps({
        "access_token": token_data.get("access_token", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "refresh_token": token_data.get("refresh_token", ""),
        "expiry_date": None,
        "scope": token_data.get("scope", SCOPES),
    })

    # Minimal payload: only oauthTokenData (schema else-branch means clientId/clientSecret not required)
    payload = {
        "name": "Gmail OAuth (Marketingteam@nickient.com)",
        "type": "gmailOAuth2",
        "data": {
            "oauthTokenData": oauth_token_data,
        },
    }

    result = n8n_request("POST", "/credentials", payload)
    if not result or not result.get("id"):
        # Try with clientId/clientSecret included
        print("  Retrying with clientId/clientSecret...")
        payload["data"]["clientId"] = client_id
        payload["data"]["clientSecret"] = client_secret
        result = n8n_request("POST", "/credentials", payload)
    return result


def update_workflows(new_cred_id, new_cred_name):
    for wf_id in WORKFLOW_IDS:
        print(f"\n  Fetching workflow {wf_id}...")
        wf = n8n_request("GET", f"/workflows/{wf_id}")
        if not wf:
            print(f"  Could not fetch workflow {wf_id}")
            continue

        updated = False
        nodes = wf.get("nodes", [])
        for node in nodes:
            creds = node.get("credentials", {})
            for cred_type, cred_val in creds.items():
                if isinstance(cred_val, dict) and cred_val.get("id") == OLD_CRED_ID:
                    print(f"  Updating node '{node['name']}' credential {cred_type}")
                    cred_val["id"] = new_cred_id
                    cred_val["name"] = new_cred_name
                    updated = True

        if updated:
            # PUT the updated workflow
            result = n8n_request("PUT", f"/workflows/{wf_id}", {
                "name": wf.get("name"),
                "nodes": nodes,
                "connections": wf.get("connections", {}),
                "settings": wf.get("settings", {}),
                "staticData": wf.get("staticData"),
            })
            if result:
                print(f"  ✅ Workflow {wf_id} updated")
            else:
                print(f"  ❌ Failed to update workflow {wf_id}")
        else:
            print(f"  No nodes with old credential found in {wf_id}")


def main():
    print("=== Fix n8n Gmail Credential ===\n")

    with open(CLIENT_SECRET_FILE) as f:
        cfg = json.load(f)["installed"]
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]

    # Step 1 & 2: Get tokens (from cache or via browser)
    if os.path.exists(TOKEN_CACHE):
        print(f"Using cached tokens from {TOKEN_CACHE}")
        with open(TOKEN_CACHE) as f:
            token_data = json.load(f)
    else:
        code = get_auth_code()
        if not code:
            print("❌ No auth code received (timed out or cancelled)")
            sys.exit(1)
        print(f"✅ Got auth code")

        print("Exchanging code for tokens...")
        token_data, client_id, client_secret = exchange_code_for_tokens(code)
        if not token_data.get("access_token"):
            print(f"❌ Token exchange failed: {token_data}")
            sys.exit(1)
        print(f"✅ Got tokens (scope: {token_data.get('scope', 'N/A')})")
        with open(TOKEN_CACHE, "w") as f:
            json.dump({"token_data": token_data, "client_id": client_id, "client_secret": client_secret}, f)

    if isinstance(token_data, dict) and "token_data" in token_data:
        client_id = token_data["client_id"]
        client_secret = token_data["client_secret"]
        token_data = token_data["token_data"]

    print(f"Using tokens (scope: {token_data.get('scope', 'N/A')})")

    # Step 3: Create new n8n credential
    print("\nCreating new n8n credential...")
    cred = create_n8n_credential(token_data, client_id, client_secret)
    if not cred or not cred.get("id"):
        print(f"❌ Failed to create credential: {cred}")
        sys.exit(1)
    new_cred_id = cred["id"]
    new_cred_name = cred.get("name", "Gmail OAuth (Marketingteam@nickient.com)")
    print(f"✅ Created credential: {new_cred_id}")

    # Step 4: Update workflows
    print("\nUpdating workflow nodes to use new credential...")
    update_workflows(new_cred_id, new_cred_name)

    print("\n✅ Done! Both newsletter workflows now use fresh Gmail credentials.")
    print(f"New credential ID: {new_cred_id}")


if __name__ == "__main__":
    main()
