"""The battle log on disk, rotated by number of lines rather than by size."""

import logging
import logging.handlers
from pathlib import Path


class RotatingLog(logging.handlers.RotatingFileHandler):
    """The log on disk, set aside every `lines_per_file` lines.

    `RotatingFileHandler` counts bytes; this one counts **lines**, because it is in lines that the
    log is read - one per game event. The counter starts from what the file already contains: a
    server restarted ten times in a day must not write ten thousand lines into the same file.
    """

    lines_per_file: int
    lines_written: int

    def __init__(self, path: Path, lines_per_file: int, files_kept: int) -> None:
        """Opens the log file, creating its directory if needed.

        Args:
            path: The current log file; archives are `path.1`, `path.2`, ...
            lines_per_file: How many lines the current file takes before being set aside.
            files_kept: How many archives are kept behind it.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lines_per_file = lines_per_file
        self.lines_written = self._lines_already_written(path)
        super().__init__(path, backupCount=files_kept, encoding="utf-8")

    @staticmethod
    def _lines_already_written(path: Path) -> int:
        """Counts the lines the file already carries.

        Args:
            path: The log file.

        Returns:
            The line count, or zero if the file does not exist yet.
        """
        try:
            with open(path, encoding="utf-8") as source:
                return sum(1 for _ in source)
        except OSError:
            return 0

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """Says whether the current file is full.

        Args:
            record: The record about to be written; unused, the count decides.

        Returns:
            True once `lines_per_file` lines have been written.
        """
        return self.lines_written >= self.lines_per_file

    def doRollover(self) -> None:
        """Sets the current file aside and starts the count again."""
        super().doRollover()
        self.lines_written = 0

    def emit(self, record: logging.LogRecord) -> None:
        """Writes the record and counts the line.

        Args:
            record: The record the logger hands over.
        """
        super().emit(record)
        self.lines_written += 1
