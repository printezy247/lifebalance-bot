# LifeBalance Bot

A Telegram bot for keeping work and life in balance. It manages tasks, reminds
you proactively, and watches whether one area of your life is quietly crowding
out the rest.

Built with [python-telegram-bot](https://python-telegram-bot.org/) 21.x, deployed
on Railway.

---

## What it does

**Tap, don't type.** `/today` lists your tasks as buttons. Tap one to open it,
then Done / Snooze / Coach me / Reschedule. A persistent keyboard sits under the
message box so there is nothing to memorise.

**It comes to you.** A morning briefing, an evening wind-down with one-tap
rollover of anything unfinished, overdue nudges, and a Sunday digest. All of it
silenced during quiet hours, all of it toggleable from `/settings`.

**It notices patterns.** Once there is enough history, it will tell you when 60%
of your completed work is one category, when your energy ratings are trending
low, or when `family` has gone quiet for ten days.

---

## Commands

### Basics
| Command | Description |
|---|---|
| `/start` | Welcome message, sets up the persistent keyboard |
| `/help` | Every command, plus your current schedule and timezone |

### Tasks
| Command | Description |
|---|---|
| `/add <task> <time> [category]` | Add a task. `/add Pick up kids 3:30pm family` |
| `/today` | Today's tasks with tap-to-act buttons |
| `/week` | Weekly progress bars, per category, plus streak |
| `/done <id>` | Mark complete, then rate energy 1-5 with one tap |
| `/snooze <id>` | Delay 30 minutes |
| `/reschedule <id> <time>` | Move to a new time |

Accepted time formats: `3pm`, `3:30pm`, `15:00`, `tomorrow`, `tomorrow 9am`

Categories: `family` `trading` `marketing` `content` `learning` `health`
`admin` `general`

### Focus
| Command | Description |
|---|---|
| `/focus` | Start a timer using `FOCUS_DEFAULT` minutes |
| `/focus 50` | 50-minute block |
| `/focus 50 deep work` | With a label |
| `/focus stop` | Cancel a running timer |

### AI
| Command | Description |
|---|---|
| `/suggest` | A task suggestion, weighted by your recent energy ratings |
| `/ai_suggest` | Alias for `/suggest`, kept for backward compatibility |
| `/plan <goal> [category]` | Break a goal into subtasks with estimates |
| `/assist <id>` | Coaching tip for one task |

### Reflection and settings
| Command | Description |
|---|---|
| `/reflect` | Pick an area and answer one focused question |
| `/settings` | Toggle every automation, adjust quiet hours |
| `/brief` | Preview the morning briefing now |
| `/winddown` | Preview the evening wind-down now |
| `/digest` | Preview the weekly digest now |

The three preview commands exist so you can test the scheduled features
immediately instead of waiting until 07:00 or Sunday. They reply directly and
are not subject to quiet hours.

---

## Automations

| What | Default | Notes |
|---|---|---|
| Task reminder | 10 min before | **Exempt from quiet hours** — you scheduled it |
| Overdue nudge | 30 min after due | Fires once per task, never repeats |
| Morning briefing | 07:00 | Today's tasks, streak, what's up first |
| Evening wind-down | 21:00 | Recap + "roll unfinished to tomorrow" button |
| Weekly digest | Sunday 19:00 | Week stats + a reflection prompt |
| Backup | 03:00 | Snapshot to `DATA_DIR/backups`, keeps 14 |
| Quiet hours | 22:00-07:00 | Silences everything above except reminders |

### Insights

Balance, burnout and neglect warnings are folded into the wind-down and the
weekly digest rather than sent as separate notifications, each with a cooldown.
Every one refuses to speak until it has enough data to say something true:

| Insight | Stays silent until |
|---|---|
| Balance | 8 completed tasks in 14 days, then fires if one category is 60%+ |
| Burnout | 4 energy ratings in 7 days, then fires if the average is under 2.5 |
| Neglect | A watched category has 10 days of silence |

Expect quiet for the first week or two on a fresh install. That is intentional.

---

## Configuration

### Required

| Variable | Description |
|---|---|
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |

### Strongly recommended

| Variable | Default | Why it matters |
|---|---|---|
| `DATA_DIR` | `.` | **Must point at a mounted volume.** Without it, all data is lost on every redeploy |
| `BOT_TZ` | `UTC` | IANA name, e.g. `Asia/Kuala_Lumpur`. Without it, "3pm" means 3pm UTC |

The bot prints a warning at startup if `DATA_DIR` is unset.

### AI

| Variable | Default |
|---|---|
| `HF_TOKEN` | — (AI features report "not configured" without it) |
| `AI_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` |
| `AI_BASE_URL` | `https://router.huggingface.co/v1/chat/completions` |
| `AI_TIMEOUT` | `45` |

The token needs **Make calls to Inference Providers** permission. Tokens created
before Inference Providers existed will return 401 even though they are valid.

Any OpenAI-compatible chat-completions endpoint works, so `AI_BASE_URL` can point
elsewhere without code changes. To see what Hugging Face currently serves:

```bash
curl https://router.huggingface.co/v1/models
```

### Schedules

| Variable | Default | Range |
|---|---|---|
| `QUIET_START` / `QUIET_END` | `22` / `7` | 0-23. Set equal to disable |
| `BRIEFING_ENABLED` / `BRIEFING_HOUR` | `1` / `7` | |
| `WINDDOWN_ENABLED` / `WINDDOWN_HOUR` | `1` / `21` | |
| `DIGEST_ENABLED` / `DIGEST_DAY` / `DIGEST_HOUR` | `1` / `0` / `19` | Day 0 = Sunday |
| `NUDGE_ENABLED` / `NUDGE_AFTER_MINUTES` | `1` / `30` | |
| `BACKUP_ENABLED` / `BACKUP_HOUR` / `BACKUP_KEEP` | `1` / `3` / `14` | |
| `FOCUS_DEFAULT` / `FOCUS_MAX` | `25` / `180` | minutes |

Scheduling a briefing, wind-down or digest **inside** quiet hours would silently
suppress it, so the bot warns you at startup if you do.

### Insight thresholds

| Variable | Default |
|---|---|
| `INSIGHT_COOLDOWN_DAYS` | `7` |
| `BALANCE_WINDOW_DAYS` / `BALANCE_MIN_TASKS` / `BALANCE_THRESHOLD` | `14` / `8` / `60` |
| `BURNOUT_WINDOW_DAYS` / `BURNOUT_MIN_RATINGS` / `BURNOUT_THRESHOLD` | `7` / `4` / `2.5` |
| `NEGLECT_DAYS` / `NEGLECT_CATEGORIES` | `10` / `family,health` |

Every numeric variable is clamped to a sane range and falls back to its default
if unparseable, so a typo degrades rather than crashes.

Per-user toggles set through `/settings` override the enabled/disabled defaults
above. Thresholds are environment-only.

---

## Deploying on Railway

1. **New Project → Deploy from GitHub**, pick this repo. Railpack detects Python
   and reads the `worker` process from the `Procfile`.

2. **Attach a volume.** Service → Variables → **+ New Volume**, mount path:

   ```
   /data
   ```

   Do not mount at `/app` — that is where the build places your code, and a
   volume there will shadow it.

3. **Set variables:**

   ```
   BOT_TOKEN = <from @BotFather>
   DATA_DIR  = /data
   BOT_TZ    = Asia/Kuala_Lumpur
   HF_TOKEN  = <optional, for AI features>
   ```

4. Deploy. A healthy startup looks like:

   ```
   [init] Backup directory ready: /data/backups
   [init] Morning briefing at 07:00 Asia/Kuala_Lumpur
   [init] Evening wind-down at 21:00 Asia/Kuala_Lumpur
   [init] Backup at 03:00 Asia/Kuala_Lumpur, keeping 14
   [init] Weekly digest scheduled for Sunday 19:00 Asia/Kuala_Lumpur
   [init] Quiet hours default: 22:00-07:00 (reminders exempt)
   [init] LifeBalance Bot running (tz=Asia/Kuala_Lumpur, data=/data/user_data.json)
   ```

   If that last line reads `data=./user_data.json`, `DATA_DIR` is not being
   picked up and your data is still ephemeral.

The bot uses long polling, so it needs no public URL or health check. It runs as
a `worker`, not a `web` service.

---

## Data and backups

Everything lives in one JSON file at `DATA_DIR/user_data.json`, written
atomically via a temp file and `os.replace` so an interrupted write cannot
corrupt it.

The daily backup job writes timestamped copies to `DATA_DIR/backups/` and prunes
to the newest `BACKUP_KEEP`. The file is only kilobytes, so retention costs
essentially nothing.

To restore, stop the service, copy a snapshot over `user_data.json`, and restart:

```bash
cp /data/backups/user_data_20260904_030000.json /data/user_data.json
```

`user_data.json` and `backups/` are gitignored — they contain personal content
and must never be committed.

---

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Create a `.env` file (gitignored):

```
BOT_TOKEN=...
BOT_TZ=Asia/Kuala_Lumpur
DATA_DIR=./local-data
HF_TOKEN=...
```

Then:

```bash
python lifebalance_bot.py
```

Only one instance may poll a given bot token at a time. Running locally while
Railway is live will cause both to fight over updates — stop the Railway service
or use a second bot token for development.

---

## Notes for maintainers

**Do not pin `httpx`, `httpcore` or `anyio` in `requirements.txt`.**
`python-telegram-bot` pins its own compatible versions. Adding manual pins
previously produced an unresolvable conflict (`httpcore<1.0.0` against
`httpx 0.25.2`, which requires `httpcore==1.*`) and broke the build outright.

**Python is pinned in `.python-version`.** Leaving it unpinned let the builder
default drift to 3.13, which PTB 20.7 and APScheduler 3.10.4 predate.

**`tzdata` is an explicit dependency** because `zoneinfo` has no timezone
database on slim Linux images.

**Jobs must not hold data across an await.** `load_data` and `save_data` are
synchronous, so a read-modify-write with no await between is atomic on the event
loop. Awaiting a send in the middle is not: a concurrent handler write in that
window gets silently overwritten. Scheduled jobs therefore collect under
`_data_lock`, send outside it, then re-load and mark delivery under the lock
again. Follow that pattern for any new job.

**`callback_data` is capped at 64 bytes.** Callbacks are namespaced —
`t:` tasks, `nav:` navigation, `dash:` dashboards, `rate:` ratings, `rf:`
reflection, `set:` settings, `roll:` rollover, `focus:` timer. Dispatch on the
namespace; never assume a trailing integer.

**All user text is HTML-escaped** before interpolation into messages. A task
containing `&` or `<` will otherwise cause Telegram to reject the send.

**PTB maps `run_daily(days=...)` 0-6 to Sunday-Saturday**, changed from
Monday-Sunday in v20. Scheduled times must carry explicit `tzinfo` or they are
treated as UTC.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Tasks vanish after deploy | `DATA_DIR` unset or no volume attached |
| Reminders at the wrong hour | `BOT_TZ` unset, so times are UTC |
| Briefing or digest never arrives | Scheduled inside quiet hours — check startup warnings — or toggled off in `/settings` |
| `AI unavailable - the API token is missing or invalid` | `HF_TOKEN` lacks Inference Providers permission |
| `AI unavailable - the account is out of inference credits` | Free tier exhausted; resets monthly |
| `model '...' is not served` | Pick another from `/v1/models` and set `AI_MODEL` |
| `Could not reach ...` | `AI_BASE_URL` host is wrong or unreachable |
| Nudges silent late at night | Working as designed; quiet hours |
| Insights never appear | Below threshold. They stay silent on purpose until there is enough data |

---

## License

See [LICENSE](LICENSE).
