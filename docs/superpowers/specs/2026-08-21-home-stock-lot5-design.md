# home_stock — Lot 5 : équipements, piles et consommables

> Spec du lot 5. Le découpage en huit lots est fixé par
> `2026-08-18-home-stock-lot0-design.md` § 3, qui pose aussi le catalogue
> `product`/`article`/`batch` et le journal en ajout seul. Le panneau, la file
> d'attente hors-ligne et l'ingestion Open Food Facts viennent de
> `2026-08-19-home-stock-lot1-design.md` ; la validation aux deux surfaces et la
> règle « aucune surface n'a le droit d'être la plus faible » de
> `2026-08-20-home-stock-lot2-design.md`.

## 1. Objectif et livrable

Le lot 0 a nommé cette dette dès sa feuille de route :

> `config/custom_templates/maintenance.jinja` lit `todo.grocy_batteries` pour
> enrichir les tâches de pile (« 18 % — 1x CR2032 »). Il casse le jour où Grocy
> s'éteint : c'est un travail du lot 5, pas une découverte du lot 7.

Le livrable vérifiable est donc littéralement : **`todo.maintenance` marche sans
Grocy**. Conteneur Grocy arrêté, la réconciliation horaire continue de tourner,
les mêmes tâches apparaissent et se ferment aux mêmes seuils, et la bascule
elle-même ne crée ni ne ferme aucune tâche.

Réussir uniquement ça serait manquer l'occasion. Le lot 5 ajoute trois choses que
Grocy ne savait pas faire :

1. **Savoir quoi acheter.** Une tâche dit aujourd'hui « Pile à changer — Velux
   (CH) — 18 % » sans dire le format ni s'il en reste une au placard. Elle dira
   « 18 % — 1× CR2032, aucune en stock », et le manque remontera dans
   `binary_sensor.home_stock_shortages`, donc dans la liste de courses du lot 4.
2. **Cesser de deviner.** Le verbe (« Recharger » ou « Pile à changer ») est
   déduit d'un motif `rideau|lock` sur le nom affiché ; l'exclusion d'un capteur
   d'un motif `browser|pixel|brya|tablette|aspirateur`. Les deux deviennent des
   colonnes.
3. **Tenir les équipements** : date d'achat, garantie, notice, et les
   consommables qui vont avec — filtre du purificateur, brosses de l'aspirateur —
   rattachés au catalogue existant plutôt qu'à un modèle parallèle.

## 2. Périmètre

**Dans le lot :** les tables `battery`, `battery_event`, `equipment`,
`equipment_consumable` ; l'ancrage d'une pile sur le registre Home Assistant ;
les exclusions déclaratives ; les trois natures de pile et leurs verbes ; le
rattachement d'une pile ou d'un consommable à son produit de rechange ; les
recharges et remplacements ; garantie et notice ; le service
`home_stock.maintenance_plan` et le raccord qui remplace le bloc « Piles » de
`maintenance.jinja` ; deux écrans de panneau ; l'import rejouable des piles et
équipements Grocy ; la migration `m006`.

**Hors du lot :** les tablettes murales et le vocal (lot 6) ; la reprise du stock
alimentaire et l'arrêt de Grocy (lot 7) ; les *chores* Grocy (§ 20) ; toute
modification des blocs 1, 2, 4 et 5 de `maintenance.jinja` autrement que par
l'enrichissement de leurs descriptions ; tout téléversement de fichier.

**Hors du lot, et ce n'est pas un oubli :** le lot 5 n'écrit **rien** dans
`/opt/nivuus/HomeAssistant/config/`. Les deux fichiers de raccord sont versionnés
ici comme copies de référence, testés ici, et **appliqués à la main par le
propriétaire**. Même règle que le blueprint du lot 2 : l'intégration livre, elle
n'installe pas.

## 3. Décisions validées

| Question | Réponse retenue |
|---|---|
| Une CR2032 est-elle un produit du catalogue ? | **Oui pour la rechange, non pour celle qui est installée.** La rechange est un `product` (`edible = 0`) ; la pile installée est une ligne de `battery` qui pointe vers ce produit |
| Ancrage capteur ↔ pile | L'**`id` de l'entrée du registre d'entités** (UUID) en clé, le `device_id` en second. Jamais l'`entity_id` |
| Exclusions | **Déclaratives, en base** : `battery.tracked` ∈ {1, 0, NULL} + `exclusion_reason`. Plus aucun motif d'`entity_id` |
| Capteur de pile inconnu de `home_stock` | Ni tâche ni silence : compté par `sensor.home_stock_batteries_undeclared` et listé « à déclarer » dans le panneau |
| Verbe | Une colonne `kind` à trois valeurs (`primary`, `rechargeable_cell`, `built_in`) |
| Piles de rechange nommées une à une | **Non.** 18 lignes Grocy pour 18 cellules deviennent 5 produits avec une quantité |
| Cycles de charge | Sur la **place**, pas sur la cellule : une ligne `battery_event` par recharge, en ajout seul |
| Reprise de `maintenance.jinja` | **Un service à réponse** `home_stock.maintenance_plan`, qui prend le plan jinja en entrée et rend le plan fusionné. Le bloc « Piles » du macro disparaît |
| Notice | **URL d'abord**, chemin sous `media/` en option. Aucun téléversement, jamais `www/` |
| Garantie | Ne produit **jamais** de tâche ; un capteur et ses attributs |
| Achat d'un équipement | N'écrit **jamais** de mouvement |
| Migration | `m006` (§ 6.1 pour l'hypothèse et son garde-fou) |

## 4. Ce que la maison fait aujourd'hui — mesuré le 2026-08-21

Rien de ce qui suit n'est supposé : tout est relevé dans `ha_sync/entities/`,
`config/.storage/core.entity_registry`, `core.device_registry` et une copie en
lecture seule de `grocy.db`.

### 4.1 Les capteurs de pile

**28 entités `sensor` portent `device_class: battery`.** Le bloc 3 de
`maintenance.jinja` en écarte 14 : 5 par `entity_id` exact (les trois capteurs
de présence HOBEIAN en NiMH, les deux batteries de la e208) et 9 par le motif
`browser|pixel|brya|tablette|aspirateur` (Pixel, Chromebook, deux aspirateurs,
trois tablettes, deux capteurs `browser_mod`).

**Il reste 14 piles réellement suivies.** Aucune n'est sous 20 % au 2026-08-21 —
la plus basse est le rideau de la cuisine à 32 % — et `todo.maintenance` porte
4 tâches, aucune de pile. La fenêtre de bascule est calme.

### 4.2 L'enrichissement Grocy couvre deux capteurs, pas cinq

`todo.grocy_batteries` porte 8 éléments ; la table `batteries` de Grocy en
contient 26 :

| Nature | Lignes | Ce qu'elles deviennent |
|---|---|---|
| Appareil avec un `entity_id` dans la description | 5 | Une ligne `battery` avec son format |
| Appareil retiré (« plus aucune entité HA », vérifié 2026-07-31) | 3 | Rapportées, non importées |
| Cellules de rechange nommées une à une (LADDA ×4, 9 V ×5, CR2032 ×3, C/LR14 ×4, AA ×2) | 18 | **5 produits** de catalogue avec une quantité |

Or **3 des 5 lignes qui portent un `entity_id` visent des capteurs que
`piles_exclues` écarte** (`sensor.capteur_humain_batterie`,
`sensor.capteur_batterie`, `sensor.capteur_batterie_2`). L'enrichissement « type
de pile » ne s'applique donc qu'à **deux** capteurs :
`sensor.interrupteur_sdb_batterie` (1× CR2032) et `sensor.interrupteur_c_batterie`
(2× AAA).

Ce chiffre dimensionne le lot. CLAUDE.md annonce « 5 sur 14 » ; la mesure dit
2 sur 14. Ce que l'extinction de Grocy détruit, c'est un suffixe sur deux
tâches — pas une fonction. **Le raccord est bon marché à remplacer, et la vraie
valeur du lot 5 est ailleurs : les 12 piles dont personne ne connaît le format,
et les rechanges qui ne sont dans aucun stock.**

### 4.3 Ce que Grocy a modélisé et que personne n'a rempli

Deux mesures qui doivent freiner l'envie de tout reproduire :

- **`battery_charge_cycles` contient 0 ligne.** Six mois après la création des
  26 piles, aucune recharge n'a jamais été enregistrée : le suivi par cellule
  physique a été modélisé et jamais utilisé.
- **Les 34 lignes de `equipment` ont 0 notice.** `instruction_manual_file_name`
  est vide sur les 34, et la table n'a aucun champ de garantie ni de date d'achat.

Ce qui ne se remplit pas en un geste ne se remplit pas du tout. Le lot 5 ne
construit ni identité par cellule, ni machinerie de téléversement de PDF.

### 4.4 Le piège des deux tags BLE, tel qu'il est vraiment

| `entity_id` | `device_id` | Nom de l'appareil | Modèle |
|---|---|---|---|
| `sensor.cle_de_la_peugeot_e208_batterie_ble` | `8b506dca…` | **Sac** | MiTag |
| `sensor.sac_batterie_ble` | `cea43cc1…` | **Clé Peugeot** | FnR 6ATAG72R |

L'`entity_id` a été figé à la création et n'a jamais suivi le renommage de
l'appareil. Le désaccord n'est pas entre deux noms, il est entre un nom
**vivant** (celui de l'appareil) et un nom **fossile** (celui de l'`entity_id`) —
exactement le mode de défaillance que CLAUDE.md décrit pour l'enrichissement
Grocy. Note pour l'implémentation : l'inventaire de CLAUDE.md dit par ailleurs
que la clé de la e208 est un MiTag, ce qui contredit le nom de l'appareil. Le
lot 5 **ne tranche pas** (§ 10).

## 5. Amendements aux specs précédents

**A1 — `product.edible = 0` cesse d'être décoratif.** Le lot 0 a posé la colonne
sans lui donner de rôle. Elle sépare désormais deux mondes qui partagent le même
catalogue. Une pile CR2032 sortie du stock écrit un mouvement `consumption`
comme n'importe quel produit, avec `kcal` à `NULL` (l'article n'a aucune table
nutritionnelle : la règle du lot 2 s'applique telle quelle) et un coût réel.
**Les capteurs de nutriments ne bougent pas ; `cost_today` monte.** C'est
correct — une pile achetée et consommée est une dépense du jour — et c'est
précisément pourquoi la rechange est un produit et pas une table à part.

**A2 — « aucune entité par produit » (lot 0 § 8) vaut aussi ici.** 14 piles ne
feront pas 14 entités : trois synthèses (§ 14.3), le détail par le panneau et le
service à réponse.

**A3 — `REASONS` ne change pas.** Un remplacement consomme une rechange avec le
motif `consumption` existant. Ajouter un motif `battery` aurait obligé à repasser
sur `COUNTED_REASONS`, `totals_between`, `journal_entries` et les onze capteurs
du lot 2 pour une distinction qui se lit déjà dans `product.edible = 0`.

## 6. Migration `m006`

### 6.1 Le numéro, et pourquoi il n'est pas garanti

L'état réel de `storage/migrations/` au 2026-08-21 est `m001_initial`
(VERSION 1), `m002_scan` (2), `m003_consumption` (3). Le lot 3 prendra `m004`, le
lot 4 `m005` ; le lot 5 prend donc **`m006`**.

**Hypothèse, et son garde-fou.** `apply_migrations()` lit `MAX(version)` dans
`schema_version` et n'applique que les migrations strictement supérieures. Un
trou est sans conséquence ; un **dépassement** ne l'est pas. Si le lot 5 était
livré avant les lots 3 et 4, une base passée en version 6 ne verrait jamais
`m004` ni `m005` : sautées définitivement, silencieusement, et l'intégration
démarrerait sur un schéma amputé. Le plan d'implémentation doit donc (a) relire
`migrations/__init__.py` **au moment du merge** et prendre le premier numéro
libre, pas `6` par réflexe, et (b) ajouter à `tests/storage/test_migrations.py`
une assertion que les `VERSION` du tuple `MIGRATIONS` sont strictement
croissantes et contiguës à partir de 1 — ce qui transforme la règle en quelque
chose que la suite fait respecter au lieu d'une chose dont il faut se souvenir.

### 6.2 DDL

```sql
-- Une place où une pile vit : la CR2032 du dimmer de la salle de bain, la
-- batterie intégrée de la serrure, les deux AAA de la télécommande cuisine.
-- Ce n'est PAS une cellule physique : c'est un emplacement, et il survit au
-- remplacement de ce qu'on y met.
CREATE TABLE battery (
  id INTEGER PRIMARY KEY,
  label TEXT NOT NULL,             -- le texte affiché dans la tâche (§ 10)
  -- L'ancre : l'`id` (UUID) de l'entrée du registre d'entités, pas l'entity_id.
  entity_registry_id TEXT,
  device_id TEXT,                  -- ancre de secours et source du nom vivant
  equipment_id INTEGER REFERENCES equipment(id),  -- informatif, jamais résolutif
  kind TEXT NOT NULL CHECK (kind IN ('primary','rechargeable_cell','built_in')),
  product_id INTEGER REFERENCES product(id),      -- la rechange, dans le catalogue
  cell_count INTEGER NOT NULL DEFAULT 1 CHECK (cell_count >= 1),
  tracked INTEGER CHECK (tracked IN (0, 1)),      -- NULL = découvert, pas décidé
  exclusion_reason TEXT,           -- obligatoire quand tracked = 0
  low_percent REAL NOT NULL DEFAULT 20,           -- seuil d'apparition
  keep_percent REAL NOT NULL DEFAULT 25,          -- seuil de maintien
  -- Dernier relevé NUMÉRIQUE vu, écrit par le coordinateur. En base, et pas
  -- déduit de `last_changed`, qui repart au démarrage de HA (§ 8.4).
  last_percent REAL,
  last_reading_at TEXT,
  installed_on TEXT,
  expected_life_days INTEGER,
  note TEXT,
  external_ref TEXT,               -- id Grocy, pour un import rejouable
  active INTEGER NOT NULL DEFAULT 1
);

-- AJOUT SEUL, comme `movement`.
CREATE TABLE battery_event (
  id INTEGER PRIMARY KEY,
  battery_id INTEGER NOT NULL REFERENCES battery(id),
  occurred_at TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('install','charge','replacement','removal')),
  movement_id INTEGER REFERENCES movement(id),    -- la rechange consommée, s'il y en a
  note TEXT,
  idempotency_key TEXT UNIQUE
);

CREATE TABLE equipment (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  device_id TEXT,                  -- l'appareil HA, quand il en a un
  location_id INTEGER REFERENCES location(id),
  brand TEXT, model TEXT, serial TEXT,
  purchased_on TEXT,               -- AAAA-MM-JJ, validé par validators.iso_date
  purchase_price REAL,             -- € TTC. N'écrit AUCUN mouvement (§ 11.2)
  warranty_months INTEGER,
  receipt_media_id TEXT,           -- chemin sous media/, jamais sous www/
  manual_url TEXT,
  manual_media_id TEXT,
  note TEXT,
  external_ref TEXT,
  active INTEGER NOT NULL DEFAULT 1
);

-- Le filtre du purificateur, le sac de l'aspirateur, la brosse latérale :
-- des produits du catalogue, rattachés à l'équipement qui les use.
CREATE TABLE equipment_consumable (
  id INTEGER PRIMARY KEY,
  equipment_id INTEGER NOT NULL REFERENCES equipment(id),
  product_id INTEGER NOT NULL REFERENCES product(id),
  role TEXT NOT NULL CHECK (role IN ('filter','bag','brush','cartridge','other')),
  label TEXT,                      -- « brosse principale », « filtre HEPA »
  entity_registry_id TEXT,         -- le capteur d'usure, même ancre qu'une pile
  low_value REAL, keep_value REAL, -- seuils, dans l'unité du capteur
  unit TEXT,                       -- 'percent' | 'minutes'
  expected_life_days INTEGER,
  installed_on TEXT,
  UNIQUE (equipment_id, product_id, role)
);

CREATE INDEX idx_battery_tracked ON battery(tracked, active);
CREATE UNIQUE INDEX idx_battery_anchor ON battery(entity_registry_id)
  WHERE entity_registry_id IS NOT NULL;
CREATE INDEX idx_battery_event_battery ON battery_event(battery_id, occurred_at);
CREATE INDEX idx_equipment_consumable ON equipment_consumable(equipment_id);

CREATE TRIGGER battery_event_no_update BEFORE UPDATE ON battery_event
BEGIN SELECT RAISE(ABORT, 'battery_event is append-only'); END;
CREATE TRIGGER battery_event_no_delete BEFORE DELETE ON battery_event
BEGIN SELECT RAISE(ABORT, 'battery_event is append-only'); END;
```

Aucune colonne n'est ajoutée à `product`, `article` ni `batch`. C'est le critère
qui prouve que la réutilisation du catalogue en est vraiment une : si une pile
avait eu besoin d'une colonne dans `product`, c'est que ce n'était pas un produit.

`m006` n'expose **pas** de hook `apply()`. Le remplissage vient d'un service
d'import (§ 16) : peupler 14 lignes depuis le registre demande `hass`, ce qu'une
migration qui tourne dans l'executor sur une connexion SQLite n'a pas — et ne
doit pas avoir.

## 7. Architecture

| Fichier | Rôle |
|---|---|
| `domain/maintenance.py` | **Nouveau.** `battery_plan()` et la fusion : purs, sans `hass`, sans SQLite |
| `storage/migrations/m006_equipment.py` | **Nouveau.** Quatre tables, index, déclencheurs d'ajout-seul |
| `storage/repositories.py` | Dépôts des quatre tables, écriture du dernier relevé |
| `application.py` | `declare_battery()`, `record_battery_event()`, `maintenance_plan()`, `equipment_*()` |
| `coordinator.py` | Résout les ancres du registre, relève les niveaux, mémorise le dernier relevé numérique |
| `sensor.py`, `services.py`, `services.yaml`, `websocket_api.py` | Trois capteurs, trois services, onze commandes |
| `import_grocy.py` | Un second import, `import_grocy_equipment` |
| `docs/raccord/maintenance.jinja` · `maintenance_sync.yaml` | **Nouveaux.** Copies de référence du raccord, jamais installées |
| `frontend/src/ecrans/piles.ts` · `equipements.ts` | **Nouveaux.** |

`domain/maintenance.py` ne connaît ni `hass`, ni le registre, ni SQLite : il
reçoit une liste de dictionnaires (une pile et son dernier relevé) et rend deux
listes. Même discipline qu'au lot 2 avec `domain/foodday.py`, qui reçoit son
fuseau en argument, et pour la même raison : la règle qui décide de créer ou de
fermer une tâche dans la vraie maison doit se tester sans démarrer Home
Assistant, et surtout sans la maison.

## 8. Les piles

### 8.1 L'ancre : pourquoi elle survit à un renommage

Quatre identifiants désignent « le capteur de pile du dimmer de la salle de
bain ». Ils ne se valent pas :

| Identifiant | Valeur réelle | Change quand… |
|---|---|---|
| `entity_id` | `sensor.interrupteur_sdb_batterie` | quelqu'un le renomme dans l'interface, en deux clics |
| `unique_id` | `0x001788010e77ad70_battery_zigbee2mqtt` | l'intégration change de convention, ou le matériel est remplacé |
| **`id` du registre** | `9c03f558eabb5b7691b37e0a43558e9f` | **jamais**, tant que l'entrée existe |
| `device_id` | `c695b2712501e0bc719d08fbe4b12102` | jamais, tant que l'appareil existe |

Le lot 5 stocke l'**`id` du registre d'entités** et le `device_id`. Il ne stocke
jamais l'`entity_id` : il le résout à chaque rafraîchissement du coordinateur.
Trois raisons, par ordre d'importance :

1. **Renommer une entité ne casse plus rien** — le défaut exact que CLAUDE.md
   reproche au raccord actuel : un `entity_id` écrit en dur dans une description,
   muet et sans erreur après un renommage. L'`id` du registre est un UUID que
   l'interface n'expose même pas.
2. **Le `device_id` porte le nom vivant.** Le libellé n'a plus à être bricolé
   depuis `friendly_name` par une chaîne de `replace()` (`'Batterie '`,
   `' Batterie'`, `' Battery level'`).
3. **Le `unique_id` n'est unique que par plate-forme.** Conservé pour le
   diagnostic, pas comme clé.

**Ce qui casse quand même, et c'est correct :** remplacer physiquement un
appareil crée un nouveau `device_id` et une nouvelle entrée de registre — c'est
un autre objet. Une migration d'intégration en frappe plusieurs d'un coup, comme
le passage de ZHA à Zigbee2MQTT du 2026-07-14. Dans ce cas la pile passe
`orphaned`, et **sa tâche n'est jamais fermée** (§ 17).

### 8.2 Trois natures, trois gestes

| `kind` | Ce que c'est | Verbe | Consomme une rechange |
|---|---|---|---|
| `primary` | Pile non rechargeable : CR2032, AAA alcaline | « Pile à changer » | oui |
| `rechargeable_cell` | Cellule qui sort de l'appareil et revient : les NiMH LADDA | « Piles à recharger » | non par défaut (§ 8.3) |
| `built_in` | Batterie soudée qu'on recharge sur place : serrure Aqara U200 Lite, rideaux Tuya | « Recharger » | jamais |

C'est le bon axe : ce qui distingue les trois cas n'est pas le nom de l'appareil,
c'est le **geste** — sortir une pile du placard, brancher un chargeur, ou
brancher l'appareil. Le motif actuel donne « Recharger » à trois appareils (deux
rideaux, la serrure) et « Pile à changer » aux onze autres ; parmi ces onze se
trouvent la molette BILRESA et les tags BLE, et **rien dans la maison n'a jamais
vérifié que les onze prennent une pile jetable.** Une colonne remplie une fois
règle ça ; un motif ne le réglera jamais.

Contraintes appliquées aux deux surfaces : `built_in` interdit `product_id` et
`battery_event.kind = 'replacement'` ; `primary` interdit
`battery_event.kind = 'charge'` ; `tracked = 0` exige `exclusion_reason` non vide.

`low_percent` (défaut 20) et `keep_percent` (défaut 25) sont **par pile**, avec
les valeurs d'aujourd'hui comme défaut pour que la bascule ne déplace aucun
seuil. Les rendre déclarables sert un cas concret : une CR2032 annonce 100 %
jusqu'à mourir en trois jours, une AAA descend lentement. L'invariant
`keep_percent >= low_percent` est vérifié à l'écriture — un seuil de maintien
plus bas que le seuil d'apparition ferait clignoter la tâche à chaque
synchronisation, exactement le piège que CLAUDE.md documente, et il devient ici
impossible à poser.

### 8.3 Le remplacement, et le lien avec le stock

`home_stock.record_battery_event` avec `kind: replacement` écrit une ligne
`battery_event` ; puis, **si** la pile porte un `product_id` et que
`consume_spare` n'est pas désactivé, un mouvement `consumption` de `cell_count`
unités sur ce produit, par le chemin FIFO normal du lot 0 — donc avec son prix
réel figé. `installed_on` prend la date, `last_percent` repasse à `NULL` : on ne
sait rien de la nouvelle pile tant que l'appareil n'a pas parlé.

L'idempotence traverse les deux tables : la clé du mouvement est celle de
l'événement préfixée par `_namespaced_key('battery_event', key)` — l'utilitaire
existe déjà dans `application.py`. Un rejeu depuis la file hors-ligne ne peut ni
créer deux événements, ni décrémenter deux fois le placard.

**Pourquoi `rechargeable_cell` ne consomme rien par défaut.** Les quatre LADDA
tournent entre le tiroir et trois capteurs de présence. Compter chaque rotation
comme une consommation viderait le stock de rechange en un an alors que les
quatre cellules sont toujours dans la maison, et déclencherait une rupture
mensongère — donc une ligne de courses pour des piles qu'on possède.
`consume_spare: true` reste disponible pour le jour où une cellule meurt. C'est
aussi la réponse à « pourquoi garder un produit de catalogue pour une pile
rechargeable » : on veut savoir qu'on en possède quatre, pas suivre un cycle.

### 8.4 Le capteur muet, et une amélioration sur l'existant

Le bloc 3 actuel produit « Pile HS ? — X » quand l'état est `unavailable` ou
`unknown` depuis au moins **1 h**, et son commentaire explique ce seuil très
court : `last_changed` d'une entité muette repart à l'heure du **dernier
démarrage de Home Assistant**, pas au début de la panne. Un seuil de 12 h avait
laissé le capteur de la porte d'entrée muet **9 jours** (2026-08-07 → 08-16) sans
jamais créer de tâche, faute d'un uptime assez long.

Le lot 5 supprime la cause plutôt que le symptôme. Le coordinateur écrit
`battery.last_reading_at` chaque fois qu'il voit un relevé numérique, **en
base** : « muet depuis N heures » se calcule alors sur une date qui survit à un
redémarrage, et le seuil peut redevenir honnête.

```python
# Zigbee2MQTT ne publie `offline` pour un appareil sur pile qu'après 25 h de
# silence (passive.timeout par défaut). En dessous, un capteur muet est un
# capteur qui n'a rien eu à dire. Ce seuil n'est plus contraint par l'uptime
# de Home Assistant depuis que last_reading_at vit en base.
BATTERY_MUTE_HOURS: Final = 26
```

Une pile jamais relevée (`last_reading_at IS NULL`, cas d'une déclaration
fraîche) ne produit **pas** d'item « Pile HS ? » ; elle alimente `keep`.

Les deux règles d'or de `maintenance.jinja` sont reprises telles quelles :
**jamais de fermeture sur un capteur indisponible** (état non numérique, entité
disparue, ancre orpheline → `keep` sans `items`) ; et **deux résumés à protéger
quand le capteur se tait**, « Pile HS ? — X » *et* « Pile à changer — X », parce
qu'une pile faible qui se tait ne prouve pas qu'elle a été changée.

## 9. Les exclusions, rendues déclaratives

Le motif `browser|pixel|brya|tablette|aspirateur` et la liste `piles_exclues`
disparaissent. À leur place, une ligne `battery` par capteur découvert, avec
`tracked = 0` et une `exclusion_reason` en clair : téléphone et Chromebook (leur
charge ne se gère pas ici) ; trois tablettes murales sur secteur ; deux capteurs
`browser_mod` qui doublonnent ces tablettes ; deux aspirateurs qui se rechargent
seuls ; trois capteurs HOBEIAN en NiMH (faux positifs de tension) ; les deux
batteries de la e208.

Ce que ce changement gagne, au-delà de l'esthétique :

1. **Le motif `peugeot|e208` redevient inoffensif.** CLAUDE.md avertit qu'un
   motif écarterait aussi `sensor.cle_de_la_peugeot_e208_batterie_ble`, un tag
   BLE à CR2032 légitimement suivi. Sans motif, l'avertissement n'a plus d'objet :
   deux lignes disent `tracked = 0`, une troisième `tracked = 1`, et aucune ne
   dépend de l'orthographe d'une autre.
2. **Un nouvel appareil ne devient pas une tâche par accident.** Aujourd'hui,
   ajouter un capteur sur pile crée une tâche au premier passage sous 20 %, avec
   un verbe deviné et sans format. Demain il est `tracked = NULL` : compté,
   listé « à déclarer », et **silencieux dans `todo.maintenance`**.
3. **Il ne disparaît pas non plus.** C'est le compromis, assumé : on échange
   « une tâche approximative tout de suite » contre « un compteur visible et une
   déclaration en deux appuis ». La règle du lot 0 § 12, « rien n'échoue
   silencieusement », est tenue par le compteur ; ce serait `tracked = NULL`
   **sans** compteur qui la violerait.

## 10. Le libellé, et le refus d'arbitrer

`battery.label` est **stocké**, pas dérivé. Trois conséquences.

**La chaîne de `replace()` disparaît** — trois motifs qui suivent la langue de
l'intégration d'origine et qu'il faut rallonger à chaque nouvelle marque.

**Les noms inversés cessent d'être un piège.** Le libellé est saisi une fois, en
regardant l'objet, et plus jamais recalculé. Le lot 5 ne décide **pas** lequel
des deux tags est la clé de la e208 : l'inventaire de CLAUDE.md dit MiTag, le
registre d'appareils dit « Sac » pour le MiTag, et aucune donnée du système ne
tranche. Ce que le lot 5 fait, c'est rendre la question **posable une fois pour
toutes** : l'écran Piles montre côte à côte le libellé, l'appareil, le modèle et
l'`entity_id` ; on corrige, c'est fini. Trancher à la place du propriétaire, sur
la foi d'un nom, serait reproduire l'erreur qu'on est en train de retirer.

**L'import sème le libellé rendu aujourd'hui, pas le libellé correct** (§ 13.4) :
c'est ce qui rend le déploiement neutre.

## 11. Les équipements

### 11.1 Ce qu'un équipement est ici

Un objet durable du foyer — les 34 lignes Grocy vont de la Cookeo aux poêles, en
passant par le purificateur, les tablettes et l'imprimante 3D. La ligne porte
quatre choses que Grocy ne portait pas : date d'achat, garantie, notice, et un
lien vers l'appareil Home Assistant.

Ce lien est **facultatif et informatif**. Une poêle n'a pas de `device_id` ; le
purificateur en a un. Exiger un `device_id` reviendrait à ne suivre que ce qui
est connecté, ce qui exclut d'emblée la moitié de la cuisine.

### 11.2 La garantie ne produit jamais de tâche

`warranty_ends_on` est **calculé** (`purchased_on + warranty_months`), jamais
stocké : une date dérivée stockée finit par diverger de ses sources. Elle
alimente `sensor.home_stock_warranty_next` et rien d'autre.

Elle n'entre pas dans `todo.maintenance`, pour une raison de fond : la liste
appartient au robot, qui **ferme** une tâche dès que la condition disparaît. Une
échéance de garantie disparaît le jour où elle est dépassée — la tâche se
fermerait donc toute seule le seul jour où elle aurait été utile. Une échéance se
regarde, elle ne se coche pas.

L'achat **n'écrit aucun mouvement** : `purchase_price` est une donnée de fiche.
Faire passer une télévision à 900 € dans un journal dont `cost_today` alimente la
dépense alimentaire du jour rendrait ce capteur inutilisable pour toujours — et
le journal est en ajout seul, donc la faute ne serait pas corrigible.

### 11.3 La notice : URL, et sinon `media/`

`manual_url` d'abord : une notice constructeur est un lien, à jour, sans poids,
et qui n'entre pas dans les sauvegardes. `manual_media_id` ensuite pour le PDF
qu'on possède : un chemin sous le dossier `media/` que le conteneur voit déjà
(cf. `docs/exploitation.md`). **Jamais sous `config/www/`** : tout ce qui s'y
trouve est servi sur `/local/` **sans authentification**, et une notice porte un
numéro de série.

**Aucun téléversement depuis le panneau.** Déposer un fichier dans `media/` est
une copie faite une ou deux fois par an ; construire un point d'entrée HTTP
authentifié, avec ses limites de taille, son typage et sa suppression, pour ce
geste-là serait du travail dont la mesure du § 4.3 dit qu'il ne servira pas :
0 des 34 équipements Grocy a une notice, alors que la colonne existait.

### 11.4 Les consommables non alimentaires

Il n'y a **pas** de modèle parallèle. Un filtre de purificateur, un sac
d'aspirateur, une brosse latérale, une tête de brosse à dents sont des `product`
avec `edible = 0`, avec leurs `article`, `barcode`, `batch` et prix. Le lot 5
ajoute **le lien** : « ce produit est le filtre du purificateur, son usure se lit
sur ce capteur, en dessous de 15 % il faut le changer ».

Ce que ce lien débloque sans une ligne de plus :

- **Le rayon existe déjà.** Le lot 1 a créé « Entretien et maison » et
  « Animalerie », et la cascade OFF interroge Open Products Facts. Un filtre se
  scanne comme un yaourt.
- **La rupture existe déjà.** Un consommable sous son `min_quantity` est un
  produit sous son seuil : il remonte dans `binary_sensor.home_stock_shortages`.
  C'est pour ça qu'aucun `binary_sensor.home_stock_spares_missing` n'est créé —
  ce serait la même donnée, sur la même tablette, sous deux noms.
- **La tâche devient actionnable.** « Purificateur — filtre à remplacer — 12 % »
  devient « … — 12 %, 1 en stock » ou « … — 12 %, **aucun en stock** ». La
  deuxième phrase est celle qui change ce qu'on fait le soir même.

**Les seuils restent dans `maintenance.jinja`.** Les blocs 1 et 2 (aspirateurs,
filtres air et eau) ne bougent pas : savoir qu'un filtre HEPA est usé à 12 % est
l'affaire du purificateur, pas d'un garde-manger. `home_stock` n'apporte à ces
blocs qu'**une** chose : la réponse à « en as-tu une d'avance ? ».

## 12. Surface Home Assistant

### 12.1 Services

| Service | Réponse | Rôle |
|---|---|---|
| `home_stock.maintenance_plan` | `ONLY` | `extra_items`, `extra_keep` → `{items, keep}` fusionné et enrichi |
| `home_stock.record_battery_event` | non | `battery_id`, `kind`, `occurred_at?`, `consume_spare?`, `note?`, `idempotency_key?` |
| `home_stock.import_grocy_equipment` | `ONLY` | Piles et équipements, `apply: false` par défaut (§ 16) |

`maintenance_plan` valide ses entrées comme n'importe quelle écriture : chaque
item de `extra_items` doit être un dictionnaire avec `summary` non vide,
`entity` et `description` facultatifs. Un item qu'il ne comprend pas est
**recopié tel quel**, jamais écarté : le service ne doit pas pouvoir faire
disparaître une tâche du purificateur parce que sa forme a évolué.

### 12.2 Websocket

| Commande | Effet |
|---|---|
| `home_stock/batteries/list` | Les piles déclarées : relevé, verbe, état de la rechange |
| `home_stock/batteries/discover` | Les capteurs `device_class: battery` sans ligne `battery`. N'écrit rien |
| `home_stock/battery/declare` · `update` · `event` | Déclaration, correction, recharge ou remplacement |
| `home_stock/equipment/list` · `get` · `create` · `update` | Fiche d'équipement |
| `home_stock/equipment/consumable/link` · `unlink` | Rattache un produit à un équipement |

Toute commande d'écriture accepte une `idempotency_key` : c'est la règle du
lot 1, et `tests/test_offline_queue_contract.py` la fait respecter tout seul en
**découvrant** les types de commande dans les sources TypeScript pour les
confronter aux schémas réels. Une commande de pile mise en file avec un schéma
strict sans clé fera échouer ce test le jour où elle est écrite.

**Aucune surface n'a le droit d'être la plus faible** (lot 2). Les bornes de
`low_percent`/`keep_percent`, les trois valeurs de `kind`, les quatre de
`battery_event.kind`, l'exigence d'`exclusion_reason`, le refus d'une recharge
sur une `primary` : tout passe par les helpers de `validators.py`
(`finite_float`, `bounded_int`, `bounded_text`, `iso_date`) et tout est vérifié
des deux côtés. `purchased_on` passe par `iso_date` pour la raison exacte que ce
helper documente : une date mal formée y devient un `ValueError` à chaque
rafraîchissement du coordinateur, et toutes les entités partent en `unavailable`.

### 12.3 Entités

| Entité | Rôle |
|---|---|
| `sensor.home_stock_batteries_low` | Piles suivies sous leur seuil. Attributs : la liste (libellé, %, verbe, format, rechange en stock) |
| `sensor.home_stock_batteries_undeclared` | Capteurs `device_class: battery` sans ligne `battery`. Attribut : leurs `entity_id` |
| `sensor.home_stock_warranty_next` | Jours jusqu'à la prochaine fin de garantie. Attribut : les échéances à venir |

Trois capteurs, pas quatorze — le lot 0 § 8 tient. Les trois sont activés
d'office : chacun peut valoir zéro, et un zéro est une information.

**Aucune entité `event` nouvelle, et aucun blueprint.** Le lot 2 en a créé parce
que rien n'annonçait les dates limites ; ici l'annonce existe et fonctionne — la
réconciliation horaire pousse les nouvelles tâches vers Bleuenn par
`personas_home.send_event`. Un second canal annoncerait deux fois la même pile
faible, et CLAUDE.md est explicite : « Bleuenn n'annonce que les nouvelles
tâches. Ne pas rajouter de rappel périodique. »

Noms affichés dans `translations/fr.json` (`batteries_low`,
`batteries_undeclared`, `warranty_next`) ; `entity_id`, code et schéma en
anglais, comme aux lots 0 à 2. `config/lovelace_garde_manger.yaml` gagne une
carte `entities` avec les trois capteurs, rien de plus : le détail d'une pile
demande un formulaire, ce que la répartition du lot 0 § 5.1 range du côté du
panneau.

### 12.4 Le panneau

`Ecran` gagne `'piles'` et `'equipements'` ; la barre de navigation les expose,
et le garde-fou du lot 1 (quitter le rangement avec des lignes en attente demande
une confirmation) s'applique à ces cibles comme aux autres.

**Piles.** Les piles suivies, triées par niveau croissant : libellé,
pourcentage, verbe, format de rechange et son stock. Un appui ouvre la fiche —
seuils, nature, rechange, historique des événements, et le bouton « je viens de
la changer » / « … de la recharger » selon `kind`. En tête, quand il y en a, le
bloc « à déclarer » : libellé proposé (nom de l'appareil), modèle, `entity_id`,
et deux boutons « suivre » / « ignorer », ignorer demandant un motif puisque la
colonne l'exige.

**Équipements.** Liste par emplacement ; la fiche porte marque, modèle, numéro de
série, date d'achat, garantie avec les jours restants, lien vers la notice, et
les consommables rattachés avec leur usure et leur stock.

Contraintes de rendu inchangées : 412 × 915 et 1280 × 800, cibles ≥ 48 px,
contraste ≥ 4,5:1, aucun débordement, aucun appui long. Toutes les écritures
passent par la file hors-ligne du lot 1.

## 13. La reprise de `maintenance.jinja`

### 13.1 La décision

| Option | Ce que c'est | Écartée parce que |
|---|---|---|
| A | `todo.home_stock_batteries` imitant `todo.grocy_batteries`, `entity_id` dans la description | Reproduit à l'identique la fragilité que CLAUDE.md dénonce, pour économiser trois lignes de YAML |
| B | `home_stock` écrit directement dans `todo.maintenance` | Deux robots sur une liste dont CLAUDE.md dit qu'elle appartient à un seul : la réconciliation fermerait ce que l'autre vient d'ajouter |
| **C** | **Un service à réponse qui rend `{items, keep}`** | **Retenue** |

`home_stock.maintenance_plan` prend le plan du macro (`extra_items`,
`extra_keep`) et rend le plan **fusionné et enrichi** : en un appel, ses propres
items de pile, les descriptions enrichies des items du macro, et deux listes
d'hystérésis cohérentes. Les deux arguments sont **facultatifs** — appelé nu, le
service rend les piles seules. `home_stock` ne dépend donc pas de la forme du
macro ; la fusion est un service rendu, pas un couplage.

### 13.2 Le diff attendu sur `maintenance.jinja`

Copie de référence : `docs/raccord/maintenance.jinja`, appliquée à la main.

**Supprimé — la totalité du bloc 3 « Piles », lignes 57 à 110**, en-tête de
commentaire compris, ainsi que les variables `piles_exclues` et `motifs_exclus`.
Le macro perd 54 lignes et ne parcourt plus `states.sensor`.

**Inchangé —** les blocs 1 (consommables aspirateurs), 2 (filtres air et eau),
4 (plantes) et 5 (mises à jour manuelles), avec leurs seuils, leur hystérésis et
leurs branches « capteur muet ». Le contrat de sortie ne change pas :
`{"items": [...], "keep": [...]}`, chaque item portant `summary`, `description`
et `entity`.

**Ajouté — rien.** Le macro ne connaît pas `home_stock` ; c'est l'automation qui
appelle le service. Un macro Jinja ne peut pas appeler un service, et lui faire
lire un attribut d'entité aurait ramené la donnée dans le `recorder` pour rien.

**La regex des mises à jour manuelles n'est pas touchée** — le bloc 5 conserve
`firmware|micrologiciel|system_apt|docker_homeassistant` — mais elle est
**verrouillée** : CLAUDE.md rappelle qu'elle est dupliquée dans l'automation
« Système - Mises à jour automatiques », et un test compare désormais les deux
copies de référence (§ 18.3). C'est gratuit puisqu'on écrit déjà ces fichiers, et
ça ferme une dette ouverte depuis le 2026-07-31.

### 13.3 Le diff attendu sur l'automation

Copie de référence : `docs/raccord/maintenance_sync.yaml`.

**Supprimé —** l'action `todo.get_items` sur `todo.grocy_batteries` avec son
`continue_on_error` et son `response_variable: grocy` ; et la totalité du
template `voulu`, qui cherchait l'`entity_id` d'un item dans les descriptions
Grocy pour en dériver un suffixe par `g.description.split(' - ')[0]`.

**Ajouté —** à la place :

```yaml
    - action: home_stock.maintenance_plan
      continue_on_error: true
      data:
        extra_items: "{{ plan['items'] }}"
        extra_keep: "{{ plan['keep'] }}"
      response_variable: stock
    - variables:
        # Service injoignable (intégration déchargée, HA qui démarre) :
        # on retombe sur le plan du macro seul, et on DÉSARME la fermeture.
        fusionne: "{{ stock | default(none, true) }}"
        voulu: "{{ fusionne.items if fusionne else plan['items'] }}"
        garde: "{{ fusionne.keep if fusionne else plan['keep'] }}"
        peut_fermer: "{{ fusionne is not none }}"
```

**Modifié —** `a_fermer` lit `garde` au lieu de `plan['keep']`, et la boucle de
fermeture est enveloppée dans un `if` sur `peut_fermer`.

### 13.4 Les deux pièges du raccord

**Piège 1 — le service absent ne doit pas fermer les tâches.** C'est le risque le
plus grave du lot, et il n'existe pas aujourd'hui : Grocy arrêté ne coûte qu'un
suffixe, tandis que `home_stock` absent ferait disparaître les items de pile de
`items` **et** de `keep` — `a_fermer` les contiendrait toutes, et une seule
synchronisation à 5 h 05 refermerait les 14 tâches de pile de la maison. Le
garde-fou est `peut_fermer` : **quand le plan est incomplet, on a le droit
d'ajouter et de rafraîchir, jamais de fermer.** C'est la règle que CLAUDE.md
énonce pour un capteur (« on ne ferme une tâche que sur une mesure qui prouve que
la condition a disparu »), appliquée au plan entier.

**Piège 2 — les résumés doivent rester identiques au caractère près.** La
réconciliation apparie sur `summary` : un « Piles à changer — Velux (CH) » là où
il y avait « Pile à changer — Velux (CH) » ferme l'ancienne tâche, en crée une
nouvelle, et déclenche l'annonce de Bleuenn. D'où deux exigences : la grammaire
reste `«{verbe} — {libellé}»` sans exception, et **l'import sème `battery.label`
avec le libellé rendu aujourd'hui** par la chaîne de `replace()` du macro, pas
avec le libellé souhaité. La première synchronisation après déploiement est alors
strictement neutre ; corriger un libellé ensuite est une décision, avec sa churn
d'une tâche, prise en connaissance de cause.

Circonstance favorable (§ 4.1) : au 2026-08-21 aucune des 14 piles n'est sous son
seuil et aucune tâche de pile n'est ouverte. Le déploiement peut se faire sans
qu'aucune tâche existante ne soit en jeu.

## 14. Import depuis Grocy

`home_stock.import_grocy_equipment`, même discipline que `import_grocy_catalog` :
lit une **copie** de `grocy.db` en lecture seule, simulation par défaut,
rejouable, rapport de contrôle obligatoire. `external_ref` garde l'id Grocy des
deux côtés, ce qui rend le rejeu sûr et le lot 7 trivial.

Des 26 lignes `batteries` :

1. **18 lignes de rechange → 5 produits.** Regroupées par format (LADDA AAA,
   9 V, CR2032, C/LR14, AA), chacune devient un `product` `edible = 0`,
   `base_unit = 'piece'`, rayon « Entretien et maison », avec son article
   générique (lot 0 § 6.3) et un `batch` de 4, 5, 3, 4 et 2 unités, sans prix.
   `min_quantity` est proposé à 2 et se règle ensuite.
2. **5 lignes avec `entity_id` → 5 lignes `battery`**, format lu dans la
   description (`1x CR2032`, `2x AAA rechargeable`), `cell_count` lu dans le
   `Nx`, `kind` déduit de la présence du mot « rechargeable ».
3. **3 lignes d'appareils retirés → rapportées, non importées.** Leurs
   descriptions le disent (« appareil retiré, plus aucune entité HA, vérifié
   2026-07-31 ») ; les importer créerait trois piles orphelines dès le premier
   jour.

Des 34 lignes `equipment` : une ligne chacune, `name` et `note` repris,
`device_id` laissé vide. **Rien n'est deviné** — date d'achat, garantie et
notice n'existent pas dans Grocy (§ 4.3), et un appariement automatique du nom
vers le `device_registry` produirait des liens plausibles et faux :
« Télévision » désigne trois appareils différents dans ce registre.

Puis un **balayage du registre** peuple les lignes manquantes : chaque `sensor`
`device_class: battery` sans ligne obtient `tracked = NULL`, sauf celles que le
rapport propose de pré-remplir en `tracked = 0` d'après les exclusions actuelles
(§ 9) — la seule information que le macro possède et qu'il faut sauver avant de
le raccourcir.

**Contrôle de sortie, obligatoire**, dans l'esprit du lot 0 § 10. L'import n'est
réputé réussi que si le rapport ne contient : 0 pile sans libellé ; 0 pile
`tracked = 1` sans `kind` ; 0 pile `built_in` avec un `product_id` ; 0
`entity_registry_id` en double ; 0 `keep_percent < low_percent` ; et **0 écart
entre les résumés que produirait le nouveau plan et ceux qu'aurait produits le
bloc 3 sur le même état** — ce dernier contrôle garantit le déploiement neutre
du § 13.4.

## 15. Erreurs

| Situation | Comportement |
|---|---|
| Ancre orpheline (entrée de registre disparue) | La pile passe `orphaned` : `keep` sans `items`, **aucune tâche fermée**, comptée en attribut de `batteries_low` |
| Appareil remplacé, nouveau `device_id` | Nouvelle entrée « à déclarer », l'ancienne devient `orphaned`. Aucun appariement automatique |
| État non numérique (`unavailable`, `unknown`, texte) | `keep` sans `items`, comme le macro le fait déjà |
| Capteur muet depuis plus de `BATTERY_MUTE_HOURS` | Item « Pile HS ? — X », et les **deux** résumés protégés |
| Pile jamais relevée | Ni item de niveau, ni « Pile HS ? ». `keep` seulement |
| Remplacement sans rechange en stock | L'événement s'écrit ; la consommation est refusée par `InsufficientStock` en français, et le refus est **visible** |
| Recharge sur une `primary`, remplacement sur une `built_in`, `tracked = 0` sans motif | Refusés aux deux surfaces, avant écriture |
| `home_stock.maintenance_plan` injoignable | Repli sur le plan du macro, **fermeture désarmée** (§ 13.4) |
| Rejeu d'un `battery/event` | La clé rend le même `event_id` : ni double événement, ni double décrément |
| Notice pointant un fichier absent de `media/` | Le lien est signalé introuvable ; aucune entité ne devient indisponible pour autant |

## 16. Tests

### 16.1 Python pur — le gros du lot

`domain/maintenance.py` se teste sur des dictionnaires, sans Home Assistant :

- hystérésis : à 22 % avec `low = 20` / `keep = 25`, pas d'item et le résumé
  reste dans `keep` ; à 26 %, il en sort ;
- les trois `kind` produisent les trois verbes ;
- capteur muet : les deux résumés protégés, le seuil de 26 h, la pile jamais
  relevée qui ne produit pas d'item ; ancre orpheline en `keep` sans `items` ;
- **`items ⊆ keep`** — invariant global qui doit tenir sur tous les cas ci-dessus,
  parce que sa violation est exactement le clignotement de tâche que CLAUDE.md
  décrit ;
- fusion : un item de `extra_items` non reconnu est recopié tel quel, un item
  avec une `entity` connue reçoit son suffixe de rechange, l'ordre est stable.

### 16.2 Couche Home Assistant

Via `./scripts/test.sh` (`pytest-homeassistant-custom-component`) :

- `m006` : les quatre tables et leurs index, les déclencheurs qui refusent
  `UPDATE` et `DELETE` sur `battery_event`, la migration rejouable, appliquée à
  une **copie de la base réelle du lot 2** — pas à une base vide, comme au lot 1 ;
- validation croisée : pour chaque contrainte du § 12.2, un test service **et**
  un test websocket, qui doivent refuser de la même façon ;
- `record_battery_event` : idempotence traversant `battery_event` et `movement` ;
  `rechargeable_cell` qui ne consomme rien par défaut ; `consume_spare: true` qui
  consomme ; stock insuffisant qui écrit quand même l'événement ;
- coordinateur : `last_reading_at` écrit sur un relevé numérique, **pas** écrit
  sur `unavailable`, conservé à travers un redémarrage simulé — c'est le test qui
  prouve l'amélioration du § 8.4 ;
- capteurs : les trois publient leurs attributs, `batteries_undeclared` compte
  juste après l'ajout d'un capteur de pile inconnu ;
- import : deux passages successifs ne créent rien ; les 3 appareils retirés sont
  rapportés et non importés ; les 18 cellules donnent 5 produits.

### 16.3 Le raccord, sans toucher l'instance vivante

C'est le point délicat : tester un fichier qui vit dans
`/opt/nivuus/HomeAssistant/config/` depuis un dépôt qui n'a le droit ni d'y
écrire, ni de redémarrer quoi que ce soit. La méthode : **les copies de référence
sont dans le dépôt**, et le test les monte dans un Home Assistant de test.

1. Le test écrit `docs/raccord/maintenance.jinja` dans
   `hass.config.path('custom_templates/')` — un répertoire temporaire, jamais
   celui de la maison.
2. Il peuple le `hass` de test depuis `tests/fixtures/maintenance/etats.json`,
   capturé une fois depuis `ha_sync/entities/sensor.json` (les 28 capteurs de
   pile, les filtres, les plantes, les `update`). Un instantané versionné, pas
   une lecture de l'instance.
3. Il rend `{% from 'maintenance.jinja' import maintenance_plan %}{{ maintenance_plan() }}`
   par `homeassistant.helpers.template.Template` et vérifie : JSON valide avec
   exactement `items` et `keep` ; **aucune occurrence de `grocy`** ; aucune
   occurrence de `device_class` ni de `piles_exclues` (le bloc 3 a bien disparu) ;
   et les blocs 1, 2, 4 et 5 produisent exactement ce que produit le macro
   **actuel** sur les mêmes états — une copie de l'avant est versionnée dans
   `tests/fixtures/maintenance/avant.jinja`, ce qui prouve que la suppression n'a
   rien emporté d'autre.
4. Un test appelle `home_stock.maintenance_plan` avec ce rendu comme
   `extra_items`/`extra_keep` et vérifie la fusion.
5. **Déploiement neutre** : sur les états de la fixture, l'ensemble des `summary`
   du plan fusionné est **égal** à celui du macro d'avant. C'est le test qui
   empêche les 14 tâches de se fermer et de se rouvrir le jour du basculement.
6. **Regex dupliquée** : `firmware|micrologiciel|system_apt|docker_homeassistant`
   apparaît à l'identique dans les deux fichiers de référence ; un test compare
   les deux chaînes extraites.

**Interdit, repris tel quel du lot 2 :** rien ne touche l'instance vivante. Pas
de `docker compose`, pas de redémarrage, pas de rechargement d'intégration, pas
de lecture de jeton, aucune écriture dans `config/`. Le seul accès à la maison
est la **lecture** de `ha_sync/` et d'une copie de `grocy.db`, faite une fois et
versionnée en fixture.

### 16.4 Front

`piles.test.ts` (tri par niveau, les trois verbes, le bloc « à déclarer », le
refus d'ignorer sans motif, l'écriture par la file hors-ligne) ;
`equipements.test.ts` (garantie expirée / à venir / absente, notice absente,
consommable sans stock) ; `outils/verifier-rendu.mjs`, deux scénarios de plus aux
deux formats, avec la vérification préalable que l'écran visé est bien atteint.

## 17. Ce que le lot 5 prépare pour le lot 6

**La ligne de synthèse ne bouge pas.** `tools/wallpanel-app/src/pieces.ts`
affiche déjà `todo.maintenance` comme « {n} tâche{s} d'entretien » sur les trois
pièces, et `src/rendu/taches.ts` coche en deux appuis. Après le lot 5 le contenu
des tâches change, l'entité et son compte ne changent pas : **les tablettes ne
demandent aucune modification**, et c'est un objectif du raccord, pas un heureux
hasard. Une entité `home_stock` en remplacement de `todo.maintenance` aurait
imposé un déploiement de `wallpanel-app`.

**Le vocal a déjà sa porte.** « Il me reste des CR2032 ? » se répond par
`home_stock.query_stock`, qui existe depuis le lot 0 et fonctionne sur un produit
de rechange sans une ligne de plus — troisième conséquence du choix « la rechange
est un produit ». Le lot 6 n'aura qu'à écrire l'intent.

**Ce que le lot 6 devra ajouter :** une ligne « n piles faibles » si elle se
révèle utile, alimentée par `sensor.home_stock_batteries_low` dont l'attribut
porte déjà la liste — donc sans template Jinja côté tablette, ce que
`wallpanel-app` ne saurait de toute façon pas faire puisqu'il parle websocket et
non Lovelace.

## 18. Points différés

| Sujet | Lot | Raison |
|---|---|---|
| **Les 6 *chores* Grocy** (litière, fontaine, croquettes, poubelles) | à trancher au lot 7 | La feuille de route du lot 0 ne les mentionne nulle part : ce sont des tâches **périodiques**, pas conditionnelles, et `todo.maintenance` est piloté par des conditions. Soit elles meurent avec Grocy, soit elles deviennent une `local_todo` et une automation horaire. **C'est un trou de la feuille de route, pas un choix** — à poser avant l'extinction |
| Identité par cellule physique, compteur de cycles par pile | — | Modélisé par Grocy, **0 ligne en six mois** (§ 4.3). Les événements par place suffisent |
| Téléversement de notice ou de ticket depuis le panneau | — | 0 des 34 équipements Grocy a une notice alors que la colonne existait |
| Déduction du format de pile depuis le modèle de l'appareil | — | Aucune source fiable ; une devinette produirait une liste de courses fausse |
| Rattachement automatique équipement ↔ `device_registry` par le nom | — | Trois appareils s'appellent « Télévision » dans ce registre |
| Amortissement, valeur résiduelle, assurance | — | Aucun usage identifié dans le foyer |
| Alerte de fin de garantie annoncée à la voix | 6 | Le capteur et ses attributs existent ; l'annonce est une décision de surface |
| Déplacer les seuils des blocs 1, 2 et 4 vers `home_stock` | — | Frontière de responsabilité (§ 11.4) : `home_stock` sait ce qu'il y a dans le placard, pas comment va l'aspirateur |

*Rédigé le 2026-08-21.*
