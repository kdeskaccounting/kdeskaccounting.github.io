# scripts/

Operational scripts for the KDesk Accounting blog. Mirrors the
`~/digitalproducts/scripts/` pattern (PEP-723 inline-script dependencies via `uv`).

## `pull_seo_snapshot.py`

Pulls a fresh GSC + GA4 snapshot and appends two JSONL rows under
`marketing/seo-tracking/`. Designed to be invoked weekly by a systemd timer
(see `scheduling/`) or run manually.

```bash
./scripts/pull_seo_snapshot.py            # full run: pull, append, commit, push
KDESK_SEO_SKIP_COMMIT=1 ./scripts/pull_seo_snapshot.py   # dry-run (no git ops)
```

## One-time setup (10 min, you only do this once)

1. **Create a Google Cloud project + enable APIs**

   - Go to <https://console.cloud.google.com/projectcreate> and create a project
     (or pick an existing one). Project name like `kdesk-analytics`.
   - Enable two APIs at <https://console.cloud.google.com/apis/library>:
     - "Search Console API"
     - "Google Analytics Data API"

2. **Configure OAuth consent screen**

   - <https://console.cloud.google.com/apis/credentials/consent>
   - User type: External (you're the only user)
   - App name: KDesk Analytics
   - User support email + developer email: your email
   - Add yourself (santiagokdesk@gmail.com) as a Test user
   - No scopes need to be added on the consent screen — the script requests them

3. **Create OAuth client ID**

   - <https://console.cloud.google.com/apis/credentials>
   - Create Credentials → OAuth client ID → Application type: **Desktop**
   - Name: `kdesk-seo-snapshot`
   - Download the JSON. Save it as `~/kdesk-analytics/credentials.json` (NOT in this repo).

4. **Mint the refresh token (one interactive step)**

   ```bash
   cd ~/kdeskaccounting-blog
   ./scripts/setup_seo_oauth.py ~/kdesk-analytics/credentials.json
   ```

   A browser opens, you authorize the two scopes (Search Console read + Analytics read)
   for `santiagokdesk@gmail.com`. The token is written to
   `~/kdesk-analytics/google-token.json`.

5. **Test the puller**

   ```bash
   KDESK_SEO_SKIP_COMMIT=1 ./scripts/pull_seo_snapshot.py
   ```

   Should print two summary lines and append rows to both JSONL files. If anything
   throws, fix it before wiring the timer.

6. **Wire the weekly systemd timer**

   See `scheduling/README.md` in this repo.

## Credentials hygiene

- `~/kdesk-analytics/credentials.json` and `~/kdesk-analytics/google-token.json`
  live outside the repo on purpose. Never commit them.
- The refresh token is read-only-scoped to GSC + GA4. It can't write anything to
  either property and can't touch other Google services.
- To revoke: <https://myaccount.google.com/permissions> → KDesk Analytics → remove.
