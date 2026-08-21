"""The second Grocy import: batteries, spares, equipment — and the check that
proves the switch-over is neutral.

Independent of `import_grocy.py` on purpose: that one copies the food
catalogue, this one copies a different pair of tables and then does something
`import_grocy.py` never has to — it reproduces, ONE last time, the heuristics
of `maintenance.jinja`'s block 3 so that the first reconciliation after the
switch produces exactly the same summaries as the last one before it.

That is the counter-intuitive part of this file, and it is deliberate. The
whole of lot 5 exists to REMOVE those heuristics (a label guessed by a chain
of `replace()`, a verb guessed by a `rideau|lock` pattern). Seeding them here
is what makes the deployment open and close nothing: correcting a label
afterwards becomes a DECISION, taken knowingly from the Piles screen, with
its one task of churn. The heuristic is used once and then never again; it
lives here and nowhere else.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .const import DEFAULT_KEEP_PERCENT, DEFAULT_LOW_PERCENT, MUTE_SUMMARY_PREFIX
from .storage import repositories as repo
from .storage.database import Database

# --- ce que le macro fait aujourd'hui, recopié une fois ----------------------

# `maintenance.jinja` bloc 3, lignes 57-110. Ces trois constantes sont la
# copie EXACTE de ce que le macro écarte aujourd'hui. Elles ne servent qu'à
# l'import : rien d'autre ne doit les lire, et elles ne seront jamais mises à
# jour — leur rôle s'arrête à la bascule.
MACRO_EXCLUDED_IDS = (
    "sensor.capteur_humain_batterie", "sensor.capteur_batterie",
    "sensor.capteur_batterie_2", "sensor.peugeot_e208_batterie_de_service",
    "sensor.peugeot_e208_batterie_niveau",
)
MACRO_EXCLUDED_PATTERN = re.compile("browser|pixel|brya|tablette|aspirateur")

# Le motif humain, par famille. C'est la seule information que le macro
# possède et qu'on perdrait en le raccourcissant : QUI est exclu, et POURQUOI.
_EXCLUSION_REASONS = (
    ("browser", "capteur browser_mod d'une tablette, pas une pile à entretenir"),
    ("pixel", "téléphone, sa charge ne se gère pas ici"),
    ("brya", "chromebook, sa charge ne se gère pas ici"),
    ("tablette", "tablette murale sur secteur, jamais à changer"),
    ("aspirateur", "batterie d'aspirateur, sa charge ne se gère pas ici"),
)
_EXPLICIT_REASONS = {
    "sensor.capteur_humain_batterie": "NiMH rechargeable, faux positif de voltage",
    "sensor.capteur_batterie": "NiMH rechargeable, faux positif de voltage",
    "sensor.capteur_batterie_2": "NiMH rechargeable, faux positif de voltage",
    "sensor.peugeot_e208_batterie_de_service":
        "batterie du véhicule, elle ne se change pas à la maison",
    "sensor.peugeot_e208_batterie_niveau":
        "batterie de traction du véhicule, elle ne se change pas à la maison",
}

# Les seuils du bloc 3, en dur : 20 % pour apparaître, 25 % pour se maintenir.
_MACRO_LOW = 20
_MACRO_KEEP = 25


def macro_label(name: str) -> str:
    """The chain of `replace()` block 3 applies to an entity's display name.

    « Velux (CH) Batterie » becomes « Velux (CH) ». Reproduced exactly,
    including its order — `'Batterie '` before `' Batterie'` — because the two
    do not commute on a name like « Batterie Capteur Cuisine ».
    """
    return (name.replace("Batterie ", "")
                .replace(" Batterie", "")
                .replace(" Battery level", "")
                .strip())


def macro_kind(name: str) -> str:
    """« Recharger » for a name carrying `rideau` or `lock` (the USB-charged
    Tuya blinds and the Aqara U200 Lite lock), « Pile à changer » otherwise."""
    lowered = name.lower()
    return "built_in" if ("rideau" in lowered or "lock" in lowered) else "primary"


def macro_excludes(entity_id: str) -> str | None:
    """The reason block 3 would skip this sensor today, or None."""
    if entity_id in _EXPLICIT_REASONS:
        return _EXPLICIT_REASONS[entity_id]
    for fragment, reason in _EXCLUSION_REASONS:
        if fragment in entity_id:
            return reason
    return None


def _macro_int(state: Any) -> int:
    """`s.state | int(-1)`: Jinja's own coercion, -1 on anything unparseable."""
    try:
        return int(float(state))
    except (TypeError, ValueError):
        return -1


def macro_summaries(states) -> dict[str, list[str]]:
    """Exactly the summaries block 3 would produce on these states.

    Kept as a function rather than inlined so the drift check can be read
    against the macro it is meant to reproduce — and so a test can call it
    directly and see that it does produce tasks when a battery is low.
    """
    items: list[str] = []
    keep: list[str] = []
    for row in states:
        attributes = row.get("attributes") or {}
        if attributes.get("device_class") != "battery":
            continue
        entity_id = row["entity_id"]
        if entity_id in MACRO_EXCLUDED_IDS or MACRO_EXCLUDED_PATTERN.search(entity_id):
            continue
        name = attributes.get("friendly_name") or entity_id
        label = macro_label(name)
        verb = "Recharger" if macro_kind(name) == "built_in" else "Pile à changer"
        level = f"{verb} — {label}"
        state = row.get("state")
        if state in ("unavailable", "unknown"):
            mute = f"{MUTE_SUMMARY_PREFIX}{label}"
            # The macro adds the mute ITEM only past its own delay, which it
            # measures from `last_changed`. The import compares plans, not
            # clocks: both sides are given the same states, and the mute item
            # is the one summary whose presence depends on a duration, so it
            # is compared through `keep` only. `keep` is what closes tasks,
            # and closing is the irreversible half.
            keep.extend([mute, level])
            continue
        value = _macro_int(state)
        if value < 0:
            keep.append(level)
            continue
        if value < _MACRO_LOW:
            items.append(level)
        if value < _MACRO_KEEP:
            keep.append(level)
    return {"items": items, "keep": keep}


# --- le rapport --------------------------------------------------------------

@dataclass
class EquipmentImportReport:
    """What was written, and what must be looked at by hand.

    Same shape as `ImportReport` (lot 0), plus `summary_diff` — the check that
    guarantees the neutral deployment.
    """

    products: int = 0
    batteries: int = 0
    equipment: int = 0
    discovered: int = 0
    pre_excluded: int = 0
    skipped: int = 0
    applied: bool = False
    anomalies: list[str] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    summary_diff: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the import may be applied.

        `anomalies` is everything worth reading; `blocking` is the subset that
        must be fixed first. The distinction is not cosmetic: the two swapped
        BLE tags and the three retired devices are QUESTIONS for the owner and
        FACTS about what was skipped — reporting them must not refuse an
        import that is otherwise perfectly safe, or the report becomes a thing
        one learns to ignore. A dead anchor or a summary drift is a different
        matter: those change what todo.maintenance does.
        """
        return not self.blocking and not self.summary_diff

    def as_dict(self) -> dict[str, Any]:
        return {
            "products": self.products, "batteries": self.batteries,
            "equipment": self.equipment, "discovered": self.discovered,
            "pre_excluded": self.pre_excluded, "skipped": self.skipped,
            "applied": self.applied, "anomalies": self.anomalies,
            "blocking": self.blocking, "summary_diff": self.summary_diff,
            "ok": self.ok,
        }


# --- la lecture de Grocy -----------------------------------------------------

# 18 lignes de rechange pour 18 cellules, c'est un inventaire par objet. Ce
# qu'on veut savoir, c'est « combien de CR2032 au placard » : chaque famille
# devient UN produit, et le nombre de lignes devient sa quantité.
# Le produit porte le FORMAT, jamais la marque : c'est le format qu'on achète,
# et c'est lui que la tâche doit dire (« 1× CR2032 »). La marque descend dans
# l'article générique, ce qui est exactement le partage product/article du
# catalogue. L'ordre compte : « LADDA » avant « AA Alcaline », sinon « AAA »
# serait attrapé par le motif « AA ».
_SPARE_FAMILIES = (
    ("LADDA", "AAA", "IKEA LADDA 900 mAh"),
    ("9V", "9 V", None),
    ("CR2032", "CR2032", None),
    ("C/LR14", "C/LR14", None),
    ("AA Alcaline", "AA", None),
)
_ENTITY_RE = re.compile(r"(sensor\.[a-z0-9_]+)")
_COUNT_RE = re.compile(r"(\d+)\s*x\s*([A-Za-z0-9/]+)", re.IGNORECASE)
_REMOVED_RE = re.compile(r"appareil retir", re.IGNORECASE)


def _open_grocy(path: str) -> sqlite3.Connection:
    """Read-only, always. Grocy is never written to, not once."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _spare_family(name: str) -> str | None:
    for fragment, product, _brand in _SPARE_FAMILIES:
        if fragment.lower() in name.lower():
            return product
    return None


def _spare_brand(product: str) -> str | None:
    for _fragment, name, brand in _SPARE_FAMILIES:
        if name == product:
            return brand
    return None


def import_grocy_equipment(db: Database, grocy_path: str, *, hass_states,
                           registry_rows, apply: bool = False,
                           ) -> EquipmentImportReport:
    """Copy Grocy's batteries and equipment over, and sweep the registry.

    Like `import_catalog`, a dry run WALKS EVERYTHING and REPORTS EVERYTHING;
    only the writes are skipped. That is the whole point of `apply: false` —
    proving the same anomalies a real pass would raise.
    """
    report = EquipmentImportReport(applied=apply)
    grocy = _open_grocy(grocy_path)
    try:
        battery_rows = list(grocy.execute(
            "SELECT id, name, COALESCE(description, '') AS description"
            " FROM batteries ORDER BY id"))
        equipment_rows = list(grocy.execute(
            "SELECT id, name, COALESCE(description, '') AS description"
            " FROM equipment ORDER BY id"))
    finally:
        grocy.close()

    states_by_id = {row["entity_id"]: row for row in hass_states}
    registry_by_entity = {row["entity_id"]: row for row in registry_rows}

    # --- 1. les rechanges : 18 lignes, 5 produits ---------------------------
    spares: dict[str, int] = {}
    for row in battery_rows:
        if _ENTITY_RE.search(row["description"]) or _REMOVED_RE.search(row["description"]):
            continue
        family = _spare_family(row["name"]) or _spare_family(row["description"])
        if family is None:
            report.blocking.append(
                f"rechange non classée : {row['name']!r} (Grocy {row['id']})")
            continue
        spares[family] = spares.get(family, 0) + 1
    report.products = len(spares)

    # --- 2. les piles ancrées, et les appareils retirés ---------------------
    anchored: dict[str, dict[str, Any]] = {}
    for row in battery_rows:
        if _REMOVED_RE.search(row["description"]):
            report.skipped += 1
            report.anomalies.append(
                f"appareil retiré, non importé : {row['name']!r} (Grocy {row['id']})")
            continue
        found = _ENTITY_RE.search(row["description"])
        if not found:
            continue
        count, format_name = 1, None
        counted = _COUNT_RE.search(row["description"])
        if counted:
            count, format_name = int(counted.group(1)), counted.group(2)
        anchored[found.group(1)] = {
            "grocy_id": row["id"],
            "cell_count": count,
            "format": format_name,
            "rechargeable": "rechargeable" in row["description"].lower(),
        }
    report.batteries = len(anchored)
    report.equipment = len(equipment_rows)

    # --- 3. le balayage du registre ----------------------------------------
    planned: list[dict[str, Any]] = []
    for entity_id, entry in sorted(registry_by_entity.items()):
        state_row = states_by_id.get(entity_id)
        if state_row is None:
            continue
        name = (state_row.get("attributes") or {}).get("friendly_name") or entity_id
        reason = macro_excludes(entity_id)
        detail = anchored.get(entity_id)
        # The seeded kind reproduces today's verb; a Grocy description saying
        # "rechargeable" refines it, because that is knowledge the macro did
        # not have and cannot be wrong about.
        kind = macro_kind(name)
        if detail and detail["rechargeable"] and kind != "built_in":
            kind = "rechargeable_cell"
        planned.append({
            "entity_id": entity_id,
            "entity_registry_id": entry["entity_registry_id"],
            "device_id": entry.get("device_id"),
            "label": macro_label(name),
            "kind": kind,
            "cell_count": detail["cell_count"] if detail else 1,
            "spare_format": detail["format"] if detail else None,
            "tracked": reason is None,
            "exclusion_reason": reason,
            "external_ref": (f"grocy:battery:{detail['grocy_id']}" if detail
                             else f"ha:battery:{entry['entity_registry_id']}"),
        })
        if reason is not None:
            report.pre_excluded += 1
        else:
            report.discovered += 1

    # --- 4. les contrôles de sortie ----------------------------------------
    for row in planned:
        if not row["label"]:
            report.blocking.append(f"pile sans libellé : {row['entity_id']}")
        if row["tracked"] and not row["kind"]:
            report.blocking.append(f"pile suivie sans nature : {row['entity_id']}")
        friendly = ((states_by_id[row["entity_id"]].get("attributes") or {})
                    .get("friendly_name") or "")
        # The two BLE tags of the keyring have their names swapped in the
        # registry (CLAUDE.md). Nothing in the system arbitrates it, so lot 5
        # reports both, side by side, and renames neither: deciding on the
        # strength of a name would reproduce the very guess being removed.
        if "BLE" in friendly and row["entity_id"] in (
                "sensor.cle_de_la_peugeot_e208_batterie_ble", "sensor.sac_batterie_ble"):
            report.anomalies.append(
                f"tag BLE au nom possiblement inversé, à trancher à la main : "
                f"{row['entity_id']} affiche {friendly!r}")

    # An anchor that resolves to nothing ON THE DAY of the import is a typing
    # mistake, not a legitimate orphan.
    for entity_id in anchored:
        if entity_id not in registry_by_entity:
            report.blocking.append(
                f"ancre morte le jour de l'import : {entity_id} ne résout aucune entité")

    # --- 5. l'écriture ------------------------------------------------------
    if apply:
        _write(db, spares=spares, planned=planned, equipment_rows=equipment_rows)

    # --- 6. le contrôle « 0 écart de résumés » ------------------------------
    report.summary_diff = _summary_diff(db, planned=planned, states_by_id=states_by_id,
                                        hass_states=hass_states, applied=apply)
    return report


def _write(db: Database, *, spares, planned, equipment_rows) -> None:
    with db.write() as conn:
        location = conn.execute(
            "SELECT id FROM location ORDER BY id LIMIT 1").fetchone()
        location_id = location["id"] if location else None
        product_ids: dict[str, int] = {}
        for name, quantity in spares.items():
            existing = conn.execute(
                "SELECT id FROM product WHERE name = ?", (name,)).fetchone()
            if existing is not None:
                product_ids[name] = int(existing["id"])
                continue
            product_id = repo.insert_product(
                conn, name=name, base_unit="piece", edible=0,
                # Without a min_quantity an exhausted spare would never reach
                # `binary_sensor.home_stock_shortages`, so never the shopping
                # list — and "knowing what to buy" would be lost.
                min_quantity=2, external_ref=f"grocy:spare:{name}")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             is_generic=1, label=_spare_brand(name))
            if location_id is not None:
                repo.insert_batch(conn, article_id=article_id,
                                  location_id=location_id, quantity=float(quantity),
                                  entered_at="2026-08-21T00:00:00")
            product_ids[name] = product_id

        for row in equipment_rows:
            marker = f"grocy:equipment:{row['id']}"
            if conn.execute("SELECT id FROM equipment WHERE external_ref = ?",
                            (marker,)).fetchone() is not None:
                continue
            repo.insert_equipment(conn, name=row["name"],
                                  note=row["description"] or None,
                                  external_ref=marker)

        for row in planned:
            if conn.execute("SELECT id FROM battery WHERE entity_registry_id = ?",
                            (row["entity_registry_id"],)).fetchone() is not None:
                continue
            product_id = None
            if row["spare_format"]:
                for name in product_ids:
                    if row["spare_format"].lower() in name.lower():
                        product_id = product_ids[name]
                        break
            if row["kind"] == "built_in":
                product_id = None
            repo.insert_battery(
                conn, label=row["label"], kind=row["kind"],
                entity_registry_id=row["entity_registry_id"],
                device_id=row["device_id"], product_id=product_id,
                cell_count=row["cell_count"],
                tracked=1 if row["tracked"] else 0,
                exclusion_reason=row["exclusion_reason"],
                low_percent=DEFAULT_LOW_PERCENT, keep_percent=DEFAULT_KEEP_PERCENT,
                external_ref=row["external_ref"])


def _summary_diff(db: Database, *, planned, states_by_id, hass_states,
                  applied: bool) -> list[str]:
    """The summaries the NEW plan would produce, against the OLD macro's.

    Compared on `keep`, not on `items`: `keep` is what CLOSES a task, and
    closing is the irreversible half — a task that appears one sync late is a
    delay, a task closed by mistake is an announcement in the house and a
    battery nobody replaces. The mute summary is also the one whose presence
    depends on a duration rather than on a state, and only `keep` holds it on
    both sides.
    """
    from .domain.maintenance import battery_plan

    rows = []
    if applied:
        source = db.read().execute(
            "SELECT * FROM battery WHERE active = 1").fetchall()
        rows = [dict(row) for row in source]
    else:
        rows = [{"id": index, "label": row["label"], "kind": row["kind"],
                 "tracked": row["tracked"], "active": 1,
                 "low_percent": DEFAULT_LOW_PERCENT,
                 "keep_percent": DEFAULT_KEEP_PERCENT,
                 "entity_registry_id": row["entity_registry_id"],
                 "spare": None}
                for index, row in enumerate(planned, start=1)]

    by_registry = {row["entity_registry_id"]: row for row in planned}
    enriched = []
    for row in rows:
        planned_row = by_registry.get(row["entity_registry_id"])
        if planned_row is None:
            continue
        state_row = states_by_id.get(planned_row["entity_id"], {})
        enriched.append({
            **row,
            "tracked": bool(row["tracked"]),
            "spare": row.get("spare"),
            "entity_id": planned_row["entity_id"],
            "state": state_row.get("state"),
            # The new plan reads `last_reading_at` from the database, which is
            # empty on the day of the import. Feeding it the snapshot's own
            # state keeps the comparison about the RULE, not about a clock.
            "last_percent": _numeric(state_row.get("state")),
            "last_reading_at": "2026-08-21T00:00:00",
        })

    from datetime import datetime
    nouveau = battery_plan(enriched, now=datetime(2026, 8, 21, 0, 30, 0))
    ancien = macro_summaries(hass_states)
    manquants = sorted(set(ancien["keep"]) - set(nouveau["keep"]))
    en_trop = sorted(set(nouveau["keep"]) - set(ancien["keep"]))
    return ([f"le macro gardait « {s} », le nouveau plan ne le garde plus"
             for s in manquants]
            + [f"le nouveau plan garde « {s} », que le macro ne gardait pas"
               for s in en_trop])


def _numeric(state: Any) -> float | None:
    try:
        value = float(state)
    except (TypeError, ValueError):
        return None
    return None if value != value else value
