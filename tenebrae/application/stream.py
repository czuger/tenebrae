"""The broadcaster: who is following the game, and how a move played reaches them.

Each browser holds an **open stream** (`GET /stream`, Server-Sent Events) and the server pushes the
game to it at the moment it changes - not before, not after. The mechanism has three pieces:

- one **subscriber** per open stream, that is, per tab watching the game;
- a **one-slot box** per subscriber: a `Queue(maxsize=1)` whose content is *replaced* rather than
  stacked. Only the last state counts, and a request that raises the version several times (as
  `/game/new` does when the AI plays its first turn) wakes the subscriber only once. The box does
  the coalescing, not the browser;
- `publish`, called by the thread that has just played the move, with the snapshot **already
  taken**.

That last point is what rules out races on the game state: the board, the turn and the combat
register are module globals of `app.py`, and nothing protects them. The snapshot is taken once, in
the thread that has just written, and it is the snapshot that travels. The only shared state left is
the subscriber registry, and it has its lock.

This module knows neither Flask nor the game: it only carries the snapshots it is handed. The SSE
formatting and the route are in `app.py`.

TODO: PRODUCTION - the registry is in memory, in the process. With more than one worker, each would
only broadcast to its own subscribers; an external pub/sub (Redis) would then be needed. See
`DEPLOYMENT.md`.
"""

import queue
import threading
from collections.abc import Mapping
from typing import Optional

# What travels to the streams: the shared snapshot `app.py` takes after each move.
Snapshot = Mapping[str, object]


class Subscriber:
    """An open stream: its one-slot box, and the means to wait there for the next state.

    The subscriber does not know *who* is watching - nor does the broadcaster. It is the route
    that knows which player is behind which stream, and that composes what it sends them.
    """

    __slots__ = ("_box",)

    _box: queue.Queue[Snapshot]

    def __init__(self) -> None:
        """Opens an empty box."""
        self._box = queue.Queue(maxsize=1)

    def put(self, state: Snapshot) -> None:
        """Puts the latest known state in, replacing the one that has not been read yet.

        The removal then the deposit are not atomic together, and that is of no consequence: the
        only reader is the generator of *that* stream, and two concurrent deposits leave one of
        the two states in any case - one state behind is caught up at the next deposit.

        Args:
            state: The snapshot to deliver.
        """
        try:
            self._box.get_nowait()
        except queue.Empty:
            pass
        try:
            self._box.put_nowait(state)
        except queue.Full:  # pragma: no cover - another deposit has just filled it
            pass

    def wait(self, delay: float) -> Optional[Snapshot]:
        """Waits for the next state.

        Args:
            delay: How long to wait, in seconds.

        Returns:
            The state, or `None` if nothing came in time - which is what triggers the heartbeat.
        """
        try:
            return self._box.get(timeout=delay)
        except queue.Empty:
            return None


class Broadcaster:
    """The registry of open streams, and the sending of a state to all of them.

    One instance per process (`BROADCASTER` in `app.py`), like the board and the turn: there is
    only one game, and everyone watching it watches it together.
    """

    _subscribers: set[Subscriber]
    _lock: threading.Lock

    def __init__(self) -> None:
        """Opens an empty registry."""
        self._subscribers = set()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        """The number of open streams."""
        with self._lock:
            return len(self._subscribers)

    def subscribe(self) -> Subscriber:
        """Opens a subscription.

        Prefer `subscription()`, which guarantees removal; this one is for whoever needs the two
        steps apart.

        Returns:
            The new subscriber.
        """
        subscriber = Subscriber()
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Removes a subscriber from the registry; removing twice does nothing more.

        Args:
            subscriber: The subscriber to remove.
        """
        with self._lock:
            self._subscribers.discard(subscriber)

    def subscription(self) -> "_Subscription":
        """Opens a subscription as a context manager: `with broadcaster.subscription() as s:`.

        **The** way to subscribe from a stream generator: tab closed, network cut or server
        stopped, the generator is closed, `GeneratorExit` crosses the `with`, and the subscriber
        is removed. Without that, every closed page would leave a box behind it.

        Returns:
            The context manager, yielding the subscriber.
        """
        return _Subscription(self, self.subscribe())

    def publish(self, state: Snapshot) -> int:
        """Deposits a state with every subscriber.

        The copy of the registry is taken under the lock, the deposits happen outside it: a
        subscriber joining or leaving during the send does not wait. One arriving too late catches
        up when its stream opens.

        Args:
            state: The snapshot the calling thread has just taken.

        Returns:
            The number of subscribers served.
        """
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(state)
        return len(subscribers)


class _Subscription:
    """What `Broadcaster.subscription()` returns: a subscriber, removed whatever happens on exit."""

    __slots__ = ("_broadcaster", "_subscriber")

    def __init__(self, broadcaster: Broadcaster, subscriber: Subscriber) -> None:
        """Binds a subscriber to the registry it will be removed from.

        Args:
            broadcaster: The registry.
            subscriber: The subscriber already registered there.
        """
        self._broadcaster = broadcaster
        self._subscriber = subscriber

    def __enter__(self) -> Subscriber:
        """Hands the subscriber over."""
        return self._subscriber

    def __exit__(self, *_: object) -> None:
        """Removes the subscriber; exceptions are not swallowed."""
        self._broadcaster.unsubscribe(self._subscriber)
