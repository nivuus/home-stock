"""Split a Grocy recipe description into pages, titles, bullets and images.

Pure: no hass, no network, no SQLite. This is the part that breaks, so it is
the part that gets tested with plain pytest against the 102 real descriptions.

Three traps, measured on the real database — do not rediscover them:

1. **There is no bare `<h3>`.** All 234 carry a style attribute. A literal
   `<h3>` pattern finds zero titles and silently produces nameless steps.
2. **A description with no `page-recipes` must yield ONE page, not zero.**
   That is the shape of the 15 type-`1` recipes, and the exact shape of a
   silent loss: a findall that finds nothing, a loop that never runs, an
   import that reports "0 anomalies".
3. **`html.unescape()` runs exactly once.** Grocy already decodes `&#x27;`
   back to `'` on save; a second pass would turn a legitimate `&amp;lt;`
   into `<`.
"""
from __future__ import annotations

import html as _html
import re
from typing import NamedTuple

PAGE_CLASS = "page-recipes"

# `[^>]*` is mandatory: every h3 in the base carries a style attribute.
_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)
_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL)
_IMG_SRC = re.compile(r"<img[^>]*?\ssrc\s*=\s*([\"'])(.*?)\1", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_OPEN_DIV = re.compile(r"<div\b[^>]*>", re.IGNORECASE)
_CLOSE_DIV = re.compile(r"</div\s*>", re.IGNORECASE)
_PAGE_DIV = re.compile(
    rf"<div\b[^>]*class\s*=\s*[\"'][^\"']*\b{PAGE_CLASS}\b[^\"']*[\"'][^>]*>",
    re.IGNORECASE)

# La ligne méta de la couverture : trois <span>, toujours trois, dans cet
# ordre — durée, apport, ustensiles. Le 🔥 du milieu est délibérément absent
# de Meta : c'est une valeur CALCULÉE depuis le catalogue par
# recettes_miseenpage.py, donc un chiffre daté qu'on recalcule à l'affichage.
#
# La durée n'est pas toujours « 15 min » : une recette dit « 30 sec » (la
# mayonnaise au mixeur) et une autre « 8-10 min » (le gaspacho). Un motif qui
# n'accepte que les minutes entières rend deux total_minutes à NULL sans que
# personne s'en aperçoive. Une fourchette est lue par sa BORNE HAUTE (on
# planifie sur le pire), et les secondes montent à la minute (« moins d'une
# minute » n'est pas « zéro »).
_DURATION = re.compile(
    r"⏱\s*~?\s*(\d{1,3})\s*(?:[-–—]\s*(\d{1,3})\s*)?(min|sec|h)\b",
    re.IGNORECASE)
_SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.DOTALL)
_SUMMARY = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)
# L'emoji de tête du troisième span : 🍳 sur 86 recettes, 🌀 sur la
# mayonnaise. Retirer « le premier caractère non alphanumérique » plutôt que
# de lister les emojis, sinon la 87ᵉ recette se perd sur un pictogramme neuf.
_LEADING_PICTOGRAM = re.compile(r"^[^\w(]+\s*")

_STEP_TITLE = re.compile(r"^Étape\s+\d+\s*[—–-]\s*(.*)$")

# L'étiquette contient des espaces (#Repos poulet:600) et 327 des 443 `#` de
# la base sont des couleurs CSS. Interdire #, :, ;, < et > dans l'étiquette
# est ce qui sépare les deux — un motif plus lâche fait de
# `style="color:#888;font-size:12px"` un minuteur de 12 secondes.
TIMER = re.compile(r"#([^#:;<>]{1,40}?):(\d{1,5})\b")


class Page(NamedTuple):
    """One page of a recipe description."""

    kind: str                 # "cover" | "ingredients" | "step" | "other"
    title: str | None
    images: list[str]
    bullets: list[str]
    html: str


class Instruction(NamedTuple):
    """One line of a step, with at most one timer.

    `recipe_instruction` carries a CHECK ((timer_label IS NULL) =
    (timer_seconds IS NULL)): a label without a duration cannot be born,
    because the pattern demands both.
    """

    text: str
    timer_label: str | None
    timer_seconds: int | None


class Meta(NamedTuple):
    """The cover's meta line. No kcal — see the module docstring."""

    total_minutes: int | None
    utensils: str | None
    summary: str | None


def texte(fragment: str) -> str:
    """Tags out, entities decoded ONCE, whitespace normalised.

    The order matters: unescaping first would turn a literal `&lt;strong&gt;`
    into a tag, which the stripping pass would then eat.
    """
    if not fragment:
        return ""
    sans_balise = _TAG.sub(" ", fragment)
    return " ".join(_html.unescape(sans_balise).split())


def _fragments(description: str) -> list[str]:
    """The top-level `page-recipes` divs, by depth scan.

    A non-greedy `re.findall` would stop at the first inner `</div>`: the
    pages contain nested divs, so the scan has to count them.
    """
    fragments: list[str] = []
    for depart in [m.start() for m in _PAGE_DIV.finditer(description)]:
        if fragments and depart < _fin_precedente[0]:
            continue                      # imbriquée dans la page précédente
        profondeur = 0
        position = depart
        fin = len(description)
        while position < len(description):
            ouvrant = _OPEN_DIV.search(description, position)
            fermant = _CLOSE_DIV.search(description, position)
            if fermant is None:
                break
            if ouvrant is not None and ouvrant.start() < fermant.start():
                profondeur += 1
                position = ouvrant.end()
                continue
            profondeur -= 1
            position = fermant.end()
            if profondeur == 0:
                fin = position
                break
        fragments.append(description[depart:fin])
        _fin_precedente[0] = fin
    return fragments


# Le scan a besoin de savoir où la page précédente s'est refermée pour écarter
# les <div class="page-recipes"> imbriqués. Une liste d'un élément plutôt
# qu'un global : la fonction reste pure vis-à-vis de son appelant.
_fin_precedente = [0]


def _page(fragment: str) -> Page:
    titres = _H3.findall(fragment)
    titre_brut = texte(titres[0]) if titres else None
    images = [m.group(2) for m in _IMG_SRC.finditer(fragment)]
    bullets = [texte(b) for b in _LI.findall(fragment)]
    bullets = [b for b in bullets if b]

    kind = "other"
    titre = titre_brut
    if titre_brut == "Ingrédients":
        kind = "ingredients"
    elif titre_brut and titre_brut.startswith("Étape"):
        kind = "step"
        # Le numéro ORDONNE, il ne titre pas : « Étape 10 — Dresser » a pour
        # titre « Dresser », et la position vient de la place de la page.
        capture = _STEP_TITLE.match(titre_brut)
        titre = capture.group(1).strip() if capture else titre_brut
    elif titre_brut is None and _DURATION.search(fragment):
        kind = "cover"
    return Page(kind=kind, title=titre, images=images, bullets=bullets,
                html=fragment)


def decouper(description: str | None) -> list[Page]:
    """The pages of a description, in order.

    A description with no `page-recipes` div yields ONE page holding the whole
    fragment — never zero. This branch is written first and on purpose: it is
    what saves the 15 type-`1` recipes from disappearing without a sound.
    """
    if not description:
        return []
    _fin_precedente[0] = 0
    fragments = _fragments(description)
    if not fragments:
        return [_page(description)]
    return [_page(fragment) for fragment in fragments]


def _minutes(fragment: str) -> int | None:
    capture = _DURATION.search(fragment)
    if capture is None:
        return None
    borne = int(capture.group(2) or capture.group(1))
    unite = capture.group(3).lower()
    if unite == "h":
        return borne * 60
    if unite == "sec":
        return max(1, round(borne / 60))
    return borne


def meta(description: str | None) -> Meta:
    """The cover's meta line: minutes and utensils. Never the kcal.

    Read off the cover PAGE, not off the raw description: the three spans are
    the cover's, and looking for them anywhere in the HTML would pick up a
    step's styling on the day someone adds a span to one.
    """
    if not description:
        return Meta(None, None, None)
    couverture = next((p for p in decouper(description) if p.kind == "cover"),
                      None)
    if couverture is None:
        return Meta(None, None, None)
    spans = [texte(s) for s in _SPAN.findall(couverture.html)]
    ustensiles = None
    if len(spans) >= 2:
        ustensiles = _LEADING_PICTOGRAM.sub("", spans[-1]).strip() or None
    resume = _SUMMARY.search(couverture.html)
    return Meta(
        total_minutes=_minutes(couverture.html),
        utensils=ustensiles,
        summary=texte(resume.group(1)) or None if resume else None,
    )


def minuteurs(fragment: str) -> list[tuple[str, int]]:
    """The `#Label:seconds` timers of a fragment, in order of appearance."""
    if not fragment:
        return []
    return [(label.strip(), int(seconds))
            for label, seconds in TIMER.findall(fragment)]


def instructions(bullet: str) -> list[Instruction]:
    """One bullet, one or two instructions.

    Eight bullets in the base carry two timers — they are two-sided cooks
    ("saisir 4 min par face. #Poulet face 1:240 #Poulet face 2:240"). The
    bullet is SPLIT: the first instruction keeps the sentence and the first
    timer, the second carries the SECOND TIMER'S LABEL as its text. Nothing is
    invented — that string is already in the source — and no timer is lost.

    Keeping only the first would drop 8 timers; merging them into 480 s would
    be wrong, since you turn the chicken between the two.
    """
    trouves = minuteurs(bullet)
    phrase = texte(TIMER.sub(" ", bullet))
    if not trouves:
        return [Instruction(text=phrase, timer_label=None, timer_seconds=None)]
    resultat = [Instruction(text=phrase, timer_label=trouves[0][0],
                            timer_seconds=trouves[0][1])]
    for label, secondes in trouves[1:]:
        resultat.append(Instruction(text=label, timer_label=label,
                                    timer_seconds=secondes))
    return resultat
