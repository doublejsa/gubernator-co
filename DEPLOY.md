# Deployment & Update Process

The single source of truth for how gubernator.co gets updated. Both Claude Code
(laptop) and OpenClaw (Telegram) follow this exact process.

---

## The model

> **One branch (`main`) = truth. Two FTP targets = environments.**

- Git is **source-of-truth and history only** — it is **not** the deploy mechanism.
- Deployment is **FTP file upload**, done separately, to two targets:
  - **UAT** — `uat.gubernator.co` (review/staging gate)
  - **Prod** — `gubernator.co` (live)
- There is only **one branch: `main`**. Branches do **not** map to environments.
  (The old dev/staging/production branches were removed — they caused drift.)

---

## The update loop (both actors follow this)

```
1. git pull origin main          # ALWAYS pull first — prevents clobbering the other actor
2. make the edit
3. git commit -m "..." && git push origin main
4. FTP-deploy the changed files → uat.gubernator.co
5. review at https://uat.gubernator.co
6. approve → FTP-deploy the same files → gubernator.co
```

---

## Division of labour

| Actor | Handles | Trigger |
|---|---|---|
| **OpenClaw** (Telegram) | Small content tweaks — text, prices, copy | You message it |
| **Claude Code** (laptop) | Structural / design changes, new pages | You work with Claude Code |

---

## Rules (these prevent collisions and leaks)

1. **`main` is the only branch.** Both actors commit to it. Whoever edits
   **pulls first, pushes after.**
2. **Deploy = FTP files only. NEVER `git clone` / `git pull` into the webroot.**
   Doing so previously put a `.git` folder (with a live token) on the public site.
   Git lives on the laptop and in OpenClaw's workspace — **never** in a docroot.
3. **UAT is the review gate.** Nothing reaches prod without appearing on UAT first.
4. **No parallel edits.** Don't have OpenClaw and Claude Code editing at the same moment.

---

## FTP deploy details

- **Server:** `ftp.jws.co.za`, port 21, **explicit FTPS**.
- **Method that works reliably:** control-channel TLS only (data channel plain).
  With curl: `curl --ftp-ssl-control -T <file> "ftp://ftp.jws.co.za/<path>"`
  (Plain `--ssl-reqd` hangs on larger files waiting for the completion reply.)

| Target | FTP username | Docroot |
|---|---|---|
| UAT  | `gubernator_uat@uat.gubernator.co` | `/home4/s9802008/public_html/uat.gubernator.co` |
| Prod | `gubernator_prod@gubernator.co`    | `/home4/s9802008/public_html/gubernator.co` |

> Passwords are held securely by the operator / OpenClaw vault — not stored in this repo.

### Files to deploy
The static site files (never `.git`, `.claude`, `.well-known`, `cgi-bin`):
```
index.html
confirmation-free-call.html
confirmation-consulting.html
confirmation-executive.html
confirmation-demo.html
assets/images/*
```

---

## Calendly confirmation redirects (prod URLs)

| Event | Redirect URL |
|---|---|
| 15-min call | `https://gubernator.co/confirmation-free-call.html` |
| 30-min demo | `https://gubernator.co/confirmation-demo.html` |
| 1-hr consulting | `https://gubernator.co/confirmation-consulting.html` |
| Executive discovery | `https://gubernator.co/confirmation-executive.html` |
