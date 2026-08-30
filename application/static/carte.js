// Pose les pions sur la carte, et montre où ils peuvent aller.
//
// Ce fichier ne connaît aucune règle : il fait de l'affichage. Un clic est converti en
// coordonnées cubiques « q, r, s » par geometrie.js, puis le serveur dit ce qui est atteignable
// (/deplacements) et ce qui est permis (/deplacer). Les requêtes portent la clé du pion en main,
// pas son mouvement : c'est le serveur qui sait de combien de points il dispose.
//
// Les positions sont en pixels de map.jpg, donc dans le repère de #plateau, qui porte l'image à
// sa taille naturelle et n'est mis à l'échelle qu'ensuite.

const ROTATION_MAXIMALE = 5; // degrés, en avant ou en arrière

const plateau = document.getElementById("plateau");
const carte = document.getElementById("carte");
const cadre = document.getElementById("cadre");

const pions = JSON.parse(document.getElementById("pions").value);
const grille = JSON.parse(document.getElementById("grille").value);
const { centre: centreDeLHexagone, hexagoneDuPixel } = calage(grille);

// Les images posées sur la carte : les pions, et les fantômes du pion sélectionné.
const pionsPoses = [];
let fantomes = [];
let selection = null;

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

function libelle(pion, hexagone) {
  return `${pion.nom} — ${cle(hexagone)} — ${pion.mouvement} PM`;
}

function creerImage(pion, hexagone, classe) {
  const image = document.createElement("img");
  image.className = classe;
  image.src = `/pions/${pion.image}`;
  image.alt = pion.nom;
  image.title = libelle(pion, hexagone);
  image.style.width = `${grille.taille_pion}px`;
  image.style.height = `${grille.taille_pion}px`;
  poser(image, hexagone);
  plateau.appendChild(image);
  return image;
}

function poserLesPions() {
  for (const pion of pions) {
    const image = creerImage(pion, { q: pion.q, r: pion.r, s: pion.s }, "pion");
    image.pion = pion; // le pion tiré par le serveur, pour ses fantômes et son libellé
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
  image.title = libelle(image.pion, arrivee);
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

function ajusterLEchelle() {
  // La carte fait 6173 × 5102 px : on la réduit pour qu'elle tienne dans la fenêtre.
  const largeur = carte.naturalWidth;
  const hauteur = carte.naturalHeight;
  if (!largeur || !hauteur) return;

  const echelle = Math.min(window.innerWidth / largeur, window.innerHeight / hauteur);
  plateau.style.transform = `scale(${echelle})`;
  cadre.style.width = `${largeur * echelle}px`;
  cadre.style.height = `${hauteur * echelle}px`;
  cadre.style.margin = "0 auto";
}

function demarrer() {
  poserLesPions();
  ajusterLEchelle();
  plateau.addEventListener("click", auClic);
}

if (carte.complete) {
  demarrer();
} else {
  carte.addEventListener("load", demarrer);
}
window.addEventListener("resize", ajusterLEchelle);
