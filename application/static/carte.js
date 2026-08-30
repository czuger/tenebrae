// Pose les pions envoyés par Flask sur la carte.
//
// Le serveur donne des coordonnées cubiques « q, r, s » ; le calage de la grille sur map.jpg
// (voir game_box/carte.md) tient dans une origine et une matrice 2 × 2 :
//
//     centre(q, r) = origine + matrice · (q, r)
//
// Les positions obtenues sont en pixels de map.jpg, donc dans le repère de #plateau, qui porte
// l'image à sa taille naturelle et n'est mis à l'échelle qu'ensuite.

const ROTATION_MAXIMALE = 5; // degrés, en avant ou en arrière

const plateau = document.getElementById("plateau");
const carte = document.getElementById("carte");
const cadre = document.getElementById("cadre");

const pions = JSON.parse(document.getElementById("pions").value);
const grille = JSON.parse(document.getElementById("grille").value);

function centreDeLHexagone(q, r) {
  const [origine, matrice] = [grille.origine, grille.matrice];
  return {
    x: origine[0] + matrice[0][0] * q + matrice[0][1] * r,
    y: origine[1] + matrice[1][0] * q + matrice[1][1] * r,
  };
}

function poserLesPions() {
  const taille = grille.taille_pion;

  for (const pion of pions) {
    const centre = centreDeLHexagone(pion.q, pion.r);
    const inclinaison = (Math.random() * 2 - 1) * ROTATION_MAXIMALE;

    const image = document.createElement("img");
    image.className = "pion";
    image.src = `/pions/${pion.image}`;
    image.alt = pion.nom;
    image.title = `${pion.nom} — ${pion.q},${pion.r},${pion.s}`;
    image.dataset.q = pion.q;
    image.dataset.r = pion.r;
    image.dataset.s = pion.s;
    image.style.width = `${taille}px`;
    image.style.height = `${taille}px`;
    image.style.left = `${centre.x}px`;
    image.style.top = `${centre.y}px`;
    // Le décalage de moitié centre le pion sur l'hexagone ; la rotation vient après.
    image.style.transform = `translate(-50%, -50%) rotate(${inclinaison.toFixed(2)}deg)`;
    plateau.appendChild(image);
  }
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
}

if (carte.complete) {
  demarrer();
} else {
  carte.addEventListener("load", demarrer);
}
window.addEventListener("resize", ajusterLEchelle);
