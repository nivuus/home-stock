# home-stock — notes d'implémentation

Intégration Home Assistant custom « Garde-manger » (domaine `home_stock`) : stocks
de la maison en lots (date limite, prix payé), journal des mouvements en ajout
seul, courses, recettes, comptabilité kcal et euros. Panneau Lit/TypeScript,
services et websocket, phrases vocales françaises, blueprints.
C'est aussi un **package Nivuus** (satellite de `home-manager`) : `hooks/install.py`
dépose l'intégration dans la configuration du socle. Suite de 9 dépôts sous
`packages/` ; le README est court, ce fichier ne le recopie pas.

## Commandes vérifiées (2026-09-29, arbre `origin/main`)

Le serveur a déjà gelé par saturation mémoire : **un lot à la fois**, jamais deux
suites en parallèle.

```bash
make test                    # package : manifeste + hooks install/activate. python3 + PyYAML, rapide
make test NIVUUS_INSTALLER_DIR=/home/mallanic/Projects/Nivuus/packages/installer
                             # idem, avec le VRAI parseur du moteur (chemin ABSOLU : $HOME vaut /root ici)
./scripts/test.sh -q tests/domain      # pytest dans Docker (image HA 2026.8.2), 259 tests, ~15 s
./scripts/test.sh -q                   # suite complète : 2223 passés, 1 ignoré, 14 min, ~450 Mo de RAM (mesuré sur `master`)
./scripts/test.sh -m network           # tests réseau réel, exclus par défaut (pytest.ini)
cd frontend && npm test | npm run typecheck | npm run verifier   # vitest / tsc / rendu
```

- `make test-integration` exige `homeassistant` installé sur l'hôte : absent ici, passer par
  `scripts/test.sh`. Aucun test ne touche l'instance de production.
- `scripts/test.sh` reconstruit l'image (`pip install`, réseau requis) et monte `$PWD` en
  écriture : le conteneur, root, laisse des `__pycache__`. Pour lire seulement :
  `docker run --rm -e PYTHONDONTWRITEBYTECODE=1 --entrypoint python -v "$PWD:/src:ro" -w /src home-stock-test -m pytest -q -p no:cacheprovider tests/<lot>`.
  Le démon Docker ne voit pas le scratchpad sous `/tmp/user/...` (montage vide, pytest
  répond « file not found ») : lancer depuis le dépôt.
- `NIVUUS_INSTALLER_DIR` : le dépôt `installer` doit être sur un `main` récent, sinon
  `manifest.source` n'existe pas et `test_manifest_contract.py` échoue (constaté sur une
  branche `spec/…` en retard).
- Non vérifiés ici (pas de `node_modules`) : les commandes `npm`. Lint CI : `ruff check`,
  version épinglée dans `requirements.txt`, règles dans `ruff.toml` (E4, E7, E9, F seulement).

## Architecture (`custom_components/home_stock/`)

- `application.py` (`StockManager`) : toute la logique métier, seule voie d'écriture.
  `services.py` et `websocket*.py` sont deux surfaces sur ce même noyau — voir « Pièges ».
- `domain/` : règles pures sans HA (`stock`, `units`, `conversion`, `nutrition`, `pricing`,
  `matching`, `shoppinglist`, `foodday`, `goals`, `route`, `maintenance`…).
- `storage/` : SQLite (`database.py` : un écrivain sérialisé + un lecteur WAL),
  `repositories.py`, `migrations/m001…m008` (schéma, catalogue, lots, journal ; le journal
  `movement` est protégé par des triggers posés par m001).
- `coordinator.py` (`DataUpdateCoordinator`) alimente les plateformes `sensor`,
  `binary_sensor`, `event`, `todo`, `calendar`. `__init__.py` ouvre la base dans
  l'executor et lève `ConfigEntryNotReady` si elle échoue.
- `off/` (Open Food Facts, Open Prices), `grocy/` + `import_grocy*.py` (import
  unidirectionnel, simulation par défaut), `receipt/` (tickets, `ai_task`), `recipes/`
  (TheMealDB), `migration_check.py` (contrôles de la bascule Grocy).
- `panel.py` sert `panel/home-stock-panel.js` (bundle **suivi par git**) ; sources dans
  `frontend/src/` (points d'entrée `panneau.ts`, écrans dans `ecrans/`, `shell/`, `scan/`).
- Hors intégration : `custom_sentences/fr/home_stock.yaml` (7 phrases),
  `packages/home_stock_intents.yaml` (leurs `intent_script`), `blueprints/automation/home_stock/`,
  `docs/exploitation.md` (montage, import Grocy), `docs/extinction/` (18 gestes, à la main),
  `docs/raccord/` (copies de référence, jamais installées).

## Pièges (présents dans le code, les docs ou la CI)

- **Le dépôt EST l'intégration déployée** sur l'instance de référence : montage docker de
  `data/meal/custom_components/home_stock` (`docs/exploitation.md`), exclusif avec HACS.
  Un changement de volume exige `docker compose up -d homeassistant`, pas `restart`.
- **`npm run build` déploie** : rollup écrit dans `custom_components/home_stock/panel/`.
  Ne le lancer que pour livrer un changement voulu ; `npm run verifier` construit en mémoire
  (esbuild) et sert un `hass` factice sur 127.0.0.1, sans jamais toucher l'instance réelle.
  Le bundle est servi sans cache (`cache_headers=False`), volontairement.
- **Hook `install` idempotent, ré-exécuté à chaque mise à jour** (`hooks/install.py`) :
  refuse (code 1) si `opt/nivuus/home-manager/config` est absent ; remplace en entier
  `OWNED_TREES` (`custom_components/home_stock`, `blueprints/automation/home_stock`) par copie
  voisine + `os.replace` ; ne copie que des **fichiers** dans les répertoires partagés
  (`packages/`, `custom_sentences/fr/`) ; sérialise par `flock` sur le répertoire de config.
  Il n'écrit **jamais** dans `configuration.yaml`.
- **Phrases vocales conditionnelles** : `custom_sentences/` est chargé seul par HA, mais
  `packages/` seulement si `configuration.yaml` déclare `packages: !include_dir_named packages`.
  Sans cette ligne le hook ne dépose pas les phrases (sinon reconnues sans gestionnaire) et
  émet un message. Les `speech:` lisent `action_response` et le script finit par
  `stop:` porteur du `response_variable` (`tests/test_voice_package.py`).
- **`hooks/activate.py`** redémarre le conteneur `homeassistant` s'il tourne (HA n'importe
  une intégration qu'au démarrage) ; conteneur absent ou arrêté = pas d'erreur.
- **`nivuus-package.yaml`** : `version: 0.0.0` ; `requires.packages: [home-manager]` impose
  l'ordre ; ni `apt:` ni `wizard:` (voulu) ; `source.github: nivuus/home-stock` est ce que
  lit `nivuus update`. `tests/test_manifest_contract.py` fige tout cela.
- **Services** : `async_register_services` n'enregistre qu'une fois (`has_service`) et rien
  ne les retire à l'unload ; ils sont donc domaine-larges, pas par entrée. Toujours un
  `vol.Schema`, et les handlers passés en `partial`/coroutines (jamais un `lambda`, que HA
  exécuterait dans un thread en jetant la coroutine).
- **Parité service/websocket** : ce que l'un refuse, l'autre le refuse
  (`tests/test_surface_parity.py`). Les deux importent `validators.py` : y mettre les règles communes.
- **Panneau** : `_STATIC_PATH_REGISTERED_KEY` — le chemin statique ne se désenregistre pas
  (aiohttp), le panneau de la barre latérale si ; ne pas les regrouper sous un seul drapeau.
- **Base** `config/home_stock.db` : partir d'une création fraîche par l'intégration (les
  triggers du journal viennent de m001), jamais d'une copie de base de développement.
  Import Grocy : lire une copie, jamais la base Grocy de production.
- `requirements.txt` : la liste d'appoint (ffmpeg, hassil, frontend…) est la clôture
  transitive des manifestes pour HA 2026.8.2 ; à recalculer quand on bouge la version de
  `pytest-homeassistant-custom-component`, pas à éditer ligne à ligne.

## Conventions

- CI (`.github/workflows/ci.yml`) : workflows partagés `nivuus/.github` (`policy`,
  `security`, `python` en Python 3.14, `package`). Checks bloquants : `policy / Coding rules`
  et `security / Secrets and dependencies`. `release.yml` publie à chaque push sur `main`
  via le workflow partagé. Les contrôles ne portent que sur les fichiers modifiés par la PR.
- `main` protégée : PR obligatoire, **merge en squash**, branche supprimée après. **Titre de
  PR en Conventional Commits, en anglais** (`feat(scope): …`). Le squash fond les commits
  de la branche dans un seul. Gabarit : `.github/PULL_REQUEST_TEMPLATE.md`.
- Push en **HTTPS** (`origin` = `https://github.com/nivuus/home-stock.git`).
- Code, commentaires, commits et branches en anglais ; textes affichés à l'utilisateur,
  README et `docs/` en français. Exemptions : `policy: allow-fr`, `allow-fr-file`,
  `allow-long-file` (voir `CONTRIBUTING.md`). Fichiers source ≤ 500 lignes (tests exemptés) :
  `application.py`, `websocket_api.py`, `services.py`, `migration_check.py` et `sensor.py` dépassent déjà : ne pas aggraver.
- Le checkout local peut rester sur l'ancienne branche `master` alors que `origin/main` a
  avancé (relevé le 2026-09-29 : 9 commits de retard, dont le hook `activate`, le manifeste
  `source:` et `create_product`) : `git fetch` et se placer sur `main` avant tout travail.
