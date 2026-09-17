# parsers/__init__.py  –  registry of all parsers
from importlib import import_module

_REGISTRY: dict = {}


def _load():
    modules = [
        "pemerintah_daerah", "tribunnews", "carapandang", "gopos",
        "beritabaru", "daripohuwato", "gorontalopost", "inipohuwato",
        "wartanesia", "antaranews", "dulohupa", "seputarpohuwato",
        "hibata", "harianpost", "rri",
    ]
    for mod_name in modules:
        mod = import_module(f"parsers.{mod_name}")
        _REGISTRY[mod.SOURCE_SLUG] = mod


_load()


def get_parser(slug: str):
    """Return the parser module for a given source slug, or None."""
    if not slug:
        return None
    return (
        _REGISTRY.get(slug) or
        _REGISTRY.get(slug.replace("_", "-")) or
        _REGISTRY.get(slug.replace("-", "_"))
    )
