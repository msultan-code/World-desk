# WORLD DESK v1.0.1 — Deployment Checklist

**Target:** Render Blueprint deployment of `msultan-code/World-desk` (`main`).
**Rule:** This release must deploy with **no manual recreation** of existing Render services
and **no changes** to `render.yaml` plans or paid resources.

---

## Pre-deployment (on the branch, before merge)

- [x] All 34 regression tests pass: `python -m pytest test_worlddesk.py -v` → 34 passed.
- [x] `/healthz` returns `200 {"status":"ok","version":"1.0.1","sources":30}`.
- [x] UI displays `v1.0.1`; `v0.7.2`/`v0.6` are gone.
- [x] `manifest.json` reports `version: 1.0.1`.
- [x] No secrets, tokens, or credentials are committed. (no `.env`, no hardcoded keys)
- [x] No new infrastructure dependencies added; `requirements.txt` unchanged in substance.
- [x] `render.yaml` not modified — no plan/resource changes.
- [x] Branch `fix/world-desk-v1.0.1` contains the complete diff + 4 docs + test file.
- [x] Pull request opened into `main`; **not** merged (awaiting review/approval).

## What changes on Render after merge (automatic deploy from `main`)

Render's auto-deploy from `main` will rebuild the web service from the updated `app.py`.
No manual action is required for:

- **Web service** — rebuilds from the same Dockerfile/start command; `/healthz` is a new
  route on the existing FastAPI app. Health check should point to `/healthz` (if it
  already does, no change; if it pointed to `/`, that still returns 200).
- **PostgreSQL** — untouched. v1.0.1 makes no schema or connection changes.
- **Background worker** — untouched. The ingestion functions used by the worker are the
  same `fetch_one`/`cluster`/`dedup_headlines` functions the web service uses; the worker
  picks up the new code on its next deploy.
- **Docker / Render Blueprint** — untouched (`render.yaml` not modified).

## Post-deployment verification (after Render auto-deploy completes)

1. `curl -s https://world-desk-web.onrender.com/healthz`
   → expect `{"status":"ok","version":"1.0.1","sources":30}`
2. `curl -s https://world-desk-web.onrender.com/ | grep -o 'v1.0.1'`
   → expect `v1.0.1`
3. `curl -s https://world-desk-web.onrender.com/api/refresh | python -m json.tool`
   → expect `"version":"1.0.1"`, `sources` array with ~22 `ok:true`, and `headlines`
   containing no literal `&nbsp;` or `&`.
4. Open the app in a browser → TOP STORIES cards should show Arabic titles right-aligned
   with correct RTL spacing and a metadata line like
   `45 منشورًا · 12 دولة · 47 عنوانًا` (no malformed `headlines 2`).
5. Trigger a source failure (e.g. temporarily disable one source) and confirm the cycle
   completes and the other sources still ingest.
6. Confirm the worker and database remain live (Render dashboard).

## Rollback (if needed)

Revert the merge commit on `main`; Render auto-deploys the previous state. No service
recreation is required because no infrastructure changed.

## Things this release explicitly does NOT do
- Does not modify `render.yaml` plans or paid resource tiers.
- Does not delete infrastructure, rotate secrets, or recreate the database.
- Does not change the hosting platform, deployment model, or Docker setup.
- Does not begin production deployment before PR review and explicit approval.
