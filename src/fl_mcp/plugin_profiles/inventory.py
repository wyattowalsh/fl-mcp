"""Local plugin and preset inventory scanning."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import cast

from fl_mcp.schemas.plugin_profiles import (
    PluginFormat,
    PluginInventoryItem,
    PluginInventoryStatus,
    PluginKind,
    PluginPresetAsset,
)

PLUGIN_FORMAT_BY_SUFFIX: dict[str, PluginFormat] = {
    ".component": "au",
    ".vst": "vst",
    ".vst3": "vst3",
    ".clap": "clap",
    ".fst": "fst",
    ".fxp": "fxp",
    ".fxb": "fxb",
}
PLUGIN_BUNDLE_SUFFIXES = {".component", ".vst", ".vst3", ".clap"}
PRESET_SUFFIXES = {".fst", ".fxp", ".fxb"}

VENDOR_HINTS: tuple[tuple[str, str], ...] = (
    ("fabfilter", "FabFilter"),
    ("sylenth", "LennarDigital"),
    ("serum", "Xfer Records"),
    ("shaperbox", "Cableguys"),
    ("camelcrusher", "Camel Audio"),
    ("drumazon", "D16 Group"),
    ("valhalla", "Valhalla DSP"),
    ("trash", "iZotope"),
    ("izotope", "iZotope"),
    ("flstudio", "Image-Line"),
    ("flstudiovsti", "Image-Line"),
    ("fruity", "Image-Line"),
    ("maximus", "Image-Line"),
    ("grossbeat", "Image-Line"),
    ("flex", "Image-Line"),
    ("directwave", "Image-Line"),
    ("edison", "Image-Line"),
    ("slicex", "Image-Line"),
    ("sytrus", "Image-Line"),
    ("harmor", "Image-Line"),
    ("patcher", "Image-Line"),
    ("wavecandy", "Image-Line"),
)


def normalize_plugin_id(value: str) -> str:
    """Normalize a plugin display name or path stem to a stable lookup key."""

    text = value.casefold()
    text = text.replace("(mono)", " mono ")
    text = re.sub(r"[^a-z0-9]+", ".", text)
    text = re.sub(r"\.+", ".", text).strip(".")
    aliases = {
        "pro.q.3": "fabfilter.pro_q3",
        "fabfilter.pro.q.3": "fabfilter.pro_q3",
        "pro.c.2": "fabfilter.pro_c2",
        "fabfilter.pro.c.2": "fabfilter.pro_c2",
        "fabfilter.pro.c.2.mono": "fabfilter.pro_c2",
        "fabfilter.micro": "fabfilter.micro",
        "fabfilter.micro.mono": "fabfilter.micro",
        "fabfilter.one": "fabfilter.one",
        "fabfilter.pro.ds": "fabfilter.pro_ds",
        "fabfilter.pro.ds.mono": "fabfilter.pro_ds",
        "fabfilter.pro.g": "fabfilter.pro_g",
        "fabfilter.pro.g.mono": "fabfilter.pro_g",
        "fabfilter.pro.l.2": "fabfilter.pro_l2",
        "fabfilter.pro.mb": "fabfilter.pro_mb",
        "fabfilter.pro.mb.mono": "fabfilter.pro_mb",
        "fabfilter.pro.r": "fabfilter.pro_r",
        "fabfilter.saturn.2": "fabfilter.saturn2",
        "fabfilter.simplon": "fabfilter.simplon",
        "fabfilter.timeless.3": "fabfilter.timeless3",
        "fabfilter.twin.3": "fabfilter.twin3",
        "fabfilter.volcano.3": "fabfilter.volcano3",
        "serum2": "xfer.serum2",
        "serum.2": "xfer.serum2",
        "serum": "xfer.serum2",
        "serum.2.fx": "xfer.serum2_fx",
        "sylenth1": "lennardigital.sylenth1",
        "sylenth.1": "lennardigital.sylenth1",
        "shaperbox.2": "cableguys.shaperbox2",
        "fl.studio": "image_line.fl_studio_vst",
        "fl.studio.vsti": "image_line.fl_studio_vst",
        "camelcrusher": "camel_audio.camelcrusher",
        "drumazon": "d16.drumazon",
        "valhallaroom": "valhalla.valhallaroom",
        "valhalla.room": "valhalla.valhallaroom",
        "trash": "izotope.trash",
        "trash.2": "izotope.trash",
        "izotope.trash": "izotope.trash",
        "fruity.parametric.eq.2": "image_line.fruity_parametric_eq_2",
        "fruity.limiter": "image_line.fruity_limiter",
        "maximus": "image_line.maximus",
        "gross.beat": "image_line.gross_beat",
        "flex": "image_line.flex",
        "fpc": "image_line.fpc",
        "directwave": "image_line.directwave",
        "edison": "image_line.edison",
        "slicex": "image_line.slicex",
        "sytrus": "image_line.sytrus",
        "harmor": "image_line.harmor",
        "patcher": "image_line.patcher",
        "fruity.reeverb.2": "image_line.fruity_reeverb_2",
        "fruity.delay.3": "image_line.fruity_delay_3",
        "fruity.soft.clipper": "image_line.fruity_soft_clipper",
        "wave.candy": "image_line.wave_candy",
    }
    return aliases.get(text, text.replace(".", "_"))


def _display_name_from_path(path: Path) -> str:
    name = path.stem
    if name.endswith("_x64"):
        name = name[:-4]
    if name.startswith("FabFilter "):
        return name
    parent = path.parent.name
    if parent in {"VST3", "AudioUnit", "VST", "CLAP", "New"} and not name.startswith("FabFilter"):
        if name in {"Pro-Q 3", "Pro-C 2", "Pro-DS", "Pro-G", "Pro-L 2", "Pro-MB"}:
            return f"FabFilter {name}"
        if name in {"Pro-R", "Saturn 2", "Simplon", "Timeless 3", "Volcano 3"}:
            return f"FabFilter {name}"
        if name in {"One", "Twin 3", "Micro"}:
            return f"FabFilter {name}"
    return name


def _infer_vendor(display_name: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "", display_name.casefold())
    for token, vendor in VENDOR_HINTS:
        if token in normalized:
            return vendor
    return None


def _infer_kind(path: Path, display_name: str) -> PluginKind:
    parts = {part.casefold() for part in path.parts}
    if "generators" in parts:
        return "instrument"
    if "effects" in parts:
        return "effect"
    if display_name.casefold() in {"sylenth1", "serum", "serum2", "serum 2", "drumazon"}:
        return "instrument"
    if display_name.casefold() == "fl studio vsti":
        return "instrument"
    return "unknown"


def _system_plugin_roots() -> list[Path]:
    roots = [
        Path("/Library/Audio/Plug-Ins"),
        Path.home() / "Library/Audio/Plug-Ins",
    ]
    return [root for root in roots if root.exists()]


def _fl_user_roots() -> list[Path]:
    candidates = [
        Path.home() / "Documents/Image-Line/FL Studio",
        Path.home() / "Documents/Image-Line 2/FL Studio",
    ]
    return [root for root in candidates if root.exists()]


def _iter_paths(root: Path, suffixes: set[str], *, max_depth: int = 8) -> list[Path]:
    paths: list[Path] = []
    root_depth = len(root.parts)
    try:
        iterator = root.rglob("*")
        for path in iterator:
            if len(path.parts) - root_depth > max_depth:
                continue
            if path.suffix.casefold() in suffixes:
                paths.append(path)
    except OSError:
        return []
    return sorted(paths)


def _format_for_path(path: Path) -> PluginFormat:
    return PLUGIN_FORMAT_BY_SUFFIX.get(path.suffix.casefold(), "unknown")


def _status_for(
    *,
    bundle_paths: list[str],
    fl_database_entries: list[str],
    preset_paths: list[str],
) -> PluginInventoryStatus:
    if bundle_paths and fl_database_entries:
        return "installed"
    if bundle_paths:
        return "filesystem_only"
    if fl_database_entries:
        return "fl_database_only"
    if preset_paths:
        return "preset_only"
    return "unknown"


@lru_cache(maxsize=1)
def scan_preset_assets() -> tuple[PluginPresetAsset, ...]:
    """Scan local FL folders for preset, bank, and wrapper-state assets."""

    assets: list[PluginPresetAsset] = []
    for root in _fl_user_roots():
        for path in _iter_paths(root, PRESET_SUFFIXES, max_depth=10):
            display_name = _display_name_from_path(path)
            inferred = None
            normalized_path = path.as_posix().casefold()
            for token, plugin_id in (
                ("sylenth", "lennardigital.sylenth1"),
                ("serum", "xfer.serum2"),
                ("fabfilter", "fabfilter"),
                ("trash", "izotope.trash"),
            ):
                if token in normalized_path:
                    inferred = plugin_id
                    break
            extension = _format_for_path(path)
            kind = (
                "bank"
                if extension == "fxb"
                else ("wrapper_state" if extension == "fst" else "preset")
            )
            source_pack = None
            parts = list(path.parts)
            for marker in ("sample packs", "Plugin presets", "Plugin database"):
                if marker in parts:
                    index = parts.index(marker)
                    if index + 1 < len(parts):
                        source_pack = parts[index + 1]
                    break
            tags = []
            if "hardstyle" in normalized_path:
                tags.append("hardstyle")
            if inferred:
                tags.append(inferred)
            assets.append(
                PluginPresetAsset(
                    path=str(path),
                    extension=extension,
                    inferred_plugin=inferred or normalize_plugin_id(display_name),
                    kind=kind,  # type: ignore[arg-type]
                    bank_or_single="bank" if extension == "fxb" else "single",
                    tags=tags,
                    source_pack=source_pack,
                )
            )
    return tuple(assets)


@lru_cache(maxsize=1)
def scan_plugin_inventory() -> tuple[PluginInventoryItem, ...]:
    """Scan system plugin bundles and FL database entries into normalized inventory."""

    records: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "display_name": "",
            "vendor": None,
            "kind": "unknown",
            "formats": set(),
            "bundle_paths": set(),
            "fl_database_entries": set(),
            "favorite_entries": set(),
            "preset_paths": set(),
            "detected_by": set(),
        }
    )

    def add_path(path: Path, *, detected_by: str, is_fl_database: bool = False) -> None:
        display_name = _display_name_from_path(path)
        plugin_id = normalize_plugin_id(display_name)
        record = records[plugin_id]
        record["display_name"] = record["display_name"] or display_name
        record["vendor"] = record["vendor"] or _infer_vendor(display_name)
        record["kind"] = _infer_kind(path, display_name)
        cast_set(record["formats"]).add(_format_for_path(path))
        if is_fl_database:
            cast_set(record["fl_database_entries"]).add(str(path))
            if "Plugin database" in path.as_posix() and "Installed" not in path.as_posix():
                cast_set(record["favorite_entries"]).add(str(path))
        else:
            cast_set(record["bundle_paths"]).add(str(path))
        cast_set(record["detected_by"]).add(detected_by)

    for root in _system_plugin_roots():
        for path in _iter_paths(root, PLUGIN_BUNDLE_SUFFIXES, max_depth=4):
            add_path(path, detected_by="system_bundle")

    for root in _fl_user_roots():
        plugin_db = root / "Presets/Plugin database"
        if plugin_db.exists():
            for path in _iter_paths(plugin_db, {".fst"}, max_depth=8):
                add_path(path, detected_by="fl_plugin_database", is_fl_database=True)

    for asset in scan_preset_assets():
        plugin_id = asset.inferred_plugin or normalize_plugin_id(Path(asset.path).stem)
        record = records[plugin_id]
        if not record["display_name"]:
            record["display_name"] = Path(asset.path).stem
        record["vendor"] = record["vendor"] or _infer_vendor(str(record["display_name"]))
        cast_set(record["preset_paths"]).add(asset.path)
        cast_set(record["detected_by"]).add("preset_asset")
        cast_set(record["formats"]).add(asset.extension)

    items: list[PluginInventoryItem] = []
    for plugin_id, record in sorted(records.items()):
        bundle_paths = sorted(cast_set(record["bundle_paths"]))
        fl_database_entries = sorted(cast_set(record["fl_database_entries"]))
        preset_paths = sorted(cast_set(record["preset_paths"]))
        status = _status_for(
            bundle_paths=bundle_paths,
            fl_database_entries=fl_database_entries,
            preset_paths=preset_paths,
        )
        items.append(
            PluginInventoryItem(
                plugin_id=plugin_id,
                display_name=str(record["display_name"] or plugin_id),
                vendor=record["vendor"] if isinstance(record["vendor"], str) else None,
                kind=cast(PluginKind, record["kind"]),
                formats=cast(list[PluginFormat], sorted(cast_set(record["formats"]))),
                bundle_paths=bundle_paths,
                fl_database_entries=fl_database_entries,
                favorite_entries=sorted(cast_set(record["favorite_entries"])),
                preset_paths=preset_paths,
                detected_by=sorted(cast_set(record["detected_by"])),
                status=status,
            )
        )
    return tuple(items)


def cast_set(value: object) -> set[str]:
    """Return a mutable string set stored in an inventory accumulator."""

    if isinstance(value, set):
        return cast(set[str], value)
    return set()


def clear_inventory_caches() -> None:
    """Clear inventory scan caches; useful for tests and live rescan actions."""

    scan_plugin_inventory.cache_clear()
    scan_preset_assets.cache_clear()


def plugin_profile_overlay_dir() -> Path:
    """Return the machine-local plugin profile overlay directory."""

    configured = os.environ.get("FL_MCP_PLUGIN_PROFILE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".fl-mcp/plugin-profiles"
