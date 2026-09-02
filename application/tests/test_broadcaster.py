"""The broadcaster alone, without Flask or a browser: one-slot box, registry, removal.

It is the piece the whole SSE stream rests on, and it can be exercised without a server - it knows
neither the game nor the web. What shows in a page is exercised separately, in `test_stream.py`
(Flask) and `test_stream_browser.py` (Chromium).
"""

import threading

from stream import Broadcaster

# Enough not to wait a second to observe that a box is empty.
INSTANT = 0.05
# The margin left to a thread to wake up on a loaded machine.
PATIENCE = 2.0


def test_a_subscriber_receives_what_is_published():
    broadcaster = Broadcaster()
    with broadcaster.subscription() as subscriber:
        broadcaster.publish({"version": 7})
        assert subscriber.wait(PATIENCE) == {"version": 7}


def test_an_empty_box_returns_none_after_the_delay():
    """It is this `None` that triggers the stream's heartbeat."""
    broadcaster = Broadcaster()
    with broadcaster.subscription() as subscriber:
        assert subscriber.wait(INSTANT) is None


def test_all_subscribers_receive_the_same_publication():
    """Two players, two tabs: a single move played wakes them both."""
    broadcaster = Broadcaster()
    with broadcaster.subscription() as first, broadcaster.subscription() as second:
        assert broadcaster.publish({"version": 1}) == 2
        assert first.wait(PATIENCE) == {"version": 1}
        assert second.wait(PATIENCE) == {"version": 1}


def test_the_box_keeps_only_the_last_state():
    """The coalescing: `/game/new` raises the version three times in one request.

    The subscriber has no use for the intermediate states - it lays the whole scene out again at
    every wake-up. It must therefore be woken only once, and on the last one.
    """
    broadcaster = Broadcaster()
    with broadcaster.subscription() as subscriber:
        broadcaster.publish({"version": 1})
        broadcaster.publish({"version": 2})
        broadcaster.publish({"version": 3})

        assert subscriber.wait(PATIENCE) == {"version": 3}
        assert subscriber.wait(INSTANT) is None, "an intermediate state stayed pending"


def test_publishing_with_nobody_there_does_nothing():
    assert Broadcaster().publish({"version": 1}) == 0


def test_the_registry_empties_on_leaving_the_with():
    """The leak we want to catch: a closed tab leaving its box behind it."""
    broadcaster = Broadcaster()
    with broadcaster.subscription():
        assert len(broadcaster) == 1
    assert len(broadcaster) == 0


def test_the_registry_empties_even_on_an_error():
    """A network cut raises inside the stream generator: the subscriber must leave all the same."""
    broadcaster = Broadcaster()
    try:
        with broadcaster.subscription():
            raise BrokenPipeError("the browser has gone")
    except BrokenPipeError:
        pass
    assert len(broadcaster) == 0


def test_an_abandoned_generator_removes_its_subscriber():
    """The real case: the browser closes the tab, the generator is closed, `GeneratorExit` crosses
    the `with`. That is what werkzeug does when the connection drops."""
    broadcaster = Broadcaster()

    def stream():
        with broadcaster.subscription() as subscriber:
            while True:
                yield subscriber.wait(INSTANT)

    generator = stream()
    next(generator)
    assert len(broadcaster) == 1

    generator.close()
    assert len(broadcaster) == 0


def test_removing_twice_does_nothing_more():
    broadcaster = Broadcaster()
    subscriber = broadcaster.subscribe()
    broadcaster.unsubscribe(subscriber)
    broadcaster.unsubscribe(subscriber)
    assert len(broadcaster) == 0


def test_a_sleeping_subscriber_is_woken_by_a_publication():
    """The heart of the matter: the stream **waits**, it asks for nothing. Publishing wakes it.

    Without that we would have a disguised poll on the server side - a loop rereading the state at
    a fixed interval to see whether it had moved - which would only have moved the problem one
    notch.
    """
    broadcaster = Broadcaster()
    received = []
    ready = threading.Event()

    def listen():
        with broadcaster.subscription() as subscriber:
            ready.set()
            received.append(subscriber.wait(PATIENCE))

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    assert ready.wait(PATIENCE), "the listening thread did not start"

    broadcaster.publish({"version": 42})
    thread.join(PATIENCE)

    assert received == [{"version": 42}]
    assert len(broadcaster) == 0, "the thread gone, its subscription must be too"
