// La géométrie de la grille, partagée par les pages qui affichent la carte.
//
// Le calage relevé dans game_box/carte.md tient dans une origine et une matrice 2 × 2 :
//
//     centre(q, r) = origine + matrice · (q, r)
//
// Les pixels obtenus sont ceux de map.jpg (6173 × 5102), donc le repère de #plateau, qui porte
// l'image à sa taille naturelle et n'est mis à l'échelle qu'ensuite. Rien ici ne connaît les
// règles du jeu ni le DOM de la page : seulement des nombres et l'image de la carte.

function inverser([[a, b], [c, d]]) {
  const determinant = a * d - b * c;
  return [[d / determinant, -b / determinant], [-c / determinant, a / determinant]];
}

function calage(grille) {
  const [origine, matrice] = [grille.origine, grille.matrice];
  const matriceInverse = inverser(matrice);

  // Demi-largeur et demi-hauteur d'un hexagone : la matrice porte le pas de la grille, dont on
  // retire les facteurs du pavage flat-top (1,5 en x, √3 en y). Voir game_box/extraction_carte.py.
  const demiLargeur = matrice[0][0] / 1.5;
  const demiHauteur = matrice[1][1] / Math.sqrt(3);

  function centre(q, r) {
    return {
      x: origine[0] + matrice[0][0] * q + matrice[0][1] * r,
      y: origine[1] + matrice[1][0] * q + matrice[1][1] * r,
    };
  }

  function hexagoneDuPixel(x, y) {
    // Le calage inversé donne des coordonnées fractionnaires ; l'arrondi cubique les ramène sur
    // l'hexagone le plus proche en corrigeant celle des trois qui a le plus dérivé.
    const dx = x - origine[0];
    const dy = y - origine[1];
    const q = matriceInverse[0][0] * dx + matriceInverse[0][1] * dy;
    const r = matriceInverse[1][0] * dx + matriceInverse[1][1] * dy;
    const s = -q - r;

    let [aq, ar, as] = [Math.round(q), Math.round(r), Math.round(s)];
    const [ecartQ, ecartR, ecartS] = [Math.abs(aq - q), Math.abs(ar - r), Math.abs(as - s)];
    if (ecartQ > ecartR && ecartQ > ecartS) aq = -ar - as;
    else if (ecartR > ecartS) ar = -aq - as;
    else as = -aq - ar;
    return { q: aq, r: ar, s: as };
  }

  function sommets(q, r) {
    // Les six coins d'un hexagone flat-top, le premier plein est. Sert à le surligner.
    const { x, y } = centre(q, r);
    return Array.from({ length: 6 }, (_, k) => ({
      x: x + demiLargeur * Math.cos((Math.PI / 3) * k),
      y: y + demiHauteur * Math.sin((Math.PI / 3) * k),
    }));
  }

  return { centre, hexagoneDuPixel, sommets };
}

function cle(hexagone) {
  return `${hexagone.q},${hexagone.r},${hexagone.s}`;
}

function pixelDuPointeur(evenement, carte) {
  // De l'écran aux pixels de map.jpg : la carte peut être réduite, et n'est pas au coin de l'écran.
  const cadreCarte = carte.getBoundingClientRect();
  const echelle = cadreCarte.width / carte.naturalWidth;
  return {
    x: (evenement.clientX - cadreCarte.x) / echelle,
    y: (evenement.clientY - cadreCarte.y) / echelle,
  };
}
