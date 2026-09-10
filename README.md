# LifeBalance Bot

<div align="center">
  <svg width="240" height="240" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="lifeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#667eea">
          <animate attributeName="stop-color" values="#667eea;#764ba2;#f093fb;#f5576c;#667eea" dur="6s" repeatCount="indefinite"/>
        </stop>
        <stop offset="100%" stop-color="#764ba2">
          <animate attributeName="stop-color" values="#764ba2;#f093fb;#f5576c;#667eea;#764ba2" dur="6s" repeatCount="indefinite"/>
        </stop>
      </linearGradient>
      <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#4facfe"/>
        <stop offset="100%" stop-color="#00f2fe"/>
      </linearGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="4" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <filter id="softGlow">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    
    <!-- Outer rotating rings -->
    <g transform="translate(120, 120)">
      <ellipse rx="100" ry="25" fill="none" stroke="url(#ringGrad)" stroke-width="1.5" opacity="0.4" stroke-dasharray="8 4">
        <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="20s" repeatCount="indefinite"/>
      </ellipse>
      <ellipse rx="80" ry="20" fill="none" stroke="url(#ringGrad)" stroke-width="1" opacity="0.3" stroke-dasharray="6 6">
        <animateTransform attributeName="transform" type="rotate" from="360" to="0" dur="15s" repeatCount="indefinite"/>
      </ellipse>
      <ellipse rx="60" ry="15" fill="none" stroke="url(#ringGrad)" stroke-width="0.8" opacity="0.2" stroke-dasharray="4 8">
        <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="12s" repeatCount="indefinite"/>
      </ellipse>
    </g>
    
    <!-- Floating particles -->
    <g transform="translate(120, 120)">
      <circle r="3" fill="#4facfe" opacity="0.8">
        <animate attributeName="cx" values="0;80;0;-80;0" dur="8s" repeatCount="indefinite"/>
        <animate attributeName="cy" values="-80;0;80;0;-80" dur="8s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.3;0.9;0.3;0.9;0.3" dur="8s" repeatCount="indefinite"/>
      </circle>
      <circle r="2.5" fill="#f093fb" opacity="0.7">
        <animate attributeName="cx" values="0;-70;0;70;0" dur="10s" repeatCount="indefinite"/>
        <animate attributeName="cy" values="70;0;-70;0;70" dur="10s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.2;0.8;0.2;0.8;0.2" dur="10s" repeatCount="indefinite"/>
      </circle>
      <circle r="2" fill="#00f2fe" opacity="0.6">
        <animate attributeName="cx" values="0;60;0;-60;0" dur="7s" repeatCount="indefinite"/>
        <animate attributeName="cy" values="-60;0;60;0;-60" dur="7s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.4;1;0.4;1;0.4" dur="7s" repeatCount="indefinite"/>
      </circle>
    </g>
    
    <!-- Central pulsing orb -->
    <circle cx="120" cy="120" r="50" fill="url(#lifeGrad)" filter="url(#glow)">
      <animate attributeName="r" values="45;55;45" dur="3s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.8;1;0.8" dur="3s" repeatCount="indefinite"/>
    </circle>
    
    <!-- Inner core -->
    <circle cx="120" cy="120" r="28" fill="#ffffff" opacity="0.15">
      <animate attributeName="r" values="25;32;25" dur="3s" repeatCount="indefinite"/>
    </circle>
    
    <!-- Balance symbol -->
    <g transform="translate(120, 120)">
      <path d="M0 -20 L0 20 M-15 -5 L15 -5 M-10 5 L10 5 M-5 15 L5 15" stroke="#ffffff" stroke-width="2" stroke-linecap="round" opacity="0.9">
        <animate attributeName="stroke-dashoffset" values="0;20;0" dur="4s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.7;1;0.7" dur="4s" repeatCount="indefinite"/>
      </path>
    </g>
  </svg>

  <h1>🌿 LifeBalance Bot</h1>
  <p><strong>Tap, don't type. Balance work & life effortlessly.</strong></p>
  <p>Your intelligent Telegram companion for task management, focus sessions, AI coaching & life insights.</p>
</div>

<!-- Animated wave separator -->
<svg viewBox="0 0 1200 120" preserveAspectRatio="none" style="width:100%;height:60px;display:block;margin:-10px 0;">
  <defs>
    <linearGradient id="waveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#667eea"/>
      <stop offset="50%" stop-color="#f093fb"/>
      <stop offset="100%" stop-color="#4facfe"/>
    </linearGradient>
  </defs>
  <path d="M0 60 Q 300 100 600 60 T 1200 60 V120 H0 Z" fill="url(#waveGrad)" opacity="0.3">
    <animate attributeName="d" dur="8s" repeatCount="indefinite"
      values="M0 60 Q 300 100 600 60 T 1200 60 V120 H0 Z;
              M0 40 Q 300 80 600 40 T 1200 40 V120 H0 Z;
              M0 60 Q 300 100 600 60 T 1200 60 V120 H0 Z" />
  </path>
</svg>

<div align="center">
  
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.0-0088CC?style=for-the-badge&logo=telegram&logoColor=white)](https://github.com/python-telegram-bot/python-telegram-bot)
[![APScheduler](https://img.shields.io/badge/APScheduler-3.10-009688?style=for-the-badge)](https://apscheduler.readthedocs.io)
[![Railway](https://img.shields.io/badge/Deploy%20on-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/printezy247/lifebalance-bot?style=for-the-badge&logo=github&logoColor=white)](https://github.com/printezy247/lifebalance-bot/stargazers)
[![Forks](https://img.shields.io/github/forks/printezy247/lifebalance-bot?style=for-the-badge&logo=github&logoColor=white)](https://github.com/printezy247/lifebalance-bot/network/members)
[![Issues](https://img.shields.io/github/issues/printezy247/lifebalance-bot?style=for-the-badge&logo=github&logoColor=white)](https://github.com/printezy247/lifebalance-bot/issues)

</div>

---

## ✨ The Promise

<div align="center">
  <svg width="800" height="200" viewBox="0 0 800 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="promiseGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#667eea"/>
        <stop offset="50%" stop-color="#764ba2"/>
        <stop offset="100%" stop-color="#f093fb"/>
      </linearGradient>
      <filter id="cardGlow">
        <feGaussianBlur stdDeviation="6" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <filter id="textGlow">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    
    <!-- Background cards -->
    <rect x="20" y="20" width="760" height="160" rx="24" fill="#0a0e1a" stroke="url(#promiseGrad)" stroke-width="2" filter="url(#cardGlow)" opacity="0.9"/>
    
    <!-- Animated top bar -->
    <rect x="20" y="20" width="760" height="4" rx="2" fill="url(#promiseGrad)">
      <animate attributeName="opacity" values="0.6;1;0.6" dur="2s" repeatCount="indefinite"/>
    </rect>
    
    <!-- Title -->
    <text x="400" y="70" text-anchor="middle" fill="url(#promiseGrad)" font-family="Segoe UI, system-ui, sans-serif" font-weight="800" font-size="28" filter="url(#textGlow)">⚡ ONE BOT · ZERO FRICTION · INSTANT BALANCE</text>
    
    <!-- Pillars -->
    <g font-family="Segoe UI, system-ui, sans-serif" font-size="11" fill="#e2e8f0">
      <text x="80" y="115" text-anchor="middle" font-weight="600">🎯 Tap-to-Act</text>
      <text x="80" y="130" text-anchor="middle" fill="#94a3b8" font-size="9">Buttons, not commands</text>
      
      <text x="240" y="115" text-anchor="middle" font-weight="600">🤖 AI Coach</text>
      <text x="240" y="130" text-anchor="middle" fill="#94a3b8" font-size="9">Smart suggestions</text>
      
      <text x="400" y="115" text-anchor="middle" font-weight="600">📊 Auto Insights</text>
      <text x="400" y="130" text-anchor="middle" fill="#94a3b8" font-size="9">Pattern detection</text>
      
      <text x="560" y="115" text-anchor="middle" font-weight="600">⏰ Smart Reminders</text>
      <text x="560" y="130" text-anchor="middle" fill="#94a3b8" font-size="9">Quiet-hour aware</text>
      
      <text x="720" y="115" text-anchor="middle" font-weight="600">🔒 Local-First</text>
      <text x="720" y="130" text-anchor="middle" fill="#94a3b8" font-size="9">Your data, your control</text>
    </g>
    
    <!-- Pulsing indicator -->
    <circle cx="400" cy="35" r="5" fill="#00ffa3">
      <animate attributeName="r" values="5;9;5" dur="1.5s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="1;0.4;1" dur="1.5s" repeatCount="indefinite"/>
    </circle>
    <text x="400" y="48" text-anchor="middle" fill="#00ffa3" font-family="Segoe UI" font-weight="700" font-size="9">LIVE</text>
  </svg>
</div>

---

## 🚀 Quick Start

### Zero-Config Deploy (Railway)

```bash
# 1. Fork this repo
# 2. New Project → Deploy from GitHub → Select lifebalance-bot
# 3. Add Volume: mount path /data
# 4. Set env vars (see below)
# 5. Deploy → Done!
```

**Required:** `BOT_TOKEN` (from [@BotFather](https://t.me/BotFather))  
**Strongly recommended:** `DATA_DIR=/data`, `BOT_TZ=Asia/Kuala_Lumpur`  
**Optional AI:** `HF_TOKEN`, `AI_MODEL=meta-llama/Llama-3.1-8B-Instruct`

<details>
<summary><strong>📋 Full Environment Variables</strong></summary>

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *required* | Telegram bot token |
| `DATA_DIR` | `.` | **Must be a mounted volume** for persistence |
| `BOT_TZ` | `UTC` | IANA timezone (e.g. `Asia/Kuala_Lumpur`) |
| `HF_TOKEN` | — | HuggingFace token for AI features |
| `AI_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | OpenAI-compatible model |
| `AI_BASE_URL` | `https://router.huggingface.co/v1/chat/completions` | API endpoint |
| `AI_TIMEOUT` | `45` | Request timeout (seconds) |
| `QUIET_START` / `QUIET_END` | `22` / `7` | Quiet hours (0-23, equal = disabled) |
| `BRIEFING_ENABLED` / `BRIEFING_HOUR` | `1` / `7` | Morning briefing toggle & hour |
| `WINDDOWN_ENABLED` / `WINDDOWN_HOUR` | `1` / `21` | Evening wind-down toggle & hour |
| `DIGEST_ENABLED` / `DIGEST_DAY` / `DIGEST_HOUR` | `1` / `0` / `19` | Weekly digest (Day 0=Sunday) |
| `NUDGE_ENABLED` / `NUDGE_AFTER_MINUTES` | `1` / `30` | Overdue nudges |
| `BACKUP_ENABLED` / `BACKUP_HOUR` / `BACKUP_KEEP` | `1` / `3` / `14` | Daily backups, retention |
| `FOCUS_DEFAULT` / `FOCUS_MAX` | `25` / `180` | Focus timer defaults (minutes) |

</details>

---

## ⚡ Core Features

<div align="center">
  <svg width="900" height="420" viewBox="0 0 900 420" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="featGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#667eea"/>
        <stop offset="100%" stop-color="#764ba2"/>
      </linearGradient>
      <linearGradient id="featGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#f093fb"/>
        <stop offset="100%" stop-color="#f5576c"/>
      </linearGradient>
      <linearGradient id="featGrad3" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#4facfe"/>
        <stop offset="100%" stop-color="#00f2fe"/>
      </linearGradient>
      <linearGradient id="featGrad4" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#43e97b"/>
        <stop offset="100%" stop-color="#38f9d7"/>
      </linearGradient>
      <linearGradient id="featGrad5" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#fa709a"/>
        <stop offset="100%" stop-color="#fee140"/>
      </linearGradient>
      <filter id="featGlow">
        <feGaussianBlur stdDeviation="4" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>

    <!-- Feature 1: Tap-to-Act Tasks -->
    <g transform="translate(30, 20)" filter="url(#featGlow)">
      <rect x="0" y="0" width="260" height="180" rx="16" fill="url(#featGrad1)" opacity="0.15" stroke="url(#featGrad1)" stroke-width="1.5"/>
      <circle cx="130" cy="50" r="35" fill="url(#featGrad1)" opacity="0.2">
        <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite"/>
      </circle>
      <text x="130" y="55" text-anchor="middle" font-size="28">📋</text>
      <text x="130" y="105" text-anchor="middle" fill="#e2e8f0" font-family="Segoe UI" font-weight="700" font-size="14">Tap-to-Act Tasks</text>
      <text x="130" y="125" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI" font-size="10">/today shows buttons<br/>Done · Snooze · Coach · Reschedule</text>
      <text x="130" y="155" text-anchor="middle" fill="#667eea" font-family="Segoe UI" font-weight="600" font-size="9">Persistent keyboard • Natural time parsing</text>
    </g>

    <!-- Feature 2: AI Coaching -->
    <g transform="translate(320, 20)" filter="url(#featGlow)">
      <rect x="0" y="0" width="260" height="180" rx="16" fill="url(#featGrad2)" opacity="0.15" stroke="url(#featGrad2)" stroke-width="1.5"/>
      <circle cx="130" cy="50" r="35" fill="url(#featGrad2)" opacity="0.2">
        <animate attributeName="r" values="32;38;32" dur="3.5s" repeatCount="indefinite"/>
      </circle>
      <text x="130" y="55" text-anchor="middle" font-size="28">🤖</text>
      <text x="130" y="105" text-anchor="middle" fill="#e2e8f0" font-family="Segoe UI" font-weight="700" font-size="14">AI Coaching</text>
      <text x="130" y="125" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI" font-size="10">/suggest · /plan · /assist<br/>Energy-weighted suggestions</text>
      <text x="130" y="155" text-anchor="middle" fill="#f093fb" font-family="Segoe UI" font-weight="600" font-size="9">OpenAI-compatible • Any endpoint</text>
    </g>

    <!-- Feature 3: Focus Timer -->
    <g transform="translate(610, 20)" filter="url(#featGlow)">
      <rect x="0" y="0" width="260" height="180" rx="16" fill="url(#featGrad3)" opacity="0.15" stroke="url(#featGrad3)" stroke-width="1.5"/>
      <circle cx="130" cy="50" r="35" fill="url(#featGrad3)" opacity="0.2">
        <animate attributeName="r" values="32;38;32" dur="2.5s" repeatCount="indefinite"/>
      </circle>
      <text x="130" y="55" text-anchor="middle" font-size="28">⏱️</text>
      <text x="130" y="105" text-anchor="middle" fill="#e2e8f0" font-family="Segoe UI" font-weight="700" font-size="14">Focus Timer</text>
      <text x="130" y="125" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI" font-size="10">/focus [min] [label]<br/>Pomodoro-style blocks</text>
      <text x="130" y="155" text-anchor="middle" fill="#4facfe" font-family="Segoe UI" font-weight="600" font-size="9">Configurable defaults • Stop anytime</text>
    </g>

    <!-- Feature 4: Auto Insights -->
    <g transform="translate(30, 230)" filter="url(#featGlow)">
      <rect x="0" y="0" width="260" height="170" rx="16" fill="url(#featGrad4)" opacity="0.15" stroke="url(#featGrad4)" stroke-width="1.5"/>
      <circle cx="130" cy="45" r="35" fill="url(#featGrad4)" opacity="0.2">
        <animate attributeName="r" values="32;38;32" dur="4s" repeatCount="indefinite"/>
      </circle>
      <text x="130" y="50" text-anchor="middle" font-size="28">📊</text>
      <text x="130" y="100" text-anchor="middle" fill="#e2e8f0" font-family="Segoe UI" font-weight="700" font-size="14">Auto Insights</text>
      <text x="130" y="120" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI" font-size="10">Balance • Burnout • Neglect<br/>Fires only after thresholds met</text>
      <text x="130" y="150" text-anchor="middle" fill="#43e97b" font-family="Segoe UI" font-weight="600" font-size="9">Silent first week • Data-driven</text>
    </g>

    <!-- Feature 5: Smart Scheduling -->
    <g transform="translate(320, 230)" filter="url(#featGlow)">
      <rect x="0" y="0" width="260" height="170" rx="16" fill="url(#featGrad5)" opacity="0.15" stroke="url(#featGrad5)" stroke-width="1.5"/>
      <circle cx="130" cy="45" r="35" fill="url(#featGrad5)" opacity="0.2">
        <animate attributeName="r" values="32;38;32" dur="3.2s" repeatCount="indefinite"/>
      </circle>
      <text x="130" y="50" text-anchor="middle" font-size="28">⏰</text>
      <text x="130" y="100" text-anchor="middle" fill="#e2e8f0" font-family="Segoe UI" font-weight="700" font-size="14">Smart Scheduling</text>
      <text x="130" y="120" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI" font-size="10">Briefing • Wind-down • Digest<br/>Quiet-hour aware • Per-user</text>
      <text x="130" y="150" text-anchor="middle" fill="#fa709a" font-family="Segoe UI" font-weight="600" font-size="9">Preview commands • Timezone-aware</text>
    </g>

    <!-- Feature 6: Data Ownership -->
    <g transform="translate(610, 230)" filter="url(#featGlow)">
      <rect x="0" y="0" width="260" height="170" rx="16" fill="#ffd89b" opacity="0.15" stroke="#ffd89b" stroke-width="1.5"/>
      <circle cx="130" cy="45" r="35" fill="#ffd89b" opacity="0.2">
        <animate attributeName="r" values="32;38;32" dur="3.8s" repeatCount="indefinite"/>
      </circle>
      <text x="130" y="50" text-anchor="middle" font-size="28">🔒</text>
      <text x="130" y="100" text-anchor="middle" fill="#e2e8f0" font-family="Segoe UI" font-weight="700" font-size="14">Data Ownership</text>
      <text x="130" y="120" text-anchor="middle" fill="#94a3b8" font-family="Segoe UI" font-size="10">Single JSON + atomic writes<br/>Daily encrypted backups</text>
      <text x="130" y="150" text-anchor="middle" fill="#ffd89b" font-family="Segoe UI" font-weight="600" font-size="9">Git-ignored • One-file restore</text>
    </g>
  </svg>
</div>

---

## 📋 Command Reference

<details open>
<summary><strong>🎯 Basics</strong></summary>

| Command | Description |
|---|---|
| `/start` | Welcome + persistent keyboard |
| `/help` | All commands, schedule, timezone |

</details>

<details>
<summary><strong>📝 Tasks</strong></summary>

| Command | Description | Example |
|---|---|---|
| `/add <task> <time> [cat]` | Add task | `/add Call mom 3:30pm family` |
| `/today` | Today's tasks as buttons | — |
| `/week` | Weekly progress bars + streak | — |
| `/done <id>` | Complete + rate energy 1-5 | `/done 3` |
| `/snooze <id>` | Delay 30 minutes | `/snooze 3` |
| `/reschedule <id> <time>` | Move task | `/reschedule 3 tomorrow 9am` |

**Time formats:** `3pm`, `3:30pm`, `15:00`, `tomorrow`, `tomorrow 9am`  
**Categories:** `family` `trading` `marketing` `content` `learning` `health` `admin` `general`

</details>

<details>
<summary><strong>⏱️ Focus</strong></summary>

| Command | Description |
|---|---|
| `/focus` | Start timer (default minutes) |
| `/focus 50` | 50-minute block |
| `/focus 50 deep work` | Timer with label |
| `/focus stop` | Cancel running timer |

</details>

<details>
<summary><strong>🤖 AI</strong></summary>

| Command | Description |
|---|---|
| `/suggest` | Task suggestion (energy-weighted) |
| `/ai_suggest` | Alias for backwards compat |
| `/plan <goal> [cat]` | Break goal into subtasks |
| `/assist <id>` | Coaching tip for task |

</details>

<details>
<summary><strong>🧠 Reflection & Settings</strong></summary>

| Command | Description |
|---|---|
| `/reflect` | Guided reflection prompt |
| `/settings` | Toggle automations, quiet hours |
| `/brief` | Preview morning briefing |
| `/winddown` | Preview evening wind-down |
| `/digest` | Preview weekly digest |

</details>

---

## 🔄 Automations

<div align="center">
  <svg width="900" height="200" viewBox="0 0 900 200" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="autoGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#667eea"/>
        <stop offset="50%" stop-color="#764ba2"/>
        <stop offset="100%" stop-color="#f093fb"/>
      </linearGradient>
    </defs>
    
    <rect x="10" y="10" width="880" height="180" rx="16" fill="#0a0e1a" stroke="url(#autoGrad)" stroke-width="1.5"/>
    
    <text x="450" y="40" text-anchor="middle" fill="url(#autoGrad)" font-family="Segoe UI" font-weight="800" font-size="18">⚙️ AUTOMATED WORKFLOWS</text>
    
    <!-- Automation items -->
    <g font-family="Segoe UI, system-ui, sans-serif" font-size="10" fill="#e2e8f0">
      <text x="60" y="75" text-anchor="middle" font-weight="600" fill="#4facfe">🔔</text>
      <text x="60" y="90" text-anchor="middle" font-weight="600">Task Reminder</text>
      <text x="60" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">10 min before</text>
      <text x="60" y="120" text-anchor="middle" fill="#00ffa3" font-size="8">Exempt from quiet hours</text>
      
      <text x="220" y="75" text-anchor="middle" font-weight="600" fill="#f093fb">⚠️</text>
      <text x="220" y="90" text-anchor="middle" font-weight="600">Overdue Nudge</text>
      <text x="220" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">30 min after due</text>
      <text x="220" y="120" text-anchor="middle" fill="#fa709a" font-size="8">Fires once per task</text>
      
      <text x="380" y="75" text-anchor="middle" font-weight="600" fill="#43e97b">🌅</text>
      <text x="380" y="90" text-anchor="middle" font-weight="600">Morning Briefing</text>
      <text x="380" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">07:00 daily</text>
      <text x="380" y="120" text-anchor="middle" fill="#43e97b" font-size="8">Tasks + streak + focus</text>
      
      <text x="540" y="75" text-anchor="middle" font-weight="600" fill="#fee140">🌙</text>
      <text x="540" y="90" text-anchor="middle" font-weight="600">Evening Wind-down</text>
      <text x="540" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">21:00 daily</text>
      <text x="540" y="120" text-anchor="middle" fill="#fee140" font-size="8">Recap + roll forward</text>
      
      <text x="700" y="75" text-anchor="middle" font-weight="600" fill="#667eea">📅</text>
      <text x="700" y="90" text-anchor="middle" font-weight="600">Weekly Digest</text>
      <text x="700" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">Sun 19:00</text>
      <text x="700" y="120" text-anchor="middle" fill="#667eea" font-size="8">Stats + reflection</text>
      
      <text x="860" y="75" text-anchor="middle" font-weight="600" fill="#fa709a">💾</text>
      <text x="860" y="90" text-anchor="middle" font-weight="600">Auto Backup</text>
      <text x="860" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">03:00 daily</text>
      <text x="860" y="120" text-anchor="middle" fill="#fa709a" font-size="8">Keep 14 snapshots</text>
    </g>
  </svg>
</div>

---

## 🧠 Insight Engine

| Insight | Trigger Condition | Action |
|---|---|---|
| **⚖️ Balance** | 8 tasks in 14 days, one category > 60% | Suggests diversification |
| **🔥 Burnout** | 4 energy ratings in 7 days, avg < 2.5 | Recommends rest / lighter load |
| **👁️ Neglect** | Watched category silent 10+ days | Gentle nudge to revisit |

> **Note:** Insights stay silent during the first week on fresh installs — this is intentional. The bot learns your patterns before speaking up.

---

## 🛠️ Local Development

```bash
# 1. Clone & enter
git clone https://github.com/printezy247/lifebalance-bot.git
cd lifebalance-bot

# 2. Virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate      # macOS/Linux

# 3. Install deps
pip install -r requirements.txt

# 4. Create .env (git-ignored)
cat > .env << 'EOF'
BOT_TOKEN=your_token_from_botfather
BOT_TZ=Asia/Kuala_Lumpur
DATA_DIR=./local-data
HF_TOKEN=your_hf_token_optional
EOF

# 5. Run
python lifebalance_bot.py
```

> ⚠️ Only one instance may poll a given bot token. Stop Railway service or use a second token for local dev.

---

## 📦 Project Structure

```
lifebalance-bot/
├── lifebalance_bot.py      # Main entry point (long-polling worker)
├── requirements.txt        # Pinned minimal deps
├── Procfile                # Railway: worker: python lifebalance_bot.py
├── .python-version         # Pinned Python 3.11
├── .gitignore              # Ignores data/, backups/, .env, __pycache__
├── LICENSE                 # MIT
└── README.md               # You are here
```

**Runtime files (git-ignored, created at runtime):**
```
data/
├── user_data.json          # Single atomic JSON store
└── backups/
    ├── user_data_20260911_030000.json
    └── ...
```

---

## 🏗️ Architecture Highlights

<div align="center">
  <svg width="800" height="180" viewBox="0 0 800 180" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="archGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#667eea"/>
        <stop offset="50%" stop-color="#764ba2"/>
        <stop offset="100%" stop-color="#f093fb"/>
      </linearGradient>
      <filter id="archGlow">
        <feGaussianBlur stdDeviation="3" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    
    <rect x="10" y="10" width="780" height="160" rx="16" fill="#0a0e1a" stroke="url(#archGrad)" stroke-width="1.5"/>
    <text x="400" y="38" text-anchor="middle" fill="url(#archGrad)" font-family="Segoe UI" font-weight="800" font-size="16">🏗️ TECHNICAL ARCHITECTURE</text>
    
    <g font-family="Segoe UI, system-ui, sans-serif" font-size="10" fill="#e2e8f0">
      <!-- Row 1 -->
      <text x="80" y="75" text-anchor="middle" font-weight="600" fill="#4facfe">📦</text>
      <text x="80" y="90" text-anchor="middle" font-weight="600">Single Process</text>
      <text x="80" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">Long-polling worker</text>
      <text x="80" y="120" text-anchor="middle" fill="#4facfe" font-size="8">No webhook needed</text>
      
      <text x="240" y="75" text-anchor="middle" font-weight="600" fill="#f093fb">🧵</text>
      <text x="240" y="90" text-anchor="middle" font-weight="600">Thread-Safe</text>
      <text x="240" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">RLock + atomic writes</text>
      <text x="240" y="120" text-anchor="middle" fill="#f093fb" font-size="8">temp file + os.replace</text>
      
      <text x="400" y="75" text-anchor="middle" font-weight="600" fill="#43e97b">⏰</text>
      <text x="400" y="90" text-anchor="middle" font-weight="600">APScheduler</text>
      <text x="400" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">Timezone-aware jobs</text>
      <text x="400" y="120" text-anchor="middle" fill="#43e97b" font-size="8">Cron + interval triggers</text>
      
      <text x="560" y="75" text-anchor="middle" font-weight="600" fill="#fee140">🤖</text>
      <text x="560" y="90" text-anchor="middle" font-weight="600">AI Layer</text>
      <text x="560" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">OpenAI-compatible</text>
      <text x="560" y="120" text-anchor="middle" fill="#fee140" font-size="8">Pluggable endpoint</text>
      
      <text x="720" y="75" text-anchor="middle" font-weight="600" fill="#fa709a">🔒</text>
      <text x="720" y="90" text-anchor="middle" font-weight="600">Privacy First</text>
      <text x="720" y="105" text-anchor="middle" fill="#94a3b8" font-size="9">Local JSON only</text>
      <text x="720" y="120" text-anchor="middle" fill="#fa709a" font-size="8">No external DB</text>
    </g>
  </svg>
</div>

---

## 🐛 Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Tasks vanish after deploy | `DATA_DIR` unset / no volume | Attach volume at `/data`, set `DATA_DIR=/data` |
| Reminders at wrong hour | `BOT_TZ` unset | Set IANA timezone (e.g. `Asia/Kuala_Lumpur`) |
| Briefing/digest never arrives | Inside quiet hours or toggled off | Check `/settings` or adjust schedule |
| `AI unavailable - token missing` | `HF_TOKEN` lacks Inference permission | Enable **Inference Providers** in HF settings |
| `AI unavailable - out of credits` | Free tier exhausted | Resets monthly or add credits |
| `model '...' not served` | Model unavailable | Change `AI_MODEL` |
| Connection errors | `AI_BASE_URL` wrong | Verify endpoint URL |
| Nudges silent at night | Working as designed | Quiet hours exempt reminders only |
| Insights never appear | Below data thresholds | Wait for enough history |

---

## 📝 Maintainer Notes

- **Don't pin** `httpx`, `httpcore`, `anyio` — PTB manages compatible versions
- Python version pinned in `.python-version` — leave unpinned at your own risk
- `tzdata` required (zoneinfo lacks tz DB on slim Linux images)
- Jobs must not hold data across `await` — `load_data`/`save_data` are sync
- Callback data limited to 64 bytes — use namespaces (`t:`, `nav:`, `dash:`)
- **HTML-escape all user text** before insertion — otherwise Telegram rejects
- PTB schedule mapping: Sunday-Saturday (v20+) — use explicit `tzinfo`

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feat/amazing-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <svg width="400" height="60" viewBox="0 0 400 60" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="footGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#667eea">
          <animate attributeName="stop-color" values="#667eea;#764ba2;#f093fb;#f5576c;#667eea" dur="8s" repeatCount="indefinite"/>
        </stop>
        <stop offset="100%" stop-color="#764ba2">
          <animate attributeName="stop-color" values="#764ba2;#f093fb;#f5576c;#667eea;#764ba2" dur="8s" repeatCount="indefinite"/>
        </stop>
      </linearGradient>
    </defs>
    <text x="200" y="35" text-anchor="middle" font-family="Segoe UI, system-ui, sans-serif" font-weight="800" font-size="20" fill="url(#footGrad)">printezy · lifebalance-bot</text>
    <text x="200" y="52" text-anchor="middle" font-family="Segoe UI" font-size="10" fill="#64748b">Built for balance. Free forever. No subscriptions.</text>
  </svg>
  <br><br>
  <sub>Educational & personal productivity tool. Not professional advice.</sub>
</div>