"""The broadcaster: who is following the game, and how a move played reaches them.

Before, each browser asked for the state again every three seconds (`GET /game/state`) and was
told "nothing has moved" twenty times out of twenty-one. Now it holds an **open stream** (`GET
/stream`, Server-Sent Events) and the server pushes the game to it at the moment it changes - not
before, not after.

The mechanism has three pieces:

- one **subscriber** per open stream, that is, per tab watching the game;
- a **one-slot box** per subscriber: a `Queue(maxsize=1)` whose content is *replaced* rather than
  stacked. Nobody needs a stale state - only the last one counts - and a request that raises the
  version three times (that is the case of `/game/new`, which lays out the scenario again then
  lets the AI play its turn) wakes the subscriber only once, on the last state. It is this box
  that does the coalescing, and not the browser;
- `publish`, called by the thread that has just played the move, with the snapshot **already
  taken**.

That last point is what rules out races on the game state: the board, the turn and the combat
register are module globals of `app.py`, and nothing protects them. If a stream's generator went
and re-read them itself on waking, it would read them from the server thread serving *its* stream,
while another thread might be moving a piece. So we leave it nothing to re-read: the snapshot is
taken once, in the thread that has just written, and it is the snapshot that travels. The only
shared state left is the subscriber registry, and it has its lock.

This module knows neither Flask nor the game: it only carries objects it is handed. The SSE
formatting and the route are in `app.py`.

TODO: PRODUCTION - the registry is in memory, in the process. As long as there is only one worker
(`gunicorn -w 1`, and the development server), every player is subscribed to the same broadcaster
and all is well. Beyond that, each worker would have its own and would only broadcast to its own
subscribers: a player served by worker 2 would never see the move played on worker 1. An external
pub/sub - Redis - would then be needed between `publish` and the boxes. See `DEPLOYMENT.md`.
"""

import queue
import threading


class Subscriber:
    """An open stream: its one-slot box, and the means to wait there for the next state.

    The subscriber does not know *who* is watching - nor does the broadcaster. It is the route
    that knows which player is behind which stream, and that composes what it sends them.
    """

    __slots__ = ("_box",)

    def __init__(self):
        self._box = queue.Queue(maxsize=1)

    def put(self, state):
        """Puts the latest known state in, replacing the one that has not been read yet.

        The removal then the deposit are not atomic together, and that is of no consequence: the
        only reader of this box is the generator of *that* stream, and two concurrent deposits
        would in any case leave one of the two states - the most recent to within a few
        microseconds. One state behind is caught up at the next deposit; the browser would not
        even see the difference.
        """
        try:
            self._box.get_nowait()
        except queue.Empty:
            pass
        try:
            self._box.put_nowait(state)
        except queue.Full:  # pragma: no cover - another deposit has just filled it
            pass

    def wait(self, delay):
        """The next state, or `None` if nothing came within `delay` seconds.

        The `None` is not a failure: it is what triggers the heartbeat, without which an
        intermediary - or the browser itself - would end up closing a connection it believes dead.
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

    def __init__(self):
        self._subscribers = set()
        self._lock = threading.Lock()

    def __len__(self):
        """The number of open streams. The tests use it to observe that none is left once the
        pages have been closed."""
        with self._lock:
            return len(self._subscribers)

    def subscribe(self):
        """Opens a subscription and returns the subscriber.

        Prefer `subscription()`, which guarantees removal; this one is here for the tests and for
        whoever needs the two steps apart.
        """
        subscriber = Subscriber()
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber):
        """Removes a subscriber from the registry. Removing twice does nothing more."""
        with self._lock:
            self._subscribers.discard(subscriber)

    def subscription(self):
        """The subscription as a context manager: `with BROADCASTER.subscription() as subscriber:`.

        This is **the** way to subscribe from a stream generator. A browser closing its tab, a
        network cut, a server being stopped: in every case the generator is closed, `GeneratorExit`
        crosses the `with`, and the subscriber is removed. Without that, every closed page would
        leave a box behind it, into which the server would go on depositing every move played - a
        leak of both memory and work.
        """
        return _Subscription(self, self.subscribe())

    def publish(self, state):
        """Deposits this state with every subscriber, and returns their number.

        The caller is the thread that has just played the move, and `state` the snapshot it took
        itself: the broadcaster is not going to re-read anything.

        The copy of the registry is taken under the lock, but the deposits happen outside it: a
        subscriber joining or leaving during the send does not have to wait for it to finish. One
        arriving a microsecond too late catches up with the current state anyway when its stream
        opens, which the route sends it straight away.
        """
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(state)
        return len(subscribers)


class _Subscription:
    """What `Broadcaster.subscription()` returns: a subscriber, removed whatever happens on exit."""

    __slots__ = ("_broadcaster", "_subscriber")

    def __init__(self, broadcaster, subscriber):
        self._broadcaster = broadcaster
        self._subscriber = subscriber

    def __enter__(self):
        return self._subscriber

    def __exit__(self, *_):
        self._broadcaster.unsubscribe(self._subscriber)
        return False
