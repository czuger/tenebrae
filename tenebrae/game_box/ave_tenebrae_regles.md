# Ave Tenebrae

*Jeu de François Marcela-Froideval*

> Transcription en Markdown du fascicule de règles (`ave_tenebrae_regles.pdf`, 16 pages).
> Le texte original est composé en caractères gothiques ; l'orthographe a été rétablie en
> français moderne (le gothique utilise le glyphe « b » pour « v »). Les illustrations ne
> sont pas reprises ; les tableaux sont convertis en tableaux Markdown.
>
> Les règles ne détaillent jamais le contenu des planches de pions : voir `pions/README.md`
> pour l'inventaire complet des unités, classé par faction et par utilité.

---

## Introduction

Ave Tenebrae est une simulation stratégique de type fantastique, qui se joue à deux joueurs ;
mais on peut également jouer jusqu'à quatre joueurs.

L'aube se lève sur les ruines de la troisième province de l'Empire Tharque. Tout autour de vous,
des flammes et des monceaux de cadavres. Les forts sont abattus, les villages rasés, les forêts en
feu : c'est la fin de la civilisation.

L'aube noire se lève et déjà vous entendez au loin les troupes victorieuses saluer le Magiocrate
Ovarth, en scandant deux mots qui vous font horreur : « Ave Tenebrae ». Vous, Général en Chef des
armées de l'Empire, avez échoué. Vous n'avez pu contenir les hordes hurlantes, les armées
démoniaques et le flot incessant des morts vivants. À cause de vous, l'Empire qui maintenant ne
pourra plus résister, va être anéanti, et votre nom à jamais sera maudit, par tous les descendants
de l'Empire. Cependant, des Dieux cléments ont eu pitié de vous et, lentement autour de vous, un
brouillard étrange se forme et au travers, instinctivement, vous voyez vos soldats morts se relever,
et lentement, vous voyez le temps aller à reculons jusqu'au moment où les portes, qui vomirent les
immondes armées du Magiocrate, se referment.

Autour de vous, tout est normal comme avant, et alors vous entendez une voix puissante tonner dans
le ciel : vos Dieux qui vous donnent une chance, la dernière. Le temps a été remonté et maintenant
vous devez réussir là où vous aviez échoué ; mais prenez garde, car tout échec provoquera votre
anéantissement à jamais, car si les Dieux sont parfois cléments, ils pardonnent rarement l'échec.

L'aube se lève et avec elle, des portes lointaines s'ouvrent. La horde hurlante approche, mais
cette fois-ci vous êtes prêt.

---

# Règles

## Matériel

Le jeu comprend une carte ; un fascicule de règles ; plusieurs planches de pions et quelques aides
de jeu.

- **La carte** : elle représente une partie de la région des Dreamrifts, que contrôlent le
  Magiocrate et l'Empire, ainsi que diverses petits royaumes ou ethnies.
  Sur la carte est surimprimée une grille d'hexagones, qui facilitera le mouvement des pions et
  l'appréciation des distances. Chaque hexagone représente une distance de 1 km environ.
- **Les pions** : ils symbolisent les différentes unités qui s'affrontent sur la carte ; chaque pion
  porte plusieurs indications qui déterminent ses divers potentiels : combat, mouvement, tir,
  distance de tir, facultés spéciales, type de l'unité, etc.

### Carte vierge

Une feuille d'hexagones vierge vous est fournie afin que vous créiez vos propres terrains
d'affrontements pour vos propres scénarios. Vous trouverez facilement dans le commerce d'autres
feuilles d'hexagones vierges.

### Anatomie d'un pion

```
        Facultés spéciales
                 |
      +----------v----------+
      |   7      p      3   |  <- Force d'attaque et de défense (gauche) / Mouvement (droite)
      |      +---------+    |
      |      |   [X]   |    |  <- Identification (symbole du type d'unité)
      |      +---------+    |
      |   7     (8)     3   |  <- Force de combat par tir de missile (gauche) / Portée des missiles (droite)
      +----------^----------+
                 |
     Mouvement en vol (chiffre entre parenthèses)
     (sauf lettre : type de non humain) ou G : garde
```

| Position sur le pion | Signification |
| --- | --- |
| Haut, au centre | Facultés spéciales (lettre) |
| Haut, à gauche | Force d'attaque et de défense |
| Haut, à droite | Mouvement |
| Centre | Identification (symbole du type d'unité) |
| Bas, à gauche | Force de combat par tir de missile |
| Bas, à droite | Portée des missiles |
| Bas, au centre (entre parenthèses) | Mouvement en vol — sauf lettre : type de non humain, ou **G** : garde |

## Symboles

| Symbole | Signification | Symbole | Signification |
| --- | --- | --- | --- |
| ⊠ | Infanterie | ⚔ (catapulte) | Catapultes |
| ▭ | Cavalerie | ⊞ | Templiers |
| ⧅ (cavalier + flèche) | Archers à cheval | (rat) | Rats |
| ↗ (flèche) | Archers | (crâne) | Squelettes |
| ↑↑↑ | Infanterie (tridents) | (chauve-souris) | Chauve-souris |
| ↑ | Phalange | (loup) | Loups |
| (créature ailée) | Volants | (démon rampant) | Démons protoplasmiques |
| (char léger) | Char léger | ⑂ (trident) | Démons |
| (char lourd encadré) | Char lourd | (groupe de figures) | Population |
| (dragon) | Dragons | (bélier) | Bélier |
| (crâne) | Zombies | ⚓→ | Arbalète |
| (visage de goule) | Ghoules | ⚓⇉ | Arbalète lourde |
| ● | Terre | ▲ | Feu |
| ■ | Air | ⚡ | Eau |
| **PA** | Paralysation | **D** | Déroute |
| **M** | Vorgtd | (blason) | Huluth |
| ● (disque plein) | Azolin (ou Hazolin) | | |

---

## Phases du jeu

### Placement des pièces

Celui-ci varie selon les scénarios (voir scénarios).
Déterminez vous-même le placement pour vos scénarios.

### Phases de jeu

Le déroulement du jeu se subdivise en plusieurs tours, subdivisés eux-mêmes en plusieurs phases
dans l'ordre suivant :

1. Phase de mouvement du 1er joueur
2. Phase de magie du 1er joueur
3. Phase de combat du 1er joueur (résolution des combats)
4. Fin des actions du 1er joueur
5. Phase de mouvement du 2ème joueur
6. Phase de magie du 2ème joueur
7. Phase de combat du 2ème joueur (résolution des combats)
8. Fin des actions du 2ème joueur

S'il y a plus de 2 joueurs, intercalez ceux-ci dans une des deux phases (voir scénario Ave Tenebrae).

### But du jeu

Écraser l'adversaire en anihilant ses troupes ; ou bien remplir les conditions de victoire du
scénario.

---

## Mouvements

Au cours de sa phase active, chaque joueur déplace autant d'unités qu'il désire, dans la limite des
points de mouvements attribués à chaque unité.

Le nombre de points nécessaires pour se déplacer d'une case varie selon la nature du terrain
(représentée par une couleur sur la carte). L'accès aux montagnes nécessite le passage par les cases
collines qui les bordent. En l'absence de cases collines, un massif montagneux est inaccessible.

Les unités accèdent aux villes librement, pour autant que les cases qui les bordent soient
elles-mêmes accessibles.

Si une unité doit emprunter une route au cours d'un mouvement, et si elle ne se trouve pas sur cette
route au début de son déplacement, elle doit d'abord utiliser le nombre de points de mouvements
nécessités par la nature du terrain qui la sépare de la route.

Au cours d'un déplacement, une unité peut traverser une case occupée par une unité de la même armée.

## Zones de contrôle

Chaque unité exerce une influence particulière sur les six cases qui environnent celle qu'elle
occupe : ces six cases constituent sa « zone de contrôle ».

Elle présente des propriétés particulières :

- une unité peut pénétrer dans une zone de contrôle ennemie sans dépense de points supplémentaires,
  mais elle n'a pas le droit de s'y déplacer : elle doit donc s'arrêter dès qu'elle y est entrée ;
- on ne peut passer d'une zone de contrôle à une autre qu'après être sorti de la première ;
- une zone ne s'exerce pas au-delà d'une rivière, mais franchit les ponts ;
- il est interdit de faire retraite (voir combats) dans une zone de contrôle ennemie.

**Exemple :** l'unité **C**, se trouvant dans la zone de contrôle de **A**, ne peut atteindre la case
**X2** en passant par la case **X1**, qui se trouve également dans la zone de contrôle de **A**.
Elle sera obligée de sortir de la zone, de contourner **X1** et de pénétrer de nouveau dans la zone
en **X2**. Elle dépensera donc 4 points de mouvement au lieu de 2.

- Les unités placées dans les forteresses n'ont pas de zone de contrôle.

## Stacking

Il n'est pas possible de placer plus d'une unité dans la même case ; à l'exception des cases de
villes, de villages ou de citadelles qui peuvent elles contenir 3 unités.

Les leaders et les magiciens ne comptent pas comme étant une unité et peuvent donc être stackés sans
problèmes.

Cependant pas plus de 2 leaders ou jeteurs de sorts ne peuvent être stackés avec une unité (sauf
dans le cas d'un château, d'une citadelle ou d'une ville).

---

## Combats

Pour livrer bataille, il faut que l'unité attaquante se trouve à une certaine distance de l'unité
attaquée. Soit : cases contiguës pour l'infanterie et la cavalerie, une ou deux cases d'écart pour
l'archerie. Plusieurs unités d'une même armée peuvent attaquer une seule unité adverse ; chaque
unité attaquante devant remplir les conditions de proximité.

**Tableau I : table des résultats**

| Dé \ Rapport | 1-5 | 1-4 | 1-3 | 1-2 | 1-1 | 2-1 | 3-1 | 4-1 | 5-1 | 6-1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | AR | AR | DR | DR | DR | DR | DR | DE | DE | DE |
| **2** | AE | AR | AR | DR | DR | DR | DR | DR | DE | DE |
| **3** | AE | AE | AR | AR | DR | DR | DR | DR | DE | DE |
| **4** | AE | AE | AR | AR | AR | DR | DR | DR | DR | DE |
| **5** | AE | AE | AE | AR | AR | AR | DR | DR | DR | EX |
| **6** | AE | AE | AE | AR | AR | AR | AR | EX | EX | EX |

- **AE** (attaquant éliminé) : les unités attaquantes sont retirées du jeu.
- **AR** (attaquant recule) : les unités attaquantes reculent d'une case.
- **DE** (défense éliminée) : les unités de défense sont retirées du jeu.
- **DR** (défense recule) : les unités de défense reculent d'une case.
- **EX** (échange) : les unités attaquées sont retirées du jeu, ainsi que les unités attaquantes
  totalisant une force au moins égale.

Le combat étant déclaré, on additionne les points des unités attaquantes, puis les points de la
défense. On fait le rapport des points, lequel s'exprime en plaçant l'attaquant au numérateur et le
défenseur au dénominateur. Ce rapport de force peut aller de 1/5 (soit 1 contre 5) à 6/1 (6 contre
1). Le rapport est toujours arrondi en faveur du défenseur. Par exemple : 10/4 vaut pour 2 contre 1.
L'attaquant jette alors le dé. Le nombre obtenu est modifié, le cas échéant, par la nature du
terrain (voir effets de terrain sur les combats) ou certaines conditions précisées plus avant. Sur
le tableau I, à la croisée de l'une des colonnes (indiquant le rapport de force) et de l'un des
rangs (correspondant au résultat du jet de dé) est mentionné l'issue du combat.

Les combats doivent obéir aux règles suivantes :

- on ne peut attaquer une unité donnée qu'une seule fois au cours de la même phase ;
- une unité donnée (ou un groupe d'unités) ne peut attaquer qu'une seule unité ennemie durant la
  même phase ;
- plusieurs unités de la même armée peuvent s'allier pour attaquer une unité adverse, mais cette
  action ne constitue qu'un seul combat, et ne comporte donc qu'un seul jet de dé ;
- les résultats du combat sont applicables immédiatement, avant le début de la phase suivante.

Une unité tirant des missiles ne peut en aucun cas subir un résultat de retraite ou d'échange ; il
en va de même pour un mage jetant un sort d'attaque à distance.

Une unité en défense dans un château ou une citadelle ne subit pas les résultats de **DR**
(défenseur recule) ; cependant elle peut les subir si elle défend une muraille, auquel cas l'unité
ennemie peut prendre pied sur la muraille dans sa phase d'avance après combat.

### Avance après les combats

Lorsque l'issue d'un combat oblige le défenseur à faire retraite, l'unité attaquante peut, si elle
le désire, occuper la case abandonnée par le défenseur, et ceci sans tenir compte des zones de
contrôle, ni des limites de déplacements qui lui sont propres. La décision d'occuper ou non la case
de l'adversaire doit être annoncée immédiatement après le combat.

### Retraite ou élimination d'une unité

Une unité qui se trouve dans l'impossibilité de reculer (présence d'un lac, une rivière ou une zone
de contrôle ennemie) est retirée du jeu, sauf si elle est entourée d'unités-amies. Auquel cas, elle
pousse une de ces unités et prend sa place. Ce recul simultané d'une ou plusieurs unités doit faire
reculer l'unité en retraite en cherchant le minimum de déplacement et faire reculer le moins
possible d'unités-amies.

Les unités éliminées sont conservées par le joueur qui les a éliminées, pour établir son total de
points en fin de partie.

---

## Facultés spéciales

Sur certains pions figure une petite lettre en haut au milieu de 2 chiffres, sur la première ligne
du pion. Cette lettre représente la faculté spéciale que possède ce monstre : ces facultés spéciales
sont une possibilité propre à l'unité et qui est applicable constamment jusqu'à l'élimination de
cette unité. Les différentes facultés spéciales sont la peur, la paralysie (pour les Ghoules) ou
l'utilisation de la magie. Ces facultés seront toujours traitées comme les sorts de magiciens et
sont appliquées uniquement en cas de combat ou d'une avance de ces unités vers un défenseur.

Il est à noter que certains pions de cavalerie possèdent le symbole de peur ; ceci sert à refléter
le terrible effet que produit la vision d'une charge de cavalerie extra-lourde sur des unités en
défense.

Mais les phalanges, les autres unités de cavalerie lourde et les magiciens ne sont pas affectés par
cette possibilité. Les démons et les morts-vivants sont, quant à eux, immunisés contre ce type de
peur.

### Facultés spéciales (dragons)

Les dragons peuvent, une seule fois par unité, durant tout le cours de la bataille, faire une
attaque à 4 contre 1 quelle que soit la force de l'unité en défense. Tous les résultats sont
applicables.

## Jets de protection

Certaines unités doivent tirer, dans des circonstances particulières, des jets de protection. Ces
jets de protection symbolisent la résistance ou la survie d'une unité à une attaque magique ou à la
peur. Les jets de protection sont différents selon chaque type d'unités. Les jets de protection sont
les suivants :

| Type d'unité | Jet de protection |
| --- | --- |
| Non-humains | 1, 2, 3, 4 réussis |
| Humains | 1, 2, 3, 4, 5 réussis |
| Mages et Elfes | tirer avec 2 dés ; si vous faites un double (2-2, 4-4, 1-1, etc.) le jet de protection est manqué |
| Dragons et créatures conjurées | comme les humains |

Si le jet de protection est manqué, appliquer alors intégralement le résultat du sort ou de la
faculté spéciale.

Les unités paralysées n'ont pas de jets de protection contre les sorts-éradicates, murs de brume et
sont automatiquement détruites par les incendies.

Les unités de Templiers ne sont pas affectées par la paralysie des morts-vivants (Ghoules).

---

# Unités spéciales

## Démons

*(Cinq pions de Princes démons illustrés, gravés de signes cabalistiques.)*

Il y a de cela quelques décennies, Orvarth, pour affermir son pouvoir, passa un pacte avec les sept
princes-démons ; ceux-ci, en échange de nombreux sacrifices et de son âme, firent serment de l'aider
à faire régner sur Terre l'ordre noir.

Afin que cela s'accomplisse, il fût donné à Orvarth des formules d'incantations qui lui permettent
de commander aux démons. Ces incantations se décomposent en deux rituels : le premier libère les
légions démoniaques qui, dirigées par trois démons majeurs, accompliront alors toutes les volontés
du Magiocrate. La deuxième incantation permet de faire jaillir du gouffre de Tsaroth des hordes de
démons protoplasmiques qui, s'ils sont d'une lenteur et d'une stupidité énormes, ont cependant un
pouvoir de destruction extrêmement conséquent. Ces deux rituels doivent être accomplis dans la tour
d'Orvarth. C'est principalement ce pouvoir sur les légions infernales qui rend le mage Orvarth si
craint et si redouté de ses contemporains.

- **Invocations** : Pour invoquer les démons, il faut que le Magiocrate se rende dans sa tour.
  L'invocation des légions coûte 100 points de magie qui ne peuvent être dépensés que par le
  Magiocrate. L'invocation des démons protoplasmiques coûte 50 points de magie qui ne peuvent
  également être dépensés que par Orvarth. Une fois activés, les démons se mettront en marche au gré
  de la volonté du joueur qui les a invoqués.
- **Caractéristiques** : Les légions auront comme points de départ les routes noires, tandis que les
  protoplasmes apparaîtront sur toute la longueur de la faille de Tsaroth.

Mis à part ceux dotés de facultés spéciales (peur), les démons se comportent comme des unités
normales, à ceci près qu'elles n'exercent pas de zones de contrôle, bien qu'elles en subissent les
effets.

Il existe trois démons majeurs qui sont représentés chacun par un pion gravé d'un signe
cabalistique. Ces trois pions sont les seuls à pouvoir exercer une zone de contrôle, car ils
représentent des créatures douées d'une volonté propre. Il doit toujours avoir trois hexagones
libres entre les unités de démons et les autres unités non-humaines des troupes du Mage. Seule
exception : les morts-vivants qui peuvent, étant donné leur nature, fréquenter les démons sur le
champ de bataille sans en être le moins du monde affectés et pour cause. Réciproquement, les
morts-vivants n'affectent pas les démons.

Cependant, le corps des démons doit rester uni et toujours combattre en un seul bloc. Il en va de
même pour les démons protoplasmiques. En cas d'interpénétration d'unités alliées et non-humaines
(troupes régulières du Magiocrate), traitez les effets comme pour les morts-vivants.

- **Règles spéciales** : S'ils désirent briser la conjuration des légions démoniaques, les magiciens
  de l'Empire doivent dépenser le double de points de magie nécessaires pour les invoquer. Il n'est
  pas nécessaire que les magiciens se trouvent en un lieu précis ; cependant, ils doivent être à
  moins de 10 cases des cohortes de morts-vivants.

***

## Dragons

Les forces de l'Empire peuvent, si elles le souhaitent, demander l'aide des dragons qui vivent au
sein de leur royaume. Pour cela, à chaque tour, un des magiciens de l'Empire doit dépenser 20 points
de magie (énergie nécessaire pour appeler les dragons). À partir de ce moment, le joueur qui
représente l'Empire devra tirer un dé à 6 faces. Si un 1 sort, les dragons apparaîtront immédiatement
en bordure de la carte près de la capitale. Ceux-ci possèdent plusieurs facultés spéciales, la peur
et le souffle (voir facultés spéciales).

Les troupes du Magiocrate possèdent également trois dragons ; ils servent de monture aux princes des
morts-vivants. Cependant, ces dragons, moins puissants que les dragons d'or, n'ont aucune
caractéristique spéciale.

***

## Morts-vivants

*(Pions : **W**, Ghoule, Squelette, Zombie.)*

Le pacte infernal qui lie le Magiocrate aux puissances des ténèbres lui donne certains pouvoirs ;
dont celui de commander aux morts de sortir de leur tombe pour accomplir ses volontés. Pour cela, il
doit effectuer un rituel compliqué, au centre du Lac noir sur l'Île du Crâne. Au jour choisi, à la
tombée de la nuit, le Magiocrate se rend sur l'île ; à minuit, il commence le grand rituel et profère
les terrifiantes incantations qui vont ouvrir les « portes de la mort » et libérer des antiques
ruines de la ville de Ghaarth, les cohortes de morts-vivants qui, dès lors, ne pourront plus
qu'obéir aveuglément à sa toute puissante volonté.

- **Invocations** : Pour invoquer les morts-vivants, le Magiocrate doit se rendre au sanctuaire des
  morts, au centre du Lac noir. L'invocation des morts-vivants coûte 80 points de magie qui ne peut
  être dépensé que par le Magiocrate. Une fois activés, les morts-vivants se mettront en marche au
  gré de la volonté du joueur qui les a invoqués, à partir des ruines de la ville de Ghaarth sur
  laquelle ses pions apparaîtront. Mis à part ceux dotés de facultés spéciales (peur et paralysie),
  les morts-vivants se comportent comme des unités normales à ceci près qu'elles n'exercent pas de
  zones de contrôle, bien qu'ils en subissent les effets.

Il existe trois seigneurs des morts-vivants qui sont représentés par un pion marqué d'un **W**. Ces
trois pions sont les seuls qui peuvent exercer une zone de contrôle, car ils représentent des
créatures douées d'une volonté propre. Il doit toujours avoir trois hexagones libres entre les
unités de morts-vivants et les autres unités non-humaines des troupes du Magiocrate (à l'exception
des démons). Si pour une raison quelconque, recul ou omission, ce cas se présentait, la (ou les)
troupe concernée subirait immédiatement une peur intense ; elle serait alors déroutée dans une
direction opposée, au maximum de leur potentiel de déplacement. D'autre part, le corps d'armée des
morts-vivants ne peut jamais être séparé : il doit toujours combattre en un bloc uni.

- **Règles spéciales** : Les morts-vivants ne peuvent combattre que la nuit ; dès que pointe l'aube,
  leurs pions doivent être retournés (faces cachées) à l'endroit précis où ils se trouvaient avant
  le lever du soleil. Le terrain est alors considéré comme normal (si c'est plaine = plaine, si
  c'est forêt = forêt). Lorsque la nuit tombe, les morts-vivants ont la faculté de réapparaître à
  l'endroit précis où ils se trouvaient (retourner, faces visibles) et de se déplacer et de
  combattre normalement.
  Pour briser la conjuration de ces unités, il faut qu'à un moment quelconque de la nuit, les
  magiciens de l'Empire puissent dépenser le double de points de magie nécessaires pour les
  invoquer. Ils n'ont pas besoin d'être en un lieu précis pour le faire ; par contre, ils doivent se
  trouver à moins de 10 cases des cohortes de morts-vivants.
  Pour les facultés spéciales voir le chapitre « facultés spéciales ».

---

# Autres unités

## La cavalerie

*(Pions : cavalerie, archers à cheval.)*

- Elle ne peut en aucun cas attaquer une citadelle ;
- La charge est un cas particulier du déplacement et de la force de combat d'une unité : à chaque
  fois qu'une unité de cavalerie emploie son potentiel de déplacement au maximum (6 cases) en ligne
  droite, et qu'en outre la dernière case où elle aboutit jouxte une unité ennemie, il s'agit d'une
  charge. Celle-ci multiplie par deux le potentiel d'attaque de la cavalerie (4 × 2 = 8).

***

## Phalanges

Les phalanges, grâce à leur formation particulière, voient, lorsqu'elles subissent une charge de
cavalerie, leur potentiel de défense multiplié par trois. Elles sont insensibles à la peur que peut
causer une charge de cavalerie lourde.

***

## Non-humains

Le magicien utilise de nombreuses troupes non-humaines afin d'attaquer les forces de l'Empire.

Les troupes non-humaines, dont les races différentes sont représentées par des pions de couleurs
différentes, ne peuvent en aucun cas être mélangées et doivent combattre par corps (unités de la
même couleur). Si, pour une raison quelconque, ces unités sont mélangées avec d'autres unités
alliées ou si elles sont séparées de plus de 3 cases d'une autre unité de leur groupe, ces unités
devront alors tirer un jet de projection contre la paralysie (identique au sort).

Durant la nuit, ces unités combattent avec un bonus de −1 au dé en attaque.
Cependant, durant le jour, elles ont un malus de +1 au dé en attaque.

***

## Templiers

Les Templiers sont immunisés contre la peur. Dès que ceux-ci apparaissent sur la carte, s'il se
trouve des unités de démons ou de morts-vivants à moins de 5 cases, ces unités vont immédiatement
aller les combattre, car, les Templiers représentant le Bien dans son essence, les démons n'ont plus
qu'un seul but : les détruire. De même, la cible des Templiers sera avant toute chose :

1. les troupes d'Yzent ;
2. les démons et les morts-vivants. Cependant si ceux-ci se font attaquer, ils répliqueront.

Il est à noter que si, à un moment quelconque, les troupes des Templiers perdent la moitié ou plus
de leur force (nombre d'unités) les survivants verront alors leur force multipliée par 2.

***

## Juggernaut

*(Pion : catapulte et bélier.)*

Le Juggernaut est une invention monstrueuse du Seigneur Whismerhill spécialement étudiée pour
détruire les fortifications ennemies. Cette machine est prêtée pour l'occasion au Magiocrate. Son
potentiel de combat est énorme. Elle possède une puissance énorme et un bélier incorporé identique à
celui d'Yzent quant à ses effets. Cette énorme machine qui ressemble à un puissant vaisseau sur roue
apparaît aux yeux de ceux qui la regardent comme un horrible monstre d'une taille titanesque. Cette
machine possède la faculté spéciale d'inspirer la peur.

***

## Bélier

Ce pion sert à détruire la porte ou les murailles. Lorsque, dans une phase de combat, le bélier est
adjacent à la porte ou à la muraille, tirez un dé. Sur un jet de 1, la porte ou la muraille est
détruite. Placez alors un marqueur de destruction.

Les unités en défense n'auront plus le bonus de défense que leur donnait la protection de la
muraille.

Les forces d'Yzent possèdent aussi 3 machines de sièges qui peuvent tirer à distance des blocs de
pierre.

***

## Sahuaguins

Les Sahuaguins sont une race aquatique soumise au Magiocrate et vivent dans le Lac Noir. Ceux-ci
interviennent lorsqu'une unité ennemie arrive à moins de 6 cases du Lac Noir. Il est à noter que les
Sahuaguins sont multipliés par 2 lorsqu'ils combattent ou défendent dans une case en milieu
aquatique.

***

## Yzent

Les forces d'Yzent, ennemies héréditaires du Vicomte de Reissland, n'ont qu'un seul but : anéantir
ses troupes, afin de contrôler son royaume. Bloquées jusqu'ici par l'énorme forteresse qui protège
la frontière, celles-ci ont prévu des machines de sièges pour détruire ce mur.

***

## Magiocrate

*(Pion : 30 / **P** / 20 — **M** — 15 / 10.)*

Le pion qui représente le Magiocrate ne peut jamais être définitivement détruit. S'il était éliminé
du jeu à un moment quelconque, ce pion réapparaîtrait 2 tours plus tard en un endroit de son choix.

---

# Leaders

**Pions de leaders et leurs symboles :**

| Symbole | Leader / groupe |
| --- | --- |
| ☾ / ⧜ / ≋ | Princes démons |
| **W** | Lords morts-vivants |
| **W** (stylisé) | Whismerhill |
| Blason **T** | Lullth |
| Blason (couronne) | Gruntd |
| Blason (soleil) | URM |
| Blason (croix) | PARSIFAL |
| Blason (croix) | WHILLEM |
| Blason (éclair) | RESSLAND |
| Blason (arbre/feuille) | ELENDIL |
| Blason (croissant) | CORDR |
| Blason (croissant) | OVGNORD |
| Blason (croissant) | NURM |
| Blason (chauve-souris) | YZENT |
| Blason (chauve-souris) | RENT |

Un pion de leader représente un chef ou un guerrier de très grande renommée présent avec sa suite
sur le champ de bataille.

L'influence d'un leader n'est pas négligeable ; en ce sens qu'elle permet à l'unité empilée avec lui
de ne pas subir les effets de la peur.

Lorsqu'un pion de leader subit un résultat de recul, tirer un jet de protection (comme un jeteur de
sorts) ; si celui-ci est manqué alors le leader a été capturé par une des unités attaquantes ;
autrement il peut retraiter normalement.

Les pions de jeteurs de sorts peuvent eux en revanche toujours reculer sauf s'ils sont complètement
encerclés auquel cas ils peuvent choisir de se faire prisonniers.

Un pion de leader et de jeteur de sort ne possède pas de zone de contrôle.

## Capture

Un leader ou un magicien peut être capturé dans certains cas. Le joueur capturant peut alors choisir
de tuer, de rançonner son adversaire ou de le garder prisonnier.

Le prix en couronnes d'une rançon est de 10 % plus cher que celui du coût d'achat du leader.

La capture n'est pas importante dans certains scénarios, mais elle peut l'être dans une de vos
campagnes.

---

# Magie

La part de la magie dans « Ave Tenebrae » est prépondérante. Cependant seuls certains pions
représentant des jeteurs de sorts peuvent l'utiliser à l'exception de certaines créatures mythiques
(dragons, démons…), ou certains leaders particuliers.

Chacun de ces pions possède des caractéristiques d'attaques au contact ou à distance et un potentiel
de mouvement, ainsi qu'un symbole servant à l'identifier.

Le potentiel de magie d'une créature représentée par un pion ne figure cependant jamais sur celui-ci
mais sur une feuille de personnage (voir feuille de personnage).

Aucun jeteur de sort ne peut posséder plus de points de magie que son potentiel initial. Ces points
de magie servent à payer l'effort que nécessite la conjuration de certains sorts et rituels.

Chaque sort jeté par un mage ou consort coûte un certain nombre de points de magie variables selon
la puissance du sort ou sa fonction.

Ces points de magie sont retirés du potentiel de magie du conjurateur immédiatement après que le
sort ait été jeté.

Il est fourni un tableau pour vous aider à gérer vos points de magie.

**Important**, notez qu'à chaque tour, chaque conjureur récupère 20 points de magie. Cette
récupération intervient à la fin de chaque tour.

## Transfert

**Important** : Les points des potentiels de magie peuvent être transférés des mages inférieurs aux
mages supérieurs, afin que ceux-ci les utilisent pour leurs conjurations, mais ces points transférés
ne doivent jamais excéder la limite du potentiel de magie du conjureur.

Le transfert d'énergie doit être fait en début de la phase de magie et ce avant qu'aucun sort n'ait
été jeté par le camp concerné. Prenez bien garde à indiquer au joueur adverse quelle est la
direction du transfert, qui en bénéficie, et qui l'effectue.

*Ex. :* Dans le scénario Ave Tenebrae, le transfert peut s'effectuer des mages mineurs vers les 2
mages majeurs : à savoir Orvarth & Thornz.

**Important** : Dans certains scénarios, pour certains rituels, des dépenses de point de magie ne
peuvent être effectuées que par certains mages et cela sans aide (transferts), ce qui veut dire que
le transfert d'énergie ne peut être applicable dans de tels cas. Voir scénarios pour les cas
précités.

À la fin de la phase de magie, les points dûs au transfert non utilisés seront dissipés et non
comptabilisés pour le tour suivant.

Cependant les points propres à chaque conjureur seront eux répertoriés et valables pour le tour
suivant.

## Les Conjurateurs

Il existe trois types de conjurateurs dans Ave Tenebrae (2ᵉ formule) : les Mages, les Clercs et les
Nécromanciens. Chacun de ces types de jeteurs de sort possède une source de magie qui lui est propre
ainsi que des conjurations qui lui sont particulières.

### Mages

Les Mages ou magiciens tirent leur puissance de rituels compliqués et obscurs qui leur permettent de
transformer ou de créer à loisir des choses, des êtres, ou des effets sur le plan matériel en
utilisant l'énergie des vents mystiques.

Dans le monde d'Ave Tenebrae, les magiciens sont puissants et redoutés.

Les magiciens peuvent utiliser tous les rituels précédés par la lettre **M**.

### Clercs

Les Clercs ou Grands Prêtres tirent leur puissance de cérémoniels ardus et de prières initiatiques
qui leur permettent de forger selon leur volonté le souffle divin des dieux qu'ils représentent.

Ils sont souvent redoutés et obéis ; mais ils sont, en général, moins craints que la caste des
mages, car plus prompts à fréquenter leurs fidèles et les vivants.

Les Clercs peuvent utiliser tous les sorts précédés de la lettre **C**.

### Nécromanciens

Les Nécromanciens tirent leur puissance d'incantations inhumaines et innomables qui leur permettent
d'assujettir à leur volonté les forces immondes et noires des plans infernaux, et du plan de la
négation.

Ils sont unanimement craints et redoutés et la seule présence de l'un d'eux suffit à glacer le sang
du plus brave, leur corps se métamorphosant lentement pour ne plus devenir qu'un indescriptible
ensemble d'ombres et de chairs sombres d'où sourd l'étrange lueur de deux yeux rouges sans pupilles.

Ils ne chérissent que les ténèbres et la souffrance dont ils se repaissent.

Les Nécromants peuvent utiliser tous les sorts précédés par la lettre **N**.

---

# Livre des sortilèges

## Magie

Dans cette nouvelle version d'Ave Tenebrae la part de la magie a été augmentée de deux sortes.

Premièrement, ont été ajoutés à la classe des mages, des nécromanciens et des clercs.

Deuxièmement, un grand nombre de nouveaux sorts ont été ajoutés (20 sorts).

Les sorts sont de deux types : les sorts personnels et les sorts de masse.

Les sorts personnels sont réservés aux jeteurs de sorts, tandis que les sorts de masse peuvent être
utilisés pour donner à une unité le bénéfice du sort.

Certains sorts sont réservés, seulement, aux clercs ou aux magiciens ; cependant les nécromanciens
peuvent à loisir utiliser les sorts des clercs et les sorts des mages ; pour plus de précision, voir
paragraphe « jeteurs de sorts ».

Les sorts précédés d'un « **C** » sont réservés aux clercs tandis que les sorts précédés d'un
« **M** » sont réservés aux magiciens.

Cependant, certains de ces sorts, accessibles aux deux classes, seront précédés d'un « **C** » et
d'un « **M** ».

## Sorts et conjurations

Chaque magicien peut, s'il le désire durant sa phase de magie, jeter des sorts.

Les magiciens doivent impérativement être dans un rayon de 10 cases de la cible des sorts pour
pouvoir jeter ceux-ci (sauf spécifications particulières aux sorts).

Durant sa phase de magie, un joueur peut jeter autant de sorts qu'il le souhaite tant que son
potentiel de force le lui permet.

La liste des sorts qu'il peut employer, et leurs effets, sont les suivants.

## Sortilèges et charmes

### Invisibilité — *M, N*

Ce sort permet à la personne ou à l'unité de devenir invisible.

**Important** : Penser à noter, à chaque tour, le mouvement de l'unité sur une feuille de papier,
afin que le joueur adverse puisse vérifier vos mouvements, en cas de contestation ou une fois que
vous serez redevenu visible.

Ce sort ne permet pas de passer sur une case équipée par une case animée, mais il permet de franchir
les zones de contrôle comme si celles-ci n'existaient pas.

**Important** : une unité ou un mage redeviennent visibles dès qu'ils attaquent une autre unité ou
sont engagés dans un autre combat.

**Coût du sort** : 2 points et pour une unité 20 points.

### Protection des missiles — *M, N*

Ce sort permet à une personne ou à une unité de ne pas être affectée par des missiles non magiques
durant un tour.

**Coût du sort** : utilisation personnelle 2 points ; pour une unité 10 points.

### Protection contre la peur — *C, N*

Ce sort permet aux récipiendaires de ne pas être affectés par la peur, qu'elle soit d'origine
magique ou autre.

**Coût du sort** : utilisation personnelle 2 points ; pour une unité 5 points.

### Vision de l'invisible — *M, N*

Ce sort permet aux récipiendaires de distinguer l'invisible dans un rayon de cinq cases autour
d'eux ; annulant donc pour eux uniquement l'effet d'un sort d'invisibilité.

**Coût du sort** : utilisation personnelle 2 points ; pour une unité 5 points.

### Animation des morts — *C, N*

Ce sort permet à son invocateur de ramener à un semblant de vie une unité détruite en la
transformant en une unité de zombie.

Pour être utile, ce sort doit être jeté à l'endroit exact où une unité a été détruite. Après le
sort, remplacer l'unité concernée par une unité de morts vivants (zombie).

**Important** : Il ne peut y avoir plus d'unités de morts vivants présentes sur le champ de bataille
qu'il n'y a de pions du même type dans le jeu. Si toutes les unités zombies sont donc déjà
présentées dans le jeu, le sort sera donc sans effet.

Une unité de zombie ainsi créée sera sous le contrôle de son conjurateur ; cependant elle se
comportera et aura les mêmes facultés qu'une unité de morts vivants normale même à l'égard des
troupes au côté desquelles elle combat.

**Coût du sort** : 20 points de magie.

### Boule de feu — *M, N*

Ce sort permet à son conjurateur de créer dans un hexagone une énorme boule de feu qui attaquera
toute unité présente avec une force de 5 pour chaque tranche de 10 points de magie utilisée dans la
conjuration.

La réussite d'un jet de protection entraîne le décalage d'une colonne vers la gauche dans la
résolution du combat sur la table.

Une protection contre le feu entraîne un décalage de 2 colonnes vers la gauche cumulable avec un jet
de protection.

Ce sort se jette dans un rayon de dix cases.

**Coût du sort** : variable ; voir plus haut.

### Tempête — *C, N*

Ce sort permet à son invocateur de conjurer une immense tempête au-dessus de la zone des combats ;
tempête qui durera aussi longtemps que son invocateur le désirera.

**Effets** : Durant une tempête, tous les mouvements sont réduits de moitié, les tirs de missiles
voient leur efficacité réduite de moitié, et tous les combats sont décalés d'une colonne vers la
gauche (à l'exception de ceux menés par des troupes aquatiques pour qui l'inverse est vrai).

**Important** : les troupes stationnées dans une citadelle ne sont pas affectées par une tempête
hormis pour les tirs de missiles.

**Coût du sort** : 80 points de magie non transférables (voir magie).

### Protection contre les unités conjurées — *C, M, N*

Ce sort permet à son invocateur de créer autour de lui un pentacle puissant qui interdira le passage
ou même la vision de ce qui se tient en son centre à toute unité conjurée (née ou intervenant grâce
à un sortilège).

Notez cependant que ce sort est statique et que tout mouvement de l'unité ou du magiste protégé par
ce sort causera la dissipation de ce sort. Ce sort se jette dans un rayon de 5 cases.

**Coût du sort** : utilisation personnelle 5 points ; utilisation de masse 20 points par unité.

### Cercle de peur — *C, N*

Ce sort permet à son conjurateur de faire bénéficier une unité ou une personne d'une aura de peur
qui fait que toute unité attaquée par elle ou l'attaquant devra jeter un jet de protection afin de
tester son moral ; si celui-ci échoue l'unité ne pourra alors aucunement attaquer et restera sur
place sans rien faire ; ou bien si elle est attaquée, elle devra retraiter immédiatement. Se jette
dans un rayon de 5 cases.

**Coût du sort** : utilisation personnelle 10 points ; utilisation de masse 20 points.

### Souffle de dragon — *M, N*

Ce sort permet à son conjurateur de cracher le feu tel un dragon et d'attaquer un hexagone sur la
colonne 1-1 par 10 points de magie employés ; soit 6-1 si 60 points de magie sont employés.

**Important** : Les effets de ce sort sont décalés de 2 colonnes vers la gauche si l'unité possède
une protection contre le feu et de 3 si elle réussit son jet de protection. Le jeteur de sort doit
cependant être au contact pour utiliser son sort correctement. Les résultats d'échanges comme pour
tous tirs de missiles ne sont pas applicables pour le jeteur de sort.

**Coût du sort** : variable selon puissance, voir plus haut.

### Déparalisation — *C, N*

Ce sort permet à son évocateur de neutraliser les effets d'un sort de paralisation ou de la faculté
spéciale du même nom. Ce sort se jette au contact de l'unité paralysée.

**Coût du sort** : 3 points par point de défense de l'unité.

### Fanatisation ; Berseks — *C, N*

Ce sort permet à son conjurateur de fanatiser une unité si totalement qu'elle sera, pendant le reste
du combat, totalement insensible à la peur et à la perte de moral ; la rendant par le fait même deux
fois plus dangereuse en combat (potentiel d'attaque et de défense × 2 jusqu'à la fin des combats).

Cependant, une unité bersek (à l'exception des unités templières) sera totalement incapable de
retraiter ; en cas de résultat de retraite elle se verra donc retirée du jeu.

**Coût du sort** : 4 points par points d'attaque et de défense de l'unité.

### Négation de la distance — *M, N*

Ce sort permet à son utilisateur de faire se déplacer une unité de deux fois son potentiel de
mouvement. Se jette dans un rayon de 10 cases.

**Coût du sort** : 20 points par unité concernée.

### Bélier phantasmatique — *M, N*

Ce sort permet à son évocateur de conjurer un bélier mystique qui attaquera alors une muraille ou un
mur comme un pion « bélier » à ceci près que le mur sera alors détruit sur un jet de 1 à 2.

**Coût du sort** : 20 points par tour.

### Invocation démoniaque — *M, N, C*

Ce sort permet au thaumaturge d'invoquer une unité de démon, qui sera tirée au hasard parmi les
unités de démons présentés dans le jeu (si elles ne sont pas déjà présentées sur la carte) ; cette
unité obéira alors à son conjurateur durant 7 tours après quoi elle attaquera toujours l'unité la
plus proche d'elle tant qu'elle n'aura pas été dissipée ou anéantie. **Important** : si un pion de
démon majeur a été tiré, ceux-ci à la fin des sept tours attaqueront immédiatement le magicien qui
les a évoqués à moins que celui-ci n'ait un pacte avec eux (tel le magiocrate Orvarth).

L'unité apparaît devant le jeteur de sort et peut immédiatement agir.

**Coût du sort** : 40 points par unité invoquée.

### Invocation des morts vivants — *C, N*

Identique au sort précédent.

**Coût du sort** : 30 points par unité invoquée.

### Ténèbres — *C, N*

Ce sort permet à son évocateur de créer une éclipse de soleil qui durera aussi longtemps qu'il le
souhaitera.

Traiter les effets de ce sort comme étant comparable à la nuit.

**Coût du sort** : 100 points de magie (non transférables).

### Bénédiction divine — *C, N*

Ce sort permet d'annuler pendant un tour les effets de la peur pour toutes les unités d'un camp et
donne un bonus de −1 au dé pour tout combat et jet de protection des armes (les autres sauvent
automatiquement).

**Coût du sort** : 70 points de magie (non transférables).

### Malédiction divine — *C, N*

Ce sort est exactement inverse dans ses effets à part le fait qu'il ne cause pas la peur (notez que
les deux sorts s'annulent).

**Coût du sort** : idem que pour le précédent.

### Protection contre la magie — *M, N*

Ce sort permet à son conjurateur de se protéger contre la magie à l'exception d'un sort de
dissipation réussi. Cette protection s'étend aussi aux unités magiquement évoquées qui ne pourront
alors pas attaquer la personne ainsi protégée.

**Coût du sort** : 40 points.

### Dissipation de la magie — *C, M, N*

Ce sort permet de dissiper l'effet d'un sortilège quelconque ; il doit se jeter dans un rayon de dix
cases. Ce sort coûte un tiers de points de magie de plus que le coût du sort qu'il entend annuler.
Cependant, il convient de jeter un dé à six faces afin de voir si ce sort réussit bien son but. Si
un 1 apparaît sur le dé, le sort n'a pas réussi à dissiper la magie.

**Coût du sort** : 1/3 de plus que le coût du sort que l'invocateur tente de dissiper.

### Vol — *M, N*

Certaines unités, représentant des forces ailées, sont présentes dans le jeu. Ces unités ne sont
donc pas soumises durant leur vol aux restrictions des terrains sur le mouvement.

La seule exception est le survol du volcan de Toth (pour le franchir, tirer un jet de protection
contre la paralysie). Si ce jet de protection échoue, l'unité est détruite par sa chute dans le
volcan.

Les combats en vol ne sont pas possibles. Lorsqu'elles subissent un sort de vent, les créatures
ailées doivent jeter un jet de protection ou être retirées du jeu pour cause de mort due à une
mauvaise chute. Si elles réussissent, elles resteront sur place et pourront franchir la barrière
durant ce tour.

Les magiciens, grâce à ce sort, peuvent se déplacer dans les airs ; le coût est de 1 point de magie
par point de mouvement et ceci jusqu'à concurrence du potentiel de déplacement du magicien.

### Erradicate — *C, M, N*

Ce sort permet de désintégrer une unité ou un magicien, si ceux-ci manquent leurs jets de protection.

**Coût du sort** : 4 points de magie par 1 point du potentiel de défense de l'unité visée.

### Mur de flamme — *M, N*

Ce sort permet de créer une muraille de flammes dans un rayon de 5 cases autour de celui qui le
crée, ceci dans un terrain de type combustible (bois et plaines). Si ce mur est créé dans un bois,
tirer un dé ; si le résultat est 1, 2, 3 ou 4, les hexagones, immédiatement au contact, prennent
feu. Dans la plaine, le feu se transmet si l'on fait 1 aux dés.

Une fois créé, l'hexagone de feu initial dure 3 tours en plaine, et ne s'arrête dans les bois que si
le feu meurt (non transmission par contact, tirer à chaque tour) ou qu'il n'y a plus rien à dévorer.

**Coût** : 15 points par hexagone enflammé.

Les unités, qui auraient à subir ou à traverser un mur de flammes, sont considérées comme étant
attaquées à 2 contre 1 sur la table de combat ; les résultats sont applicables dans leur intégralité.

En outre, si, pour une raison quelconque, la forêt Elfique est attaquée de cette manière, un
magicien Elfe apparaîtra, magicien qui dispose d'un potentiel de magie de 50 points. Ce magicien
restant uniquement dans la forêt, n'est pas représenté par un pion, car il est pratiquement
irrepérable et inattaquable. Il pourra donc, au moment de la phase de magie, jeter ses sorts d'un
point quelconque d'une case de la forêt Elfique et ceci jusqu'à la portée limite même si c'est à
l'extérieur de la forêt. Ce mage ne peut cependant pas jeter de sorts à partir d'une case de forêt
en feu.

### Vent — *M, N*

Le magicien qui jette ce sort crée une explosion soudaine de vent qui couvre une ligne de 5
hexagones, ligne qui peut pousser un mur de brouillard de 2 cases, éteindre un incendie (1, 2, 3, 4,
5 par case enflammée égal d'incendie éteint) ou empêcher, dans le tour immédiat qui précède le
lancement de ce sort, un tir de missiles (flèches uniquement) sur la surface protégée par la ligne.
Deux murs de vent, jetés dans le même tour, s'annulent.

**Coût** : 40 points de magie pour une ligne de cinq hexagones.

### Peur — *C, N*

Ce sort permet de faire dérouter les unités qui manqueraient leurs jets de protection, de la
totalité de leurs points de mouvement, et ceci durant un tour.

**Coût** : 1 point par point de défense de ou des unités visées.

### Conjuration — *C, M, N*

Il est fourni avec le jeu une série de pions qui représentent des élémentaires d'air, d'eau, de feu
et de terre ainsi que des pions qui représentent des créatures diverses tels que rats, chauve-souris
ou loups. Ces pions représentent des créatures qui peuvent être conjurées d'une manière magique afin
de les faire combattre selon le souhait de celui qui les a invoquées.

Le coût d'une conjuration est de 2 points pour chaque point de force de cette unité. Les créatures
apparaissent alors à l'endroit où se trouve le magicien et pourront alors servir immédiatement. Ces
créatures restent présentes durant 3 tours puis disparaissent. Pour conjurer des élémentaires d'eau
et de feu, l'on doit se rendre soit près d'un lac ou d'une rivière pour ceux de l'eau, soit au
volcan de Toth, pour les élémentaires de feu.

Des pions sont fournis pour marquer le début d'une invocation.

### Paralysie — *C, N*

Ce sort permet de paralyser les unités qui manqueraient leurs jets de protection. Ces unités ne
pourront alors ni bouger ni se défendre durant un tour. Les attaques dirigées contre elles seront
automatiquement victorieuses et l'unité est alors éliminée.

**Coût** : 2 points par point de défense de l'unité.

### Mur de brume — *M, N*

Ce sort permet de créer un mur de brume dans un rayon de cinq cases autour du mage qui le crée.
Toute unité qui tenterait de traverser ce mur devra tirer un jet de protection. Si celui-ci est
réussi, elle pourra alors le traverser, sinon elle sera détruite et dissoute par les gaz.

**Coût** : 10 points de magie par case de brouillard.

### Dissipation d'une invocation — *C, M, N*

Il est possible de dissiper des pions conjurés à condition de dépenser 2 fois plus de puissance que
ces pions n'en ont coûté pour être invoqués.

**Important** : La protection d'un sort dure généralement un tour ; sauf spécification, ce tour
s'entend pour la magie d'une phase de magie d'un tour à celle de l'autre tour pour le même joueur
(soyez donc prévoyants quant à vos défenses et notez sur un papier vos protections et vos dépenses
en point de magie).

---

# Points d'achat

## Détermination de la valeur d'une unité

Afin de vous permettre de créer vos propres scénarios ou de faire des batailles avec les troupes de
votre choix, il vous est donné, plus bas, une règle vous permettant de chiffrer le coût d'une unité,
ce qui vous permettra de faire des batailles de 1 000, 2 000 ou 3 000 couronnes.

Un point d'achat est appelé dans le jeu une couronne et correspond, approximativement, à une pièce
d'or.

Certaines unités ont un coût de revient oscillant entre 8 et 20 couronnes ; ce sont des unités
standard représentatives d'une unité humaine ou typique sans grand entraînement ni puissance
particulière.

### Achat d'une unité

Le coût d'une unité est déterminé comme suit :

Le coût de base est de deux couronnes par point d'attaque et de défense de la pièce. À ceci
s'ajoutera :

| Modificateur | Coût |
| --- | --- |
| Base | 2 couronnes par point d'attaque et de défense de la pièce |
| Unité montée sur un animal normal (cheval, etc.) | + 1 couronne par point d'attaque et de défense |
| Unité pouvant tirer des missiles (archers) | + 1 couronne par point d'attaque et de défense |
| Facultés spéciales | + 5 couronnes par faculté |
| Mouvements spéciaux | + 5 couronnes par mouvement spécial |
| Unité de démons ou de morts vivants | + 10 couronnes |
| Pion représentant un dragon | + 20 couronnes |

Le coût d'achat d'un mage ou d'un leader sera discuté sous ces rubriques respectives.

***

**Exemple :** achat d'une unité humaine standard, potentiel de défense et d'attaque 4 × 2 = 8
couronnes ; + aucune faculté = 0. **Valeur totale de l'unité = 8 couronnes.**

***

**Autre exemple :** unité humaine de cavalerie standard :

- Potentiel d'attaque et de défense 5 × 2 = 10 couronnes
- L'unité est montée, ce qui fait 5 × 1 = 5 couronnes
- L'unité peut charger + 5

**Coût total de l'unité = 20 couronnes.**

***

**Dernier exemple :** coût de la plus lourde unité de cavalerie templière :

- Potentiel d'attaque et de défense : 30 × 2 = 60 couronnes
- L'unité est montée 30 × 1 = 30 couronnes
- L'unité peut tirer des flèches 30 × 1 = 30 couronnes
- L'unité possède la faculté spéciale de charge : + 5 = 5 couronnes
- L'unité possède la faculté spéciale de résistance à la peur : + 5 = 5 couronnes
- L'unité peut devenir bersek + 5 = 5 couronnes

**Le coût total de l'unité sera donc de 140 couronnes.**

***

Comme vous pouvez le voir, il existe une différence énorme entre les deux unités de cavalerie,
différence qui s'explique par les nombreuses facultés et la puissance de l'unité des templiers, ce
qui reflète parfaitement le coût des armures et l'entraînement d'une unité de chevalerie lourde ou
extra lourde.

Cette méthode de calcul du coût d'une unité peut sembler compliquée a priori, mais elle permet de
construire facilement une armée d'après un nombre fixe de couronnes et permet d'être sûr que votre
adversaire aura autant de chances que vous de gagner une bataille ; l'ensemble des forces étant
alors relativement égal.

**Important** : Notez que toute unité conjurée durant le cours du jeu par un magicien ne coûte rien
en couronnes mais se paye avec des points de magie. Remarquez que cette faculté ainsi que celle qui
permet de jeter des sorts est comprise dans le coût d'achat d'un leader ou d'un jeteur de sorts.

***

## Coût d'un jeteur de sort

Le coût d'achat de base d'un jeteur de sort est de :

| Classe | Coût de base |
| --- | --- |
| Mage | 10 couronnes |
| Clerc | 10 couronnes |
| Nécromancien | 20 couronnes |

À ceci viennent s'ajouter :

| Caractéristique | Coût | Maximum |
| --- | --- | --- |
| Point d'attaque ou de défense | 5 couronnes | potentiel de défense max. 20 |
| Point de mouvement | 5 couronnes | 15 |
| Point d'attaque à distance | 5 couronnes | 10 |
| Point de portée | 5 couronnes | 10 |
| Faculté spéciale d'un jeteur de sort | 50 couronnes en supplément | — |
| Potentiel magique | 200 couronnes par tranche de 20 points de potentiel | 80 points de magie |

Une fois que vous avez créé votre jeteur de sort, faites un pion à son image et notez ses
caractéristiques et ses points de magie sur un papier.

Vous remarquerez qu'un jeteur de sort coûte très cher, c'est pourquoi nous vous conseillons les
maxima ci-dessus.

Cependant rien ne vous empêche de faire des scénarios à plusieurs milliers de couronnes où chaque
camp pourra posséder de nombreux mages.

Mais n'oubliez pas que les batailles d'armées sont quand même le but principal de ce jeu.

***

## Coût des ouvrages de défense

Certains symboles existent sur la carte d'Ave Tenebrae, les autres (fossés, fossé piégé, mur) sont
donnés à titre indicatif pour la création de vos propres scénarios ou campagnes grâce aux cartes
vierges.

| Ouvrage | Coût par hexagone | Effet |
| --- | --- | --- |
| Fossés | 10 couronnes | L'unité le franchissant perd un tour. |
| Fossés piégés | 40 couronnes | L'unité le franchissant doit stopper et subir une attaque à 2 contre 1. Elle peut passer si elle réussit. |
| Murs | 50 couronnes | Défenseur × 2. |
| Murailles | 100 couronnes | Défenseur × 3. |
| Forts | 1000 couronnes | Défense × 3 et pas de résultats **DR** applicables. |

---

# Points litigieux

Lorsqu'un point de litige intervient au sujet de l'interprétation d'une ou de plusieurs règles,
mettez-vous d'accord à l'amiable ou bien accordez-vous sur le point litigieux avant de jouer.

N'hésitez pas à modifier ou ajouter une règle, Ave Tenebrae est un jeu et n'a qu'un but, votre
divertissement.

---

# Scénarios

## Scénario n° 1 — La bataille (de l'aube des ténèbres)

Cette bataille (voir chronique) est la bataille la plus importante qui ait secoué l'empire durant
toute son histoire.

**Déroulement** : Dans un premier temps, les forces de l'Empire placent leurs pions sur la carte, à
savoir un pion de population sur chaque case de ville ou village ainsi que 3 pions d'armées dans
chaque citadelle. Le joueur de l'Empire placera alors les restants de sa troupe de garnison à son
gré à l'intérieur de ses frontières.

Les troupes humaines du Magiocrate entrent en jeu par le seuil des brumes.

Répartition des pions des magiciens et des potentiels de magie.

**Important** : le Magiocrate est considéré comme étant un nécromancien.

**Elfes** : Les Elfes apparaissent si une unité du Magiocrate arrive à 10 cases d'un hexagone de la
forêt Elfique. À ce moment, l'intégralité des pions Elfique apparaîtra en un endroit quelconque de
la forêt au gré du joueur.

**Vicomté de Reissland** : Le joueur du Vicomté placera ses troupes où il le souhaitera à l'intérieur
de son royaume mais celui-ci doit se souvenir que son principal objectif est d'empêcher le passage
des forces d'Yzent.

**La force noire** : Les troupes du Magiocrate sont mises en place dans le jeu comme suit : les
troupes Orques sont initialement placées dans l'enceinte de Orcreich. Les autres troupes
non-humaines entrent en jeu par le Seuil des Brumes.

**Troupes d'Yzent** : Les troupes d'Yzent arrivent par le côté Nord-Ouest de la carte et doivent se
frayer un passage au travers des fortifications des Marches afin de tenter de détruire leur ennemi
héréditaire (le Reissland).

**Démons et morts-vivants** : Ceux-ci entrent en jeu à partir du moment où ils sont invoqués. Les
démons entrent par la route noire tandis que les morts-vivants surgissent des ruines de la ville de
Ghaarth.

**Les Sahuaguins** : Ceux-ci entrent en jeu dès qu'une unité de l'alliance arrive à moins de 6 cases
du Lac Noir. Ils combattront alors sous les ordres du Magiocrate.

**Renforts des ténèbres** : Ceux-ci entrent en jeu si la moitié des forces régulières (non
conjurées) a été anéantie ou bien si une unité ennemie arrive à moins de 5 cases de Orcreich.

**Renforts de l'alliance** : Ceux-ci arrivent dès qu'une citadelle est prise ou dès qu'a
proximativement 1/4 du territoire de l'Empire est sous le contrôle des forces des ténèbres.

Les renforts de l'Empire arrivent alors au début de la phase de mouvement du tour suivant. Avec ces
forces, apparaissent aussi les magiciens de l'Empire.

Si les troupes de l'Empire ne peuvent pénétrer par les endroits cités plus haut, faites-les alors
rentrer par un point quelconque de la carte situé en bordure de celle-ci.

**Les Templiers** : Les Templiers apparaissent à partir du 12ᵉ tour ou bien le tour suivant
l'anéantissement des forces du Reissland.

Les renforts de l'Empire rentrent par la route du Val de Froy ou, si cette zone est sous contrôle
ennemi, par la plaine qui est située derrière la capitale. Les Templiers rentrent en jeu par un
point quelconque du bord du royaume de Reissland.

**Magie** : Chacun de ces pions possède une certaine valeur en potentiel de puissance ; le plus
puissant représente le mage Orvarth. La répartition des différents potentiels est la suivante :

| Camp | Personnage | Potentiel de magie |
| --- | --- | --- |
| Forces noires | Orvarth | 100 points de magie |
| Forces noires | 5 pions (magiciens) | 20 points de magie |
| Alliance | Thornz | 80 points de magie |
| Alliance | 4 pions (magiciens) | 20 points de magie |

La bataille de l'aube des ténèbres se joue en 32 tours ou moins. L'alliance gagne si elle réussit à
repousser les invasions et à garder sa capitale. Les Forces des Ténèbres gagnent en anéantissant les
troupes ennemies ou en contrôlant puis détruisant la capitale.

---

## Chronique des terres de Dreamrift

En l'an 7977 de l'âge d'or, se leva l'aube noire. De partout sur le monde, surgirent des hordes
ténébreuses qui noyèrent dans un déluge de feu, de fer et de sang, les antiques civilisations qui
régnaient depuis huit mille ans. Sur l'Empire de Lynn, fondit le Seigneur du mal et des ténèbres,
Whismerhill, qui, après une terrifiante bataille, renversa et tua l'Empereur, tandis que Lynn la
capitale était réduite en cendres. Aidé en cela par le terrible Hazolhim, mage puissant et
redoutable, fils d'Asmodée ; après que les tables de la loi eurent été brisées par le nouvel
Empereur, il ouvrit un seuil qui permit de communiquer avec les puissances infernales. Cette date
sanctifiée est considérée par tous les historiographes comme étant le début de l'ère des ténèbres.

Après cette victoire, de tous côtés, dans tous les royaumes, des révoltes apparurent, et de noirs
serviteurs du Malin jetèrent leurs armées contre les forces du Bien. La guerre d'Orvarth est l'un de
ces nombreux combats qui ravagèrent le monde, afin que l'aube nouvelle s'instaure ; et, en moins de
10 ans, la noire marée avait totalement submergé les bastions de la loi et de l'ordre : les temples
étaient en ruine, les villes dévastées, et là où ne régnait pas la poigne de fer des ténèbres, était
un monde désemparé en proie à la barbarie. Vint le moment où il ne resta plus que deux contrées dont
le flambeau faisait échec à la noirceur : le Royaume de Sisigye et la puissante d'entre les
puissantes, l'Empire Tharque.

C'est la terrible bataille qui anéantit cet Empire, que je vais vous conter.

À l'aube, les puissantes armées du Magiocrate attaquèrent ; elles surgissaient de la brume, comme
sorties du néant ; lorsque les généraux de l'Empire les virent, il était trop tard. Ils furent pris
par surprise, et leurs renforts tardèrent à arriver (il était dès lors trop tard). Déjà Orvarth le
ténébreux avait invoqué les légions des morts et les cohortes infernales.

Lorsque l'Empire tenta de faire front avec la faible garnison qui était sur place, ils se firent
balayer ; les renforts, arrivés juste à temps, se firent massacrer jusqu'au dernier, malgré
l'alliance des Elfes. Tout à côté, les forces d'Yzent fondaient, tels des rapaces, sur les armées du
Vicomte de Reissland, qui, massées sur la muraille des marches d'Yzent, tentèrent, en vain,
d'endiguer la ruée de ceux-ci. Et lorsqu'enfin les templiers de Sisigye, sous la direction de leur
commandeur, arrivèrent avec leurs puissantes cavaleries, il était vraiment trop tard ; malgré un
combat acharné, ils ne purent renverser la situation et durent pitoyablement retourner vaincus en
leur royaume. Il fut souvent dit que, si les généraux de l'Empire avaient attendu les renforts avant
de lancer leurs troupes dans la bataille, l'issue du combat aurait été changé. Mais ce ne sont pas
avec de telles hypothèses que l'Histoire s'écrit, et ainsi donc, le grand Orvarth, fort de cette
première victoire, put déferler impunément sur l'Empire dont les deux autres provinces tombèrent
sans trop de difficulté.

Deux ans après, les forces du Magiocrate firent jonction devant Tharkis avec les forces de
l'alliance de Braise dirigées par les redoutés Whismerhill et Wuthering Height. Ce fut le début d'un
long siège, qui dura un an, au bout duquel la fière capitale fut anéantie. En ce jour glorieux,
l'alliance de Braise avait remporté sa plus grande victoire, et tel un noir linceul, les forces du
mal s'étaient répandues sur le Monde.

> *(Marlfriss le sage, chroniqueur du Magiocrate, en l'an Grale 8000 de l'avènement des Ténèbres.)*

### Phases du jeu (scénario n° 1)

Le déroulement du jeu se décompose en plusieurs tours subdivisés eux-mêmes en plusieurs phases ; qui
sont dans l'ordre :

1. Phase de mouvement du joueur des Forces noires ;
2. Phase de mouvement du joueur d'Yzent ;
3. Phase de magie du joueur des Forces noires ;
4. Phase de combat du joueur des Forces noires ;
5. Phase de combat du joueur d'Yzent ;
   — fin des actions du ou des joueurs des Forces noires ;
6. Phase de mouvement du joueur de l'Empire ;
7. Phase de mouvement du joueur du vicomte de Reissland ;
8. Phase de magie du joueur de l'Empire ;
9. Phase de combat du joueur de l'Empire ;
10. Phase de combat du joueur de Reissland ;
    — fin des actions du ou des joueurs des forces de l'Alliance.

### But du jeu

Il s'agit pour les Forces noires de contrôler la capitale de la troisième province et les forts
situés sur la frontière des terres mortes, ainsi que le Krak de Reiss.

Pour les forces de l'alliance, leur but est de contrôler la capitale de la province et la plus
grande surface de territoire possible, ou bien d'anéantir les hordes du Magiocrate.

Sera déclaré vainqueur le joueur qui remplira ces conditions de victoire, à la fin du nombre de
tours alloué par le jeu.

Attention, il existe, pour les différents scénarios, des conditions de victoires qui diffèrent selon
les cas.

---

## Scénario n° 2 — La révolte des esclaves

Alors que le Magiocrate est absent de son royaume et que ses troupes humaines occupent les
citadelles et châteaux des terrains nouvellement conquis : les troupes non humaines lancent un
assaut surprise et tentent d'éliminer toutes les troupes humaines afin de mieux piller les villes.

Le joueur n° 1 contrôle les armées humaines du Magiocrate (rouge sur fond noir) qui se placent dans
les villes et fortifications de la carte (Morgenstern, portes des brumes, et autres citadelles).

Le joueur n° 1 contrôlera aussi 3 magiciens mineurs du Magiocrate.

Le Magiocrate reviendra dans son royaume à partir du 10ᵉ tour avec son potentiel de magie au plus
fort et ses pouvoirs habituels.

Le joueur n° 2 contrôlera toutes les unités non humaines du Magiocrate ainsi que ses renforts ;
ceux-ci se masseront au nord de la faille de Tsaroth ; tandis que les orcs feront irruption de
l'Orcreich.

Le joueur n° 2 contrôlera 2 mages mineurs du Magiocrate.

Le joueur n° 1 gagnera s'il réussit à contrôler Morgenstern, la tour d'Orvarth, et trois citadelles
à la fin du tour 16.

Le joueur n° 2 gagnera s'il réussit à empêcher le joueur n° 1 de réussir ses objectifs ; ou s'il
élimine plus de 80 % des troupes humaines du Magiocrate.

Les elfes resteront d'une neutralité sans bornes dans ce conflit.

---

## Scénario n° 3 — Pour qui sonne le glas

Rompant l'alliance de braise, le Magiocrate brise son serment d'allégeance à l'empire de Lynn.

3 mois après celui-ci voit avec horreur s'avancer vers son territoire les troupes d'élite de l'armée
impériale de l'empereur Wismerhill, flanquées par les troupes démoniaques et mort vivantes qu'il a
l'habitude de contrôler avec, bien entendu, le Juggernaut.

Le Magiocrate réunissant alors toutes ses troupes tenta alors de se faire front tandis que ses
citadelles résistaient pied à pied.

**Joueur n° 1** : Celui-ci contrôlera toutes les troupes de l'empire de Lynn ; plus les troupes
démoniaques et mort vivantes (n'étant pas summonées, elles ne peuvent être dispellées), elles
pénètreront sur la carte par le Val de Froy.

L'empereur Wismerhill possède 100 points de magie cléricale.

Tandis que le demi-dieu Azolhim possède 120 points de potentiel (Azolhim est un mage).

Le joueur n° 1 contrôlera aussi 4 mages mineurs.

**Joueur n° 2** : Celui-ci contrôlera le Magiocrate et toutes ses troupes humaines et non humaines
ainsi que les troupes d'Yzent, et ses renforts.

Si par accident, les pions de l'empereur et d'Azolhim venaient à être éliminés, ils réapparaîtraient
2 tours plus tard à un endroit quelconque de la carte.

Le vainqueur sera celui qui exterminera l'autre ; à la différence près que même si les troupes
impériales étaient éliminées rien n'empêcherait l'empereur de revenir une autre fois ; mais pas
avant 10 ou 20 ans ce qui laisserait donc au Magiocrate une relative tranquillité.

Se joue avec un nombre de tours indéterminé.

---

## Scénario n° 4 — La guerre des nains

1 000 ans avant l'aube noire, un violent conflit opposa les nations naines et orques.

Afin de répondre aux raids incessants des orcs, le chef nain Grundt ordonna à son armée l'attaque
immédiate de l'Orcreich et l'extermination totale des orcs.

**Joueur n° 1** : Le joueur n° 1 contrôlera l'armée naine et le leader Grundt ainsi que le mage
Vorgtd (potentiel de magie : 45).

L'armée naine se masse au sud du volcan de Toth.

**Joueur n° 2** : Le joueur n° 2 contrôlera toutes les pièces orques qu'il place à l'intérieur de
l'Orcreich. Le joueur orque possède un nécromant mineur (20 points de magie).

Le vainqueur est celui qui exterminera l'autre.

---

## Scénario n° 5

En l'an 50 avant l'aube des ténèbres, la ville de Morgenstern fut attaquée par une race étrange
appelée « les volants » dont tous les membres possédaient des ailes.

La ville fut totalement dévastée avant que les renforts n'arrivent.

**Joueur n° 1** : Placer sur la carte comme pour le scénario de l'aube des ténèbres les pions de
garnison de l'empire. Ainsi que 3 mages mineurs.

**Joueur n° 2** : L'armée des volants entre en jeu par un point quelconque de la carte. Elle possède
le leader Lullth, et le mage Huluth (40 points de magie).

**But du joueur n° 1** : Empêcher la destruction des villes et des kraks ainsi que la mise à sac de
Morgenstern.

**But du joueur n° 2** : Détruire et enflammer le plus de territoire possible avant le 10ᵉ tour,
moment où les renforts de l'empire arrivent avec Thornz et 5 dragons.

Comme vous pouvez le voir, il est facile d'élaborer de multiples scénarios ; aussi nous vous
laissons le champ libre. Utilisez les points d'achat en couronnes pour construire vos armées ;
résolvez les batailles imaginaires de vos jeux de rôles préférés, le champ de bataille est vôtre.

---

# Feuille de personnage

- **Nom :**
- **Pays :**
- **Identification :** (case pour dessiner le pion)
- **Force att. / déf. :**
- **Mouvement :**
- **Force (missiles) :**
- **Portée des missiles :**
- **Mouvement en vol :**
- **Facultés spéciales :**
- **Potentiel de magie :**

**Piste de potentiel de magie**

| | | | | | | | | | |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 120 | 130 | 140 | 150 | 160 | 170 | 180 | 190 | 200 | |
| 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 | 100 | 110 |
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |

**Statuts du personnage** : paralis. / déroute / mort

**Coût du personnage (en couronnes) :**

---

# Tableau des terrains

| Terrain | Mouvement | Combat |
| --- | --- | --- |
| **BOIS** | 2 points sauf Elfes | Elfes : × 2 en défense ; + 2 au dé de l'attaquant |
| **COLLINES** | 2 points sauf élémentaire Terre | + 2 au dé de l'attaquant |
| **MONTAGNE** | Infranchissable sauf passage par colline, route ou air ; idem élémentaire de terre | Défense × 3 |
| **RIVIÈRES** | Infranchissables sauf passage par ponts, air ou créatures aquatiques | Défense × 2 |
| **CHEMINS** | × 2 | — |
| **ROUTES** | × 3 | — |
| **FAILLE** | Infranchissable sauf par air | — |
| **LACS** | Infranchissables sauf par eau et air | Défense × 2 |
| **MURAILLES** | Infranchissables sauf par combats ou alliés | Défense × 3 |
| **RUINES** | × 2 | Défense × 2 |
| **VILLAGES** | Normal | Défense × 2 |
| **FORTS** | Infranchissables sauf par combats ou alliés | Défense × 3 |

---

*Éditeur : **Jeux Descartes**, 5 rue de la Baume, 75008 Paris — Tél. : 45.62.35.27.
Maquette Atelier 00 — Imp. Métais s.a., 95110 Sannois.*
