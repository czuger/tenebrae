# Deployment — what the SSE stream will require

The game runs only in development today: `python3 app.py`, a single process, no server in front.
This document is therefore not a how-to for going into production — it is the list of what will
have to be settled **the day** there is one, and which does not show locally.

Everything hinges on one thing: since the game is followed through an **event stream**
(`GET /stream`, Server-Sent Events — see `application/stream.py` and the "Following the opponent's
game" section of `application/README.md`), every open tab holds an **HTTP request that never
ends**. Everything that, in an ordinary web stack, assumes a response is short — concurrency,
buffering, timeouts — has to be revisited.

The places in the code concerned all carry the `TODO: PRODUCTION` marker:

```
grep -rn "TODO: PRODUCTION" application/
```

---

## a) The WSGI server

**Do not serve the game through `app.run()`.** Flask's development server is fine for the stream
locally — it is multi-threaded by default, and that is what lets several tabs be served at once —
but it is not made to be exposed: neither robust, nor fast, nor secure.

With **Gunicorn**, a worker capable of holding many connections open at once is needed. An ordinary
synchronous worker holds only one per process: two players, and the server stops answering.

```
pip install gunicorn gevent
gunicorn -k gevent -w 1 'app:create_app()'
```

Two remarks on that line:

- **`gevent` rather than `eventlet`.** The brief mentioned `eventlet`; it is no longer maintained
  and fares badly on recent Pythons. `gevent` does the same thing and is still looked after. If one
  insists on `eventlet`, `-k eventlet` works the same way — to be checked against the Python
  version in use.
- **`'app:create_app()'` and not `app:app`.** This repository has no global application: `app.py`
  exposes only the `game` blueprint and the factory. Gunicorn knows how to call a factory if it is
  written that way.
- **Launch from `application/`**, or set `--pythonpath application`: the project's imports are
  absolute and assume `application/` is on the path (see `CLAUDE.md`).

An alternative to asynchronous workers, if one wants to stay synchronous: `-k gthread` with enough
threads (`--threads 32`). It is simpler to reason about, and enough for a two-player game; but
every open tab consumes a thread, and the count is soon reached if the game is being watched.

---

## b) The Nginx configuration

Nginx buffers responses by default: it would wait until it had enough to fill a buffer before
passing anything on, and the game's messages would stay stuck with it. The board would look frozen,
and nothing in the logs would say so.

```nginx
location /stream {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_read_timeout 24h;
}
```

**The `X-Accel-Buffering: no` header is already set by the Flask response** (in the `/stream`
route, `application/app.py`), and it tells Nginx the same thing as `proxy_buffering off;` — for
that response only. Both together, and not one or the other: the header protects if the
configuration is forgotten, the configuration protects if an intermediary ignores the header.

The rest of the site does not need this treatment: `map.jpg` is 10 MB, and buffering serves it
well. Hence the separate `location /stream` rather than a global setting.

---

## c) The timeouts to watch

A silent stream looks like a dead connection. The server therefore sends an SSE comment
(`: battement`) every **20 seconds** (`HEARTBEAT` in `application/app.py`): that is what keeps the
connection alive across intermediaries.

Every intermediary has its own timeout, and **the shortest wins**:

| Where | Setting | Default | What to do |
| --- | --- | --- | --- |
| Nginx | `proxy_read_timeout` | 60 s | raise to `24h` on `/stream` |
| Gunicorn | `--timeout` | 30 s | irrelevant on an asynchronous worker; on `gthread`, raise it |
| AWS ALB | *idle timeout* | 60 s | raise it, or check that 20 s of heartbeat is enough |
| Cloudflare | — | ~100 s | the heartbeat is enough |

The 20 s heartbeat falls under all those default values: even badly configured, the stream should
not drop. And if it does drop, that is not a failure — `EventSource` reconnects by itself and sends
back its `Last-Event-ID`, on which the server returns what it missed. **So prefer raising the
intermediary's timeout to lowering the heartbeat**: a shorter heartbeat is traffic for nothing.

---

## d) Several workers — the limit to know about

**The registry of open streams is in memory, in the process** (`Broadcaster`, in
`application/stream.py`). The same is true of the whole game state: the board, the turn, the combat
register and the seating table are module globals of `application/app.py`. The game therefore
assumes **a single process** — which was already the case long before the stream.

With `gunicorn -w 2` or more, two things would break, and not only the stream:

1. **Each worker would have its own broadcaster.** A player served by worker 2 would never see the
   move played on worker 1: `mark_a_move` only publishes to the subscribers of its own process.
2. **Each worker would have its own game in memory.** Two players spread over two workers would
   each play on a different board, MongoDB only piecing them back together when `/` is reloaded.

In other words: **`-w 1` is not a precaution tied to SSE, it is what the application requires
today.** The stream only adds one more reason.

To go beyond that, two distinct pieces of work would be needed:

- **An external pub/sub** — Redis, typically — between `mark_a_move` and the subscribers' boxes:
  each worker would publish on a channel and subscribe to it, and `Broadcaster.publish` would
  become a `PUBLISH`. The structure lends itself to it, everything already goes through a single
  point.
- **The game state taken out of the module globals**, re-read from the base at every request and
  written under a lock. That is the bigger of the two, and it has nothing to do with the stream.

As long as those two are not done: **a single worker**.

---

## What does not need to change

- **The player's actions.** The stream is one-way, server → browser. Everything the player does
  leaves as a `POST` on the ordinary routes (`/move`, `/combat`, `/phase/next`, `/game/seat`), and
  none of that has moved.
- **The fallback.** `GET /game/state` is still served: a page whose `EventSource` fails five times
  in a row falls back on it and polls every three seconds. A badly configured intermediary slows
  the game down, it does not break it.
- **The secrets and the session.** Nothing new: `.env`, `SECRET_KEY`, and `SECURE_COOKIE=yes`
  behind HTTPS (see `.env.example`).
