// Approcher et reculer sur la carte, partagé par les pages qui l'affichent.
//
// Le zoom met #plateau à l'échelle. Son transform ne compte pas dans la mise en page : c'est
// #toile qui porte la taille visible, et donc les barres de défilement de #cadre. Tout ce qui est
// posé sur la carte — les pions, le surlignage — reste exprimé en pixels de map.jpg et n'a donc
// rien à recalculer quand l'échelle change.
//
// Rien ici ne connaît le jeu : seulement l'image de la carte et les quatre éléments qui la
// portent, plus les boutons de la barre d'outils s'ils existent.
//
// Rien ici ne retient non plus quoi que ce soit d'un chargement à l'autre. La page qui veut
// retrouver sa vue au rechargement se sert des trois pièces exposées pour cela — `echelle()`,
// `centreVu()` pour la relever, `regler()` pour la reposer — et décide seule où la ranger : c'est
// `carte.js` qui l'envoie au serveur, et `map_fix.html`, qui charge le même zoom, n'en fait rien.

const ECHELLE_MIN = 0.05;
const ECHELLE_MAX = 1;
const PAS_DU_BOUTON = 1.25; // un cran de « + » ou « − »
const PAS_DE_LA_MOLETTE = 0.002; // par pixel de défilement

function zoom({ cadre, toile, plateau, carte, affichage, auChangement }) {
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
    if (auChangement) auChangement();
  }

  function centreDuCadre() {
    const visible = cadre.getBoundingClientRect();
    return [visible.x + visible.width / 2, visible.y + visible.height / 2];
  }

  function ajuster() {
    appliquer(echelleAjustee());
    ajusteeALaFenetre = true;
    cadre.scrollTo(0, 0);
    if (auChangement) auChangement();
  }

  // Poser une échelle sans rien viser : c'est ce qu'il faut pour **reprendre** une vue rangée,
  // dont le centre sera replacé juste après par `centrer`. Elle sort de l'ajustement, comme un
  // tour de molette — la vue qu'on reprend est celle de quelqu'un qui avait réglé son zoom.
  // Rien n'est signalé : reposer ce qu'on vient de lire n'est pas un changement.
  function regler(valeur) {
    appliquer(valeur);
    ajusteeALaFenetre = false;
  }

  // Amener au milieu de la fenêtre un point donné en pixels de map.jpg. La toile est centrée par
  // ses marges automatiques tant que la carte tient dans la fenêtre : son décalage entre donc dans
  // le compte. Le défilement se borne de lui-même — un point près d'un bord vient aussi près du
  // centre que la carte le permet, et rien ne bouge quand elle tient tout entière à l'écran.
  function centrer(x, y) {
    // `clientWidth` et non le rectangle du cadre : c'est la partie visible, barres de défilement
    // déduites, et c'est en son milieu que le point doit venir.
    cadre.scrollLeft = toile.offsetLeft + x * echelle - cadre.clientWidth / 2;
    cadre.scrollTop = toile.offsetTop + y * echelle - cadre.clientHeight / 2;
  }

  // L'inverse de `centrer` : quel point de la carte est en ce moment au milieu de la fenêtre.
  // C'est cela qu'une page range pour retrouver sa vue, et non le défilement : un `scrollLeft` en
  // pixels d'écran ne voudrait plus rien dire à une autre échelle, ni sur un autre écran.
  function centreVu() {
    return {
      x: (cadre.scrollLeft - toile.offsetLeft + cadre.clientWidth / 2) / echelle,
      y: (cadre.scrollTop - toile.offsetTop + cadre.clientHeight / 2) / echelle,
    };
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
  // `centrer` est laissé aux pages : celle qui sait ce qu'il y a sur la carte dit quoi viser.
  return { ajuster, centrer, regler, centreVu, echelle: () => echelle,
           suitLaFenetre: () => ajusteeALaFenetre };
}
