// The debug log of the pages, shared by all of them.
//
// The board is played in a browser, and what goes wrong there leaves no trace: a piece that does
// not move, a card that stays open, a stream that no longer delivers. This file gives the other
// scripts a way to say what they are doing, loud enough to follow a whole game in the console, and
// **silent by default**: nothing is written unless the log has been turned on.
//
// It is loaded first by the three templates, before every other script, and hangs everything off
// `window.tenebraeDebug`: a file that loads out of order still finds the namespace rather than a
// missing function.
//
// --- Turning it on ---
//
//   /?debug=1            in the address bar - and it is remembered for the next loads
//   /?debug=0            turns it off again
//   tenebraeDebug.on()   from the console, without reloading
//   tenebraeDebug.off()
//   window.TENEBRAE_DEBUG = true   set before this script, from a page that wants it on
//
// The choice is kept in `localStorage` under "tenebrae.debug": one turns the log on, plays, and
// reads the console; nothing else in the application knows this file exists.
//
// --- The levels ---
//
// "trace" carries what happens by the hundred - a pointer moving over the map, a scroll, a
// hexagon converted into coordinates - and "info", "warn", "error" the rest. Everything is shown
// by default; `tenebraeDebug.level("info")` drops the noise of the pointer without losing the
// moves played.
//
// Everything here is English, console lines included: they are the log's own lines, not something
// the player reads (see CLAUDE.md).

(function () {
  const STORAGE_KEY = "tenebrae.debug";
  const LEVEL_KEY = "tenebrae.debug.level";
  const QUERY_KEY = "debug";

  // From the most talkative to the gravest: a level is shown when it ranks at or above the
  // minimum in force.
  const RANKS = { trace: 0, info: 1, warn: 2, error: 3 };
  const CONSOLE = { trace: "log", info: "info", warn: "warn", error: "error" };
  const DEFAULT_LEVEL = "trace";

  // A body longer than that is cut: a scenario's placement or a whole game state would fill the
  // console by itself and hide the line that follows.
  const BODY_LIMIT = 2000;

  function stored(key) {
    // Private browsing and a blocked storage both throw rather than answer: the log is a
    // convenience, it must never be what breaks a page.
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function remember(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, value);
    } catch (error) {
      // Nothing to do: the choice will simply not survive the reload.
    }
  }

  function askedInTheAddress() {
    // "?debug", "?debug=1", "?debug=true" turn it on; "?debug=0", "?debug=no", "?debug=off" turn
    // it off; the absence of the parameter says nothing and leaves what was stored.
    const asked = new URLSearchParams(window.location.search).get(QUERY_KEY);
    if (asked === null) return null;
    return !["0", "no", "off", "false"].includes(asked.toLowerCase());
  }

  function initialState() {
    const asked = askedInTheAddress();
    if (asked !== null) {
      remember(STORAGE_KEY, asked ? "on" : null);
      return asked;
    }
    if (stored(STORAGE_KEY) === "on") return true;
    return window.TENEBRAE_DEBUG === true;
  }

  function initialLevel() {
    const kept = stored(LEVEL_KEY);
    return kept !== null && RANKS[kept] !== undefined ? kept : DEFAULT_LEVEL;
  }

  let enabled = initialState();
  let minimum = initialLevel();

  function shows(level) {
    return enabled && RANKS[level] >= RANKS[minimum];
  }

  function timestamp() {
    const now = new Date();
    const pad = (value, width) => String(value).padStart(width, "0");
    return `${pad(now.getHours(), 2)}:${pad(now.getMinutes(), 2)}:${pad(now.getSeconds(), 2)}`
      + `.${pad(now.getMilliseconds(), 3)}`;
  }

  // The line itself: time, the file that speaks, the level when it is not the ordinary one, then
  // the message. The data, if there is any, goes as a second argument rather than into the string:
  // the console then lets one open it and walk through it.
  function write(scope, level, message, data) {
    if (!shows(level)) return;
    const mark = level === "info" || level === "trace" ? "" : `[${level.toUpperCase()}] `;
    const line = `${timestamp()} ${scope} · ${mark}${message}`;
    const method = CONSOLE[level] ?? "log";
    if (data === undefined) console[method](line);
    else console[method](line, data);
  }

  function shorten(text) {
    if (typeof text !== "string" || text.length <= BODY_LIMIT) return text;
    return `${text.slice(0, BODY_LIMIT)}… (${text.length} characters)`;
  }

  // A JSON body is shown as the object it is; anything else - a form, nothing at all - as it
  // comes.
  function payloadOf(options) {
    if (!options || options.body === undefined || options.body === null) return undefined;
    if (typeof options.body !== "string") return options.body;
    try {
      return JSON.parse(options.body);
    } catch (error) {
      return shorten(options.body);
    }
  }

  // The answer's body, read off a **clone**: the caller reads the original, and reading a body
  // twice is refused. Deliberately not awaited - the caller must get its answer at the moment it
  // would have got it without the log.
  function reportTheAnswer(scope, method, url, answer, milliseconds) {
    const level = answer.ok ? "info" : "warn";
    const heading = `← ${answer.status} ${method} ${url} (${milliseconds.toFixed(0)} ms)`;
    let clone = null;
    try {
      clone = answer.clone();
    } catch (error) {
      write(scope, level, heading, { body: "unreadable (already consumed)" });
      return;
    }
    clone.text().then(
      (text) => {
        let body = shorten(text);
        try {
          body = JSON.parse(text);
        } catch (error) {
          // Not JSON: the text stands as it is.
        }
        write(scope, level, heading, { body });
      },
      (error) => write(scope, level, heading, { body: "unreadable", error }),
    );
  }

  // `fetch` with the round trip written down: the request with its payload, then the status, the
  // time it took and the body. Turned off, it is `fetch` itself - not one clone, not one line -,
  // and in both cases it returns exactly what `fetch` returns and throws exactly what it throws.
  async function tracedFetch(scope, url, options) {
    if (!enabled) return fetch(url, options);
    const method = (options && options.method) || "GET";
    write(scope, "info", `→ ${method} ${url}`, payloadOf(options));
    const started = performance.now();
    try {
      const answer = await fetch(url, options);
      reportTheAnswer(scope, method, url, answer, performance.now() - started);
      return answer;
    } catch (error) {
      write(scope, "error", `✗ ${method} ${url} did not answer`, error);
      throw error; // the caller's `catch` is the one that decides, exactly as before
    }
  }

  // One logger per file: `const trace = debugScope("map.js")`, then `trace.info(...)`. `enter` and
  // `exit` are the two ends of a function, and read as such in the console.
  function scope(name) {
    return {
      trace: (message, data) => write(name, "trace", message, data),
      info: (message, data) => write(name, "info", message, data),
      warn: (message, data) => write(name, "warn", message, data),
      error: (message, data) => write(name, "error", message, data),
      enter: (called, data) => write(name, "trace", `→ ${called}`, data),
      exit: (called, data) => write(name, "trace", `← ${called}`, data),
      fetch: (url, options) => tracedFetch(name, url, options),
      enabled: () => enabled,
    };
  }

  window.tenebraeDebug = {
    enabled: () => enabled,
    on(persist = true) {
      enabled = true;
      if (persist) remember(STORAGE_KEY, "on");
      write("debug.js", "info", "debug log on", { level: minimum });
      return enabled;
    },
    off(persist = true) {
      write("debug.js", "info", "debug log off");
      enabled = false;
      if (persist) remember(STORAGE_KEY, null);
      return enabled;
    },
    // Read without an argument, set with one; an unknown name changes nothing.
    level(name) {
      if (name === undefined) return minimum;
      if (RANKS[name] === undefined) return minimum;
      minimum = name;
      remember(LEVEL_KEY, name);
      return minimum;
    },
    levels: Object.keys(RANKS),
    scope,
    log: (scopeName, message, data) => write(scopeName, "info", message, data),
    fetch: tracedFetch,
  };

  // The two shorthands the files use: a logger of one's own, and the one-off line.
  window.debugScope = scope;
  window.debugLog = window.tenebraeDebug.log;

  write("debug.js", "info", "debug log ready", { level: minimum, url: window.location.href });
}());
