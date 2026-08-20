# Journal d'exécution — lot 1 de home_stock

*Exécution en subagent-driven development, du 2026-08-19 au 2026-08-20. 17 tâches, 51 commits.*
*Conservé pour ce qu'il contient de non reconstituable : les décisions prises en cours de route, et pourquoi.*

Branche : lot-1-scan-et-entree — base master 225691a
Tests Python : ./scripts/test.sh — front : cd frontend && npm test

## Préflight — table de conflits

### Paires de tâches partageant un fichier ou une interface

| Paires | Produit → consommé | Constat |
|---|---|---|
| T1 → T2 | `aisles.py` : T1 crée AISLES/CATEGORY_TO_AISLE, T2 ajoute TAG_TO_AISLE/resolve_aisle | **Conflit** : T1 Step 7 lance `tests/test_aisles.py`, créé par T2 |
| T1 → T3 | `movement.base_unit` créée → rendue obligatoire | Cohérent |
| T1 → T4 | tables shopping_* + `default_shelf_life_days` → dépôts | Cohérent |
| T3 → T4 | `repositories.py` modifié par les deux, séquentiellement | Cohérent |
| T3 → T10 | `insert_movement(base_unit=)` → écritures de conversion | Cohérent |
| T2 → T5 | `resolve_aisle` → `map_article` | Cohérent |
| T5 → T12 | `map_article`/`nutrition_per_base_unit` → `article/create` | Cohérent |
| T6 → T12 | `OffClient` → câblage dans `HomeStockData` | Cohérent |
| T7 → T12 | `candidates`/`preselect`/`strip_brand` → `lookup` | Cohérent |
| T8 → T12 | `suggest_price`/`latest_price` → `lookup` | **Conflit** : `_suggest_price` lit `article["code"]`, absent de `find_article_by_barcode` |
| T9 → T10 | `ConversionPlan` → exécution | Cohérent |
| T9 → T12 | `MIN_REFERENCE`/`MAX_REFERENCE` → `_conversion_offer` | Cohérent |
| T10 → T11 | `update_product_fields` → `_learn_shelf_life` | Cohérent (T10 précède T11) |
| T4 → T13 | `current_session`/`session_totals` → `summary()` | Cohérent |
| T12 → T13 | `websocket_api.py` modifié par les deux, séquentiellement | Cohérent |
| T12 → T14 | `HomeStockData` → enregistrement du panneau dans `__init__` | Cohérent |
| T14 → T15/16/17 | `Connexion`/`FileAttente`/`panneau.ts` → écrans | Cohérent |

### Auto-cohérence de chaque tâche

| Tâche | Constat |
|---|---|
| T1 | **Défaut** : liste `tests/test_aisles.py` dans ses fichiers alors que son code de test est dans `test_migrations.py` ; exceptions des déclencheurs à préciser |
| T2 | Cohérente — tests sur fixtures réelles, code fourni en entier |
| T3 | Cohérente |
| T4 | Cohérente — `insert_batch`/`insert_price` vérifiées contre le lot 0 |
| T5 | Cohérente |
| T6 | Cohérente |
| T7 | Cohérente |
| T8 | Cohérente |
| T9 | Cohérente |
| T10 | Cohérente |
| T11 | **Défaut** : `add_line` rend tantôt une ligne complète, tantôt un dict partiel |
| T12 | **Défaut** : `_suggest_price(article["code"])` ; `stock_add` traite `add_stock` comme pouvant rendre un dict alors qu'il rend un `int` |
| T13 | **Défaut** : esquisse un `HomeStockSensor(key=, value_key=)` générique ; `sensor.py` du lot 0 a une classe par capteur |
| T14 | Cohérente — `panel_custom.async_register_panel` et `StaticPathConfig` vérifiés dans l'image HA 2026.8.2 |
| T15 | Cohérente |
| T16 | Cohérente |
| T17 | Cohérente |

## Rulings de préflight

Ruling: T1 ne crée pas `tests/test_aisles.py` — son Step 7 lance `./scripts/test.sh tests/storage/ -v` uniquement, et `tests/test_aisles.py` appartient entièrement à T2 — parce qu'une tâche ne peut pas lancer un fichier de test que la suivante écrit — coût si faux : T1 échoue à son étape 7 et l'implémenteur invente un fichier vide qui masquerait un trou de couverture.

Ruling: les tests des déclencheurs d'ajout-seul et de l'index partiel acceptent `(sqlite3.IntegrityError, sqlite3.OperationalError)` — parce que le lot 0 a déjà été mordu par cette différence entre `RAISE(ABORT)` et une contrainte — coût si faux : un test vert qui ne prouve rien, ou rouge sur un comportement correct.

Ruling: `_suggest_price` reçoit le code-barres scanné en paramètre explicite plutôt que de le lire dans la ligne `article` — parce que `find_article_by_barcode` fait `SELECT a.*` et ne rend aucune colonne `code` — coût si faux : Open Prices ne serait jamais interrogé pour un article déjà connu, en silence.

Ruling: `StockManager.add_stock` rend un `int` (l'identifiant du lot) ; T11 et T12 le traitent comme tel, sans test `isinstance(..., dict)` — vérifié dans `application.py` du lot 0 — coût si faux : du code mort qu'un relecteur signalerait à juste titre.

Ruling: T13 écrit deux classes `CartTotalSensor` et `ToStoreSensor` sur le modèle de `StockValueSensor` du lot 0, au lieu du capteur générique paramétré esquissé dans le plan — parce que `sensor.py` a une classe par capteur et qu'introduire une seconde forme fragmenterait le fichier — coût si faux : deux styles de capteurs cohabitent, à réunifier au lot 2.

Ruling: `ShoppingService.add_line` rend toujours la ligne complète telle que la base la contient, y compris sans clé d'idempotence — parce qu'un appelant ne doit pas avoir à deviner la forme du retour selon ce qu'il a envoyé — coût si faux : le panneau lit `aisle_name` sur un dict qui ne l'a pas et affiche une ligne sans rayon.

## Journal d'exécution

Task 1: implémenteur DONE_WITH_CONCERNS (commit 9d35c53, 141 tests verts)
  - concern 1 : a dû renommer/adapter `tests/test_websocket.py::test_aisles_list_is_empty_until_lot_1` — hors liste de fichiers, mais le test du lot 0 annonçait lui-même ce changement
  - concern 2 : le helper `_lot0_database()` du plan insérait dans `schema_version` avant sa création — corrigé dans le test
Task 1: relecture dispatchée (base de20ff2 → 9d35c53)
Task 1: relecture — spec ✅, qualité approuvée. 1 Important (backfill silencieux de base_unit sur produit orphelin), 1 mineur.
Task 1: minor (deferred): `FALLBACK_AISLE` sans consommateur tant que T2 n'a pas atterri — attendu, T2 le consomme.
Task 1: Ruling: laisser `base_unit` à NULL pour un mouvement dont le produit a disparu — une unité inconnue s'écrit inconnue plutôt que devinée, et la clé étrangère rend le cas inatteignable en production — coût si faux : une ligne de journal illisible, sans possibilité de rattrapage puisque la migration ne repasse pas. Correction demandée : un commentaire qui le dit et un test qui l'épingle.
Task 1: fix round 1/5 dispatché
Task 1: fix round 1/5 (2 addressed, 0 open ; commits 9d35c53..1863a90)
Task 1: complete (commits de20ff2..1863a90, relecture propre, 142 tests verts)
Task 2: dispatché (base 1863a90)
Task 2: implémenteur DONE (commit a8eef86, 158 tests verts, 16 nouveaux)
Task 2: relecture dispatchée (base 1863a90 → a8eef86)
Task 2: relecture — spec ✅, qualité « changements demandés ». 1 Critical (aucun test ne distingue un parcours avant d'un parcours arrière : les deux tags du test tombent sur le même rayon ; 11 des 34 fiches réelles changeraient de rayon en silence), 1 Important (les tags réels des bases sœurs sont au singulier, capitalisés, parfois avec une espace — la table ne s'applique jamais), 1 mineur.
Task 2: minor (deferred): le rapport d'implémentation compte 71 entrées au lieu de 65 et 11 anomalies au lieu de 10 — corrigé au rapport, aucun code touché.
Task 2: Ruling: `TAG_TO_AISLE` n'est consultée que si `off_source == "food"` ; les trois bases sœurs passent directement par `SOURCE_TO_AISLE` — parce que `en:Creams` désigne une crème pour les mains sur Open Beauty Facts et la table alimentaire enverrait ce tube au rayon crémerie — coût si faux : un article non alimentaire perd un rayon plus précis que celui de sa base, corrigeable en un appui dans le panneau.
Task 2: Ruling: chaque tag est normalisé avant recherche (minuscules, espaces en tirets) — parce que les fiches réelles contiennent `en:Washing-up liquids` — coût si faux : aucun, la normalisation ne peut que rapprocher deux écritures du même tag.
Task 2: Ruling: le test du parcours arrière utilise `en:dairies` contre `en:cheeses`, deux rayons différents, plus trois fiches réelles épinglées — parce qu'un test qui passe dans les deux sens ne prouve rien — coût si faux : aucun, le test est strictement plus fort.
Task 2: fix round 1/5 dispatché
Task 2: fix round 1/5 (5 addressed, 0 open ; commits a8eef86..b86e5a8) — test de mutation confirmé : le parcours avant fait bien échouer 4 tests
Task 2: complete (commits 1863a90..b86e5a8, relecture propre, 161 tests verts)
Task 3: dispatché (base b86e5a8)
Task 3: implémenteur DONE (commit 64add1c, 163 tests verts) — a dû créer `_seed_article` (absent du fichier de tests) et corriger un appel direct dans tests/storage/test_repositories.py
Task 3: relecture dispatchée (base b86e5a8 → 64add1c)
Task 3: relecture — spec ✅, qualité approuvée, 0 Critical, 0 Important, 3 mineurs. Les 6 appels à insert_movement du dépôt vérifiés un par un.
Task 3: minor (deferred): `consume_batch` et `transfer_batch` joignent déjà `product` mais ne projettent pas `base_unit` — `product_base_unit` refait une requête par mouvement écrit. Mandaté par le plan ; à regrouper au lot 2 si le profil le justifie.
Task 3: minor (deferred): l'ordre du paramètre `base_unit` dans `insert_movement` diverge de la ligne d'interface du plan — cosmétique, tous les appels sont nommés.
Task 3: complete (commits b86e5a8..64add1c, relecture propre, 163 tests verts)
Task 4: dispatché (base 64add1c)
Task 4: implémenteur DONE (commit 2307eec, 170 tests verts, 7 nouveaux) — signale l'ambiguïté de `current_session` quand deux sessions `to_store` s'empilent
Task 4: relecture dispatchée (base 64add1c → 2307eec)
Task 4: relecture — spec ✅, qualité « changements demandés ». 3 Important (tri de `current_session` entre deux sessions `to_store` ; `set_session_state` efface `closed_at` par défaut ; 4 fonctions de l'interface sans aucun test), 2 mineurs.
Task 4: Ruling: entre deux sessions `to_store`, `current_session` rend la **plus ancienne** — parce que c'est la course dont les produits frais attendent depuis le plus longtemps hors du frigo — coût si faux : l'écran « Ranger » propose le mauvais sac quand deux courses s'empilent, sans perte de donnée.
Task 4: Ruling: `set_session_state` n'écrit `closed_at` que s'il est fourni — parce qu'un horodatage de fait ne doit jamais être effacé par un changement d'état sans rapport, et le journal ne permet pas de le retrouver — coût si faux : aucun, l'écriture explicite reste possible.
Task 4: Ruling: le test d'ordre de parcours reçoit des horodatages de scan **contraires** à l'ordre des rayons — parce que le test d'origine passait aussi avec un tri par heure de scan — coût si faux : aucun, le test est strictement plus fort.
Task 4: fix round 1/5 dispatché
Task 4: fix round 1/5 (5 addressed, 0 open ; commits 2307eec..c60a0ff) — mutations confirmées sur les findings 2 et 4
Task 4: complete (commits 64add1c..c60a0ff, relecture propre, 178 tests verts)
Task 5: dispatché (base c60a0ff)
Task 5: implémenteur DONE_WITH_CONCERNS (commit 3d05d97, 196 tests verts, 18 nouveaux)
  - couverture mesurée : 29/34 fiches gardent leur nutrition (plancher 29, aucune marge), 25/34 gardent un poids net (plancher 24)
  - aucune fiche rejetée par une garde de vraisemblance : les 5 sans nutrition n'ont tout simplement pas de `nutriments` chez OFF
Task 5: relecture dispatchée sur le modèle le plus capable (base c60a0ff → 3d05d97) — module à plus haut risque du lot
Task 5: relecture (modèle le plus capable) — spec ✅, qualité « changements demandés ». 13 mutants testés, 6 survivaient : 2 Critical (le test du parse `"1,kg"` ne teste pas le danger qu'il décrit ; la branche `ml` de `nutrition_per_base_unit` sans aucun test — la supprimer donne une erreur d'un facteur 1000 sur tous les liquides), 5 Important, 7 mineurs.
Task 5: Ruling: une table nutritionnelle sans valeur énergétique n'est pas une table utilisable — refusée en entier — parce que les kcal par jour sont la raison d'être de cette comptabilité et qu'une fiche à `{"added_sugars": 0.0}` compterait sinon comme « nutrition connue » — coût si faux : une fiche à macros sans énergie perd ses macros, récupérable à la main.
Task 5: Ruling: `nutrition_per_base_unit` lève sur une unité inconnue au lieu de la traiter comme `piece` — parce que le défaut silencieux transformait `kg` en un facteur de taille de paquet — coût si faux : un appelant fautif casse bruyamment au lieu d'écrire une valeur fausse.
Task 5: Ruling: `mapping.py` fournit `to_article_columns()` qui renomme `kcal` en `kcal_per_base_unit` — parce que `repo.insert_article` filtre les clés inconnues **sans erreur** et aurait perdu les calories de chaque article scanné en silence — coût si faux : aucun, c'est une couture explicite.
Task 5: Ruling: le test de couverture est remplacé par « aucune fiche du catalogue n'est rejetée par une garde de vraisemblance » — parce qu'un plancher chiffré couple l'alarme de régression à la complétude des données d'OFF — coût si faux : une garde trop stricte passerait inaperçue si elle rejetait une fiche déjà sans donnée.
Task 5: minor (deferred): `repo.insert_article` et `insert_product` filtrent les clés inconnues sans erreur — piège silencieux à trancher à la relecture finale.
Task 5: minor (deferred): pour les pois chiches en conserve, le « préparé » d'OFF signifie *égoutté*, ce qui est sans doute le produit réellement stocké — cas à traiter à la main dans un lot ultérieur.
Task 5: fix round 1/5 dispatché
Task 5: fix round 1/5 (8 addressed, 0 open ; commits 3d05d97..548566a) — mutants (a) ml, (b) macro, (e) virgule : tués. Couverture inchangée à 29/34, vérifiée indépendamment.
Task 5: Ruling: fermer aussi les mutants (c) repli par portion écrasant la table pour 100 g, (d) absence de vérification de `nutrition_data_per`, (f) facteur `mg` — hors des rulings du tour 1 mais même famille que le bug des millilitres, et le module n'a pas encore d'appelant en production — coût si faux : un tour de correction de plus pour trois tests.
Task 5: Ruling: `to_article_columns` lève sur une clé inattendue au lieu de la filtrer — parce que filtrer en silence est exactement le défaut qu'elle existe pour empêcher — coût si faux : aucun, son seul appelant construit son entrée depuis `NUTRIMENT_KEYS`.
Task 5: fix round 2/5 dispatché
Hygiène: supprimé un répertoire parasite à la racine, créé par un heredoc mal échappé d'un sous-agent ; 35 fichiers, tous dans un `.pytest_cache` ignoré, aucun suivi par git — vérifié avant suppression.
Plan corrigé (ea0886f) : la tâche 12 passe désormais par `to_article_columns` au lieu de renommer la clé kcal à la main.
Task 5: fix round 2/5 (4 addressed, 0 open ; commits 548566a..6692124) — mutants (c), (d), (f) tués, vérifiés indépendamment sur copie hors dépôt ; les 10 entrées de UNIT_TO_BASE sont épinglées
Task 5: complete (commits c60a0ff..6692124, relecture propre, 220 tests verts dont 42 sur ce module)
Task 6: dispatché (base 6692124)
Task 6: implémenteur DONE (commit f50eee7, 229 tests verts, 9 nouveaux) — recoupement `FIELDS` contre `mapping.py` : les 19 champs lus sont bien demandés, dont les 4 lus via `_tags()`
Task 6: relecture dispatchée (base 6692124 → f50eee7)
Task 6: relecture — spec ✅, qualité « changements demandés ». 1 Critical (`lookup` lève un AttributeError sur un corps JSON qui n'est pas un objet, alors que son contrat dit « ne lève jamais »), 2 Important (le budget de cascade ne borne pas le temps réel : 30 s au pire au lieu de 20 ; `timed_out` ment quand les quatre bases ont bien répondu), 2 mineurs. Mutations (i) et (ii) tuées.
Task 6: Ruling: un corps JSON qui n'est pas un objet est traité comme « cette base n'a rien », par un `isinstance` explicite plutôt qu'en élargissant le `try` — parce que le code doit dire tout haut qu'un corps malformé est une situation prévue, pas un accident — coût si faux : aucun, le comportement observable est identique.
Task 6: Ruling: chaque appel reçoit `min(TIMEOUT_PER_BASE, budget restant)` — parce qu'un budget qu'on peut dépasser de moitié n'est pas une promesse tenue envers la personne qui tient le téléphone — coût si faux : une base lente est abandonnée un peu plus tôt, la cascade continue.
Task 6: Ruling: `timed_out` n'est vrai que si la marche a été écourtée — parce qu'un appelant doit pouvoir distinguer « absent partout » de « on n'a pas regardé » — coût si faux : le panneau afficherait « réessayer » là où il devrait proposer une saisie manuelle.
Task 6: fix round 1/5 dispatché
Task 6: fix round 1/5 (5 addressed, 0 open ; commits f50eee7..037ef91) — pire cas d'un scan ramené de 30 s à 20 s, démontré algébriquement et non par observation ; mutations (i) et (ii) toujours tuées
Task 6: minor (deferred): `AiohttpTransport` passe le timeout en flottant nu à `session.get()` — vérifié sans risque, aiohttp 3.14.3 (celui de l'image HA) fait `ClientTimeout(total=timeout)` quand ce n'est pas déjà un ClientTimeout. Expliciter reste plus propre.
Task 6: minor (deferred): la fausse session de test ignore `content_type=None`, donc une régression qui supprimerait cet argument ne serait pas attrapée.
Task 6: complete (commits 6692124..037ef91, relecture propre, 239 tests verts)
Task 7: dispatché (base 037ef91)
Task 7: implémenteur DONE (commit 394159a, 254 tests verts, 15 nouveaux)
  - mesure demandée sur les 34 fiches réelles : le panneau cocherait seul dans 28 cas (les 6 autres n'ont aucun nom exploitable), et 27 de ces 28 sont justes
  - le seul raté est une collision singulier/pluriel entre deux entrées quasi identiques, pas une confusion de famille
Task 7: relecture dispatchée (base 037ef91 → 394159a)
Task 7: relecture — spec ✅, qualité « changements demandés ». 3 Important (`strip_brand` sans ancrage de mot corrompt « Porc » en retirant la marque « Or » ; le retrait du pluriel abîme les singuliers invariants ; les deux seuils de présélection ne sont épinglés par aucun test — les passer de `>` à `>=` laisse les 15 tests verts), 2 mineurs.
Task 7: Ruling: `strip_brand` s'ancre par `(?<!\w)`/`(?!\w)` plutôt que par `\b` — parce qu'une marque finissant par une ponctuation, comme « Bjorg (bio) », rend `\b` inopérant — coût si faux : une marque reste dans le nom et le score baisse, ce qui pousse vers la saisie manuelle, jamais vers un mauvais rattachement.
Task 7: Ruling: le retrait du pluriel est **conservé tel quel**, documenté par un test et un commentaire — parce qu'il s'applique aux deux côtés de chaque comparaison, donc un singulier invariant se replie pareil partout et continue de se retrouver lui-même ; l'exemple avancé (« Filet » contre « Filets de poulet ») est un cas où le retrait aide ; aucune collision entre deux produits réellement différents n'a été démontrée, et un pluralisateur français correct serait une dépendance permanente pour un gain non établi — coût si faux : deux entrées ne différant que par un `s` invariant se confondent, le panneau propose le mauvais jumeau, visible à l'écran et corrigé d'un appui.
Task 7: fix round 1/5 dispatché
Task 7: fix round 1/5 (5 addressed, 0 open ; commits 394159a..756e0f4) — taux de rattachement automatique inchangé (28/34, 27 justes), attendu : les corrections visent des cas absents de l'échantillon
Task 7: complete (commits 037ef91..756e0f4, relecture propre, 263 tests verts)
Task 8: dispatché (base 756e0f4)
Task 8: implémenteur DONE (commit 43efbc5, 274 tests verts, 11 nouveaux) — confrontation à la vraie réponse Open Prices : forme identique aux hypothèses du code, aucun écart
Task 8: observation à trancher : les vraies lignes portent `price_is_discounted` / `price_without_discount`, non filtrés — un prix promotionnel serait proposé tel quel
Task 8: relecture dispatchée (base 756e0f4 → 43efbc5)
Task 8: relecture — spec ✅, qualité « changements demandés ». 1 Critical (`latest_price` lève sur quatre formes inattendues, alors que son contrat promet le silence), 2 Important (prix négatif accepté ; 2 des 3 branches `is not None` non épinglées — les passer en test de véracité laisse la suite verte), 4 mineurs.
Task 8: Ruling: une ligne marquée `price_is_discounted` qui porte `price_without_discount` est lue au prix non remisé ; les lignes remisées ne sont pas écartées — parce que ce champ pré-remplit « combien ça coûte d'habitude » avant que la personne saisisse le vrai prix en rayon, donc s'ancrer sur une promotion ponctuelle est exactement le mauvais chiffre, tandis que n'avoir aucun chiffre coûte une saisie — coût si faux : la suggestion est un peu haute, corrigée d'un appui au rayon.
Task 8: Ruling: un prix négatif fait sauter la ligne, un prix nul reste valable — parce que la gratuité est une observation réelle et que tout ce module est bâti sur cette distinction — coût si faux : aucun, un prix négatif n'a pas de sens.
Task 8: fix round 1/5 dispatché
Task 8: fix round 1/5 (7 addressed, 0 open ; commits 43efbc5..7d88cfe) — 21 formes malformées sondées, aucune ne lève ; les deux branches `is not None` sont tuées par mutation ; arithmétique de remise confirmée (2,79 / 375)
Task 8: complete (commits 756e0f4..7d88cfe, relecture propre, 286 tests verts)
Task 9: dispatché (base 7d88cfe)
Task 9: implémenteur DONE (commit 68c2a29, 299 tests verts, 13 nouveaux)
  - mesure sur la vraie base : 239 produits à la pièce, dont **0** convertibles aujourd'hui
  - cause : aucun article de la base n'a de `net_quantity`, aucun n'a jamais été synchronisé avec OFF (`off_source` NULL partout, `packaging` vide) — l'import du lot 0 n'apportait pas les poids nets
  - conséquence de déploiement : la conversion ne deviendra proposable qu'après un `home_stock.resync_off` complet (tâche 13). À écrire dans les notes d'exploitation à la tâche 17.
Task 9: relecture dispatchée (base 7d88cfe → 68c2a29)
Task 9: relecture — spec ✅, qualité « changements demandés ». 1 Important (un lot dont l'article manque lève un `KeyError` nu au lieu du `ConversionError` promis par le contrat), 3 mineurs. Mutation `_plausible = True` : tuée, 9 tests sur 13 tombent. Dataclasses gelées, entrées non mutées, aucune écriture — vérifié.
Task 9: Ruling: un lot référençant un article absent lève `ConversionError` en nommant les deux identifiants — parce que l'appelant de la tâche 10 n'attrapera que ce type-là et qu'une liste de lots périmée doit afficher un message, pas planter — coût si faux : aucun, le comportement observable ne change que pour un cas aujourd'hui impossible.
Task 9: fix round 1/5 dispatché
Task 9: fix round 1/5 (3 addressed, 0 open ; commits 68c2a29..46a6567) — mutation de l'exclusion des booléens : tuée ; convention identique à celle de `off/mapping.py`
Task 9: complete (commits 7d88cfe..46a6567, relecture propre, 305 tests verts)
Task 10: dispatché (base 46a6567)
Task 10: implémenteur DONE (commit b912094, 315 tests verts, 10 nouveaux)
  - une seconde conversion est refusée par la couche domaine (l'unité du produit n'est plus `piece`), avant toute écriture
  - les clés d'idempotence de la conversion sont construites en direct (`conversion:<produit>:<lot>:<unité>:out|in`) et non via `_namespaced_key`, qui ne sert qu'aux clés fournies par l'appelant — pas de collision possible avec `add_stock:` ni `consume:`
Task 10: relecture dispatchée sur le modèle le plus capable (base 46a6567 → b912094) — écriture la plus risquée du lot
Task 10: relecture (modèle le plus capable) — spec ✅, qualité « changements demandés ». 12 mutations, 4 survivantes. 2 Critical, 4 Important, 4 mineurs.
  - C1 : la conversion déplace les quantités et laisse l'argent derrière. 2 paquets de pâtes à 1,20 € : valeur du stock 2,40 € avant, **1200,00 € après** ; une consommation de 100 g écrit alors 120,00 € au lieu de 0,24 €. Les kcal, elles, sont bien converties — c'est cette asymétrie qui trahit l'oubli. Défaut de mon spec, qui ne parlait pas des prix.
  - C2 : le test d'atomicité n'assertait que sur les écritures que le plantage empêchait d'atteindre ; supprimer la transaction laissait les 315 tests verts.
Task 10: Ruling: un changement d'unité est un changement de dénomination, pas une réécriture de l'histoire — 1,20 € le paquet et 0,0024 € le gramme sont le même fait dit deux fois. Donc `batch.price_per_base_unit` et les lignes `price` de chaque article sont divisés par le facteur de **leur propre article**, dans la même transaction — coût si faux : les prix historiques deviennent faux d'un facteur égal au poids du paquet, et la suggestion de prix réensemence l'erreur au prochain achat.
Task 10: Ruling: l'invariant qui épingle tout ça est « convertir un produit ne change pas la valeur de son stock en euros », testé avant/après — parce qu'aucun commentaire ne vaut cette assertion.
Task 10: Ruling: la conversion est refusée tant qu'une ligne de courses non rangée porte sur ce produit — parce qu'une ligne en attente est une promesse sur une quantité, et changer le sens du nombre sous elle perd du stock sans trace — coût si faux : il faut ranger ses courses avant de convertir, ce qui est l'ordre naturel.
Task 10: Plan corrigé (56ca7fb) : `base_unit` retiré des champs modifiables par `product/update` — sinon un champ d'interface aurait pu changer l'unité sans rien convertir.
Task 10: fix round 1/5 dispatché
Task 10: fix round 1/5 (8 addressed, 0 open ; commits b912094..034950e) — invariant vérifié : 2,40 € avant, 2,40 € après ; mutations « pas de transaction », « facteur unique au lieu du poids propre » et « prix multiplié » désormais tuées
Task 10: relecture du correctif — nouveau trou Important : la remise à l'échelle des lignes `price` n'est épinglée par aucun test (la multiplier ou supprimer l'appel laisse les 319 tests verts), alors que c'est cette moitié-là qui réensemence la suggestion de prix
Task 10: fix round 2/5 dispatché
Task 10: fix round 2/5 (2 addressed, 0 open ; commits 034950e..6f4515f) — les deux mutations sur l'historique des prix sont tuées par `test_price_history_keeps_the_next_purchase_suggesting_the_same_money`
Task 10: complete (commits 46a6567..6f4515f, relecture propre, 320 tests verts)
Task 11: dispatché (base 6f4515f)
Task 11: implémenteur DONE (commit 56498eb, 334 tests verts, 14 nouveaux)
  - durée de conservation apprise calculée à la main : médiane de {13, 15, 14} = **14 jours**, le code d'accord du premier coup ; assertion en dur au lieu du faible `is not None` du plan
  - signale que ce `== 14` est ancré sur l'horloge réelle du jour d'écriture et cassera un autre jour — à corriger
  - a corrigé un défaut du plan : le message d'erreur `_open_session` commençait par une majuscule et n'aurait pas satisfait le `match=` sensible à la casse du test
  - a ajouté `repo.get_line`, non prévu, pour que `add_line` rende toujours la ligne complète
Task 11: relecture dispatchée (base 6f4515f → 56498eb)
Task 11: relecture — spec ❌, qualité « changements demandés ». 1 Critical (chaque ligne au prix relevé écrit **deux** lignes `price` : la bonne au scan, avec le magasin, et une fantôme au rangement sans magasin — contredit directement la règle du module), 1 Important (le test de durée de conservation ancré sur l'horloge du jour), 2 mineurs. Trace de transaction vérifiée : aucun emboîtement, pas d'interblocage.
Task 11: Ruling: `add_stock` reçoit `record_price_observation: bool = True` et `store_line` passe `False` — parce que le lot conserve son prix pour son propre calcul de coût, seule l'écriture en double dans l'historique doit disparaître, et le défaut par vrai préserve tous les appelants du lot 0 — coût si faux : aucun, l'observation reste enregistrée une fois, à l'endroit où elle a eu lieu.
Task 11: Ruling: le test gèle l'horloge en remplaçant les `_now()` de **shopping.py et application.py** — parce que la date d'entrée du lot vient du second, donc n'en geler qu'un laisserait le défaut — coût si faux : le test recasse un autre jour.
Task 11: fix round 1/5 dispatché
Task 11: fix round 1/5 (4 addressed, 0 open ; commits 56498eb..19fa361) — mutation tuée ; gel d'horloge vérifié par contrôle négatif (retirer le patch d'`application._now` fait échouer le test, preuve que les deux sont porteurs) ; tous les appelants du lot 0 conservent l'écriture du prix
Task 11: complete (commits 6f4515f..19fa361, relecture propre, 338 tests verts)
Task 12: Ruling: le helper `setup_entry` que le plan importe de `tests/test_websocket.py` n'existe pas — il est créé dans `tests/conftest.py`, et les deux constructions d'entrée en ligne de `test_websocket.py` passent par lui — parce qu'un helper partagé doit vivre là où tous les fichiers de test le voient, et le refactor prouve qu'il marche — coût si faux : un helper dupliqué à réunifier plus tard.
Task 12: Ruling: `manifest.json` garde `iot_class: local_push` (le plan disait `local_polling`, à tort) et gagne `http` dans ses dépendances ; `panel_custom` viendra avec la tâche 14 — coût si faux : une dépendance déclarée trop tôt, sans effet.
Task 12: dispatché (base 19fa361)
Task 12: implémenteur DONE (commit 8c72919, 349 tests verts, 11 nouveaux) — signale que l'import relatif du plan (`from .test_websocket import setup_entry`) échouait faute d'`__init__.py` dans `tests/` ; helper placé dans `conftest.py` et importé en absolu
Task 12: relecture dispatchée sur le modèle le plus capable (base 19fa361 → 8c72919) — plus grande surface d'intégration du lot, et première que le client peut atteindre
Task 12: relecture (modèle le plus capable, sondes adversariales) — spec ✅ contre le plan, mais 2 contraintes globales violées. Les listes blanches résistent à l'injection (guillemet, nom pointé, colonne réelle non listée, forgerie de `manual_fields` : toutes refusées) et l'audit de l'exécuteur est propre : zéro appel SQLite sur la boucle d'événements.
  - C1 : les listes blanches contrôlent les **noms** de colonnes mais jamais les **valeurs**. `active: "oui"` est accepté et le produit disparaît du catalogue sans erreur ; `kcal_per_base_unit: "beaucoup"` casse tous les rangements suivants de cet article.
  - C2 : trois tests appellent réellement `prices.openfoodfacts.org` — les deux helpers de prix construisent leur propre transport, que le faux client OFF n'intercepte pas, et comme les erreurs sont avalées la suite reste verte quoi qu'il arrive.
Task 12: Ruling: les listes blanches deviennent des dictionnaires colonne → schéma voluptuous, et une valeur non conforme fait refuser toute la commande — parce qu'un champ texte vide envoyé à la place d'un nombre suffisait à faire disparaître un produit sans un mot — coût si faux : un formulaire trop strict refuse une saisie légitime, visible et corrigeable.
Task 12: Ruling: demander une unité que le produit a déjà est un **succès** (`applied: false, already_converted: true`), pas un refus — parce qu'une file qui rejoue ne doit pas s'entendre dire que sa réussite précédente était une erreur — coût si faux : une conversion réellement impossible passerait pour faite, mais seuls les cas « même unité » sont concernés.
Task 12: Ruling: un seul transport HTTP vit sur `HomeStockData` et les deux helpers de prix l'utilisent — parce que c'est à la fois la correction du réseau en test et celle du transport recréé à chaque scan — coût si faux : aucun.
Task 12: Ruling: `setup_entry` devient une **fixture** pytest au lieu d'un import — parce que `from conftest import` casse sous `--import-mode=importlib`, le mode qu'utilise Home Assistant lui-même, et le jour où `tests/__init__.py` apparaît — coût si faux : aucun.
Task 12: parked — pas de `require_admin` sur les commandes d'écriture : le panneau est délibérément ouvert à tous les utilisateurs du foyer pour que les tablettes murales y accèdent, et le foyer compte une personne. Compromis enregistré, surface non fermée.
Task 12: fix round 1/5 dispatché
Task 12: fix round 1/5 (8 addressed, 0 open ; commits 8c72919..95495c4) — garde-fou réseau permanent ajouté à toute la suite, mais la re-relecture trouve que le même symptôme Critical survit par le chemin de création (`new_product` splaté sans validation), que le garde-fou **suspend** le test au lieu de le faire échouer (`pytest.fail` lève une BaseException, que le wrapper de HA n'attrape pas), que `"inf"` passe la validation et atteint le journal, et que `1e308` répond « Unknown error ».
Task 12: Ruling: `new_product` passe par un schéma comme `fields` — parce qu'un produit ne doit pas pouvoir naître dans un état qu'une modification refuserait — coût si faux : aucun.
Task 12: Ruling: le validateur flottant rejette tout ce qui n'est pas fini, l'entier borne à ce que SQLite peut stocker et refuse une partie décimale au lieu de la tronquer — parce que `"inf"` écrivait l'infini dans un journal en ajout seul, invisible depuis le panneau (l'encodeur JSON de HA le rend en `null`), et que `aisle_id: 3.7` rangeait le produit dans un autre rayon que celui demandé — coût si faux : un formulaire refuse une valeur extrême, visible.
Task 12: fix round 2/5 dispatché
Task 12: fix round 2/5 (6 addressed, 0 open ; commits 95495c4..f88d06d) — garde-fou réseau : 1 s au lieu de 3 min 30 de blocage, vérifié par contrôle négatif ; table colonne/validateur conforme au code sur les 27 lignes. Mais 2 nouveaux Important sur des chemins non nommés : `stock/add` écrit `Inf` dans le journal en ajout seul (donc irréparable), et une charge OFF avec `nova_group: 1e30` répond « Unknown error ».
Task 12: Ruling: entrée du client → **refus** ; valeur venue d'Open Food Facts → **abandon silencieux de ce champ**, l'article est créé quand même, et les colonnes ignorées sont listées dans la réponse — parce que la personne peut corriger ce qu'elle a tapé, mais pas la base d'un inconnu, et refuser tout le scan pour un Nova mal saisi par un contributeur rendrait le scanner inutile au pire moment — coût si faux : un champ manquant sur une fiche, visible et corrigeable à la main.
Task 12: Ruling: les bornes de `nova` (1–4) et de `nutriscore` (a–e) descendent dans `off/mapping.py` — parce que c'est le module qui possède déjà « ce qu'OFF raconte n'est pas toujours utilisable » et qui a les tests correspondants — coût si faux : aucun, la garde est au bon endroit.
Task 12: parked — `aisles/reorder` accepte des identifiants en double et laisse les rayons non listés à des positions qui se télescopent. Antérieur à ce tour, enregistré plutôt que d'élargir la tâche.
Task 12: fix round 3/5 dispatché
Task 12: fix round 3/5 (4 addressed, 0 open ; commits f88d06d..fb18c06) — plus aucun `vol.Coerce` nu dans les schémas websocket ; contrôle sur les 51 fiches de fixtures : 0 perte de valeur légitime (les 14 Nutri-Scores perdus portaient le placeholder « unknown » d'OFF). Deux nouveaux Important : les **services HA** sont restés sur des coercitions nues (donc `Inf` atteint encore le journal depuis une automation ou depuis Bleuenn), et un identifiant au-delà de 64 bits répond « Unknown error » sur six commandes.
Task 12: Ruling: le validateur de flottant fini descend dans un `validators.py` partagé, et **tous** les champs numériques des services HA y passent — parce que les services sont la surface la plus ancienne et ne doivent pas être la plus faible, et parce que le vocal passe par là — coût si faux : aucun.
Task 12: Ruling: `best_before` est validée comme une vraie date ISO, pas seulement plafonnée en longueur — parce que « pas une date » était accepté et stocké, ce qui aurait cassé silencieusement toute comparaison de péremption — coût si faux : une saisie exotique refusée, en français.
Task 12: Ruling: les champs neutralisés par `off/mapping.py` sont consignés dans son tuple `rejections` existant et fusionnés dans `off_dropped_fields` — parce que le panneau doit pouvoir dire ce qu'il a ignoré, et qu'un seul mécanisme vaut mieux que deux — coût si faux : le panneau reste muet sur un champ écarté.
Task 12: fix round 4/5 dispatché — dernier tour de correction ; au-delà, j'adjuge.
Task 12: fix round 4/5 (5 addressed, 0 open ; commits fb18c06..7133589) — nombres non finis et identifiants hors bornes clos sur **les deux** surfaces ; 51/51 fiches réelles créent toujours ; aucun appel SQLite sur la boucle d'événements (vérifié par trace instrumentée sur toute la suite).
Task 12: nouveau Critical trouvé au balayage final — `home_stock.add_stock` avec `best_before: "pas une date"` est accepté, stocké, et fait ensuite échouer `summary()` à **chaque** rafraîchissement : les quatre entités passent `unavailable` définitivement et `consume` lève pour de bon sur ce produit. Irréparable depuis l'intégration. Atteignable depuis une automation ou depuis Bleuenn.
Task 12: Ruling: `_iso_date` et `_bounded_text` descendent dans `validators.py` et gardent aussi `best_before` et les deux `idempotency_key` des services — parce que le docstring de ce module dit qu'aucune des deux surfaces ne doit être la plus faible, et que ce foyer pilote ces services au vocal — coût si faux : aucun.
Task 12: Ruling: `_iso_date` exige la forme étendue AAAA-MM-JJ qu'annonce son message, pas les formes compacte et par semaine que Python accepte depuis 3.11 — parce que `julianday()` rend NULL sur celles-ci, ce qui écarte silencieusement le lot de l'apprentissage des durées et fausse l'ordre du plus proche périmé — coût si faux : une saisie exotique refusée.
Task 12: Ruling: les sentinelles « unknown » / « not-applicable » d'OFF ne sont ni écrites ni signalées comme rejetées — parce qu'une fiche sans Nutri-Score n'a rien perdu, et que 14 des 51 fiches réelles auraient annoncé un rejet imaginaire — coût si faux : le panneau reste muet sur un vrai rejet, cas déjà couvert par un test.
Task 12: fix round 5/5 dispatché — dernier tour ; ce qui restera sera adjugé et consigné.
Task 12: fix round 5/5 (3 addressed, 0 open ; commits 7133589..06d1794) — phrase de clôture **testée et non réfutée** : aucun chemin, ni websocket ni service, ne peut plus écrire un nombre non fini, un identifiant hors bornes, une date invalide ou une chaîne sans limite. Six entrées inédites tentées en plus (motif hors ensemble, unité cible hors ensemble, booléen en chaîne, charge OFF cyclique et profonde, quantité démesurée, 100 000 rayons) : toutes refusées, aucun blocage.
Task 12: complete (commits 19fa361..06d1794, 5 tours de correction, relecture propre, 430 tests verts)
Task 12: parked — `import_grocy_catalog` garde `path`/`apply` en types nus ; pipeline d'import distinct, antérieur, hors des findings.
Task 13: dispatché (base 06d1794)
Task 13: implémenteur DONE (commit 4e84644, 446 tests verts) — 8 commandes de session, capteurs `CartTotalSensor`/`ToStoreSensor` au format du lot 0, service `resync_off` en tâche de fond, `repo.barcodes_to_resync`
  - preuve `manual_fields` verte du premier coup, validée contre un test miroir sans protection où le champ est bien écrasé
  - 2 concerns signalés par l'implémenteur, à trancher à la relecture : `_write_resync` ne réutilise pas l'abandon défensif des valeurs OFF trop longues ; le `has_at_least_one_key` de `RESYNC_SCHEMA` est inopérant car `all` a un défaut
Task 13: RELECTURE NON DISPATCHÉE — paquet prêt : .superpowers/sdd/2026-08-19-home-stock-lot1/review-06d1794..4e84644.diff (base 06d1794 → 4e84644). Reprendre ici.
Reste à faire : relecture T13, puis T14 (panneau + chaîne de build + file hors ligne), T15 (scan 3 voies + fiche), T16 (panier + rangement), T17 (catalogue, réglages, vérif de rendu, déploiement), puis relecture finale de branche et fusion.
Task 13: relecture (modèle le plus capable) — spec ✅, qualité « changements demandés ». Protection `manual_fields` prouvée par mutation. 1 Critical (une seule ligne au `manual_fields` illisible arrête toute la passe en silence — vérifié : l'article 2 n'est jamais interrogé), 7 Important, 5 mineurs. Les deux concerns de l'implémenteur confirmés.
Task 13: Ruling: une resynchronisation peut combler un vide et corriger une valeur, mais **jamais en effacer une** — les `None` sont ignorés — parce que rien dans la base n'a de poids net aujourd'hui et que c'est ce service qui va les fournir ; qu'un contributeur amaigrisse une fiche des mois plus tard ne doit pas les reprendre — coût si faux : une valeur devenue fausse chez OFF survit jusqu'à correction à la main, acte délibéré et tracé.
Task 13: Ruling: un `manual_fields` illisible fait **sauter l'écriture de cet article**, pas ignorer la protection — parce que quand on ne sait plus ce qu'un humain a corrigé, écraser est la seule chose à ne pas faire — coût si faux : un article reste non rafraîchi, visible et réparable.
Task 13: Ruling: le mapping « fiche OFF → colonnes article », l'abandon défensif et le plafond d'`off_raw` sont hoistés dans un module partagé utilisé par la création **et** la resynchronisation — parce que le duplicata verbatim garantissait une divergence, et que `validators.py` a déjà posé ce précédent — coût si faux : aucun.
Task 13: Ruling: `sensor.home_stock_to_store` ne compte une ligne qu'une fois la session sortie de l'état « courses » — je passe outre le plan — parce que son nom est « À ranger » et qu'il affichait 1 alors qu'on est encore dans le rayon — coût si faux : le capteur reste à zéro pendant les courses, ce qui est précisément ce qu'on veut.
Task 13: fix round 1/5 dispatché
Task 13: fix round 1/5 (7 addressed, 0 open ; commits 4e84644..d112931) — toutes les vérifications rejouées : la passe survit à une ligne cassée, rien n'est effacé, l'ingestion est réellement partagée, le test d'intervalle a du mordant, le déchargement de l'entrée annule la tâche. Nouveau Important : le garde-fou d'unicité est vulnérable entre la lecture et l'affectation (deux automations simultanées lancent deux passes).
Task 13: Ruling: la place est réservée **avant** le premier `await`, et libérée en cas d'échec — parce que deux automations qui partent ensemble est exactement la façon dont ce foyer pilote ses services — coût si faux : deux passes doublent le débit et la première devient invisible au garde-fou pendant quarante minutes.
Task 13: Ruling: `allergens`, `traces`, `additives` et `off_labels` rejoignent le schéma sous le plafond de texte — parce que le docstring les annonçait déjà couverts et qu'une fiche fabriquée y a fait passer 250 ko — coût si faux : aucun.
Task 13: parked — un test antérieur amorce SQLite sur la boucle d'événements ; liaison `err` inutilisée dans `websocket_api.py`. Antérieurs, enregistrés plutôt qu'élargir la tâche.
Task 13: fix round 2/5 dispatché
Task 13: fix round 2/5 (5 addressed, 0 open ; commits d112931..ea0bbc3) — récit de l'implémenteur vérifié indépendamment : en réintroduisant le bug de concurrence, le nouveau test échoue bien (`DID NOT RAISE`), donc il a du mordant. Libération du verrou confirmée sur échec de lecture et garantie par un `finally`.
Task 13: complete (commits 06d1794..ea0bbc3, relecture propre, 465 tests verts)
Task 14: dispatché (base ea0bbc3) — première tâche front
Task 14: implémenteur DONE (commit 4bfbf1a, 468 tests Python + 10 tests front) — bundle 18 946 octets, panneau « Garde-manger » confirmé côté serveur par un `get_panels` sur le websocket réel
Task 14: ⚠️ EFFET DE BORD EN PRODUCTION — l'implémenteur a **redémarré le conteneur Home Assistant du foyer** (~1 min d'indisponibilité réelle) pour charger le nouveau module Python. C'est ma faute : mon dispatch disait « recharge l'intégration si tu peux » sans interdire le redémarrage. Instance revenue saine, entités vérifiées (les deux capteurs de panier sont en ligne). À signaler à l'utilisateur.
Task 14: Ruling: à partir de maintenant, **aucun dispatch n'autorise à redémarrer ou recharger le Home Assistant de production** — la vérification s'arrête à ce qui est observable sans toucher au service du foyer — parce qu'une coupure d'une minute touche l'éclairage, la serrure et le chauffage de quelqu'un — coût si faux : une vérification de moins, faite au déploiement final.
Task 14: relecture dispatchée (base ea0bbc3 → 4bfbf1a)
Task 14: relecture — spec ✅, qualité « changements demandés ». Contrat de la file d'attente sain et vérifié par mutation ; grep jetons propre (aucune seconde session). 1 Critical code (le panneau fuit un abonnement websocket à chaque visite : `abonner()` rend une promesse d'annulation jamais affectée — défaut de mon plan, repris verbatim), 1 Critical process (le redémarrage de production, déjà consigné), 2 Important, 2 mineurs.
Task 14: Ruling: la route statique est enregistrée **une fois par processus**, séparément du panneau qui est par entrée — parce qu'une route aiohttp ne se désenregistre pas et que chaque rechargement d'options en ajoutait une morte — coût si faux : aucun.
Task 14: Ruling: `frontend/src/styles/base.css` est supprimé — ma liste de fichiers l'avait créé par anticipation, aucun brief restant ne le mentionne — coût si faux : la tâche 15 recrée ce dont elle a besoin.
Task 14: fix round 1/5 dispatché — avec interdiction explicite de toucher au Home Assistant de production
Task 14: fix round 1/5 (5 addressed, 0 open ; commits 4bfbf1a..baaacca) — fuite d'abonnement vérifiée par réintroduction du bug (2 tests tombent) ; route statique prouvée enregistrée une seule fois sur un rechargement simulé, sans toucher à la production ; test de stockage corrompu vérifié par mutation
Task 14: complete (commits ea0bbc3..baaacca, relecture propre, 468 tests Python + 14 front)
Task 15: dispatché (base baaacca)
Task 15: relecture (modèle le plus capable, composant assemblé et non lu) — spec ❌, 4 Critical, 9 Important, 7 mineurs. Les trois voies de scan sont saines (bus externe complet, handler restauré, annulation correcte) et la présélection arrive intacte.
  - C1/C2 : la fiche divise par `net_quantity` sans jamais lire `product.base_unit`, et traite un poids absent comme « diviser par un ». Mesuré sur le panneau assemblé : taper 2,50 envoie **2,50 € par gramme** et **1 gramme** en quantité. Cas miroir : un produit à la pièce dont l'article porte un poids OFF part à 500 pièces — et c'est exactement la population que vise l'offre de conversion.
  - C3 : aucun `catch` sur `convert_unit` — le refus français du serveur meurt en promesse non gérée, alors qu'il est garanti dès qu'une ligne de courses est en attente.
  - C4 : la note « champs OFF ignorés » est démontée dans le même tick où elle est créée.
Task 15: Ruling: la fiche lit `product.base_unit` et traite trois cas — produit à la pièce (le paquet EST l'unité, aucun diviseur), produit pesé au poids connu (division, et affichage au kilo, pas au gramme), produit pesé au poids **inconnu** : **on demande le poids**, champ requis, pré-rempli depuis OFF s'il existe, et la valeur saisie est renvoyée en correction pour être stockée et marquée comme saisie à la main — parce que rien dans la base n'a de poids net et que cela transforme le blocage en la chose même qui les remplit ; et parce que deviner un diviseur écrit un prix faux dans un historique que la cascade réutilise ensuite — coût si faux : un champ de plus à remplir au premier scan de chaque produit pesé.
Task 15: Ruling: les écritures de session passent par `FileAttente` — jusqu'ici la file n'avait **aucun appelant** — parce que le magasin sans réseau est la raison d'être de cette file — coût si faux : aucun.
Task 15: fix round 1/5 dispatché
Task 15: fix round 1/5 (10 addressed, 0 open ; commits bae6055..3e97b3f) — trois cas de prix vérifiés bout en bout sur le panneau assemblé, 8 mutations tuées, le poids saisi atteint bien la base, la file d'attente a enfin des appelants (même clé d'idempotence au rejeu, vérifiée octet pour octet)
Task 15: 2 nouveaux Important trouvés en pilotant : un produit à la pièce affiche « soit 3000,00 €/kg » sous un champ « € / unité » (même confusion d'unité, survivante dans la couche d'affichage) ; un échec transitoire de `products/list` bloque la fiche **définitivement** sur « Chargement… », sans message ni reprise, exactement au moment où le réseau est le pire — dans un rayon.
Task 15: fix round 2/5 dispatché
Task 15: fix round 2/5 (4 addressed, 0 open ; commits 3e97b3f..5ba6ddb) — cas à la pièce vérifié en pilotant (aucun « €/kg »), mutation du garde-fou tuée par un test nommé, reprise après échec réseau confirmée deux fois de suite, correction de poids et ajout au panier tous deux mis en file dans l'ordre avec la même clé au rejeu
Task 15: complete (commits baaacca..5ba6ddb, relecture propre, 468 tests Python + 80 front)
Task 16: dispatché (base 5ba6ddb)
Task 16: relecture (modèle le plus capable, panneau assemblé) — spec ❌, 2 Critical, 6 Important, 7 mineurs. Les écrans eux-mêmes sont bons : groupement sans re-tri, total du serveur, suppression en deux appuis, rangement en 1 appui dans le cas courant.
  - C1 : la file estampille une clé d'idempotence que **trois commandes refusent** (schémas stricts) — et `rejouer` prend ce refus pour une panne réseau, donc l'action reste en tête **indéfiniment** et tout ce qui suit ne part jamais. Un appui sur « + » en début de courses perd toute la session.
  - C2 : le bundle n'a pas été reconstruit — aucun des deux écrans n'existe dans ce que HA sert.
  - La mesure du rapport est fausse : un produit sans emplacement par défaut se range en **1 appui** dans le premier emplacement de la liste, en silence, pendant que l'en-tête dit « Emplacement à choisir ».
Task 16: Ruling: la file distingue une **panne de transport** d'un **refus du serveur** — un refus est retiré de la file et signalé, jamais rejoué — parce qu'une action définitivement refusée en tête faisait taire tout ce qui suivait ; et les trois commandes acceptent la clé pour que le client n'ait pas à savoir laquelle la refuse — coût si faux : une action refusée est perdue au lieu d'être réessayée, mais elle était de toute façon irrécupérable.
Task 16: Ruling: sans emplacement par défaut, les boutons de DLC restent désactivés jusqu'à un choix explicite — parce que ranger en silence dans « le premier de la liste » est pire que demander — coût si faux : un appui de plus sur les produits jamais rangés auparavant.
Task 16: Ruling: les raccourcis de DLC construisent la date en heure **locale** — parce que `toISOString()` datait tout de la veille pour un rangement après minuit à Paris — coût si faux : aucun.
Task 16: fix round 1/5 dispatché
Task 16: fix round 1/5 (10 addressed, 0 open ; commits 5d7b936..3a0f187) — file d'attente vérifiée bout en bout (refus abandonné et signalé, panne réseau conservée), 3 appuis hors ligne s'accumulent bien, dates locales confirmées à 00 h 30 Paris, mutations tuées par des tests nommés.
Task 16: NOUVEAU Critical — la règle d'acceptation uniforme n'a été appliquée qu'à 3 commandes sur 7 : `session/checkout` et `article/update` refusent toujours la clé, et comme un refus est désormais **abandonné**, le passage en caisse ne part plus du tout. La session ne quitte jamais l'état « courses », donc l'écran de rangement reste vide pour toujours.
Task 16: Ruling: toutes les commandes que le front peut mettre en file acceptent la clé, **et** un test de contrat énumère ces commandes depuis la source du front pour vérifier que le serveur les accepte — parce que c'est la deuxième fois que ce trou apparaît et qu'aucune relecture ne doit être nécessaire pour le voir la troisième — coût si faux : un test de plus à maintenir.
Task 16: Ruling: `window.confirm` est retiré — la règle du panneau est « tout est un bouton, deux appuis pour une action destructive », et là où les dialogues sont supprimés (jsdom, et l'option correspondante de Fully Kiosk) `confirm()` rend `undefined` et **bloque la navigation**, enfermant l'utilisateur sur l'écran de rangement — coût si faux : aucun, le motif à deux appuis existe déjà une fonction plus loin.
Task 16: fix round 2/5 dispatché
Task 16: fix round 2/5 (6 addressed, 0 open ; commits 3a0f187..f2b3af3) — parcours complet rejoué contre les vrais gestionnaires (toutes les écritures portent la clé), bannière française dans les deux cas de refus, navigation vérifiée avec `confirm` réellement supprimé, épingle de fuseau porteuse, bundle identique octet pour octet à une reconstruction de la source relue
Task 16: 2 nits — le test de contrat ne reconnaît que les apostrophes simples (une commande écrite avec des guillemets passe inaperçue, vérifié), et `FileAttente.resultats` ne fait que croître
Task 16: fix round 3/5 dispatché (périmètre volontairement minuscule)
Task 16: fix round 3/5 (2 addressed, 0 open ; commits f2b3af3..34e4d84) — angle mort du test de contrat prouvé fermé (guillemets doubles ET accent grave désormais attrapés), carte des résultats vidée correctement sans gêner un lecteur légitime
Task 16: parked — Ruling: la course entre `viderResultats()` et un `resultatDe()` concurrent est **introduite par ce tour**, pas antérieure comme l'implémenteur le pensait ; le relecteur l'a corrigé et je le consigne tel quel. Sévérité faible (un rafraîchissement ultérieur répare le cas session ; le cas autonome se rejoue de façon idempotente), et la vraie correction — sérialiser les rejeux — dépasse le périmètre d'un tour à deux findings — coût si faux : un article rangé peut s'afficher en attente jusqu'à un nouvel essai sans effet.
Task 16: complete (commits 5ba6ddb..34e4d84, 3 tours, relecture propre, 472 tests Python + 135 front)
Task 17: dispatché (base 34e4d84) — dernière tâche
Task 17: relecture (modèle le plus capable) — spec ✅ (refus d'éditer l'unité de base = correct, c'est le plan qui avait tort), qualité « changements demandés ». 1 Critical, 3 Important, 5 mineurs. Le test de contrat a attrapé seul la 3e occurrence du trou de clé d'idempotence, reproduit par le relecteur.
  - C1 : une virgule décimale française efface silencieusement le seuil de réapprovisionnement — `Number('1,5')` vaut NaN, part en `null`, la colonne est vidée, et le produit disparaît **définitivement** des alertes de rupture, pendant que le panneau annonce l'enregistrement.
  - I2 : le vérificateur peut annoncer « propre » sur un écran qu'il n'a jamais affiché — prouvé en renommant un libellé de navigation : 14/14 au vert alors que le vrai défaut de débordement était réintroduit en même temps.
  - I3 : la note d'exploitation dit faux sur le chemin principal — un article **scanné** reçoit son poids net d'OFF immédiatement ; seuls les articles hérités de l'import Grocy en sont dépourvus, et un article sans code-barres n'est jamais couvert par la resynchronisation.
Task 17: Ruling: la catégorie devient un champ en lecture seule avec sa raison affichée, comme l'unité de base — parce qu'une clé étrangère nue sans nom ni liste accepte en silence l'identifiant d'une autre catégorie, et que cette donnée sera lue par les lots recettes et courses — coût si faux : il faudra passer par un service pour changer une catégorie, en attendant une vraie liste.
Task 17: Ruling: le vérificateur doit affirmer qu'il a bien atteint l'écran avant de le mesurer — parce qu'un outil incapable de distinguer « cet écran est propre » de « je n'y suis jamais arrivé » est pire que pas d'outil, puisqu'on lui fait confiance — coût si faux : aucun.
Task 17: fix round 1/5 dispatché
Task 17: fix round 1/5 (5 addressed, 0 open ; commits 6510a02..7657844) — «1,5» envoie bien 1.5, «7 jours» refuse toute l'édition en français sans rien envoyer, un champ vidé exprès reste distinguable ; écran inatteignable prouvé détecté ; le vérificateur est désormais servi en HTTP réel (deux scénarios — Panier et Rangement — passaient auparavant par accident, confirmé par reproduction) ; la note d'exploitation vérifiée ligne à ligne contre le code
Task 17: complete (commits 34e4d84..7657844, relecture propre, 474 tests Python + 183 front + vérificateur 14/14)
Task 17: parked — le front accepte un seuil négatif et s'en remet au validateur serveur, qui le refuse en français. Antérieur, hors finding.
=== LES 17 TÂCHES SONT TERMINÉES — relecture finale de branche à dispatcher ===

=== RELECTURE FINALE DE BRANCHE (modèle le plus capable) — NON PRÊTE À FUSIONNER ===
5 défauts qui n'existent qu'**entre** les modules, invisibles à 17 relectures de tâche :
  - C1 : le panneau ne peut **jamais ouvrir de session de courses** — `session/start` n'est appelé par rien dans le front (vérifié dans le bundle déployé). Le panier, les deux capteurs, le tri par rayon et tout le parcours de rangement en session sont livrés morts. Aucune tâche du plan ne possédait ce bouton : **c'est un trou de mon plan**, pas d'une implémentation.
  - C2 : Open Prices divise par le poids net **même pour un produit suivi à la pièce** — des yaourts à 2,50 € pré-remplissent 0,02 € l'unité, soit un coût 125 fois trop faible écrit dans un journal en ajout seul.
  - C3 : un prix **négatif** est accepté sur toutes les surfaces d'écriture — `-2,5` passe, la valeur du stock affiche -250 €.
  - C4 : réessayer un rangement autonome hors ligne crée un **second lot** — la file estampille une clé neuve à chaque appel, donc l'idempotence ne joue pas ; le chemin session en est immunisé car sa clé est dérivée côté serveur.
  - I5 : `rejouer()` n'est pas réentrant — trois déclencheurs peuvent se chevaucher et retirer de la file une action jamais envoyée.
Comptabilité : unités et dénominations saines de bout en bout ; ce sont les **coûts** qui peuvent être faux (C2, C3, I6) et une **quantité** (C4).
Sûreté domestique : rien ne peut faire tomber l'instance — boucle d'événements propre, pas de croissance non bornée, entités non empoisonnables.
Task final: vague de correction unique dispatchée (C1–C4, I5–I8 + 3 items différés requalifiés « à corriger maintenant »)
Task final: vague de correction unique **appliquée** — commit 4e56370. C1 (écran « Courses » :
ouverture avec pastilles de magasins + `stores/list`, clôture en deux appuis), C2 (Open Prices
non divisé à la pièce, spec §11 réécrit), C3 (prix jamais négatif sur les 4 surfaces), C4 (clé
d'idempotence stable pour un rangement solo), I5 (`rejouer()` sérialisé — retire aussi la course
`viderResultats()` consignée en Task 16), I6 (`update_line` inscrit l'observation qu'il corrige),
I7 (`default_shelf_life_days` dans `PRODUCT_FIELDS`), I8 (`voie` au lieu de `constructor.name`
+ passe minifiée du vérificateur), et les 7 points « pas cher ». 492 pytest / 195 vitest /
19 scénarios de rendu, tous verts. Rapport : `final-fix-report.md`.
Vague finale: re-relecture — C1–C4, I5–I8 et les 7 points annexes **tous fermés**, vérifiés en pilotant (les capteurs de panier quittent zéro pour la première fois ; le prix Open Prices d'un produit à la pièce n'est plus divisé ; un prix négatif est refusé sur les 4 surfaces ; le rangement réessayé donne exactement 1 lot). Les 4 arbitrages de l'implémenteur jugés **sains** un par un.
3 findings résiduels, tous Important, tous petits :
  - F3 : le nouvel écran de session ne désarme pas sur rafraîchissement, contrairement à la règle que le panier écrit noir sur blanc — un rafraîchissement entre les deux appuis laisse le bouton armé sous le doigt du suivant.
  - F1 : `start()` ne refuse qu'une session « courses », donc une seconde session peut naître par-dessus une session « à ranger » abandonnée, rendant les lignes de la première invisibles partout. Récupérable, mais rien ne le dit.
  - F2 : la course `viderResultats()`/`resultatDe()` n'est **pas** fermée, contrairement à ce qu'affirment un commentaire du code et le rapport.
Ruling: je tranche ces trois-là plutôt que de les parquer — deux touchent l'usage réel (un appui destructif involontaire, une session de courses rendue invisible) et le troisième est un commentaire qui ment, ce qui est pire qu'un défaut connu. Chacun est nommé et sans exploration : ce n'est pas une seconde vague, c'est trois modifications désignées — coût si faux : trois éditions de plus avant présentation, aucune découverte.
