"""LifeBalance Bot - a friendly planner for work, family, and you.

Storage note: user data lives in DATA_DIR, which MUST point at a Railway
Volume mount path in production. The container filesystem is ephemeral, so
writing to the repo directory means every redeploy wipes all user data.

Time note: all datetimes are timezone-aware, anchored to BOT_TZ. Legacy
records stored as naive ISO strings are interpreted as BOT_TZ on read.
"""

import asyncio
import datetime
import json
import os
import random
import re
from html import escape
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

DATA_DIR = os.getenv("DATA_DIR", ".")
DATA_FILE = os.path.join(DATA_DIR, "user_data.json")

_TZ_NAME = os.getenv("BOT_TZ") or os.getenv("TZ") or "UTC"
try:
    TZ = ZoneInfo(_TZ_NAME)
except Exception:
    print(f"[warn] Unknown timezone {_TZ_NAME!r}, falling back to UTC.")
    _TZ_NAME = "UTC"
    TZ = ZoneInfo("UTC")

CATEGORIES = [
    "family", "trading", "marketing", "content",
    "learning", "health", "admin", "general",
]

CATEGORY_EMOJI = {
    "family": "\U0001F46A",
    "trading": "\U0001F4B9",
    "marketing": "\U0001F4E3",
    "content": "\u270D\uFE0F",
    "learning": "\U0001F4DA",
    "health": "\U0001F3C3",
    "admin": "\U0001F4CE",
    "general": "\U0001F4CC",
}

SNOOZE_MINUTES = 30
REMINDER_LEAD_MINUTES = 10
MAX_BUTTON_LABEL = 32


def _env_int(name, default, low, high):
    """Read an int env var, clamped, falling back on anything unparseable."""
    try:
        return max(low, min(high, int(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        print(f"[warn] {name} is not a number, using {default}.")
        return default


def _env_float(name, default, low, high):
    try:
        return max(low, min(high, float(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        print(f"[warn] {name} is not a number, using {default}.")
        return default


def _env_bool(name, default=True):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def _env_list(name, default):
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


# Weekly digest schedule. PTB maps days 0-6 to sunday-saturday (it was
# monday-sunday before v20), so 0 really is Sunday here.
DIGEST_ENABLED = _env_bool("DIGEST_ENABLED", True)
DIGEST_DAY = _env_int("DIGEST_DAY", 0, 0, 6)
DIGEST_HOUR = _env_int("DIGEST_HOUR", 19, 0, 23)
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

# Quiet hours gate every bot-initiated message. Task reminders you scheduled
# yourself are deliberately exempt.
QUIET_START = _env_int("QUIET_START", 22, 0, 23)
QUIET_END = _env_int("QUIET_END", 7, 0, 23)

BRIEFING_ENABLED = _env_bool("BRIEFING_ENABLED", True)
BRIEFING_HOUR = _env_int("BRIEFING_HOUR", 7, 0, 23)

WINDDOWN_ENABLED = _env_bool("WINDDOWN_ENABLED", True)
WINDDOWN_HOUR = _env_int("WINDDOWN_HOUR", 21, 0, 23)

NUDGE_ENABLED = _env_bool("NUDGE_ENABLED", True)
NUDGE_AFTER_MINUTES = _env_int("NUDGE_AFTER_MINUTES", 30, 5, 720)

BACKUP_ENABLED = _env_bool("BACKUP_ENABLED", True)
BACKUP_HOUR = _env_int("BACKUP_HOUR", 3, 0, 23)
BACKUP_KEEP = _env_int("BACKUP_KEEP", 14, 1, 365)

FOCUS_DEFAULT = _env_int("FOCUS_DEFAULT", 25, 1, 480)
FOCUS_MAX = _env_int("FOCUS_MAX", 180, 1, 480)

# Insight thresholds. Each insight stays silent until it has enough data to
# say something true, and then goes quiet for a cooldown period.
INSIGHT_COOLDOWN_DAYS = _env_int("INSIGHT_COOLDOWN_DAYS", 7, 1, 90)
BALANCE_WINDOW_DAYS = _env_int("BALANCE_WINDOW_DAYS", 14, 3, 90)
BALANCE_MIN_TASKS = _env_int("BALANCE_MIN_TASKS", 8, 2, 200)
BALANCE_THRESHOLD = _env_int("BALANCE_THRESHOLD", 60, 30, 100)
BURNOUT_WINDOW_DAYS = _env_int("BURNOUT_WINDOW_DAYS", 7, 2, 60)
BURNOUT_MIN_RATINGS = _env_int("BURNOUT_MIN_RATINGS", 4, 2, 50)
BURNOUT_THRESHOLD = _env_float("BURNOUT_THRESHOLD", 2.5, 1.0, 5.0)
NEGLECT_DAYS = _env_int("NEGLECT_DAYS", 10, 2, 120)
NEGLECT_CATEGORIES = _env_list("NEGLECT_CATEGORIES", ("family", "health"))

# Per-user overrides live in user["settings"]; these are the defaults.
DEFAULT_SETTINGS = {
    "quiet_start": QUIET_START,
    "quiet_end": QUIET_END,
    "briefing": BRIEFING_ENABLED,
    "winddown": WINDDOWN_ENABLED,
    "nudges": NUDGE_ENABLED,
    "insights": True,
    "digest": DIGEST_ENABLED,
}

SETTING_LABELS = (
    ("briefing", "\U0001F305 Morning briefing"),
    ("winddown", "\U0001F319 Evening wind-down"),
    ("nudges", "\u23F0 Overdue nudges"),
    ("insights", "\U0001F4A1 Balance insights"),
    ("digest", "\U0001F4CA Weekly digest"),
)

# --------------------------------------------------------------------------
# TIME HELPERS
# --------------------------------------------------------------------------


def now():
    """Current time, timezone-aware in BOT_TZ."""
    return datetime.datetime.now(TZ)


def parse_dt(value):
    """Parse a stored ISO timestamp, treating naive values as BOT_TZ."""
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def fmt_time(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def _parse_clock(token, base):
    """Parse '3pm', '3:30pm', '15:00' against a base date. None if no match."""
    token = token.lower().strip()

    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)", token)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        meridiem = m.group(3)
        if hour == 12:
            hour = 0 if meridiem == "am" else 12
        elif meridiem == "pm":
            hour += 12
        if hour > 23 or minute > 59:
            return None
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)

    m = re.fullmatch(r"(\d{1,2}):(\d{2})", token)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if hour > 23 or minute > 59:
            return None
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return None


def parse_when(tokens):
    """Read a time off the END of `tokens`.

    Returns (datetime, tokens_consumed). (None, 0) when nothing parses.
    Handles: '3pm', '3:30pm', '15:00', 'tomorrow', 'tomorrow 9am'.
    """
    if not tokens:
        return None, 0

    current = now()
    last = tokens[-1].lower()

    if len(tokens) >= 2 and tokens[-2].lower() == "tomorrow":
        target = _parse_clock(last, current + datetime.timedelta(days=1))
        if target:
            return target, 2

    if last == "tomorrow":
        target = current + datetime.timedelta(days=1)
        return target.replace(hour=9, minute=0, second=0, microsecond=0), 1

    target = _parse_clock(last, current)
    if target:
        if target < current:
            target += datetime.timedelta(days=1)
        return target, 1

    return None, 0


# --------------------------------------------------------------------------
# STORAGE
# --------------------------------------------------------------------------


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[error] Could not read {DATA_FILE}: {exc}. Starting empty.")
        return {}


def save_data(data):
    """Write atomically so a crash mid-write cannot corrupt the file."""
    if DATA_DIR and DATA_DIR != ".":
        os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)


def ensure_user(data, user_id):
    """Guarantee every key this bot reads exists. Backward compatible.

    Previously different commands created user records with different keys,
    so /reflect-then-/add raised KeyError on 'reminders'.
    """
    user = data.setdefault(user_id, {})
    user.setdefault("tasks", [])
    user.setdefault("reminders", [])
    user.setdefault("reflections", [])
    user.setdefault("insight_cooldowns", {})
    if "next_id" not in user:
        highest = max((t.get("id", 0) for t in user["tasks"]), default=0)
        user["next_id"] = highest + 1
    settings = user.setdefault("settings", {})
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)
    return user


def find_task(user, task_id):
    for task in user["tasks"]:
        if task.get("id") == task_id:
            return task
    return None


# --------------------------------------------------------------------------
# CONCURRENCY
# --------------------------------------------------------------------------

# load_data/save_data are synchronous, so a read-modify-write with no await
# in between is already atomic on the event loop. The danger is a job that
# loads data, awaits a send, then saves: a handler running in that window has
# its write silently overwritten. Jobs therefore use a three-phase pattern -
# collect under the lock, send outside it, then re-load and mark under the
# lock again - and every mutation goes through this lock.
_data_lock = asyncio.Lock()


async def read_data():
    async with _data_lock:
        return load_data()


async def mutate_data(mutator):
    """Atomically load, apply mutator(data), save. mutator must not await."""
    async with _data_lock:
        data = load_data()
        result = mutator(data)
        save_data(data)
        return result


# --------------------------------------------------------------------------
# QUIET HOURS AND OUTBOUND MESSAGES
# --------------------------------------------------------------------------


def in_quiet_hours(dt, start, end):
    """True when dt falls inside the quiet window.

    The window normally wraps midnight (22 -> 7), which is the usual source
    of off-by-one bugs here, so both orientations are handled explicitly.
    """
    if start == end:
        return False
    hour = dt.hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def user_settings(user):
    settings = dict(DEFAULT_SETTINGS)
    settings.update(user.get("settings") or {})
    return settings


async def send_proactive(bot, user_id, text, markup=None, *, kind, settings,
                         ignore_quiet=False):
    """Single chokepoint for every bot-initiated message.

    Returns True only if Telegram accepted it, so callers can decide whether
    to mark the item as delivered.
    """
    if kind and not settings.get(kind, True):
        return False
    if not ignore_quiet and in_quiet_hours(
        now(), settings.get("quiet_start", QUIET_START),
        settings.get("quiet_end", QUIET_END)
    ):
        return False
    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
        return True
    except Exception as exc:
        print(f"[warn] {kind or 'message'} to {user_id} failed: {exc}")
        return False


# --------------------------------------------------------------------------
# UI HELPERS
# --------------------------------------------------------------------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["\U0001F4C5 Today", "\u2795 Add task"],
        ["\U0001F4CA Reflect", "\U0001F9E0 Suggest"],
        ["\U0001F3AF Focus", "\u2699\uFE0F Settings"],
        ["\u2753 Help"],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Tap an action or type a command",
)


def bar(value, total, width=10):
    """Text progress bar. Telegram has no native progress widget."""
    if total <= 0:
        return "\u2591" * width
    filled = max(0, min(width, round(width * value / total)))
    return "\u2588" * filled + "\u2591" * (width - filled)


def truncate(text, limit=MAX_BUTTON_LABEL):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def cat_emoji(category):
    return CATEGORY_EMOJI.get(category, CATEGORY_EMOJI["general"])


def rating_keyboard(task_id):
    """Row of 1-5 buttons. Simulates a slider; Telegram has no real one."""
    digits = ["1\uFE0F\u20E3", "2\uFE0F\u20E3", "3\uFE0F\u20E3", "4\uFE0F\u20E3", "5\uFE0F\u20E3"]
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(d, callback_data=f"rate:{task_id}:{i}")
          for i, d in enumerate(digits, start=1)]]
    )


def today_view(user):
    """Build the today list. Returns (html_text, markup)."""
    today = now().date()
    rows = []
    for task in user["tasks"]:
        try:
            when = parse_dt(task["time"])
        except (ValueError, KeyError):
            continue
        if when.date() == today:
            rows.append((task, when))

    rows.sort(key=lambda pair: pair[1])

    if not rows:
        text = (
            "\U0001F33F <b>Today</b>\n\n"
            "Nothing scheduled. Enjoy the freedom.\n\n"
            "Add something with <code>/add Call mom 7pm family</code>"
        )
        return text, InlineKeyboardMarkup(
            [[InlineKeyboardButton("\U0001F504 Refresh", callback_data="nav:today")]]
        )

    done_count = sum(1 for task, _ in rows if task.get("done"))
    lines = [
        f"\U0001F4C5 <b>Today</b>  \u00B7  {now().strftime('%a %d %b')}",
        f"<code>{bar(done_count, len(rows))}</code>  {done_count}/{len(rows)} done",
    ]
    streak = streak_line(user)
    if streak:
        lines.append(streak)
    lines.append("")

    buttons = []
    for task, when in rows:
        category = task.get("category", "general")
        mark = "\u2705" if task.get("done") else "\u23F3"
        lines.append(
            f"{mark} <b>{fmt_time(when)}</b> \u2014 {escape(task['text'])} "
            f"{cat_emoji(category)}"
        )
        if not task.get("done"):
            buttons.append([
                InlineKeyboardButton(
                    f"{cat_emoji(category)} {truncate(task['text'], 26)}",
                    callback_data=f"t:view:{task['id']}",
                )
            ])

    if buttons:
        lines.append("")
        lines.append("<i>Tap a task to act on it.</i>")

    buttons.append([
        InlineKeyboardButton("\U0001F504 Refresh", callback_data="nav:today"),
        InlineKeyboardButton("\U0001F4CA Week", callback_data="dash:week"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)


def task_view(task):
    """Detail view for one task. Returns (html_text, markup)."""
    when = parse_dt(task["time"])
    category = task.get("category", "general")
    status = "\u2705 Done" if task.get("done") else "\u23F3 Pending"

    text = (
        f"{cat_emoji(category)} <b>{escape(task['text'])}</b>\n\n"
        f"\U0001F551 {fmt_time(when)} on {when.strftime('%a %d %b')}\n"
        f"\U0001F3F7 {escape(category)}\n"
        f"\U0001F4CD {status}"
    )

    if task.get("done"):
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")]]
        )
        return text, markup

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\u2705 Done", callback_data=f"t:done:{task['id']}"),
            InlineKeyboardButton(
                f"\U0001F634 +{SNOOZE_MINUTES}m", callback_data=f"t:snz:{task['id']}"
            ),
        ],
        [
            InlineKeyboardButton("\U0001F9E0 Coach me", callback_data=f"t:coach:{task['id']}"),
            InlineKeyboardButton("\u270F\uFE0F Reschedule", callback_data=f"t:resch:{task['id']}"),
        ],
        [InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")],
    ])
    return text, markup


def week_view(user):
    """Weekly stats with text progress bars. Returns (html_text, markup)."""
    cutoff = now() - datetime.timedelta(days=7)
    recent = []
    for task in user["tasks"]:
        stamp = task.get("created") or task.get("time")
        if not stamp:
            continue
        try:
            if parse_dt(stamp) > cutoff:
                recent.append(task)
        except ValueError:
            continue

    if not recent:
        text = (
            "\U0001F4CA <b>This Week</b>\n\n"
            "No activity in the last 7 days yet."
        )
        return text, InlineKeyboardMarkup(
            [[InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")]]
        )

    done = [t for t in recent if t.get("done")]
    lines = [
        f"\U0001F4CA <b>This Week</b>  \u00B7  {now().strftime('%a %d %b')}",
        f"<code>{bar(len(done), len(recent))}</code>  {len(done)}/{len(recent)} completed",
    ]
    streak = streak_line(user)
    if streak:
        lines.append(streak)
    lines.append("")

    totals = {}
    for task in recent:
        category = task.get("category", "general")
        bucket = totals.setdefault(category, [0, 0])
        bucket[1] += 1
        if task.get("done"):
            bucket[0] += 1

    for category, (completed, total) in sorted(
        totals.items(), key=lambda kv: -kv[1][1]
    ):
        label = f"{cat_emoji(category)} {category[:9].ljust(9)}"
        lines.append(f"{label} <code>{bar(completed, total, 8)}</code> {completed}/{total}")

    ratings = [
        int(r["rating"])
        for r in user.get("reflections", [])
        if str(r.get("rating", "")).isdigit()
    ]
    if ratings:
        avg = sum(ratings) / len(ratings)
        lines.append("")
        lines.append(f"\u26A1 Avg energy: <b>{avg:.1f}</b>/5 over {len(ratings)} reflections")

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001F504 Refresh", callback_data="dash:week")],
        [InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")],
    ])
    return "\n".join(lines), markup


async def safe_edit(query, text, markup):
    """Edit a message, tolerating Telegram's 'not modified' error."""
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


# --------------------------------------------------------------------------
# AI HELPERS
# --------------------------------------------------------------------------

# api-inference.huggingface.co was retired and no longer has a DNS A record,
# which surfaced as "No address associated with hostname". Hugging Face now
# serves an OpenAI-compatible endpoint through Inference Providers. Both the
# URL and the model are env-overridable so a future migration needs no code
# change.
AI_BASE_URL = os.getenv(
    "AI_BASE_URL", "https://router.huggingface.co/v1/chat/completions"
)
AI_MODEL = (
    os.getenv("AI_MODEL")
    or os.getenv("DEFAULT_MODEL")
    or "meta-llama/Llama-3.1-8B-Instruct"
)
AI_TOKEN = os.getenv("HF_TOKEN") or os.getenv("AI_TOKEN")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "45"))


class AIError(RuntimeError):
    """An AI call failed in a way worth showing the user verbatim."""


def _describe_http_error(response):
    detail = ""
    try:
        body = response.json()
        error = body.get("error")
        if isinstance(error, dict):
            detail = error.get("message", "")
        elif isinstance(error, str):
            detail = error
    except ValueError:
        detail = (response.text or "")[:200]

    code = response.status_code
    if code == 401:
        return "the API token is missing or invalid (check HF_TOKEN)."
    if code == 402:
        return "the account is out of inference credits."
    if code == 403:
        return f"access to '{AI_MODEL}' is not permitted with this token."
    if code == 404:
        return (
            f"model '{AI_MODEL}' is not served. Set AI_MODEL to a supported "
            "one, e.g. meta-llama/Llama-3.1-8B-Instruct"
        )
    if code == 429:
        return "rate limited. Give it a minute."
    return f"HTTP {code}{' - ' + detail if detail else ''}"


def _chat_blocking(system, user, max_tokens):
    response = requests.post(
        AI_BASE_URL,
        headers={
            "Authorization": f"Bearer {AI_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        },
        timeout=AI_TIMEOUT,
    )

    if response.status_code >= 400:
        raise AIError(_describe_http_error(response))

    try:
        body = response.json()
    except ValueError:
        raise AIError("the response was not valid JSON.")

    choices = body.get("choices") or []
    if not choices:
        raise AIError("the model returned no choices.")

    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise AIError("the model returned an empty message.")
    return content


async def ask_ai(system, user, max_tokens, fallback):
    """Chat completion, run off the event loop.

    requests.post inside an async handler froze the whole bot for the
    duration of every AI request, so it goes through a worker thread.
    """
    if not AI_TOKEN:
        return "AI is not configured \u2014 set HF_TOKEN in your Railway variables."
    try:
        return await asyncio.to_thread(_chat_blocking, system, user, max_tokens)
    except AIError as exc:
        return f"AI unavailable \u2014 {exc}"
    except requests.exceptions.ConnectionError:
        host = AI_BASE_URL.split("/")[2] if "//" in AI_BASE_URL else AI_BASE_URL
        return f"Could not reach {host}. Check AI_BASE_URL."
    except requests.exceptions.Timeout:
        return f"The model took longer than {AI_TIMEOUT}s. Try again."
    except Exception as exc:
        return f"AI error ({type(exc).__name__}): {exc}" or fallback


SUGGEST_SYSTEM = (
    "You are a wise, warm life coach helping someone balance work and family. "
    "Reply with ONE specific, actionable suggestion in 2 sentences or fewer. "
    "No preamble, no lists, no markdown."
)

PLAN_SYSTEM = (
    "You are a practical project planner. Break the goal into 3-5 concrete "
    "subtasks, each under 90 minutes, each with a realistic time estimate. "
    "Then give one likely blocker with a prep step. Be concise and practical, "
    "not idealistic. If the goal is too big, give only the first step. "
    "Use plain text with simple numbered lines, no markdown."
)

COACH_SYSTEM = (
    "You are a supportive task coach. Give ONE specific, actionable tip to "
    "help the person start or push through. Under 2 sentences. Warm and "
    "practical. No preamble, no markdown."
)


def build_suggestion_prompt(ctx):
    return (
        f"Name: {ctx['name']}\n"
        f"Unfinished tasks: {', '.join(ctx['recent_tasks'])}\n"
        f"Energy level (1-5): {ctx['energy']}\n"
        f"Time of day: {ctx['time_of_day']}\n"
        f"Priorities: {', '.join(ctx['priorities'])}\n\n"
        "Suggest one task for the next 2-4 hours. Respect their energy level: "
        "do not suggest deep work at low energy. Include a small element of "
        "enjoyment. Keep it under 90 minutes."
    )


def build_planning_prompt(goal, category="general"):
    return f'Goal: "{goal}"\nCategory: {category}'


def build_coach_prompt(task_text):
    return f'The task is: "{task_text}"'


# --------------------------------------------------------------------------
# REFLECTION PROMPTS
# --------------------------------------------------------------------------

REFLECTION_PROMPTS = {
    "family": [
        "What's 1 meaningful moment you shared with your family this week?",
        "How did you balance work time with family time? What could be better?",
        "What's 1 family activity you'd like to do more of next week?",
    ],
    "trading": [
        "What's 1 trading lesson you learned this week?",
        "Did you stick to your trading rules? If not, what got in the way?",
        "What's 1 adjustment you'd make to your approach next week?",
    ],
    "marketing": [
        "What's 1 piece of content you created that you're proud of?",
        "Which channel gave you the best engagement this week?",
        "What's 1 marketing experiment you want to try next week?",
    ],
    "balance": [
        "On a scale of 1-10, how was your work-life balance this week?",
        "What's 1 thing you sacrificed for work that you wish you hadn't?",
        "What's 1 non-work activity that recharged you?",
    ],
}


# --------------------------------------------------------------------------
# STREAKS AND INSIGHTS
# --------------------------------------------------------------------------


def _completed_at(task):
    stamp = task.get("completed_at")
    if not stamp:
        return None
    try:
        return parse_dt(stamp)
    except ValueError:
        return None


def completion_dates(user):
    dates = set()
    for task in user.get("tasks", []):
        when = _completed_at(task)
        if when:
            dates.add(when.date())
    return dates


def current_streak(user):
    """Consecutive days ending today, or yesterday if today is still open.

    Anchoring on yesterday matters: without it the streak would read 0 every
    morning until the first task of the day was completed.
    """
    dates = completion_dates(user)
    if not dates:
        return 0

    today = now().date()
    yesterday = today - datetime.timedelta(days=1)
    if today in dates:
        cursor = today
    elif yesterday in dates:
        cursor = yesterday
    else:
        return 0

    streak = 0
    while cursor in dates:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak


def streak_line(user):
    streak = current_streak(user)
    if streak <= 0:
        return ""
    flame = "\U0001F525" if streak >= 3 else "\u2728"
    day_word = "day" if streak == 1 else "days"
    return f"{flame} <b>{streak}</b> {day_word} in a row"


def _recent_ratings(user, days):
    cutoff = now() - datetime.timedelta(days=days)
    out = []
    for reflection in user.get("reflections", []):
        rating = reflection.get("rating")
        if not str(rating).isdigit():
            continue
        stamp = reflection.get("timestamp")
        if not stamp:
            continue
        try:
            if parse_dt(stamp) >= cutoff:
                out.append(int(rating))
        except ValueError:
            continue
    return out


def _last_activity(user, category):
    """Most recent created-or-completed time for a category, or None."""
    latest = None
    for task in user.get("tasks", []):
        if task.get("category", "general") != category:
            continue
        for key in ("completed_at", "created", "time"):
            stamp = task.get(key)
            if not stamp:
                continue
            try:
                when = parse_dt(stamp)
            except ValueError:
                continue
            if latest is None or when > latest:
                latest = when
    return latest


def compute_insights(user):
    """Return [(key, text)] of things worth telling the user.

    Each check refuses to speak without a minimum sample, so a brand new user
    is never lectured on the basis of two tasks.
    """
    insights = []
    current = now()

    # 1. Balance: is one category crowding out everything else?
    cutoff = current - datetime.timedelta(days=BALANCE_WINDOW_DAYS)
    done = [
        task for task in user.get("tasks", [])
        if task.get("done") and (_completed_at(task) or cutoff) >= cutoff
    ]
    if len(done) >= BALANCE_MIN_TASKS:
        counts = {}
        for task in done:
            category = task.get("category", "general")
            counts[category] = counts.get(category, 0) + 1
        top, top_n = max(counts.items(), key=lambda kv: kv[1])
        share = round(100 * top_n / len(done))
        if share >= BALANCE_THRESHOLD:
            insights.append((
                "balance",
                f"{cat_emoji(top)} <b>{share}%</b> of your last {len(done)} "
                f"completed tasks were <b>{escape(top)}</b>. Worth protecting "
                "time for something else this week?",
            ))

    # 2. Burnout: is energy trending low?
    ratings = _recent_ratings(user, BURNOUT_WINDOW_DAYS)
    if len(ratings) >= BURNOUT_MIN_RATINGS:
        average = sum(ratings) / len(ratings)
        if average < BURNOUT_THRESHOLD:
            insights.append((
                "burnout",
                f"\U0001FAAB Your energy averaged <b>{average:.1f}</b>/5 across "
                f"{len(ratings)} tasks this week. That is low \u2014 consider a "
                "lighter week, or fewer commitments.",
            ))

    # 3. Neglect: has a category the user cares about gone quiet?
    for category in NEGLECT_CATEGORIES:
        last = _last_activity(user, category)
        if last is None:
            continue
        days = (current - last).days
        if days >= NEGLECT_DAYS:
            insights.append((
                f"neglect:{category}",
                f"{cat_emoji(category)} Nothing logged under "
                f"<b>{escape(category)}</b> for <b>{days}</b> days.",
            ))

    return insights


def due_insights(user):
    """Filter computed insights by their per-key cooldown."""
    cooldowns = user.get("insight_cooldowns") or {}
    current = now()
    fresh = []
    for key, text in compute_insights(user):
        stamp = cooldowns.get(key)
        if stamp:
            try:
                if (current - parse_dt(stamp)).days < INSIGHT_COOLDOWN_DAYS:
                    continue
            except ValueError:
                pass
        fresh.append((key, text))
    return fresh


def mark_insights_sent(user, keys):
    cooldowns = user.setdefault("insight_cooldowns", {})
    stamp = now().isoformat()
    for key in keys:
        cooldowns[key] = stamp


def insight_block(insights):
    if not insights:
        return ""
    lines = ["", "\u2500" * 10, "\U0001F4A1 <b>Worth noticing</b>", ""]
    lines.extend(text for _, text in insights)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# COMMANDS
# --------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {escape(user.first_name)}! \U0001F44B I'm <b>LifeBalance</b> \u2014 "
        "your planner for work, family, and YOU.\n\n"
        "Use the buttons below, or these commands:\n"
        "\u2022 <code>/add Call mom 7pm family</code> \u2014 add a task\n"
        "\u2022 /today \u2014 your day, with tap-to-act buttons\n"
        "\u2022 /week \u2014 weekly progress\n"
        "\u2022 /suggest \u2014 AI task suggestion\n"
        "\u2022 /plan &lt;goal&gt; \u2014 break a goal into steps\n"
        "\u2022 /reflect \u2014 weekly reflection\n"
        "\u2022 /help \u2014 all commands\n\n"
        f"\U0001F551 Times use <b>{escape(_TZ_NAME)}</b>.\n\n"
        "This is about <i>harmony</i>, not perfection. \U0001F49B",
        reply_markup=MAIN_KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quiet = (
        "off" if QUIET_START == QUIET_END
        else f"{QUIET_START:02d}:00\u2013{QUIET_END:02d}:00"
    )
    await update.message.reply_html(
        "<b>Tasks</b>\n"
        "<code>/add &lt;task&gt; &lt;time&gt; [category]</code>\n"
        "   Times: <code>3pm</code>, <code>3:30pm</code>, <code>15:00</code>, "
        "<code>tomorrow</code>, <code>tomorrow 9am</code>\n"
        "/today \u2014 today's tasks with buttons\n"
        "/week \u2014 weekly progress and streak\n"
        "/done &lt;id&gt; \u00B7 /snooze &lt;id&gt; \u00B7 "
        "/reschedule &lt;id&gt; &lt;time&gt;\n\n"
        "<b>Focus</b>\n"
        "<code>/focus 25</code> \u2014 timer, pings when done\n"
        "<code>/focus 50 deep work</code> \u2014 with a label\n"
        "<code>/focus stop</code> \u2014 cancel\n\n"
        "<b>AI</b>\n"
        "/suggest \u2014 task suggestion\n"
        "/plan &lt;goal&gt; \u2014 break a goal into steps\n"
        "/assist &lt;id&gt; \u2014 coaching tip\n\n"
        "<b>Automatic</b>\n"
        f"\U0001F305 Morning briefing \u2014 {BRIEFING_HOUR:02d}:00\n"
        f"\U0001F319 Evening wind-down \u2014 {WINDDOWN_HOUR:02d}:00\n"
        f"\U0001F4CA Weekly digest \u2014 {DAY_NAMES[DIGEST_DAY]} "
        f"{DIGEST_HOUR:02d}:00\n"
        f"\U0001F507 Quiet hours \u2014 {quiet}\n"
        "Preview any of them: /brief \u00B7 /winddown \u00B7 /digest\n"
        "/settings \u2014 toggle each one\n\n"
        f"Categories: {', '.join(CATEGORIES)}\n"
        f"Timezone: <b>{escape(_TZ_NAME)}</b>",
        reply_markup=MAIN_KEYBOARD,
    )


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user = ensure_user(data, user_id)

    tokens = list(context.args or [])
    if len(tokens) < 2:
        await update.message.reply_html(
            "<b>Usage:</b> <code>/add &lt;task&gt; &lt;time&gt; [category]</code>\n\n"
            "Examples:\n"
            "<code>/add Pick up kids 3:30pm family</code>\n"
            "<code>/add Review charts tomorrow 9am trading</code>\n\n"
            f"Categories: {', '.join(CATEGORIES)}"
        )
        return

    category = "general"
    if len(tokens) >= 3 and tokens[-1].lower() in CATEGORIES:
        category = tokens.pop().lower()

    target, consumed = parse_when(tokens)
    if not target:
        await update.message.reply_html(
            "I couldn't read that time. Try <code>3pm</code>, <code>3:30pm</code>, "
            "<code>15:00</code>, <code>tomorrow</code>, or <code>tomorrow 9am</code>."
        )
        return

    task_text = " ".join(tokens[: len(tokens) - consumed]).strip()
    if not task_text:
        await update.message.reply_text("The task needs a name. Example: /add Call mom 7pm")
        return

    task_id = user["next_id"]
    user["next_id"] += 1
    user["tasks"].append({
        "id": task_id,
        "text": task_text,
        "time": target.isoformat(),
        "done": False,
        "created": now().isoformat(),
        "category": category,
    })

    reminder_at = target - datetime.timedelta(minutes=REMINDER_LEAD_MINUTES)
    reminder_note = ""
    if reminder_at > now():
        user["reminders"].append({
            "task_id": task_id,
            "time": reminder_at.isoformat(),
            "sent": False,
        })
        reminder_note = f"\nI'll nudge you {REMINDER_LEAD_MINUTES} mins before. \U0001F552"
    else:
        reminder_note = "\n<i>That's soon, so no advance reminder.</i>"

    save_data(data)

    await update.message.reply_html(
        f"\u2705 Added {cat_emoji(category)} <b>{escape(task_text)}</b>\n"
        f"\U0001F551 {fmt_time(target)} on {target.strftime('%a %d %b')}"
        f"{reminder_note}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001F4C5 View today", callback_data="nav:today"),
            InlineKeyboardButton("\u2705 Done now", callback_data=f"t:done:{task_id}"),
        ]]),
    )


async def show_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Previously built a message and never sent it, so /today did nothing."""
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    save_data(data)
    text, markup = today_view(user)
    await update.message.reply_html(text, reply_markup=markup)


async def show_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    save_data(data)
    text, markup = week_view(user)
    await update.message.reply_html(text, reply_markup=markup)


async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))

    try:
        task_id = int(context.args[0])
    except (IndexError, ValueError, TypeError):
        await update.message.reply_text("Usage: /done <task_id>  (see /today)")
        return

    task = find_task(user, task_id)
    if not task or task.get("done"):
        await update.message.reply_text("Task not found, or already done.")
        return

    task["done"] = True
    task["completed_at"] = now().isoformat()
    save_data(data)

    await update.message.reply_html(
        f"\U0001F389 Completed <b>{escape(task['text'])}</b>\n\n"
        "How energizing was it?  <i>(1 = draining, 5 = energizing)</i>",
        reply_markup=rating_keyboard(task_id),
    )


async def snooze_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))

    try:
        task_id = int(context.args[0])
    except (IndexError, ValueError, TypeError):
        await update.message.reply_text("Usage: /snooze <task_id>")
        return

    task = find_task(user, task_id)
    if not task or task.get("done"):
        await update.message.reply_text("Task not found, or already done.")
        return

    new_time = _apply_snooze(user, task)
    save_data(data)
    await update.message.reply_html(
        f"\U0001F634 Snoozed <b>{escape(task['text'])}</b> to {fmt_time(new_time)}"
    )


def _apply_snooze(user, task):
    new_time = parse_dt(task["time"]) + datetime.timedelta(minutes=SNOOZE_MINUTES)
    task["time"] = new_time.isoformat()
    for reminder in user["reminders"]:
        if reminder["task_id"] == task["id"]:
            reminder["time"] = (
                new_time - datetime.timedelta(minutes=REMINDER_LEAD_MINUTES)
            ).isoformat()
            reminder["sent"] = False
            break
    return new_time


async def reschedule_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))

    tokens = list(context.args or [])
    if len(tokens) < 2:
        await update.message.reply_text(
            "Usage: /reschedule <task_id> <new time>\nExample: /reschedule 3 tomorrow 2pm"
        )
        return

    try:
        task_id = int(tokens.pop(0))
    except ValueError:
        await update.message.reply_text("The task id must be a number. See /today.")
        return

    task = find_task(user, task_id)
    if not task:
        await update.message.reply_text("Task not found.")
        return

    target, _ = parse_when(tokens)
    if not target:
        await update.message.reply_html(
            "I couldn't read that time. Try <code>3pm</code>, <code>15:00</code>, "
            "or <code>tomorrow 9am</code>."
        )
        return

    task["time"] = target.isoformat()
    task["done"] = False

    reminder_at = target - datetime.timedelta(minutes=REMINDER_LEAD_MINUTES)
    for reminder in user["reminders"]:
        if reminder["task_id"] == task_id:
            reminder["time"] = reminder_at.isoformat()
            reminder["sent"] = False
            break
    else:
        if reminder_at > now():
            user["reminders"].append(
                {"task_id": task_id, "time": reminder_at.isoformat(), "sent": False}
            )

    save_data(data)
    await update.message.reply_html(
        f"\U0001F4C5 Rescheduled <b>{escape(task['text'])}</b> to "
        f"{fmt_time(target)} on {target.strftime('%a %d %b')}"
    )


async def ai_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))

    await update.effective_chat.send_action(ChatAction.TYPING)

    pending = [t["text"] for t in user["tasks"][-5:] if not t.get("done")]
    ratings = [
        int(r["rating"])
        for r in user.get("reflections", [])[-5:]
        if str(r.get("rating", "")).isdigit()
    ]
    energy = round(sum(ratings) / len(ratings)) if ratings else 3

    prompt = build_suggestion_prompt({
        "name": update.effective_user.first_name,
        "recent_tasks": pending or ["None recently"],
        "energy": energy,
        "time_of_day": now().strftime("%I %p"),
        "priorities": ["Work", "Family", "Health"],
    })

    suggestion = await ask_ai(
        SUGGEST_SYSTEM, prompt, 200, "Couldn't generate a suggestion."
    )
    await update.message.reply_html(
        f"\U0001F4A1 <b>Suggestion</b>  <i>(energy \u2248 {energy}/5)</i>\n\n"
        f"{escape(suggestion)}\n\n"
        "Like it? Add it with <code>/add &lt;task&gt; &lt;time&gt;</code>"
    )


async def plan_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tokens = list(context.args or [])
    if not tokens:
        await update.message.reply_html(
            "<b>Usage:</b> <code>/plan &lt;goal&gt; [category]</code>\n"
            "Example: <code>/plan Launch the new landing page marketing</code>"
        )
        return

    category = "general"
    if len(tokens) >= 2 and tokens[-1].lower() in CATEGORIES:
        category = tokens.pop().lower()
    goal = " ".join(tokens)

    await update.effective_chat.send_action(ChatAction.TYPING)
    plan = await ask_ai(
        PLAN_SYSTEM, build_planning_prompt(goal, category), 450, "Planning failed."
    )

    await update.message.reply_html(
        f"\U0001F9E0 <b>Plan: {escape(goal)}</b> {cat_emoji(category)}\n\n"
        f"{escape(plan)}\n\n"
        "Turn a step into a task with <code>/add &lt;step&gt; &lt;time&gt;</code>"
    )


async def assist_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))

    try:
        task_id = int(context.args[0])
    except (IndexError, ValueError, TypeError):
        await update.message.reply_text("Usage: /assist <task_id>  (see /today)")
        return

    task = find_task(user, task_id)
    if not task or task.get("done"):
        await update.message.reply_text("Task not found, or already done.")
        return

    await update.effective_chat.send_action(ChatAction.TYPING)
    tip = await ask_ai(
        COACH_SYSTEM,
        build_coach_prompt(task["text"]),
        120,
        "Try breaking it into smaller steps.",
    )
    await update.message.reply_html(
        f"\U0001F3AF <b>Coach tip</b> \u2014 {escape(task['text'])}\n\n{escape(tip)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\u2705 Done", callback_data=f"t:done:{task_id}"),
            InlineKeyboardButton("\U0001F4C5 Today", callback_data="nav:today"),
        ]]),
    )


async def weekly_reflect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    user["last_reflect"] = now().isoformat()
    save_data(data)

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001F46A Family", callback_data="rf:family"),
            InlineKeyboardButton("\U0001F4B9 Trading", callback_data="rf:trading"),
        ],
        [
            InlineKeyboardButton("\U0001F4E3 Marketing", callback_data="rf:marketing"),
            InlineKeyboardButton("\u2696\uFE0F Balance", callback_data="rf:balance"),
        ],
        [InlineKeyboardButton("\U0001F4CA Weekly dashboard", callback_data="dash:week")],
    ])

    await update.message.reply_html(
        "\U0001F33F <b>Weekly Reflection</b>\n\n"
        "Pick an area to reflect on. I'll ask one focused question.",
        reply_markup=markup,
    )


# --------------------------------------------------------------------------
# FOCUS TIMER
# --------------------------------------------------------------------------


def _focus_job_name(user_id):
    return f"focus:{user_id}"


def _cancel_focus(job_queue, user_id):
    """Remove any running focus timer. Returns how many were cancelled."""
    if job_queue is None:
        return 0
    jobs = job_queue.get_jobs_by_name(_focus_job_name(user_id))
    for job in jobs:
        job.schedule_removal()
    return len(jobs)


async def focus_done(context: ContextTypes.DEFAULT_TYPE):
    minutes = (context.job.data or {}).get("minutes", FOCUS_DEFAULT)
    label = (context.job.data or {}).get("label")
    body = (
        f"\U0001F514 <b>Focus block finished</b>\n\n"
        f"That was <b>{minutes}</b> minute{'' if minutes == 1 else 's'}"
        + (f" on {escape(label)}" if label else "")
        + ".\n\nStretch, drink water, then decide the next block."
    )
    try:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=body,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("\U0001F4C5 Today", callback_data="nav:today"),
            ]]),
        )
    except Exception as exc:
        print(f"[warn] Focus completion to {context.job.chat_id} failed: {exc}")


async def focus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = list(context.args or [])

    if args and args[0].lower() in ("stop", "cancel", "off", "end"):
        cancelled = _cancel_focus(context.job_queue, user_id)
        await update.message.reply_html(
            "\U0001F6D1 Focus timer cancelled."
            if cancelled else "No focus timer was running."
        )
        return

    minutes = FOCUS_DEFAULT
    label = None
    if args:
        try:
            minutes = max(1, min(FOCUS_MAX, int(args[0])))
            label = " ".join(args[1:]).strip() or None
        except ValueError:
            label = " ".join(args).strip() or None

    if context.job_queue is None:
        await update.message.reply_text("Timers are unavailable right now.")
        return

    _cancel_focus(context.job_queue, user_id)
    ends_at = now() + datetime.timedelta(minutes=minutes)
    context.job_queue.run_once(
        focus_done,
        when=datetime.timedelta(minutes=minutes),
        name=_focus_job_name(user_id),
        chat_id=update.effective_chat.id,
        data={"minutes": minutes, "label": label},
    )

    await update.message.reply_html(
        f"\U0001F3AF <b>Focus: {minutes} min</b>"
        + (f"\n{escape(label)}" if label else "")
        + f"\n\nI'll ping you at <b>{fmt_time(ends_at)}</b>. "
        "Put the phone down.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001F6D1 Cancel", callback_data="focus:stop"),
        ]]),
    )


# --------------------------------------------------------------------------
# SETTINGS
# --------------------------------------------------------------------------


def settings_view(user):
    """Toggle panel. Returns (html, markup)."""
    settings = user_settings(user)
    quiet_start = settings.get("quiet_start", QUIET_START)
    quiet_end = settings.get("quiet_end", QUIET_END)

    quiet_desc = (
        "off" if quiet_start == quiet_end
        else f"{quiet_start:02d}:00 \u2192 {quiet_end:02d}:00"
    )

    text = (
        "\u2699\uFE0F <b>Settings</b>\n\n"
        f"\U0001F551 Timezone: <b>{escape(_TZ_NAME)}</b>\n"
        f"\U0001F507 Quiet hours: <b>{quiet_desc}</b>\n\n"
        "<i>Quiet hours silence briefings, wind-downs, nudges and digests. "
        "Reminders you scheduled yourself always come through.</i>\n\n"
        "Tap to toggle:"
    )

    rows = []
    for key, label in SETTING_LABELS:
        mark = "\u2705" if settings.get(key, True) else "\u2B1C"
        rows.append([
            InlineKeyboardButton(f"{mark} {label}", callback_data=f"set:toggle:{key}")
        ])

    rows.append([
        InlineKeyboardButton("\U0001F507 Start \u2212", callback_data="set:quiet:start:dec"),
        InlineKeyboardButton(f"{quiet_start:02d}:00", callback_data="noop"),
        InlineKeyboardButton("+", callback_data="set:quiet:start:inc"),
    ])
    rows.append([
        InlineKeyboardButton("\U0001F514 End \u2212", callback_data="set:quiet:end:dec"),
        InlineKeyboardButton(f"{quiet_end:02d}:00", callback_data="noop"),
        InlineKeyboardButton("+", callback_data="set:quiet:end:inc"),
    ])
    rows.append([InlineKeyboardButton("\U0001F4C5 Today", callback_data="nav:today")])

    return text, InlineKeyboardMarkup(rows)


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    save_data(data)
    text, markup = settings_view(user)
    await update.message.reply_html(text, reply_markup=markup)


# --------------------------------------------------------------------------
# CALLBACK ROUTER
# --------------------------------------------------------------------------


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Namespaced dispatch.

    The old router did `action, task_id = data.split("_", 1)` then
    `int(task_id)`, so every non-task button (reflect_family,
    weekly_dashboard, ...) raised ValueError and silently did nothing.
    """
    query = update.callback_query
    raw = query.data or ""
    parts = raw.split(":")
    namespace = parts[0]

    data = load_data()
    user = ensure_user(data, str(query.from_user.id))

    try:
        if namespace == "nav" and parts[1] == "today":
            await query.answer()
            text, markup = today_view(user)
            await safe_edit(query, text, markup)
            return

        if namespace == "dash" and parts[1] == "week":
            await query.answer()
            text, markup = week_view(user)
            await safe_edit(query, text, markup)
            return

        if namespace == "t":
            await _handle_task_action(query, context, data, user, parts)
            return

        if namespace == "rate":
            await _handle_rating(query, context, data, user, parts)
            return

        if namespace == "rf":
            await _handle_reflection_choice(query, context, parts)
            return

        if namespace == "set":
            await _handle_settings(query, context, data, user, parts)
            return

        if namespace == "roll" and parts[1] == "tomorrow":
            await _handle_rollover(query, context, data, user)
            return

        if namespace == "focus" and parts[1] == "stop":
            cancelled = _cancel_focus(context.job_queue, str(query.from_user.id))
            await query.answer(
                "Focus timer cancelled." if cancelled else "No timer running."
            )
            return

        if namespace == "noop":
            await query.answer()
            return

        await query.answer("That button is no longer active.", show_alert=False)

    except (IndexError, ValueError):
        await query.answer("Sorry, that button is malformed.", show_alert=True)


async def _handle_settings(query, context, data, user, parts):
    """set:toggle:<key> or set:quiet:<start|end>:<inc|dec>."""
    action = parts[1]
    settings = user.setdefault("settings", {})
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)

    if action == "toggle":
        key = parts[2]
        if key not in dict(SETTING_LABELS):
            await query.answer("Unknown setting.")
            return
        settings[key] = not settings.get(key, True)
        save_data(data)
        await query.answer("On" if settings[key] else "Off")

    elif action == "quiet":
        field, direction = parts[2], parts[3]
        if field not in ("start", "end") or direction not in ("inc", "dec"):
            await query.answer("Unknown setting.")
            return
        setting_key = f"quiet_{field}"
        step = 1 if direction == "inc" else -1
        settings[setting_key] = (settings.get(setting_key, 0) + step) % 24
        save_data(data)
        await query.answer(f"{settings[setting_key]:02d}:00")

    else:
        await query.answer("Unknown setting.")
        return

    text, markup = settings_view(user)
    await safe_edit(query, text, markup)


async def _handle_rollover(query, context, data, user):
    """Move every still-open task dated today or earlier to tomorrow."""
    today = now().date()
    tomorrow_delta = datetime.timedelta(days=1)
    moved = 0

    for task in user["tasks"]:
        if task.get("done"):
            continue
        try:
            when = parse_dt(task["time"])
        except (ValueError, KeyError):
            continue
        if when.date() > today:
            continue

        new_time = when + tomorrow_delta
        while new_time.date() <= today:
            new_time += tomorrow_delta
        task["time"] = new_time.isoformat()
        task["nudged"] = False

        reminder_at = new_time - datetime.timedelta(minutes=REMINDER_LEAD_MINUTES)
        for reminder in user["reminders"]:
            if reminder.get("task_id") == task["id"]:
                reminder["time"] = reminder_at.isoformat()
                reminder["sent"] = False
                break
        else:
            user["reminders"].append({
                "task_id": task["id"],
                "time": reminder_at.isoformat(),
                "sent": False,
            })
        moved += 1

    if not moved:
        await query.answer("Nothing to roll over.")
        return

    save_data(data)
    await query.answer(f"Moved {moved} to tomorrow.")
    await safe_edit(
        query,
        f"\u27A1\uFE0F Moved <b>{moved}</b> task"
        f"{'' if moved == 1 else 's'} to tomorrow.\n\n"
        "<i>Reminders were reset to match.</i>",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001F4C5 Today", callback_data="nav:today"),
        ]]),
    )


async def _handle_task_action(query, context, data, user, parts):
    action, task_id = parts[1], int(parts[2])
    task = find_task(user, task_id)

    if not task:
        await query.answer("Task not found.", show_alert=True)
        text, markup = today_view(user)
        await safe_edit(query, text, markup)
        return

    if action == "view":
        await query.answer()
        text, markup = task_view(task)
        await safe_edit(query, text, markup)
        return

    if action == "done":
        if task.get("done"):
            await query.answer("Already done.")
            return
        task["done"] = True
        task["completed_at"] = now().isoformat()
        save_data(data)
        await query.answer("Nice work!")
        await safe_edit(
            query,
            f"\U0001F389 Completed <b>{escape(task['text'])}</b>\n\n"
            "How energizing was it?  <i>(1 = draining, 5 = energizing)</i>",
            rating_keyboard(task_id),
        )
        return

    if action == "snz":
        new_time = _apply_snooze(user, task)
        save_data(data)
        await query.answer(f"Snoozed to {fmt_time(new_time)}")
        text, markup = task_view(task)
        await safe_edit(query, text, markup)
        return

    if action == "resch":
        await query.answer()
        await safe_edit(
            query,
            f"\u270F\uFE0F Reschedule <b>{escape(task['text'])}</b>\n\n"
            f"Send:\n<code>/reschedule {task_id} tomorrow 2pm</code>\n\n"
            "Accepted times: <code>3pm</code>, <code>3:30pm</code>, "
            "<code>15:00</code>, <code>tomorrow</code>, <code>tomorrow 9am</code>",
            InlineKeyboardMarkup(
                [[InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")]]
            ),
        )
        return

    if action == "coach":
        await query.answer("Thinking\u2026")
        tip = await ask_ai(
            COACH_SYSTEM,
            build_coach_prompt(task["text"]),
            120,
            "Try breaking it into smaller steps.",
        )
        await safe_edit(
            query,
            f"\U0001F3AF <b>Coach tip</b>\n{escape(task['text'])}\n\n{escape(tip)}",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("\u2705 Done", callback_data=f"t:done:{task_id}"),
                    InlineKeyboardButton(
                        f"\U0001F634 +{SNOOZE_MINUTES}m", callback_data=f"t:snz:{task_id}"
                    ),
                ],
                [InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")],
            ]),
        )
        return

    await query.answer("Unknown action.")


async def _handle_rating(query, context, data, user, parts):
    task_id, rating = int(parts[1]), int(parts[2])
    task = find_task(user, task_id)

    user["reflections"].append({
        "task_id": task_id,
        "task_text": task["text"] if task else "Unknown",
        "rating": rating,
        "notes": "",
        "timestamp": now().isoformat(),
    })
    save_data(data)

    if rating >= 4:
        insight = "This energized you. Schedule more like it."
    elif rating <= 2:
        insight = "This drained you. Next time try it earlier, smaller, or paired with something you enjoy."
    else:
        insight = "Neutral. Notice what tips it either way next time."

    context.user_data["awaiting_note"] = task_id

    await query.answer(f"Logged {rating}/5")
    await safe_edit(
        query,
        f"\u2705 <b>{escape(task['text'] if task else 'Task')}</b>\n\n"
        f"\u26A1 Energy: <code>{bar(rating, 5, 5)}</code> {rating}/5\n\n"
        f"\U0001F4A1 {insight}\n\n"
        "<i>Reply with a note to remember why, or just carry on.</i>",
        InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001F4C5 Today", callback_data="nav:today"),
            InlineKeyboardButton("\U0001F4CA Week", callback_data="dash:week"),
        ]]),
    )


async def _handle_reflection_choice(query, context, parts):
    domain = parts[1]
    prompts = REFLECTION_PROMPTS.get(domain)
    if not prompts:
        await query.answer("Unknown area.")
        return

    prompt = random.choice(prompts)
    context.user_data["awaiting_reflection"] = domain

    await query.answer()
    await safe_edit(
        query,
        f"{cat_emoji(domain if domain != 'balance' else 'general')} "
        f"<b>{domain.title()} reflection</b>\n\n"
        f"<i>{escape(prompt)}</i>\n\n"
        "Reply with your thoughts \u2014 I'll save them.",
        InlineKeyboardMarkup(
            [[InlineKeyboardButton("\u2190 Back to today", callback_data="nav:today")]]
        ),
    )


# --------------------------------------------------------------------------
# TEXT ROUTER
# --------------------------------------------------------------------------

BUTTON_ROUTES = {
    "\U0001F4C5 Today": show_today,
    "\u2795 Add task": None,
    "\U0001F4CA Reflect": weekly_reflect,
    "\U0001F9E0 Suggest": ai_suggest,
    "\U0001F3AF Focus": focus_cmd,
    "\u2699\uFE0F Settings": settings_cmd,
    "\u2753 Help": help_command,
}


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route reply-keyboard taps, then pending reflection input."""
    text = (update.message.text or "").strip()

    if text in BUTTON_ROUTES:
        handler = BUTTON_ROUTES[text]
        if handler is None:
            await update.message.reply_html(
                "<b>Add a task</b>\n\n"
                "<code>/add &lt;task&gt; &lt;time&gt; [category]</code>\n\n"
                "Examples:\n"
                "<code>/add Pick up kids 3:30pm family</code>\n"
                "<code>/add Review charts tomorrow 9am trading</code>"
            )
            return
        context.args = []
        await handler(update, context)
        return

    domain = context.user_data.pop("awaiting_reflection", None)
    if domain:
        data = load_data()
        user = ensure_user(data, str(update.effective_user.id))
        user["reflections"].append({
            "domain": domain,
            "notes": text,
            "timestamp": now().isoformat(),
        })
        save_data(data)
        await update.message.reply_html(
            f"\U0001F4DD Saved your <b>{escape(domain)}</b> reflection.\n\n"
            "<i>These shape the suggestions I give you.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("\U0001F4CA Week", callback_data="dash:week"),
            ]]),
        )
        return

    task_id = context.user_data.pop("awaiting_note", None)
    if task_id is not None:
        data = load_data()
        user = ensure_user(data, str(update.effective_user.id))
        for reflection in reversed(user["reflections"]):
            if reflection.get("task_id") == task_id:
                reflection["notes"] = text
                break
        save_data(data)
        await update.message.reply_text("\U0001F4DD Noted, thanks.")
        return

    await update.message.reply_html(
        "I didn't catch that. Use the buttons below, or /help for commands.",
        reply_markup=MAIN_KEYBOARD,
    )


# --------------------------------------------------------------------------
# REMINDERS
# --------------------------------------------------------------------------


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Deliver due reminders and one-shot overdue nudges.

    Three phases: collect under the lock, send outside it, then re-load and
    mark under the lock. Sending inside the read-modify-write window used to
    let a concurrent handler write get overwritten.
    """
    current = now()
    outbox = []

    async with _data_lock:
        data = load_data()
        stale = []

        for user_id in list(data.keys()):
            user = ensure_user(data, user_id)
            settings = user_settings(user)

            for reminder in user["reminders"]:
                if reminder.get("sent"):
                    continue
                try:
                    due = parse_dt(reminder["time"])
                except (ValueError, KeyError):
                    continue
                if current < due:
                    continue

                task = find_task(user, reminder.get("task_id"))
                if not task or task.get("done"):
                    stale.append((user_id, reminder.get("task_id")))
                    continue

                outbox.append({
                    "user_id": user_id,
                    "task_id": task["id"],
                    "field": "reminder",
                    "settings": settings,
                    "text": (
                        f"\u23F0 <b>Reminder</b>\n\n"
                        f"{cat_emoji(task.get('category', 'general'))} "
                        f"<b>{escape(task['text'])}</b>\n"
                        f"\U0001F551 {fmt_time(parse_dt(task['time']))}"
                    ),
                })

            # Overdue nudge: fires once per task, never repeats.
            if settings.get("nudges", True):
                threshold = current - datetime.timedelta(minutes=NUDGE_AFTER_MINUTES)
                for task in user["tasks"]:
                    if task.get("done") or task.get("nudged"):
                        continue
                    try:
                        when = parse_dt(task["time"])
                    except (ValueError, KeyError):
                        continue
                    if when > threshold:
                        continue
                    late = int((current - when).total_seconds() // 60)
                    outbox.append({
                        "user_id": user_id,
                        "task_id": task["id"],
                        "field": "nudged",
                        "settings": settings,
                        "text": (
                            f"\U0001F440 <b>Still open</b>\n\n"
                            f"{cat_emoji(task.get('category', 'general'))} "
                            f"<b>{escape(task['text'])}</b>\n"
                            f"Was due {late} min ago."
                        ),
                    })

        for user_id, task_id in stale:
            user = data.get(user_id) or {}
            for reminder in user.get("reminders", []):
                if reminder.get("task_id") == task_id:
                    reminder["sent"] = True
        if stale:
            save_data(data)

    if not outbox:
        return

    delivered = []
    for item in outbox:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("\u2705 Done", callback_data=f"t:done:{item['task_id']}"),
            InlineKeyboardButton(
                f"\U0001F634 +{SNOOZE_MINUTES}m", callback_data=f"t:snz:{item['task_id']}"
            ),
            InlineKeyboardButton(
                "\u270F\uFE0F Move", callback_data=f"t:resch:{item['task_id']}"
            ),
        ]])
        # Reminders are explicitly user-scheduled, so they ignore quiet hours.
        # Nudges are bot-initiated and do not.
        ok = await send_proactive(
            context.bot,
            item["user_id"],
            item["text"],
            markup,
            kind=None if item["field"] == "reminder" else "nudges",
            settings=item["settings"],
            ignore_quiet=item["field"] == "reminder",
        )
        if ok:
            delivered.append(item)

    if not delivered:
        return

    async with _data_lock:
        data = load_data()
        for item in delivered:
            user = data.get(item["user_id"])
            if not user:
                continue
            if item["field"] == "reminder":
                for reminder in user.get("reminders", []):
                    if reminder.get("task_id") == item["task_id"]:
                        reminder["sent"] = True
                        break
            else:
                task = next(
                    (t for t in user.get("tasks", []) if t.get("id") == item["task_id"]),
                    None,
                )
                if task:
                    task["nudged"] = True
        save_data(data)


def digest_content(user, insights=()):
    """Weekly stats plus a reflection prompt. Returns (html, markup)."""
    text, _ = week_view(user)
    domain = random.choice(list(REFLECTION_PROMPTS))
    prompt = random.choice(REFLECTION_PROMPTS[domain])

    body = (
        f"{text}"
        f"{insight_block(insights)}\n\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001F33F <b>Weekly reflection</b>\n\n"
        f"<i>{escape(prompt)}</i>\n\n"
        "Reply with your thoughts, or pick another area:"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001F46A Family", callback_data="rf:family"),
            InlineKeyboardButton("\U0001F4B9 Trading", callback_data="rf:trading"),
        ],
        [
            InlineKeyboardButton("\U0001F4E3 Marketing", callback_data="rf:marketing"),
            InlineKeyboardButton("\u2696\uFE0F Balance", callback_data="rf:balance"),
        ],
        [InlineKeyboardButton("\U0001F4C5 Plan tomorrow", callback_data="nav:today")],
    ])
    return body, markup


def briefing_content(user):
    """Morning briefing. Returns (html, markup) or (None, None) if nothing."""
    today = now().date()
    rows = []
    for task in user.get("tasks", []):
        if task.get("done"):
            continue
        try:
            when = parse_dt(task["time"])
        except (ValueError, KeyError):
            continue
        if when.date() == today:
            rows.append((task, when))

    if not rows:
        return None, None

    rows.sort(key=lambda pair: pair[1])
    lines = [
        f"\U0001F305 <b>Good morning</b>  \u00B7  {now().strftime('%a %d %b')}",
    ]
    streak = streak_line(user)
    if streak:
        lines.append(streak)
    lines.append("")
    lines.append(
        f"You have <b>{len(rows)}</b> task{'' if len(rows) == 1 else 's'} today:"
    )
    for task, when in rows[:8]:
        lines.append(
            f"\u23F3 <b>{fmt_time(when)}</b> \u2014 {escape(task['text'])} "
            f"{cat_emoji(task.get('category', 'general'))}"
        )
    if len(rows) > 8:
        lines.append(f"<i>\u2026and {len(rows) - 8} more</i>")

    first_task, first_when = rows[0]
    lines.append("")
    lines.append(
        f"First up at <b>{fmt_time(first_when)}</b>. "
        f"{escape(first_task['text'])}"
    )

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("\U0001F4C5 Open today", callback_data="nav:today"),
        InlineKeyboardButton("\U0001F9E0 Coach me", callback_data=f"t:coach:{first_task['id']}"),
    ]])
    return "\n".join(lines), markup


def winddown_content(user, insights=()):
    """Evening recap. Returns (html, markup, rollover_ids)."""
    today = now().date()
    done_today, still_open = [], []
    for task in user.get("tasks", []):
        try:
            when = parse_dt(task["time"])
        except (ValueError, KeyError):
            continue
        completed = _completed_at(task)
        if task.get("done") and completed and completed.date() == today:
            done_today.append(task)
        elif not task.get("done") and when.date() <= today:
            still_open.append((task, when))

    if not done_today and not still_open:
        return None, None, []

    total = len(done_today) + len(still_open)
    lines = [
        f"\U0001F319 <b>Winding down</b>  \u00B7  {now().strftime('%a %d %b')}",
        f"<code>{bar(len(done_today), total)}</code>  "
        f"{len(done_today)}/{total} done today",
    ]
    streak = streak_line(user)
    if streak:
        lines.append(streak)

    if done_today:
        lines.append("")
        lines.append("\u2705 <b>Completed</b>")
        for task in done_today[:6]:
            lines.append(
                f"   {cat_emoji(task.get('category', 'general'))} "
                f"{escape(task['text'])}"
            )

    still_open.sort(key=lambda pair: pair[1])
    rollover_ids = [task["id"] for task, _ in still_open]
    if still_open:
        lines.append("")
        lines.append("\u23F3 <b>Still open</b>")
        for task, when in still_open[:6]:
            lines.append(
                f"   {cat_emoji(task.get('category', 'general'))} "
                f"{escape(task['text'])} <i>({fmt_time(when)})</i>"
            )
        if len(still_open) > 6:
            lines.append(f"   <i>\u2026and {len(still_open) - 6} more</i>")

    body = "\n".join(lines) + insight_block(insights)

    buttons = []
    if rollover_ids:
        count = len(rollover_ids)
        buttons.append([InlineKeyboardButton(
            f"\u27A1\uFE0F Roll {count} to tomorrow", callback_data="roll:tomorrow"
        )])
    buttons.append([
        InlineKeyboardButton("\U0001F4C5 Today", callback_data="nav:today"),
        InlineKeyboardButton("\U0001F4CA Week", callback_data="dash:week"),
    ])
    return body, InlineKeyboardMarkup(buttons), rollover_ids


async def _run_daily_broadcast(context, *, kind, stamp_key, builder, label):
    """Shared driver for the once-a-day proactive jobs.

    Collects under the lock, sends outside it, then records delivery and
    insight cooldowns under the lock again.
    """
    today_iso = now().date().isoformat()
    outbox = []

    async with _data_lock:
        data = load_data()
        for user_id in list(data.keys()):
            user = ensure_user(data, user_id)
            settings = user_settings(user)
            if not settings.get(kind, True):
                continue
            if user.get(stamp_key) == today_iso:
                continue
            if not user["tasks"]:
                continue

            insights = due_insights(user) if settings.get("insights", True) else []
            built = builder(user, insights)
            body, markup = built[0], built[1]
            if not body:
                continue
            outbox.append({
                "user_id": user_id,
                "settings": settings,
                "body": body,
                "markup": markup,
                "insight_keys": [key for key, _ in insights],
            })
        save_data(data)

    sent = 0
    for item in outbox:
        ok = await send_proactive(
            context.bot,
            item["user_id"],
            item["body"],
            item["markup"],
            kind=kind,
            settings=item["settings"],
        )
        if not ok:
            continue
        sent += 1
        async with _data_lock:
            data = load_data()
            user = ensure_user(data, item["user_id"])
            user[stamp_key] = today_iso
            mark_insights_sent(user, item["insight_keys"])
            save_data(data)

    print(f"[job] {label} sent to {sent} user(s).")


async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    await _run_daily_broadcast(
        context,
        kind="briefing",
        stamp_key="last_briefing",
        builder=lambda user, insights: briefing_content(user),
        label="Morning briefing",
    )


async def evening_winddown(context: ContextTypes.DEFAULT_TYPE):
    await _run_daily_broadcast(
        context,
        kind="winddown",
        stamp_key="last_winddown",
        builder=lambda user, insights: winddown_content(user, insights),
        label="Evening wind-down",
    )


async def weekly_digest(context: ContextTypes.DEFAULT_TYPE):
    """Send each user their week plus a reflection prompt.

    Runs on DIGEST_DAY at DIGEST_HOUR in BOT_TZ. Guarded by an ISO-week
    stamp so a restart cannot double-send.
    """
    this_week = now().isocalendar()[:2]
    outbox = []

    async with _data_lock:
        data = load_data()
        for user_id in list(data.keys()):
            user = ensure_user(data, user_id)
            settings = user_settings(user)
            if not settings.get("digest", True):
                continue

            stamp = user.get("last_digest")
            if stamp:
                try:
                    if parse_dt(stamp).isocalendar()[:2] == this_week:
                        continue
                except ValueError:
                    pass

            # Skip users with nothing to report; an empty digest is just noise.
            if not user["tasks"]:
                continue

            insights = due_insights(user) if settings.get("insights", True) else []
            body, markup = digest_content(user, insights)
            outbox.append({
                "user_id": user_id,
                "settings": settings,
                "body": body,
                "markup": markup,
                "insight_keys": [key for key, _ in insights],
            })
        save_data(data)

    sent = 0
    for item in outbox:
        ok = await send_proactive(
            context.bot,
            item["user_id"],
            item["body"],
            item["markup"],
            kind="digest",
            settings=item["settings"],
        )
        if not ok:
            continue
        sent += 1
        async with _data_lock:
            data = load_data()
            user = ensure_user(data, item["user_id"])
            user["last_digest"] = now().isoformat()
            mark_insights_sent(user, item["insight_keys"])
            save_data(data)

    print(f"[job] Weekly digest sent to {sent} user(s).")


BACKUP_DIR = os.path.join(DATA_DIR, "backups")


def _prune_backups(keep):
    try:
        names = sorted(
            n for n in os.listdir(BACKUP_DIR)
            if n.startswith("user_data_") and n.endswith(".json")
        )
    except OSError:
        return 0
    removed = 0
    for name in names[:-keep] if keep < len(names) else []:
        try:
            os.remove(os.path.join(BACKUP_DIR, name))
            removed += 1
        except OSError:
            pass
    return removed


async def backup_job(context: ContextTypes.DEFAULT_TYPE):
    """Snapshot the data file. Cheap insurance: it is only kilobytes."""
    data = await read_data()
    if not data:
        print("[job] Backup skipped, no data yet.")
        return

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        path = os.path.join(
            BACKUP_DIR, f"user_data_{now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        pruned = _prune_backups(BACKUP_KEEP)
        print(
            f"[job] Backup written to {path}"
            + (f" ({pruned} old file(s) pruned)" if pruned else "")
        )
    except OSError as exc:
        print(f"[error] Backup failed: {exc}")


# --------------------------------------------------------------------------
# PREVIEW COMMANDS
# --------------------------------------------------------------------------


async def digest_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Preview the weekly digest on demand, bypassing the once-a-week guard."""
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    save_data(data)

    if not user["tasks"]:
        await update.message.reply_html(
            "Nothing to report yet \u2014 add a task first with "
            "<code>/add Call mom 7pm family</code>"
        )
        return

    body, markup = digest_content(user, compute_insights(user))
    schedule = (
        f"{DAY_NAMES[DIGEST_DAY]} at {DIGEST_HOUR:02d}:00 {_TZ_NAME}"
        if DIGEST_ENABLED
        else "disabled"
    )
    await update.message.reply_html(
        f"{body}\n\n<i>Automatic delivery: {escape(schedule)}</i>",
        reply_markup=markup,
    )


async def brief_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Preview the morning briefing on demand."""
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    save_data(data)

    body, markup = briefing_content(user)
    if not body:
        await update.message.reply_html(
            "Nothing scheduled for today, so there would be no briefing.\n\n"
            "Add something with <code>/add Call mom 7pm family</code>"
        )
        return

    schedule = (
        f"daily at {BRIEFING_HOUR:02d}:00 {_TZ_NAME}"
        if BRIEFING_ENABLED else "disabled"
    )
    await update.message.reply_html(
        f"{body}\n\n<i>Automatic delivery: {escape(schedule)}</i>",
        reply_markup=markup,
    )


async def winddown_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Preview the evening wind-down on demand."""
    data = load_data()
    user = ensure_user(data, str(update.effective_user.id))
    save_data(data)

    body, markup, _ = winddown_content(user, compute_insights(user))
    if not body:
        await update.message.reply_html(
            "Nothing recorded for today, so there would be no wind-down.\n\n"
            "Add something with <code>/add Call mom 7pm family</code>"
        )
        return

    schedule = (
        f"daily at {WINDDOWN_HOUR:02d}:00 {_TZ_NAME}"
        if WINDDOWN_ENABLED else "disabled"
    )
    await update.message.reply_html(
        f"{body}\n\n<i>Automatic delivery: {escape(schedule)}</i>",
        reply_markup=markup,
    )


# --------------------------------------------------------------------------
# STARTUP
# --------------------------------------------------------------------------


async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("today", "Today's tasks, with buttons"),
        BotCommand("add", "Add a task: /add Call mom 7pm family"),
        BotCommand("week", "Weekly progress"),
        BotCommand("focus", "Start a focus timer: /focus 25"),
        BotCommand("suggest", "AI task suggestion"),
        BotCommand("plan", "Break a goal into steps"),
        BotCommand("reflect", "Weekly reflection"),
        BotCommand("brief", "Preview your morning briefing"),
        BotCommand("winddown", "Preview your evening wind-down"),
        BotCommand("digest", "Preview your weekly digest"),
        BotCommand("settings", "Toggle automations and quiet hours"),
        BotCommand("done", "Complete a task by id"),
        BotCommand("snooze", "Delay a task 30 mins"),
        BotCommand("reschedule", "Move a task to a new time"),
        BotCommand("assist", "Coaching tip for a task"),
        BotCommand("help", "All commands"),
    ])
    print(f"[init] Commands registered. Timezone={_TZ_NAME}. Data={DATA_FILE}")


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN is not set. Add it to your Railway variables.")

    if DATA_DIR in (".", "", None):
        print(
            "[warn] DATA_DIR is unset, so data is written to the container "
            "filesystem and WILL be lost on redeploy. Mount a Railway Volume "
            "and set DATA_DIR to its mount path."
        )
    else:
        # Fail loudly at startup rather than silently at 03:00.
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            print(f"[init] Backup directory ready: {BACKUP_DIR}")
        except OSError as exc:
            print(f"[warn] Cannot create {BACKUP_DIR}: {exc}. Backups will fail.")

    application = Application.builder().token(token).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("today", show_today))
    application.add_handler(CommandHandler("week", show_week))
    application.add_handler(CommandHandler("done", complete_task))
    application.add_handler(CommandHandler("snooze", snooze_task))
    application.add_handler(CommandHandler("reschedule", reschedule_task))
    application.add_handler(CommandHandler("reflect", weekly_reflect))
    application.add_handler(CommandHandler("digest", digest_now))
    application.add_handler(CommandHandler("brief", brief_now))
    application.add_handler(CommandHandler("winddown", winddown_now))
    application.add_handler(CommandHandler("settings", settings_cmd))
    application.add_handler(CommandHandler("focus", focus_cmd))
    application.add_handler(CommandHandler(["suggest", "ai_suggest"], ai_suggest))
    application.add_handler(CommandHandler("plan", plan_goal))
    application.add_handler(CommandHandler("assist", assist_task))

    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    jobs = application.job_queue
    jobs.run_repeating(check_reminders, interval=60, first=10)

    # tzinfo must be explicit on every scheduled time: a naive time would be
    # treated as UTC and fire hours off.
    def daily(callback, hour, name):
        jobs.run_daily(
            callback,
            time=datetime.time(hour=hour, minute=0, tzinfo=TZ),
            name=name,
        )

    if BRIEFING_ENABLED:
        daily(morning_briefing, BRIEFING_HOUR, "morning_briefing")
        print(f"[init] Morning briefing at {BRIEFING_HOUR:02d}:00 {_TZ_NAME}")

    if WINDDOWN_ENABLED:
        daily(evening_winddown, WINDDOWN_HOUR, "evening_winddown")
        print(f"[init] Evening wind-down at {WINDDOWN_HOUR:02d}:00 {_TZ_NAME}")

    if BACKUP_ENABLED:
        daily(backup_job, BACKUP_HOUR, "backup")
        print(
            f"[init] Backup at {BACKUP_HOUR:02d}:00 {_TZ_NAME}, "
            f"keeping {BACKUP_KEEP}"
        )

    if DIGEST_ENABLED:
        jobs.run_daily(
            weekly_digest,
            time=datetime.time(hour=DIGEST_HOUR, minute=0, tzinfo=TZ),
            days=(DIGEST_DAY,),
            name="weekly_digest",
        )
        print(
            f"[init] Weekly digest scheduled for {DAY_NAMES[DIGEST_DAY]} "
            f"{DIGEST_HOUR:02d}:00 {_TZ_NAME}"
        )
    else:
        print("[init] Weekly digest disabled (DIGEST_ENABLED=0)")

    quiet = (
        "off" if QUIET_START == QUIET_END
        else f"{QUIET_START:02d}:00-{QUIET_END:02d}:00"
    )
    print(f"[init] Quiet hours default: {quiet} (reminders exempt)")

    # A job scheduled inside quiet hours would be silently swallowed by
    # send_proactive, which looks exactly like the feature being broken.
    probe = now()
    for label, hour, enabled in (
        ("Morning briefing", BRIEFING_HOUR, BRIEFING_ENABLED),
        ("Evening wind-down", WINDDOWN_HOUR, WINDDOWN_ENABLED),
        ("Weekly digest", DIGEST_HOUR, DIGEST_ENABLED),
    ):
        if enabled and in_quiet_hours(probe.replace(hour=hour), QUIET_START, QUIET_END):
            print(
                f"[warn] {label} is scheduled at {hour:02d}:00, which falls "
                f"inside quiet hours ({quiet}), so it will be suppressed. "
                "Move the hour or change QUIET_START/QUIET_END."
            )

    # Keep startup logs ASCII: a non-UTF8 stdout would crash on emoji.
    print(f"[init] LifeBalance Bot running (tz={_TZ_NAME}, data={DATA_FILE})")
    application.run_polling()


if __name__ == "__main__":
    main()
