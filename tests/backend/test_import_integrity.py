"""Every relative import in the package must resolve — including lazy
imports inside function bodies, which module-import alone never executes.

Regression for the B7/B9 lifts: function bodies moved between package
depths kept their original dot-counts, so e.g. `.data_access` inside
pipeline/profile_scoring.py resolved to the nonexistent
pipeline.data_access and only crashed at runtime, mid-newsletter.
"""
import ast
import importlib.util
import pathlib


def test_all_relative_imports_resolve():
    root = pathlib.Path(__file__).resolve().parents[2] / "theseus_insight"
    bad = []

    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root.parent)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            pkg_parts = parts[:-1]          # an __init__.py's module IS its package
        else:
            pkg_parts = parts[:-1]
        # For a non-__init__ module, relative level 1 = its containing package.
        # For an __init__.py, level 1 = the package itself.
        if rel.name != "__init__.py":
            base_parts = pkg_parts
        else:
            base_parts = parts[:-1]

        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                if node.level > len(base_parts):
                    bad.append(f"{rel}:{node.lineno} `from {'.' * node.level}{node.module or ''}` escapes the package")
                    continue
                target_parts = base_parts[: len(base_parts) - node.level + 1]
                target = ".".join(target_parts + ([node.module] if node.module else []))
                try:
                    spec = importlib.util.find_spec(target)
                except (ImportError, ModuleNotFoundError, ValueError):
                    spec = None
                if spec is None:
                    bad.append(f"{rel}:{node.lineno} `from {'.' * node.level}{node.module or ''}` -> {target} (unresolvable)")

    assert bad == [], "Broken relative imports:\n" + "\n".join(bad)
