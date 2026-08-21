# Éteindre Grocy — dix-huit gestes

> **Compter une soirée, sans interruption.** Les gestes 1 à 11 tiennent dans
> une même session, parce que le geste 2 gèle Grocy et que rien ne doit être
> rangé entre-temps.

**Cette procédure est un livrable, pas un script.** Aucune de ses commandes
n'a été exécutée en l'écrivant, et le composant `home_stock` n'en exécute
aucune : **arrêter un conteneur de la maison est un geste humain**, et rien
dans le code ne peut le faire — `migration_check.py` ne contient ni `docker`,
ni `subprocess`, ni `Popen`, et un test le vérifie sur sa propre source.

Tout ce qui suit est adressé au propriétaire, à la main, dans cet ordre.

---

## Avant de commencer

- Le service `home_stock.check_grocy_migration` (ou le bloc **Bascule** de
  l'écran Réglages) est votre juge. **Ne passez jamais au geste suivant si un
  contrôle est rouge.**
- Un contrôle qui dit « rien mesuré » n'est **pas** un contrôle vert. C'est un
  contrôle qui n'a pas su regarder, et il est traité comme un échec.
- Les imports sont **en simulation par défaut**. Lisez le rapport en entier
  avant d'ajouter `apply: true`.

---

## Les dix-huit gestes

1. **Sauvegarder.** Sauvegarde native Home Assistant complète, puis, datés,
   dans votre dossier personnel : `grocy.db`, le dossier `storage/` de Grocy,
   et `config.php`. C'est le seul geste qui n'a pas de retour arrière s'il est
   sauté.

2. **Geler Grocy.** Ne plus rien y saisir : ni une course rangée, ni un
   produit créé, ni une recette modifiée. Rappel de ce qui est arrivé pendant
   l'écriture de la spec : le produit #350 « Sorbet Fraise » a été créé le
   2026-08-21 à 18 h 54, trois heures avant. **Tant que quelqu'un range une
   course dans Grocy, aucun contrôle d'égalité ne veut rien dire** — et le
   contrôle **C0** le détectera en comparant la dernière écriture de Grocy à
   la date de la copie.

3. **Copier la source dans `config/`.** Le conteneur Home Assistant ne monte
   que `config/` et `media/` : il **ne voit pas** `/opt/nivuus/Grocy/`. Copier :
   - `grocy.db` → `config/grocy_import.db`
   - `storage/recipepictures/` → `config/media/home_stock/recipes/`
   - `storage/productpictures/` → `config/media/home_stock/articles/`

   Sans `test.jpg` ni les vignettes `__downscaledto64x64`.

4. **Déployer les lots 2 à 6.** La base de production est au schéma **2** ;
   `m003` → `m008` s'appliquent au redémarrage de Home Assistant. Vérifier
   ensuite : `repairs/list_issues` à **0**, et C0 doit voir
   `schema_version = 8`.

5. **Supprimer les statistiques des trois cumuls** — `kcal_total`,
   `cost_total`, `cost_waste_total`, dans Outils de développement →
   Statistiques. Rendu obligatoire par leur passage en `state_class: total` au
   lot 4. **Irréversible** : c'est pour cette raison que le geste 1 vient
   avant.

6. **Rejouer l'import du catalogue.** `home_stock.import_grocy_catalog`,
   `apply: false` d'abord. Exiger `ok: true` et `anomalies: []`, puis
   `apply: true`. C'est ce geste qui rattrape ce qui a été créé dans Grocy
   depuis le premier import — au minimum le produit #350. **Sans lui, l'import
   du stock s'arrête net** et vous dit lequel manque.

7. **Importer piles et équipements.** `home_stock.import_grocy_equipment`,
   `apply: false`, exiger un `summary_diff` **vide**, puis `apply: true`.

8. **Appliquer le raccord `maintenance.jinja`.** Suivre
   `docs/raccord/README.md`, **dans son ordre**, sans sauter une étape.
   Vérifié le 2026-08-21 : le fichier fait encore ses **142 lignes** avec son
   bloc 3 « Piles », et `config/automations.yaml` lit encore
   `todo.grocy_batteries`. C'est ce raccord qui débranche cette liste, et il
   doit venir **après** le geste 7 : un import d'équipements non fait avant le
   raccord ferait *disparaître* 14 tâches de pile au lieu de les déplacer.
   C'est la seule dépendance d'ordre entre le lot 5 et le lot 7, et c'est un
   **préalable** à toute extinction. Le contrôle **C11** le mesure.

9. **Importer le stock.** `home_stock.import_grocy_stock`, `apply: false`.
   Lire **toutes** les anomalies, en particulier les **7 lots dont le prix est
   écarté** : leur note Grocy est citée mot pour mot parce que quatre d'entre
   elles nomment un autre produit que celui auquel le lot est attaché. Puis
   `apply: true`.

10. **Importer recettes, images et planning.**
    `home_stock.import_grocy_recipes`, `apply: false` puis `apply: true`. Les
    images vont sous `media/`, jamais sous `www/`.

11. **Contrôler.** `home_stock.check_grocy_migration`, ou le bloc **Bascule**
    de l'écran Réglages. Acquitter **nominativement** les 7 lots au prix
    écarté et les 25 lignes d'ingrédient sans quantité, un identifiant à la
    fois — `all` et `*` sont refusés.
    **Ne pas continuer tant que `ok` n'est pas `true`.**

12. **Preuve sur pièce, Grocy encore allumé.** Ouvrir une recette sur la
    tablette cuisine et vérifier que son image s'affiche. Puis, **temporairement** :

    ```bash
    docker stop grocy
    ```

    Rouvrir la même recette. Si l'image s'affiche encore, le rapatriement a
    tenu. Puis :

    ```bash
    docker start grocy
    ```

    **On n'éteint pas encore.**

13. **Débrancher ce qui reste dans la maison.** Trois entrées, chacune pour sa
    raison :
    - `script.afficher_recette_cuisine` (`config/scripts.yaml`, l. 293-331)
      ouvre une iframe sur `/local/grocy-recipes.html`, qui **interroge l'API
      de Grocy** : elle affichera une erreur. Pointer la vue Recettes du
      panneau, ou supprimer le script.
    - `script.afficher_repas_prevu` (l. 407-435) lit
      `state_attr('sensor.grocy_meal_plan', 'meals')`. L'attribut devient
      `None` et le script part dans sa branche « pas de recette » : **une
      dégradation silencieuse**. `sensor.home_stock_next_meal` porte déjà
      `meal_id`.
    - `automation.grocy_rappel_liste_de_courses_au_depart`
      (`config/automations.yaml`, l. 3672-3699) est **le pire des cas** :
      l'entité `todo.grocy_shopping_list` passe `unavailable`, le
      `| int(0)` du modèle la lit **0**, et l'automation **ne se déclenche
      plus jamais, sans erreur**. Une panne bruyante se voit ; celle-ci non.
      La rebrancher sur `todo.home_stock_shopping`, ou la supprimer.

    Puis `automation.reload`, `script.reload`, et `repairs/list_issues` à 0.

14. **Commenter le cron de 5 h 40.** `crontab -e` en root : la ligne
    `grocy-off/sync.sh` échouerait chaque nuit contre un port fermé, en
    remplissant `/var/log/grocy-off.log`.

15. **Arrêter Grocy, sans le supprimer.**

    ```bash
    docker compose stop grocy
    ```

    **PAS `down -v`** : les volumes partent avec, et le geste 1 devient votre
    seul filet. Retirer aussi le label **watchtower** du service, sinon il le
    relancera à la prochaine passe. **Ne pas supprimer
    `/opt/nivuus/Grocy/config/`** avant le délai de rétention de
    `retour-arriere.md`.

16. **Retirer les deux routes Pomerium** `grocy.allanic.me` →
    `127.0.0.1:9283` de `/opt/nivuus/Pomerium/config.yaml`. **Sauvegarde datée
    du fichier d'abord**, puis recharger Pomerium. Sans ce geste, l'adresse
    répond 502.

17. **Supprimer l'entrée de configuration `grocy`** dans Paramètres →
    Appareils et services (elle retire les 21 entités : 7 `binary_sensor`,
    6 `sensor`, 6 `todo`, 1 `calendar`), **puis** désinstaller le dépôt HACS.
    `repairs/list_issues` à 0.

18. **Ranger.** Supprimer `config/grocy_import.db` — c'est un intrant, pas un
    fichier d'exploitation — et retirer `grocy-recipes.html` et
    `grocy-scanner.html` de `config/www/`.

---

## Ce que cette procédure ne fait pas

- Elle **n'est pas exécutée** par le lot qui la livre. Le lot 5 a livré son
  raccord dans `docs/raccord/` et ne l'a jamais appliqué ; le lot 7 fait
  pareil, à plus grande échelle. L'intégration livre, elle n'installe pas.
- Elle ne réinjecte **jamais** l'historique de `stock_log` dans le journal.
  Il est archivé en JSON par `check_grocy_migration` ; les raisons sont dans
  la spec, § 9, et dans `retour-arriere.md`.
- Elle n'écrit **jamais** vers Grocy. Décision du lot 0, jamais assouplie,
  y compris pendant un retour arrière.
