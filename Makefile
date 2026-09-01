# Ave Tenebrae — lancement de la suite de tests.
#
# `make test` monte un MongoDB de test dans un conteneur, attend qu'il réponde, puis lance
# pytest en le lui désignant. C'est la façon de vérifier le dépôt : tout ce qu'on veut éprouver
# s'écrit en test et se rejoue par cette commande — on ne lance pas l'application à la main.
#
# Le conteneur est à part de celui du jeu : il écoute sur un autre port (27018) et travaille dans
# sa propre base, `tenebrae_test`. Il reste allumé entre deux `make test`, ce qui rend les séries
# rapides ; `make mongo-arret` le retire.
#
# Sans Docker, `make test-rapide` lance la même suite sans base : les tests qui demandent un vrai
# MongoDB se sautent d'eux-mêmes, tous les autres tournent (mongomock couvre la persistance en
# mémoire).

CONTENEUR ?= tenebrae-mongo-test
IMAGE     ?= mongo:7
PORT      ?= 27018
BASE      ?= tenebrae_test
URI       := mongodb://localhost:$(PORT)/$(BASE)

# Arguments passés à pytest : `make test ARGS="-k persistance -v"`.
ARGS ?=

.PHONY: test test-rapide test-navigateur mongo mongo-arret navigateur aide

aide:
	@echo "make test            — monte MongoDB et lance toute la suite"
	@echo "make test-rapide     — la suite sans MongoDB (les tests qui en demandent se sautent)"
	@echo "make test-navigateur — les seuls tests Chromium"
	@echo "make mongo           — monte le MongoDB de test et l'attend"
	@echo "make mongo-arret     — retire le conteneur"
	@echo "make navigateur      — installe Chromium pour Playwright"
	@echo ""
	@echo "ARGS passe des arguments à pytest :  make test ARGS='-k persistance -v'"

test: mongo
	MONGODB_URI_TEST=$(URI) python3 -m pytest $(ARGS)

test-rapide:
	python3 -m pytest $(ARGS)

test-navigateur: mongo
	MONGODB_URI_TEST=$(URI) python3 -m pytest application/tests/test_plateau.py \
		application/tests/test_map_fix_navigateur.py \
		application/tests/test_reprise_navigateur.py \
		application/tests/test_connexion_navigateur.py \
		application/tests/test_ia_navigateur.py \
		application/tests/test_flux_navigateur.py $(ARGS)

# Monte le conteneur s'il n'est pas déjà là, puis attend que la base réponde vraiment : un
# conteneur « Up » n'est pas encore un serveur qui accepte les connexions, et pytest partirait
# alors en sautant les tests qui la demandent.
mongo:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "Docker est absent : utiliser « make test-rapide » (les tests MongoDB se sauteront)."; \
		exit 1; \
	fi
	@if [ -z "$$(docker ps -q -f name=^/$(CONTENEUR)$$)" ]; then \
		if [ -n "$$(docker ps -aq -f name=^/$(CONTENEUR)$$)" ]; then \
			echo "Redémarrage du conteneur $(CONTENEUR)..."; \
			docker start $(CONTENEUR) >/dev/null; \
		else \
			echo "Création du conteneur $(CONTENEUR) sur le port $(PORT)..."; \
			docker run -d --name $(CONTENEUR) -p $(PORT):27017 $(IMAGE) >/dev/null; \
		fi; \
	fi
	@printf "Attente de MongoDB sur le port $(PORT)"
	@for i in $$(seq 1 60); do \
		if docker exec $(CONTENEUR) mongosh --quiet --eval "db.runCommand({ping:1})" \
			>/dev/null 2>&1; then \
			echo " — prêt."; exit 0; \
		fi; \
		printf "."; sleep 1; \
	done; \
	echo " — pas de réponse après 60 s."; exit 1

mongo-arret:
	@docker rm -f $(CONTENEUR) >/dev/null 2>&1 && echo "Conteneur $(CONTENEUR) retiré." \
		|| echo "Aucun conteneur $(CONTENEUR)."

navigateur:
	python3 -m playwright install chromium
