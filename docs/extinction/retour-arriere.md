# Retour arrière — ce qu'on garde, combien de temps, et ce qui ne revient pas

## Ce qu'on garde, et jusqu'à quand

| Quoi | Durée | Pourquoi cette durée |
|---|---|---|
| `/opt/nivuus/Grocy/config/` complet (base, `storage/`, `config.php`) | **12 mois** | Le temps qu'une saison complète passe : une recette d'hiver, une DLC longue, une pile changée une fois l'an. Après ça, ce qui n'a pas servi ne servira pas |
| Les sauvegardes datées du geste 1, dans le dossier personnel | **12 mois** | Même raison, et elles sont hors du serveur |
| `config/home_stock_grocy_archive_<date>.json` | **toujours** | 1 123 lignes d'historique, 25 notes de lots, 39 pointages de corvées, 66 entrées de planning. Quelques centaines de kilooctets, emportés par les sauvegardes natives de Home Assistant |
| La sauvegarde datée de `/opt/nivuus/Pomerium/config.yaml` | **3 mois** | Le temps de s'apercevoir qu'une autre route a été cassée en même temps |
| Le conteneur `grocy` arrêté (pas supprimé) | **3 mois** | Assez pour un rallumage de lecture ; au-delà, l'image aura vieilli et la base sera de toute façon dans les sauvegardes |

## Les trois situations d'après-coup

### 1. « Il manque quelque chose, je veux juste regarder »

Rallumer Grocy **pour le LIRE**, jamais pour le réutiliser :

```bash
docker compose start grocy
```

Les routes Pomerium ayant été retirées au geste 16, l'accès se fait en local,
sur **`127.0.0.1:9283`** (par un tunnel SSH depuis votre poste si besoin).

Consigne, en toutes lettres : **ne rien saisir dedans**. Le sens de la
migration ne s'inverse jamais —
décision du lot 0, « Écriture vers Grocy : jamais ». Ce qui manque se saisit
dans `home_stock`, pas dans Grocy : sinon la maison a deux vérités, et c'est
exactement l'état dont cette bascule sort.

Une fois la lecture faite : `docker compose stop grocy`.

### 2. « Un import s'est trompé, je veux le refaire »

Les trois imports sont **rejouables** : chacun retrouve ce qu'il a déjà écrit
par `external_ref` et ne le réécrit pas. Corriger la source (dans
`config/grocy_import.db`, pas dans Grocy), relancer en `apply: false`, lire le
rapport, puis `apply: true`.

**Un rejeu ne défait rien.** Il complète. Un lot déjà importé sur lequel on a
mangé garde son `remaining` : le rejeu ne remet jamais `remaining = initial`,
parce que ce serait défaire une consommation réelle **sans laisser de trace** —
et `movement` est en **ajout seul**, donc on ne pourrait même pas la
retrouver. Une vraie correction se fait par contrepassation (lot 4).

### 3. « Je veux tout remettre comme avant »

Dans cet ordre **strict**, et c'est l'inverse exact de l'extinction :

1. restaurer la sauvegarde native Home Assistant du geste 1 ;
2. remettre les deux routes Pomerium depuis leur sauvegarde datée ;
3. décommenter le cron de 5 h 40 ;
4. réinstaller le dépôt HACS et recréer l'entrée de configuration `grocy` ;
5. **Grocy en dernier des services** : `docker compose start grocy` ;
6. **ses fichiers de configuration en dernier des fichiers** : ne restaurer
   `/opt/nivuus/Grocy/config/` que si la base a réellement été touchée.

Redémarrer Grocy avant Home Assistant ferait apparaître les 21 entités
pendant que la restauration est à moitié faite, et l'automation de rappel des
courses se déclencherait sur une liste à moitié restaurée.

## Ce qui ne revient pas — à lire AVANT, pas après

- **Les statistiques long terme des trois cumuls**, supprimées au geste 5, ne
  se restaurent pas depuis la sauvegarde de Home Assistant sans restaurer
  aussi toute la base du recorder. C'est le geste irréversible de la
  procédure, et c'est pour lui que le geste 1 existe.
- **Le journal de `home_stock` est en ajout seul.** Deux triggers refusent
  `UPDATE` et `DELETE` sur `movement`. Un import appliqué ne s'annule pas : il
  se corrige par contrepassation. C'est pourquoi tous les imports sont en
  simulation par défaut.
- **L'historique de `stock_log` n'entrera jamais dans la comptabilité**, même
  en revenant en arrière. Ses valeurs sont fausses d'un facteur trente sur les
  35 journées mesurées, sa couverture est de 20 %, et ses heures sont des
  heures de saisie et non de repas. Il est **conservé** dans
  `config/home_stock_grocy_archive_<date>.json`, lisible sans le schéma de
  Grocy : des noms, des dates, des quantités et des unités.
- **Les 46 images Unsplash** ne sont pas rapatriées et ne le seront pas. Elles
  ne meurent pas avec le conteneur ; elles mourront un autre jour, toutes
  ensemble.
