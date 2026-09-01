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

const phaseLibelle = document.getElementById("phase-libelle");
const boutonAttaquer = document.getElementById("attaquer");
const boutonAnnuler = document.getElementById("annuler-combat");
const boutonLocaliser = document.getElementById("localiser");
const boutonPhaseSuivante = document.getElementById("phase-suivante");

const boutonJoueur = document.getElementById("joueur");
const zoneDeMessage = document.getElementById("message");
const dialogueDeLaTable = document.getElementById("table-dialogue");
const tableTitre = document.getElementById("table-titre");
const tablePlaces = document.getElementById("table-places");
const boutonQuitter = document.getElementById("table-quitter");
const boutonContreIA = document.getElementById("table-contre-ia");

// Le pseudo que le serveur donne à la place tenue par l'IA (voir `moteur/ia.py`).
const NOM_IA = "IA";

let pions = JSON.parse(document.getElementById("pions").value);
const grille = JSON.parse(document.getElementById("grille").value);
const { centre: centreDeLHexagone, hexagoneDuPixel } = calage(grille);

// Les images posées sur la carte : les pions, et les fantômes du pion sélectionné.
const pionsPoses = [];
let fantomes = [];
let selection = null;
let survole = null; // le pion dont la fiche est ouverte
let vue = null; // le zoom, monté une fois la carte chargée

// La phase courante, telle que le serveur la donne : { camp, type, armee, libelle, numero,
// indisponibles }. Le type ne vaut jamais « magie » — le serveur la saute. `indisponibles` dit les
// cases des unités qui ont déjà donné cette phase-ci : { attaquants: [...], cibles: [...] }.
let phase = JSON.parse(document.getElementById("phase").value);

// Qui regarde et qui tient quel camp, tel que le serveur le donne : { connecte, pseudo, avatar,
// administrateur, camps, armees, places }. `camps` dit les camps que **ce** navigateur tient —
// d'ordinaire un seul. `places` donne le pseudo de chaque occupant, jamais son identifiant.
let table = JSON.parse(document.getElementById("table").value);

// Le numéro de version de la partie. Il monte à chaque coup joué, du nôtre comme de celui d'en
// face : c'est à lui qu'on voit qu'il y a quelque chose à reprendre (voir `suivreLaPartie`).
let version = Number(document.getElementById("version").value);

// La sélection de la phase de combat : une cible adverse, et un ensemble d'attaquants alliés.
let cible = null;
let attaquants = new Set();

// --- Retrouver le dernier pion cliqué ---
//
// Approcher la carte fait vite perdre de vue l'unité qu'on manœuvre : le bouton « localiser » la
// ramène au centre. On retient l'image, pas une case — un pion déplacé emporte son repère avec
// lui. Le souvenir traverse les phases ; seule l'élimination l'efface.

let dernierPionClique = null;

function retenirLePion(image) {
  dernierPionClique = image;
  boutonLocaliser.disabled = false;
}

function oublierLePion() {
  dernierPionClique = null;
  boutonLocaliser.disabled = true;
}

function localiser() {
  if (!dernierPionClique) return;
  const { x, y } = centreDeLHexagone(Number(dernierPionClique.dataset.q),
                                    Number(dernierPionClique.dataset.r));
  vue.centrer(x, y);
}

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

  const reponse = await envoyer(`/deplacements?q=${image.dataset.q}&r=${image.dataset.r}`
    + `&s=${image.dataset.s}&pion=${encodeURIComponent(image.pion.cle)}`);
  if (!reponse) return;
  const { hexagones } = await reponse.json();
  // La sélection a pu changer pendant l'attente de la réponse.
  if (selection !== image) return;

  fantomes = hexagones.map((hexagone) => creerImage(image.pion, hexagone, "pion fantome"));
}

async function deplacer(image, hexagone) {
  const reponse = await envoyer("/deplacer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      depart: { q: Number(image.dataset.q), r: Number(image.dataset.r), s: Number(image.dataset.s) },
      arrivee: hexagone,
      pion: image.pion.cle,
    }),
  });
  if (!reponse) return;
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

  // Le souvenir est pris avant tout tri : « localiser » suit le doigt, pas les règles. Un clic sur
  // une case vide — ou sur un fantôme, où le pion n'est pas encore — laisse le repère précédent.
  const clique = pionSurLHexagone(hexagone);
  if (clique) retenirLePion(clique);

  if (phase.type === "combat") {
    auClicDeCombat(hexagone);
    return;
  }

  if (selection && fantomeSurLHexagone(hexagone)) {
    deplacer(selection, hexagone);
    return;
  }

  const pion = pionSurLHexagone(hexagone);
  if (!pion || pion === selection || pion.pion.camp !== phase.camp) {
    // Hors de sa phase de mouvement, une unité ne montre pas ses cases : seul le camp actif joue.
    effacerLesFantomes();
    return;
  }
  montrerLesDeplacements(pion);
}

// --- La phase de combat ---
//
// Un clic sur une unité adverse en fait la cible (surlignée en rouge). Les clics suivants sur des
// unités du camp actif les ajoutent comme attaquants s'ils sont à portée (surlignés en or) ; le
// serveur seul juge de la portée. Le bouton « Attaquer » résout, « Annuler » vide la sélection.
//
// Une unité ne combat qu'une fois par phase — elle attaque une fois, elle n'est prise pour cible
// qu'une fois. Là encore, c'est le serveur qui tient le compte : la page l'interroge avant de
// surligner, et grise ce qu'il lui dit d'avoir déjà donné.

function hexagoneDuPion(image) {
  return { q: Number(image.dataset.q), r: Number(image.dataset.r), s: Number(image.dataset.s) };
}

function majBoutonsDeCombat() {
  const enCombat = phase.type === "combat";
  boutonAnnuler.hidden = !(enCombat && cible);
  boutonAttaquer.hidden = !(enCombat && cible && attaquants.size > 0);
}

function nettoyerLeCombat() {
  if (cible) cible.classList.remove("cible");
  for (const attaquant of attaquants) attaquant.classList.remove("attaquant");
  cible = null;
  attaquants = new Set();
  majBoutonsDeCombat();
}

async function auClicDeCombat(hexagone) {
  const pion = pionSurLHexagone(hexagone);
  if (!pion) return;

  if (pion === cible) {
    nettoyerLeCombat();
    return;
  }

  if (!cible) {
    if (pion.pion.camp === phase.camp) return; // il faut d'abord une cible adverse
    const c = pion.dataset;
    const reponse = await envoyer(`/combat/cible?cq=${c.q}&cr=${c.r}&cs=${c.s}`);
    if (!reponse) return;
    const { disponible } = await reponse.json();
    // Déjà attaquée cette phase-ci : le refus est parti au journal du serveur, et rien ne rougit.
    if (!disponible || cible) return;
    cible = pion;
    cible.classList.add("cible");
    majBoutonsDeCombat();
    return;
  }

  if (pion.pion.camp !== phase.camp) return; // une autre unité adverse : sans effet

  if (attaquants.has(pion)) {
    attaquants.delete(pion);
    pion.classList.remove("attaquant");
    majBoutonsDeCombat();
    return;
  }

  const c = cible.dataset;
  const a = pion.dataset;
  const reponse = await envoyer(`/combat/portee?cq=${c.q}&cr=${c.r}&cs=${c.s}`
    + `&aq=${a.q}&ar=${a.r}&as=${a.s}`);
  if (!reponse) return;
  const { a_portee, disponible } = await reponse.json();
  if (!a_portee || !disponible) return; // le refus est parti au journal du serveur

  attaquants.add(pion);
  pion.classList.add("attaquant");
  majBoutonsDeCombat();
}

// Les unités qui ont déjà donné sont grisées : sans cela, rien ne distinguerait sur la carte une
// unité qu'on peut encore engager d'une qui refusera le clic.
function marquerLesIndisponibles(indisponibles) {
  const cases = new Set([...(indisponibles?.attaquants ?? []),
                         ...(indisponibles?.cibles ?? [])].map(cle));
  for (const image of pionsPoses) {
    image.classList.toggle("indisponible", cases.has(cle(image.dataset)));
  }
}

async function attaquer() {
  if (!cible || attaquants.size === 0) return;
  const reponse = await envoyer("/combat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cible: hexagoneDuPion(cible),
      attaquants: [...attaquants].map(hexagoneDuPion),
    }),
  });
  if (!reponse) return;
  const resultat = await reponse.json();
  if (resultat.resolu) {
    for (const elimine of resultat.elimines) retirerLePion(elimine);
  }
  nettoyerLeCombat();
  marquerLesIndisponibles(resultat.indisponibles);
}

function retirerLePion(hexagone) {
  const image = pionSurLHexagone(hexagone);
  if (!image) return;
  const rang = pionsPoses.indexOf(image);
  if (rang >= 0) pionsPoses.splice(rang, 1);
  attaquants.delete(image);
  if (cible === image) cible = null;
  if (dernierPionClique === image) oublierLePion();
  image.remove();
}

function rafraichirLaPhase(nouvelle) {
  phase = nouvelle;
  phaseLibelle.textContent = phase.libelle;
  effacerLesFantomes();
  nettoyerLeCombat();
  // Une nouvelle phase de combat repart avec toutes ses unités : le serveur envoie des listes
  // vides, et le grisage tombe de lui-même.
  marquerLesIndisponibles(phase.indisponibles);
  majBoutonsDuJoueur();
}

async function phaseSuivante() {
  const reponse = await envoyer("/phase/suivante", { method: "POST" });
  if (!reponse) return;
  rafraichirLaPhase(await reponse.json());
}

// --- Parler au serveur ---
//
// Le serveur refuse maintenant un coup joué hors de son tour, par un visiteur sans compte ou par
// quelqu'un qui n'a pas pris place. Un refus muet — ce que faisait `if (!reponse.ok) return;` —
// laisserait croire à une panne : on montre ces deux-là, et ceux-là seulement. Les autres échecs
// gardent le silence qu'ils avaient, leurs refus partant au journal du serveur.

const DELAI_DU_MESSAGE = 4000; // millisecondes

async function envoyer(url, options) {
  const reponse = await fetch(url, options);
  if (reponse.status === 401 || reponse.status === 403) {
    const { message } = await reponse.json().catch(() => ({}));
    signaler(message ?? "Ce n'est pas à vous de jouer.");
    return null;
  }
  return reponse.ok ? reponse : null;
}

function signaler(texte) {
  zoneDeMessage.textContent = texte;
  zoneDeMessage.hidden = false;
  clearTimeout(signaler.minuterie);
  signaler.minuterie = setTimeout(() => { zoneDeMessage.hidden = true; }, DELAI_DU_MESSAGE);
}

// --- Le joueur et sa place ---

function cEstMonTour() {
  return table.camps.includes(phase.camp);
}

// Un bouton qu'on ne peut pas presser s'éteint plutôt que de rendre un refus. `#outils
// button:disabled` est déjà stylé par zoom.css : l'atténuation vient sans une ligne de plus.
function majBoutonsDuJoueur() {
  boutonPhaseSuivante.disabled = !cEstMonTour();
  boutonAttaquer.disabled = !cEstMonTour();
}

function majBoutonDuCompte() {
  boutonJoueur.textContent = "";
  if (!table.connecte) {
    boutonJoueur.textContent = "Se connecter";
    boutonJoueur.title = "S'identifier par Discord pour jouer";
    return;
  }
  if (table.avatar) {
    const avatar = document.createElement("img");
    avatar.src = table.avatar;
    avatar.alt = "";
    boutonJoueur.appendChild(avatar);
  }
  const pseudo = document.createElement("span");
  pseudo.className = "pseudo";
  pseudo.textContent = table.pseudo;
  boutonJoueur.appendChild(pseudo);
  const camps = table.camps.map((camp) => table.armees[camp]).join(", ");
  boutonJoueur.title = camps ? `Vous tenez : ${camps}` : "Vous ne tenez aucun camp";
}

// Une ligne par camp : l'armée, son occupant, et de quoi s'y asseoir s'il est libre.
function construireLesPlaces() {
  tablePlaces.textContent = "";
  for (const [camp, armee] of Object.entries(table.armees)) {
    const ligne = document.createElement("div");
    ligne.className = table.camps.includes(camp) ? "camp mien" : "camp";
    ligne.dataset.camp = camp;

    const nom = document.createElement("span");
    nom.textContent = armee;
    ligne.appendChild(nom);

    const occupant = table.places[camp];
    if (occupant) {
      const tenu = document.createElement("span");
      tenu.className = "occupant";
      tenu.textContent = table.camps.includes(camp) ? `${occupant} (vous)` : occupant;
      ligne.appendChild(tenu);
    } else if (table.camps.length > 0) {
      // On tient déjà un camp : la place reste libre, mais elle n'est pas pour nous.
      const libre = document.createElement("span");
      libre.className = "libre";
      libre.textContent = "libre";
      ligne.appendChild(libre);
    } else {
      const bouton = document.createElement("button");
      bouton.type = "button";
      bouton.textContent = "Prendre ce camp";
      bouton.addEventListener("click", () => prendrePlace(camp));
      ligne.appendChild(bouton);
    }
    tablePlaces.appendChild(ligne);
  }
  boutonQuitter.hidden = table.camps.length === 0;
  // Repartir de zéro contre l'IA demande d'être assis, et que l'autre camp soit à donner :
  // libre, ou déjà tenu par l'IA. Un camp tenu par un humain n'est pas à donner.
  const adverses = Object.keys(table.armees).filter((camp) => !table.camps.includes(camp));
  boutonContreIA.hidden = table.camps.length === 0
    || !adverses.every((camp) => !table.places[camp] || table.places[camp] === NOM_IA);
}

function ouvrirLaTable() {
  tableTitre.textContent = table.camps.length
    ? `Vous jouez ${table.camps.map((camp) => table.armees[camp]).join(", ")}`
    : "Prenez place à un camp pour jouer";
  construireLesPlaces();
  dialogueDeLaTable.showModal();
}

function majLaTable(nouvelle) {
  table = nouvelle;
  majBoutonDuCompte();
  majBoutonsDuJoueur();
  if (dialogueDeLaTable.open) ouvrirLaTable();
}

async function prendrePlace(camp) {
  const reponse = await envoyer("/partie/place", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ camp }),
  });
  if (!reponse) return;
  const resultat = await reponse.json();
  if (!resultat.assis) signaler(resultat.message);
  // Assis, on n'a plus rien à faire dans ce dialogue : il se referme sur la partie. Le laisser
  // ouvert masquerait la carte, et son fond modal avalerait le clic suivant.
  else dialogueDeLaTable.close();
  majLaTable(resultat);
}

async function quitterLaPlace() {
  const reponse = await envoyer("/partie/place/quitter", { method: "POST" });
  if (!reponse) return;
  majLaTable(await reponse.json());
}

async function nouvellePartieContreIA() {
  const reponse = await envoyer("/partie/nouvelle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contre_ia: true }),
  });
  if (!reponse) return;
  const resultat = await reponse.json();
  // La réponse porte la partie neuve entière — et si l'IA ouvrait le scénario, son premier tour
  // est déjà joué : les pions arrivent tels qu'elle les a laissés.
  reposerLesPions(resultat.pions);
  rafraichirLaPhase(resultat.phase);
  majLaTable(resultat);
  dialogueDeLaTable.close();
}

async function seDeconnecter() {
  await fetch("/deconnexion", { method: "POST" });
  location.reload();
}

// --- Suivre la partie de l'adversaire ---
//
// Deux joueurs, deux navigateurs : sans cela, chacun resterait devant un plateau périmé jusqu'à
// ce qu'il pense à recharger. On demande donc au serveur, régulièrement, s'il s'est passé quelque
// chose — en lui donnant le numéro de version qu'on connaît. Tant que rien n'a bougé, il ne rend
// que ce numéro ; dès qu'il a changé, tout revient d'un coup et la scène se repose.

const PERIODE_DU_SUIVI = 3000; // millisecondes

async function suivreLaPartie() {
  // Un onglet caché ne regarde rien : inutile de tenir le serveur éveillé pour lui.
  if (document.hidden) return;
  const reponse = await fetch(`/partie/etat?version=${version}`).catch(() => null);
  if (!reponse || !reponse.ok) return; // le serveur redémarre : on retentera dans trois secondes
  const etat = await reponse.json();
  version = etat.version;
  if (!etat.change) return;

  // On ne défait pas ce que le joueur est en train de faire de son côté : une sélection ou un
  // combat en cours de composition sont abandonnés, ils portaient sur une position dépassée.
  reposerLesPions(etat.pions);
  rafraichirLaPhase(etat.phase);
  majLaTable(etat.table);
}

function reposerLesPions(nouveaux) {
  effacerLesFantomes();
  nettoyerLeCombat();
  for (const image of pionsPoses) image.remove();
  pionsPoses.length = 0;
  oublierLePion(); // le repère visait une image qui vient d'être retirée du plateau
  pions = nouveaux;
  poserLesPions();
}

function demarrer() {
  poserLesPions();
  phaseLibelle.textContent = phase.libelle;
  marquerLesIndisponibles(phase.indisponibles);
  document.getElementById("phase-suivante").addEventListener("click", phaseSuivante);
  boutonAttaquer.addEventListener("click", attaquer);
  boutonAnnuler.addEventListener("click", nettoyerLeCombat);
  boutonLocaliser.addEventListener("click", localiser);
  boutonJoueur.addEventListener("click", () => {
    if (table.connecte) ouvrirLaTable();
    else location.href = "/connexion";
  });
  boutonQuitter.addEventListener("click", quitterLaPlace);
  boutonContreIA.addEventListener("click", nouvellePartieContreIA);
  document.getElementById("table-deconnexion").addEventListener("click", seDeconnecter);
  document.getElementById("table-fermer").addEventListener("click", () => {
    dialogueDeLaTable.close();
  });
  majBoutonDuCompte();
  majBoutonsDuJoueur();
  setInterval(suivreLaPartie, PERIODE_DU_SUIVI);
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
