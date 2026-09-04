# LifeBalance Bot

A Telegram bot designed to help maintain work and life balance through task management, planning, and reflection.

## Features

- **Task Management**: Add tasks with time and category (/add)
- **Daily View**: See today's tasks (/today)
- **Task Completion**: Mark tasks as done (/done)
- **Snooze**: Delay tasks by 30 minutes (/snooze)
- **AI Planning**: Break down goals into actionable steps (/plan)
- **AI Suggestions**: Get personalized task suggestions (/ai_suggest)
- **Assistance**: Get coaching tips mid-task (/assist)
- **Weekly Reflection**: Reflect on past week and plan ahead (/reflect)
- **Rescheduling**: Change task times (/reschedule)

## Category Support

Tasks can be organized into categories:
- family
- trading
- marketing
- content
- learning
- health
- admin
- general (default)

Example usage:
```
/add Pick up kids 3:30pm family
/plan Learn Python programming
/today
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   - `BOT_TOKEN`: Telegram Bot Token
   - `HF_TOKEN`: Hugging Face API Token (for NVIDIA models)
   - Optional: `DEFAULT_MODEL` (defaults to "nvidia/Llama3-ChatQA-1.5-8B")

3. Run the bot:
   ```bash
   python lifebalance_bot.py
   ```

## Commands

- `/start` - Welcome message and feature overview
- `/help` - Show all available commands
- `/add <task> <time> [category]` - Add a new task
- `/today` - View today's tasks
- `/done <task_id>` - Mark task as complete
- `/snooze <task_id>` - Delay task by 30 minutes
- `/plan [goal] [category]` - Get AI-generated plan for a goal
- `/ai_suggest` - Get AI-powered task suggestion
- `/assist [task_id]` - Get coaching tip mid-task
- `/reflect` - Weekly reflection (runs every Sunday)
- `/reschedule <task_id> <new time>` - Reschedule a task

## How It Works

The bot uses:
- Telegram Bot API for user interaction
- Hugging Face Inference API with NVIDIA models for AI capabilities
- JSON file (`user_data.json`) for persistent storage
- Python's datetime module for time management

## Notes

- Times can be specified as: "3pm", "15:00", "tomorrow 9am"
- Categories are optional and default to "general"
- The bot sends reminders 10 minutes before scheduled tasks
- Completed tasks are tracked for weekly reflection insights

## Deployment on Railway

1. Create a new Railway account at https://railway.app
2. Click "New Project" and select "Deploy from GitHub"
3. Connect your GitHub repository containing this bot
4. Railway will automatically detect the Python project and:
   - Install dependencies from `requirements.txt`
   - Use the Procfile command: `web: python lifebalance_bot.py`
5. Set environment variables in the Railway dashboard:
   - Go to your project's "Variables" tab
   - Add:
     - `BOT_TOKEN`: Your Telegram Bot Token (from @BotFather)
     - `HF_TOKEN`: Your Hugging Face API Token (for AI features)
6. Deploy! Railway will build and deploy your bot automatically.

### Important Notes for Railway:
- The bot uses long-polling to communicate with Telegram, which works well on Railway's always-on instances.
- Ensure your project is set to "Always On" in Railway settings to prevent sleeping.
- The bot stores data in `user_data.json` which will persist across redeploys as long as the volume is not cleared.
- For persistent storage beyond redeploys, consider using Railway's Volumes or a database (though the current JSON file approach works for personal use).

### Troubleshooting on Railway:
- If the bot fails to start, check the logs in the Railway dashboard
- Common issues:
  - Missing BOT_TOKEN or HF_TOKEN environment variables
  - Network issues preventing Telegram API calls
  - Memory limits (the bot is lightweight and should stay within Railway's free tier limits)
