# Telegram PC Control Bot

Remote control a Windows PC from Telegram: wake it up, return it from sleep or hibernate, inspect its state, manage a predefined ComfyUI process, fetch screenshots, clear clipboard history and control sound.

## Features

| Command | Description |
|---------|-------------|
| `Wake` | Send a Wake-on-LAN magic packet |
| `Wake&Wait` | Wake the PC and wait until the agent is online again |
| `Sleep` | Put the PC to sleep |
| `Hibernate` | Hibernate the PC and preserve the session state |
| `Status` | Check whether the host and the agent are reachable |
| `Health` | Show agent uptime, PID and runtime info |
| `Tasks` | Show managed background tasks |
| `Start ComfyUI` | Launch a managed ComfyUI loop |
| `Stop ComfyUI` | Stop the managed ComfyUI loop |
| `Screen` | Capture a screenshot from the remote PC |
| `Clipboard` | Show recent clipboard entries |
| `Clear Clip` | Clear the clipboard history stored by the agent |
| `Stats` | CPU, RAM and disk usage |
| `Logs` | Last agent log lines |
| `Volume` | Show current sound state, mute and adjust by 10% |
| `Voice` | Speech-to-text commands with local Vosk recognition |

## Sleep / Hibernate Resume Flow

To get the practical scenario `sleep -> wake -> return to previous desktop state`, the bot is only part of the solution.

You should use:

- `Sleep` or `Hibernate` instead of full shutdown
- `Wake&Wait` to send Wake-on-LAN and wait until the agent is reachable again
- a Windows setting that disables sign-in after wake, otherwise the machine will resume to the lock screen

The bot does not store or inject your Windows password.

## Managed ComfyUI Task

The agent can manage a predefined ComfyUI loop in:

```text
C:\Users\user\ComfyUI
```

By default it starts:

```powershell
venv\Scripts\python.exe main.py --listen 0.0.0.0 --port 8188
```

If the process exits, the agent restarts it after 5 seconds. Output is written to:

```text
logs\comfyui.log
```

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
AGENT_HOST=0.0.0.0
AGENT_PORT=8000
AGENT_TIMEOUT=5
ALLOWED_USERS=123456789
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-4o-mini
COMFYUI_DIR=C:\Users\user\ComfyUI
COMFYUI_PORT=8188
```

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `TARGET_MAC` | MAC address used for Wake-on-LAN |
| `TARGET_HOST` | IP or hostname of the Windows PC |
| `AGENT_HOST` | Bind host for the Flask agent |
| `AGENT_PORT` | Agent port, default `8000` |
| `AGENT_TIMEOUT` | Default HTTP timeout for bot-to-agent requests |
| `ALLOWED_USERS` | Comma-separated Telegram user IDs |
| `OPENROUTER_API_KEY` | Optional. Used for better intent parsing |
| `OPENROUTER_MODEL` | Optional. OpenRouter model for intent parsing |
| `COMFYUI_DIR` | Root directory of ComfyUI |
| `COMFYUI_PORT` | Port passed to ComfyUI |

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

The launcher:

- works without a hardcoded absolute path
- prefers `venv\Scripts\python.exe`, then `py -3`, then `python`
- loads `.env` for agent settings
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
| `/health` | `GET` | Runtime info and managed task snapshot |
| `/shutdown` | `POST` | Shutdown the PC |
| `/sleep` | `POST` | Put the PC to sleep |
| `/hibernate` | `POST` | Hibernate the PC |
| `/screenshot` | `GET` | Capture a screenshot |
| `/clipboard` | `GET` | Return clipboard history |
| `/clipboard` | `DELETE` | Clear clipboard history |
| `/stats` | `GET` | CPU, RAM and disk usage |
| `/volume` | `POST` | Get, set, mute or step volume |
| `/tasks` | `GET` | List managed tasks |
| `/tasks/comfyui/start` | `POST` | Start ComfyUI loop |
| `/tasks/comfyui/stop` | `POST` | Stop ComfyUI loop |
| `/logs` | `GET` | Read recent agent logs |

## Notes

- The bot does not unlock Windows itself. To resume directly into the desktop, configure Windows to not require sign-in after wake.
- Clipboard and logs are escaped before being sent to Telegram, so copied HTML-like text no longer breaks formatting.
- Voice processing uses temporary files in a platform-safe way.
- The bot registers Telegram slash commands and also accepts free-form text like `wake and wait`, `hibernate`, `tasks` or `start comfyui`.

## Security

- Only users listed in `ALLOWED_USERS` can operate the bot.
- The agent still has no built-in authentication, so keep it behind a trusted network or firewall rules.
- Auto-return to desktop after wake is convenient, but it reduces local physical security.

## License

MIT
