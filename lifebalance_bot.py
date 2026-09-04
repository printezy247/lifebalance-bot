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
    if "next_id" not in user:
        highest = max((t.get("id", 0) for t in user["tasks"]), default=0)
        user["next_id"] = highest + 1
    return user


def find_task(user, task_id):
    for task in user["tasks"]:
        if task.get("id") == task_id:
            return task
    return None


# --------------------------------------------------------------------------
# UI HELPERS
# --------------------------------------------------------------------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["\U0001F4C5 Today", "\u2795 Add task"],
        ["\U0001F4CA Reflect", "\U0001F9E0 Suggest"],
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
        "",
    ]

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
        "",
    ]

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

HF_API_URL = "https://api-inference.huggingface.co/models/"
HEADERS = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "nvidia/Llama3-ChatQA-1.5-8B")


def _query_hf_blocking(payload, model):
    response = requests.post(
        f"{HF_API_URL}{model}", headers=HEADERS, json=payload, timeout=30
    )
    response.raise_for_status()
    return response.json()


async def query_hf_model(payload, model=None):
    """Run the blocking HTTP call off the event loop.

    Calling requests.post directly inside an async handler froze the whole
    bot for the duration of every AI request.
    """
    model = model or DEFAULT_MODEL
    return await asyncio.to_thread(_query_hf_blocking, payload, model)


def _extract_text(output, fallback):
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, dict):
            return first.get("generated_text") or fallback
    if isinstance(output, dict):
        if "error" in output:
            return f"Model error: {output['error']}"
        return output.get("generated_text") or fallback
    return fallback


async def ask_ai(prompt, max_tokens, fallback):
    if not os.getenv("HF_TOKEN"):
        return "AI is not configured \u2014 set HF_TOKEN in Railway variables."
    try:
        output = await query_hf_model(
            {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}
        )
        return _extract_text(output, fallback)
    except Exception as exc:
        return f"AI unavailable right now ({type(exc).__name__}: {exc})."


def build_suggestion_prompt(ctx):
    return f"""
You are a wise, kind life coach helping {ctx['name']} balance work and family.
Based on:
- Recent tasks: {ctx['recent_tasks']}
- Energy level (1-5): {ctx['energy']}
- Time of day: {ctx['time_of_day']}
- Stated priorities: {ctx['priorities']}

Suggest ONE specific, actionable task for the next 2-4 hours that:
1. Advances a meaningful goal (work OR personal)
2. Respects their energy level (e.g. don't suggest deep work if energy=2)
3. Includes a tiny joy element
4. Takes < 90 mins
5. Is phrased warmly

Respond ONLY with the suggestion.
""".strip()


def build_planning_prompt(goal, category="general"):
    return f"""
You are a project planning expert. Break this goal into:
- 3-5 concrete subtasks (each < 90 mins)
- Time estimates (realistic, includes buffer)
- One potential blocker + prep step
- How to celebrate completion

Goal: "{goal}" [{category}]

Be practical, not idealistic. If the goal is too big, suggest the FIRST step only.
""".strip()


def build_coach_prompt(task_text):
    return f"""
You are a supportive task coach. The user is about to work on: "{task_text}"
Give ONE specific, actionable tip to help them start or overcome a hurdle.
Keep it under 2 sentences. Be warm and practical.
""".strip()


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
    await update.message.reply_html(
        "<b>Commands</b>\n\n"
        "<code>/add &lt;task&gt; &lt;time&gt; [category]</code>\n"
        "   Times: <code>3pm</code>, <code>3:30pm</code>, <code>15:00</code>, "
        "<code>tomorrow</code>, <code>tomorrow 9am</code>\n"
        "/today \u2014 today's tasks with buttons\n"
        "/week \u2014 weekly progress bars\n"
        "/done &lt;id&gt; \u2014 complete a task\n"
        "/snooze &lt;id&gt; \u2014 delay 30 mins\n"
        "/reschedule &lt;id&gt; &lt;time&gt; \u2014 move a task\n"
        "/suggest \u2014 AI suggestion\n"
        "/plan &lt;goal&gt; \u2014 AI breakdown\n"
        "/assist &lt;id&gt; \u2014 coaching tip\n"
        "/reflect \u2014 weekly reflection\n\n"
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

    suggestion = await ask_ai(prompt, 150, "Couldn't generate a suggestion.")
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
    plan = await ask_ai(build_planning_prompt(goal, category), 250, "Planning failed.")

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
        build_coach_prompt(task["text"]), 100, "Try breaking it into smaller steps."
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

        await query.answer("That button is no longer active.", show_alert=False)

    except (IndexError, ValueError):
        await query.answer("Sorry, that button is malformed.", show_alert=True)


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
            build_coach_prompt(task["text"]), 100, "Try breaking it into smaller steps."
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
    current = now()
    data = load_data()
    dirty = False

    for user_id, user in data.items():
        for reminder in user.get("reminders", []):
            if reminder.get("sent"):
                continue
            try:
                due = parse_dt(reminder["time"])
            except (ValueError, KeyError):
                continue
            if current < due:
                continue

            task = next(
                (t for t in user.get("tasks", []) if t.get("id") == reminder["task_id"]),
                None,
            )
            if not task or task.get("done"):
                reminder["sent"] = True
                dirty = True
                continue

            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("\u2705 Done", callback_data=f"t:done:{task['id']}"),
                InlineKeyboardButton(
                    f"\U0001F634 +{SNOOZE_MINUTES}m", callback_data=f"t:snz:{task['id']}"
                ),
                InlineKeyboardButton("\u270F\uFE0F Move", callback_data=f"t:resch:{task['id']}"),
            ]])

            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=(
                        f"\u23F0 <b>Reminder</b>\n\n"
                        f"{cat_emoji(task.get('category', 'general'))} "
                        f"<b>{escape(task['text'])}</b>\n"
                        f"\U0001F551 {fmt_time(parse_dt(task['time']))}"
                    ),
                    reply_markup=markup,
                    parse_mode="HTML",
                )
                reminder["sent"] = True
                dirty = True
            except Exception as exc:
                print(f"[warn] Reminder to {user_id} failed: {exc}")

    if dirty:
        save_data(data)


# --------------------------------------------------------------------------
# STARTUP
# --------------------------------------------------------------------------


async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("today", "Today's tasks, with buttons"),
        BotCommand("add", "Add a task: /add Call mom 7pm family"),
        BotCommand("week", "Weekly progress"),
        BotCommand("suggest", "AI task suggestion"),
        BotCommand("plan", "Break a goal into steps"),
        BotCommand("reflect", "Weekly reflection"),
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
    application.add_handler(CommandHandler(["suggest", "ai_suggest"], ai_suggest))
    application.add_handler(CommandHandler("plan", plan_goal))
    application.add_handler(CommandHandler("assist", assist_task))

    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    application.job_queue.run_repeating(check_reminders, interval=60, first=10)

    # Keep startup logs ASCII: a non-UTF8 stdout would crash on emoji.
    print(f"[init] LifeBalance Bot running (tz={_TZ_NAME}, data={DATA_FILE})")
    application.run_polling()


if __name__ == "__main__":
    main()
