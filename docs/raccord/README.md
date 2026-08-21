# Raccord `todo.maintenance` — fichiers de référence

Ces deux fichiers sont des **copies de référence**. Ils ne sont installés
**ni par le composant, ni par un test, ni par aucune tâche du lot 5**.
L'intégration livre, elle n'installe pas — même discipline que le blueprint du
lot 2. Les poser dans `/opt/nivuus/HomeAssistant/config/` est un geste du
propriétaire, à la main.

| Fichier | Ce qu'il est |
|---|---|
| `maintenance.jinja` | Ce que devra contenir `config/custom_templates/maintenance.jinja` : le macro **sans son bloc 3 « Piles »** (54 lignes de moins). Les blocs 1, 2, 4 et 5 sont inchangés, seuils et hystérésis compris. |
| `maintenance_sync.yaml` | Le bloc de l'automation `maintenance_sync_taches`, avec l'appel à `home_stock.maintenance_plan` et le drapeau `peut_fermer`. |

## Pourquoi le macro perd son bloc « Piles »

Il déduit aujourd'hui le libellé d'une pile par une chaîne de `replace()` sur
le nom de l'entité, son verbe par un motif `rideau|lock`, et ses exclusions par
un motif `browser|pixel|brya|tablette|aspirateur`. Ces trois devinettes
deviennent des colonnes de `home_stock`. Le macro **ne parcourt plus
`states.sensor`** du tout.

L'enrichissement « type de pile » que le macro allait chercher dans
`todo.grocy_batteries` disparaît avec Grocy : c'est `home_stock` qui sait
désormais qu'il reste trois CR2032 au placard.

## Procédure d'application, dans l'ordre

L'ordre compte. Le `.jinja` **d'abord** : le macro sans bloc 3 reste correct
même avec l'ancienne automation, il produit simplement moins de tâches.
L'inverse laisserait une fenêtre où l'automation appelle le service **en
doublon** du bloc 3, et chaque pile faible produirait deux fois le même résumé.

1. **Sauvegarder** les deux originaux :
   ```bash
   cp config/custom_templates/maintenance.jinja \
      config/custom_templates/maintenance.jinja.avant-lot5
   cp config/automations.yaml config/automations.yaml.avant-lot5
   ```
2. **Importer d'abord les piles** (voir `docs/exploitation.md`, section lot 5) :
   `home_stock.import_grocy_equipment` avec `apply: false`, lire le rapport,
   vérifier que `summary_diff` est **vide** et que `ok` est **vrai**, puis
   relancer avec `apply: true`. Sans cet import, l'étape 3 fait disparaître
   les tâches de pile au lieu de les déplacer.
3. **Poser** `docs/raccord/maintenance.jinja` dans
   `config/custom_templates/maintenance.jinja`.
4. `homeassistant.reload_custom_templates`.
5. **Rendre le macro** dans Outils de développement → Modèle :
   ```jinja
   {% from 'maintenance.jinja' import maintenance_plan %}{{ maintenance_plan() }}
   ```
   Comparer les `summary` à ceux d'avant : seules les tâches de pile doivent
   avoir disparu. Rien d'autre.
6. **Remplacer** le bloc `- id: maintenance_sync_taches` de
   `config/automations.yaml` par `docs/raccord/maintenance_sync.yaml`.
7. `automation.reload`, puis vérifier `repairs/list_issues` à **0**.
8. **Attendre la synchronisation de l'heure suivante** (minute 5) et contrôler
   que `todo.maintenance` a **exactement le même nombre de tâches** qu'avant,
   et que Bleuenn n'a **rien** annoncé. Une annonce à la première synchro est
   le signal que le déploiement n'a pas été neutre.

## Retour arrière

Reposer les deux fichiers sauvegardés à l'étape 1, recharger les modèles et
les automations. L'intégration n'a **rien** écrit dans `config/` : il n'y a
rien d'autre à défaire. Les lignes écrites dans `home_stock.db` peuvent
rester — sans le raccord, personne ne les lit.

## Le garde-fou `peut_fermer`

Aujourd'hui, Grocy arrêté ne coûte qu'un suffixe manquant. Demain,
`home_stock` indisponible ferait disparaître les items de pile de `items`
**et** de `keep` : `a_fermer` les contiendrait toutes, et **une seule
synchronisation à 5 h 05 refermerait les quatorze tâches de pile de la
maison**, chacune se rouvrant à la suivante avec son annonce.

D'où `peut_fermer`, qui n'arme la fermeture que si le service a répondu **et**
que sa réponse dit `complete: true`. Un plan incomplet a le droit d'ajouter et
de rafraîchir, **jamais** de fermer. Le défaut d'un garde-fou doit être
« prudent », jamais « permissif » : c'est pourquoi le drapeau lit
`get('complete', false)` et non la seule présence de la réponse.
