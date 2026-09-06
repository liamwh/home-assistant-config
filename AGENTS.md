# AGENTS.md — working with this Home Assistant config

## What this repo is

The Home Assistant configuration for Liam's home, **declaratively managed**.
Ground truth for all configuration is this Git repo. The Home Assistant
instance must never be configured imperatively (no UI-created automations, no
API-written config). Using the API/UI to *inspect*, *test*, or *temporarily*
toggle something is fine — but anything worth keeping gets committed here.

## Topology

| Piece | Where | Notes |
|---|---|---|
| **ha-mcp MCP server** (preferred) | `.omp/mcp.json` in this repo (`uvx ha-mcp@latest`) | Talk to the running HA instance through its tools: inspect states, call services, reload. Auth via `HA_TOKEN` (exported in `~/.zshenv`, long-lived) → `http://homeassistant.local:8123` |
| SSH (backup) | `root@192.168.1.27` (HAOS SSH add-on, port 22) | Passwordless from Zeus. Use for `git pull`, file access, `ha core logs`, `ha core restart`, and anything MCP can't do |
| GitHub | `https://github.com/liamwh/home-assistant-config.git` | `origin` (master) |
| HA VM | `root@192.168.1.27` — `/config` **is** a git checkout of this repo | Same host as SSH above; `homeassistant.local` resolves to it |
| HA frontend | `http://192.168.1.27:8123` / `https://home.liamwh.com` | HA account auth |
| HA API token (Zeus) | `~/.config/sops-nix/secrets/home-assistant-token` (SOPS, 0400) | Direct REST fallback; can read states and **call services**, but cannot fire raw events (non-admin user) — drive the integration's own services instead |

**Interacting with the running instance: prefer the `ha-mcp` MCP server tools**
(states, service calls, reloads). Fall back to SSH only for git operations on
the VM, logs, restarts, and file-level work.

## Skill: home-assistant-best-practices

This repo ships the **`home-assistant-best-practices` skill** at
`.agents/skills/home-assistant-best-practices/` (tracked in `skills-lock.json`,
source: `homeassistant-ai/skills`). **Read it before creating or editing
automations, scripts, scenes, dashboards, or blueprints**, choosing helpers vs
template sensors, picking automation `mode:`s, or touching entity IDs — it
encodes the conventions this config should follow (e.g. prefer native options
over Jinja, `entity_id` over `device_id`, check consumers before renames).

## Standard workflow (edit → deploy)

```bash
# on Zeus
cd ~/git/home-assistant-config
# ... edit YAML (read the home-assistant-best-practices skill first) ...
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('**/*.yaml', recursive=True)]"  # sanity parse
git commit -am "..." && git push

# deploy to the VM (SSH — the one step that still needs it)
ssh root@192.168.1.27 'git -C /config pull --ff-only'

# make HA pick it up (pick the cheapest that works; prefer ha-mcp tools):
#   automations only  → call the automation.reload service (ha-mcp, or curl below)
#   includes/*.yaml   → depends on integration; many support a reload service
#   configuration.yaml / logger / integrations without reload → restart core
```

Reload automations via ha-mcp (service call to `automation.reload`), or via REST:

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" -H 'Content-Type: application/json' \
     -d '{"entity_id": "all"}' http://homeassistant.local:8123/api/services/automation/reload
```

Full restart (SSH only): `ssh root@192.168.1.27 'ha core restart'` (~1 min).

## Repo conventions & gotchas

- **Automations** live in `automations/*.yaml` (`!include_dir_merge_list`).
  Legacy `platform:`/`service:` trigger/action syntax is used throughout —
  match it; don't modernize files you're not otherwise touching.
- **Integration config** lives in `includes/*.yaml`, wired from
  `configuration.yaml` with `!include`. The file must be a bare list when the
  key expects a list (e.g. `template:`).
- **Custom components (HACS)**: only `services.yaml` + `translations/` are
  tracked; `*.py` is gitignored. The actual code is installed/updated by HACS
  on the VM (`/config/custom_components/<name>/`). Version drift between the
  committed `services.yaml` and the installed code is normal and shows up as a
  dirty file on the VM — check `/config/custom_components/<name>/manifest.json`
  for the *installed* version.
- **`secrets.yaml` exists only on the VM** (gitignored). Never commit secrets;
  reference `!secret` in committed YAML.
- `.HA_VERSION` is machine state, gitignored (untracked 2026-09). Don't
  re-add it; the VM stays clean so `git pull --ff-only` works.
- **CI**: Super Linter + yamllint run on PRs (not master pushes). Many files
  are CRLF; yamllint's `new-lines` error on those is pre-existing — don't
  "fix" line endings in files you aren't otherwise changing.
- `README.md` badge versions are manual/stale; `utils/commit-readme.sh` is a
  convenience for committing regenerated README content.

## Inspecting / debugging the running system

- **First choice: ha-mcp tools** for states, service calls, and anything the
  running instance can tell you. What follows are the lower-level routes.
- **Logs**: `ssh root@192.168.1.27 'ha core logs'` (journald, follow with
  grep). Log *files* in `/config` are stale leftovers; one 10 GB `.old` log
  was caused by `custom_components.adaptive_lighting: debug` logger config
  (removed 2026-09-06) — avoid re-enabling debug logging for it.
- **Database** (recorder, 7-day retention): no `sqlite3` on the VM — copy it
  to Zeus: `scp root@192.168.1.27:/config/home-assistant_v2.db /tmp/` and
  query locally. Also grab `home-assistant_v2.db-wal` if you need the last
  minutes. Schema: `events(event_type, time_fired_ts, data_id →
  event_data.shared_data JSON)`, `states(...)`, `event_types` maps ids.
- **Timestamps in the DB are UTC epoch seconds**; the home runs
  Europe/Amsterdam (CEST = UTC+2 in summer). "3:17 AM" storms are ~01:17 UTC.
- Light *states* may be absent from the recorder for some entities; service
  calls (`call_service` events) and integration events
  (`adaptive_lighting.manual_control`, `automation_triggered`, …) are the
  reliable record. To attribute a service call to an automation, join
  `call_service.context_id` = `automation_triggered.context_id`.
- **Traces**: `/config/.storage/trace.saved_traces` on the VM.
- Entity-level API inspection: `GET /api/states/<entity_id>` with the token.

## Adaptive lighting specifics (why the notification storm happened)

Config: `includes/adaptive_lighting.yaml` — 9 switches, all with
`take_over_control: true`, `detect_non_ha_changes: true`, `interval: 30`.

- `detect_non_ha_changes` polls every light every `interval` (30 s) via
  `homeassistant.update_entity` and compares against the last service data
  *it* sent. If a light sits at a brightness/colour that AL didn't set — e.g.
  dimmed from a Hue dimmer, Hue app, or bridge scene — adaptive-lighting
  ≥1.31.0 re-fires the `adaptive_lighting.manual_control` **event every
  interval** until the light is turned off or reset. That was the September
  2026 notification storm (~1.6k events/day, every 30 s for hours,
  e.g. 23:00→03:18 while a light sat at a manually-dimmed level).
- `automations/adaptive_lighting.yaml` therefore **rate-limits both
  manual_control automations to one run per 30 min** (`this.attributes.
  last_triggered` guard). Don't remove it; upstream has no fix as of 1.31.0.
- The "reset manual_control after 1 hour" automation is the circuit breaker:
  a successful `adaptive_lighting.set_manual_control(false)` clears AL's
  `last_service_data` and re-adapts, which ends the event loop. Its old
  condition had `state_attr('switch', ...)` (string literal!) which always
  errored → 3.7k triggers, 0 resets in a week. Fixed 2026-09-06; the correct
  form is `state_attr(switch, 'manual_control')` (the variable).
- Hallway/staircase lights are excluded from both automations by condition —
  they generate the most events (motion-lit Hue bulbs) but are intentionally
  silent.
- If storms ever recur: check `switch.adaptive_lighting_*`'s `manual_control`
  attribute to see which light is flagged, and look for lights ON at a
  brightness AL didn't set.
