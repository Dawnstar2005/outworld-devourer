"""Суралцах хэсэг (pygame-гүй): тоглолтын log, зуршлын профайл, дараагийн нүүдэл таамаглагч.

    from learning import GameLogger, read_log
    logger = GameLogger("logs")
    session.add_hook(logger.on_action)      # game/session.py-ийн on_action hook
"""

from .log import LOG_VERSION, GameLogger, iter_logs, read_log, replay_check

__all__ = ["GameLogger", "read_log", "iter_logs", "replay_check", "LOG_VERSION"]
