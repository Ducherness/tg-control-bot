# 🎮 Telegram PC Control Bot

Remote control your Windows PC from Telegram with Wake-on-LAN, screenshots, system stats, volume control, and more.

## ✨ Features

| Command | Description |
|---------|-------------|
| 🚀 **Wake** | Send Wake-on-LAN magic packet |
| 🛑 **Shutdown** | Remote system shutdown |
| 😴 **Sleep** | Put PC to sleep |
| 📸 **Screen** | Capture remote screenshot |
| 📋 **Clipboard** | View last 5 copied items |
| 📊 **Stats** | View CPU, RAM, Disk usage |
| 🔊 **Volume** | Control system volume |
| 🔍 **Status** | Check PC & Agent connectivity |
| 🎤 **Voice** | Voice commands via AI |

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   Telegram Bot  │◄───────►│   Windows PC    │
│  (Linux Server) │   HTTP  │   (Agent.py)    │
└─────────────────┘         └─────────────────┘
       │                           │
       │                           ├── Screenshot
       │                           ├── Clipboard
       │                           ├── Volume
       │                           ├── Stats
       │                           └── Shutdown/Sleep
       │
       └── Wake-on-LAN (UDP)
```

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Ducherness/tg-control-bot.git
cd tg-control-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```env
BOT_TOKEN=your_telegram_bot_token
TARGET_MAC=AA:BB:CC:DD:EE:FF
TARGET_HOST=192.168.0.102
AGENT_PORT=8000
ALLOWED_USERS=123456789,987654321
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram Bot token from [@BotFather](https://t.me/BotFather) |
| `TARGET_MAC` | MAC address of PC for Wake-on-LAN |
| `TARGET_HOST` | IP address of your Windows PC |
| `AGENT_PORT` | Port for Agent (default: 8000) |
| `ALLOWED_USERS` | Comma-separated Telegram user IDs |
| `OPENROUTER_API_KEY` | API key for voice command AI |
| `OPENROUTER_MODEL` | AI model for intent parsing |

### 4. Download Vosk model (for voice commands)

```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
```

## 🚀 Running

### On Windows PC (Agent)

```bash
python agent.py
```

Or run hidden in background:
```bash
wscript start_agent_hidden.vbs
```

### On Linux Server (Bot)

```bash
python main.py
```

## 📁 Project Structure

```
tg-control-bot/
├── agent.py              # Windows agent (Flask API)
├── main.py               # Telegram bot entry point
├── bot/
│   ├── handlers.py       # Command handlers
│   ├── config.py         # Environment config
│   ├── ai.py             # AI intent parser
│   ├── voice.py          # Speech-to-text
│   └── wol.py            # Wake-on-LAN
├── models/               # Vosk speech models
├── requirements.txt
├── start_agent.bat
├── start_agent_hidden.vbs
└── .env
```

## 🔧 Agent Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Health check |
| `/shutdown` | POST | Shutdown PC |
| `/sleep` | POST | Sleep PC |
| `/screenshot` | GET | Capture screen (JPEG) |
| `/clipboard` | GET | Get clipboard history |
| `/stats` | GET | Get system stats |
| `/volume` | POST | Control volume |

### Volume Actions

```json
{"action": "get"}           // Get current volume
{"action": "set", "level": 0.5}  // Set volume (0.0 - 1.0)
{"action": "mute"}          // Toggle mute
```

## 🎤 Voice Commands

Send a voice message to the bot. Supported commands:
- "Turn on my computer" → Wake
- "Shut it down" → Shutdown
- "Take a screenshot" → Screenshot
- "Show me CPU usage" → Stats
- "What's on my clipboard" → Clipboard
- "Mute the volume" → Volume

## 🔒 Security

- Only users listed in `ALLOWED_USERS` can control the bot
- Agent runs on local network only by default
- No authentication on Agent (use firewall rules)

---

## 📋 TODO / Roadmap

### 🔐 Security
- [ ] IP whitelist for Agent
- [ ] Two-factor confirmation (PIN + Telegram ID)
- [ ] `/panic` — instant shutdown
- [ ] Auto-lock on new device login

### 🗣️ Natural Language Control
Complex multi-step commands:
```
"Close all browsers and put PC to sleep"
```
AI generates action plan:
```json
[
  { "action": "close", "target": "browser" },
  { "action": "sleep" }
]
```

### 🧩 Context Memory
```
User: "включи компьютер"
User: "подожди 10 минут"  
User: "а теперь выключи"
```
Bot understands "а теперь" refers to the same PC.

### 🧍 Wake-word (Future)
```
"Assistant, turn on my PC"
```
Voice activation via microphone, without Telegram.

### ⏱️ Timers & Scenarios
- [ ] `"выключи через 30 минут"`
- [ ] `"каждый день в 23:00 sleep"`
- [ ] `"если CPU > 90% → уведомить"`

### 🛠️ Dev / Ops
- [ ] `/logs` — last 100 lines
- [ ] `/restart_bot`
- [ ] `/update` — git pull + restart
- [ ] `/health`

---

## 📄 License

MIT License
