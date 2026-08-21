"""L'ordre du parcours d'un magasin, appris de l'ordre des scans. Pur et
déterministe : ni `hass`, ni SQLite, ni horloge.

La donnée existe depuis le lot 1 et personne ne la lisait :
`shopping_line.scanned_at`. **L'ordre des scans est l'ordre du parcours**, à
ceci près qu'on scanne parfois trois articles du même rayon d'affilée et
qu'on revient parfois sur ses pas.

**Une moyenne de rangs, et pas un tri topologique.** Le tri topologique sur
les précédences observées est la solution élégante, et elle meurt sur le
premier cycle. Or les cycles sont la norme : on retourne à la boulangerie en
fin de course, on revient chercher le lait oublié. Un algorithme qui doit
alors « casser une arête » choisit arbitrairement laquelle, donc produit un
ordre différent pour deux jeux de données presque identiques. La moyenne de
rangs n'a pas de cas dégénéré, se recalcule en temps linéaire, s'explique en
une phrase au propriétaire (« tu prends le pain vers la fin ») et se corrige
à la main sans surprise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from ..const import ROUTE_MIN_AISLE_SESSIONS, ROUTE_MIN_SESSIONS


@dataclass(frozen=True)
class RouteEntry:
    """La place d'un rayon dans un magasin, et pourquoi elle est là."""

    aisle_id: int
    position: int
    mean_rank: float | None
    observed_sessions: int
    source: str


def is_reliable(session_count: int) -> bool:
    """Trois sessions closes, pas moins.

    Avec une observation, un détour exceptionnel devient la loi ; avec deux,
    rien ne distingue une habitude d'une coïncidence ; à trois, une valeur
    aberrante est minoritaire. Le foyer fait une grande course par semaine :
    un magasin devient fiable en trois semaines, ce qui est acceptable pour
    une information qui ne fait que trier une liste.
    """
    return session_count >= ROUTE_MIN_SESSIONS


def session_ranks(aisle_sequence: Sequence[int]) -> dict[int, float]:
    """Le rang moyen NORMALISÉ de chaque rayon dans UNE session.

    Normaliser sur `[0, 1]` est indispensable : une session de 8 lignes et
    une de 40 doivent peser pareil, sinon le magasin n'apprend que du plus
    gros voyage.

    Les répétitions sont moyennées, pas comptées : trois yaourts d'affilée ne
    déplacent pas la crémerie de trois rangs.
    """
    total = len(aisle_sequence)
    if total == 0:
        return {}
    if total == 1:
        return {aisle_sequence[0]: 0.0}
    seen: dict[int, list[float]] = {}
    for index, aisle_id in enumerate(aisle_sequence):
        seen.setdefault(aisle_id, []).append(index / (total - 1))
    return {aisle_id: sum(ranks) / len(ranks) for aisle_id, ranks in seen.items()}


def learn_route(sessions: Sequence[Sequence[int]], *,
                default_positions: Mapping[int, int],
                pinned: Mapping[int, int] | None = None) -> list[RouteEntry]:
    """L'ordre d'un magasin : la moyenne des rangs moyens de ses sessions.

    Un rayon vu dans moins de `ROUTE_MIN_AISLE_SESSIONS` sessions garde sa
    place par défaut, même dans un magasin fiable : l'animalerie visitée une
    fois ne doit pas s'installer entre la crémerie et les fromages.

    L'apprentissage ne déplace JAMAIS une ligne épinglée — règle
    `article.manual_fields` du lot 0, transposée. Le calcul continue de
    tourner et `mean_rank` reste visible, donc on VOIT que l'ordre appris
    contredit l'ordre épinglé ; seule `position` ne bouge pas.

    Ne tronque rien : la fenêtre des dix dernières sessions est appliquée par
    l'appelant, et la tronquer une seconde fois ici la diviserait par deux en
    silence.
    """
    pinned = dict(pinned or {})
    observed: dict[int, list[float]] = {}
    for session in sessions:
        for aisle_id, rank in session_ranks(session).items():
            observed.setdefault(aisle_id, []).append(rank)

    known = sorted(set(default_positions) | set(observed) | set(pinned),
                   key=lambda aisle_id: (default_positions.get(aisle_id, 999), aisle_id))
    stats: dict[int, tuple[float | None, int]] = {}
    for aisle_id in known:
        ranks = observed.get(aisle_id, [])
        mean = sum(ranks) / len(ranks) if ranks else None
        stats[aisle_id] = (mean, len(ranks))

    def _sort_key(aisle_id: int) -> tuple[int, float, int, int]:
        mean, count = stats[aisle_id]
        default = default_positions.get(aisle_id, 999)
        if mean is None or count < ROUTE_MIN_AISLE_SESSIONS:
            # Pas assez vu ici : la place par défaut, et rien d'autre. Le
            # 1 du premier champ range ces rayons APRÈS ceux qu'on connaît
            # vraiment, sans les mélanger à eux.
            return (1, float(default), default, aisle_id)
        # Le rang par défaut départage deux moyennes égales : sans lui,
        # l'ordre dépendrait de l'itération d'un dictionnaire.
        return (0, mean, default, aisle_id)

    free = sorted((aisle_id for aisle_id in known if aisle_id not in pinned),
                  key=_sort_key)
    slots = _place(free, pinned, len(known))
    return [
        RouteEntry(
            aisle_id=aisle_id,
            position=position,
            mean_rank=stats[aisle_id][0],
            observed_sessions=stats[aisle_id][1],
            source="manual" if aisle_id in pinned else "learned",
        )
        for position, aisle_id in sorted(slots.items())
    ]


def _place(free: Sequence[int], pinned: Mapping[int, int],
           total: int) -> dict[int, int]:
    """Les rayons épinglés prennent leur place, les autres comblent le reste.

    Un rayon épinglé ne prend jamais la place d'un autre épinglé : deux
    épingles sur la même position seraient une contradiction que ni le calcul
    ni l'affichage ne sauraient trancher, alors on les range dans l'ordre.
    """
    slots: dict[int, int] = {}
    taken: set[int] = set()
    for aisle_id, wanted in sorted(pinned.items(), key=lambda pair: (pair[1], pair[0])):
        position = max(1, min(int(wanted), total))
        while position in taken:
            position += 1
        taken.add(position)
        slots[position] = aisle_id
    position = 1
    for aisle_id in free:
        while position in taken:
            position += 1
        taken.add(position)
        slots[position] = aisle_id
    return slots
