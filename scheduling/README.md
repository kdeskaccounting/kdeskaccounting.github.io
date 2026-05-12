# scheduling/

systemd user timers for KDesk Accounting recurring jobs. Mirrors the
`~/digitalproducts/scheduling/` pattern.

## Active timers

| Unit | Cadence | Purpose |
|---|---|---|
| `kdesk-seo-weekly.timer` | Monday 09:00 local | Pull GSC + GA4, append to `marketing/seo-tracking/*.jsonl`, commit + push |

## Install

```bash
# Copy unit files into user systemd dir
mkdir -p ~/.config/systemd/user
cp scheduling/kdesk-seo-weekly.{service,timer} ~/.config/systemd/user/

# Enable + start
systemctl --user daemon-reload
systemctl --user enable --now kdesk-seo-weekly.timer

# Verify
systemctl --user list-timers --all | grep kdesk-seo
systemctl --user status kdesk-seo-weekly.timer
```

## WSL2 caveat

User units only run while the WSL distro is up. Two options:

1. Enable lingering so user units keep running after logout:
   `sudo loginctl enable-linger $USER` (one-time, persists across reboots)
2. Accept that if WSL is shut down at 9am Monday, the run skips. `Persistent=true`
   in the timer means it will catch up on the next boot — so missed Mondays
   trigger as soon as the distro comes back up.

## Logs

```bash
journalctl --user -u kdesk-seo-weekly.service -n 50
tail -f logs/seo-snapshot.log
```

The script writes a 2-line summary on success and a clear error message on
failure. If the OAuth token is missing or expired, it points you back to
`scripts/setup_seo_oauth.py`.

## Manual run (no timer, ad hoc)

```bash
./scripts/pull_seo_snapshot.py
```

Same code path — appends rows, commits, pushes.
