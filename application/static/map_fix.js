// Corriger à l'œil les terrains de la carte.
//
// Le serveur a passé toute la carte dans un champ caché : le survol lit dedans, sans rien lui
// demander. Seul le choix d'un terrain fait un aller-retour, pour aller s'écrire dans
// game_box/map_fix.json. La carte transcrite, elle, n'est jamais touchée.

const ECHELLE_MIN = 0.05;
const ECHELLE_MAX = 1;
const ECART_INFOBULLE = 16; // pixels entre le pointeur et l'encadré

const cadre = document.getElementById("cadre");
const toile = document.getElementById("toile");
const plateau = document.getElementById("plateau");
const carte = document.getElementById("carte");
const surlignage = document.getElementById("surlignage");
const infobulle = document.getElementById("infobulle");
const compteur = document.getElementById("compteur");
const redemarrage = document.getElementById("redemarrage");
const affichageEchelle = document.getElementById("echelle");

const choix = document.getElementById("choix");
const choixTitre = document.getElementById("choix-titre");
const choixEtat = document.getElementById("choix-etat");
const choixTerrains = document.getElementById("choix-terrains");
const choixRetablir = document.getElementById("choix-retablir");

const hexagones = JSON.parse(document.getElementById("hexagones").value);
const corrections = JSON.parse(document.getElementById("corrections").value);
// Les corrections que le moteur a fusionnées à son démarrage : la carte du jeu s'arrête là.
const appliquees = JSON.parse(document.getElementById("appliquees").value);
const terrains = JSON.parse(document.getElementById("terrains").value);
const grille = JSON.parse(document.getElementById("grille").value);
const { hexagoneDuPixel, sommets } = calage(grille);

let echelle = 1;
let vise = null; // l'hexagone sous le pointeur
let enCoursDeCorrection = null; // celui dont le dialogue est ouvert

// --- La carte, lue en mémoire ---

function terrainDeLaCarte(clef) {
  return hexagones[clef] ?? null;
}

function terrainActuel(clef) {
  return corrections[clef] ?? hexagones[clef] ?? null;
}

// --- Échelle et défilement ---

function echelleAjustee() {
  return Math.min(window.innerWidth / carte.naturalWidth,
                  window.innerHeight / carte.naturalHeight);
}

function appliquerLEchelle(valeur) {
  echelle = Math.min(ECHELLE_MAX, Math.max(ECHELLE_MIN, valeur));
  plateau.style.transform = `scale(${echelle})`;
  // Le transform ne compte pas dans la mise en page : c'est la toile qui porte la taille visible,
  // et donc les barres de défilement.
  toile.style.width = `${carte.naturalWidth * echelle}px`;
  toile.style.height = `${carte.naturalHeight * echelle}px`;
  affichageEchelle.textContent = `${Math.round(echelle * 100)} %`;
}

function changerLEchelle(valeur, clientX, clientY) {
  // Le point de la carte sous le pointeur doit y rester : on le relève avant, on replace le
  // défilement après.
  const point = pixelDuPointeur({ clientX, clientY }, carte);
  appliquerLEchelle(valeur);
  const cadreVisible = cadre.getBoundingClientRect();
  cadre.scrollLeft = point.x * echelle + cadreVisible.x - clientX;
  cadre.scrollTop = point.y * echelle + cadreVisible.y - clientY;
}

function centreDuCadre() {
  const cadreVisible = cadre.getBoundingClientRect();
  return [cadreVisible.x + cadreVisible.width / 2, cadreVisible.y + cadreVisible.height / 2];
}

function ajusterALaFenetre() {
  appliquerLEchelle(echelleAjustee());
  cadre.scrollTo(0, 0);
}

// --- Surlignage ---

function polygone(hexagone, classe) {
  const forme = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  forme.setAttribute("points",
    sommets(hexagone.q, hexagone.r).map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "));
  forme.setAttribute("class", classe);
  return forme;
}

function dessinerLesCorrections() {
  surlignage.replaceChildren();
  for (const clef of Object.keys(corrections)) {
    const [q, r, s] = clef.split(",").map(Number);
    surlignage.appendChild(polygone({ q, r, s }, "corrige"));
  }
  if (vise) surlignage.appendChild(polygone(vise, "vise"));
}

function dimensionnerLeSurlignage() {
  surlignage.setAttribute("width", carte.naturalWidth);
  surlignage.setAttribute("height", carte.naturalHeight);
  surlignage.setAttribute("viewBox", `0 0 ${carte.naturalWidth} ${carte.naturalHeight}`);
}

// --- Survol ---

function montrerLInfobulle(clef, clientX, clientY) {
  const origine = terrainDeLaCarte(clef);
  const correction = corrections[clef];
  infobulle.textContent = `${clef} — ${origine}`;
  if (correction) {
    const fleche = document.createElement("span");
    fleche.className = "correction";
    fleche.textContent = ` → ${correction}`;
    infobulle.appendChild(fleche);
  }
  infobulle.hidden = false;

  // L'encadré se range de l'autre côté du pointeur quand il déborderait de la fenêtre.
  const taille = infobulle.getBoundingClientRect();
  const x = clientX + ECART_INFOBULLE + taille.width > window.innerWidth
    ? clientX - ECART_INFOBULLE - taille.width : clientX + ECART_INFOBULLE;
  const y = clientY + ECART_INFOBULLE + taille.height > window.innerHeight
    ? clientY - ECART_INFOBULLE - taille.height : clientY + ECART_INFOBULLE;
  infobulle.style.left = `${x}px`;
  infobulle.style.top = `${y}px`;
}

function cacherLInfobulle() {
  infobulle.hidden = true;
  vise = null;
  dessinerLesCorrections();
}

function auSurvol(evenement) {
  const { x, y } = pixelDuPointeur(evenement, carte);
  const hexagone = hexagoneDuPixel(x, y);
  const clef = cle(hexagone);
  if (!terrainDeLaCarte(clef)) {
    cacherLInfobulle();
    return;
  }

  if (!vise || cle(vise) !== clef) {
    vise = hexagone;
    dessinerLesCorrections();
  }
  montrerLInfobulle(clef, evenement.clientX, evenement.clientY);
}

// --- Le dialogue de correction ---

function construireLesBoutons() {
  for (const terrain of terrains) {
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.dataset.terrain = terrain;
    bouton.textContent = terrain;
    bouton.addEventListener("click", () => corriger(terrain));
    choixTerrains.appendChild(bouton);
  }
}

function ouvrirLeChoix(hexagone) {
  const clef = cle(hexagone);
  const origine = terrainDeLaCarte(clef);
  if (!origine) return;

  enCoursDeCorrection = hexagone;
  const actuel = terrainActuel(clef);
  choixTitre.textContent = `Hexagone ${clef}`;
  choixEtat.textContent = corrections[clef]
    ? `carte : ${origine} — corrigé en ${corrections[clef]}`
    : `carte : ${origine}`;
  for (const bouton of choixTerrains.children) {
    bouton.classList.toggle("actuel", bouton.dataset.terrain === actuel);
  }
  choixRetablir.hidden = !corrections[clef];
  choixRetablir.textContent = `Rétablir (${origine})`;
  choix.showModal();
}

async function corriger(terrain) {
  const hexagone = enCoursDeCorrection;
  if (!hexagone) return;

  const reponse = await fetch("/admin/map_fix", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: hexagone.q, r: hexagone.r, s: hexagone.s, terrain }),
  });
  // Le serveur seul décide : tant qu'il n'a pas répondu, rien ne bouge ici.
  if (!reponse.ok) return;
  const { cle: clef, terrain: retenu, corrige } = await reponse.json();

  if (corrige) corrections[clef] = retenu;
  else delete corrections[clef];

  dessinerLesCorrections();
  compter();
  choix.close();
}

function memesCorrections(unes, autres) {
  // Comparaison de contenu : l'ordre des clés n'a pas de sens ici.
  const clefs = Object.keys(unes);
  return clefs.length === Object.keys(autres).length
    && clefs.every((clef) => unes[clef] === autres[clef]);
}

function compter() {
  const nombre = Object.keys(corrections).length;
  compteur.textContent = nombre === 0 ? "aucune correction"
    : nombre === 1 ? "1 correction" : `${nombre} corrections`;
  // Le moteur a fusionné la carte à son démarrage : tout écart demande de le relancer.
  redemarrage.hidden = memesCorrections(corrections, appliquees);
}

// --- Démarrage ---

function demarrer() {
  dimensionnerLeSurlignage();
  construireLesBoutons();
  dessinerLesCorrections();
  compter();
  ajusterALaFenetre();

  plateau.addEventListener("mousemove", auSurvol);
  plateau.addEventListener("mouseleave", cacherLInfobulle);
  plateau.addEventListener("click", (evenement) => {
    const { x, y } = pixelDuPointeur(evenement, carte);
    ouvrirLeChoix(hexagoneDuPixel(x, y));
  });

  cadre.addEventListener("wheel", (evenement) => {
    evenement.preventDefault();
    changerLEchelle(echelle * Math.exp(-evenement.deltaY * 0.002),
                    evenement.clientX, evenement.clientY);
  }, { passive: false });

  document.getElementById("zoomer").addEventListener("click",
    () => changerLEchelle(echelle * 1.25, ...centreDuCadre()));
  document.getElementById("dezoomer").addEventListener("click",
    () => changerLEchelle(echelle / 1.25, ...centreDuCadre()));
  document.getElementById("ajuster").addEventListener("click", ajusterALaFenetre);
  choixRetablir.addEventListener("click",
    () => corriger(terrainDeLaCarte(cle(enCoursDeCorrection))));
  document.getElementById("choix-annuler").addEventListener("click", () => choix.close());
}

if (carte.complete) {
  demarrer();
} else {
  carte.addEventListener("load", demarrer);
}
