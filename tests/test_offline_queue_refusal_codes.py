"""Every error code the integration sends is classified by the offline queue.

frontend/src/file-attente.ts drops a queued write only when the server answers
with a code from its closed set of final refusals (`FINAL_REFUSAL_CODES`);
any other code keeps the write at the head of the queue to be retried. A new
refusal code added here and forgotten there would therefore block the queue
behind it on every replay. This test reads both sides and fails on any code
the integration can send that the front end does not know.
"""
import ast
import re
from pathlib import Path

from custom_components.home_stock import messages
from custom_components.home_stock.domain.errors import TranslatedError

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION = ROOT / "custom_components" / "home_stock"
QUEUE_SOURCE = ROOT / "frontend" / "src" / "file-attente.ts"

# Answered while the config entry is unloaded for a moment: deliberately
# retried by the queue, never a final refusal.
TRANSIENT_CODES = {"not_loaded"}


def _module_constants(tree: ast.Module) -> dict[str, str]:
    constants = {}
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if (isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            constants[target.id] = node.value.value
    return constants


def _translated_codes() -> set[str]:
    """`code` of every TranslatedError class (error_surface sends `err.code`)."""
    # Import every module so each subclass is defined before walking them.
    import importlib
    for path in INTEGRATION.rglob("*.py"):
        if path.name != "__init__.py" or path.parent != INTEGRATION:
            module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
            importlib.import_module(module)
    found, pending = set(), [TranslatedError]
    while pending:
        cls = pending.pop()
        found.add(cls.code)
        pending.extend(cls.__subclasses__())
    return found


def _sent_codes() -> set[str]:
    """The codes passed to `connection.send_error` anywhere in the integration."""
    french_codes = {code for _, code, _ in messages.DOMAIN_ERROR_PATTERNS}
    french_codes.add(messages.GENERIC_CODE)
    imported: dict[str, str] = {}
    for path in INTEGRATION.rglob("*.py"):
        imported |= _module_constants(ast.parse(path.read_text(), str(path)))

    codes: set[str] = set()
    unresolved: list[str] = []
    for path in sorted(INTEGRATION.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        local = imported | _module_constants(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "send_error"):
                continue
            where = f"{path.relative_to(ROOT)}:{node.lineno}"
            args = node.args
            if len(args) >= 2 and isinstance(args[1], ast.Constant):
                codes.add(args[1].value)
            elif len(args) >= 2 and isinstance(args[1], ast.Name) and args[1].id in local:
                codes.add(local[args[1].id])
            elif (len(args) >= 2 and isinstance(args[1], ast.Attribute)
                  and args[1].attr == "code"):
                codes |= _translated_codes()
            elif (len(args) == 2 and isinstance(args[1], ast.Starred)
                  and isinstance(args[1].value, ast.Call)
                  and getattr(args[1].value.func, "id", None) == "french_error"):
                codes |= french_codes
            elif (len(args) >= 2 and isinstance(args[1], ast.Name)
                  and _assigned_from_french_error(tree, node, args[1].id)):
                codes |= french_codes
            else:
                unresolved.append(where)
    assert not unresolved, f"send_error with a code this test cannot read: {unresolved}"
    return codes


def _assigned_from_french_error(tree: ast.Module, call: ast.Call, name: str) -> bool:
    """True when `name` is unpacked from `french_error(...)` in the function
    that holds `call` (websocket_api._send_domain_error)."""
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if call not in ast.walk(func):
            continue
        for node in ast.walk(func):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", None) == "french_error"
                    and isinstance(node.targets[0], ast.Tuple)
                    and any(getattr(e, "id", None) == name for e in node.targets[0].elts)):
                return True
    return False


def _final_refusal_codes() -> set[str]:
    source = QUEUE_SOURCE.read_text()
    block = re.search(r"FINAL_REFUSAL_CODES[^=]*=\s*new Set\(\[(.*?)\]\)", source, re.S)
    assert block, "FINAL_REFUSAL_CODES not found in file-attente.ts"
    body = re.sub(r"//[^\n]*", "", block.group(1))
    return set(re.findall(r"'([a-z_]+)'", body))


def test_the_reader_sees_the_codes_the_integration_is_known_to_send():
    codes = _sent_codes()
    for expected in ("not_loaded", "invalid_field", "insufficient_stock", "delete_blocked",
                     "shopping_refused", "conversion_refused", "invalid_format"):
        assert expected in codes


def test_every_code_sent_is_a_final_refusal_or_a_known_transient_answer():
    unknown = _sent_codes() - _final_refusal_codes() - TRANSIENT_CODES
    assert not unknown, (
        f"codes sent by the integration but unknown to the offline queue: {sorted(unknown)}; "
        "add each to FINAL_REFUSAL_CODES (frontend/src/file-attente.ts) if a replay "
        "would get the same answer, or to TRANSIENT_CODES here if it would not")


def test_a_transient_code_is_never_listed_as_final():
    assert not (TRANSIENT_CODES & _final_refusal_codes())
