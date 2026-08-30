// Approcher et reculer sur la carte, partagé par les pages qui l'affichent.
//
// Le zoom met #plateau à l'échelle. Son transform ne compte pas dans la mise en page : c'est
// #toile qui porte la taille visible, et donc les barres de défilement de #cadre. Tout ce qui est
// posé sur la carte — les pions, le surlignage — reste exprimé en pixels de map.jpg et n'a donc
// rien à recalculer quand l'échelle change.
//
// Rien ici ne connaît le jeu : seulement l'image de la carte et les quatre éléments qui la
// portent, plus les boutons de la barre d'outils s'ils existent.

const ECHELLE_MIN = 0.05;
const ECHELLE_MAX = 1;
const PAS_DU_BOUTON = 1.25; // un cran de « + » ou « − »
const PAS_DE_LA_MOLETTE = 0.002; // par pixel de défilement

function zoom({ cadre, toile, plateau, carte, affichage }) {
  let echelle = 1;
  // Tant que personne n'a touché à l'échelle, la carte suit la fenêtre et se réajuste avec elle.
  let ajusteeALaFenetre = true;

  function echelleAjustee() {
    return Math.min(window.innerWidth / carte.naturalWidth,
                    window.innerHeight / carte.naturalHeight);
  }

  function appliquer(valeur) {
    echelle = Math.min(ECHELLE_MAX, Math.max(ECHELLE_MIN, valeur));
    plateau.style.transform = `scale(${echelle})`;
    toile.style.width = `${carte.naturalWidth * echelle}px`;
    toile.style.height = `${carte.naturalHeight * echelle}px`;
    if (affichage) affichage.textContent = `${Math.round(echelle * 100)} %`;
  }

  function changer(valeur, clientX, clientY) {
    // Le point de la carte sous le pointeur doit y rester : on le relève avant, on replace le
    // défilement après.
    const point = pixelDuPointeur({ clientX, clientY }, carte);
    appliquer(valeur);
    ajusteeALaFenetre = false;
    const visible = cadre.getBoundingClientRect();
    cadre.scrollLeft = point.x * echelle + visible.x - clientX;
    cadre.scrollTop = point.y * echelle + visible.y - clientY;
  }

  function centreDuCadre() {
    const visible = cadre.getBoundingClientRect();
    return [visible.x + visible.width / 2, visible.y + visible.height / 2];
  }

  function ajuster() {
    appliquer(echelleAjustee());
    ajusteeALaFenetre = true;
    cadre.scrollTo(0, 0);
  }

  function brancher(identifiant, action) {
    document.getElementById(identifiant)?.addEventListener("click", action);
  }

  cadre.addEventListener("wheel", (evenement) => {
    evenement.preventDefault();
    changer(echelle * Math.exp(-evenement.deltaY * PAS_DE_LA_MOLETTE),
            evenement.clientX, evenement.clientY);
  }, { passive: false });

  brancher("zoomer", () => changer(echelle * PAS_DU_BOUTON, ...centreDuCadre()));
  brancher("dezoomer", () => changer(echelle / PAS_DU_BOUTON, ...centreDuCadre()));
  brancher("ajuster", ajuster);

  // `suitLaFenetre` dit si l'échelle est encore celle de l'ajustement : une page qui se
  // redimensionne peut ainsi réajuster sans défaire le zoom que l'on vient de régler à la main.
  return { ajuster, suitLaFenetre: () => ajusteeALaFenetre };
}
