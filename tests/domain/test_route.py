"""L'ordre du parcours d'un magasin, appris de l'ordre des scans. Pur.

Une moyenne de rangs, et pas un tri topologique : le tri topologique sur les
précédences observées est la solution élégante, et elle meurt sur le premier
cycle — or les cycles sont la norme, on retourne à la boulangerie en fin de
course. Un algorithme qui doit alors « casser une arête » choisit
arbitrairement laquelle, donc produit un ordre différent pour deux jeux de
données presque identiques.
"""
import pytest

from custom_components.home_stock.const import (
    ROUTE_MIN_AISLE_SESSIONS, ROUTE_MIN_SESSIONS, ROUTE_SESSION_WINDOW,
)
from custom_components.home_stock.domain.route import (
    RouteEntry, is_reliable, learn_route, session_ranks,
)

# Rayons par défaut : 1 → 5, dans cet ordre.
DEFAULTS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}


def _order(entries):
    return [entry.aisle_id for entry in entries]


# --- le rang moyen d'une session -------------------------------------------

def test_a_clean_walk_gives_back_its_own_order():
    ranks = session_ranks([1, 2, 3])
    assert ranks[1] < ranks[2] < ranks[3]
    assert all(0.0 <= value <= 1.0 for value in ranks.values())


def test_repeated_scans_of_one_aisle_average_out():
    """Trois yaourts d'affilée ne déplacent pas la crémerie de trois rangs."""
    once = session_ranks([1, 2, 3])
    thrice = session_ranks([1, 2, 2, 2, 3])
    assert once[2] == pytest.approx(0.5)
    assert thrice[2] == pytest.approx(0.5)


def test_a_backtrack_pulls_the_aisle_towards_the_middle():
    """On revient chercher le lait oublié : la crémerie glisse, elle ne saute
    pas à la fin."""
    straight = session_ranks([1, 2, 3, 4, 5])
    back = session_ranks([1, 2, 3, 4, 5, 2])
    assert straight[2] < back[2] < back[5]


def test_an_empty_session_ranks_nothing():
    assert session_ranks([]) == {}


# --- l'ordre appris d'un magasin -------------------------------------------

def test_a_full_cycle_produces_a_stable_order():
    """LE cas qui tue un tri topologique : A→B→C→A. Ici, un ordre, et le
    même ordre à chaque appel."""
    sessions = [[1, 2, 3, 1]] * 3
    first = learn_route(sessions, default_positions=DEFAULTS)
    second = learn_route(sessions, default_positions=DEFAULTS)
    assert _order(first) == _order(second)
    assert set(_order(first)) == {1, 2, 3, 4, 5}


def test_two_sessions_of_very_different_sizes_weigh_the_same():
    """8 lignes contre 40 : sans normalisation, la grande écraserait la
    petite et le magasin apprendrait un seul voyage."""
    small = [1, 2]
    large = [2] * 20 + [1] * 20
    entries = learn_route([small, large, small], default_positions=DEFAULTS)
    ranks = {entry.aisle_id: entry.mean_rank for entry in entries}
    # Deux sessions sur trois passent par 1 puis 2 : c'est cet ordre qui gagne.
    assert ranks[1] < ranks[2]


def test_an_aisle_seen_in_only_one_session_keeps_its_default_place():
    """L'animalerie visitée une fois ne doit pas s'installer entre la
    crémerie et les fromages."""
    assert ROUTE_MIN_AISLE_SESSIONS == 2
    sessions = [[3, 1, 2], [3, 1, 2], [3, 1, 2, 5]]
    entries = {entry.aisle_id: entry for entry in
               learn_route(sessions, default_positions=DEFAULTS)}
    assert entries[5].observed_sessions == 1
    # Le rang moyen reste VISIBLE — c'est l'explication qu'on montre dans les
    # réglages — mais il ne déplace pas le rayon.
    assert entries[5].mean_rank is not None
    assert entries[5].position == 5
    assert _order(learn_route(sessions, default_positions=DEFAULTS))[:3] == [3, 1, 2]


def test_an_unobserved_aisle_keeps_aisle_position():
    entries = {entry.aisle_id: entry for entry in
               learn_route([[3, 1], [3, 1]], default_positions=DEFAULTS)}
    assert entries[4].mean_rank is None
    assert entries[4].observed_sessions == 0


def test_a_tie_is_broken_by_the_default_position():
    """Déterminisme : deux moyennes égales ne doivent pas dépendre de
    l'ordre d'itération d'un dictionnaire."""
    sessions = [[2, 1], [1, 2]] * 2
    entries = learn_route(sessions, default_positions=DEFAULTS)
    ranks = {entry.aisle_id: entry.mean_rank for entry in entries}
    assert ranks[1] == pytest.approx(ranks[2])
    assert _order(entries).index(1) < _order(entries).index(2)


def test_the_positions_are_contiguous_from_one():
    entries = learn_route([[3, 1], [3, 1]], default_positions=DEFAULTS)
    assert [entry.position for entry in entries] == list(range(1, len(entries) + 1))


# --- épingler ---------------------------------------------------------------

def test_a_pinned_aisle_is_never_moved_by_learning():
    """Règle `article.manual_fields` du lot 0, transposée. Le calcul continue
    de tourner et `mean_rank` reste visible — on VOIT donc que l'ordre appris
    contredit l'ordre épinglé — mais `position` ne bouge pas."""
    sessions = [[5, 4, 3, 2, 1]] * 3
    entries = {entry.aisle_id: entry for entry in learn_route(
        sessions, default_positions=DEFAULTS, pinned={1: 1})}
    assert entries[1].position == 1
    assert entries[1].source == "manual"
    assert entries[1].mean_rank is not None      # l'apprentissage reste visible
    assert entries[5].source == "learned"


def test_a_pinned_aisle_does_not_take_the_place_of_another():
    sessions = [[5, 4, 3, 2, 1]] * 3
    entries = learn_route(sessions, default_positions=DEFAULTS, pinned={1: 1})
    positions = [entry.position for entry in entries]
    assert sorted(positions) == list(range(1, len(entries) + 1))
    assert len(set(positions)) == len(positions)


def test_learning_stays_available_after_unpinning():
    """Le bouton « reprendre l'apprentissage » rend la ligne à l'automatisme."""
    sessions = [[5, 4, 3, 2, 1]] * 3
    free = learn_route(sessions, default_positions=DEFAULTS)
    assert _order(free)[0] == 5
    assert all(entry.source == "learned" for entry in free)


# --- la fiabilité -----------------------------------------------------------

@pytest.mark.parametrize("count, reliable", [(0, False), (1, False), (2, False),
                                             (3, True), (10, True)])
def test_fewer_than_three_sessions_is_not_reliable(count, reliable):
    """Avec une observation, un détour exceptionnel devient la loi ; avec
    deux, rien ne distingue une habitude d'une coïncidence ; à trois, une
    valeur aberrante est minoritaire. Le foyer fait une grande course par
    semaine : trois semaines."""
    assert ROUTE_MIN_SESSIONS == 3
    assert is_reliable(count) is reliable


def test_only_the_last_ten_sessions_are_kept():
    """Un magasin réaménage ses rayons, et une moyenne sur toute l'histoire
    mettrait des mois à s'en apercevoir. Le tronquage est fait par
    l'appelant ; ce test épingle que `learn_route` n'en tronque PAS un
    deuxième, ce qui diviserait la fenêtre par deux en silence."""
    assert ROUTE_SESSION_WINDOW == 10
    sessions = [[1, 2]] * ROUTE_SESSION_WINDOW
    entries = {entry.aisle_id: entry for entry in
               learn_route(sessions, default_positions=DEFAULTS)}
    assert entries[1].observed_sessions == ROUTE_SESSION_WINDOW


def test_learn_route_is_deterministic():
    """Deux appels, même sortie, y compris sur des égalités parfaites."""
    sessions = [[1, 2, 3], [3, 2, 1], [2, 1, 3]]
    first = learn_route(sessions, default_positions=DEFAULTS, pinned={4: 2})
    second = learn_route(sessions, default_positions=DEFAULTS, pinned={4: 2})
    assert first == second


def test_an_empty_history_returns_the_default_order_untouched():
    entries = learn_route([], default_positions=DEFAULTS)
    assert _order(entries) == [1, 2, 3, 4, 5]
    assert all(entry.mean_rank is None for entry in entries)
    assert all(isinstance(entry, RouteEntry) for entry in entries)
