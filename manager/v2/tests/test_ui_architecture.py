import ast
from pathlib import Path


UI_DIR = Path(__file__).resolve().parents[1] / "app" / "ui"


def test_ui_does_not_import_browser_storage_or_selenium() -> None:
    forbidden = ("selenium", "app.browser", "app.storage")
    for path in UI_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        assert not any(module.startswith(forbidden) for module in modules), path.name


def test_main_window_declares_all_required_tabs() -> None:
    source = (UI_DIR / "main_window.py").read_text(encoding="utf-8")

    for title in ("الحسابات", "تحديث الإعلانات", "نشر الإعلانات", "التشغيل والسجل", "الإعدادات"):
        assert title in source
