# Supprimer un produit ou un article — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `home_stock/product/delete` and `home_stock/article/delete` (websocket, admin only) plus the matching admin HA services: refuse on open stock or upcoming uses, hard-delete what never served, hide (`active = 0`) everything else, and make "hidden" actually hide.

**Architecture:** One application-layer module owns the rules (blockers, "never served", hide vs delete, restore cascade); storage gets the queries; the websocket and the services are thin surfaces over it. Migration `m009` adds `article.active`. Filters are added where hidden items leaked (default lists, ingredient matching, shopping suggestions); the barcode lookup keeps finding them, flagged.

**Tech Stack:** Python 3.14, Home Assistant custom component, SQLite, pytest-homeassistant-custom-component.

**Spec:** `docs/superpowers/specs/2026-09-28-suppression-produit-article-design.md` (this repo, PR #18).

## Global Constraints

- Branch from the **latest** `origin/main` at start time (the pantry work, PR "batches carry their aisle…", must already be merged; if it is not, stop and report).
- Code, identifiers, comments, commit messages in English; **user-facing error messages in French**, like the rest of the component (`messages.py`).
- No source file over 500 lines — if `websocket_api.py`/`services.py`/`application.py` would grow past it, put the new surface in its own module (e.g. `websocket_delete.py`, `deletion.py`) the way `websocket_recipes.py` was split out.
- The movement journal is **append-only**: no code path deletes or rewrites a `movement` row.
- Both surfaces admin-only; the tablet user (non-admin) must be refused — tests use `hass_read_only_access_token`.
- Websocket and service must refuse and accept exactly the same inputs (`tests/test_surface_parity.py`).
- Two-subject fixtures; every new test proven able to fail (mutate, see red, restore).
- `main`'s `security` job is red for an upstream reason (Home Assistant pins `cryptography==48.0.1`); that is the only acceptable red — say so in the PR.
- Do not touch production (`/opt`, `/etc`, live HA). Push over HTTPS. PR title conventional English; commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; PR body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Tests: `uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements.txt`, then `.venv/bin/pytest tests/<file> -q`; full run `.venv/bin/pytest tests -q` and `make test`. Host shell: wrap pipelines in `bash -c '...'`, use `command grep`.

## Review Focus

1. **A blocker must leave the database byte-identical**: count every table before/after a refused delete.
2. **"Never served" must look at CLOSED batches and at inactive recipes too** — a product whose only batch was consumed last year is history, not an error to erase.
3. **Hiding a product hides its articles without writing `article.active`** (so restoring the product brings its articles back as they were) — the filter joins on `product.active`.
4. **Scanning a hidden article's barcode** returns it with `active: false` (article and product), never "unknown".
5. **A second delete of an already hidden product** answers `hidden`, not an error, and writes nothing.

---

### Task 1: migration `m009` — `article.active`

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m009_article_active.py` (follow `m007_portion.py`'s shape and the registry the migrations use)
- Test: `tests/storage/test_migrations.py` (or the existing migration test file — find it with `command grep -rln "m008" tests`)

- [ ] **Step 1:** Failing test: a database at `m008` with two articles migrates; both have `active == 1`; a new article defaults to `1`.
- [ ] **Step 2:** Run → fail.
- [ ] **Step 3:** `ALTER TABLE article ADD COLUMN active INTEGER NOT NULL DEFAULT 1`; register the migration.
- [ ] **Step 4:** Green (plus the whole `tests/storage/`). Mutation: default `0` → red.
- [ ] **Step 5:** Commit `feat(home-stock): articles can be hidden (migration m009)`.

### Task 2: the rules — blockers, never served, delete or hide

**Files:**
- Create: `custom_components/home_stock/deletion.py` (application layer) and the SQL it needs in `storage/repositories.py` or a new `storage/deletion.py` if `repositories.py` would pass 500 lines (it is already past it — prefer the new file)
- Modify: `custom_components/home_stock/messages.py` (French message for `delete_blocked`)
- Test: `tests/test_deletion.py`

**Interfaces (Produces):**

```python
@dataclass(frozen=True)
class Blocker:
    kind: str            # 'open_batches' | 'active_recipes' | 'planned_meals' | 'shopping_items'
                         # | 'recurring' | 'equipment' | 'battery' | 'leftover' | 'shopping_session'
    count: int
    names: tuple[str, ...]   # recipe/meal/equipment names, locations for batches; may be empty

class DeleteBlocked(Exception):
    def __init__(self, blockers: tuple[Blocker, ...]): ...
    # str(err) is the French message: "Encore 2 lots en stock (Frigo) ; utilisé dans 3 recettes : Curry…, Riz…, Tajine"

def product_blockers(conn, product_id: int) -> tuple[Blocker, ...]
def article_blockers(conn, article_id: int) -> tuple[Blocker, ...]
def product_never_served(conn, product_id: int) -> bool
def article_never_served(conn, article_id: int) -> bool
# on the manager (application.py or deletion.py, called from the manager):
def delete_product(self, product_id: int) -> str      # 'deleted' | 'hidden'; raises LookupError (unknown), DeleteBlocked
def delete_article(self, article_id: int) -> str
def set_article_active(self, article_id: int, active: bool) -> None   # restoring an article restores its product
```

Rules exactly as spec §1–§2. Everything in ONE `db.write()` transaction; blockers computed inside it before any write. Hard delete of a product removes, in dependency order: `ingredient_alias`, then per article `barcode`, `packaging`, `price`, then `article`, then `product`. Hard delete of an article removes its `barcode`, `packaging`, `price`, then the article. Names in messages: at most three, then "…".

- [ ] **Step 1:** Failing tests, one per blocker kind for products and for articles (two-subject fixtures: the blocked product and an unrelated one), each asserting `DeleteBlocked`, the French message naming the blocker, and **all table row counts unchanged** (Review Focus 1). Then: never-served product → `deleted` and its articles/barcodes/packagings/prices/aliases gone, the other product untouched; product with only a CLOSED batch → `hidden`, movement count and rows identical (Review Focus 2); product used only by an INACTIVE recipe → `hidden`; second delete of a hidden product → `hidden`, no write (Review Focus 5); unknown id → `LookupError`; hiding a product leaves `article.active` untouched (Review Focus 3); restoring an article of a hidden product sets both active.
- [ ] **Step 2:** Run → fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Green; mutation checks (drop one blocker query → its test red; count only open batches in never-served → Focus 2 red).
- [ ] **Step 5:** Commit `feat(home-stock): rules to delete or hide a product or an article`.

### Task 3: "hidden" actually hides

**Files:**
- Modify: `storage/repositories.py::list_products` callers and `websocket_api.py` `home_stock/products/list` (default hides, optional `include_hidden: bool`), `domain/matching.py` callers (the product list fed to `candidates` excludes hidden products), the shopping suggestion query (find it: `command grep -rn "suggest" custom_components/home_stock`), every article listing that should skip hidden articles (`a.active = 1 AND p.active = 1`)
- Modify: `storage/products.py::find_by_barcode` and the `lookup` result — keep finding hidden items, add `active` for the article and its product
- Modify: `article/update` schema accepts `active: vol.In((0, 1))` and routes it through `set_article_active`
- Test: `tests/test_hidden.py`

- [ ] **Step 1:** Failing tests (two products, one hidden): default `products/list` omits it and `include_hidden` returns it; ingredient matching never proposes it; suggestions skip it; low-stock alerts skip it; scanning its barcode returns it with `active: false` for article and product (Review Focus 4); a hidden article of a visible product is skipped where articles are listed; `article/update {active: 1}` on an article of a hidden product restores both.
- [ ] **Step 2–4:** fail → implement → green; mutation checks.
- [ ] **Step 5:** Commit `feat(home-stock): hidden products and articles stay out of lists and matching`.

### Task 4: surfaces — websocket and admin services

**Files:**
- Create: `custom_components/home_stock/websocket_delete.py` (register from where `websocket_recipes.async_register_recipe_commands` is registered) — or add to `websocket_api.py` if it stays under 500 lines (it will not)
- Modify: `custom_components/home_stock/services.py` (register with `homeassistant.helpers.service.async_register_admin_service`, `supports_response=SupportsResponse.ONLY` or `OPTIONAL` — check the current HA docs for which fits a response-returning admin service), `services.yaml`, `translations/*.json` / `strings.json`
- Test: `tests/test_delete_surfaces.py`; extend `tests/test_surface_parity.py` (and `tests/test_offline_queue_contract.py` if its contract enumerates every command)

Websocket: `home_stock/product/delete {product_id}` and `home_stock/article/delete {article_id}`, decorated `@websocket_api.require_admin`, result `{"outcome": ...}`; `DeleteBlocked` → `connection.send_error(msg["id"], "delete_blocked", str(err))`; `LookupError` through the existing `_send_domain_error`. After success, `await runtime.coordinator.async_request_refresh()`.

- [ ] **Step 1:** Failing tests: admin websocket delete → `deleted`/`hidden`; non-admin websocket (`hass_read_only_access_token`) → `unauthorized`, nothing written; admin service returns the same outcome as response data; non-admin service call → `Unauthorized`, nothing written; blocked → `delete_blocked` on both surfaces with the same French text; parity cases added (unknown id refused on both, blocked refused on both, valid accepted on both); the sensors reflect a hidden product without waiting for the interval.
- [ ] **Step 2–4:** fail → implement → green; mutation checks (remove `require_admin` → the non-admin test goes red).
- [ ] **Step 5:** Commit `feat(home-stock): delete a product or an article from the websocket and admin services`.

### Task 5: PR, CI, merge, release

- [ ] Full suite `.venv/bin/pytest tests -q` and `make test` green; test count before/after recorded.
- [ ] PR `feat(home-stock): delete or hide a product or an article`; body lists the behaviour change (`products/list` hides hidden products by default, `include_hidden` to see them; the HA panel has no restore button — restore via `product/update`/`article/update`), and the pre-existing `security` red.
- [ ] CI green except `security`; squash-merge; wait for `Release`; record the version.
- [ ] **Stop and report** (in French): version, PR URL, test counts, mutation checks, deviations. No production step.
