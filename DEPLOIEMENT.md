# Déploiement — ce que le flux SSE demandera

Le jeu ne tourne aujourd'hui qu'en développement : `python3 app.py`, un seul processus, pas de
serveur en façade. Ce document n'est donc pas un mode d'emploi de mise en production — c'est la
liste de ce qu'il faudra régler **le jour où** il y en aura une, et qui ne se voit pas en local.

Tout tient à une chose : depuis que la partie se suit par un **flux d'événements** (`GET /flux`,
du Server-Sent Events — voir `application/flux.py` et la section « Suivre la partie de
l'adversaire » d'`application/README.md`), chaque onglet ouvert tient une **requête HTTP qui ne
se termine jamais**. Tout ce qui, dans une pile web ordinaire, suppose qu'une réponse est courte
— la concurrence, le tampon, les délais d'attente — doit être revu.

Les endroits du code concernés portent tous le marqueur `TODO: PRODUCTION` :

```
grep -rn "TODO: PRODUCTION" application/
```

---

## a) Le serveur WSGI

**Ne pas servir le jeu par `app.run()`.** Le serveur de développement de Flask convient au flux en
local — il est multi-thread par défaut, et c'est ce qui permet à plusieurs onglets d'être servis
en même temps —, mais il n'est pas fait pour être exposé : ni robustesse, ni performances, ni
sécurité.

Avec **Gunicorn**, il faut un worker capable de tenir beaucoup de connexions ouvertes à la fois.
Un worker synchrone ordinaire n'en tient qu'une par processus : deux joueurs, et le serveur ne
répond plus.

```
pip install gunicorn gevent
gunicorn -k gevent -w 1 'app:create_app()'
```

Deux remarques sur cette ligne :

- **`gevent` plutôt qu'`eventlet`.** Le brief mentionnait `eventlet` ; il n'est plus maintenu et
  passe mal sur les Python récents. `gevent` fait la même chose et reste entretenu. Si l'on tient
  à `eventlet`, `-k eventlet` marche de la même façon — à vérifier avec la version de Python
  utilisée.
- **`'app:create_app()'` et non `app:app`.** Ce dépôt n'a pas d'application globale : `app.py`
  n'expose que le blueprint `jeu` et la factory. Gunicorn sait appeler une factory si on la lui
  écrit ainsi.
- **Lancer depuis `application/`**, ou poser `--pythonpath application` : les imports du projet
  sont absolus et supposent que `application/` est sur le chemin (voir `CLAUDE.md`).

Une alternative aux workers asynchrones, si l'on veut rester en synchrone : `-k gthread` avec
assez de threads (`--threads 32`). C'est plus simple à raisonner, et suffisant pour un jeu à deux
joueurs ; mais chaque onglet ouvert consomme un thread, et le compte est vite atteint si la partie
est regardée.

---

## b) La configuration Nginx

Nginx tamponne les réponses par défaut : il attendrait d'avoir de quoi remplir un tampon avant de
transmettre quoi que ce soit, et les messages du jeu resteraient coincés chez lui. Le plateau
paraîtrait figé, et rien dans les journaux ne le dirait.

```nginx
location /flux {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_read_timeout 24h;
}
```

**L'en-tête `X-Accel-Buffering: no` est déjà posé par la réponse Flask** (dans la route `/flux`,
`application/app.py`), et il dit à Nginx la même chose que `proxy_buffering off;` — pour cette
réponse-là seulement. Les deux ensemble, et non l'un ou l'autre : l'en-tête protège si la
configuration est oubliée, la configuration protège si un intermédiaire ignore l'en-tête.

Le reste du site n'a pas besoin de ce traitement : `map.jpg` fait 10 Mo, et le tampon lui est
utile. D'où le `location /flux` séparé plutôt qu'un réglage global.

---

## c) Les délais d'attente à surveiller

Un flux silencieux ressemble à une connexion morte. Le serveur envoie donc un commentaire SSE
(`: battement`) toutes les **20 secondes** (`BATTEMENT` dans `application/app.py`) : c'est ce qui
maintient la connexion vivante à travers les intermédiaires.

Chaque intermédiaire a son propre délai, et **le plus court gagne** :

| Où | Réglage | Défaut | À faire |
| --- | --- | --- | --- |
| Nginx | `proxy_read_timeout` | 60 s | monter à `24h` sur `/flux` |
| Gunicorn | `--timeout` | 30 s | sans objet en worker asynchrone ; en `gthread`, monter |
| AWS ALB | *idle timeout* | 60 s | monter, ou vérifier que 20 s de battement suffisent |
| Cloudflare | — | ~100 s | le battement suffit |

Le battement de 20 s passe sous toutes ces valeurs par défaut : même mal configuré, le flux ne
devrait pas tomber. Et s'il tombe, ce n'est pas une panne — `EventSource` se reconnecte tout seul
et renvoie son `Last-Event-ID`, sur quoi le serveur lui rend ce qu'il a manqué. **Préférer donc
monter le délai de l'intermédiaire plutôt que descendre le battement** : un battement plus court
est du trafic pour rien.

---

## d) Plusieurs workers — la limite à connaître

**Le registre des flux ouverts est en mémoire, dans le processus** (`Diffuseur`, dans
`application/flux.py`). C'est aussi vrai de tout l'état de jeu : le plateau, le tour, le registre
des combats et la table des places sont des module-globaux d'`application/app.py`. Le jeu suppose
donc **un seul processus** — c'est déjà le cas aujourd'hui, bien avant le flux.

Avec `gunicorn -w 2` ou plus, deux choses casseraient, et pas seulement le flux :

1. **Chaque worker aurait son propre diffuseur.** Un joueur servi par le worker 2 ne verrait
   jamais le coup joué sur le worker 1 : `marquer_un_coup` ne publie qu'aux abonnés de son
   processus.
2. **Chaque worker aurait sa propre partie en mémoire.** Deux joueurs répartis sur deux workers
   joueraient chacun sur un plateau différent, MongoDB ne les recollant qu'au rechargement de
   « / ».

Autrement dit : **`-w 1` n'est pas une précaution liée au SSE, c'est ce que l'application demande
aujourd'hui.** Le flux ne fait qu'ajouter une raison de plus.

Pour aller au-delà, il faudrait deux chantiers distincts :

- **Un pub/sub externe** — Redis, typiquement — entre `marquer_un_coup` et les boîtes des
  abonnés : chaque worker publierait sur un canal et s'y abonnerait, et `Diffuseur.publier`
  deviendrait un `PUBLISH`. La structure s'y prête, tout passe déjà par un seul point.
- **L'état de jeu sorti des module-globaux**, relu en base à chaque requête et écrit sous
  verrou. C'est le plus gros des deux, et il n'a rien à voir avec le flux.

Tant que ces deux-là ne sont pas faits : **un seul worker**.

---

## Ce qui n'a pas besoin de changer

- **Les actions du joueur.** Le flux est à sens unique, serveur → navigateur. Tout ce que le
  joueur fait part en `POST` sur les routes ordinaires (`/deplacer`, `/combat`,
  `/phase/suivante`, `/partie/place`), et rien de cela n'a bougé.
- **Le repli.** `GET /partie/etat` est toujours servi : une page dont l'`EventSource` échoue cinq
  fois de suite y retombe et sonde toutes les trois secondes. Un intermédiaire mal réglé ralentit
  le jeu, il ne le casse pas.
- **Les secrets et la session.** Rien de nouveau : `.env`, `SECRET_KEY`, et
  `COOKIE_SECURISE=oui` derrière HTTPS (voir `.env.example`).
