// The landing page: the saved games listed, and the form that opens one more.
//
// Everything it shows was passed by the server in the hidden fields - the games, the set-ups on
// offer, who is looking - so the page asks nothing at start-up. The one round trip it makes is
// `POST /game/new`, and the answer is an address it follows.
//
// The set-ups are read from the page and not fetched, unlike the chooser that used to sit in the
// board's table dialog: that dialog could be opened hours after the tab was loaded, this page was
// served a moment ago. The guard is unchanged either way - `/game/new` reads the files again and
// refuses a set-up disabled since, and the refusal is shown under the form.

const trace = debugScope("home.js");

const games = JSON.parse(document.getElementById("games").value);
const scenarios = JSON.parse(document.getElementById("scenarios").value);
const visitor = JSON.parse(document.getElementById("visitor").value);

const avatar = document.getElementById("account-avatar");
const nickname = document.getElementById("account-nickname");
const logoutButton = document.getElementById("account-logout");
const gameList = document.getElementById("game-list");
const noGame = document.getElementById("no-game");
const noAccount = document.getElementById("no-account");
const noScenario = document.getElementById("no-scenario");
const form = document.getElementById("new-game");
const scenarioChoice = document.getElementById("new-scenario");
const sideChoice = document.getElementById("new-side");
const againstAI = document.getElementById("new-against-ai");
const submitButton = document.getElementById("new-game-submit");
const errorLine = document.getElementById("new-game-error");
const loginLink = document.getElementById("new-game-login");

trace.info("state received from the page",
           { games: games.length, scenarios: scenarios.length, connected: visitor.connected });

// --- Who is looking ---

// The way in and the way out are one place and not two: the header's corner carries `Se connecter`
// for a visitor and `Se déconnecter` for a player, and the other of the two stays hidden. Nothing
// else in the page offers to log in - a page that asked a logged-in player to log in again is what
// this replaces.
function showTheAccount() {
  loginLink.hidden = visitor.connected;
  logoutButton.hidden = !visitor.connected;
  nickname.textContent = visitor.connected ? visitor.nickname : "";
  nickname.hidden = !visitor.connected;
  avatar.hidden = !(visitor.connected && visitor.avatar);
  if (!avatar.hidden) avatar.src = visitor.avatar;
  trace.info("the account corner", { connected: visitor.connected });
}

async function logOut() {
  trace.info("logging out");
  await trace.fetch("/logout", { method: "POST" });
  location.reload();
}

// --- The saved games ---

function listTheGames() {
  gameList.textContent = "";
  noGame.hidden = games.length > 0;
  for (const game of games) gameList.appendChild(card(game));
  trace.info("games laid out", { count: games.length,
                                 mine: games.filter((game) => game.mine).length });
}

// A card is the whole link, unless the game cannot be opened at all - a set-up that has left the
// disk cannot be laid out, and a link leading to a refusal is worse than no link.
function card(game) {
  const playable = game.scenario_name !== null;
  const box = playable ? link(`/game/${game.id}`) : document.createElement("div");
  box.className = ["game", game.mine ? "mine" : "", playable ? "" : "unplayable"]
    .filter(Boolean).join(" ");
  box.dataset.game = game.id;
  box.appendChild(span(titleOf(game), "title"));
  box.appendChild(standingOf(game));
  box.appendChild(sidesOf(game));
  box.appendChild(span(`Dernier coup joué ${whenOf(game.played_at)}`, "played-at"));
  return box;
}

function titleOf(game) {
  return game.scenario_name === null
    ? `Scénario n° ${game.scenario} — fichier absent`
    : `Scénario n° ${game.scenario} — ${game.scenario_name}`;
}

// Where the game stands: its phase, or how it ended. Both sentences are the server's - the same
// ones the board's own toolbar shows - and neither is composed here.
function standingOf(game) {
  if (game.over) return span(game.end, "end");
  return span(`Tour ${game.turn} — ${game.phase}, ${game.army} — ${game.units} pions en jeu`,
              "standing");
}

function sidesOf(game) {
  const row = document.createElement("div");
  row.className = "sides";
  for (const side of game.sides) {
    const line = span("", "side");
    line.dataset.side = side.side;
    line.appendChild(span(`${side.army} — `));
    if (side.occupant === null) line.appendChild(span("libre", "free"));
    else line.appendChild(span(side.mine ? `${side.occupant} (vous)` : side.occupant, "occupant"));
    row.appendChild(line);
  }
  return row;
}

// The server knows only UTC; the reader's timezone is the browser's, and it is the browser that
// puts the two together.
function whenOf(moment) {
  const when = new Date(moment);
  if (Number.isNaN(when.getTime())) return "à une date inconnue";
  return `le ${when.toLocaleDateString("fr-FR", { day: "numeric", month: "long",
                                                  year: "numeric" })} `
    + `à ${when.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

// --- Opening a game ---

function prepareTheForm() {
  if (!visitor.connected) {
    noAccount.hidden = false;
    trace.info("anonymous visitor: no form, and the way in is the header's");
    return;
  }
  if (scenarios.length === 0) {
    noScenario.hidden = false;
    trace.warn("no scenario is offered: nothing can be opened");
    return;
  }
  for (const scenario of scenarios) {
    scenarioChoice.appendChild(option(scenario.number, `n° ${scenario.number} — ${scenario.name}`));
  }
  fillTheSides();
  scenarioChoice.addEventListener("change", fillTheSides);
  form.addEventListener("submit", openAGame);
  form.hidden = false;
}

// The sides are the chosen set-up's own: another scenario is another pair of armies, and a side
// kept from the one before would be a side the game has not.
function fillTheSides() {
  const chosen = chosenScenario();
  sideChoice.textContent = "";
  for (const [side, army] of Object.entries(chosen?.armies ?? {})) {
    sideChoice.appendChild(option(side, army));
  }
  trace.trace("sides offered", { scenario: chosen?.number, sides: sideChoice.length });
}

function chosenScenario() {
  const number = Number(scenarioChoice.value);
  return scenarios.find((scenario) => scenario.number === number) ?? null;
}

async function openAGame(event) {
  event.preventDefault();
  const demand = { scenario: Number(scenarioChoice.value), side: sideChoice.value,
                   against_ai: againstAI.checked };
  trace.enter("openAGame", demand);
  errorLine.hidden = true;
  submitButton.disabled = true;
  const answer = await trace.fetch("/game/new", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(demand),
  }).catch(() => null);
  // A set-up withdrawn between this page being served and this click is refused there, and the
  // player is told rather than left before an unchanged list.
  if (!answer || !answer.ok) {
    const { message } = await answer?.json().catch(() => ({})) ?? {};
    trace.warn("the new game was refused", { status: answer?.status ?? null, message });
    errorLine.textContent = message ?? "La partie n'a pas pu être ouverte.";
    errorLine.hidden = false;
    submitButton.disabled = false;
    return;
  }
  const opened = await answer.json();
  trace.exit("openAGame", opened);
  location.href = opened.url;
}

// --- Small builders ---

function span(text, className) {
  const element = document.createElement("span");
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function link(href) {
  const element = document.createElement("a");
  element.href = href;
  return element;
}

function option(value, text) {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = text;
  return element;
}

logoutButton.addEventListener("click", logOut);

showTheAccount();
listTheGames();
prepareTheForm();
