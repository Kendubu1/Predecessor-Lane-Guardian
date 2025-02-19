# Lane Guardian - Predecessor Game Timer Bot 🎮

Lane Guardian is a Discord bot designed to help Predecessor players track important game events, objectives, and timings through voice announcements. It provides customizable timers, multi-language support, and server-specific configurations.

## Features ⚡

- Voice Announcements: Automated TTS announcements for game events
- Customizable Timers: Add, remove, and manage game event timers
- Multi-language Support: Multiple languages and accents available for TTS
- Server-specific Settings: Each Discord server can have its own configuration
- Category-based Events: Organize timers by categories
- Admin Controls: Role-based permissions for bot configuration
- Import/Export: Share configurations between servers

## Quick Start Guide (How Not to Throw Your Games) 🚀

To make the most of your Lane Guardian do the following...
0. https://discord.com/oauth2/authorize?client_id=1339385702151884800&permissions=293171527744&scope=bot%20applications.commands

1. **Before You Int (Pre-Match Setup)**
   - Jump into a voice channel
   - `/pred settings` - Make sure your bot isn't speaking in cursed tongues
   - `/pred say` - Check if the volume is perfect for your precious ears or just mess with your friends
   - `/pred tts_set` - Mess with the tts voice language & accent.
   - `/pred list_timers ` - Review all the existing timers in place by default
   - `/pred export_config` & `/pred import_config` - Make any edits of the TTS voice lines in place!

2. **Time to Clap Some Cheeks (Game Start)**
   - When minions spawn (0:00), hit that `/pred start 0:00` like you mean it
   - Examples of what your bot will remind you about:
     - 2:00 - Ward time
     - 2:30 - Gold buff incoming 
     - 3:00 - River buffs are up 
     - 5:00 - Fangtooth joins the party 

3. **During Your Path to Victory (or Throwing)**
   - Bot's got your back with timely reminders
   - Disconnected? No problem! Use `/pred start` with current game time
   - Want some peace? `/pred stop` to shut it up

Remember: Lane Guardian is like your aggressive but loving coach to keep your 5 stack from getting distracted.

## Prerequisites 📋

- Python 3.8 or higher
- Discord Bot Token
- FFmpeg (for voice functionality)
- Required Python packages (see requirements.txt)

## Installation 💻

1. Clone the repository:
```bash
git clone https://github.com/yourusername/lane-guardian.git
cd lane-guardian
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your Discord bot token:
```
DISCORD_TOKEN=your_discord_bot_token_here
```

5. Ensure FFmpeg is installed on your system and accessible in the PATH

## Commands 🎮

### Basic Commands
- `/pred start <time>` - Start the game timer (format: M:SS)
- `/pred stop` - Stop the current game timer
- `/pred list_timers` - View all configured timers
- `/pred settings` - View current server settings

### Timer Management
- `/pred add_timer <name> <time> <message> [category]` - Add a new timer
- `/pred remove_timer <name>` - Remove an existing timer
- `/pred import_config <config_code>` - Import a timer configuration
- `/pred export_config` - Export current configuration

### Settings Management
- `/pred set_tts` - Configure TTS settings (language, accent, speed)
- `/pred set_volume <volume>` - Set announcement volume (0.0 - 1.0)
- `/pred test_voice [message]` - Test current voice settings

### Admin Commands
- `/pred add_admin <user>` - Add a bot admin
- `/pred remove_admin <user>` - Remove a bot admin
- `/pred add_admin_role <role>` - Add an admin role

## Timer Categories ⏰

- Early Game (0:00 - 5:00)
- Mid Game (5:00 - 20:00)
- Late Game (20:00+)
- Objectives
- Buffs
- Farm
- Reminders

## Configuration ⚙️

The bot stores configurations in `server_configs.json`. Each server can have its own:
- Timer events
- TTS settings
- Volume settings
- Admin roles
- Custom pronunciations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
