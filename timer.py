"""Per-guild game clock."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Set

logger = logging.getLogger('PredTimer.Timer')


class GameTimer:
    """Tracks the in-game clock for one guild."""

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.start_time: Optional[datetime] = None
        self.is_active: bool = False
        self.mode: str = 'standard'
        self.announced_events: Set[str] = set()

    @staticmethod
    def parse_time(time_str: str) -> int:
        """Parse 'M:SS' (or 'MM:SS') into seconds. Raises ValueError on bad input."""
        parts = time_str.strip().split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str!r}")
        minutes, seconds = (int(p) for p in parts)
        if minutes < 0 or not 0 <= seconds < 60:
            raise ValueError(f"Invalid time value: {time_str!r}")
        return minutes * 60 + seconds

    def start(self, time_str: str = "0:00", mode: str = 'standard') -> None:
        """Start (or restart) the clock at the given game time."""
        offset = self.parse_time(time_str)
        self.start_time = datetime.now() - timedelta(seconds=offset)
        self.is_active = True
        self.mode = mode
        self.announced_events.clear()
        logger.info(f"[{self.guild_id}] Timer started at {time_str} in {mode} mode")

    def get_game_time(self) -> int:
        """Current game time in seconds (0 when not running)."""
        if not self.is_active or not self.start_time:
            return 0
        return int((datetime.now() - self.start_time).total_seconds())

    def stop(self) -> None:
        self.is_active = False
        self.start_time = None
        self.announced_events.clear()
        logger.info(f"[{self.guild_id}] Timer stopped")

    @staticmethod
    def format_time(seconds: int) -> str:
        return f"{seconds // 60}:{seconds % 60:02d}"
