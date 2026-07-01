"""Generate the dashboard's public command catalog from the bot's own source.

Parses every ``src/modules/*/cog.py`` with :mod:`ast` (no bot, no Discord, no DB —
so it runs anywhere and can't drift from a running instance) and extracts each
command's name, aliases, one-line help, usage signature, and the group it belongs
to. Cogs are bucketed into the same display categories the in-Discord ``,help``
menu uses (read from ``src/modules/help/categories.py``), so the website and the
help command can never disagree about where a command lives.

Output: ``dashboard/frontend/src/data/commands.json`` — imported directly by the
React Commands page. Re-run this whenever commands change:

    python scripts/dump_commands.py
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "src" / "modules"
CATEGORIES_FILE = MODULES / "help" / "categories.py"
OUT = ROOT / "dashboard" / "frontend" / "src" / "data" / "commands.json"

# Decorators that define a command. `group`/`hybrid_group` also open a subcommand namespace.
COMMAND_DECOS = {"command", "hybrid_command", "group", "hybrid_group"}
GROUP_DECOS = {"group", "hybrid_group"}


def _literal(node: ast.AST | None):
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _deco_call(dec: ast.AST) -> tuple[str | None, str | None, ast.Call | None]:
    """From a decorator node return (attr, base_name, call).

    ``@commands.command(...)`` -> ("command", "commands", <Call>)
    ``@mygroup.command(...)``  -> ("command", "mygroup", <Call>)   (a subcommand)
    ``@commands.group``        -> ("group", "commands", None)
    """
    call = dec if isinstance(dec, ast.Call) else None
    func = call.func if call else dec
    if isinstance(func, ast.Attribute):
        base = func.value
        base_name = getattr(base, "id", None) or getattr(base, "attr", None)
        return func.attr, base_name, call
    if isinstance(func, ast.Name):
        return func.id, None, call
    return None, None, call


def _kwarg(call: ast.Call | None, key: str):
    if call is None:
        return None
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


def _signature(func: ast.AsyncFunctionDef | ast.FunctionDef) -> str:
    """A usage hint like ``<user> [amount]`` from the command's parameters.

    Drops ``self``/``ctx``; ``<required>`` for params without a default,
    ``[optional]`` for the rest (including keyword-only and ``*args``)."""
    a = func.args
    positional = [p.arg for p in a.args if p.arg not in ("self", "ctx")]
    defaults_start = len(positional) - len(a.defaults)
    parts: list[str] = []
    for i, name in enumerate(positional):
        parts.append(f"[{name}]" if i >= defaults_start else f"<{name}>")
    if a.vararg:
        parts.append(f"[{a.vararg.arg}...]")
    for i, p in enumerate(a.kwonlyargs):
        default = a.kw_defaults[i] if i < len(a.kw_defaults) else None
        parts.append(f"[{p.arg}]" if default is not None else f"<{p.arg}>")
    return " ".join(parts)


def _cog_display_name(cls: ast.ClassDef) -> str:
    """The cog's Discord name: the ``name=`` class keyword, else the class name."""
    for kw in cls.keywords:
        if kw.arg == "name":
            val = _literal(kw.value)
            if isinstance(val, str):
                return val
    return cls.name


def _is_cog(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
        # matches `commands.Cog` and bare `Cog`
        if (isinstance(base, ast.Attribute) and base.attr == "Cog") or (
            isinstance(base, ast.Name) and base.id == "Cog"
        ):
            return True
    return False


def _extract_cog(cls: ast.ClassDef) -> list[dict]:
    """Pull every command out of one cog class, resolving subcommand groups.

    Two passes: first map each method's Python name to its command name and
    parent, then walk the parent chain to build qualified names like
    ``automod words add``."""
    raw: dict[str, dict] = {}  # python func name -> record
    for node in cls.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for dec in node.decorator_list:
            attr, base, call = _deco_call(dec)
            if attr not in COMMAND_DECOS:
                continue
            name = _literal(_kwarg(call, "name")) or node.name
            aliases = _literal(_kwarg(call, "aliases")) or []
            extras = _literal(_kwarg(call, "extras")) or {}
            doc = ast.get_docstring(node) or ""
            raw[node.name] = {
                "func": node.name,
                "name": name,
                "aliases": [str(a) for a in aliases],
                "description": doc.strip().split("\n")[0].strip(),
                "signature": _signature(node),
                "is_group": attr in GROUP_DECOS,
                "example": extras.get("example") if isinstance(extras, dict) else None,
                # base is the parent group's *func* name for subcommands, else the
                # `commands` module (a top-level command).
                "parent_func": base if base and base != "commands" else None,
            }
            break

    def qualified(rec: dict) -> str:
        chain = [rec["name"]]
        seen = {rec["func"]}
        parent = rec["parent_func"]
        while parent and parent in raw and parent not in seen:
            seen.add(parent)
            prec = raw[parent]
            chain.append(prec["name"])
            parent = prec["parent_func"]
        return " ".join(reversed(chain))

    out = []
    for rec in raw.values():
        out.append(
            {
                "name": qualified(rec),
                "aliases": rec["aliases"],
                "description": rec["description"],
                "signature": rec["signature"],
                "is_group": rec["is_group"],
                "example": rec["example"],
            }
        )
    return out


def _category_map() -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Read categories.py without importing it (it pulls in Discord via Emojis).

    Returns (cog_name -> category, category -> description, ordered categories)."""
    tree = ast.parse(CATEGORIES_FILE.read_text())
    cog_to_cat: dict[str, str] = {}
    cat_desc: dict[str, str] = {}
    order: list[str] = []
    default = "Utility"
    for node in ast.walk(tree):
        # CATEGORIES carries a type annotation (AnnAssign); DEFAULT_CATEGORY doesn't (Assign).
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign):
            target, value = node.targets[0], node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == "CATEGORIES":
            assert isinstance(value, ast.Dict)
            for key_node, val_node in zip(value.keys, value.values, strict=False):
                cat = _literal(key_node)
                order.append(cat)
                # value is a tuple: (emoji, description, [cog names])
                emoji, desc, cog_list = val_node.elts  # type: ignore[attr-defined]
                cat_desc[cat] = _literal(desc) or ""
                for cog_node in cog_list.elts:  # type: ignore[attr-defined]
                    cog_to_cat[_literal(cog_node)] = cat
        if isinstance(target, ast.Name) and target.id == "DEFAULT_CATEGORY":
            default = _literal(value) or default
    cog_to_cat["__default__"] = default
    return cog_to_cat, cat_desc, order


def main() -> None:
    cog_to_cat, cat_desc, order = _category_map()
    default_cat = cog_to_cat.pop("__default__")

    # category -> list of command dicts
    buckets: dict[str, list[dict]] = {c: [] for c in order}

    for cog_file in sorted(MODULES.glob("*/cog.py")):
        tree = ast.parse(cog_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_cog(node):
                cog_name = _cog_display_name(node)
                category = cog_to_cat.get(cog_name, default_cat)
                buckets.setdefault(category, [])
                buckets[category].extend(_extract_cog(node))

    total = 0
    categories = []
    for cat in order:
        cmds = sorted(buckets.get(cat, []), key=lambda c: c["name"])
        if not cmds:
            continue
        total += len(cmds)
        categories.append(
            {"name": cat, "description": cat_desc.get(cat, ""), "commands": cmds}
        )

    payload = {"total": total, "categories": categories}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)} — {total} commands in {len(categories)} categories.")


if __name__ == "__main__":
    main()
