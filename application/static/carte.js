// Pose les pions sur la carte, et montre où ils peuvent aller.
//
// Ce fichier ne connaît aucune règle : il fait de l'affichage. Un clic est converti en
// coordonnées cubiques « q, r, s » par geometrie.js, puis le serveur dit ce qui est atteignable
// (/deplacements) et ce qui est permis (/deplacer). Les requêtes portent la clé du pion en main,
// pas son mouvement : c'est le serveur qui sait de combien de points il dispose.
//
// Les positions sont en pixels de map.jpg, donc dans le repère de #plateau, qui porte l'image à
// sa taille naturelle et n'est mis à l'échelle qu'ensuite : approcher ou reculer ne change donc
// rien à ce qui est posé sur la carte. Le zoom lui-même est dans zoom.js, partagé avec la page de
// correction.

const ROTATION_MAXIMALE = 5; // degrés, en avant ou en arrière

// Les valeurs chiffrées du carton, dans l'ordre où la fiche les donne à lire (voir la section
// « Valeurs lues sur les pions » de game_box/pions/README.md). « Mouvement » est le budget de
// déplacement que le serveur a retenu, celui-là même dont le moteur se sert. Le symbole et les
// remarques n'y sont pas : ce sont des mots, pas des nombres, et ils ont leur ligne à eux.
const CHAMPS = [
  ["force", "Force"],
  ["mouvement", "Mouvement"],
  ["tir", "Tir"],
  ["portee", "Portée"],
  ["mouvement_vol", "Vol"],
  ["facultes_speciales", "Facultés"],
];

const ABSENTE = "—"; // ce que le carton ne porte pas

const plateau = document.getElementById("plateau");
const carte = document.getElementById("carte");
const cadre = document.getElementById("cadre");
const toile = document.getElementById("toile");

const fiche = document.getElementById("fiche");
const ficheImage = document.getElementById("fiche-image");
const ficheNom = document.getElementById("fiche-nom");
const ficheAppoint = document.getElementById("fiche-appoint");
const ficheSymbole = document.getElementById("fiche-symbole");
const ficheValeurs = document.getElementById("fiche-valeurs");
const ficheRemarques = document.getElementById("fiche-remarques");

const pions = JSON.parse(document.getElementById("pions").value);
const grille = JSON.parse(document.getElementById("grille").value);
const { centre: centreDeLHexagone, hexagoneDuPixel } = calage(grille);

// Les images posées sur la carte : les pions, et les fantômes du pion sélectionné.
const pionsPoses = [];
let fantomes = [];
let selection = null;
let survole = null; // le pion dont la fiche est ouverte
let vue = null; // le zoom, monté une fois la carte chargée

function hexagoneClique(evenement) {
  const { x, y } = pixelDuPointeur(evenement, carte);
  return hexagoneDuPixel(x, y);
}

function poser(image, hexagone) {
  const centre = centreDeLHexagone(hexagone.q, hexagone.r);
  const inclinaison = (Math.random() * 2 - 1) * ROTATION_MAXIMALE;
  image.dataset.q = hexagone.q;
  image.dataset.r = hexagone.r;
  image.dataset.s = hexagone.s;
  image.style.left = `${centre.x}px`;
  image.style.top = `${centre.y}px`;
  // Le décalage de moitié centre le pion sur l'hexagone ; la rotation vient après.
  image.style.transform = `translate(-50%, -50%) rotate(${inclinaison.toFixed(2)}deg)`;
}

// --- La fiche de l'unité survolée ---
//
// Tout est déjà là : le serveur a passé les valeurs du carton dans le champ caché, le survol ne
// lui demande donc rien. La fiche prolonge la barre d'outils, qui est hors de #plateau : elle
// garde sa taille quelle que soit l'échelle, et ne se pose jamais sur la carte.

function montrerLaFiche(image) {
  const pion = image.pion;
  // La case courante, lue sur l'image : un pion déplacé n'est plus sur celle du scénario.
  const hexagone = { q: image.dataset.q, r: image.dataset.r, s: image.dataset.s };

  ficheImage.src = `/pions/${pion.image}`;
  ficheImage.alt = pion.nom;
  ficheNom.textContent = pion.nom;
  ficheAppoint.textContent = `${pion.camp} — ${cle(hexagone)}`;
  ficheSymbole.textContent = pion.symbole ?? ABSENTE;
  // Une remarque est ce que la photo laisse en suspens : elle n'apparaît que s'il y en a une.
  ficheRemarques.textContent = pion.remarques ?? "";
  ficheRemarques.hidden = !pion.remarques;

  ficheValeurs.replaceChildren();
  for (const [champ, libelle] of CHAMPS) {
    const terme = document.createElement("dt");
    terme.textContent = libelle;
    const valeur = document.createElement("dd");
    const lue = pion[champ];
    valeur.textContent = lue ?? ABSENTE;
    if (lue === null || lue === undefined) valeur.className = "absente";
    ficheValeurs.append(terme, valeur);
  }

  survole = image;
  fiche.hidden = false;
}

function cacherLaFiche() {
  survole = null;
  fiche.hidden = true;
}

function estUnPionPose(cible) {
  // Les fantômes sont écartés : ils portent l'unité déjà sélectionnée, et couvrir la carte de
  // survols qui répètent la même fiche n'apprendrait rien.
  return cible instanceof HTMLElement
    && cible.classList.contains("pion") && !cible.classList.contains("fantome");
}

function creerImage(pion, hexagone, classe) {
  const image = document.createElement("img");
  image.className = classe;
  image.src = `/pions/${pion.image}`;
  image.alt = pion.nom;
  image.style.width = `${grille.taille_pion}px`;
  image.style.height = `${grille.taille_pion}px`;
  poser(image, hexagone);
  plateau.appendChild(image);
  return image;
}

function poserLesPions() {
  for (const pion of pions) {
    const image = creerImage(pion, { q: pion.q, r: pion.r, s: pion.s }, "pion");
    image.pion = pion; // le pion tiré par le serveur, pour ses fantômes et sa fiche
    pionsPoses.push(image);
  }
}

function pionSurLHexagone(hexagone) {
  return pionsPoses.find((image) => image.dataset.q === String(hexagone.q)
    && image.dataset.r === String(hexagone.r)) ?? null;
}

function fantomeSurLHexagone(hexagone) {
  return fantomes.find((image) => image.dataset.q === String(hexagone.q)
    && image.dataset.r === String(hexagone.r)) ?? null;
}

function effacerLesFantomes() {
  for (const fantome of fantomes) fantome.remove();
  fantomes = [];
  if (selection) selection.classList.remove("selectionne");
  selection = null;
}

async function montrerLesDeplacements(image) {
  effacerLesFantomes();
  selection = image;
  image.classList.add("selectionne");

  const reponse = await fetch(`/deplacements?q=${image.dataset.q}&r=${image.dataset.r}`
    + `&s=${image.dataset.s}&pion=${encodeURIComponent(image.pion.cle)}`);
  if (!reponse.ok) return;
  const { hexagones } = await reponse.json();
  // La sélection a pu changer pendant l'attente de la réponse.
  if (selection !== image) return;

  fantomes = hexagones.map((hexagone) => creerImage(image.pion, hexagone, "pion fantome"));
}

async function deplacer(image, hexagone) {
  const reponse = await fetch("/deplacer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      depart: { q: Number(image.dataset.q), r: Number(image.dataset.r), s: Number(image.dataset.s) },
      arrivee: hexagone,
      pion: image.pion.cle,
    }),
  });
  if (!reponse.ok) return;
  const { autorise, arrivee } = await reponse.json();
  if (!autorise) return;

  effacerLesFantomes();
  // Le pion a été repris en main : il se repose de travers, autrement que la fois d'avant.
  poser(image, arrivee);
  // Si le pointeur était resté sur ce pion, sa fiche doit dire la case où il vient d'arriver.
  if (survole === image) montrerLaFiche(image);
}

function auClic(evenement) {
  const hexagone = hexagoneClique(evenement);

  if (selection && fantomeSurLHexagone(hexagone)) {
    deplacer(selection, hexagone);
    return;
  }

  const pion = pionSurLHexagone(hexagone);
  if (!pion || pion === selection) {
    effacerLesFantomes();
    return;
  }
  montrerLesDeplacements(pion);
}

function demarrer() {
  poserLesPions();
  // La carte fait 6173 × 5102 px : elle s'ouvre réduite à la fenêtre, et la molette ou les
  // boutons « + », « − » et « ajuster » la rapprochent — jusqu'à la taille du scan, où un pion
  // se lit vraiment.
  vue = zoom({ cadre, toile, plateau, carte, affichage: document.getElementById("echelle") });
  vue.ajuster();
  plateau.addEventListener("click", auClic);
  // Délégués sur le plateau, comme le clic : les fantômes naissent et meurent en cours de route,
  // et un écouteur par image serait à refaire à chaque déplacement.
  plateau.addEventListener("mouseover", (evenement) => {
    if (estUnPionPose(evenement.target)) montrerLaFiche(evenement.target);
  });
  plateau.addEventListener("mouseout", (evenement) => {
    if (estUnPionPose(evenement.target)) cacherLaFiche();
  });
}

if (carte.complete) {
  demarrer();
} else {
  carte.addEventListener("load", demarrer);
}

// Redimensionner la fenêtre réajuste la carte, tant qu'on n'a pas réglé l'échelle soi-même : ce
// serait défaire le zoom qu'on vient de choisir.
window.addEventListener("resize", () => {
  if (vue && vue.suitLaFenetre()) vue.ajuster();
});
