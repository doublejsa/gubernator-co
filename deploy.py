#!/usr/bin/env python3
"""
Gubernator.co deployment script.

Deploys the static site to one environment (UAT or Prod) over explicit-FTPS,
then verifies over HTTP. Git steps (pull/commit/push) are optional via --message.

Usage:
    python3 deploy.py uat                      # deploy current working tree to UAT
    python3 deploy.py prod                      # deploy to Prod (live)
    python3 deploy.py uat -m "Update pricing"   # git add/commit/push, then deploy to UAT

Credentials come from environment variables (NEVER hardcode them):
    FTP_HOST            e.g. ftp.jws.co.za
    UAT_FTP_USER        e.g. gubernator_uat@uat.gubernator.co
    UAT_FTP_PASS
    PROD_FTP_USER       e.g. gubernator_prod@gubernator.co
    PROD_FTP_PASS

Rules baked in:
  * Only files in FILES[] are ever uploaded — .git/.claude can't leak to the webroot.
  * Control-channel TLS only (login encrypted, data channel clear) — avoids the
    FTPS completion-hang seen on this host with full data-channel TLS.
  * Every uploaded file is re-fetched over HTTPS and checked for 200 + size match.
"""

import sys
import os
import ssl
import time
import argparse
import hashlib
import subprocess
import urllib.request
from ftplib import FTP_TLS

# --- Files that make up the site. Nothing outside this list is ever uploaded. ---
FILES = [
    "index.html",
    "confirmation-free-call.html",
    "confirmation-consulting.html",
    "confirmation-executive.html",
    "confirmation-demo.html",
    "assets/images/wheel.png",
    "assets/images/wordmark.png",
    "assets/images/screenshot.png",
]

ENVIRONMENTS = {
    "uat":  {"user_env": "UAT_FTP_USER",  "pass_env": "UAT_FTP_PASS",  "url": "https://uat.gubernator.co"},
    "prod": {"user_env": "PROD_FTP_USER", "pass_env": "PROD_FTP_PASS", "url": "https://gubernator.co"},
}

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run_git(args):
    print(f"$ git {' '.join(args)}")
    r = subprocess.run(["git", "-C", REPO_ROOT, *args], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def git_sync(message):
    """Pull, commit all changes, push. Only runs when -m/--message is given."""
    run_git(["pull", "--rebase", "origin", "main"])
    status = run_git(["status", "--porcelain"])
    if status:
        run_git(["add", "-A"])
        run_git(["commit", "-m", message])
        run_git(["push", "origin", "main"])
        print("Committed and pushed to main.")
    else:
        print("No local changes to commit; pull is up to date.")


def connect(user, password, host):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # host uses a shared/self-signed cert
    ftp = FTP_TLS(context=ctx)
    ftp.connect(host, 21, timeout=60)
    ftp.auth()            # explicit FTPS: encrypt the control channel
    ftp.login(user, password)
    # NOTE: deliberately NOT calling ftp.prot_p() -> data channel stays clear.
    # This is the equivalent of curl --ftp-ssl-control and avoids the 226-hang.
    return ftp


def ensure_dirs(ftp, remote_path):
    parts = remote_path.split("/")[:-1]
    path = ""
    for p in parts:
        path = f"{path}/{p}" if path else p
        try:
            ftp.mkd(path)
        except Exception:
            pass  # already exists


def upload(ftp, local_rel):
    local_path = os.path.join(REPO_ROOT, local_rel)
    if not os.path.isfile(local_path):
        die(f"missing local file: {local_rel}")
    ensure_dirs(ftp, local_rel)
    with open(local_path, "rb") as f:
        ftp.storbinary(f"STOR {local_rel}", f)


def verify(base_url, local_rel):
    local_path = os.path.join(REPO_ROOT, local_rel)
    local_size = os.path.getsize(local_path)
    url = f"{base_url}/{local_rel}?cb={int(time.time())}"
    req = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (gubernator-deploy)",
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            served = resp.read()
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)
    if len(served) != local_size:
        return False, f"size mismatch (local {local_size}, served {len(served)})"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser(description="Deploy gubernator.co to an environment.")
    ap.add_argument("env", choices=ENVIRONMENTS.keys(), help="target environment")
    ap.add_argument("-m", "--message", help="git commit message (runs pull/commit/push first)")
    args = ap.parse_args()

    cfg = ENVIRONMENTS[args.env]
    host = os.environ.get("FTP_HOST")
    user = os.environ.get(cfg["user_env"])
    password = os.environ.get(cfg["pass_env"])
    if not (host and user and password):
        die(f"missing env vars: FTP_HOST, {cfg['user_env']}, {cfg['pass_env']}")

    if args.message:
        git_sync(args.message)

    print(f"\nDeploying {len(FILES)} files to {args.env.upper()} ({cfg['url']}) ...")
    ftp = connect(user, password, host)
    try:
        for f in FILES:
            upload(ftp, f)
            print(f"  uploaded  {f}")
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    print("\nVerifying over HTTPS ...")
    failures = []
    for f in FILES:
        ok, detail = verify(cfg["url"], f)
        print(f"  {'OK  ' if ok else 'FAIL'}  {f}  ({detail})")
        if not ok:
            failures.append(f)

    if failures:
        die(f"{len(failures)} file(s) failed verification: {', '.join(failures)}")
    print(f"\n✅ {args.env.upper()} deploy complete and verified — {cfg['url']}")


if __name__ == "__main__":
    main()
