from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import datetime
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Loads HF_TOKEN and BOT_TOKEN from Railway env vars

# --- DATA STORAGE (Simple JSON file - works for personal use) ---
DATA_FILE = "user_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# --- NVIDIA/HUGGING FACE AI SETUP ---
HF_API_URL = "https://api-inference.huggingface.co/models/"
HEADERS = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "nvidia/Llama3-ChatQA-1.5-8B")

def query_hf_model(payload, model=None):
    """Query Hugging Face hosted NVIDIA model"""
    model = model or DEFAULT_MODEL
    response = requests.post(f"{HF_API_URL}{model}", headers=HEADERS, json=payload)
    return response.json()
  # --- AI PROMPT TEMPLATES ---
def build_suggestion_prompt(user_context):
    return f"""
You are a wise, kind life coach helping {user_context['name']} balance work and family.
Based on:
- Recent tasks: {user_context['recent_tasks']}
- Energy level (1-5): {user_context['energy']}
- Time of day: {user_context['time_of_day']}
- Stated priorities: {user_context['priorities']}

Suggest ONE specific, actionable task for the next 2-4 hours that:
1. Advances a meaningful goal (work OR personal)
2. Respects their energy level (e.g., don't suggest deep work if energy=2)
3. Includes a tiny joy element (e.g., "Listen to favorite podcast while doing X")
4. Takes < 90 mins (respects attention span)
5. Is phrased warmly: "How about trying [task]? It could help you feel [benefit]."

Respond ONLY with the suggestion — no extra text.
    """.strip()

def build_planning_prompt(goal, category="general"):
    return f"""
You are a project planning expert. Break this goal into:
- 3-5 concrete subtasks (each < 90 mins)
- Time estimates (realistic, includes buffer)
- One potential blocker + prep step
- How to celebrate completion

Goal: "{goal}" [{category}]

Format as:
🎯 **Goal**: [goal]
📋 **Plan**:
1. [Subtask] (~[time])
   - Blocker prep: [action]
2. [Subtask] (~[time])
   ...
💡 **Tip**: [One pro tip for success]
🎉 **Celebrate**: [Small reward idea]

Be practical, not idealistic. If goal is too big, suggest FIRST step only.
    """.strip()
  # --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.first_name}! 👋 I’m <b>LifeBalance</b> — your friendly planner for work, family, and YOU.\n\n"
        "Try these:\n"
        "• /add [task] [time] → Add a task (e.g., /add Call mom 7pm)\n"
        "• /today → See your priorities\n"
        "• /done [task_id] → Mark task as complete\n"
        "• /snooze [task_id] → Delay task by 30 mins\n"
        "• /ai suggest → Get AI-powered task suggestion\n"
        "• /plan [goal] → Break goal into steps\n"
        "• /assist [task_id] → Get coaching tip mid-task\n"
        "• /reflect → Weekly reflection (every Sunday)\n"
        "• /help → See all commands\n\n"
        "Remember: This is about *harmony*, not perfection. 💛"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/add <task> <time> → Add task (time formats: '3pm', '15:00', 'tomorrow 9am')\n"
        "/today → View today’s tasks\n"
        "/done <task_id> → Mark task as complete\n"
        "/snooze <task_id> → Delay task by 30 mins\n"
        "/ai suggest → Get AI-powered task suggestion\n"
        "/plan [goal] → Break goal into steps\n"
        "/assist [task_id] → Get coaching tip mid-task\n"
        "/reflect → Weekly reflection (run every Sunday)\n"
        "/help → Show this menu"
    )

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"tasks": [], "reminders": []}
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /add <task> <time> [category]\nExample: /add Pick up kids 3:30pm family\nCategories: family, trading, marketing, content, learning, health, admin, general")
        return
    
    # Check if last argument is a known category
    known_categories = ["family", "trading", "marketing", "content", "learning", "health", "admin", "general"]
    category = "general"  # default
    
    if len(args) >= 3 and args[-1].lower() in known_categories:
        category = args[-1].lower()
        time_str = args[-2]
        task_text = " ".join(args[:-2])
    else:
        time_str = args[-1]
        task_text = " ".join(args[:-1])
    
    try:
        now = datetime.datetime.now()
        if time_str.lower() == "tomorrow":
            target = now + datetime.timedelta(days=1)
            target = target.replace(hour=9, minute=0, second=0, microsecond=0)
        elif time_str.endswith("pm") or time_str.endswith("am"):
            hour = int(time_str[:-2])
            if time_str.endswith("pm") and hour != 12: hour += 12
            if time_str.endswith("am") and hour == 12: hour = 0
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target < now: target += datetime.timedelta(days=1)
        else:
            hour, minute = map(int, time_str.split(":"))
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now: target += datetime.timedelta(days=1)
    except:
        await update.message.reply_text("Couldn’t understand time. Try: '3pm', '15:00', or 'tomorrow 9am'")
        return
    
    task_id = len(data[user_id]["tasks"]) + 1
    new_task = {
        "id": task_id,
        "text": task_text,
        "time": target.isoformat(),
        "done": False,
        "created": datetime.datetime.now().isoformat(),
        "category": category
    }
    data[user_id]["tasks"].append(new_task)

    reminder_time = target - datetime.timedelta(minutes=10)
    if reminder_time > datetime.datetime.now():
        data[user_id]["reminders"].append({
            "task_id": task_id,
            "time": reminder_time.isoformat(),
            "sent": False
        })
    
    save_data(data)
    await update.message.reply_text(
        f"✅ Added: \"{task_text}\" [{category}] at {target.strftime('%I:%M %p')}\n"
        f"I’ll remind you 10 mins before! 🕒\n"
        f"Tip: Use /done {task_id} when finished."
    )



async def show_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"tasks": [], "reminders": []}

    now = datetime.datetime.now()
    today = now.date()
    today_tasks = []
    for task in data[user_id]["tasks"]:
        try:
            task_time = datetime.datetime.fromisoformat(task["time"])
            if task_time.date() == today:
                today_tasks.append((task, task_time))
        except:
            pass

    if not today_tasks:
        await update.message.reply_text("No tasks for today! Enjoy the freedom. 🌸")
        return

    today_tasks.sort(key=lambda x: x[1])
    msg = "📅 <b>Your Today</b> (Work + Live):\n\n"
    for task, t_time in today_tasks:
        status = "✅" if task["done"] else "⏳"
        time_str = t_time.strftime("%I:%M %p")
        msg += f"{status} <b>{time_str}</b> — {task['text']} [{task.get('category', 'general')}]\n"

async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        await update.message.reply_text("No tasks yet! Use /add first.")
        return
    
    try:
        task_id = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /done <task_id>")
        return
    
    task = None
    for t in data[user_id]["tasks"]:
        if t["id"] == task_id and not t["done"]:
            t["done"] = True
            t["completed_at"] = datetime.datetime.now().isoformat()
            task = t
            break
    
    if not task:
        await update.message.reply_text("Task not found or already done.")
        return
    
    save_data(data)
    
    await update.message.reply_text(
        f"🎉 Completed: \"{task['text']}! \n\n"
        f"Quick reflection (reply with 1-5 or skip):\n"
        f"1. How energizing was this? (1=draining, 5=energizing)\n"
        f"2. One thing that helped/hindered? (Optional)\n\n"
        f'Example reply: "4\nHelped: Listened to music"\n\n'
        f"This helps me suggest better tasks for you!",
        parse_mode="HTML"
    )
    
    context.user_data["awaiting_reflection"] = task_id
async def snooze_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        await update.message.reply_text("No tasks to snooze!")
        return
    
    try:
        task_id = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /snooze <task_id>")
        return
    
    for t in data[user_id]["tasks"]:
        if t["id"] == task_id and not t["done"]:
            t_time = datetime.datetime.fromisoformat(t["time"])
            new_time = t_time + datetime.timedelta(minutes=30)
            t["time"] = new_time.isoformat()
            
            for r in data[user_id]["reminders"]:
                if r["task_id"] == task_id and not r["sent"]:
                    r["time"] = (new_time - datetime.timedelta(minutes=10)).isoformat()
                    break
            
            save_data(data)
            await update.message.reply_text(
                f"😴 Snoozed: \"{t['text']}\" to {new_time.strftime('%I:%M %p')}\n"
                f"New reminder set for 10 mins before."
            )
            return
    
    await update.message.reply_text("Task not found or already done.")

async def weekly_reflect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"tasks": [], "reflections": [], "weekly_plans": []}
    
    # Get last week's tasks for context
    one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    recent_tasks = [t for t in data[user_id]["tasks"] 
                   if "created" in t and 
                   datetime.datetime.fromisoformat(t["created"]) > one_week_ago]
    
    completed_last_week = [t for t in recent_tasks if t.get("done", False)]
    pending_last_week = [t for t in recent_tasks if not t.get("done", False)]
    
    # Domain-specific reflection prompts
    family_prompts = [
        "What’s 1 meaningful moment you shared with your wife or daughter this week?",
        "How did you balance work time with family time this week? What could be better?",
        "What’s 1 family activity you’d like to do more of next week?",
        "Did you feel present with your family during non-work hours?"
    ]
    
    trading_prompts = [
        "How many hours did you spend on trading/trading analysis this week?",
        "What’s 1 trading lesson you learned this week?",
        "Did you stick to your trading plan/rules this week? If not, what got in the way?",
        "What’s 1 adjustment you’d make to your trading approach for next week?"
    ]
    
    marketing_prompts = [
        "How much time did you spend on marketing/content creation this week?",
        "What’s 1 piece of content you created that you’re proud of?",
        "Which marketing channel gave you the best engagement this week?",
        "What’s 1 marketing experiment you want to try next week?"
    ]
    
    balance_prompts = [
        "On a scale of 1-10, how would you rate your work-life balance this week?",
        "What’s 1 thing you sacrificed for work this week that you wish you hadn’t?",
        "What’s 1 non-work activity that recharged you this week?",
        "If you could protect 1 hour each day for non-work, what would you do with it?"
    ]
    
    # Select a random prompt from all categories
    all_prompts = family_prompts + trading_prompts + marketing_prompts + balance_prompts
    import random
    prompt = random.choice(all_prompts)
    
    # Add context about last week if we have data
    context_text = ""
    if recent_tasks:
        context_text = f"\n\n📊 Last Week at a Glance:\n"
        context_text += f"  ✅ Completed: {len(completed_last_week)} tasks\n"
        context_text += f"  ⏳ Pending: {len(pending_last_week)} tasks\n"
        if completed_last_week:
            # Show categories of completed tasks
            cats = {}
            for t in completed_last_week:
                cat = t.get("category", "general")
                cats[cat] = cats.get(cat, 0) + 1
            context_text += "  By category: " + ", ".join([f"{k}: {v}" for k, v in cats.items()]) + "\n"
    
    # Create inline keyboard for quick reflection responses
    keyboard = [
        [
            InlineKeyboardButton("📝 Quick Family Reflection", callback_data="reflect_family"),
            InlineKeyboardButton("💹 Quick Trading Reflection", callback_data="reflect_trading")
        ],
        [
            InlineKeyboardButton("📢 Quick Marketing Reflection", callback_data="reflect_marketing"),
            InlineKeyboardButton("⚖️ Quick Balance Reflection", callback_data="reflect_balance")
        ],
        [
            InlineKeyboardButton("📊 View Weekly Dashboard", callback_data="weekly_dashboard"),
            InlineKeyboardButton("📋 Skip Reflection", callback_data="reflect_skip")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🌿 <b>Weekly Reflection</b> (Your Plan-Do-Review Checkpoint):\n\n"
        f"<i>{prompt}</i>"
        f"{context_text}\n\n"
        f"Choose a quick reflection or reply with your thoughts:\n\n"
        f"💡 Tip: Regular reflection helps you align your time with what truly matters.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    data[user_id]["last_reflect"] = datetime.datetime.now().isoformat()
    save_data(data)
async def plan_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"tasks": [], "reminders": []}

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /plan [your goal] [category]\nExample: /plan Prepare quarterly presentation family\nCategories: family, trading, marketing, content, learning, health, admin, general")
        return

    # Check if last argument is a known category
    known_categories = ["family", "trading", "marketing", "content", "learning", "health", "admin", "general"]
    category = "general"  # default

    if len(args) >= 2 and args[-1].lower() in known_categories:
        category = args[-1].lower()
        goal = " ".join(args[:-1])
    else:
        goal = " ".join(args)

    prompt = build_planning_prompt(goal, category)

    try:
        output = query_hf_model({"inputs": prompt, "parameters": {"max_new_tokens": 200}})
        plan = output[0]["generated_text"] if isinstance(output, list) else output.get("generated_text", "Planning failed...")
    except Exception as e:
        plan = f"Planning error: {str(e)}"

    await update.message.reply_text(
        f"🧠 <b>AI Plan for: \"{goal}\" [{category}]</b>\n\n{plan}\n\n"
        f"Next steps:\n"
        f"• Pick a subtask → /add \"[subtask]\" [time] [category]\n"
        f"• Need adjustments? Reply with what to change!",
        parse_mode='HTML'
    )

async def ai_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user_data = data.get(user_id, {"tasks": [], "reflections": []})
    
    recent_tasks = [t["text"] for t in user_data["tasks"][-5:] if not t["done"]]
    energy = 3
    time_of_day = datetime.datetime.now().strftime("%p")
    priorities = ["Work", "Family", "Health"]
    
    context = {
        "name": update.effective_user.first_name,
        "recent_tasks": recent_tasks or ["None recently"],
        "energy": energy,
        "time_of_day": time_of_day,
        "priorities": priorities
    }
    
    prompt = build_suggestion_prompt(context)
    
    try:
        output = query_hf_model({"inputs": prompt, "parameters": {"max_new_tokens": 150}})
        suggestion = output[0]["generated_text"] if isinstance(output, list) else output.get("generated_text", "Sorry, I couldn't generate a suggestion.")
    except Exception as e:
        suggestion = f"AI temporarily unavailable ({str(e)}). Try again later?"
    
    await update.message.reply_text(
        f"💡 <b>AI Suggestion for You</b>:\n\n{suggestion}\n\n"
        f"Like it? Try: /add \"[your version]\" [time]\n"
        f"Want tweaks? Reply with what to adjust!",
        parse_mode='HTML'
    )

async def assist_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /assist [task_id]\nSee /today for task IDs")
        return
    
    try:
        task_id = int(context.args[0])
    except:
        await update.message.reply_text("Please provide a valid task ID number")
        return
    
    user_id = str(update.effective_user.id)
    data = load_data()
    
    task = None
    for t in data.get(user_id, {}).get("tasks", []):
        if t["id"] == task_id and not t["done"]:
            task = t
            break
    
    if not task:
        await update.message.reply_text("Task not found or already done. Check /today.")
        return
    
    prompt = f"""
You are a supportive task coach. User is about to work on: "{task['text']}"
Give ONE specific, actionable tip to help them start or overcome a common hurdle.
Examples:
- For writing: "Start with the easiest section first to build momentum"
- For chores: "Put on one favorite song and see how much you can do before it ends"
- For work: "Set a 25-min timer - focus ONLY on this until it dings"
Keep it under 2 sentences. Be warm and practical.
    """.strip()
    
    try:
        output = query_hf_model({"inputs": prompt, "parameters": {"max_new_tokens": 100}})
        tip = output[0]["generated_text"] if isinstance(output, list) else output.get("generated_text", "Try breaking it into smaller steps!")
    except Exception as e:
        tip = f"Coach unavailable: {str(e)}"
    
    await update.message.reply_text(
        f"🎯 <b>Coach Tip for: \"{task['text']}\"</b>\n\n{tip}\n\n"
        f"When done: /done {task_id}\n"
        f"Stuck? Try /assist again for another tip!",
        parse_mode='HTML'
    )

async def reschedule_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        await update.message.reply_text("No tasks! Use /add first.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /reschedule <task_id> <new time>")
        return
    
    try:
        task_id = int(context.args[0])
        new_time_str = " ".join(context.args[1:])
    except:
        await update.message.reply_text("Usage: /reschedule <task_id> <new time>")
        return
    
    task = None
    for t in data[user_id]["tasks"]:
        if t["id"] == task_id:
            task = t
            break
    
    if not task:
        await update.message.reply_text("Task not found.")
        return
    
    try:
        now = datetime.datetime.now()
        if new_time_str.lower() == "tomorrow":
            target = now + datetime.timedelta(days=1)
            target = target.replace(hour=9, minute=0, second=0, microsecond=0)
        elif new_time_str.endswith("pm") or new_time_str.endswith("am"):
            hour = int(new_time_str[:-2])
            if new_time_str.endswith("pm") and hour != 12: hour += 12
            if new_time_str.endswith("am") and hour == 12: hour = 0
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target < now: target += datetime.timedelta(days=1)
        else:
            hour, minute = map(int, new_time_str.split(":"))
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now: target += datetime.timedelta(days=1)
    except:
        await update.message.reply_text("Couldn’t understand time. Try: '3pm', '15:00', or 'tomorrow 9am'")
        return
    
    task["time"] = target.isoformat()
    task["done"] = False
    
    reminder_time = target - datetime.timedelta(minutes=10)
    for r in data[user_id]["reminders"]:
        if r["task_id"] == task_id and not r["sent"]:
            r["time"] = reminder_time.isoformat()
            r["sent"] = False
            break
    
    save_data(data)
    await update.message.reply_text(
        f"📅 Rescheduled: \"{task['text']}\" to {target.strftime('%I:%M %p')}\n"
        f"Reminder set for 10 mins before."
    )

async def handle_reflection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not context.user_data.get("awaiting_reflection"):
        return
    
    task_id = context.user_data.pop("awaiting_reflection")
    data = load_data()
    user_data = data.get(user_id, {"tasks": [], "reflections": []})
    
    text = update.message.text.strip()
    lines = text.split("\n", 1)
    rating = lines[0] if lines else "3"
    notes = lines[1] if len(lines) > 1 else ""
    
    reflection = {
        "task_id": task_id,
        "task_text": next((t["text"] for t in user_data["tasks"] if t["id"] == task_id), "Unknown"),
        "rating": rating,
        "notes": notes,
        "timestamp": datetime.datetime.now().isoformat()
    }
    user_data.setdefault("reflections", []).append(reflection)
    data[user_id] = user_data
    save_data(data)
    
    insight = ""
    if rating in ["4", "5"]:
        insight = f"Great! Tasks like this energize you — consider scheduling more similar activities."
    elif rating in ["1", "2"]:
        insight = f"This drained you. Next time, try: breaking it smaller, doing it earlier, or pairing with joy."
    else:
        insight = f"Neutral effect. Notice what made it feel 'okay' vs. 'meh' next time."
    
    await update.message.reply_text(
        f"💡 <b>Learned from this:</b>\n{insight}\n\n"
        f"Your reflections help me suggest tasks that truly fit *you*.",
        parse_mode='HTML'
    )
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = load_data()
    
    if user_id not in data:
        await query.edit_message_text("Session expired. Try /start again.")
        return
    
    action, task_id_str = query.data.split("_", 1)
    task_id = int(task_id_str)
    
    task = None
    for t in data[user_id]["tasks"]:
        if t["id"] == task_id:
            task = t
            break
    
    if not task:
        await query.edit_message_text("Task not found.")
        return
    
    if action == "done":
        task["done"] = True
        await query.edit_message_text(f"🎉 Completed: \"{task['text']}\"! Well done.")
    elif action == "snooze":
        t_time = datetime.datetime.fromisoformat(task["time"])
        new_time = t_time + datetime.timedelta(minutes=30)
        task["time"] = new_time.isoformat()
        for r in data[user_id]["reminders"]:
            if r["task_id"] == task_id and not r["sent"]:
                r["time"] = (new_time - datetime.timedelta(minutes=10)).isoformat()
                break
        await query.edit_message_text(f"😴 Snoozed: \"{task['text']}\" to {new_time.strftime('%I:%M %p')}")
    elif action == "reschedule":
        await query.edit_message_text(
            f"To reschedule \"{task['text']}\", reply with:\n"
            f"/reschedule {task_id} <new time>\n"
            f"Example: /reschedule {task_id} tomorrow 2pm"
        )
    
    save_data(data)

def main():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("today", show_today))
    application.add_handler(CommandHandler("done", complete_task))
    application.add_handler(CommandHandler("snooze", snooze_task))
    application.add_handler(CommandHandler("reflect", weekly_reflect))
    application.add_handler(CommandHandler("ai suggest", ai_suggest))
    application.add_handler(CommandHandler("plan", plan_goal))
    application.add_handler(CommandHandler("assist", assist_task))
    application.add_handler(CommandHandler("reschedule", reschedule_task))
    
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reflection))
    
    job_queue = application.job_queue
    job_queue.run_repeating(check_reminders, interval=60, first=10)
    
    print("🤖 LifeBalance Bot is running...")
    application.run_polling()

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()
    data = load_data()
    
    for user_id, user_data in data.items():
        if "reminders" not in user_data:
            continue
            
        for reminder in user_data["reminders"]:
            if reminder["sent"]:
                continue
                
            remind_time = datetime.datetime.fromisoformat(reminder["time"])
            if now >= remind_time:
                task = None
                for t in user_data["tasks"]:
                    if t["id"] == reminder["task_id"]:
                        task = t
                        break
                
                if task and not task["done"]:
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Done", callback_data=f"done_{reminder['task_id']}"),
                            InlineKeyboardButton("😴 Snooze 30m", callback_data=f"snooze_{reminder['task_id']}"),
                            InlineKeyboardButton("⏭️ Reschedule", callback_data=f"reschedule_{reminder['task_id']}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"⏰ <b>Reminder:</b> {task['text']}\n"
                             f"Scheduled for: {datetime.datetime.fromisoformat(task['time']).strftime('%I:%M %p')}\n\n"
                             f"What’s your move?",
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                    reminder["sent"] = True
        
        save_data(data)

if __name__ == "__main__":
    main()
