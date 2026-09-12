# Lane Guardian - Predecessor Game Timer Bot 🎮

Lane Guardian is a Discord bot that calls out Predecessor objectives and timings over voice: jungle spawns, Fangtooth, Orb Prime, tower plating, ward reminders and more. Each server gets its own timers, voice and settings.

## Features ⚡

- **Voice callouts**: natural Microsoft neural voices (Edge-TTS). Default is Neerja, an expressive Indian English voice at a quick pace.
- **Per-server timers**: add, edit and remove callouts, each with several randomised lines.
- **Voice presets**: pick a voice from a dropdown, with an instant preview in your channel.
- **Admin controls**: server admins, chosen users and roles can change settings.
- **Import/Export**: share timer packs between servers as JSON.
- **Self-hosted**: runs anywhere Docker runs, including a NAS.

## Quick Start (How Not to Throw Your Games) 🚀

1. Invite the bot with the `bot` and `applications.commands` scopes (see [Create the Discord application](#create-the-discord-application)).
2. **Before the match**
   - Jump into a voice channel.
   - `/pred voice_preset` to pick a voice. It plays a sample right away.
   - `/pred set_tts` to tweak speed and pitch, `/pred set_volume` for loudness.
   - `/pred list_timers` to see the default callouts.
3. **Game start**
   - When minions spawn, run `/pred start`. Joined late? `/pred start time:4:30`.
   - `/pred status` shows the game clock and the next callouts.
4. **Game over**
   - `/pred stop`. The bot also leaves on its own when the channel empties.

## Commands 🎮

| Command | What it does |
| --- | --- |
| `/pred start [time] [mode]` | Start the timer at `M:SS` (default `0:00`), standard or nitro |
| `/pred stop` | Stop the timer and leave voice |
| `/pred status` | Game time, mode and upcoming callouts |
| `/pred say <message>` | Speak any message |
| `/pred test_voice [message]` | Hear the current voice |
| `/pred voice_preset <preset>` | Pick a voice from the list (Indian, Hindi, regional, US, UK, AU) |
| `/pred set_voice <voice>` | Choose any supported voice by name |
| `/pred set_tts [speed] [pitch] [warning_time]` | Speed and pitch dropdowns, seconds of early warning |
| `/pred set_volume <0-200>` | Volume in percent |
| `/pred settings` | Show the server's settings |
| `/pred help` | In-Discord cheat sheet |
| `/pred list_timers [category]` | List callouts |
| `/pred add_timer <name> <time> <message> [category]` | Add a callout or another line to one |
| `/pred edit_timer <name> <time> [message] [category]` | Change a callout |
| `/pred remove_timer <name>` | Delete a callout |
| `/pred remove_timer_message <name> <index>` | Delete one line from a callout |
| `/pred export_config` / `/pred import_config` | Back up or share the server config |
| `/pred add_admin` / `remove_admin` / `add_admin_role` / `remove_admin_role` / `sync_admins` | Manage who can change settings |

Server owners and anyone with Discord's Administrator permission can always manage the bot. Discord administrators are synced into the admin list on startup and daily.

## Self-hosting with Docker (NAS friendly) 🐳

The bot needs only outbound internet access. No ports have to be opened on your router.

### Create the Discord application

1. Go to https://discord.com/developers/applications and create an application, then add a **Bot**.
2. Under **Bot → Privileged Gateway Intents** enable **Server Members Intent**. (Used to find server admins; the bot exits with a clear error if it is missing.)
3. Copy the bot **token**. You will put it in `.env`.
4. Invite the bot with **OAuth2 → URL Generator**: scopes `bot` and `applications.commands`; permissions `Connect`, `Speak`, `View Channels`, `Send Messages`, `Embed Links`, `Attach Files`, `View Audit Log` (optional, used to detect who invited the bot).

### Run with docker compose

```bash
git clone https://github.com/Kendubu1/Predecessor-Lane-Guardian.git
cd Predecessor-Lane-Guardian
cp .env.example .env        # put your DISCORD_TOKEN in here
docker compose up -d
docker compose logs -f      # look for "Logged in as ..."
```

Settings live in `./data/server_configs.json` (mounted at `/data` in the container), so they survive upgrades. To upgrade:

```bash
git pull
docker compose up -d --build
```

### Use the prebuilt image instead of building

Every push to `main` publishes a multi-arch image (x86-64 and ARM64) to GitHub Container Registry. In `docker-compose.yml` replace the `build: .` line with:

```yaml
    image: ghcr.io/kendubu1/predecessor-lane-guardian:latest
```

Then `docker compose pull && docker compose up -d`.

### Synology, Unraid, QNAP, Portainer

Create a container from `ghcr.io/kendubu1/predecessor-lane-guardian:latest` with:

- Environment variable `DISCORD_TOKEN` set to your token.
- A volume mapping a folder on the NAS to `/data`.
- Restart policy "unless stopped".
- Optionally publish container port `8080` for the `/health` endpoint (JSON, returns 503 until the bot is connected). Handy for Uptime Kuma.

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | required | Bot token |
| `CONFIG_PATH` | `/data/server_configs.json` in Docker, `server_configs.json` otherwise | Where server settings are stored |
| `HEALTH_PORT` | `8080` | Port for `/health` |
| `LOG_FILE` | unset | Also write logs to this file (stdout is always used) |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `VOICE_INACTIVITY_TIMEOUT` | `300` | Seconds of silence before leaving voice when no timer runs |
| `OPUS_LIB` | auto | Opus library name/path if auto-detection fails |

## Running without Docker 💻

Requirements: Python 3.11+ (3.12 recommended), FFmpeg and libopus on the PATH (`sudo apt install ffmpeg libopus0` on Debian/Ubuntu).

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add DISCORD_TOKEN
python main.py
```

`python -m discord --version` should list PyNaCl and `davey`. If `davey` is missing, voice will not work (see below).

## Why the bot used to join and leave immediately

Discord made its DAVE end-to-end encryption protocol mandatory for every voice connection on 2 March 2026. Bots that do not speak DAVE are disconnected right after joining a channel (voice close code 4017), which is exactly the "joins the lobby then drops" behaviour. Lane Guardian now runs on discord.py 2.7+ with the `davey` bindings, which implement DAVE, and refuses to start if they are missing.

## Configuration ⚙️

`server_configs.json` holds one entry per server: timers, TTS settings (voice, speed, pitch, warning time, custom pronunciations), volume, admin users and roles, and secondary owners. Use `/pred export_config` and `/pred import_config` rather than editing it by hand while the bot is running.

## Development

```bash
pip install -r requirements.txt pytest
pytest
```

CI runs the tests on every push and pull request and publishes the container image from `main`.

## License

MIT
