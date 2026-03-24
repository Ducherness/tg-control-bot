# Telegram PC Control Bot

Remote control a Windows PC from Telegram: wake it up, inspect its state, fetch screenshots, clear clipboard history and manage sound.

## Features

| Command | Description |
|---------|-------------|
| `Wake` | Send a Wake-on-LAN magic packet |
| `Status` | Check whether the host and the agent are reachable |
| `Health` | Show agent uptime, PID and basic runtime info |
| `Screen` | Capture a screenshot from the remote PC |
| `Clipboard` | Show recent clipboard entries |
| `Clear Clip` | Clear the clipboard history stored by the agent |
| `Stats` | CPU, RAM and disk usage |
| `Logs` | Last agent log lines |
| `Volume` | Show current sound state, mute and adjust by 10% |
| `Sleep` | Put the PC to sleep |
| `Shutdown` | Shut the PC down |
| `Voice` | Speech-to-text commands with local Vosk recognition |

## Architecture

```text
Telegram Bot <-> HTTP <-> Windows Agent
       |                     |
       +---- Wake-on-LAN ----+
```

The bot can run on Linux or Windows. The agent is intended for Windows.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Ducherness/tg-control-bot.git
cd tg-control-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure `.env`

Copy `.env.example` to `.env` and set your values:

```env
BOT_TOKEN=your_telegram_bot_token
TARGET_MAC=AA:BB:CC:DD:EE:FF
TARGET_HOST=192.168.0.102
AGENT_PORT=8000
AGENT_TIMEOUT=5
ALLOWED_USERS=123456789,987654321
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `TARGET_MAC` | MAC address used for Wake-on-LAN |
| `TARGET_HOST` | IP or hostname of the Windows PC |
| `AGENT_PORT` | Agent port, default `8000` |
| `AGENT_TIMEOUT` | Default HTTP timeout for bot-to-agent requests |
| `ALLOWED_USERS` | Comma-separated Telegram user IDs |
| `OPENROUTER_API_KEY` | Optional. Used for better intent parsing |
| `OPENROUTER_MODEL` | Optional. OpenRouter model for intent parsing |

If `OPENROUTER_API_KEY` is missing, the bot falls back to a local keyword parser instead of failing.

### 4. Download a Vosk model for voice commands

Create `models/vosk-model-small-en-us-0.15` and unpack the model there.

Install `ffmpeg` separately and make sure `ffmpeg` is available in `PATH`.

If the model is missing, the bot still works, but voice commands will return a readable error instead of crashing on startup.

## Running

### Windows Agent

Visible console:

```bat
start_agent.bat
```

Hidden background launch:

```bat
wscript start_agent_hidden.vbs
```

The launcher now:

- works without a hardcoded absolute path
- prefers `venv\Scripts\python.exe`, then `py -3`, then `python`
- writes startup diagnostics to `logs/agent-launch.log`
- writes runtime logs to `logs/agent.log`

### Telegram Bot

```bash
python main.py
```

## Agent endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | `GET` | Lightweight health check |
| `/health` | `GET` | Runtime info and resource snapshot |
| `/shutdown` | `POST` | Shutdown the PC |
| `/sleep` | `POST` | Put the PC to sleep |
| `/screenshot` | `GET` | Capture a screenshot |
| `/clipboard` | `GET` | Return clipboard history |
| `/clipboard` | `DELETE` | Clear clipboard history |
| `/stats` | `GET` | CPU, RAM and disk usage |
| `/volume` | `POST` | Get, set, mute or step volume |
| `/logs` | `GET` | Read recent agent logs |

### Volume actions

```json
{"action": "get"}
{"action": "set", "level": 0.5}
{"action": "step", "delta": 0.1}
{"action": "mute"}
```

## Notes

- Clipboard and logs are escaped before being sent to Telegram, so copied HTML-like text no longer breaks formatting.
- Voice processing uses temporary files in a platform-safe way.
- The bot registers Telegram slash commands and also accepts simple free-form text like `status`, `show logs` or `clear clipboard`.

## Project structure

```text
tg-control-bot/
├── agent.py
├── main.py
├── bot/
│   ├── ai.py
│   ├── config.py
│   ├── handlers.py
│   ├── voice.py
│   └── wol.py
├── start_agent.bat
├── start_agent_hidden.vbs
└── requirements.txt
```

## Security

- Only users listed in `ALLOWED_USERS` can operate the bot.
- The agent still has no built-in authentication, so keep it behind a trusted network or firewall rules.

## License

MIT
