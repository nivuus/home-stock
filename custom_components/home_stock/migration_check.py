"""The switchover checks: eleven of them, and every one has a floor.

> **La leçon du lot 6, recopiée pour qu'elle ne se reperde pas.** Son
> vérificateur ouvrait les pages contre l'instance réelle ; les commandes
> websocket n'existaient pas encore, « il mesure un écran vide et déclare que
> tout va bien ». **Un contrôle qui passe à vide est pire que pas de
> contrôle** : il transforme une absence de donnée en preuve de succès.

Every check therefore carries a FLOOR: a threshold below which it fails
*because it measured nothing*, independently of any gap. **A check comparing 0
to 0 is red, never green.** That is the heart of this lot, and the floor is
evaluated FIRST, before any comparison.

This module stops nothing and starts nothing. The component never shuts Grocy
down — stopping one of the household's containers is a human gesture — and a
test scans this source to make sure it could not.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, NamedTuple

from .const import (
    GROCY_COPY_MAX_AGE_HOURS,
    GROCY_FREEZE_TOLERANCE_HOURS,
    GROCY_NEVER_EXPIRES,
    GROCY_STOCK_REF_PREFIX,
    MIGRATION_CHECKS,
    MIGRATION_DETAIL_CAP,
    MIGRATION_QUANTITY_TOLERANCE,
    REASON_PURCHASE,
)
from .grocy.units import base_unit

SCHEMA_VERSION_EXPECTED = 8

# Les contrôles dont un verdict vert exige un acquittement NOMINATIF. Un
# bouton « tout va bien » finit toujours par être pressé sans regarder.
_NEEDS_ACK = ("C4", "C8")


class CheckResult(NamedTuple):
    """One check, its two counts, its gap and its verdict."""

    code: str
    label: str
    grocy_count: int
    home_count: int
    gap: int
    verdict: str            # "ok" | "empty" | "gap" | "unacknowledged"
    blocking: bool
    details: list[str]


@dataclass
class CheckReport:
    checks: list[CheckResult] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    archive_path: str | None = None

    @property
    def ok(self) -> bool:
        return not self.blocking

    def as_dict(self) -> dict[str, Any]:
        return {
            "checks": [c._asdict() for c in self.checks],
            "blocking": self.blocking,
            "archive_path": self.archive_path,
            "ok": self.ok,
        }


@dataclass
class Measures:
    """Everything measured once, so no check re-reads a table on its own."""

    grocy_present: bool = False
    copy_age_hours: float | None = None
    grocy_last_write: str | None = None
    copy_taken_at: str | None = None
    schema_version: int = 0

    grocy_stock: int = 0
    home_batches: int = 0
    quantity_gaps: list[str] = field(default_factory=list)
    date_gaps: list[str] = field(default_factory=list)
    sentinels: int = 0
    dated_batches: int = 0
    unpriced: int = 0
    dropped_prices: list[tuple[str, str]] = field(default_factory=list)
    entry_movements: int = 0
    movement_gaps: list[str] = field(default_factory=list)
    polluted_movements: list[str] = field(default_factory=list)

    grocy_batteries: int = 0
    grocy_equipment: int = 0
    home_batteries: int = 0
    home_equipment: int = 0
    battery_gaps: list[str] = field(default_factory=list)

    recipes: int = 0
    ingredients: int = 0
    instructions: int = 0
    timers: int = 0
    phantoms: list[str] = field(default_factory=list)
    unmatched_lines: list[tuple[str, str]] = field(default_factory=list)

    picture_dir_seen: bool = False
    pictures_referenced: int = 0
    pictures_present: int = 0
    picture_gaps: list[str] = field(default_factory=list)

    meals: int = 0
    meal_recipes: int = 0
    list_items: int = 0
    plan_gaps: list[str] = field(default_factory=list)

    config_seen: bool = False
    residues: list[str] = field(default_factory=list)


# Le plancher AVANT la comparaison. Un contrôle qui compare 0 à 0 est rouge,
# jamais vert : le lot 6 a démontré qu'un vérificateur qui mesure du vide
# déclare tout conforme, et transforme une absence de donnée en preuve de
# succès. Chaque entrée rend True quand il y a de quoi mesurer.
FLOORS: dict[str, Callable[[Measures], bool]] = {
    # `grocy_last_write` fait partie du plancher : une copie présente mais
    # vide ne permet PAS de dire que Grocy est gelé, elle permet seulement de
    # dire qu'on n'en sait rien. Sans ça, C0 passait au vert sur une copie
    # sans une seule ligne — le défaut même que ce lot existe pour empêcher,
    # trouvé par le test des deux bases vides.
    "C0": lambda m: (m.grocy_present and m.schema_version > 0
                     and m.grocy_last_write is not None),
    "C1": lambda m: m.grocy_stock > 0 and m.home_batches > 0,
    "C2": lambda m: m.grocy_stock > 0 and m.home_batches > 0,
    "C3": lambda m: m.dated_batches > 0,
    "C4": lambda m: m.home_batches > 0,
    "C5": lambda m: m.entry_movements > 0,
    "C6": lambda m: m.entry_movements > 0,
    # Sans cet import, le raccord du lot 5 FERME 14 tâches de pile au lieu de
    # les déplacer. C'est la seule dépendance d'ordre du lot 5 vers le lot 7,
    # et le lot 7 la VÉRIFIE — il ne refait pas l'import.
    "C7": lambda m: m.home_batteries > 0 and m.home_equipment > 0,
    "C8": lambda m: m.recipes > 0,
    # C9 sort de la base. Un contrôle qui ne fait que relire des colonnes ne
    # prouve RIEN sur des fichiers : les image_url peuvent être parfaitement
    # cohérentes et pointer un dossier vide.
    "C9": lambda m: m.picture_dir_seen and m.pictures_present > 0,
    "C10": lambda m: m.meals > 0,
    # Quand le dossier n'existe pas, C11 ne prétend pas que la maison est
    # propre : il dit qu'il n'a pas su regarder.
    "C11": lambda m: m.config_seen,
}

# Ce que C11 cherche, en LECTURE SEULE, dans une copie du dossier config qu'on
# lui désigne. Il n'écrit jamais rien, ne recharge rien, et n'applique JAMAIS
# le raccord du lot 5.
GROCY_RESIDUES = (
    ("todo.grocy_batteries", "une liste de piles que l'import du lot 5 remplace"),
    ("grocy_shopping_list", "la liste de courses de Grocy"),
    ("sensor.grocy_meal_plan", "le planning de Grocy"),
    ("grocy-recipes.html", "la page de recettes servie depuis www/"),
    ("grocy-scanner.html", "le scanner servi depuis www/"),
)
# Le bloc 3 du .jinja : c'est lui que le raccord retire, et sa présence dit à
# elle seule que le raccord n'est pas posé.
JINJA_BATTERY_BLOCK = "3. Piles"


def _open_grocy(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _parse(moment: str | None) -> datetime | None:
    if not moment:
        return None
    try:
        return datetime.fromisoformat(moment.replace(" ", "T"))
    except ValueError:
        return None


def _measure(db, grocy_path: str, *, now: datetime) -> Measures:
    """Read both databases once. Nothing here decides anything."""
    measures = Measures()
    conn = db.read()
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    measures.schema_version = (row["v"] if row and row["v"] else 0) or 0

    chemin = Path(grocy_path)
    if not chemin.exists():
        return measures
    measures.grocy_present = True
    prise = datetime.fromtimestamp(chemin.stat().st_mtime)
    measures.copy_taken_at = prise.isoformat(timespec="seconds")
    measures.copy_age_hours = (
        now.replace(tzinfo=None) - prise).total_seconds() / 3600

    grocy = _open_grocy(grocy_path)
    try:
        _measure_freeze(grocy, measures)
        _measure_equipment(conn, grocy, measures)
        _measure_recipes(conn, measures)
        _measure_plan(conn, measures)
        if measures.schema_version >= SCHEMA_VERSION_EXPECTED:
            # Avant m008 il n'y a pas de batch.external_ref : les dix autres
            # contrôles n'ont rien à lire, et leur plancher les rendra `empty`
            # de lui-même. C0 dit pourquoi, et le dit en premier.
            _measure_stock(conn, grocy, measures)
            _measure_movements(conn, measures)
    finally:
        grocy.close()
    return measures


def _measure_freeze(grocy, measures: Measures) -> None:
    """The last moment Grocy wrote anything, across the four tables that move.

    A write after the copy invalidates all ten other checks: C0 says so before
    they lie.
    """
    derniers = []
    for table in ("stock", "stock_log", "products", "meal_plan"):
        try:
            row = grocy.execute(
                f"SELECT MAX(row_created_timestamp) AS m FROM {table}").fetchone()
        except sqlite3.Error:
            continue
        if row and row["m"]:
            derniers.append(row["m"])
    measures.grocy_last_write = max(derniers) if derniers else None


def _measure_stock(conn, grocy, measures: Measures) -> None:
    measures.grocy_stock = grocy.execute(
        "SELECT COUNT(*) AS n FROM stock").fetchone()["n"]

    unites = {row["id"]: row["name"] for row in
              grocy.execute("SELECT id, name FROM quantity_units")}
    attendus: dict[str, dict[str, Any]] = {}
    for row in grocy.execute(
        "SELECT s.id AS id, s.amount AS amount,"
        "       s.best_before_date AS best_before_date, s.price AS price,"
        "       s.note AS note, prod.name AS product_name,"
        "       prod.qu_id_stock AS qu_id_stock"
        " FROM stock AS s JOIN products AS prod ON prod.id = s.product_id"
    ):
        mappee = base_unit(unites.get(row["qu_id_stock"], "?"))
        attendus[f"{GROCY_STOCK_REF_PREFIX}{row['id']}"] = {
            "quantity": (row["amount"] * mappee[1]) if mappee else None,
            "best_before": row["best_before_date"],
            "name": row["product_name"],
            "note": row["note"],
            "price": row["price"],
            "amount": row["amount"],
        }

    presents: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        "SELECT bat.external_ref AS ref, bat.remaining AS remaining,"
        "       bat.best_before AS best_before,"
        "       bat.price_per_base_unit AS price"
        " FROM batch AS bat WHERE bat.external_ref IS NOT NULL"
    ):
        presents[row["ref"]] = dict(row)
    measures.home_batches = len(presents)

    for ref, attendu in sorted(attendus.items()):
        present = presents.get(ref)
        if present is None:
            measures.quantity_gaps.append(
                f"{ref} ({attendu['name']}) : aucun lot importé")
            measures.date_gaps.append(f"{ref} ({attendu['name']}) : absent")
            continue
        cible = attendu["quantity"]
        if cible is None:
            measures.quantity_gaps.append(
                f"{ref} ({attendu['name']}) : unité Grocy non convertible")
        elif abs(present["remaining"] - max(cible, 0.0)) > MIGRATION_QUANTITY_TOLERANCE \
                and not (cible < 0.001 and present["remaining"] == 0.0):
            measures.quantity_gaps.append(
                f"{ref} ({attendu['name']}) : {present['remaining']} en base"
                f" contre {cible} attendus")

        sentinelle = attendu["best_before"] == GROCY_NEVER_EXPIRES
        if sentinelle:
            measures.sentinels += 1
            if present["best_before"] is not None:
                measures.date_gaps.append(
                    f"{ref} ({attendu['name']}) : la sentinelle"
                    f" {GROCY_NEVER_EXPIRES} aurait dû devenir NULL")
        else:
            measures.dated_batches += 1
            if present["best_before"] != attendu["best_before"]:
                measures.date_gaps.append(
                    f"{ref} ({attendu['name']}) : DLC"
                    f" {present['best_before']} contre {attendu['best_before']}")

        if present["price"] is None:
            measures.unpriced += 1
        if attendu["price"] and attendu["amount"] * attendu["price"] > 20.0:
            measures.dropped_prices.append(
                (ref, f"{ref} ({attendu['name']}) : prix écarté —"
                      f" {attendu['amount']} × {attendu['price']} ="
                      f" {attendu['amount'] * attendu['price']:.2f} EUR."
                      f" Note Grocy : « {attendu['note'] or 'sans note'} »"))

    for ref in sorted(set(presents) - set(attendus)):
        measures.quantity_gaps.append(f"{ref} : lot importé sans ligne Grocy")


def _measure_movements(conn, measures: Measures) -> None:
    """One entry movement per batch, and not one euro on any of them."""
    measures.entry_movements = conn.execute(
        "SELECT COUNT(*) AS n FROM movement WHERE reason = ?"
        "   AND idempotency_key LIKE ?",
        (REASON_PURCHASE, f"{GROCY_STOCK_REF_PREFIX}%")).fetchone()["n"]

    for row in conn.execute(
        "SELECT bat.external_ref AS ref FROM batch AS bat"
        " WHERE bat.external_ref IS NOT NULL"
        "   AND NOT EXISTS (SELECT 1 FROM movement AS mv"
        "                    WHERE mv.idempotency_key = bat.external_ref)"
    ):
        measures.movement_gaps.append(
            f"{row['ref']} : lot sans mouvement d'entrée")

    for row in conn.execute(
        "SELECT prod.name AS name, prod.id AS pid,"
        "       (SELECT COALESCE(SUM(mv.quantity), 0) FROM movement AS mv"
        "         WHERE mv.product_id = prod.id AND mv.reason = ?"
        "           AND mv.idempotency_key LIKE ?) AS entree,"
        "       (SELECT COALESCE(SUM(bat.remaining), 0) FROM batch AS bat"
        "         JOIN article AS art ON art.id = bat.article_id"
        "         WHERE art.product_id = prod.id"
        "           AND bat.external_ref IS NOT NULL) AS restant"
        " FROM product AS prod WHERE prod.external_ref IS NOT NULL",
        (REASON_PURCHASE, f"{GROCY_STOCK_REF_PREFIX}%")
    ):
        if abs(row["entree"] - row["restant"]) > MIGRATION_QUANTITY_TOLERANCE:
            measures.movement_gaps.append(
                f"{row['name']} : {row['entree']} entrés contre"
                f" {row['restant']} en stock")

    for row in conn.execute(
        "SELECT mv.idempotency_key AS key FROM movement AS mv"
        " WHERE mv.reason = ? AND mv.idempotency_key LIKE ?"
        "   AND (mv.kcal IS NOT NULL OR mv.cost IS NOT NULL)",
        (REASON_PURCHASE, f"{GROCY_STOCK_REF_PREFIX}%")
    ):
        measures.polluted_movements.append(
            f"{row['key']} : un mouvement d'entrée porte des calories ou un"
            " coût — les trois cumuls sauteraient d'un bloc")


def _measure_equipment(conn, grocy, measures: Measures) -> None:
    """What lot 5's import produced. This module VERIFIES it; it never redoes
    it — a check that re-runs the thing it checks proves only that it can."""
    try:
        measures.grocy_batteries = grocy.execute(
            "SELECT COUNT(*) AS n FROM batteries WHERE active = 1").fetchone()["n"]
    except sqlite3.Error:
        measures.grocy_batteries = 0
    # Les piles ne se comptent PAS ligne à ligne contre Grocy : l'import du
    # lot 5 part du registre d'entités de Home Assistant et se sert des lignes
    # Grocy pour renseigner ce qu'il trouve. Les deux nombres n'ont aucune
    # raison d'être égaux, et exiger l'égalité ferait échouer C7 parce que
    # l'import a bien fonctionné. Ce qui se compare ligne à ligne, c'est
    # l'équipement, qui est une recopie.
    measures.home_batteries = conn.execute(
        "SELECT COUNT(*) AS n FROM battery").fetchone()["n"]
    try:
        measures.grocy_equipment = grocy.execute(
            "SELECT COUNT(*) AS n FROM equipment").fetchone()["n"]
    except sqlite3.Error:
        measures.grocy_equipment = 0
    measures.home_equipment = conn.execute(
        "SELECT COUNT(*) AS n FROM equipment").fetchone()["n"]
    for row in conn.execute(
        "SELECT bt.label AS label FROM battery AS bt"
        " WHERE bt.tracked = 1 AND bt.entity_registry_id IS NULL"
        "   AND bt.device_id IS NULL"
    ):
        measures.battery_gaps.append(
            f"{row['label']} : suivie mais ancrée à rien — la tâche de"
            " maintenance ne saura pas de quelle pile elle parle")


def _measure_recipes(conn, measures: Measures) -> None:
    measures.recipes = conn.execute(
        "SELECT COUNT(*) AS n FROM recipe WHERE source = 'grocy'").fetchone()["n"]
    measures.ingredients = conn.execute(
        "SELECT COUNT(*) AS n FROM recipe_ingredient").fetchone()["n"]
    measures.instructions = conn.execute(
        "SELECT COUNT(*) AS n FROM recipe_instruction").fetchone()["n"]
    measures.timers = conn.execute(
        "SELECT COUNT(*) AS n FROM recipe_instruction"
        " WHERE timer_seconds IS NOT NULL").fetchone()["n"]
    for row in conn.execute(
        "SELECT rec.name AS name, rec.source_ref AS ref FROM recipe AS rec"
        " WHERE rec.source = 'grocy' AND CAST(rec.source_ref AS INTEGER) <= 0"
    ):
        measures.phantoms.append(
            f"{row['name']} (source_ref {row['ref']}) : copie fantôme de"
            " meal_plan importée — le filtre a été relâché")
    for row in conn.execute(
        "SELECT ri.id AS id, ri.raw_text AS raw_text, rec.name AS recipe"
        " FROM recipe_ingredient AS ri"
        " JOIN recipe AS rec ON rec.id = ri.recipe_id"
        " WHERE ri.match_state = 'unmatched' ORDER BY ri.id"
    ):
        measures.unmatched_lines.append(
            (str(row["id"]),
             f"{row['recipe']} : ligne {row['id']} sans quantité —"
             f" « {row['raw_text']} », à trancher à la main"))


def _measure_plan(conn, measures: Measures) -> None:
    measures.meals = conn.execute(
        "SELECT COUNT(*) AS n FROM meal").fetchone()["n"]
    measures.meal_recipes = conn.execute(
        "SELECT COUNT(DISTINCT recipe_id) AS n FROM meal"
        " WHERE recipe_id IS NOT NULL").fetchone()["n"]
    measures.list_items = conn.execute(
        "SELECT COUNT(*) AS n FROM shopping_list_item"
        " WHERE checked_at IS NULL AND removed_at IS NULL").fetchone()["n"]
    for row in conn.execute(
        "SELECT ml.day AS day, ml.recipe_id AS recipe_id FROM meal AS ml"
        " WHERE ml.recipe_id IS NOT NULL"
        "   AND NOT EXISTS (SELECT 1 FROM recipe AS rec WHERE rec.id = ml.recipe_id)"
    ):
        measures.plan_gaps.append(
            f"repas du {row['day']} : la recette {row['recipe_id']} n'existe"
            " pas — il se découvrirait au dîner")


def _measure_pictures(conn, measures: Measures, picture_dir) -> None:
    """Go out to the file system. A check that only re-reads columns proves
    NOTHING about files: the image_url can be perfectly consistent with each
    other and point at an empty folder. A zero-byte file is a failure — it
    would pass every database check and display nothing."""
    racine = Path(picture_dir) if picture_dir else None
    measures.picture_dir_seen = racine is not None and racine.exists()

    references: set[str] = set()
    # `article` nomme sa colonne `image`, les deux autres `image_url` : le
    # lot 0 l'a écrit ainsi et le lot 7 ne renomme rien.
    for table, colonne in (("recipe", "image_url"), ("recipe_step", "image_url"),
                           ("article", "image")):
        for row in conn.execute(f"SELECT {colonne} AS url FROM {table}"
                                f"  WHERE {colonne} IS NOT NULL"):
            url = row["url"]
            if "grocy.allanic.me" in url:
                measures.picture_gaps.append(
                    f"{table} : une URL grocy.allanic.me résiduelle"
                    f" ({url}) — elle mourra avec le conteneur")
            elif url.startswith("media-source://media_source/local/"):
                references.add(url.split("/local/", 1)[1])
            # Les URL externes (Unsplash) ne sont NI comptées NI visitées :
            # elles ne meurent pas avec le conteneur.
    measures.pictures_referenced = len(references)
    if racine is None:
        return
    for relative in sorted(references):
        # `home_stock/recipes/x.jpg` sous une racine qui EST `media/home_stock`.
        chemin = racine / Path(relative).relative_to("home_stock") \
            if relative.startswith("home_stock/") else racine / relative
        if not chemin.exists():
            measures.picture_gaps.append(
                f"{chemin.name} : référencé mais absent du dossier media")
        elif chemin.stat().st_size == 0:
            measures.picture_gaps.append(
                f"{chemin.name} : fichier de 0 octet — il n'afficherait rien")
        else:
            measures.pictures_present += 1


def _measure_config(measures: Measures, config_dir) -> None:
    """Read config/ — READ ONLY, through a path handed in as a parameter.

    Never written, never reloaded, and the lot 5 raccord is NEVER applied.
    When the path does not exist, C11 reports `empty`: it does not claim the
    house is clean because it could not look.
    """
    if not config_dir:
        return
    racine = Path(config_dir)
    if not racine.exists():
        return
    measures.config_seen = True
    fichiers = [racine / "automations.yaml", racine / "scripts.yaml",
                racine / "custom_templates" / "maintenance.jinja"]
    for chemin in fichiers:
        if not chemin.exists():
            continue
        texte = chemin.read_text("utf-8", errors="replace")
        for motif, quoi in GROCY_RESIDUES:
            if motif in texte:
                measures.residues.append(
                    f"{chemin.name} cite encore {motif} — {quoi}")
        if chemin.name == "maintenance.jinja" and JINJA_BATTERY_BLOCK in texte:
            measures.residues.append(
                f"{chemin.name} porte encore son bloc « {JINJA_BATTERY_BLOCK} »"
                " — appliquer le raccord de docs/raccord/README.md AVANT toute"
                " extinction, sinon 14 tâches de pile disparaissent")


def _verdict(code: str, gap: int, measures: Measures,
             acknowledged: set[str], to_acknowledge: set[str]) -> str:
    if not FLOORS[code](measures):
        return "empty"                  # d'abord, toujours
    if code in _NEEDS_ACK and to_acknowledge and not to_acknowledge <= acknowledged:
        return "unacknowledged"
    return "ok" if gap == 0 else "gap"


def _result(code: str, label: str, *, grocy_count: int, home_count: int,
            gap: int, details: list[str], measures: Measures,
            acknowledged: set[str],
            to_acknowledge: set[str] | None = None) -> CheckResult:
    verdict = _verdict(code, gap, measures, acknowledged, to_acknowledge or set())
    return CheckResult(
        code=code, label=label, grocy_count=grocy_count, home_count=home_count,
        gap=gap, verdict=verdict, blocking=verdict != "ok",
        details=details[:MIGRATION_DETAIL_CAP])


def _c0(measures: Measures, acknowledged: set[str]) -> CheckResult:
    details: list[str] = []
    gap = 0
    if not measures.grocy_present:
        details.append("la copie de grocy.db est introuvable")
    if measures.schema_version != SCHEMA_VERSION_EXPECTED:
        gap += 1
        details.append(
            f"schema_version = {measures.schema_version}, attendu"
            f" {SCHEMA_VERSION_EXPECTED} — Home Assistant n'a pas redémarré")
    if measures.copy_age_hours is not None \
            and measures.copy_age_hours > GROCY_COPY_MAX_AGE_HOURS:
        gap += 1
        details.append(
            f"la copie a {measures.copy_age_hours:.1f} h : elle n'est plus une"
            " photo de l'instant, la refaire")
    derniere = _parse(measures.grocy_last_write)
    prise = _parse(measures.copy_taken_at)
    if derniere is not None and prise is not None:
        limite = prise + timedelta(hours=GROCY_FREEZE_TOLERANCE_HOURS)
        if derniere > limite:
            gap += 1
            details.append(
                f"Grocy a écrit le {measures.grocy_last_write}, après la copie"
                f" du {measures.copy_taken_at} : geler Grocy et recommencer")
    return _result("C0", "Schéma et gel de Grocy",
                   grocy_count=1 if measures.grocy_present else 0,
                   home_count=measures.schema_version, gap=gap, details=details,
                   measures=measures, acknowledged=acknowledged)


def _c1(measures: Measures, acknowledged: set[str]) -> CheckResult:
    manquants = [d for d in measures.quantity_gaps if "aucun lot importé" in d
                 or "sans ligne Grocy" in d]
    return _result("C1", "Un lot par ligne de stock",
                   grocy_count=measures.grocy_stock,
                   home_count=measures.home_batches,
                   gap=abs(measures.grocy_stock - measures.home_batches)
                   + len(manquants) - (
                       len(manquants) if measures.grocy_stock
                       != measures.home_batches else 0),
                   details=manquants, measures=measures,
                   acknowledged=acknowledged)


def _c2(measures: Measures, acknowledged: set[str]) -> CheckResult:
    ecarts = [d for d in measures.quantity_gaps
              if "aucun lot importé" not in d and "sans ligne Grocy" not in d]
    return _result("C2", "Les quantités, au millionième près",
                   grocy_count=measures.grocy_stock,
                   home_count=measures.home_batches, gap=len(ecarts),
                   details=ecarts, measures=measures, acknowledged=acknowledged)


def _c3(measures: Measures, acknowledged: set[str]) -> CheckResult:
    details = [f"{measures.sentinels} sentinelles {GROCY_NEVER_EXPIRES}"
               " attendues à NULL", *measures.date_gaps]
    return _result("C3", "Les dates de péremption",
                   grocy_count=measures.dated_batches + measures.sentinels,
                   home_count=measures.dated_batches,
                   gap=len(measures.date_gaps), details=details,
                   measures=measures, acknowledged=acknowledged)


def _c4(measures: Measures, acknowledged: set[str]) -> CheckResult:
    """The unpriced batches, and the seven that must be acknowledged by name."""
    refs = {ref for ref, _ in measures.dropped_prices}
    details = [texte for _, texte in measures.dropped_prices]
    return _result("C4", "Les prix écartés, acquittés nommément",
                   grocy_count=len(refs), home_count=measures.unpriced,
                   gap=0, details=details, measures=measures,
                   acknowledged=acknowledged, to_acknowledge=refs)


def _c5(measures: Measures, acknowledged: set[str]) -> CheckResult:
    return _result("C5", "Un mouvement d'entrée par lot",
                   grocy_count=measures.grocy_stock,
                   home_count=measures.entry_movements,
                   gap=len(measures.movement_gaps),
                   details=measures.movement_gaps, measures=measures,
                   acknowledged=acknowledged)


def _c6(measures: Measures, acknowledged: set[str]) -> CheckResult:
    """The three running totals, proven mechanically rather than assumed.

    `repo.totals_between()` only sums consumption reasons, so an entry
    movement cannot reach kcal_total, cost_total or cost_waste_total — as long
    as no entry movement carries calories or a cost. That is what is measured.
    """
    details = ["kcal_total", "cost_total", "cost_waste_total",
               f"{measures.entry_movements} mouvements d'entrée, aucun ne"
               " porte de calories ni de coût",
               *measures.polluted_movements]
    return _result("C6", "Les trois cumuls n'ont pas bougé",
                   grocy_count=measures.entry_movements,
                   home_count=measures.entry_movements,
                   gap=len(measures.polluted_movements), details=details,
                   measures=measures, acknowledged=acknowledged)


def _c7(measures: Measures, acknowledged: set[str]) -> CheckResult:
    return _result("C7", "Piles et équipements (lot 5)",
                   grocy_count=measures.grocy_equipment,
                   home_count=measures.home_equipment,
                   gap=abs(measures.grocy_equipment - measures.home_equipment)
                   + len(measures.battery_gaps),
                   details=[f"{measures.grocy_batteries} piles chez Grocy,"
                            f" {measures.home_batteries} dans home_stock",
                            f"{measures.home_equipment} équipements",
                            *measures.battery_gaps],
                   measures=measures, acknowledged=acknowledged)


def _c8(measures: Measures, acknowledged: set[str]) -> CheckResult:
    """Recipes, and the 25 lines a human has to sign.

    Blocking on the counts, NOT on the 25 unmatched — those are listed and
    acknowledged by name, because they are work to do, not a defect to fix.
    """
    details = [
        f"{measures.recipes} recettes", f"{measures.ingredients} ingrédients",
        f"{measures.instructions} instructions", f"{measures.timers} minuteurs",
        *measures.phantoms,
        *[texte for _, texte in measures.unmatched_lines],
    ]
    return _result("C8", "Recettes, ingrédients, instructions, minuteurs",
                   grocy_count=measures.recipes, home_count=measures.recipes,
                   gap=len(measures.phantoms), details=details,
                   measures=measures, acknowledged=acknowledged,
                   to_acknowledge={ident for ident, _ in measures.unmatched_lines})


def _c9(measures: Measures, acknowledged: set[str]) -> CheckResult:
    return _result("C9", "Les images, sur le disque",
                   grocy_count=measures.pictures_referenced,
                   home_count=measures.pictures_present,
                   gap=len(measures.picture_gaps), details=measures.picture_gaps,
                   measures=measures, acknowledged=acknowledged)


def _c10(measures: Measures, acknowledged: set[str]) -> CheckResult:
    details = [f"{measures.meals} repas à venir",
               f"{measures.meal_recipes} recettes distinctes atteignables",
               f"{measures.list_items} lignes de courses ouvertes",
               *measures.plan_gaps]
    return _result("C10", "Planning et liste de courses",
                   grocy_count=measures.meals, home_count=measures.meals,
                   gap=len(measures.plan_gaps), details=details,
                   measures=measures, acknowledged=acknowledged)


def _c11(measures: Measures, acknowledged: set[str]) -> CheckResult:
    return _result("C11", "Ce qui lit encore Grocy dans la maison",
                   grocy_count=len(measures.residues), home_count=0,
                   gap=len(measures.residues), details=measures.residues,
                   measures=measures, acknowledged=acknowledged)


_CHECKS: dict[str, Callable[[Measures, set[str]], CheckResult]] = {
    "C0": _c0, "C1": _c1, "C2": _c2, "C3": _c3, "C4": _c4, "C5": _c5, "C6": _c6,
    "C7": _c7, "C8": _c8, "C9": _c9, "C10": _c10, "C11": _c11,
}


def check_migration(db, grocy_path: str, *, acknowledged=(), archive: bool = True,
                    now: str | None = None, picture_dir=None, config_dir=None,
                    archive_dir=None) -> CheckReport:
    """Run every check. C0 is evaluated first, and the others still run.

    C0 first because a stale or written-to copy makes the ten others lie; the
    others still run because their measurement is worth having even then —
    but `ok` stays false.
    """
    moment = _parse(now) or datetime.now(UTC)
    measures = _measure(db, grocy_path, now=moment)
    _measure_pictures(db.read(), measures, picture_dir)
    _measure_config(measures, config_dir)
    acquittes = set(acknowledged)

    report = CheckReport()
    for code in MIGRATION_CHECKS:
        fabrique = _CHECKS.get(code)
        if fabrique is None:
            continue
        resultat = fabrique(measures, acquittes)
        report.checks.append(resultat)
        if resultat.blocking:
            report.blocking.append(code)
    return report
