"""La réconciliation de la liste de courses. Pur : ni `hass`, ni SQLite, ni
horloge — l'instant, quand il compte, est passé en argument.

La liste a quatre origines et une seule est humaine. Les fusionner par un
`UNION` dédupliqué sur le produit échoue sur trois cas quotidiens : le lait
réclamé deux fois (sous son seuil ET manquant pour le gratin de jeudi), la
rupture qui disparaît alors que le repas reste, et la ligne barrée à la main
que la passe suivante remettrait. D'où le couple item / revendication :
**l'item est une ligne de liste, la revendication est une raison de
l'acheter**, au plus une par origine.

Les cinq règles du § 7.3, dans l'ordre où elles s'appliquent :

1. **Une revendication qui n'est plus fondée est supprimée.**
2. **Un item sans revendication et jamais coché est retiré** (`removed_at`),
   sauf s'il porte une revendication `manual` — règle 5.
3. **Un item coché est laissé tranquille tant que la session en cours n'est
   pas close.** C'est la fenêtre entre le chariot et le placard : la rupture
   existe encore en base, et rien ne doit remettre la ligne pendant qu'on
   est à la caisse.
4. **Un item coché dont la session est close est purgé.** Si la rupture
   persiste — on a coché sans acheter, ou pas assez — une ligne neuve est
   recréée. La liste dit ce qui manque *maintenant*.
5. **Une ligne posée à la main n'est jamais retirée par le robot.** Seule
   dérogation à « la liste appartient au composant », et indispensable :
   sans elle, « prends des piles pour la télécommande du salon »
   disparaîtrait en quinze minutes.

Et la règle qui les traverse toutes, reprise mot pour mot de
`maintenance.jinja` : **jamais de fermeture sur une donnée absente**. Elle
vit dans `shortage_claim`, seul endroit qui voie une mesure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..const import SHORTAGE_KEEP_FACTOR


@dataclass(frozen=True)
class Claim:
    """Une raison d'acheter cette ligne. Au plus une par origine."""

    origin: str
    quantity: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class WantedItem:
    """Une ligne telle que les origines la réclament, à cet instant."""

    product_id: int | None = None
    free_text: str | None = None
    claims: tuple[Claim, ...] = ()


@dataclass(frozen=True)
class Plan:
    """Ce que la réconciliation demande d'écrire. Aucune connexion dedans."""

    to_create: tuple[WantedItem, ...] = ()
    to_update: tuple[dict[str, Any], ...] = ()
    to_remove: tuple[int, ...] = ()
    claims_to_add: tuple[dict[str, Any], ...] = ()
    claims_to_drop: tuple[dict[str, Any], ...] = ()


MANUAL = "manual"


def item_quantity(claims: Sequence[Claim]) -> float | None:
    """Le MAXIMUM des quantités connues, jamais leur somme.

    Un seuil de réapprovisionnement et un besoin de recette décrivent le
    même stock manquant vu de deux côtés, pas deux stocks : on n'achète pas
    deux fois le même litre. Une revendication sans quantité (« prends du
    pain ») n'écrase pas une quantité connue et ne s'y ajoute pas ; sans
    aucune valeur, la ligne dit « ce qu'il faut ».
    """
    known = [claim.quantity for claim in claims if claim.quantity is not None]
    return max(known) if known else None


def shortage_claim(row: Mapping[str, Any], *,
                   already_claimed: bool) -> Claim | None:
    """La revendication `shortage` d'un produit, hystérésis comprise.

    Apparaît STRICTEMENT sous `min_quantity`, se maintient jusqu'à
    `min_quantity × SHORTAGE_KEEP_FACTOR` inclus. Sans cette marge, un
    produit qui oscille autour de son seuil fait clignoter sa ligne tous les
    quarts d'heure — et une liste qui clignote est une liste qu'on n'ouvre
    plus.

    Une mesure absente (seuil supprimé, produit désactivé, stock illisible)
    MAINTIENT une revendication existante et n'en crée jamais : on ne retire
    une ligne que sur une mesure qui prouve que le besoin a disparu.
    """
    threshold = row.get("min_quantity")
    quantity = row.get("quantity")
    if threshold is None or quantity is None:
        return _kept_claim(row) if already_claimed else None
    if already_claimed:
        if quantity > threshold * SHORTAGE_KEEP_FACTOR:
            return None
    elif quantity >= threshold:
        return None
    missing = threshold - quantity
    return Claim("shortage", missing if missing > 0 else None,
                 f"seuil {_trim(threshold)}")


def _kept_claim(row: Mapping[str, Any]) -> Claim:
    threshold = row.get("min_quantity")
    detail = "mesure indisponible" if threshold is None else f"seuil {_trim(threshold)}"
    return Claim("shortage", None, detail)


def _trim(value: float) -> str:
    """`500.0` s'écrit « 500 ». Un seuil affiché avec une décimale morte
    donne l'impression d'une précision qui n'existe pas."""
    return f"{value:g}"


def _key(product_id: int | None, free_text: str | None) -> tuple[str, Any]:
    """L'identité d'une ligne.

    Une ligne en texte libre ne fusionne JAMAIS avec une ligne de produit,
    même si les deux disent « Lait » : l'appariement par nom est ce qui a
    produit 35 doublons dans Grocy en avril 2026.
    """
    if product_id is not None:
        return ("product", product_id)
    return ("text", free_text)


def _claims_of(row: Mapping[str, Any]) -> dict[str, Claim]:
    return {
        claim["origin"]: Claim(claim["origin"], claim.get("quantity"),
                               claim.get("detail"))
        for claim in row.get("claims") or ()
    }


def reconcile(*, wanted: Sequence[WantedItem], existing: Sequence[Mapping[str, Any]],
              session_open: bool) -> Plan:
    """L'état voulu contre l'état réel : à créer, à mettre à jour, à retirer."""
    blocked: set[tuple[str, Any]] = set()       # barrées à la main, règle « on s'en souvient »
    untouched: set[tuple[str, Any]] = set()     # cochées, session ouverte — règle 3
    open_rows: dict[tuple[str, Any], Mapping[str, Any]] = {}
    to_remove: list[int] = []

    for row in existing:
        key = _key(row.get("product_id"), row.get("free_text"))
        if row.get("removed_at") is not None:
            if row.get("checked_at") is None:
                blocked.add(key)
            continue
        if row.get("checked_at") is not None:
            if session_open:
                untouched.add(key)              # règle 3
            else:
                to_remove.append(int(row["id"]))  # règle 4 : purge, recréable
            continue
        open_rows[key] = row

    to_create: list[WantedItem] = []
    to_update: list[dict[str, Any]] = []
    claims_to_add: list[dict[str, Any]] = []
    claims_to_drop: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()

    for item in wanted:
        key = _key(item.product_id, item.free_text)
        seen.add(key)
        if key in blocked or key in untouched:
            continue
        row = open_rows.get(key)
        if row is None:
            if item.claims:
                to_create.append(item)
            continue
        _diff(row, item.claims, to_update, to_remove, claims_to_add, claims_to_drop)

    for key, row in open_rows.items():
        if key not in seen:
            _diff(row, (), to_update, to_remove, claims_to_add, claims_to_drop)

    return Plan(tuple(to_create), tuple(to_update), tuple(to_remove),
                tuple(claims_to_add), tuple(claims_to_drop))


def _diff(row: Mapping[str, Any], claims: Sequence[Claim],
          to_update: list[dict[str, Any]], to_remove: list[int],
          claims_to_add: list[dict[str, Any]],
          claims_to_drop: list[dict[str, Any]]) -> None:
    """Une ligne ouverte contre ce que les origines en disent maintenant."""
    item_id = int(row["id"])
    held = _claims_of(row)
    asked = {claim.origin: claim for claim in claims}

    for origin, claim in asked.items():
        if held.get(origin) != claim:
            claims_to_add.append({"item_id": item_id, "claim": claim})

    for origin in held:
        # Règle 5 : une revendication `manual` n'est jamais retirée par le
        # robot. Elle ne s'éteint que quand quelqu'un barre la ligne.
        if origin != MANUAL and origin not in asked:
            claims_to_drop.append({"item_id": item_id, "origin": origin})

    remaining = tuple(
        {**held, **asked}[origin]
        for origin in {**held, **asked}
        if origin in asked or origin == MANUAL
    )
    if not remaining:
        to_remove.append(item_id)               # règle 2
        return
    quantity = item_quantity(remaining)
    if quantity != row.get("quantity"):
        to_update.append({"item_id": item_id, "quantity": quantity})
