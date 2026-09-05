"""Every request written into the general log: what came in, what went out, and how long it took.

Wired by `create_app` onto the application itself and not onto a blueprint, so that **nothing is
outside it**: a page, an image, a refusal, an address that matches no route at all - each one
leaves its two lines, `Request` then `Answer`, and a third when it fails.

    Request — method='GET', path='/game/state', query={}, endpoint='game.state', visitor='1000…'
    Answer  — status=200, type='application/json', took='3.1 ms', body={"version": 12, …}

**The answer is written out in full**, because that is what one comes to this log for: what the
page was actually given, not what it was meant to be. Three exceptions, and only three:

- a **streamed** answer is never read here. `/stream` is a generator held open for the life of a
  tab and `send_file` hands the file over untouched: reading either to log it would consume the
  one and load the other into memory. It is named, and left alone.
- anything **not JSON** is described rather than copied - a page is 40 KB of HTML that says nothing
  a status code does not say better - **unless it is a refusal**: from 400 up the body carries the
  sentence explaining it, and that sentence is the whole point of the line. A refusal is read
  whatever its shape, streamed included: it is never an endless stream.
- a value longer than `VALUE_LIMIT` is cut and says by how much (`general_log.py`).

Secrets travel in bodies and in query strings - the `code` and the `state` of the return from
Discord are fields of `request.args` - and `general_log.sanitised` hides them wherever they sit,
here as everywhere else.
"""

import time
from typing import Optional

from flask import Flask, Response, g, request, session

from tenebrae.application.logs.general_log import failure, note, without_the_secrets
from tenebrae.application.models.connection import PLAYER_KEY

# When the request started, kept on `g` for the length of that request, as `players.py` keeps the
# player it has read.
STARTED = "request_opened_at"


def wire_the_request_trace(application: Flask) -> None:
    """Hooks the trace onto the application: the arrival, the answer, and the failure.

    Args:
        application: The application being built.
    """
    application.before_request(trace_the_arrival)
    application.after_request(trace_the_answer)
    application.teardown_request(trace_the_failure)


def trace_the_arrival() -> None:
    """Writes what came in: the address asked for, who is asking, and the payload in full."""
    setattr(g, STARTED, time.monotonic())
    note("Request",
         method=request.method,
         path=request.path,
         query=request.args.to_dict(),
         endpoint=request.endpoint,
         route=request.view_args,
         visitor=session.get(PLAYER_KEY),
         address=request.remote_addr,
         payload=what_came_in())


def trace_the_answer(response: Response) -> Response:
    """Writes what goes out, and hands the answer back untouched.

    Args:
        response: The answer Flask has composed.

    Returns:
        That same answer: an `after_request` handler that returned anything else would be serving
        it.
    """
    note("Answer",
         method=request.method,
         path=request.path,
         status=response.status_code,
         type=response.content_type,
         took=how_long_it_took(),
         body=what_goes_out(response),
         **where_it_sends(response))
    return response


def where_it_sends(response: Response) -> dict[str, object]:
    """Where a redirect sends, for the lines that are one.

    A redirect's body says nothing - three hundred bytes of "you are being redirected" - and its
    `Location` says everything: it is what the login flow is read on. It is also where the OAuth
    state travels on the way to Discord, so it goes out scrubbed like any other URL.

    Args:
        response: The answer.

    Returns:
        `{"destination": ...}` for a redirect, nothing at all otherwise, so that every other line
        is not lengthened by a variable that would always be empty.
    """
    location = response.headers.get("Location")
    return {"destination": without_the_secrets(location)} if location else {}


def trace_the_failure(trouble: Optional[BaseException]) -> None:
    """Writes the exception a request died of, with its traceback.

    Called at the end of every request, with `None` for those that went well - a refusal raised by
    `abort` is one of those: it was handled, and it left as an answer with a status of its own.

    Args:
        trouble: What was raised, or `None`.
    """
    if trouble is None:
        return
    failure("Request failed", trouble=trouble, method=request.method, path=request.path,
            endpoint=request.endpoint, took=how_long_it_took())


def how_long_it_took() -> str:
    """How long the request has been in the server's hands.

    Returns:
        The duration in milliseconds; `unknown` where the arrival was not marked - an answer
        composed before the trace was reached, which a `before_request` raising would give.
    """
    started = g.get(STARTED)
    if started is None:
        return "unknown"
    return f"{(time.monotonic() - started) * 1000:.1f} ms"


def what_came_in() -> object:
    """The request's payload, in the form it is read back.

    Returns:
        The parsed JSON body, the form as a dict, `None` for a request carrying nothing, and a
        description of anything else - a file being uploaded is not copied into a log.
    """
    if request.is_json:
        return request.get_json(silent=True)
    if request.form:
        return request.form.to_dict()
    if not request.content_length:
        return None
    return f"<{request.content_length} bytes, {request.content_type}>"


def what_goes_out(response: Response) -> object:
    """The answer's body, in full where reading it costs nothing.

    Args:
        response: The answer.

    Returns:
        The parsed JSON, the text of a refusal, a description of a page or an image, and a word
        for a streamed answer, which is never read here (see this module's docstring).
    """
    # The refusal first: a 404 raised by the router reaches here as an iterable and would read as
    # streamed, and a refusal is never an endless stream - reading it costs a few hundred bytes.
    if response.status_code >= 400 and not response.direct_passthrough:
        return response.get_json(silent=True) or response.get_data(as_text=True)
    if response.direct_passthrough or response.is_streamed:
        return "<streamed, left untouched>"
    if response.is_json:
        return response.get_json(silent=True)
    return f"<{response.content_length} bytes of {response.mimetype}>"
