# Pions d'Ave Tenebrae — classement par faction et par utilité

Ce répertoire rassemble les **127 photos de pions** de la 2ᵉ édition d'Ave Tenebrae (1986),
extraites du répertoire `base_material/images/` et classées d'après le découpage détaillé dans
`base_material/vintageboard-1-ave-tenebrae.html` (article « Vintageboard 1 : Ave Tenebrae »,
R-One Chaff).

Les fichiers d'origine sont **conservés intacts** dans `base_material/images/` ; ce répertoire
n'en contient que des copies renommées. `base_material/` n'est pas versionné : la colonne
« Photo d'origine » des tables ci-dessous ne se vérifie qu'avec les sources en local.

## Sommaire

| Répertoire | Faction / utilité | Pions |
| --- | --- | --- |
| `01-yzent/` | Yzent | 12 |
| `02-reissland/` | Vicomté de Reissland | 4 |
| `03-empire/` | Empire Tharque | 10 |
| `04-templiers/` | Templiers | 7 |
| `05-population/` | Population | 1 |
| `06-empire-de-lynn/` | Empire de Lynn | 12 |
| `07-chaos/` | Chaos | 6 |
| `08-non-humains/` | Non-humains | 11 |
| `09-elfes/` | Elfes | 6 |
| `10-nains/` | Nains | 6 |
| `11-orques/` | Orques | 8 |
| `12-sahuaguins/` | Sahuaguins | 4 |
| `13-dragons/` | Dragons | 1 |
| `14-morts-vivants/` | Morts-vivants | 6 |
| `15-demons/` | Démons | 8 |
| `16-volants/` | Volants | 5 |
| `17-conjurations/` | Conjurations diverses | 7 |
| `18-machines-de-siege/` | Machines de siège | 1 |
| `19-magiciens/` | Magiciens et clercs | 2 |
| `20-marqueurs/` | Marqueurs et éléments de jeu | 6 |
| `21-vues-d-ensemble/` | Vues d'ensemble | 4 |

### Camps

- **Forces de l'Alliance / du Bien** : Empire Tharque, Vicomté de Reissland, Templiers, Elfes,
  Population, Dragons, Empire de Lynn (scénario 3), Nains (scénario 4).
- **Forces des Ténèbres / du Magiocrate** : Chaos, Non-humains, Orques, Sahuaguins, Yzent
  (allié d'opportunité), Morts-vivants, Démons, Juggernaut.
- **Neutre / hors camp** : Volants (scénario 5), conjurations, marqueurs.

## Valeurs lues sur les pions — `pions.json`

`pions.json` reprend, pour chacune des 127 photos de ce répertoire, les valeurs **lues à l'œil sur
la photo**. La clé est le nom de l'image sans répertoire ni extension ; le dictionnaire porte le
chemin de l'image depuis la racine du dépôt.

| Champ | Contenu | Position sur le pion |
| --- | --- | --- |
| `image` | chemin de la photo depuis la racine du dépôt | — |
| `faction` | répertoire de classement (`01-yzent`, …) | — |
| `force` | force d'attaque et de défense | haut, à gauche |
| `mouvement` | points de mouvement | haut, à droite |
| `tir` | force de combat par tir de missile | bas, à gauche |
| `portee` | portée des missiles | bas, à droite |
| `mouvement_vol` | mouvement en vol (chiffre entre parenthèses) | bas, au centre |
| `facultes_speciales` | lettre de faculté spéciale (`P`, `s`, `PA`, `D`…) | haut, au centre |
| `symbole` | type d'unité identifié d'après la table des symboles | centre |
| `remarques` | lettres de non-humains, noms de leaders, doutes de lecture | — |

Un champ absent du pion vaut `null`. 114 des 127 entrées portent une valeur de mouvement ; les 13
autres sont les marqueurs, les deux feuilles de suivi, les quatre vues d'ensemble et les
chauves-souris (qui n'ont qu'un mouvement en vol).

Le fichier est **écrit à la main d'après les photos**, pas généré : le corriger revient à
rouvrir la photo concernée.

## Yzent

`01-yzent/` — Ennemi héréditaire du Vicomté de Reissland. Arrive par le nord-ouest de la carte (scénarios 1 et 3).

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `yzent-01-9-infanteries-de-puissance-4.jpg` | 9 infanteries de puissance 4 | `20170714_154512.jpg` |
| `yzent-02-6-infanteries-de-puissance-6.jpg` | 6 infanteries de puissance 6 | `20170714_154739.jpg` |
| `yzent-03-8-archers.jpg` | 8 archers | `20170714_154526.jpg` |
| `yzent-04-3-catapultes.jpg` | 3 catapultes | `20170714_154702.jpg` |
| `yzent-05-1-belier.jpg` | 1 belier | `20170714_154648.jpg` |
| `yzent-06-5-phalanges-de-puissance-5-renforts.jpg` | 5 phalanges de puissance 5 (renforts ?) | `20170714_154631.jpg` |
| `yzent-07-5-phalanges-de-puissance-8-renforts.jpg` | 5 phalanges de puissance 8 (renforts ?) | `20170714_154616.jpg` |
| `yzent-08-7-cavaleries-de-puissance-5-renforts.jpg` | 7 cavaleries de puissance 5 (renforts ?) | `20170714_154720.jpg` |
| `yzent-09-6-cavaleries-de-puissance-10-renforts.jpg` | 6 cavaleries de puissance 10 (renforts ?) | `20170714_154757.jpg` |
| `yzent-10-1-general-de-puissance-25-renforts.jpg` | 1 general de puissance 25 (renforts ?) | `20170714_154810.jpg` |
| `yzent-11-leader-1.jpg` | leader 1 | `20170714_154821.jpg` |
| `yzent-12-leader-2.jpg` | leader 2 | `20170714_154834.jpg` |

## Vicomté de Reissland

`02-reissland/` — Royaume indépendant de l'Empire, présent dans le scénario 1. Doit contenir l'invasion d'Yzent.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `reissland-01-15-infanteries.jpg` | 15 infanteries | `20170714_162924.jpg` |
| `reissland-02-8-cavaleries.jpg` | 8 cavaleries | `20170714_162904.jpg` |
| `reissland-03-3-archers.jpg` | 3 archers | `20170714_162845.jpg` |
| `reissland-04-1-leader.jpg` | 1 leader | `20170714_162934.jpg` |

## Empire Tharque

`03-empire/` — Les forces humaines de l'Empire : troupes de garnison puis renforts.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `empire-01-26-infanteries.jpg` | 26 infanteries | `20170715_142502.jpg` |
| `empire-02-6-cavaleries.jpg` | 6 cavaleries | `20170715_142519.jpg` |
| `empire-03-7-archers.jpg` | 7 archers | `20170715_142430.jpg` |
| `empire-04-1-leader.jpg` | 1 leader | `20170715_142541.jpg` |
| `empire-05-8-infanteries-renforts.jpg` | 8 infanteries (renforts) | `20170715_142630.jpg` |
| `empire-06-13-phalanges-renforts.jpg` | 13 phalanges (renforts) | `20170715_142559.jpg` |
| `empire-07-7-archers-renforts.jpg` | 7 archers (renforts) | `20170715_142614.jpg` |
| `empire-08-4-cavaleries-de-puissance-8-renforts.jpg` | 4 cavaleries de puissance 8 (renforts) | `20170715_143543.jpg` |
| `empire-09-6-cavaleries-de-puissance-10-renforts.jpg` | 6 cavaleries de puissance 10 (renforts) | `20170715_142646.jpg` |
| `empire-10-1-leader-renforts.jpg` | 1 leader (renforts) | `20170715_143428.jpg` |

## Templiers

`04-templiers/` — Renfort d'élite du scénario 1 (tour 12 ou chute du Reissland). Immunisés à la peur.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `templiers-01-5-infanteries.jpg` | 5 infanteries | `20170715_150125.jpg` |
| `templiers-02-9-cavaleries-de-puissance-10.jpg` | 9 cavaleries de puissance 10 | `20170715_150145.jpg` |
| `templiers-03-8-cavaleries-lourdes-de-puissance-15.jpg` | 8 cavaleries lourdes de puissance 15 | `20170715_150159.jpg` |
| `templiers-04-4-archers-montes-a-cheval.jpg` | 4 archers montes a cheval | `20170715_150216.jpg` |
| `templiers-05-1-general.jpg` | 1 general | `20170715_150243.jpg` |
| `templiers-06-leader-1.jpg` | leader 1 | `20170715_150259.jpg` |
| `templiers-07-leader-2.jpg` | leader 2 | `20170715_150314.jpg` |

## Population

`05-population/` — Pions de populace disséminés dans les villages de l'Empire en début de partie.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `population-01-20-populaces.jpg` | 20 populaces | `20170715_192640.jpg` |

## Empire de Lynn

`06-empire-de-lynn/` — Armée impériale du scénario 3 (Pour qui sonne le glas). Seule force du jeu à posséder des chars.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `empire-de-lynn-01-10-infanteries.jpg` | 10 infanteries | `20170715_194401.jpg` |
| `empire-de-lynn-02-10-cavaleries-de-puissance-10.jpg` | 10 cavaleries de puissance 10 | `20170715_194457.jpg` |
| `empire-de-lynn-03-4-cavaleries-lourdes-de-puissance-15.jpg` | 4 cavaleries lourdes de puissance 15 | `20170715_194532.jpg` |
| `empire-de-lynn-04-4-cavaleries-lourdes-de-puissance-30.jpg` | 4 cavaleries lourdes de puissance 30 | `20170715_194600.jpg` |
| `empire-de-lynn-05-10-phalanges.jpg` | 10 phalanges | `20170715_194633.jpg` |
| `empire-de-lynn-06-6-archers-de-puissance-4.jpg` | 6 archers de puissance 4 | `20170715_194708.jpg` |
| `empire-de-lynn-07-4-archers-de-puissance-10.jpg` | 4 archers de puissance 10 | `20170715_194739.jpg` |
| `empire-de-lynn-08-3-chars-legers.jpg` | 3 chars legers | `20170715_194802.jpg` |
| `empire-de-lynn-09-3-chars-lourds.jpg` | 3 chars lourds | `20170715_194825.jpg` |
| `empire-de-lynn-10-4-catapultes.jpg` | 4 catapultes | `20170715_194853.jpg` |
| `empire-de-lynn-11-empereur-whismerhill.jpg` | Empereur Whismerhill | `20170715_194935.jpg` |
| `empire-de-lynn-12-demi-dieu-azolhim.jpg` | Demi-dieu Azolhim | `20170715_194913.jpg` |

## Chaos

`07-chaos/` — Armée humaine de base du Magiocrate, première sur le champ de bataille.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `chaos-01-4-infanteries-de-puissance-5.jpg` | 4 infanteries de puissance 5 | `20170718_124656.jpg` |
| `chaos-02-10-archers-de-puissance-3.jpg` | 10 archers de puissance 3 | `20170718_124823.jpg` |
| `chaos-03-5-cavaleries-de-puissance-9.jpg` | 5 cavaleries de puissance 9 | `20170718_124942.jpg` |
| `chaos-04-10-phalanges.jpg` | 10 phalanges | `20170718_125122.jpg` |
| `chaos-05-6-infanteries-de-puissance-10-renforts.jpg` | 6 infanteries de puissance 10 (renforts ?) | `20170718_125449.jpg` |
| `chaos-06-1-leader.jpg` | 1 leader | `20170718_125540.jpg` |

## Non-humains

`08-non-humains/` — Sept races entrant par le Seuil des Brumes. Doivent toujours combattre groupées.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `non-humains-01-3-infanteries-de-trolls.jpg` | 3 infanteries de trolls | `20170718_133713.jpg` |
| `non-humains-02-6-infanteries-de-gobelins.jpg` | 6 infanteries de gobelins | `20170718_133804.jpg` |
| `non-humains-03-4-cavaleries-de-gobelins.jpg` | 4 cavaleries de gobelins | `20170718_133848.jpg` |
| `non-humains-04-3-infanteries-d-hobgobelins.jpg` | 3 infanteries d'hobgobelins | `20170718_133946.jpg` |
| `non-humains-05-2-archers-hobgobelins-h.jpg` | 2 archers hobgobelins (h) | `20170720_201750.jpg` |
| `non-humains-06-3-infanteries-k-kobolds.jpg` | 3 infanteries K (kobolds ?) | `20170720_201834.jpg` |
| `non-humains-07-2-archers-k-kobolds.jpg` | 2 archers K (kobolds ?) | `20170720_201919.jpg` |
| `non-humains-08-3-infanteries-m-minotaures-ou-manticores.jpg` | 3 infanteries m (minotaures ou manticores ?) | `20170720_202022.jpg` |
| `non-humains-09-3-infanteries-o-ogres-ou-orog.jpg` | 3 infanteries o (ogres ou orog ?) | `20170720_202128.jpg` |
| `non-humains-10-3-infanteries-bug.jpg` | 3 infanteries bug (?) | `20170720_202247.jpg` |
| `non-humains-11-2-phalanges-bug.jpg` | 2 phalanges bug (?) | `20170720_202315.jpg` |

## Elfes

`09-elfes/` — Alliés de l'Empire, apparaissent si une unité ennemie approche à 10 cases de la forêt elfique.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `elfes-01-5-infanteries.jpg` | 5 infanteries | `20170718_140046.jpg` |
| `elfes-02-4-archers.jpg` | 4 archers | `20170718_140113.jpg` |
| `elfes-03-5-cavaleries-de-puissance-6.jpg` | 5 cavaleries de puissance 6 | `20170718_140153.jpg` |
| `elfes-04-5-cavaleries-de-puissance-10.jpg` | 5 cavaleries de puissance 10 | `20170718_140239.jpg` |
| `elfes-05-3-archers-montes-a-cheval.jpg` | 3 archers montes a cheval | `20170718_140313.jpg` |
| `elfes-06-1-leader.jpg` | 1 leader | `20170720_205941.jpg` |

## Nains

`10-nains/` — Absents de la 1re édition. Scénario 4 (La guerre des nains), au sud du volcan de Toth.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `nains-01-5-infanteries.jpg` | 5 infanteries | `20170720_204053.jpg` |
| `nains-02-4-arbaletriers.jpg` | 4 arbaletriers | `20170720_203935.jpg` |
| `nains-03-4-arbaletriers-lourds.jpg` | 4 arbaletriers lourds | `20170720_203953.jpg` |
| `nains-04-5-phalanges.jpg` | 5 phalanges | `20170720_204024.jpg` |
| `nains-05-2-leaders.jpg` | 2 leaders | `20170720_204117.jpg` |
| `nains-06-1-mage-vorgtd.jpg` | 1 mage (Vorgtd) | `20170720_204129.jpg` |

## Orques

`11-orques/` — Basés dans l'Orcreich. Bonus d'attaque la nuit, malus le jour. Scénarios 1 et 4.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `orques-01-15-infanteries.jpg` | 15 infanteries | `20170721_113339.jpg` |
| `orques-02-5-cavaleries.jpg` | 5 cavaleries | `20170721_113516.jpg` |
| `orques-03-5-archers.jpg` | 5 archers | `20170721_113549.jpg` |
| `orques-04-5-archers-montes-a-cheval.jpg` | 5 archers montes a cheval | `20170721_113614.jpg` |
| `orques-05-2-infanteries-renforts.jpg` | 2 infanteries (renforts) | `20170721_113659.jpg` |
| `orques-06-5-cavaleries-renforts.jpg` | 5 cavaleries (renforts) | `20170721_113717.jpg` |
| `orques-07-3-cavaleries-archers-renforts.jpg` | 3 cavaleries archers (renforts) | `20170721_113738.jpg` |
| `orques-08-1-leader.jpg` | 1 leader | `20170721_113800.jpg` |

## Sahuaguins

`12-sahuaguins/` — Race aquatique du Lac Noir, soumise au Magiocrate. Force x2 en milieu aquatique.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `sahuaguins-01-1-infanterie.jpg` | 1 infanterie | `20170721_122824.jpg` |
| `sahuaguins-02-5-phalanges.jpg` | 5 phalanges | `20170721_122901.jpg` |
| `sahuaguins-03-5-tridents.jpg` | 5 tridents | `20170721_122802.jpg` |
| `sahuaguins-04-9-archers.jpg` | 9 archers | `20170721_122750.jpg` |

## Dragons

`13-dragons/` — Invocation des forces du bien (20 points de magie, apparition sur un 1 au dé). Attaque unique à 4 contre 1.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `dragons-01-pions-de-dragons-trois-couleurs.jpg` | pions de dragons (trois couleurs) | `20170721_125028.jpg` |

## Morts-vivants

`14-morts-vivants/` — Invoqués par le Magiocrate depuis l'Île du Crâne (80 points de magie). Ne combattent que la nuit.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `morts-vivants-01-20-unites-de-squelettes.jpg` | 20 unites de squelettes | `20170721_184848.jpg` |
| `morts-vivants-02-7-unites-de-zombies.jpg` | 7 unites de zombies | `20170721_184929.jpg` |
| `morts-vivants-03-5-goules.jpg` | 5 goules | `20170721_184955.jpg` |
| `morts-vivants-04-5-archers-de-nature-indeterminee.jpg` | 5 archers de nature indeterminee | `20170721_185041.jpg` |
| `morts-vivants-05-5-cavaleries-de-nature-indeterminee.jpg` | 5 cavaleries de nature indeterminee | `20170721_185102.jpg` |
| `morts-vivants-06-3-lords-montes-sur-dragons.jpg` | 3 lords (montes sur dragons) | `20170721_185124.jpg` |

## Démons

`15-demons/` — Légions invoquées par Orvarth (100 points de magie) ; protoplasmiques (50 points).

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `demons-01-5-infanteries.jpg` | 5 infanteries | `20170723_192754.jpg` |
| `demons-02-3-cavaleries.jpg` | 3 cavaleries | `20170723_193012.jpg` |
| `demons-03-4-phalanges.jpg` | 4 phalanges | `20170723_193037.jpg` |
| `demons-04-5-tridents.jpg` | 5 tridents (?) | `20170723_193113.jpg` |
| `demons-05-prince-demon-1.jpg` | prince demon 1 | `20170723_193137.jpg` |
| `demons-06-prince-demon-2.jpg` | prince demon 2 | `20170723_193158.jpg` |
| `demons-07-prince-demon-3.jpg` | prince demon 3 | `20170723_193218.jpg` |
| `demons-08-8-demons-protoplasmiques.jpg` | 8 demons protoplasmiques | `20170723_193240.jpg` |

## Volants

`16-volants/` — Race ailée du scénario 5 (attaque de Morgenstern). Leader Lullth, mage Huluth.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `volants-01-5-infanteries.jpg` | 5 infanteries | `20170723_194849.jpg` |
| `volants-02-5-phalanges.jpg` | 5 phalanges | `20170723_194939.jpg` |
| `volants-03-8-archers.jpg` | 8 archers | `20170723_195005.jpg` |
| `volants-04-1-leader-lullth.jpg` | 1 leader (Lullth) | `20170723_195025.jpg` |
| `volants-05-1-mage-huluth.jpg` | 1 mage (Huluth) | `20170723_195041.jpg` |

## Conjurations diverses

`17-conjurations/` — Élémentaires et animaux conjurés par les mages et clercs. Durée : 3 tours.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `conjurations-01-6-chauves-souris.jpg` | 6 chauves-souris | `20170723_200755.jpg` |
| `conjurations-02-3-loups.jpg` | 3 loups | `20170723_200831.jpg` |
| `conjurations-03-6-rats.jpg` | 6 rats | `20170723_200851.jpg` |
| `conjurations-04-6-elementaires-de-feu.jpg` | 6 elementaires de feu | `20170723_200914.jpg` |
| `conjurations-05-6-elementaires-de-terre.jpg` | 6 elementaires de terre | `20170723_200939.jpg` |
| `conjurations-06-6-elementaires-d-air.jpg` | 6 elementaires d'air | `20170723_201000.jpg` |
| `conjurations-07-6-elementaires-d-eau.jpg` | 6 elementaires d'eau | `20170723_201022.jpg` |

## Machines de siège

`18-machines-de-siege/` — Le Juggernaut, engin de siège du Seigneur Whismerhill (scénario 3).

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `machines-de-siege-01-juggernaut.jpg` | Juggernaut | `20170723_204336.jpg` |

## Magiciens et clercs

`19-magiciens/` — Pions de jeteurs de sorts des deux camps (5 pour les ténèbres, 4 pour l'Empire, plus Orvarth et Thornz).

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `magiciens-01-pions-de-magiciens-vue-d-ensemble.jpg` | pions de magiciens (vue d'ensemble) | `20170707_194729.jpg` |
| `magiciens-02-pions-de-magiciens-et-clercs-vue-d-ensemble.jpg` | pions de magiciens et clercs (vue d'ensemble) | `20170707_194615.jpg` |

## Marqueurs et éléments de jeu

`20-marqueurs/` — Pions sans force de combat, posés sur la carte par les sorts ou les facultés spéciales.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `marqueurs-01-feu-mur-de-flammes.jpg` | feu (mur de flammes) | `20170711_212643.jpg` |
| `marqueurs-02-brume-mur-de-brume.jpg` | brume (mur de brume) | `20170711_213319.jpg` |
| `marqueurs-03-paralysie.jpg` | paralysie | `20170711_213715.jpg` |
| `marqueurs-04-deroute.jpg` | deroute | `20170711_214414.jpg` |
| `marqueurs-05-forteresse-ou-tour-en-ruines.jpg` | forteresse ou tour en ruines | `20170711_215353.jpg` |
| `marqueurs-06-breche-dans-un-mur.jpg` | breche dans un mur | `20170711_215436.jpg` |

## Vues d'ensemble

`21-vues-d-ensemble/` — Photos générales des planches de pions et du rangement.

| Fichier | Contenu | Photo d'origine |
| --- | --- | --- |
| `vues-d-ensemble-01-planches-de-pions.jpg` | planches de pions | `20170707_194529.jpg` |
| `vues-d-ensemble-02-boite-de-rangement-des-pions.jpg` | boite de rangement des pions | `20170707_195114.jpg` |
| `vues-d-ensemble-03-pions-en-vrac-vue-1.jpg` | pions en vrac (vue 1) | `20170403_163205.jpg` |
| `vues-d-ensemble-04-pions-en-vrac-vue-2.jpg` | pions en vrac (vue 2) | `20170403_163157.jpg` |
---

## Réserves sur l'inventaire

- **Chaos — cavaleries lourdes** : la source blog réutilise la même photo
  (`20170718_125449.jpg`) pour « 6 infanteries de puissance 10 » et pour
  « 5 cavaleries lourdes (renforts) ». La photo n'a été classée qu'une fois, sous les
  infanteries ; la photo des cavaleries lourdes du Chaos manque donc dans la source.
- Les libellés « (renforts ?) » avec point d'interrogation reprennent les incertitudes de la
  source : les règles ne précisent pas quelles unités d'Yzent et du Chaos sont les troupes de
  départ et lesquelles sont les renforts.
- Les initiales des non-humains (`h`, `K`, `m`, `o`, `bug`) ne sont expliquées nulle part dans
  les règles ; les interprétations proposées sont celles de l'auteur de l'article.
- **Lectures incomplètes dans `pions.json`** : sur cinq photos le pion est rogné ou la valeur
  illisible, et le champ reste à `null` — `yzent-02` (bas du pion), `orques-07` (pas de valeurs de
  tir imprimées), `morts-vivants-05` (un « 5 » isolé au bas centre), `conjurations-01` (pas de
  mouvement au sol), `conjurations-07` (bas gauche). Le champ `remarques` le signale à chaque fois.
- **Deux fichiers de `19-magiciens/` ne sont pas des pions** : ce sont les feuilles de suivi
  Alliance et Forces Noires (succession des tours, table des résultats, pistes de points de magie
  des mages). Les noms qu'elles portent sont relevés dans `remarques` de `pions.json` : THORNZ,
  MIRZ, ORF, CHÊL, ELIM côté Alliance ; ORVARTH, VIZ, ÔM, HAART, GÔL, ZORN côté Forces Noires.
  De même, `vues-d-ensemble-01-planches-de-pions.jpg` montre en fait la page « Symboles » du
  fascicule, pas les planches de pions.

## Images de `base_material/images/` non reprises ici

Ces 17 fichiers ne sont pas des pions et restent uniquement dans `base_material/images/` : couverture et
photos de boîte (`pic73874_md.jpg`, `20170707_194444.jpg`, `0f6274f5782e7183198dcabff5b13ed1267d.jpeg`,
`HE_BGG_2.jpg`), vues de la carte et de ses régions (`20170707_194834.jpg`, `20170403_163236.jpg`,
`20170710_134448.jpg`, `20170710_134527_001.jpg`, `20170710_134550.jpg`, `20170710_134613.jpg`,
`20170710_134853.jpg`, `20170710_143554.jpg`, `20170710_150031_001.jpg`), extension
*Fiefs et Empires* (`fiefs.jpeg`), BD *Chroniques de la Lune Noire* (`chroniques.jpg`), et
éléments d'habillage du blog (`blogger_logo_round_35.png`, `121110-F-VO466-040.JPG`).
