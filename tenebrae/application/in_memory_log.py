"""The last lines of the battle log, kept in memory so that the browser can show them."""

import collections
import logging
import time


class InMemoryLog(logging.Handler):
    """A bounded queue of the last log lines, as the browser's column shows them.

    A *handler*, and not a call added beside each `LOG.info`: the log keeps a single point of
    writing, and the browser's column cannot say anything other than the file. `deque.append` is
    atomic: the thread playing a move writes here while a stream thread copies the queue.
    """

    lines: collections.deque[dict[str, str]]

    def __init__(self, capacity: int) -> None:
        """Opens an empty queue.

        Args:
            capacity: How many lines are kept; the oldest goes out when a new one comes in.
        """
        super().__init__()
        self.lines = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        """Appends the record as `{"time": "HH:MM:SS", "text": message}`.

        Args:
            record: The record the logger hands over.
        """
        self.lines.append({
            "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "text": record.getMessage(),
        })
