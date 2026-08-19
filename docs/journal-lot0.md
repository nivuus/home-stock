# SDD ledger — plan: docs/superpowers/plans/2026-08-18-home-stock-lot0.md

Spec: docs/superpowers/specs/2026-08-18-home-stock-lot0-design.md (lu, autorité contraignante)
Branche: lot-0-fondations (dépôt créé par ce plan, master = commit initial vide de code)
Pas d'outil de todo dans cette session : ce ledger EST le suivi.

## Pré-vol — table de conflits

| Vérification | Produit / Consommé | Résultat |
|---|---|---|
| T1 → T2,5,6,7,8,9,10,12 | `const.py` : DOMAIN, BASE_UNITS, REASONS, COUNTED_REASONS, QUANTITY_EPSILON, DATABASE_FILENAME, CONF_/DEFAULT_EXPIRATION_ALERT_DAYS | toutes les constantes consommées plus tard sont définies en T1 — OK |
| T3 → T4 | colonnes DDL vs PRODUCT_FIELDS / ARTICLE_FIELDS | correspondance exacte, y compris `is_generic` et `external_ref` — OK |
| T4 → T7 | `stock_rows()` vs clés lues par `summary()`/`query_stock()` | id, remaining, best_before, opened_at, price_per_base_unit, product_id, product_name, base_unit, min_quantity, location_name : toutes produites — OK |
| T4 → T7 | `list_batches_for_product()` vs `_as_batch_view()` | b.* + kcal_per_base_unit + product_id : suffisant — OK |
| T5 → T7, T9 | `allocate`, `is_empty`, `InsufficientStock`, `BatchView`, `Allocation` | OK ; T9 doit étendre l'import de `.domain.stock` (dit dans le plan) |
| T6 → T7, T9 | `movement_values`, `COUNTED_REASONS` | OK |
| T7 → T9 | clés de `summary()` vs entités | OK après ajout de kcal_total/cost_total en T9 |
| T8 → T9 | `PLATFORMS` vs modules de plateforme | binary_sensor, sensor, todo : les trois existent (créés vides en T8) — OK |
| T9 → T11 | `entity.py` (base) vs imports de sensor/binary_sensor/todo | OK après extraction de la classe de base |
| T10 → T12 | `services.py` / `services.yaml` étendus par T12 | OK, T12 ajoute un service et un bloc YAML |
| T11 → T4 | `list_aisles` | absent de T4, ajouté par T11 (dit dans le plan) — OK |
| T12 → T3, T4 | tables et dépôts utilisés par l'import | OK |
| Cohérence interne T2 | tests de `format_quantity` vs `_french_number` | vérifié à la main : 1500→« 1,5 kg », 200→« 200 g », 1→« 1 pièce » — OK |
| Cohérence interne T3 | `executescript` et transaction | signalé dans le plan (commit implicite) — OK |
| Cohérence interne T7 | verrou d'écriture non réentrant | aucun appel imbriqué `db.write()` dans le plan ni dans les tests — OK |
| Cohérence interne T7 | `adjust_inventory` reconstruit `BatchView` à la main | **CONFLIT** : duplication de `_as_batch_view`, que la grille de revue traite comme un défaut |
| Cohérence interne T3 | imports `sqlite3`/`pytest` à l'intérieur des fonctions de test | **CONFLIT** : le plan les écrit dans le corps des tests, contraire à l'hygiène de test attendue |
| Cohérence T1 | `manifest.json` / `hacs.json` exigent un compte GitHub réel | **INCONNUE** : non fournie par le propriétaire |

## Rulings de pré-vol

Ruling: T7 `adjust_inventory` doit réutiliser `_as_batch_view` en injectant `kcal_per_base_unit`
dans le dictionnaire de ligne, au lieu de reconstruire un `BatchView` à la main — la duplication
serait signalée en revue et les deux constructions divergeraient au premier changement de schéma.
Coût si faux : une revue qui demande l'inverse, soit ~10 lignes à remettre.

Ruling: les imports `sqlite3` et `pytest` des tests de T3 remontent en tête de module — l'hygiène
de test prime sur la lettre du plan, qui ne les met dans les fonctions que par inadvertance.
Coût si faux : nul, changement purement cosmétique.

Ruling: `manifest.json` porte `codeowners: []` et `documentation`/`issue_tracker` pointent sur
`https://allanic.me/home-stock` (domaine du propriétaire, déjà utilisé pour grocy/home) plutôt
qu'un compte GitHub inventé. La publication HACS attendra que le dépôt distant existe.
Coût si faux : trois chaînes à corriger dans deux fichiers.

Ruling: le travail se fait sur la branche `lot-0-fondations` d'un dépôt créé par ce plan même,
et non dans un worktree séparé — il n'y avait pas de dépôt d'où détacher un worktree.
Coût si faux : `git worktree add` reste possible à tout moment.

## Journal

Task 1: implémenté (commits c5a69c8..1268933) — harnais Docker + const.py + manifest/hacs/README.
         RED/GREEN confirmés par l'implémenteur ; variante `--break-system-packages` retenue.
         Revue dispatchée.
Task 1: minor (deferred): commentaire français dans scripts/test.sh:2, contraire à « commentaires en anglais ».
Task 1: complete (commits c5a69c8..1268933, spec ✅, qualité approuvée, 1 mineure différée)
         ⚠️ résolus par le contrôleur : câblage de DATABASE_FILENAME = tâche 8 (prévu au plan) ;
         exécution docker/pytest = évidence de l'implémenteur, non rejouée par la revue (règle du processus).
Task 2: implémenté (commit fb78196) — domain/units.py, 7/7 tests. Revue dispatchée.
Task 2: minor (deferred): _french_number arrondit l'affichage à 2 décimales (conforme au spec §7.3,
         « l'arrondi est fait à l'affichage » — signalé pour la revue finale, aucun impact sur les calculs).
Task 2: complete (commit fb78196, spec ✅, qualité approuvée)
Task 3: implémenté (commit 81308f7) — storage/database.py, schema.py, migrations/, 8/8 tests.
         Écart signalé par l'implémenteur : assertion de test_write_rolls_back_on_error élargie
         à (IntegrityError, OperationalError) — le brief attendait IntegrityError, or CREATE TABLE
         sur une table existante lève OperationalError. Soumis au jugement de la revue.
Task 3: minor (deferred): dans test_write_rolls_back_on_error, IntegrityError reste dans le tuple
         attendu alors que seul OperationalError peut être levé — vestigial, à resserrer en revue finale.
Task 3: complete (commit 81308f7, spec ✅ — DDL byte-identique au brief, qualité approuvée)
Task 4: implémenté (commit f24dcd0) — storage/repositories.py, 8/8 tests, aucun écart signalé.
Task 4: Ruling: `list_movements` n'est PAS du YAGNI malgré son absence du bloc « Produces » du brief —
         c'est mon bloc d'interfaces qui était incomplet ; les tâches 7 (export_journal), 11
         (movements/list) et 12 en dépendent. À conserver. Coût si faux : une fonction morte de 8 lignes.
Task 4: minor (deferred): aucun test du départage même-jour de latest_price (ORDER BY id DESC).
Task 4: minor (deferred): aucun test prouvant que kcal=None/cost=None sont stockés en NULL et non 0.
Task 4: complete (commit f24dcd0, spec ✅, qualité approuvée, 2 mineures + 1 ruling)
Task 5: implémenté (commit 779cc40) — domain/stock.py, 10/10 + suite complète 34/34.
Task 5: revue — spec ✅ mais qualité « needs work » : 2 importantes, 3 mineures.
Task 5: minor (deferred): borne exacte de l'epsilon non testée (is_empty utilise `<`, 0.001 non testé).
Task 5: minor (deferred): kcal non asserté sur une sortie multi-lots (seul le prix l'est).
Task 5: minor (deferred): interaction des composantes du tri non testée (lot ouvert sans date vs lot daté jamais ouvert).
Task 5: ⚠️ résolus par le contrôleur : (a) la tâche 7 persiste bien `closed_at` quand `closes_batch`
         est vrai — c'est écrit au plan ; (b) `allocate` n'ignore pas un lot déjà sous l'epsilon, mais
         un tel lot ne peut pas persister une fois la correction 1 appliquée et la fermeture écrite.
         Aucun défaut réel, aucune action.
Task 5: fix round 1/5 dispatché — implémenteur d'origine repris, 2 importantes envoyées verbatim.
Task 5: fix round 1/5 (2 addressed, 0 open — garde epsilon sur la boucle + test de non-régression ;
         branche de tolérance épinglée par un test ; commits 779cc40..ac224c0)
Task 5: complete (commits f24dcd0..ac224c0, re-revue propre, 3 mineures différées)
Task 6: implémenté (commit 54c69a4) — domain/nutrition.py, 42/42.
Task 6: complete (commit 54c69a4, spec ✅, qualité approuvée, aucun constat réel)
         ⚠️ résolus : le câblage de movement_values dans les mouvements est la tâche 7 (prévu au plan).
--- Couche domain/ terminée (units, stock, nutrition). Reste : application + couche HA + import Grocy. ---
Task 7: implémenté (commit d7fbd65) — application.py, 15 nouveaux tests, 57/57.
         Correction mandatée appliquée (_as_batch_view réutilisé dans adjust_inventory).
         Défaut trouvé par l'implémenteur : import mort `is_empty` retiré. NB : la tâche 9 en aura
         besoin pour consume_batch — à réintroduire à ce moment-là, ce n'est pas une régression.
Task 7: revue — spec ❌ (fallback product.reference_kcal jamais lu) + 3 importantes + 5 mineures.
Task 7: Ruling: `_now()` reste en UTC naïf. Stocker l'UTC est correct et cohérent avec le recorder HA ;
         le vrai risque signalé (une consommation à 00h30 locale tombe la veille) se règle au lot 2,
         qui DOIT convertir en Europe/Paris avant de grouper par jour. Exigence inscrite ici pour le lot 2.
         Coût si faux : le lot 2 doit faire la conversion — ce qu'il doit faire de toute façon.
Task 7: minor (deferred): add_stock replay ferait TypeError si batch_id était NULL (inatteignable aujourd'hui).
Task 7: minor (deferred): abs(delta) < 0.001 code en dur QUANTITY_EPSILON au lieu de l'importer.
Task 7: minor (deferred): un SELECT article_id par allocation dans le verrou, alors que b.* le porte déjà.
Task 7: minor (deferred): open_batch sur un lot déjà ouvert réécrit opened_at (aucune règle violée).
Task 7: fix round 1/5 dispatché — 1 manquement spec + 3 importantes envoyés verbatim.
Task 7: fix round 1/5 (4 addressed, 0 open — repli reference_kcal sur les deux chemins, ruptures
         enracinées sur la table product, LIKE échappé avec ESCAPE, 8 tests ajoutés ; commits d7fbd65..7c29916)
Task 7: complete (commits 54c69a4..7c29916, re-revue propre, 65/65, 5 mineures + 1 ruling)
Task 8: implémenté (commit dce14f2) — __init__/coordinator/config_flow/traductions, 70/70.
Task 8: revue — spec ❌ (option default_currency absente) + 1 importante + 1 mineure.
Task 8: Ruling: `default_currency` est RETIRÉE du spec plutôt qu'implémentée. Aucun code ne la lit
         (les capteurs portent « EUR » en dur) ; une option inerte promet dans l'interface un
         comportement inexistant. Spec §8.0 amendé et daté. Le manquement spec tombe donc.
         Coût si faux : ~5 lignes dans config_flow.py + 2 clés de traduction.
Task 8: minor (deferred): les clés de traduction entity.* déclarent des entités qui n'existent pas
         encore — la tâche 9 devra réutiliser exactement ces translation_key, sinon elles rancissent.
Task 8: fix round 1/5 dispatché — 1 importante (ConfigEntryNotReady autour de l'ouverture de la base).
Task 8: fix round 1/5 (1 addressed, 0 open — ConfigEntryNotReady + fermeture de la base avant relance,
         test SETUP_RETRY ; commits dce14f2..75e5942)
Task 8: complete (commits 7c29916..75e5942, re-revue propre, 71/71, 1 mineure + 1 ruling)
Task 9: implémenté (commit 6a5bc04) — entity/sensor/binary_sensor/todo + counted_totals + consume_batch, 78/78.
         2 défauts trouvés par l implémenteur : repli reference_kcal absent de consume_batch ; isolation
         des tests (base partagée entre tests via le config dir fixe de phacc).
Task 9: revue — spec ✅, qualité « needs work » : 2 importantes (uid périmé qui lève une exception brute
         dans le frontend ; règle centrale du todo non testée) + 5 mineures.
Task 9: revue a CONFIRMÉ les 2 défauts trouvés par l'implémenteur. Sur l'isolation des tests : toutes les
         suites `hass` antérieures partageaient bien un config dir et une base. Impact analysé : cela ne
         pouvait que MASQUER un échec ou en provoquer un dépendant de l'ordre, jamais cacher un bug de
         production (test_application.py utilise son propre tmp_path). Suite verte après correction, rien
         n'a été démasqué. Aucune action rétroactive nécessaire.
Task 9: minor (deferred): 0.001 en dur au lieu de QUANTITY_EPSILON (application.py:170 et 241).
Task 9: minor (deferred): f-string sans placeholder dans repositories.py:241.
Task 9: minor (deferred): extra_state_attributes publie la liste `expiring` complète, non bornée.
Task 9: ⚠️ résolu : l'unité EUR sur un capteur `measurement` sans device_class `monetary` est acceptée par
         HA ; à revérifier au lot 2 quand les statistiques long terme seront réellement exploitées.
Task 9: fix round 1/5 dispatché — 2 importantes + 2 points d'une ligne.
Task 9: fix round 1/5 (2 addressed, 0 open ; commits 6a5bc04..f9bd455)
Task 9: 3e défaut trouvé par l'implémenteur et CONFIRMÉ par la re-revue contre l'image HA 2026.8.2 :
         le service todo.update_item passe le statut en CHAÎNE (vol.In ne convertit pas), donc la garde
         `is not TodoItemStatus.COMPLETED` était toujours vraie — cocher depuis l'interface réelle ne
         faisait RIEN. Fonctionnalité entièrement cassée, corrigée par `!=` + test via le vrai service.
Task 9: complete (commits 75e5942..f9bd455, re-revue propre, 85/85, 3 mineures)
Task 10: défaut trouvé par l'implémenteur et CONFIRMÉ : CONSUME_SCHEMA validait `reason` contre REASONS
         complet — un `consume` pouvait porter purchase/inventory/transfer, décrémenter le stock ET
         échapper à COUNTED_REASONS, sous-comptant kcal et euros. Corrigé (CONSUME_REASONS) + test.
Task 10: minor (deferred): la traduction UnitError -> HomeAssistantError n'est pas testée.
Task 10: minor (deferred): la garde anti-double-enregistrement des services n'est pas testée.
Task 10: minor (deferred): les services restent enregistrés après déchargement de la dernière entrée.
Task 10: minor (deferred): add_stock sans article_id NI barcode passe la validation et répond
         « Code-barres None inconnu » — message déroutant, hérité de ma rédaction du brief.
Task 10: complete (commit 7be551e, spec ✅, qualité approuvée, 92/92, 4 mineures)
Task 11: revue — spec ✅, qualité « needs work » : 4 importantes (pas de garde si l'intégration n'est
         pas chargée ; abonnement qui rediffuse à tous les clients existants, coût quadratique ;
         dépendance non testée à always_update ; movements/list sans aucun test).
Task 11: Ruling: le premier envoi de l'abonnement pousse `coordinator.data` DIRECTEMENT à la connexion
         concernée, puis demande un rafraîchissement sans l'attendre (donc débounce, donc dix onglets
         = une seule lecture). Cela supprime la rediffusion quadratique, la dépendance à always_update,
         et la séquence send_result-puis-error qui casse le protocole. Coût si faux : le panneau voit
         au pire un résumé vieux de quelques secondes, corrigé par le rafraîchissement suivant.
Task 11: fix round 1/5 dispatché — 4 importantes.
Task 11: fix round 1/5 (4 addressed, 0 open ; commits 53377b3..0b5680b)
Task 11: minor (deferred): la tâche de rafraîchissement est créée via hass.async_create_task brut,
         donc non annulée si l'entrée est déchargée pendant le débounce.
Task 11: complete (commits 15576b2..0b5680b, re-revue propre, 102/102)
Task 12: implémenté (commit c9439f5) — import_grocy.py + service, 11 tests, 113/113.
         Défaut trouvé : le service rafraîchissait le coordinateur même en simulation. Corrigé.
         Table de correspondance des unités vérifiée contre la vraie grocy.db (334 produits).
Task 12: revue — spec ❌ + 1 CRITIQUE (la simulation n'inspecte ni codes-barres ni prix, donc elle ne
         peut pas prouver « 0 code-barres attribué deux fois » avant d'écrire) + 4 importantes
         (nom en double = plantage au lieu d'anomalie ; couche codes-barres/prix non rejouable ;
         diviseur de prix faux quand unité d'achat ≠ unité de stock, cas réel Houmous 160g ;
         date d'observation en dur) + 8 mineures.
Task 12: ⚠️ résolu : les 50 produits actifs à 0 kcal ne sont pas un défaut — c'est la convention
         documentée du catalogue (« vérifié, aucun apport » pour savon, sacs, sel), pas un « inconnu ».
Task 12: note de la revue à conserver : les 39 last_price réels sont tous NULL ou vides — le chemin
         prix est mort sur les données réelles, il ne pouvait donc pas être validé en pratique.
Task 12: fix round 1/5 dispatché — 1 critique + 4 importantes + 3 points d'une ligne + tests manquants.
Task 12: fix round 1/5 (1 critique + 4 importantes + 3 points addressed, 0 open ; commits c9439f5..f6dcd07)
Task 12: complete (commits 0b5680b..f6dcd07, re-revue propre, 123/123)
--- Tâches 1 à 12 terminées. Task 13 = déploiement sur l'instance HA de production : GATE, autorisation requise. ---

## Revue finale de branche (19 commits, c5a69c8..f6dcd07)

Verdict : « needs work before merge », aucun défaut critique. 6 importantes + 9 mineures + triage
des 21 mineures différées (3 à corriger, 18 laissées). Suite rejouée par le relecteur : 123/123.
Frontières de couches vérifiées : domain/ n'importe que const ; storage/ n'importe pas hass ; aucune
règle métier réimplémentée dans la couche HA ; aucun I/O SQLite dans la boucle d'événements ;
aucun UPDATE/DELETE sur movement ; la simulation d'import n'écrit rien.

Ruling: le transfert écrit UNE ligne de quantité nulle, pas deux. Le spec §7.5 annonçait deux lignes
         de somme nulle : elles ne porteraient aucune information (movement n'a pas de colonne
         d'emplacement) et gonfleraient le journal. Spec amendé et daté.
         Coût si faux : une seconde ligne à écrire, sans reprise de données.
Ruling: les lignes `packaging` ne sont PAS créées à l'import ; reporté au lot 1. Sur la base réelle,
         239 des 299 produits actifs sont en unité de conditionnement et 37 seulement portent un poids
         dans leur nom, avec des pièges qu'aucune analyse de nom ne franchit (« San Pellegrino 6x1L »,
         « Sac poubelle 20L »). Le poids net viendra d'Open Food Facts, qui mesure au lieu de deviner.
         Spec §10 amendé et daté. Coût si faux : les conditionnements arrivent un lot plus tard.
Ruling: les 4 fonctions de dépôt sans appelant de production (latest_price, find_product_by_name,
         insert_aisle, insert_packaging) sont CONSERVÉES et commentées — le lot 1 a besoin des quatre.
         Coût si faux : quatre fonctions mortes de moins de 10 lignes chacune.
Ruling: `counts_in_daily_totals` est supprimée. La règle ships en SQL depuis const.COUNTED_REASONS ;
         une fonction que seuls les tests appellent, à côté d'une copie SQL qui tourne, dérive.
         Coût si faux : la fonction se réécrit en trois lignes.

Vague de correction unique dispatchée : 6 importantes + 7 mineures + 3 mineures différées triées.

## Autorisation de déploiement

Le propriétaire a autorisé le déploiement complet (montage, redémarrage du conteneur, ajout de
l'intégration, import du catalogue en simulation puis en réel, vue Lovelace). Réponse : « Tout,
import compris ». Grocy n'est pas touché : l'import est à sens unique.
Final fix wave: 16/16 addressed, re-revue « ready to deploy » (commits f6dcd07..d01f76d, 133/133).
Task 13: déployé (commit 657e864). Import réel : 299 produits, 299 articles génériques, 4 emplacements,
         21 catégories, 35 codes-barres, 35 produits ignorés. ok=true, 0 anomalie en simulation ET en réel.
Task 13: écart 35 vs 39 codes-barres ÉLUCIDÉ par le contrôleur contre la vraie base : les 4 manquants
         appartiennent aux produits désactivés (Graine de Sésame, Œufs, Bicarbonate, Riz basmati —
         suffixés « (doublon) »). L'import a raison de les écarter. NOTE POUR LE LOT 1 : ces 4 EAN
         réels ne sont donc rattachés à aucun produit actif ; le scan les traitera comme inconnus.
Task 13: défaut trouvé après déploiement : `step: 0.0001` sous le plancher de HA invalide TOUT
         services.yaml — aucune des 7 actions n'affiche ses libellés français. Correction dispatchée.
Task 13: le test de bout en bout a laissé un vrai lot de Beaufort dans le stock du foyer.
         Nettoyage demandé via adjust_inventory (et non en base), pour garder une trace honnête.
