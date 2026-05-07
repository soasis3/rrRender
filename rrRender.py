bl_info = {
    "name": "rrRender",
    "blender": (3, 0, 0),
    "category": "SF_Tools",
    "author": "Sean Hwang",
    "version": (1, 1),
    "location": "View3D > UI > SF_Render",
    "description": "This addon provides a simple way to reference and delete Rendering in Blender.",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
from bpy.types import Operator
import os
import re
import json
import threading
from operator import itemgetter
import math
from mathutils import Vector
import sys
import shutil
import importlib
from datetime import datetime
from copy import deepcopy

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_MODULE_SEARCH_PATHS = [
    THIS_DIR,
    r"C:\Users\hwang\Desktop\codex\rrRender",
]
for search_path in SHARED_MODULE_SEARCH_PATHS:
    if search_path and os.path.isdir(search_path) and search_path not in sys.path:
        sys.path.append(search_path)

try:
    from pipeline_shared import (
        build_legacy_rrrender_project_entry,
        get_project_entry as get_pipeline_project_entry,
        get_project_names as get_pipeline_project_names,
        load_pipeline_config,
        save_pipeline_config,
        sync_legacy_rrrender_paths_json,
    )
    PIPELINE_SHARED_AVAILABLE = True
except Exception:
    build_legacy_rrrender_project_entry = None
    get_pipeline_project_entry = None
    get_pipeline_project_names = None
    load_pipeline_config = None
    save_pipeline_config = None
    sync_legacy_rrrender_paths_json = None
    PIPELINE_SHARED_AVAILABLE = False

# -------------------------------------------------------------------
# ✅ [Global] 프로젝트별 설정 정의 (단일 소스)
# -------------------------------------------------------------------
PROJECT_SETTINGS_DIR = r"M:\RND\SFtools\2023\render\_json"
PROJECT_SETTINGS_FILENAME = "rrRender_project_paths.json"
PROJECT_SCHEMA_FILENAME = "rrRender_project_schema.json"
PROJECT_OVERRIDE_FILENAME = "rrRender_project_overrides.json"
HWANG_LOCAL_PROJECT_SETTINGS_SOURCE_DIR = r"C:\Users\hwang\Desktop\codex\rrRender\_json"
HWANG_RUNTIME_PROJECT_SETTINGS_DIR = r"C:\_json\rrRender_dev"

DEFAULT_PROJECT_CONFIG = {
    'THE_TRAP': {
        'drive': "T:/",
        'prefix': "ttm",
        'asset_base': "T:/assets",
        'scene_base': "T:/",
        'project_json_base': "T:/",
        'output_base': "T:/",
        'asset_ch_dir': "ch",
        'asset_bg_dir': "bg",
        'asset_prop_dir': "prop",
        'scene_root_dir': "scenes",
        'ren_dir': "ren",
        'cache_dir': "cache",
        'publish_dir': "pub",
    },
    'ARBOBION': {
        'drive': "A:/",
        'prefix': "ab",
        'asset_base': "A:/assets",
        'scene_base': "A:/",
        'project_json_base': "A:/",
        'output_base': "A:/",
        'asset_ch_dir': "ch",
        'asset_bg_dir': "bg",
        'asset_prop_dir': "prop",
        'scene_root_dir': "scenes",
        'ren_dir': "ren",
        'cache_dir': "cache",
        'publish_dir': "pub",
    },
    'DSC': {
        'drive': "S:/",
        'prefix': "DSC",
        'asset_base': "S:/assets",
        'scene_base': "S:/",
        'project_json_base': "S:/",
        'output_base': "S:/",
        'asset_ch_dir': "ch",
        'asset_bg_dir': "bg",
        'asset_prop_dir': "prop",
        'scene_root_dir': "scenes",
        'ren_dir': "ren",
        'cache_dir': "cache",
        'publish_dir': "pub",
    },
    'BTS': {
        'drive': "B:/",
        'prefix': "BTS",
        'asset_base': "B:/assets",
        'scene_base': "B:/",
        'project_json_base': "B:/",
        'output_base': "B:/",
        'asset_ch_dir': "ch",
        'asset_bg_dir': "bg",
        'asset_prop_dir': "prop",
        'scene_root_dir': "scenes",
        'ren_dir': "ren",
        'cache_dir': "cache",
        'publish_dir': "pub",
    },
    'FUZZ': {
        'drive': "Z:/",
        'prefix': "FUZZ",
        'asset_base': "Z:/assets",
        'scene_base': "Z:/",
        'project_json_base': "Z:/",
        'output_base': "Z:/",
        'asset_ch_dir': "ch",
        'asset_bg_dir': "bg",
        'asset_prop_dir': "prop",
        'scene_root_dir': "scenes",
        'ren_dir': "ren",
        'cache_dir': "cache",
        'publish_dir': "pub",
    },
    'COC': {
        'drive': "S:/PROJECT/COC/02_Production",
        'prefix': "COC",
        'asset_base': "S:/PROJECT/COC/02_Production",
        'scene_base': "S:/PROJECT/COC/02_Production",
        'project_json_base': "C:/_json",
        'output_base': "S:/PROJECT/COC/02_Production/output",
        'cache_base': "S:/PROJECT/COC/02_Production/Rendering",
        'asset_ch_dir': "CHSetup/controller",
        'asset_bg_dir': "bg",
        'asset_prop_dir': "prop",
        'scene_root_dir': "Animation/Detail",
        'ren_dir': "maya",
        'cache_dir': "cache",
        'publish_dir': "pub",
        'scene_identifier_mode': "filename",
        'geometry_root_hint': "Geometry/{asset_name}",
    },
}

PROJECT_CONFIG = deepcopy(DEFAULT_PROJECT_CONFIG)
PROJECT_SCHEMA = {"version": 2, "projects": {}}
PROJECT_OVERRIDES = {"version": 1, "projects": {}}
PROJECT_CONFIG_LOADED = False
PROJECT_SCHEMA_LOADED = False
PROJECT_OVERRIDES_LOADED = False
DEFAULT_SCENE_WORK_DIRS = ("ren", "cfx", "fx")
MAX_BROWSER_LEVELS = 5

PROJECT_NAME_ALIASES = {
    'THE_TRAP': 'THE_TRAP',
    'TTM': 'THE_TRAP',
    'ARBOBION': 'ARBOBION',
    'ARBO_BION': 'ARBOBION',
    'ARB': 'ARBOBION',
    'DSC': 'DSC',
    'BTS': 'BTS',
    'FUZZ': 'FUZZ',
    'COC': 'COC',
}


def normalize_path(path):
    return os.path.normcase(os.path.abspath(path or ""))


def normalize_project_name(project_name):
    raw_name = str(project_name or "").strip()
    if not raw_name:
        return ""
    return PROJECT_NAME_ALIASES.get(raw_name.upper(), raw_name.upper())


def get_project_enum_items(self=None, context=None):
    ensure_project_config_loaded()
    items = []
    for idx, project_name in enumerate(sorted(PROJECT_CONFIG.keys())):
        config = PROJECT_CONFIG.get(project_name, {})
        drive = str(config.get("drive", "") or "")
        label = project_name
        description = f"Project at {drive}" if drive else f"Project {project_name}"
        items.append((project_name, label, description, idx))
    return items or [('BTS', "BTS", "Fallback project", 0)]

PROJECT_CONFIG_FIELDS = (
    "drive",
    "prefix",
    "asset_base",
    "scene_base",
    "project_json_base",
    "output_base",
    "asset_ch_dir",
    "asset_bg_dir",
    "asset_prop_dir",
    "scene_root_dir",
    "ren_dir",
    "cache_dir",
    "cache_base",
    "publish_dir",
    "scene_example_file",
    "publish_example_file",
    "scene_structure_mode",
    "scene_identifier_mode",
    "scene_version_digits",
    "publish_version_digits",
    "publish_suffix",
    "geometry_root_hint",
)


def is_hwang_dev_environment():
    return os.environ.get("USERNAME", "").strip().lower() == "hwang"


def get_local_project_settings_source_dir():
    return HWANG_LOCAL_PROJECT_SETTINGS_SOURCE_DIR


def get_runtime_project_settings_dir():
    return HWANG_RUNTIME_PROJECT_SETTINGS_DIR


def get_active_project_settings_dir():
    if is_hwang_dev_environment():
        runtime_dir = get_runtime_project_settings_dir()
        if os.path.isdir(runtime_dir):
            return runtime_dir

        local_source_dir = get_local_project_settings_source_dir()
        if os.path.isdir(local_source_dir):
            return local_source_dir

    return PROJECT_SETTINGS_DIR


def build_default_project_schema_entry(project_name, config=None):
    normalized_name = normalize_project_name(project_name)
    config = normalize_project_config_entry(normalized_name, config or DEFAULT_PROJECT_CONFIG.get(normalized_name, {}))
    scene_root_path = os.path.join(
        str(config.get("scene_base", "") or ""),
        str(config.get("scene_root_dir", "scenes") or "scenes"),
    ).replace("\\", "/")
    output_root = str(config.get("output_base", "") or "")
    project_json_root = str(config.get("project_json_base", "") or "")
    prefix = str(config.get("prefix", "") or "")

    return {
        "project_id": normalized_name,
        "project_prefix": prefix,
        "paths": {
            "project_root": str(config.get("drive", "") or ""),
            "project_json_root": project_json_root,
            "output_root": output_root,
            "render_preset_json": os.path.join(project_json_root, "_json", "renderPreset.json").replace("\\", "/"),
            "render_setting_json": os.path.join(project_json_root, "_json", "renderSetting.json").replace("\\", "/"),
        },
        "scene_browser": {
            "levels": [
                {
                    "id": "scene",
                    "label": "Scene",
                    "root_path": scene_root_path,
                    "path_mode": "children",
                },
                {
                    "id": "cut",
                    "label": "Cut",
                    "parent_level": "scene",
                    "path_mode": "children",
                },
                {
                    "id": "work",
                    "label": "Work",
                    "parent_level": "cut",
                    "fixed_options": list(get_scene_work_dir_names_from_config(config)),
                    "default": str(config.get("ren_dir", "ren") or "ren"),
                },
            ],
            "file_level_id": "work",
            "file_extensions": [".blend"],
        },
        "scene_structure": {
            "identifier_source": "folder_depth",
            "scene_level_id": "scene",
            "cut_level_id": "cut",
            "work_level_id": "work",
            "cache_path_mode": "relative_to_work",
            "cache_relative_path": str(config.get("cache_dir", "cache") or "cache"),
        },
        "assets": {
            "categories": [
                {
                    "id": "ch",
                    "label": "Character",
                    "root_path": os.path.join(str(config.get("asset_base", "") or ""), str(config.get("asset_ch_dir", "ch") or "ch")).replace("\\", "/"),
                    "publish_file_mode": "asset_mod_blend",
                    "publish_file_template": "{root}/{asset_name}/mod/{asset_name}.blend",
                    "asset_id_source": "folder_name",
                    "geometry_root_hint": str(config.get("geometry_root_hint", "geo") or "geo"),
                },
                {
                    "id": "bg",
                    "label": "Background",
                    "root_path": os.path.join(str(config.get("asset_base", "") or ""), str(config.get("asset_bg_dir", "bg") or "bg")).replace("\\", "/"),
                    "publish_file_mode": "asset_mod_blend",
                    "publish_file_template": "{root}/{asset_name}/mod/{asset_name}.blend",
                    "asset_id_source": "folder_name",
                    "geometry_root_hint": str(config.get("geometry_root_hint", "geo") or "geo"),
                },
                {
                    "id": "prop",
                    "label": "Prop",
                    "root_path": os.path.join(str(config.get("asset_base", "") or ""), str(config.get("asset_prop_dir", "prop") or "prop")).replace("\\", "/"),
                    "publish_file_mode": "asset_mod_blend",
                    "publish_file_template": "{root}/{asset_name}/mod/{asset_name}.blend",
                    "asset_id_source": "folder_name",
                    "geometry_root_hint": str(config.get("geometry_root_hint", "geo") or "geo"),
                },
            ],
            "asset_id_rules": {
                "normalize_case": "lower",
                "replace_spaces_with": "_",
                "strip_tokens": ["rig", "mod", "pub", "fin", "final"],
                "strip_numeric_suffix": True,
            },
        },
        "cache": {
            "root_mode": "relative_to_work",
            "root_template": "{work_path}/" + str(config.get("cache_dir", "cache") or "cache"),
            "file_template": "{project_prefix}_{scene}_{cut}_{category}_{asset_id}.usd",
            "match_mode": "by_asset_id_and_category",
            "extensions": [".usd"],
        },
        "output": {
            "root_template": os.path.join(output_root, "output", str(config.get("ren_dir", "ren") or "ren"), "{scene}", "{scene}_{cut}").replace("\\", "/"),
            "version_folder_mode": "v###",
            "default_version_digits": 3,
            "file_slot_prefix_template": "{scene}_{cut}_{layer}_",
        },
        "browser_sync": {
            "filepath_parse_mode": "folder_first_then_filename",
            "filename_patterns": [
                "{project_prefix}_{scene}_{cut}_{work}_v{version}",
                "{project_prefix}_{scene}_{cut}_{work}_v{version}_{suffix}",
            ],
        },
    }


def build_default_project_override_entry():
    return {
        "asset_registry": [],
        "cache_overrides": [],
    }


def get_project_settings_store_path():
    return os.path.join(get_active_project_settings_dir(), PROJECT_SETTINGS_FILENAME)


def get_project_schema_store_path():
    return os.path.join(get_active_project_settings_dir(), PROJECT_SCHEMA_FILENAME)


def get_project_override_store_path():
    return os.path.join(get_active_project_settings_dir(), PROJECT_OVERRIDE_FILENAME)


def normalize_project_config_entry(project_name, raw_config=None):
    base_config = deepcopy(DEFAULT_PROJECT_CONFIG.get(project_name, DEFAULT_PROJECT_CONFIG['BTS']))
    if isinstance(raw_config, dict):
        for key in PROJECT_CONFIG_FIELDS:
            value = raw_config.get(key)
            if value not in (None, ""):
                base_config[key] = str(value)
    return base_config


def get_scene_work_dir_names_from_config(config):
    configured_ren = str((config or {}).get("ren_dir", "ren") or "ren")
    work_dirs = [configured_ren]
    for name in DEFAULT_SCENE_WORK_DIRS:
        if name not in work_dirs:
            work_dirs.append(name)
    return work_dirs


def ensure_project_schema_loaded(force=False):
    global PROJECT_SCHEMA, PROJECT_SCHEMA_LOADED
    schema_path = get_project_schema_store_path()
    if PROJECT_SCHEMA_LOADED and not force and os.path.exists(schema_path):
        return PROJECT_SCHEMA

    schema_projects = {}
    try:
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                schema_projects = payload.get("projects", {}) if isinstance(payload.get("projects", {}), dict) else {}
    except Exception as e:
        print(f"[ProjectSchema][WARN] load failed: {e}")

    for project_name in sorted(ensure_project_config_loaded().keys()):
        normalized_name = normalize_project_name(project_name)
        if normalized_name not in schema_projects:
            schema_projects[normalized_name] = build_default_project_schema_entry(normalized_name, PROJECT_CONFIG.get(normalized_name, {}))

    PROJECT_SCHEMA = {
        "version": 2,
        "projects": schema_projects,
    }
    PROJECT_SCHEMA_LOADED = True
    if not os.path.exists(schema_path):
        save_project_schema_store()
    return PROJECT_SCHEMA


def ensure_project_overrides_loaded(force=False):
    global PROJECT_OVERRIDES, PROJECT_OVERRIDES_LOADED
    override_path = get_project_override_store_path()
    if PROJECT_OVERRIDES_LOADED and not force and os.path.exists(override_path):
        return PROJECT_OVERRIDES

    override_projects = {}
    try:
        if os.path.exists(override_path):
            with open(override_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                override_projects = payload.get("projects", {}) if isinstance(payload.get("projects", {}), dict) else {}
    except Exception as e:
        print(f"[ProjectOverrides][WARN] load failed: {e}")

    for project_name in sorted(ensure_project_config_loaded().keys()):
        normalized_name = normalize_project_name(project_name)
        override_projects.setdefault(normalized_name, build_default_project_override_entry())

    PROJECT_OVERRIDES = {
        "version": 1,
        "projects": override_projects,
    }
    PROJECT_OVERRIDES_LOADED = True
    if not os.path.exists(override_path):
        save_project_override_store()
    return PROJECT_OVERRIDES


def save_project_schema_store():
    schema_path = get_project_schema_store_path()
    os.makedirs(os.path.dirname(schema_path), exist_ok=True)
    with open(schema_path, "w", encoding="utf-8") as handle:
        json.dump(PROJECT_SCHEMA, handle, ensure_ascii=False, indent=2)


def save_project_override_store():
    override_path = get_project_override_store_path()
    os.makedirs(os.path.dirname(override_path), exist_ok=True)
    with open(override_path, "w", encoding="utf-8") as handle:
        json.dump(PROJECT_OVERRIDES, handle, ensure_ascii=False, indent=2)


def get_project_schema_entry(project_name=None):
    ensure_project_schema_loaded()
    normalized = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    return deepcopy(PROJECT_SCHEMA.get("projects", {}).get(normalized, build_default_project_schema_entry(normalized, get_config_by_project_name(normalized))))


def set_project_schema_entry(project_name, schema_entry):
    ensure_project_schema_loaded()
    normalized = normalize_project_name(project_name)
    PROJECT_SCHEMA.setdefault("projects", {})[normalized] = deepcopy(schema_entry or build_default_project_schema_entry(normalized, get_config_by_project_name(normalized)))


def get_project_override_entry(project_name=None):
    ensure_project_overrides_loaded()
    normalized = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    return deepcopy(PROJECT_OVERRIDES.get("projects", {}).get(normalized, build_default_project_override_entry()))


def get_schema_scene_levels(project_name=None):
    schema = get_project_schema_entry(project_name)
    scene_browser = schema.get("scene_browser", {}) if isinstance(schema, dict) else {}
    levels = scene_browser.get("levels", []) if isinstance(scene_browser, dict) else []
    return levels if isinstance(levels, list) else []


def get_schema_asset_categories(project_name=None):
    schema = get_project_schema_entry(project_name)
    assets = schema.get("assets", {}) if isinstance(schema, dict) else {}
    categories = assets.get("categories", []) if isinstance(assets, dict) else []
    return categories if isinstance(categories, list) else []


def get_schema_scene_root_path(project_name=None):
    levels = get_schema_scene_levels(project_name)
    if levels:
        root_path = normalize_directory_choice(levels[0].get("root_path", ""))
        if root_path:
            return root_path
    return ""


def get_schema_work_level(project_name=None):
    levels = get_schema_scene_levels(project_name)
    for level in levels:
        fixed_options = level.get("fixed_options")
        if isinstance(fixed_options, list) and fixed_options:
            return level
    return {}


def get_schema_work_dir_names(project_name=None):
    work_level = get_schema_work_level(project_name)
    fixed_options = work_level.get("fixed_options", [])
    if isinstance(fixed_options, list) and fixed_options:
        return [str(option) for option in fixed_options if str(option or "").strip() or str(option) == "."]
    return []


def get_project_browser_file_extensions(project_name=None):
    schema = get_project_schema_entry(project_name)
    scene_browser = schema.get("scene_browser", {}) if isinstance(schema, dict) else {}
    extensions = scene_browser.get("file_extensions", []) if isinstance(scene_browser, dict) else []
    cleaned = []
    for ext in extensions if isinstance(extensions, list) else []:
        text = str(ext or "").strip().lower()
        if not text:
            continue
        if not text.startswith("."):
            text = "." + text
        cleaned.append(text)
    return cleaned or [".blend"]


def get_schema_non_work_levels(project_name=None):
    levels = get_schema_scene_levels(project_name)
    work_level = get_schema_work_level(project_name)
    work_level_id = str(work_level.get("id", "") or "")
    results = []
    for level in levels:
        level_id = str(level.get("id", "") or "")
        if work_level_id and level_id == work_level_id:
            continue
        results.append(level)
    return results


def get_schema_primary_level(project_name=None):
    levels = get_schema_non_work_levels(project_name)
    return levels[0] if levels else {}


def get_schema_secondary_level(project_name=None):
    levels = get_schema_non_work_levels(project_name)
    return levels[1] if len(levels) >= 2 else {}


def get_browser_scene_label(project_name=None):
    level = get_schema_primary_level(project_name)
    return str(level.get("label", "Scene") or "Scene")


def get_browser_cut_label(project_name=None):
    level = get_schema_secondary_level(project_name)
    return str(level.get("label", "Cut") or "Cut")


def get_browser_non_work_levels(project_name=None):
    return get_schema_non_work_levels(project_name)[:MAX_BROWSER_LEVELS]


def get_browser_level_definition(level_index, project_name=None):
    levels = get_browser_non_work_levels(project_name)
    if 1 <= level_index <= len(levels):
        return levels[level_index - 1]
    return {}


def get_browser_level_label(level_index, project_name=None):
    default_labels = {
        1: "Scene",
        2: "Cut",
        3: "Level 3",
        4: "Level 4",
        5: "Level 5",
    }
    level = get_browser_level_definition(level_index, project_name)
    return str(level.get("label", default_labels.get(level_index, f"Level {level_index}")) or default_labels.get(level_index, f"Level {level_index}"))


def get_browser_level_attr_name(level_index):
    if level_index == 1:
        return "scene_number"
    if level_index == 2:
        return "cut_number"
    return f"browser_level_{level_index}"


def get_browser_level_value(context=None, level_index=1):
    context = bpy.context if context is None else context
    my_tool = getattr(getattr(context, "scene", None), "my_tool", None)
    if not my_tool:
        return ""
    return str(getattr(my_tool, get_browser_level_attr_name(level_index), "") or "")


def get_safe_enum_identifier(items, preferred_value="", fallback_identifier="NONE"):
    valid_values = [str(item[0]) for item in (items or []) if item]
    preferred_value = str(preferred_value or "")
    if preferred_value and preferred_value in valid_values:
        return preferred_value
    if valid_values:
        return valid_values[0]
    return fallback_identifier


def safe_set_enum_property(target, attr_name, items, preferred_value="", fallback_identifier="NONE"):
    if target is None or not hasattr(target, attr_name):
        return ""
    value = get_safe_enum_identifier(items, preferred_value=preferred_value, fallback_identifier=fallback_identifier)
    try:
        setattr(target, attr_name, value)
        return value
    except Exception:
        return ""


def set_browser_level_value(context, level_index, value):
    my_tool = getattr(getattr(context, "scene", None), "my_tool", None)
    if not my_tool:
        return
    attr_name = get_browser_level_attr_name(level_index)
    level_items = get_browser_level_items(level_index, context)
    safe_set_enum_property(my_tool, attr_name, level_items, preferred_value=value, fallback_identifier=f"NO_LEVEL{level_index}")


def get_browser_level_values(context=None, project_name=None):
    values = []
    levels = get_browser_non_work_levels(project_name)
    for index in range(1, len(levels) + 1):
        values.append(get_browser_level_value(context, index))
    return values


def build_browser_level_base_path(level_index, context=None, project_name=None):
    scene_root = get_scene_root_path(project_name)
    if level_index <= 1:
        return scene_root

    values = get_browser_level_values(context, project_name)
    parts = [value for value in values[:max(0, level_index - 1)] if str(value or "").strip()]
    return os.path.join(scene_root, *parts) if parts else scene_root


def build_browser_base_path(scene_number="", cut_number="", project_name=None):
    scene_root = get_scene_root_path(project_name)
    parts = []
    levels = get_browser_non_work_levels(project_name)
    for index in range(1, len(levels) + 1):
        if index == 1:
            value = str(scene_number or "").strip()
        elif index == 2:
            value = str(cut_number or "").strip()
        else:
            value = str(get_browser_level_value(bpy.context, index) or "").strip()
        if value:
            parts.append(value)
    return os.path.join(scene_root, *parts) if parts else scene_root


def list_browser_child_dirs(base_path):
    items = []
    if not os.path.exists(base_path):
        return items
    for name in sorted(os.listdir(base_path)):
        full_path = os.path.join(base_path, name)
        if os.path.isdir(full_path) and is_valid_folder(name):
            items.append((name, name, ""))
    return items


def get_browser_level_items(level_index, context=None, project_name=None):
    level = get_browser_level_definition(level_index, project_name)
    if not level:
        return []

    base_path = build_browser_level_base_path(level_index, context, project_name)
    return list_browser_child_dirs(base_path)


def build_schema_non_work_levels(scene_root_path, level_count, labels):
    levels = []
    safe_count = max(1, min(MAX_BROWSER_LEVELS, int(level_count or 1)))
    for index in range(1, safe_count + 1):
        label = str((labels or {}).get(index, "") or get_browser_level_label(index)).strip() or f"Level {index}"
        if index == 1:
            levels.append({
                "id": "scene",
                "label": label,
                "root_path": normalize_directory_choice(scene_root_path),
                "path_mode": "children",
            })
        else:
            levels.append({
                "id": "cut" if index == 2 else f"level_{index}",
                "label": label,
                "parent_level": levels[index - 2]["id"],
                "path_mode": "children",
            })
    return levels


def upsert_schema_from_project_config(project_name, config=None):
    normalized_name = normalize_project_name(project_name)
    config = normalize_project_config_entry(normalized_name, config or get_config_by_project_name(normalized_name))
    set_project_schema_entry(normalized_name, build_default_project_schema_entry(normalized_name, config))

    ensure_project_overrides_loaded()
    PROJECT_OVERRIDES.setdefault("projects", {})
    PROJECT_OVERRIDES["projects"].setdefault(normalized_name, build_default_project_override_entry())


def ensure_project_config_loaded(force=False):
    global PROJECT_CONFIG, PROJECT_CONFIG_LOADED
    settings_path = get_project_settings_store_path()

    if PROJECT_CONFIG_LOADED and not force and os.path.exists(settings_path):
        return PROJECT_CONFIG

    PROJECT_CONFIG = deepcopy(DEFAULT_PROJECT_CONFIG)

    if PIPELINE_SHARED_AVAILABLE and load_pipeline_config and build_legacy_rrrender_project_entry:
        try:
            payload = load_pipeline_config()
            for project_name in get_pipeline_project_names(payload):
                normalized_name = normalize_project_name(project_name)
                raw_config = build_legacy_rrrender_project_entry(project_name, payload)
                if normalized_name and raw_config:
                    PROJECT_CONFIG[normalized_name] = normalize_project_config_entry(normalized_name, raw_config)
            PROJECT_CONFIG_LOADED = True
            return PROJECT_CONFIG
        except Exception as e:
            print(f"[ProjectConfig][WARN] shared pipeline load failed, fallback to legacy JSON: {e}")

    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                projects = payload.get("projects", payload)
                if isinstance(projects, dict):
                    for project_name, raw_config in projects.items():
                        normalized_name = normalize_project_name(project_name)
                        if normalized_name:
                            PROJECT_CONFIG[normalized_name] = normalize_project_config_entry(normalized_name, raw_config)
        else:
            save_project_config_store()
    except Exception as e:
        print(f"[ProjectConfig][WARN] load failed: {e}")

    PROJECT_CONFIG_LOADED = True
    return PROJECT_CONFIG


def save_project_config_store():
    settings_path = get_project_settings_store_path()
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    payload = {
        "version": 1,
        "projects": {name: normalize_project_config_entry(name, PROJECT_CONFIG.get(name, {})) for name in sorted(PROJECT_CONFIG.keys())}
    }
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def get_project_config_value(project_name, key, default=""):
    ensure_project_config_loaded()
    config = get_config_by_project_name(project_name)
    return str(config.get(key, default) or default)


def get_project_drive(project_name=None):
    return get_project_config_value(project_name, "drive", DEFAULT_PROJECT_CONFIG['BTS']['drive'])


def get_project_scene_base(project_name=None):
    scene_root_path = get_schema_scene_root_path(project_name)
    if scene_root_path:
        drive, parts = split_normalized_path(scene_root_path)
        if len(parts) >= 1:
            return join_normalized_path(drive, parts[:-1]) if parts[:-1] else (drive or scene_root_path)
    return get_project_config_value(project_name, "scene_base", get_project_drive(project_name))


def get_project_asset_base(project_name=None):
    categories = get_schema_asset_categories(project_name)
    if categories:
        root_path = normalize_directory_choice(categories[0].get("root_path", ""))
        if root_path:
            drive, parts = split_normalized_path(root_path)
            if len(parts) >= 2:
                return join_normalized_path(drive, parts[:-1])
    return get_project_config_value(project_name, "asset_base", os.path.join(get_project_drive(project_name), "assets"))


def get_project_json_base(project_name=None):
    schema = get_project_schema_entry(project_name)
    paths = schema.get("paths", {}) if isinstance(schema, dict) else {}
    project_json_root = normalize_directory_choice(paths.get("project_json_root", ""))
    if project_json_root:
        return project_json_root
    return get_project_config_value(project_name, "project_json_base", get_project_drive(project_name))


def get_project_output_base(project_name=None):
    schema = get_project_schema_entry(project_name)
    paths = schema.get("paths", {}) if isinstance(schema, dict) else {}
    output_root = normalize_directory_choice(paths.get("output_root", ""))
    if output_root:
        return output_root
    return get_project_config_value(project_name, "output_base", get_project_drive(project_name))


def get_project_scene_root_dir(project_name=None):
    scene_root_path = get_schema_scene_root_path(project_name)
    if scene_root_path:
        _drive, parts = split_normalized_path(scene_root_path)
        if parts:
            return parts[-1]
    return get_project_config_value(project_name, "scene_root_dir", "scenes")


def get_project_ren_dir_name(project_name=None):
    work_dirs = get_schema_work_dir_names(project_name)
    if work_dirs:
        return work_dirs[0]
    return get_project_config_value(project_name, "ren_dir", "ren")


def get_project_cache_dir_name(project_name=None):
    return get_project_config_value(project_name, "cache_dir", "cache")


def get_project_publish_dir_name(project_name=None):
    return get_project_config_value(project_name, "publish_dir", "pub")


def get_asset_category_dir_name(category_name, project_name=None):
    category_id = str(category_name or "").lower()
    for category in get_schema_asset_categories(project_name):
        if str(category.get("id", "")).lower() == category_id:
            root_path = normalize_directory_choice(category.get("root_path", ""))
            if root_path:
                _drive, parts = split_normalized_path(root_path)
                if parts:
                    return "/".join(parts[-1:])
    mapping = {
        "ch": "asset_ch_dir",
        "bg": "asset_bg_dir",
        "prop": "asset_prop_dir",
    }
    category_key = str(category_name or "").lower()
    field_name = mapping.get(category_key)
    if not field_name:
        return str(category_name)
    return get_project_config_value(project_name, field_name, category_key)


def get_scene_root_path(project_name=None):
    scene_root_path = get_schema_scene_root_path(project_name)
    if scene_root_path:
        return scene_root_path
    return os.path.join(get_project_scene_base(project_name), get_project_scene_root_dir(project_name))


def get_scene_path(scene_number, project_name=None):
    return os.path.join(get_scene_root_path(project_name), str(scene_number))


def get_cut_path(scene_number, cut_number, project_name=None):
    return build_browser_base_path(scene_number, cut_number, project_name)


def get_ren_path(scene_number, cut_number, project_name=None):
    return os.path.join(build_browser_base_path(scene_number, cut_number, project_name), get_project_ren_dir_name(project_name))


def get_cache_path(scene_number, cut_number, project_name=None):
    return os.path.join(get_ren_path(scene_number, cut_number, project_name), get_project_cache_dir_name(project_name))


def get_scene_identifier_mode(project_name=None):
    config = get_config_by_project_name(project_name)
    return str(config.get("scene_identifier_mode", "") or "").strip().lower()


def resolve_scene_source_filepath(scene_number, cut_number, context=None, project_name=None):
    context = bpy.context if context is None else context
    current_filepath = str((_pending_browser_focus_filepath or bpy.data.filepath) or "")
    if current_filepath:
        return current_filepath
    my_tool = getattr(getattr(context, "scene", None), "my_tool", None)
    if not my_tool:
        return ""
    blend_file_value = str(getattr(my_tool, "blend_file", "") or "")
    if not blend_file_value or blend_file_value.startswith("NO_"):
        return ""
    return resolve_selected_blend_filepath(scene_number, cut_number, blend_file_value, project_name) or ""


def resolve_cache_context(scene_number, cut_number, context=None, project_name=None):
    project_name = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    cache_dir = get_cache_path(scene_number, cut_number, project_name)
    scene_token = str(scene_number or "")
    cut_token = str(cut_number or "")
    source_file = resolve_scene_source_filepath(scene_number, cut_number, context, project_name)

    if source_file:
        scene_info = infer_scene_filename_info(source_file)
        source_dir = os.path.dirname(source_file)
        if source_dir:
            # Always prefer the currently opened scene's sibling cache folder when available.
            # This keeps legacy ren/cache projects and COC's cut/cache layout both aligned
            # with the actual file the user is working in.
            cache_dir = os.path.join(source_dir, get_project_cache_dir_name(project_name))

            if get_scene_identifier_mode(project_name) == "filename":
                config = get_config_by_project_name(project_name)
                cache_base = normalize_directory_choice(config.get("cache_base", ""))
                if cache_base and not os.path.exists(cache_dir):
                    episode_name = os.path.basename(os.path.dirname(source_dir))
                    shot_name = "_".join([token for token in (scene_info.get("scene_token", ""), scene_info.get("cut_token", "")) if str(token).strip()])
                    if episode_name and shot_name:
                        cache_dir = os.path.join(cache_base, episode_name, shot_name, get_project_cache_dir_name(project_name))
        scene_token = str(scene_info.get("scene_token", scene_token) or scene_token)
        cut_token = str(scene_info.get("cut_token", cut_token) or cut_token)

    return {
        "cache_dir": cache_dir,
        "scene_token": scene_token,
        "cut_token": cut_token,
        "source_file": source_file,
    }


def safe_usd_import(**usd_args):
    args = dict(usd_args)
    optional_keys = [
        "import_subdiv",
        "import_meshes",
        "import_materials",
        "import_usd_preview",
        "import_all_materials",
        "read_mesh_uvs",
        "read_mesh_colors",
        "apply_unit_conversion_scale",
        "set_frame_range",
        "relative_path",
        "scale",
    ]

    while True:
        try:
            return bpy.ops.wm.usd_import(**args)
        except TypeError as e:
            message = str(e)
            removed = False
            for key in list(optional_keys):
                if f'keyword "{key}" unrecognized' in message and key in args:
                    args.pop(key, None)
                    removed = True
                    print(f"[USD Import] Removed unsupported arg: {key}")
                    break
            if not removed:
                raise


def get_scene_work_dir_names(project_name=None):
    schema_work_dirs = get_schema_work_dir_names(project_name)
    if schema_work_dirs:
        return schema_work_dirs
    return get_scene_work_dir_names_from_config(get_config_by_project_name(project_name))


def get_scene_work_paths(scene_number, cut_number, project_name=None):
    base_path = build_browser_base_path(scene_number, cut_number, project_name)
    paths = []
    for work_dir in get_scene_work_dir_names(project_name):
        work_dir_text = str(work_dir or "")
        if work_dir_text in (".", "./", "\\"):
            paths.append((work_dir_text, base_path))
        else:
            paths.append((work_dir_text, os.path.join(base_path, work_dir_text)))
    return paths


def build_blend_file_identifier(work_dir_name, filename):
    return f"{work_dir_name}|{filename}"


def parse_blend_file_identifier(value):
    text = str(value or "")
    if "|" in text:
        work_dir_name, filename = text.split("|", 1)
        return work_dir_name, filename
    return "", text


def resolve_selected_blend_filepath(scene_number, cut_number, blend_file_value, project_name=None):
    work_dir_name, filename = parse_blend_file_identifier(blend_file_value)
    if work_dir_name and filename:
        base_path = build_browser_base_path(scene_number, cut_number, project_name)
        if str(work_dir_name or "") in (".", "./", "\\"):
            candidate = os.path.join(base_path, filename)
        else:
            candidate = os.path.join(base_path, work_dir_name, filename)
        if os.path.exists(candidate):
            return candidate
    return None


def normalize_directory_choice(directory):
    normalized = str(directory or "").replace("\\", "/").strip()
    if len(normalized) == 2 and normalized[1] == ":":
        normalized += "/"
    return normalized


def split_normalized_path(path):
    normalized = normalize_directory_choice(path)
    if not normalized:
        return "", []

    match = re.match(r"^([A-Za-z]:)(?:/(.*))?$", normalized)
    if match:
        drive = match.group(1) + "/"
        remainder = match.group(2) or ""
        parts = [part for part in remainder.split("/") if part]
        return drive, parts

    return "", [part for part in normalized.split("/") if part]


def join_normalized_path(drive, parts):
    clean_parts = [str(part).strip("/\\") for part in (parts or []) if str(part).strip("/\\")]
    if drive:
        return drive.rstrip("/") + ("/" + "/".join(clean_parts) if clean_parts else "/")
    return "/".join(clean_parts)


def find_marker_index(parts, markers):
    marker_lookup = {str(marker).lower() for marker in markers}
    for index, part in enumerate(parts):
        if str(part).lower() in marker_lookup:
            return index
    return None


def guess_asset_category_from_parts(parts):
    joined = "/".join(str(part).lower() for part in parts)
    if any(token in joined for token in ("bg", "background", "env", "environment")):
        return "bg"
    if any(token in joined for token in ("prop", "props", "prp")):
        return "prop"
    return "ch"


def infer_scene_filename_info(scene_file_path):
    filename = os.path.basename(scene_file_path)
    stem = os.path.splitext(filename)[0]
    info = {
        "prefix": "",
        "scene_token": "",
        "cut_token": "",
        "version_digits": 0,
        "identifier_mode": "unknown",
    }

    version_match = re.search(r"(?i)(?:^|[_\-])v(\d+)(?:$|[_\-])", stem)
    if version_match:
        info["version_digits"] = len(version_match.group(1))

    legacy_match = re.match(r"(?i)^([A-Za-z]+)_([0-9]{4})_([0-9]{4})_([A-Za-z0-9]+)_v(\d+)", stem)
    if legacy_match:
        info["prefix"] = legacy_match.group(1)
        info["scene_token"] = legacy_match.group(2)
        info["cut_token"] = legacy_match.group(3)
        info["version_digits"] = len(legacy_match.group(5))
        info["identifier_mode"] = "prefix_scene_cut_work_version"
        return info

    scene_cut_match = re.match(r"(?i)^([A-Za-z]*\d+)[_\-]([A-Za-z]*\d+)(?:[_\-]v(\d+))?", stem)
    if scene_cut_match:
        info["scene_token"] = scene_cut_match.group(1)
        info["cut_token"] = scene_cut_match.group(2)
        if scene_cut_match.group(3):
            info["version_digits"] = len(scene_cut_match.group(3))
        info["identifier_mode"] = "scene_cut_version"
        return info

    numeric_match = re.search(r"(?<!\d)(\d{4})[_\-](\d{4})(?!\d)", stem)
    if numeric_match:
        info["scene_token"] = numeric_match.group(1)
        info["cut_token"] = numeric_match.group(2)
        info["identifier_mode"] = "scene_cut_numeric"

    return info


def infer_scene_path_config(scene_file_path):
    directory = os.path.dirname(scene_file_path)
    drive, parts = split_normalized_path(directory)
    scene_info = infer_scene_filename_info(scene_file_path)
    work_dir_name = parts[-1] if parts else "ren"
    pre_work_parts = parts[:-1]
    scene_token = str(scene_info.get("scene_token", "") or "")
    cut_token = str(scene_info.get("cut_token", "") or "")

    structure_mode = "flat_files"
    scene_root_parts = []
    scene_base_parts = []
    scene_markers = ("scenes", "scene", "shots", "shot", "seq", "sequence", "animation", "ani", "detail")

    has_scene_cut_folders = (
        len(parts) >= 3
        and scene_token
        and cut_token
        and str(parts[-3]).lower() == scene_token.lower()
        and str(parts[-2]).lower() == cut_token.lower()
    )

    if has_scene_cut_folders:
        structure_mode = "folder_scene_cut"
        marker_index = find_marker_index(parts[:-3], scene_markers)
        if marker_index is not None:
            scene_base_parts = parts[:marker_index]
            scene_root_parts = parts[marker_index:-3]
        else:
            scene_base_parts = parts[:-4] if len(parts) >= 4 else []
            scene_root_parts = parts[-4:-3] if len(parts) >= 4 else ["scenes"]
    else:
        marker_index = find_marker_index(pre_work_parts, scene_markers)
        if marker_index is not None:
            scene_base_parts = pre_work_parts[:marker_index]
            scene_root_parts = pre_work_parts[marker_index:]
        else:
            scene_base_parts = pre_work_parts[:-2] if len(pre_work_parts) >= 2 else []
            scene_root_parts = pre_work_parts[-2:] if len(pre_work_parts) >= 2 else (pre_work_parts or ["scenes"])

    scene_base = join_normalized_path(drive, scene_base_parts) if (drive or scene_base_parts) else ""
    scene_root_dir = "/".join(scene_root_parts) if scene_root_parts else "scenes"

    return {
        "scene_base": scene_base,
        "scene_root_dir": scene_root_dir,
        "ren_dir": work_dir_name,
        "scene_structure_mode": structure_mode,
        "scene_identifier_mode": scene_info.get("identifier_mode", "unknown"),
        "scene_version_digits": scene_info.get("version_digits", 0),
        "inferred_prefix": scene_info.get("prefix", ""),
    }


def infer_publish_path_config(publish_file_path):
    directory = os.path.dirname(publish_file_path)
    filename = os.path.basename(publish_file_path)
    file_stem = os.path.splitext(filename)[0]
    drive, parts = split_normalized_path(directory)

    container_names = {"mod", "pub", "rig", "blend", "model", "maya"}
    asset_folder_index = len(parts) - 1
    if parts and str(parts[-1]).lower() in container_names and len(parts) >= 2:
        asset_folder_index = len(parts) - 2

    asset_name = parts[asset_folder_index] if parts else ""
    asset_base_parts = []
    category_parts = []

    assets_index = find_marker_index(parts[:asset_folder_index], ("assets", "asset"))
    if assets_index is not None:
        asset_base_parts = parts[:assets_index + 1]
        category_parts = parts[assets_index + 1:asset_folder_index]
    else:
        asset_marker_index = find_marker_index(
            parts[:asset_folder_index],
            ("chsetup", "ch", "char", "character", "characters", "bg", "background", "prop", "props", "controller"),
        )
        if asset_marker_index is not None:
            asset_base_parts = parts[:asset_marker_index]
            category_parts = parts[asset_marker_index:asset_folder_index]
        else:
            asset_base_parts = parts[:asset_folder_index - 1] if asset_folder_index >= 2 else parts[:asset_folder_index]
            category_parts = parts[asset_folder_index - 1:asset_folder_index] if asset_folder_index >= 1 else []

    publish_suffix = ""
    if asset_name and file_stem.lower().startswith(asset_name.lower()):
        publish_suffix = file_stem[len(asset_name):].lstrip("_-")

    version_match = re.search(r"(?i)(?:^|[_\-])v(\d+)(?:$|[_\-])", file_stem)

    return {
        "asset_base": join_normalized_path(drive, asset_base_parts) if (drive or asset_base_parts) else "",
        "asset_category_guess": guess_asset_category_from_parts(category_parts),
        "asset_category_path": "/".join(category_parts),
        "publish_version_digits": len(version_match.group(1)) if version_match else 0,
        "publish_suffix": publish_suffix,
    }


def infer_project_config_from_example_files(project_name, publish_file_path, scene_file_path, prefix="", geometry_root_hint="Geometry/{asset_name}"):
    normalized_publish = normalize_directory_choice(publish_file_path)
    normalized_scene = normalize_directory_choice(scene_file_path)
    if not normalized_publish or not os.path.exists(normalized_publish):
        raise ValueError("Publish file path is invalid.")
    if not normalized_scene or not os.path.exists(normalized_scene):
        raise ValueError("Scene file path is invalid.")

    scene_config = infer_scene_path_config(normalized_scene)
    publish_config = infer_publish_path_config(normalized_publish)
    drive, _parts = split_normalized_path(normalized_scene)

    inferred_prefix = str(prefix or "").strip() or str(scene_config.get("inferred_prefix", "") or "").strip()
    config = normalize_project_config_entry(project_name, DEFAULT_PROJECT_CONFIG.get('BTS', {}))
    config.update({
        "drive": drive or config.get("drive", ""),
        "prefix": inferred_prefix or config.get("prefix", ""),
        "asset_base": publish_config.get("asset_base") or config.get("asset_base", ""),
        "scene_base": scene_config.get("scene_base") or config.get("scene_base", ""),
        "project_json_base": scene_config.get("scene_base") or drive or config.get("project_json_base", ""),
        "output_base": scene_config.get("scene_base") or drive or config.get("output_base", ""),
        "scene_root_dir": scene_config.get("scene_root_dir") or config.get("scene_root_dir", "scenes"),
        "ren_dir": scene_config.get("ren_dir") or config.get("ren_dir", "ren"),
        "cache_dir": config.get("cache_dir", "cache"),
        "publish_dir": config.get("publish_dir", "pub"),
        "scene_example_file": normalized_scene,
        "publish_example_file": normalized_publish,
        "scene_structure_mode": scene_config.get("scene_structure_mode", "unknown"),
        "scene_identifier_mode": scene_config.get("scene_identifier_mode", "unknown"),
        "scene_version_digits": str(scene_config.get("scene_version_digits", 0)),
        "publish_version_digits": str(publish_config.get("publish_version_digits", 0)),
        "publish_suffix": publish_config.get("publish_suffix", ""),
        "geometry_root_hint": str(geometry_root_hint or "Geometry/{asset_name}"),
    })

    category_guess = publish_config.get("asset_category_guess", "ch")
    category_path = publish_config.get("asset_category_path", "")
    if category_path:
        if category_guess == "bg":
            config["asset_bg_dir"] = category_path
        elif category_guess == "prop":
            config["asset_prop_dir"] = category_path
        else:
            config["asset_ch_dir"] = category_path

    report_lines = [
        "=" * 80,
        f"rrRender Project Wizard | Project: {project_name}",
        f"Publish file: {normalized_publish}",
        f"Scene file:   {normalized_scene}",
        "-" * 80,
        f"Drive: {config.get('drive', '')}",
        f"Prefix: {config.get('prefix', '') or '(not inferred)'}",
        f"Asset Base: {config.get('asset_base', '')}",
        f"Scene Base: {config.get('scene_base', '')}",
        f"Scene Root Dir: {config.get('scene_root_dir', '')}",
        f"Work Dir: {config.get('ren_dir', '')}",
        f"Asset Category Guess: {category_guess}",
        f"Asset Category Path: {category_path or '(not inferred)'}",
        f"Scene Structure Mode: {config.get('scene_structure_mode', '')}",
        f"Scene Identifier Mode: {config.get('scene_identifier_mode', '')}",
        f"Scene Version Digits: {config.get('scene_version_digits', '0')}",
        f"Publish Version Digits: {config.get('publish_version_digits', '0')}",
        f"Publish Suffix: {config.get('publish_suffix', '') or '(none)'}",
        f"Geometry Root Hint: {config.get('geometry_root_hint', '')}",
        "=" * 80,
    ]

    return config, report_lines


def write_or_replace_text_block(text_name, lines):
    text = bpy.data.texts.get(text_name)
    if not text:
        text = bpy.data.texts.new(text_name)
    text.clear()
    text.write("\n".join(lines))
    return text


def get_asset_category_path(category_name, project_name=None):
    category_id = str(category_name or "").lower()
    for category in get_schema_asset_categories(project_name):
        if str(category.get("id", "")).lower() == category_id:
            root_path = normalize_directory_choice(category.get("root_path", ""))
            if root_path:
                return root_path
    return os.path.join(get_project_asset_base(project_name), get_asset_category_dir_name(category_name, project_name))


def get_asset_blend_path(category_name, asset_name, project_name=None):
    category_id = str(category_name or "").lower()
    category_aliases = {
        "ch": {"ch", "char", "character"},
        "bg": {"bg", "background", "env", "environment"},
        "prop": {"prop", "props"},
    }
    accepted_ids = category_aliases.get(category_id, {category_id})
    for category in get_schema_asset_categories(project_name):
        schema_category_id = str(category.get("id", "")).lower()
        if schema_category_id not in accepted_ids:
            continue
        template = str(category.get("publish_file_template", "") or "").strip()
        root_path = normalize_directory_choice(category.get("root_path", ""))
        if template and root_path:
            template_path = template.format(root=root_path, asset_name=asset_name, asset_id=asset_name).replace("\\", "/")
            versioned_blend_dir = os.path.join(root_path, asset_name, "mod", "blend")
            if os.path.isdir(versioned_blend_dir):
                versioned_files = []
                for file_name in os.listdir(versioned_blend_dir):
                    if not file_name.lower().endswith(".blend"):
                        continue
                    match = re.search(r"v(\d+)", file_name, re.IGNORECASE)
                    version_number = int(match.group(1)) if match else -1
                    versioned_files.append((version_number, file_name))
                if versioned_files:
                    versioned_files.sort(key=lambda item: (item[0], item[1]), reverse=True)
                    return os.path.join(versioned_blend_dir, versioned_files[0][1]).replace("\\", "/")

            direct_mod_blend = os.path.join(root_path, asset_name, "mod", f"{asset_name}.blend")
            if os.path.exists(direct_mod_blend):
                return direct_mod_blend.replace("\\", "/")

            if os.path.exists(template_path) and template_path.lower().endswith(".blend"):
                return template_path

    category_dir = get_asset_category_dir_name(category_name, project_name)
    return os.path.join(get_project_asset_base(project_name), category_dir, asset_name, "mod", f"{asset_name}.blend")


def get_project_json_path(filename, project_name=None):
    schema = get_project_schema_entry(project_name)
    paths = schema.get("paths", {}) if isinstance(schema, dict) else {}
    filename_key = os.path.splitext(os.path.basename(str(filename or "")))[0].lower()
    if filename_key == "renderpreset":
        candidate = normalize_directory_choice(paths.get("render_preset_json", ""))
        if candidate:
            return candidate
    if filename_key == "rendersetting":
        candidate = normalize_directory_choice(paths.get("render_setting_json", ""))
        if candidate:
            return candidate
    return os.path.join(get_project_json_base(project_name), "_json", filename)


def get_project_output_path(scene_number, cut_number, project_name=None):
    schema = get_project_schema_entry(project_name)
    output_schema = schema.get("output", {}) if isinstance(schema, dict) else {}
    template = str(output_schema.get("root_template", "") or "").strip()
    work_dir_name = get_project_ren_dir_name(project_name)
    if template:
        browser_values = get_browser_level_values(bpy.context, project_name)
        selection_values = {
            "scene": str(scene_number),
            "cut": str(cut_number),
            "work": "" if is_root_work_dir_name(work_dir_name) else work_dir_name,
            "episode": str(scene_number),
            "shot": str(cut_number),
        }
        for index, value in enumerate(browser_values, start=1):
            selection_values[f"level_{index}"] = str(value or "")
        level_defs = get_browser_non_work_levels(project_name)
        for index, level_def in enumerate(level_defs, start=1):
            level_id = str(level_def.get("id", "") or "").strip()
            if level_id:
                selection_values[level_id] = str(browser_values[index - 1] if index - 1 < len(browser_values) else "")
        try:
            return template.format(**selection_values).replace("\\", "/")
        except Exception:
            pass
    output_base = get_project_output_base(project_name)
    output_parts = [output_base]
    if os.path.basename(output_base.rstrip("/\\")).lower() != "output":
        output_parts.append("output")
    if not is_root_work_dir_name(work_dir_name):
        output_parts.append(work_dir_name)
    output_parts.extend([str(scene_number), f"{scene_number}_{cut_number}"])
    return os.path.join(*output_parts)

_recent_browser_state_ready = False
_recent_browser_state_suspended = False
_browser_sync_suspended = False
_pending_browser_focus_filepath = ""
_pending_browser_focus_project = ""
RECENT_BROWSER_STATE_DIR = r"C:\_json"
RECENT_BROWSER_STATE_FILE = "rrRender_recent_browser_state.json"


def get_recent_browser_state_path():
    return os.path.join(RECENT_BROWSER_STATE_DIR, RECENT_BROWSER_STATE_FILE)


def get_legacy_recent_browser_state_paths():
    paths = []
    try:
        base_dir = bpy.utils.user_resource('CONFIG')
        paths.append(os.path.join(base_dir, RECENT_BROWSER_STATE_FILE))
    except Exception:
        pass

    paths.append(os.path.join(os.path.expanduser("~"), RECENT_BROWSER_STATE_FILE))
    return [path for path in paths if os.path.abspath(path) != os.path.abspath(get_recent_browser_state_path())]


def save_recent_browser_state(context=None, force=False):
    global _recent_browser_state_ready, _recent_browser_state_suspended
    if not force and (not _recent_browser_state_ready or _recent_browser_state_suspended):
        return

    context = bpy.context if context is None else context
    try:
        scene = context.scene
        my_tool = getattr(scene, "my_tool", None)
        project_settings = getattr(scene, "my_project_settings", None)
        if not my_tool or not project_settings:
            return

        data = {
            "project": str(getattr(project_settings, "projects", "") or ""),
            "scene_number": str(getattr(my_tool, "scene_number", "") or ""),
            "cut_number": str(getattr(my_tool, "cut_number", "") or ""),
            "browser_level_3": str(getattr(my_tool, "browser_level_3", "") or ""),
            "browser_level_4": str(getattr(my_tool, "browser_level_4", "") or ""),
            "browser_level_5": str(getattr(my_tool, "browser_level_5", "") or ""),
            "blend_file": str(getattr(my_tool, "blend_file", "") or ""),
        }

        path = get_recent_browser_state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[RecentState][WARN] save failed: {e}")


def load_recent_browser_state():
    path = get_recent_browser_state_path()
    if not os.path.exists(path):
        for legacy_path in get_legacy_recent_browser_state_paths():
            if os.path.exists(legacy_path):
                path = legacy_path
                break
        else:
            return {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[RecentState][WARN] load failed: {e}")
        return {}


def restore_recent_browser_state():
    global _recent_browser_state_ready, _recent_browser_state_suspended, _pending_browser_focus_filepath
    try:
        _recent_browser_state_suspended = True
        scene = bpy.context.scene
        my_tool = getattr(scene, "my_tool", None)
        project_settings = getattr(scene, "my_project_settings", None)
        if not my_tool or not project_settings:
            _recent_browser_state_ready = True
            return None

        focus_filepath = _pending_browser_focus_filepath or bpy.data.filepath
        if focus_filepath and sync_browser_to_filepath(bpy.context, focus_filepath, save_state=True):
            _pending_browser_focus_filepath = ""
            _recent_browser_state_ready = True
            return None

        data = load_recent_browser_state()
        if not data:
            _recent_browser_state_ready = True
            return None

        project = normalize_project_name(data.get("project", ""))
        if project:
            valid_projects = {item.identifier for item in MyProjectSettings1.bl_rna.properties["projects"].enum_items}
            if project in valid_projects:
                project_settings.projects = project

        scene_number = str(data.get("scene_number", "") or "")
        if scene_number:
            safe_set_enum_property(my_tool, "scene_number", get_cached_scenes(), preferred_value=scene_number, fallback_identifier="NO_SCENES")

        cut_number = str(data.get("cut_number", "") or "")
        if cut_number and scene_number:
            safe_set_enum_property(my_tool, "cut_number", get_cached_cuts(scene_number), preferred_value=cut_number, fallback_identifier="NO_CUTS")

        for index in range(3, MAX_BROWSER_LEVELS + 1):
            level_value = str(data.get(f"browser_level_{index}", "") or "")
            if not level_value:
                continue
            safe_set_enum_property(my_tool, f"browser_level_{index}", get_browser_level_items(index, bpy.context), preferred_value=level_value, fallback_identifier=f"NO_LEVEL{index}")

        blend_file = str(data.get("blend_file", "") or "")
        if blend_file and scene_number and cut_number:
            safe_set_enum_property(my_tool, "blend_file", get_blend_files(my_tool, bpy.context), preferred_value=blend_file, fallback_identifier="NO_FILES")

        save_recent_browser_state(force=True)
    except Exception as e:
        print(f"[RecentState][WARN] restore failed: {e}")
    finally:
        _recent_browser_state_suspended = False
        _recent_browser_state_ready = True

    return None


def get_current_project_name(default='BTS'):
    """현재 UI의 프로젝트 이름을 정규화하여 반환"""
    try:
        raw_name = bpy.context.scene.my_project_settings.projects
    except Exception:
        raw_name = default

    raw_name = str(raw_name).strip()
    if not raw_name:
        raw_name = default

    return normalize_project_name(raw_name)


def get_config_by_project_name(project_name=None):
    ensure_project_config_loaded()
    normalized = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    return PROJECT_CONFIG.get(normalized, PROJECT_CONFIG['BTS'])


def get_current_config():
    ensure_project_config_loaded()
    return PROJECT_CONFIG.get(get_current_project_name(), PROJECT_CONFIG['BTS'])


def get_project_paths(project_name=None):
    return get_project_drive(project_name)


def get_project_prefix(project_name=None):
    return get_config_by_project_name(project_name)['prefix']



# ✅ 외부 rrRender.py 파일 경로
SCRIPT_PATH = r"M:\RND\SFtools\2023\render\rrRender.py"
SCRIPT_BACKUP_DIR = r"M:\RND\SFtools\2023\render\_t"
DEPLOY_ALLOWED_USERS = {"hwang"}
HWANG_LOCAL_SCRIPT_PATH = r"C:\Users\hwang\Desktop\codex\rrRender\rrRender.py"

# ✅ 현재 모듈 이름 (import할 때 씀)
MODULE_NAME = "rrRender"

# ✅ 마지막으로 불러온 수정 시간
last_mtime = None


def can_show_deploy_tools():
    return os.environ.get("USERNAME", "").strip().lower() in {user.lower() for user in DEPLOY_ALLOWED_USERS}


def get_update_source_path():
    if os.environ.get("USERNAME", "").strip().lower() == "hwang":
        return HWANG_LOCAL_SCRIPT_PATH
    return SCRIPT_PATH


def sync_hwang_local_project_json_files():
    if not is_hwang_dev_environment():
        return []
    source_dir = get_local_project_settings_source_dir()
    target_dir = get_runtime_project_settings_dir()
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Local JSON source dir not found: {source_dir}")

    os.makedirs(target_dir, exist_ok=True)
    copied_paths = []
    for file_name in (PROJECT_SETTINGS_FILENAME, PROJECT_SCHEMA_FILENAME, PROJECT_OVERRIDE_FILENAME):
        source_path = os.path.join(source_dir, file_name)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Local JSON source file not found: {source_path}")
        target_path = os.path.join(target_dir, file_name)
        shutil.copy2(source_path, target_path)
        copied_paths.append(target_path)
    return copied_paths


def get_next_script_backup_path(target_path=SCRIPT_PATH, backup_dir=SCRIPT_BACKUP_DIR):
    """_t 폴더의 기존 백업 파일명을 훑어서 다음 버전 경로를 반환한다."""
    base_name = os.path.splitext(os.path.basename(target_path))[0]
    extension = os.path.splitext(target_path)[1]
    version_pattern = re.compile(
        rf"^{re.escape(base_name)}_v(\d+)(?:.*){re.escape(extension)}$",
        re.IGNORECASE,
    )

    max_version = 0
    if os.path.isdir(backup_dir):
        for file_name in os.listdir(backup_dir):
            match = version_pattern.match(file_name)
            if not match:
                continue
            max_version = max(max_version, int(match.group(1)))

    next_version = max_version + 1
    backup_name = f"{base_name}_v{next_version:03d}{extension}"
    return os.path.join(backup_dir, backup_name), next_version

class DEV_OT_reload_rrrender(bpy.types.Operator):
    """외부 rrRender.py 다시 불러오기"""
    bl_idname = "dev.reload_rrrender"
    bl_label = "Update Script"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        module_name = "rrRender"
        source_path = get_update_source_path()

        if module_name in sys.modules:
            mod = sys.modules[module_name]
            local_path = os.path.abspath(mod.__file__)
        else:
            self.report({'ERROR'}, f"{module_name} 모듈을 찾을 수 없음")
            return {'CANCELLED'}

        # 서버 → 로컬 복사
        try:
            shutil.copy2(source_path, local_path)
        except Exception as e:
            self.report({'ERROR'}, f"복사 실패: {e}")
            return {'CANCELLED'}

        json_sync_message = ""
        if is_hwang_dev_environment():
            try:
                copied_json_paths = sync_hwang_local_project_json_files()
                json_sync_message = f" | JSON sync: {len(copied_json_paths)} files"
            except Exception as e:
                self.report({'WARNING'}, f"스크립트는 갱신됐지만 JSON sync 실패: {e}")

        self.report({'INFO'}, f"{source_path} → {local_path} 복사 완료{json_sync_message}")

        # 🔄 Blender 전체 스크립트 리로드
        bpy.ops.script.reload()

        return {'FINISHED'}


def _dev_reload_rrrender_execute(self, context):
    module_name = "rrRender"
    source_path = get_update_source_path()

    if module_name in sys.modules:
        mod = sys.modules[module_name]
        local_path = os.path.abspath(mod.__file__)
    else:
        self.report({'ERROR'}, f"{module_name} 모듈을 찾을 수 없음")
        return {'CANCELLED'}

    try:
        shutil.copy2(source_path, local_path)
    except Exception as e:
        self.report({'ERROR'}, f"복사 실패: {e}")
        return {'CANCELLED'}

    json_sync_message = ""
    if is_hwang_dev_environment():
        try:
            copied_json_paths = sync_hwang_local_project_json_files()
            json_sync_message = f" | JSON sync: {len(copied_json_paths)} files"
        except Exception as e:
            self.report({'WARNING'}, f"스크립트는 갱신됐지만 JSON sync 실패: {e}")

    self.report({'INFO'}, f"{source_path} -> {local_path} 복사 완료{json_sync_message}")

    try:
        bpy.ops.script.reload()
    except RuntimeError as e:
        message = str(e)
        if "running modal operators" in message:
            self.report({'WARNING'}, "스크립트 파일은 업데이트됐지만 현재 모달 작업 때문에 자동 리로드는 못 했습니다. 작업 종료 후 Update Script를 한 번 더 눌러주세요.")
        else:
            self.report({'WARNING'}, f"스크립트 파일은 업데이트됐지만 자동 리로드는 실패했습니다: {e}")

    return {'FINISHED'}


DEV_OT_reload_rrrender.execute = _dev_reload_rrrender_execute


class DEV_OT_deploy_rrrender(bpy.types.Operator):
    """현재 로컬 rrRender.py를 서버 경로로 배포하고 기존 배포본은 _t에 버전 백업"""
    bl_idname = "dev.deploy_rrrender"
    bl_label = "Deploy Script"
    bl_options = {'REGISTER', 'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        local_path = os.path.abspath(__file__)
        target_path = SCRIPT_PATH
        backup_dir = SCRIPT_BACKUP_DIR

        if not can_show_deploy_tools():
            self.report({'WARNING'}, "허용된 사용자만 배포할 수 있습니다.")
            return {'CANCELLED'}

        if not os.path.exists(local_path):
            self.report({'ERROR'}, f"로컬 스크립트를 찾을 수 없음: {local_path}")
            return {'CANCELLED'}

        if normalize_path(local_path) == normalize_path(target_path):
            self.report({'WARNING'}, "현재 스크립트가 이미 배포 경로에서 실행 중입니다.")
            return {'CANCELLED'}

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            os.makedirs(backup_dir, exist_ok=True)

            backup_path = None
            if os.path.exists(target_path):
                backup_path, version_number = get_next_script_backup_path(target_path, backup_dir)
                shutil.copy2(target_path, backup_path)
                print(f"[DEPLOY] 기존 배포본 백업 완료: v{version_number:03d} -> {backup_path}")

            shutil.copy2(local_path, target_path)
            message = f"배포 완료: {local_path} -> {target_path}"
            if backup_path:
                message += f" | backup: {os.path.basename(backup_path)}"
            self.report({'INFO'}, message)
            print(f"[DEPLOY] {message}")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"배포 실패: {exc}")
            return {'CANCELLED'}


# import sf_blendLdv
# if script_path not in sys.path:
    # sys.path.append(script_path)
# SF_OT_AddPropertiesAndLink 클래스를 임포트
# from sf_blendLdv import SF_OT_AddPropertiesAndLink
# from sf_blendLdv import SF_OT_LinkCharacterLights
# from SF_OT_AddPropertiesAndLink import SF_OT_AddPropertiesAndLink
# from SF_OT_LinkCharacterLights import SF_OT_LinkCharacterLights

# from sf_blendLdv import SF_OT_LinkRimToNode
# from SF_OT_LinkRimtoNode import SF_OT_LinkRimToNode

# from sf_blendLdv import MyProjectSettings

################################################################
######################### Basic Preperation ####################
################################################################

# # 파일 경로에서 씬과 컷 번호 추출 함수
# def extract_scene_cut_from_filename(filepath):
    # filename = os.path.basename(filepath)
    # project_prefix = get_project_prefix()  # 프로젝트 접두사를 가져옵니다.
    # regex_pattern = fr'{project_prefix}_(\d{4})_(\d{4})_ren_v\d{3}\.blend'  # 프로젝트 접두사를 사용한 정규 표현식
    # match = re.match(regex_pattern, filename)

    # # match = re.match(r'ttm_(\d{4})_(\d{4})_ren_v\d{3}\.blend', filename)
    # if match:
        # scene_number, cut_number = match.groups()
        # return scene_number, cut_number
    # return None, None
def extract_scene_cut_from_filename(filepath):
    if not filepath: 
        return None, None
        
    import os
    import re
    filename = os.path.basename(filepath)
    project_prefix = get_project_prefix()  # 프로젝트 접두사를 가져옵니다.
    
    # ✅ 핵심: f-string 안에서 정규식 중괄호를 쓰려면 {{ }} 처럼 두 번 써야 합니다!
    # 그리고 _ch 등이 붙은 파일도 인식하도록 패턴을 깔끔하게 다듬었습니다.
    regex_pattern = fr'{project_prefix}_(\d{{4}})_(\d{{4}})'
    match = re.search(regex_pattern, filename)

    if match:
        scene_number, cut_number = match.groups()
        return scene_number, cut_number
    return None, None


def infer_project_from_filepath(filepath):
    ensure_project_config_loaded()
    filename = os.path.basename(str(filepath or ""))
    if not filename:
        return ""

    for project_name in sorted(PROJECT_CONFIG.keys()):
        prefix = str(get_project_prefix(project_name) or "").strip()
        if not prefix:
            continue
        if re.match(rf"(?i)^{re.escape(prefix)}_", filename):
            return project_name
    return ""


def extract_scene_cut_from_root_relative_path(filepath, project_name=None):
    normalized_path = normalize_directory_choice(filepath)
    scene_root_path = normalize_directory_choice(get_scene_root_path(project_name))
    if not normalized_path or not scene_root_path:
        return "", ""

    file_directory = normalize_directory_choice(os.path.dirname(normalized_path))
    file_dir_lower = file_directory.lower()
    scene_root_lower = scene_root_path.lower().rstrip("/")
    if not file_dir_lower.startswith(scene_root_lower):
        return "", ""

    relative = file_directory[len(scene_root_lower):].strip("/")
    if not relative:
        return "", ""

    parts = [part for part in relative.split("/") if part]
    work_dirs = {str(name).lower() for name in get_scene_work_dir_names(project_name)}
    if len(parts) >= 3 and str(parts[2]).lower() in work_dirs:
        return parts[0], parts[1]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", ""


def extract_browser_level_values_from_root_relative_path(filepath, project_name=None):
    normalized_path = normalize_directory_choice(filepath)
    scene_root_path = normalize_directory_choice(get_scene_root_path(project_name))
    if not normalized_path or not scene_root_path:
        return []

    file_directory = normalize_directory_choice(os.path.dirname(normalized_path))
    file_dir_lower = file_directory.lower()
    scene_root_lower = scene_root_path.lower().rstrip("/")
    if not file_dir_lower.startswith(scene_root_lower):
        return []

    relative = file_directory[len(scene_root_lower):].strip("/")
    if not relative:
        return []

    parts = [part for part in relative.split("/") if part]
    work_dirs = {str(name).lower() for name in get_scene_work_dir_names(project_name)}
    values = []
    for part in parts:
        if str(part).lower() in work_dirs:
            break
        values.append(part)
    return values


def sync_browser_to_filepath(context=None, filepath=None, save_state=True):
    global _browser_sync_suspended, _pending_browser_focus_filepath
    context = bpy.context if context is None else context
    filepath = bpy.data.filepath if filepath is None else filepath
    if not context or not getattr(context, "scene", None) or not filepath:
        return False

    scene = context.scene
    my_tool = getattr(scene, "my_tool", None)
    project_settings = getattr(scene, "my_project_settings", None)
    if not my_tool or not project_settings:
        return False

    project_name = infer_project_from_filepath(filepath) or get_current_project_name()
    scene_number = ""
    cut_number = ""
    level_values = []

    try:
        _browser_sync_suspended = True

        original_project = get_current_project_name()
        if project_name and project_name != original_project:
            try:
                project_settings.projects = project_name
            except Exception:
                pass

        normalized_path = str(filepath).replace("\\", "/")
        work_dirs_pattern = "|".join(re.escape(name.strip("/\\")) for name in get_scene_work_dir_names(project_name))

        level_values = extract_browser_level_values_from_root_relative_path(normalized_path, project_name)
        if level_values:
            scene_number = level_values[0] if len(level_values) >= 1 else ""
            cut_number = level_values[1] if len(level_values) >= 2 else scene_number

        if not scene_number or not cut_number:
            scene_root_name = re.escape(get_project_scene_root_dir(project_name).strip("/\\"))
            path_match = re.search(rf"/{scene_root_name}/([^/]+)/([^/]+)/({work_dirs_pattern})/", normalized_path)
            if path_match:
                scene_number, cut_number, _work_dir_name = path_match.groups()
            else:
                filename = os.path.basename(normalized_path)
                file_match = re.search(rf"_([0-9]{{4}})_([0-9]{{4}})_({work_dirs_pattern})_", filename)
                if file_match:
                    scene_number, cut_number, _work_dir_name = file_match.groups()

        if not scene_number or not cut_number:
            scene_number, cut_number = extract_scene_cut_from_filename(filepath)

        if not scene_number or not cut_number:
            return False

        scene_items = get_cached_scenes()
        safe_set_enum_property(my_tool, "scene_number", scene_items, preferred_value=scene_number, fallback_identifier="NO_SCENES")

        cut_items = get_cached_cuts(scene_number)
        safe_set_enum_property(my_tool, "cut_number", cut_items, preferred_value=cut_number, fallback_identifier="NO_CUTS")

        for index in range(3, MAX_BROWSER_LEVELS + 1):
            level_items = get_browser_level_items(index, context, project_name)
            preferred_value = level_values[index - 1] if len(level_values) >= index else ""
            safe_set_enum_property(my_tool, f"browser_level_{index}", level_items, preferred_value=preferred_value, fallback_identifier=f"NO_LEVEL{index}")

        enum_value = find_blend_file_enum_value(scene_number, cut_number, filepath, context)
        if enum_value:
            my_tool.blend_file = enum_value
        else:
            set_blend_file_to_first_available(context)
    finally:
        _browser_sync_suspended = False

    if save_state:
        save_recent_browser_state(context, force=True)
    if filepath and _pending_browser_focus_filepath:
        try:
            if normalize_path(filepath) == normalize_path(_pending_browser_focus_filepath):
                _pending_browser_focus_filepath = ""
        except Exception:
            pass
    return True


def schedule_browser_sync(filepath=None, delay=0.15):
    target_path = bpy.data.filepath if filepath is None else filepath

    def _deferred_sync():
        try:
            if target_path and bpy.data.filepath and normalize_path(target_path) == normalize_path(bpy.data.filepath):
                sync_browser_to_filepath(bpy.context, bpy.data.filepath, save_state=True)
        except Exception as e:
            print(f"[BrowserSync][WARN] deferred sync failed: {e}")
        return None

    try:
        bpy.app.timers.register(_deferred_sync, first_interval=delay)
    except Exception as e:
        print(f"[BrowserSync][WARN] schedule failed: {e}")

def get_character_dir():
    return get_asset_category_path("ch")

def get_background_dir():
    return get_asset_category_path("bg")

def get_prop_dir():
    return get_asset_category_path("prop")

# ---- helper: 인스턴스 꼬리('_<숫자>')만 안전하게 제거 ----
def get_asset_base_name(name: str) -> str:
    """
    이름 끝에 '_<숫자>' 패턴이 있을 때만 그 꼬리를 제거해 base_name 반환.
    예) 'chage_1' -> 'chage', 'boxE_12' -> 'boxE'
        중간에 '_'가 있는 이름(police_box_E)은 그대로 둠.
    """
    head, sep, tail = name.rpartition('_')
    if sep and tail.isdigit():
        return head
    return name


# 디렉토리 내의 하위 폴더 이름을 가져오는 함수
def get_subfolder_names(directory, include_word=None, exclude_word=None):
    subfolder_names = [name for name in os.listdir(directory) 
                       if os.path.isdir(os.path.join(directory, name)) 
                       and (include_word is None or include_word in name) 
                       and (exclude_word is None or exclude_word not in name)]
    # print(f"Directory: {directory}")
    # print(f"Include Word: {include_word}, Exclude Word: {exclude_word}")
    # print(f"Subfolder Names: {subfolder_names}")
    return subfolder_names

def get_character_names():
    character_dir = get_character_dir()
    names = get_subfolder_names(character_dir)
    return [name for name in names if not name.startswith('light')]

def get_bg_names():
    background_dir = get_background_dir()
    names = get_subfolder_names(background_dir)
    return names

def get_prop_names():
    prop_dir = get_prop_dir()
    names = get_subfolder_names(prop_dir)
    non_floor_names = [name for name in names if not name.startswith('floor')]
    return non_floor_names


def find_asset_file_path(directory, asset_name):
    pattern = re.compile(rf"_{asset_name}\.usd$")
    # print(f"Searching in directory: {directory} for asset: {asset_name}")
    for file in os.listdir(directory):
        print(f"Checking file: {file}")
        if pattern.search(file):
            print(f"Found matching file: {file}")
            return os.path.join(directory, file)
    print("No matching file found.")
    return None

def get_category_name(self, asset_name):
    # 동적으로 이름 목록을 가져오기
    character_names = get_character_names()
    bg_names = get_bg_names()
    prop_names = get_prop_names()

    # 기존 카테고리 결정 로직
    if asset_name in character_names:
        return "ch"
    elif asset_name in bg_names:
        return "bg"
    elif asset_name in prop_names:
        return "prop"
    else:
        return "prop"

################################################################
#########################Scene Browser Operation################
################################################################
# 캐시 데이터 구조
cache = {
    "scenes": {},
    "cuts": {}
}

def open_folder(path):
    if os.path.exists(path):
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':  # macOS, Linux
            subprocess.Popen(['xdg-open', path])

class OpenSceneFolderOperator(bpy.types.Operator):
    bl_idname = "file.open_scene_folder"
    bl_label = "Open Scene Folder"

    @classmethod
    def poll(cls, context):
        return context.scene.my_tool.scene_number != ''

    def execute(self, context):
        global _pending_browser_focus_filepath
        scene_number = context.scene.my_tool.scene_number
        path = get_scene_path(scene_number)
        open_folder(path)
        return {'FINISHED'}

class OpenCutFolderOperator(bpy.types.Operator):
    bl_idname = "file.open_cut_folder"
    bl_label = "Open Cut Folder"

    @classmethod
    def poll(cls, context):
        return context.scene.my_tool.cut_number != ''

    def execute(self, context):
        global _pending_browser_focus_filepath
        scene_number = context.scene.my_tool.scene_number
        cut_number = context.scene.my_tool.cut_number
        path = get_cut_path(scene_number, cut_number)
        open_folder(path)
        return {'FINISHED'}


class SF_OT_ProjectPathSettingsPopup(bpy.types.Operator):
    bl_idname = "sf.project_path_settings_popup"
    bl_label = "Project Path Settings"
    bl_description = "Edit project-specific path settings"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        load_project_path_settings_to_ui(context)
        return context.window_manager.invoke_props_dialog(self, width=720)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.sf_project_paths

        header = layout.box()
        header.label(text=f"Project: {get_current_project_name()}", icon='TOOL_SETTINGS')
        row = header.row(align=True)
        row.operator("sf.new_project_popup", icon='ADD')
        row.operator("sf.validate_project", icon='CHECKMARK')
        row.operator("sf.reload_project_path_settings", icon='FILE_REFRESH')
        row.operator("sf.reset_project_path_settings", icon='LOOP_BACK')

        col = layout.column(align=True)
        draw_project_path_field(col, settings, "drive")
        col.prop(settings, "prefix")
        draw_project_path_field(col, settings, "asset_base")
        draw_project_path_field(col, settings, "scene_base")
        draw_project_path_field(col, settings, "project_json_base")
        draw_project_path_field(col, settings, "output_base")

        box = layout.box()
        box.label(text="Asset Sub Paths")
        grid = box.grid_flow(columns=3, align=True)
        grid.prop(settings, "asset_ch_dir")
        grid.prop(settings, "asset_bg_dir")
        grid.prop(settings, "asset_prop_dir")

        box = layout.box()
        box.label(text="Scene Structure")
        grid = box.grid_flow(columns=4, align=True)
        grid.prop(settings, "scene_root_dir")
        grid.prop(settings, "ren_dir")
        grid.prop(settings, "cache_dir")
        grid.prop(settings, "publish_dir")

        box = layout.box()
        box.label(text="Browser Levels")
        box.prop(settings, "browser_level_count")
        for index in range(1, settings.browser_level_count + 1):
            box.prop(settings, f"browser_level_{index}_label", text=f"Level {index}")

        box = layout.box()
        box.label(text="Asset Structure")
        box.prop(settings, "geometry_root_hint")

    def execute(self, context):
        save_project_path_settings_from_ui(context)
        self.report({'INFO'}, f"Saved project path settings for {get_current_project_name()}")
        return {'FINISHED'}


class SF_OT_PickProjectPath(bpy.types.Operator):
    bl_idname = "sf.pick_project_path"
    bl_label = "Pick Project Path"
    bl_description = "Choose a folder for the selected project path field"
    bl_options = {'REGISTER', 'UNDO'}

    target_field: bpy.props.EnumProperty(
        name="Target Field",
        items=[
            ('drive', "Drive", ""),
            ('asset_base', "Asset Base", ""),
            ('scene_base', "Scene Base", ""),
            ('project_json_base', "Project Json Base", ""),
            ('output_base', "Output Base", ""),
        ]
    )
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        settings = context.scene.sf_project_paths
        self.directory = getattr(settings, self.target_field, "")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = context.scene.sf_project_paths
        setattr(settings, self.target_field, normalize_directory_choice(self.directory))
        return {'FINISHED'}


def draw_project_path_field(layout, settings, field_name):
    row = layout.row(align=True)
    row.prop(settings, field_name)
    picker = row.operator("sf.pick_project_path", text="", icon='FILE_FOLDER')
    picker.target_field = field_name


class SF_OT_NewProjectPopup(bpy.types.Operator):
    bl_idname = "sf.new_project_popup"
    bl_label = "New Project Wizard"
    bl_description = "Create a new rrRender project configuration from a publish file and a scene file"
    bl_options = {'REGISTER', 'UNDO'}

    project_name: bpy.props.StringProperty(name="Project Name")
    prefix: bpy.props.StringProperty(name="Prefix")
    publish_file: bpy.props.StringProperty(name="Publish File", subtype='FILE_PATH')
    scene_file: bpy.props.StringProperty(name="Scene File", subtype='FILE_PATH')
    geometry_root_hint: bpy.props.StringProperty(name="Geometry Root", default="Geometry/{asset_name}")

    def invoke(self, context, event):
        self.project_name = ""
        self.prefix = ""
        self.publish_file = ""
        self.scene_file = ""
        self.geometry_root_hint = "Geometry/{asset_name}"
        return context.window_manager.invoke_props_dialog(self, width=720)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Project Info", icon='TOOL_SETTINGS')
        box.prop(self, "project_name")
        box.prop(self, "prefix")

        files = layout.box()
        files.label(text="Example Files", icon='FILE_FOLDER')
        files.prop(self, "publish_file")
        files.prop(self, "scene_file")

        structure = layout.box()
        structure.label(text="Geometry Root Hint", icon='MESH_DATA')
        structure.prop(self, "geometry_root_hint")
        structure.label(text="Example: Geometry/{asset_name} or geo", icon='INFO')

    def execute(self, context):
        try:
            normalized_name = normalize_project_name(self.project_name)
            if not normalized_name:
                raise ValueError("Project name is empty.")
            if normalized_name in PROJECT_CONFIG:
                raise ValueError(f"Project already exists: {normalized_name}")

            inferred_config, report_lines = infer_project_config_from_example_files(
                normalized_name,
                self.publish_file,
                self.scene_file,
                prefix=self.prefix,
                geometry_root_hint=self.geometry_root_hint,
            )
            project_name = create_new_project_config(normalized_name, self.prefix)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        PROJECT_CONFIG[project_name] = normalize_project_config_entry(project_name, inferred_config)
        save_project_config_store()
        context.scene.my_project_settings.projects = project_name
        load_project_path_settings_to_ui(context, project_name)
        clear_path_caches()
        write_or_replace_text_block("rrRender_ProjectWizardReport", report_lines)
        self.report({'INFO'}, f"Created project {project_name} from wizard")
        return {'FINISHED'}


def get_selected_asset_items(scene):
    selected_items = []
    for category in scene.sf_file_categories:
        for item in category.items:
            if item.is_selected:
                selected_items.append((category.name, item.name))
    return selected_items


class SF_OT_ValidateProject(bpy.types.Operator):
    bl_idname = "sf.validate_project"
    bl_label = "Validate Project"
    bl_description = "Dry-run validation of current project paths, assets, and cache targets"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        my_tool = getattr(scene, "my_tool", None)
        project_name = get_current_project_name()
        project_config = get_current_config()

        scene_number = str(getattr(my_tool, "scene_number", "") or "")
        cut_number = str(getattr(my_tool, "cut_number", "") or "")
        selected_items = get_selected_asset_items(scene)

        report_lines = []
        ok_count = 0
        warn_count = 0
        error_count = 0

        def add(level, message):
            nonlocal ok_count, warn_count, error_count
            report_lines.append(f"[{level}] {message}")
            if level == "OK":
                ok_count += 1
            elif level == "WARN":
                warn_count += 1
            elif level == "ERROR":
                error_count += 1

        report_lines.append("=" * 80)
        report_lines.append(f"rrRender Validate Report | Project: {project_name}")
        report_lines.append(f"Scene: {scene_number or '-'} | Cut: {cut_number or '-'}")
        report_lines.append("=" * 80)
        report_lines.append("")

        for key in PROJECT_CONFIG_FIELDS:
            value = str(project_config.get(key, "") or "")
            if value:
                add("OK", f"Config {key} = {value}")
            else:
                add("WARN", f"Config {key} is empty")

        scene_root_path = get_scene_root_path(project_name)
        add("OK" if os.path.exists(scene_root_path) else "ERROR", f"Scene root path: {scene_root_path}")

        render_setting_path = get_project_json_path("renderSetting.json", project_name)
        add("OK" if os.path.exists(render_setting_path) else "WARN", f"Render setting JSON: {render_setting_path}")

        render_preset_path = get_render_preset_json_path(project_name)
        add("OK" if render_preset_path and os.path.exists(render_preset_path) else "WARN", f"Render preset JSON: {render_preset_path}")

        if scene_number:
            scene_path = get_scene_path(scene_number, project_name)
            add("OK" if os.path.exists(scene_path) else "ERROR", f"Scene path: {scene_path}")
        else:
            add("WARN", "Scene number is empty")

        if scene_number and cut_number:
            cut_path = get_cut_path(scene_number, cut_number, project_name)
            ren_path = get_ren_path(scene_number, cut_number, project_name)
            cache_path = get_cache_path(scene_number, cut_number, project_name)
            add("OK" if os.path.exists(cut_path) else "ERROR", f"Cut path: {cut_path}")
            add("OK" if os.path.exists(ren_path) else "WARN", f"Render work path: {ren_path}")
            add("OK" if os.path.exists(cache_path) else "WARN", f"Cache path: {cache_path}")
        else:
            add("WARN", "Cut number is empty")

        report_lines.append("")
        report_lines.append("-" * 80)
        report_lines.append(f"Selected Assets: {len(selected_items)}")
        report_lines.append("-" * 80)

        if not selected_items:
            add("WARN", "No selected assets in Scene Browser")

        for cat_name, asset_name in selected_items:
            report_lines.append("")
            report_lines.append(f"[ASSET] {asset_name} ({cat_name})")

            blend_path = get_asset_blend_path(cat_name, asset_name, project_name)
            add("OK" if os.path.exists(blend_path) else "ERROR", f"Publish blend: {blend_path}")

            asset_col = bpy.data.collections.get(f"{asset_name}_col")
            if asset_col:
                add("OK", f"Scene collection found: {asset_col.name}")
                geometry_root = resolve_asset_geometry_root(asset_col, asset_name)
                if geometry_root:
                    mesh_count = sum(1 for _ in iter_asset_geometry_meshes(asset_col, asset_name))
                    add("OK", f"Geometry root: {geometry_root.name} | mesh count: {mesh_count}")
                else:
                    add("WARN", f"Geometry root not resolved inside {asset_col.name}")
            else:
                add("WARN", f"Scene collection missing: {asset_name}_col")

            if scene_number and cut_number:
                expected_usd_path = get_usd_path(scene_number, cut_number, asset_name, project_name, cat_name)
                usd_found_path = expected_usd_path if os.path.exists(expected_usd_path) else None

                cache_dir = get_cache_path(scene_number, cut_number, project_name)
                search_target = f"_{cat_name}_{asset_name}.".lower()
                if not usd_found_path and os.path.exists(cache_dir):
                    for filename in os.listdir(cache_dir):
                        if filename.lower().endswith(".usd") and search_target in filename.lower():
                            usd_found_path = os.path.join(cache_dir, filename)
                            break

                if usd_found_path:
                    add("OK", f"USD cache: {usd_found_path}")
                else:
                    add("WARN", f"USD cache not found for {asset_name}")

        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append(f"Summary | OK: {ok_count} | WARN: {warn_count} | ERROR: {error_count}")
        report_lines.append("=" * 80)

        text_name = "rrRender_ValidateReport"
        try:
            text_block = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
            text_block.clear()
            text_block.write("\n".join(report_lines))
        except Exception as e:
            print(f"[Validate][WARN] Could not write text block: {e}")

        for line in report_lines:
            print(line)

        scene.sf_message = f"Validate complete | OK {ok_count} | WARN {warn_count} | ERROR {error_count}"
        if error_count:
            self.report({'WARNING'}, scene.sf_message)
        else:
            self.report({'INFO'}, scene.sf_message)
        return {'FINISHED'}
    
def set_blend_file_to_first_available(context):
    if _recent_browser_state_suspended:
        return

    my_tool = getattr(context.scene, "my_tool", None)
    if not my_tool or not hasattr(my_tool, "blend_file"):
        return

    try:
        items = get_blend_files(my_tool, context)
        if items:
            current_value = str(getattr(my_tool, "blend_file", "") or "")
            safe_set_enum_property(my_tool, "blend_file", items, preferred_value=current_value, fallback_identifier="NO_FILES")
    except Exception as e:
        print(f"[RecentState][WARN] blend_file fallback failed: {e}")


def populate_browser_levels_from_index(context, start_index):
    my_tool = getattr(context.scene, "my_tool", None)
    if not my_tool:
        return

    for index in range(max(3, start_index), MAX_BROWSER_LEVELS + 1):
        level = get_browser_level_definition(index)
        attr_name = f"browser_level_{index}"
        if not level:
            continue

        items = get_browser_level_items(index, context)
        current_value = str(getattr(my_tool, attr_name, "") or "")
        safe_set_enum_property(my_tool, attr_name, items, preferred_value=current_value, fallback_identifier=f"NO_LEVEL{index}")


def update_browser_hierarchy(context, changed_level_index=1):
    if _browser_sync_suspended:
        return
    populate_browser_levels_from_index(context, changed_level_index + 1)
    set_blend_file_to_first_available(context)
    save_recent_browser_state(context)


def update_project_selection(self, context):
    if _browser_sync_suspended:
        return
    load_project_path_settings_to_ui(context)
    populate_browser_levels_from_index(context, 3)
    set_blend_file_to_first_available(context)
    save_recent_browser_state(context)


def load_project_path_settings_to_ui(context, project_name=None):
    scene = context.scene
    settings = getattr(scene, "sf_project_paths", None)
    if settings is None:
        return

    config = get_config_by_project_name(project_name)
    settings.drive = str(config.get("drive", ""))
    settings.prefix = str(config.get("prefix", ""))
    settings.asset_base = str(config.get("asset_base", ""))
    settings.scene_base = str(config.get("scene_base", ""))
    settings.project_json_base = str(config.get("project_json_base", ""))
    settings.output_base = str(config.get("output_base", ""))
    settings.asset_ch_dir = str(config.get("asset_ch_dir", "ch"))
    settings.asset_bg_dir = str(config.get("asset_bg_dir", "bg"))
    settings.asset_prop_dir = str(config.get("asset_prop_dir", "prop"))
    settings.scene_root_dir = str(get_schema_scene_root_path(project_name) or config.get("scene_root_dir", "scenes"))
    settings.ren_dir = str(get_project_ren_dir_name(project_name) or config.get("ren_dir", "ren"))
    settings.cache_dir = str(config.get("cache_dir", "cache"))
    settings.publish_dir = str(config.get("publish_dir", "pub"))
    settings.geometry_root_hint = str(config.get("geometry_root_hint", "Geometry/{asset_name}"))
    browser_levels = get_browser_non_work_levels(project_name)
    settings.browser_level_count = max(1, len(browser_levels) or 1)
    for index in range(1, MAX_BROWSER_LEVELS + 1):
        label = get_browser_level_label(index, project_name) if index <= len(browser_levels) else f"Level {index}"
        setattr(settings, f"browser_level_{index}_label", label)


def save_project_path_settings_from_ui(context, project_name=None):
    scene = context.scene
    settings = getattr(scene, "sf_project_paths", None)
    if settings is None:
        return

    project_name = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    raw_scene_root = normalize_directory_choice(settings.scene_root_dir)
    scene_base_value = normalize_directory_choice(settings.scene_base)
    scene_root_dir_value = settings.scene_root_dir
    if raw_scene_root and "/" in raw_scene_root.strip("/"):
        drive, parts = split_normalized_path(raw_scene_root)
        if parts:
            scene_base_value = join_normalized_path(drive, parts[:-1]) if parts[:-1] else drive
            scene_root_dir_value = parts[-1]

    PROJECT_CONFIG[project_name] = normalize_project_config_entry(project_name, {
        "drive": normalize_directory_choice(settings.drive),
        "prefix": settings.prefix,
        "asset_base": normalize_directory_choice(settings.asset_base),
        "scene_base": scene_base_value,
        "project_json_base": normalize_directory_choice(settings.project_json_base),
        "output_base": normalize_directory_choice(settings.output_base),
        "asset_ch_dir": settings.asset_ch_dir,
        "asset_bg_dir": settings.asset_bg_dir,
        "asset_prop_dir": settings.asset_prop_dir,
        "scene_root_dir": scene_root_dir_value,
        "ren_dir": settings.ren_dir,
        "cache_dir": settings.cache_dir,
        "publish_dir": settings.publish_dir,
        "geometry_root_hint": settings.geometry_root_hint,
    })
    save_project_config_store()
    upsert_schema_from_project_config(project_name, PROJECT_CONFIG[project_name])

    schema_entry = get_project_schema_entry(project_name)
    scene_browser = schema_entry.get("scene_browser", {}) if isinstance(schema_entry, dict) else {}
    existing_levels = scene_browser.get("levels", []) if isinstance(scene_browser, dict) else []
    work_level = None
    for level in existing_levels:
        if isinstance(level, dict) and isinstance(level.get("fixed_options"), list):
            work_level = deepcopy(level)
            break
    if not work_level:
        work_level = {
            "id": "work",
            "label": "Work",
            "parent_level": "cut",
            "fixed_options": list(get_scene_work_dir_names_from_config(PROJECT_CONFIG[project_name])),
            "default": str(PROJECT_CONFIG[project_name].get("ren_dir", "ren") or "ren"),
        }

    label_map = {
        1: settings.browser_level_1_label,
        2: settings.browser_level_2_label,
        3: settings.browser_level_3_label,
        4: settings.browser_level_4_label,
        5: settings.browser_level_5_label,
    }
    non_work_levels = build_schema_non_work_levels(
        settings.scene_root_dir,
        settings.browser_level_count,
        label_map,
    )
    if non_work_levels:
        work_level["parent_level"] = non_work_levels[-1]["id"]
    scene_browser["levels"] = non_work_levels + [work_level]
    scene_browser["file_level_id"] = work_level.get("id", "work")
    scene_browser.setdefault("file_extensions", [".blend"])
    schema_entry["scene_browser"] = scene_browser
    set_project_schema_entry(project_name, schema_entry)
    sync_pipeline_config_from_rrrender(project_name, PROJECT_CONFIG[project_name], scene_browser)
    save_project_schema_store()
    save_project_override_store()
    clear_path_caches()
    populate_browser_levels_from_index(context, 3)


def sync_pipeline_config_from_rrrender(project_name, config, scene_browser=None):
    if not (PIPELINE_SHARED_AVAILABLE and load_pipeline_config and save_pipeline_config and sync_legacy_rrrender_paths_json):
        return

    payload = load_pipeline_config()
    project = get_pipeline_project_entry(project_name, payload) or {"identity": {}, "paths": {}, "assets": {}, "scene_structure": {}, "scene_browser": {}, "cache": {}, "output": {}}

    drive = normalize_directory_choice(config.get("drive", ""))
    asset_base = normalize_directory_choice(config.get("asset_base", ""))
    scene_base = normalize_directory_choice(config.get("scene_base", ""))
    json_base = normalize_directory_choice(config.get("project_json_base", ""))
    output_base = normalize_directory_choice(config.get("output_base", ""))
    scene_root_dir = str(config.get("scene_root_dir", "scenes") or "scenes").strip("/")
    scene_root = join_normalized_path(scene_base, [scene_root_dir]) if scene_base else scene_root_dir

    identity = project.setdefault("identity", {})
    identity["project_id"] = project_name
    identity["project_prefix"] = str(config.get("prefix", project_name) or project_name)

    paths = project.setdefault("paths", {})
    paths["project_root"] = drive
    paths["asset_root"] = asset_base
    paths["scene_root"] = scene_root
    paths["json_root"] = json_base
    paths["output_root"] = output_base
    if json_base:
        paths["render_preset_json"] = join_normalized_path(json_base, ["_json", "renderPreset.json"])
        paths["render_setting_json"] = join_normalized_path(json_base, ["_json", "renderSetting.json"])

    assets = project.setdefault("assets", {})
    categories = assets.setdefault("categories", [])
    category_defaults = [
        ("ch", "Character", str(config.get("asset_ch_dir", "ch") or "ch")),
        ("bg", "Background", str(config.get("asset_bg_dir", "bg") or "bg")),
        ("prop", "Prop", str(config.get("asset_prop_dir", "prop") or "prop")),
    ]
    existing = dict((str(item.get("id", "")), item) for item in categories if isinstance(item, dict))
    rebuilt = []
    for category_id, label, sub_dir in category_defaults:
        item = deepcopy(existing.get(category_id, {}))
        item["id"] = category_id
        item.setdefault("label", label)
        item["root_path"] = join_normalized_path(asset_base, [sub_dir]) if asset_base else sub_dir
        item["geometry_root_hint"] = str(config.get("geometry_root_hint", "geo") or "geo")
        rebuilt.append(item)
    assets["categories"] = rebuilt

    scene_structure = project.setdefault("scene_structure", {})
    scene_structure["cache_relative_path"] = str(config.get("cache_dir", "cache") or "cache")
    scene_structure["identifier_source"] = "filename" if str(config.get("scene_identifier_mode", "") or "").lower() == "filename" else "folder_depth"

    cache_config = project.setdefault("cache", {})
    cache_config["root_mode"] = "relative_to_work"
    cache_config["root_template"] = "{work_path}/" + str(config.get("cache_dir", "cache") or "cache")

    output_config = project.setdefault("output", {})
    if output_base:
        output_config["root_template"] = output_base

    if scene_browser:
        project["scene_browser"] = deepcopy(scene_browser)

    payload.setdefault("projects", {})[project_name] = project
    save_pipeline_config(payload)
    sync_legacy_rrrender_paths_json(payload)


def clear_path_caches():
    try:
        cache["scenes"].clear()
        cache["cuts"].clear()
    except Exception:
        pass


def create_new_project_config(project_name, prefix="", drive=""):
    normalized_name = normalize_project_name(project_name)
    if not normalized_name:
        raise ValueError("Project name is empty.")
    if normalized_name in PROJECT_CONFIG:
        raise ValueError(f"Project already exists: {normalized_name}")

    template = normalize_project_config_entry('BTS', DEFAULT_PROJECT_CONFIG.get('BTS', {}))
    if drive:
        normalized_drive = normalize_directory_choice(drive)
        template["drive"] = normalized_drive
        template["scene_base"] = normalized_drive
        template["project_json_base"] = normalized_drive
        template["output_base"] = normalized_drive
        template["asset_base"] = os.path.join(normalized_drive, "assets").replace("\\", "/")
    if prefix:
        template["prefix"] = str(prefix).strip()

    PROJECT_CONFIG[normalized_name] = template
    PROJECT_NAME_ALIASES[normalized_name.upper()] = normalized_name
    save_project_config_store()
    upsert_schema_from_project_config(normalized_name, template)
    save_project_schema_store()
    save_project_override_store()
    return normalized_name


class SF_ProjectPathSettings(bpy.types.PropertyGroup):
    drive: bpy.props.StringProperty(name="Drive", subtype='DIR_PATH')
    prefix: bpy.props.StringProperty(name="Prefix")
    asset_base: bpy.props.StringProperty(name="Asset Base", subtype='DIR_PATH')
    scene_base: bpy.props.StringProperty(name="Scene Base", subtype='DIR_PATH')
    project_json_base: bpy.props.StringProperty(name="Project Json Base", subtype='DIR_PATH')
    output_base: bpy.props.StringProperty(name="Output Base", subtype='DIR_PATH')
    asset_ch_dir: bpy.props.StringProperty(name="CH", default="ch")
    asset_bg_dir: bpy.props.StringProperty(name="BG", default="bg")
    asset_prop_dir: bpy.props.StringProperty(name="PROP", default="prop")
    scene_root_dir: bpy.props.StringProperty(name="Scene Root", default="scenes")
    ren_dir: bpy.props.StringProperty(name="Ren", default="ren")
    cache_dir: bpy.props.StringProperty(name="Cache", default="cache")
    publish_dir: bpy.props.StringProperty(name="Publish", default="pub")
    geometry_root_hint: bpy.props.StringProperty(name="Geometry Root", default="Geometry/{asset_name}")
    browser_level_count: bpy.props.IntProperty(name="Levels", default=2, min=1, max=5)
    browser_level_1_label: bpy.props.StringProperty(name="Level 1", default="Scene")
    browser_level_2_label: bpy.props.StringProperty(name="Level 2", default="Cut")
    browser_level_3_label: bpy.props.StringProperty(name="Level 3", default="Level 3")
    browser_level_4_label: bpy.props.StringProperty(name="Level 4", default="Level 4")
    browser_level_5_label: bpy.props.StringProperty(name="Level 5", default="Level 5")


class SF_OT_SaveProjectPathSettings(bpy.types.Operator):
    bl_idname = "sf.save_project_path_settings"
    bl_label = "Save Project Paths"
    bl_description = "Save current project's path settings to JSON"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        save_project_path_settings_from_ui(context)
        self.report({'INFO'}, f"Saved project path settings for {get_current_project_name()}")
        return {'FINISHED'}


class SF_OT_ReloadProjectPathSettings(bpy.types.Operator):
    bl_idname = "sf.reload_project_path_settings"
    bl_label = "Reload Project Paths"
    bl_description = "Reload current project's path settings from JSON"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ensure_project_config_loaded(force=True)
        load_project_path_settings_to_ui(context)
        clear_path_caches()
        self.report({'INFO'}, f"Reloaded project path settings for {get_current_project_name()}")
        return {'FINISHED'}


class SF_OT_ResetProjectPathSettings(bpy.types.Operator):
    bl_idname = "sf.reset_project_path_settings"
    bl_label = "Reset Project Paths"
    bl_description = "Reset current project's path settings to legacy defaults"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        project_name = get_current_project_name()
        PROJECT_CONFIG[project_name] = normalize_project_config_entry(project_name, DEFAULT_PROJECT_CONFIG.get(project_name, {}))
        save_project_config_store()
        load_project_path_settings_to_ui(context, project_name)
        clear_path_caches()
        self.report({'INFO'}, f"Reset project path settings for {project_name}")
        return {'FINISHED'}


class MyProjectSettings1(bpy.types.PropertyGroup):
    projects: bpy.props.EnumProperty(
        name="Projects",
        description="Select a project",
        items=get_project_enum_items,
        update=update_project_selection
    )
    
# 씬 목록을 캐시에서 가져오거나, 없으면 로드
def get_cached_scenes():
    scene_path = get_scene_root_path()
    if scene_path in cache["scenes"]:
        return cache["scenes"][scene_path]
    scenes = list_browser_child_dirs(scene_path)
    if not scenes:
        scenes = [("NO_SCENES", "No Scenes", "No scenes available")]

    cache["scenes"][scene_path] = scenes
    return scenes


# 컷 목록을 캐시에서 가져오거나, 없으면 로드
def get_cached_cuts(scene_number):
    cut_path = get_scene_path(scene_number)
    if cut_path in cache["cuts"]:
        return cache["cuts"][cut_path]
    secondary_level = get_schema_secondary_level()
    if not secondary_level:
        cuts = [(scene_number, scene_number, "")] if scene_number else [("NO_CUTS", "No Cuts", "No cuts available")]
    else:
        cuts = list_browser_child_dirs(cut_path)
        if not cuts:
            cuts = [("NO_CUTS", "No Cuts", "No cuts available")]

    cache["cuts"][cut_path] = cuts
    return cuts


def is_valid_folder(name):
    return not (name.startswith('_') or 'omit' in name.lower() or '-' in name)

def get_scene_numbers(self, context):
    scene_path = get_scene_root_path()

    if not os.path.exists(scene_path):
        return [("NO_FILE", "No File", "No file found")]

    items = list_browser_child_dirs(scene_path)
    return items if items else [("NO_SCENES", "No Scenes", "No scenes available")]

def get_cut_numbers(self, context):
    scene_number = context.scene.my_tool.scene_number
    secondary_level = get_schema_secondary_level()
    if not secondary_level:
        return [(scene_number, scene_number, "")] if scene_number else [("NO_CUTS", "No Cuts", "No cuts available")]

    cut_path = get_scene_path(scene_number)

    if not os.path.exists(cut_path):
        return [("NO_FILE", "No File", "No cuts found")]

    items = list_browser_child_dirs(cut_path)
    return items if items else [("NO_CUTS", "No Cuts", "No cuts available")]




def get_blend_files(self, context):
    scene_number = context.scene.my_tool.scene_number
    cut_number = context.scene.my_tool.cut_number
    project_prefix = get_project_prefix()
    valid_extensions = set(get_project_browser_file_extensions())
    files_with_time = []
    for work_dir_name, blend_path in get_scene_work_paths(scene_number, cut_number):
        if not os.path.exists(blend_path):
            continue
        for file in os.listdir(blend_path):
            extension = os.path.splitext(file)[1].lower()
            if extension not in valid_extensions:
                continue
            full_path = os.path.join(blend_path, file)
            modified_time = os.path.getmtime(full_path)
            files_with_time.append((work_dir_name, file, modified_time))

    # 파일을 수정된 시간에 따라 내림차순으로 정렬
    sorted_files = sorted(files_with_time, key=itemgetter(2), reverse=True)
    
    # 파일 이름만 EnumProperty에 넣기
    items = []
    for work_dir_name, file, _ in sorted_files:
        stripped = file
        for token in get_scene_work_dir_names():
            stripped = stripped.replace(f"{project_prefix}_{scene_number}_{cut_number}_{token}_", "")
            stripped = stripped.replace(f"{project_prefix}_{scene_number}_{token}_", "")
        stripped = os.path.splitext(stripped)[0]
        identifier = build_blend_file_identifier(work_dir_name, file)
        work_label = "" if str(work_dir_name or "") in (".", "./", "\\") else f"{work_dir_name} | "
        items.append((identifier, f"{work_label}{stripped}", file))
    return items if items else [("NO_FILES", "No Files", "No files available")]


def get_browser_level_3_items(self, context):
    items = get_browser_level_items(3, context)
    return items if items else [("NO_LEVEL3", "No Items", "No items available")]


def get_browser_level_4_items(self, context):
    items = get_browser_level_items(4, context)
    return items if items else [("NO_LEVEL4", "No Items", "No items available")]


def get_browser_level_5_items(self, context):
    items = get_browser_level_items(5, context)
    return items if items else [("NO_LEVEL5", "No Items", "No items available")]


def find_blend_file_enum_value(scene_number, cut_number, filepath, context):
    target_path = os.path.abspath(filepath)
    items = get_blend_files(getattr(context.scene, "my_tool", None), context)
    for identifier, _label, _desc in items:
        candidate = resolve_selected_blend_filepath(scene_number, cut_number, identifier)
        if candidate and os.path.abspath(candidate) == target_path:
            return identifier
    return ""
    
# Open 버튼에 연결할 함수
def read_blend_file_version(filepath):
    try:
        with open(filepath, "rb") as handle:
            header = handle.read(12)
        if len(header) < 12 or not header.startswith(b"BLENDER"):
            return None
        version_text = header[9:12].decode("ascii", errors="ignore")
        if not version_text.isdigit():
            return None
        return (int(version_text[0]), int(version_text[1:]), 0)
    except Exception:
        return None


def is_blend_file_newer_than_current(filepath):
    file_version = read_blend_file_version(filepath)
    if not file_version:
        return False, None
    current_version = tuple(int(v) for v in bpy.app.version[:3])
    return file_version > current_version, file_version


class OpenFileOperator(bpy.types.Operator):
    bl_idname = "file.open_file"
    bl_label = "Open File"

    @classmethod
    def poll(cls, context):
        return context.scene.my_tool.blend_file != ''

    def execute(self, context):
        global _pending_browser_focus_filepath
        scene_number = context.scene.my_tool.scene_number
        cut_number = context.scene.my_tool.cut_number
        blend_file = context.scene.my_tool.blend_file
        file_path = resolve_selected_blend_filepath(scene_number, cut_number, blend_file)
        if not file_path:
            self.report({'ERROR'}, f"Blend file not found for selection: {blend_file}")
            return {'CANCELLED'}
        extension = os.path.splitext(file_path)[1].lower()
        if extension == ".blend":
            _pending_browser_focus_filepath = file_path
            is_newer, file_version = is_blend_file_newer_than_current(file_path)
            if is_newer and file_version:
                _pending_browser_focus_filepath = ""
                current_label = ".".join(str(v) for v in bpy.app.version[:2])
                file_label = f"{file_version[0]}.{file_version[1]}"
                self.report(
                    {'ERROR'},
                    f"This blend file was saved in Blender {file_label} and cannot be opened in Blender {current_label}."
                )
                return {'CANCELLED'}
            try:
                bpy.ops.wm.open_mainfile(filepath=file_path)
                return {'FINISHED'}
            except RuntimeError as exc:
                _pending_browser_focus_filepath = ""
                self.report({'ERROR'}, f"Failed to open blend file: {exc}")
                return {'CANCELLED'}
        else:
            open_folder(file_path)
            self.report({'INFO'}, f"Opened external scene file: {os.path.basename(file_path)}")
            return {'FINISHED'}

        # 파일 경로에서 씬과 컷 번호 추출
        scene_number, cut_number = extract_scene_cut_from_filename(file_path)
        if scene_number and cut_number:
            context.scene.my_tool.scene_number = scene_number
            context.scene.my_tool.cut_number = cut_number

        return {'FINISHED'}


class AppendSceneOperator(bpy.types.Operator):
    bl_idname = "file.append_scene"
    bl_label = "Append Scene"
    asset_path: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return context.scene.my_tool.blend_file != ''

    def execute(self, context):
        scene_number = context.scene.my_tool.scene_number
        cut_number = context.scene.my_tool.cut_number
        blend_file = context.scene.my_tool.blend_file
        self.asset_path = resolve_selected_blend_filepath(scene_number, cut_number, blend_file)
        if not self.asset_path:
            self.report({'ERROR'}, f"Blend file not found for selection: {blend_file}")
            return {'CANCELLED'}
        # 선택한 어셋 파일 내의 모든 씬을 가져옵니다.
        with bpy.data.libraries.load(self.asset_path, link=False) as (data_from, data_to):
            data_to.scenes = data_from.scenes
        
        return {'FINISHED'}
        
class SF_OT_RefreshSceneAndCutCache(bpy.types.Operator):
    bl_idname = "sf.refresh_scene_and_cut_cache"
    bl_label = "🔁 Refresh Scenes & Cuts"

    def execute(self, context):
        scene_path = get_scene_root_path()
        cache["scenes"].pop(scene_path, None)

        scene_number = context.scene.my_tool.scene_number
        if scene_number:
            cut_path = get_scene_path(scene_number)
            cache["cuts"].pop(cut_path, None)
            self.report({'INFO'}, f"Refreshed cache for scenes and cuts of scene {scene_number}")
        else:
            self.report({'INFO'}, "Scene list refreshed. (No scene selected, so cut not refreshed)")

        return {'FINISHED'}

def update_scene_number(self, context):
    context.scene.sf_scene_number = self.scene_number
    update_browser_hierarchy(context, 1)

def update_cut_number(self, context):
    context.scene.sf_cut_number = self.cut_number
    update_browser_hierarchy(context, 2)


def update_browser_level_3(self, context):
    update_browser_hierarchy(context, 3)


def update_browser_level_4(self, context):
    update_browser_hierarchy(context, 4)


def update_browser_level_5(self, context):
    update_browser_hierarchy(context, 5)

def update_blend_file(self, context):
    if _browser_sync_suspended:
        return
    save_recent_browser_state(context)

class MyProperties(bpy.types.PropertyGroup):
    scene_number: bpy.props.EnumProperty(
        name="Scene",
        description="Choose a Scene Number",
        items=lambda self, context: get_cached_scenes(),
        update=update_scene_number
    )

    cut_number: bpy.props.EnumProperty(
        name="Cut",
        description="Choose a Cut Number",
        items=lambda self, context: get_cached_cuts(context.scene.my_tool.scene_number),
        update=update_cut_number
    )

    browser_level_3: bpy.props.EnumProperty(
        name="Level 3",
        description="Choose a third browser level",
        items=get_browser_level_3_items,
        update=update_browser_level_3
    )

    browser_level_4: bpy.props.EnumProperty(
        name="Level 4",
        description="Choose a fourth browser level",
        items=get_browser_level_4_items,
        update=update_browser_level_4
    )

    browser_level_5: bpy.props.EnumProperty(
        name="Level 5",
        description="Choose a fifth browser level",
        items=get_browser_level_5_items,
        update=update_browser_level_5
    )


    blend_file: bpy.props.EnumProperty(
        name="File",
        description="Choose a Blender File",
        items=get_blend_files,
        update=update_blend_file
    )

    confirm_overwrite: bpy.props.BoolProperty(
        name="Confirm Overwrite",
        description="Confirm before overwriting files",
        default=False
    )
    custom_prefix: bpy.props.StringProperty(
        name="Custom Prefix",
        default="",
        description="사용자 정의 접두사"
    )

    sfpaint_emission_strength: bpy.props.FloatProperty(
        name="Emisstion Strengh",
        description="Set Strength input on SF_Paint* node groups across all materials",
        default=0.2,
        min=0.0,
        soft_max=10.0
    )
    
    sfpaint_mask_int: bpy.props.FloatProperty(
        name="Mask_Int",
        default=1.0,
        min=0.0,
        soft_max=10.0
    )

    sfpaint_brusk_int: bpy.props.FloatProperty(
        name="Brusk_Int",
        default=0.02,
        min=0.0,
        soft_max=10.0
    )

    sfpaint_noise_int: bpy.props.FloatProperty(
        name="Noise Int",
        default=0.02,
        min=0.0,
        soft_max=10.0
    )    


    custom_suffix: bpy.props.StringProperty(name="Custom Suffix", default="")

################################################################
#########################Scene Build Operation##################
################################################################


# -------------------------------------------------------------------
# ✅ [Output Format Compatibility] Blender 4.1 ~ 5.1
# -------------------------------------------------------------------
# Blender 5.0부터 ImageFormatSettings.file_format enum이 media_type에 의해
# 필터링됩니다. 예를 들어 media_type이 VIDEO 상태면 file_format enum에는
# FFMPEG만 남아서, 곧바로 PNG/OPEN_EXR_MULTILAYER를 넣으면 TypeError가 납니다.
# 그래서 모든 Output / File Output Node 포맷 변경은 아래 헬퍼를 통해 처리합니다.

_IMAGE_OUTPUT_FORMATS = {
    'BMP', 'IRIS', 'PNG', 'JPEG', 'JPEG2000', 'TARGA', 'TARGA_RAW',
    'CINEON', 'DPX', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER', 'TIFF', 'WEBP',
}
_VIDEO_OUTPUT_FORMATS = {'FFMPEG', 'AVI_JPEG', 'AVI_RAW'}


def _enum_identifiers(rna_owner, prop_name):
    """RNA enum identifier 리스트를 안전하게 반환."""
    try:
        prop = rna_owner.bl_rna.properties.get(prop_name)
        if not prop:
            return []
        return [item.identifier for item in prop.enum_items]
    except Exception:
        return []


def _set_enum_if_available(rna_owner, prop_name, value, label=""):
    """해당 enum 값이 사용 가능할 때만 설정. 실패하면 False."""
    if not hasattr(rna_owner, prop_name):
        return False

    try:
        available = _enum_identifiers(rna_owner, prop_name)
        if available and value not in available:
            print(f"[OutputCompat][SKIP] {label}{prop_name}='{value}' not in {available}")
            return False
        setattr(rna_owner, prop_name, value)
        return True
    except Exception as e:
        print(f"[OutputCompat][FAIL] {label}{prop_name}='{value}' ({e})")
        return False


def _wanted_media_type_for_file_format(file_format):
    fmt = str(file_format).upper()
    if fmt in _VIDEO_OUTPUT_FORMATS:
        # Blender 빌드에 따라 식별자가 VIDEO 또는 MOVIE일 가능성을 모두 방어.
        return ('VIDEO', 'MOVIE')
    # rrRender의 PNG / EXR / TGA 계열은 모두 IMAGE.
    return ('IMAGE',)


def _set_media_type_for_file_format(format_settings, file_format, label=""):
    """Blender 5.x용 media_type 선세팅. 4.x에서는 media_type이 없어서 자동 패스."""
    if not hasattr(format_settings, "media_type"):
        return True

    available = _enum_identifiers(format_settings, "media_type")
    candidates = _wanted_media_type_for_file_format(file_format)

    for candidate in candidates:
        if not available or candidate in available:
            try:
                format_settings.media_type = candidate
                return True
            except Exception as e:
                print(f"[OutputCompat][WARN] {label}media_type='{candidate}' 실패: {e}")

    print(f"[OutputCompat][WARN] {label}media_type 후보 {candidates} 적용 실패. available={available}")
    return False


def set_output_image_format(format_settings, file_format, color_mode=None, color_depth=None,
                            exr_codec=None, compression=None, label=""):
    """
    Blender 4.1~5.1 공용 Output Format setter.

    사용 대상:
      - scene.render.image_settings
      - CompositorNodeOutputFile.format

    핵심:
      Blender 5.x에서는 file_format 설정 전에 media_type을 IMAGE/VIDEO로 먼저 맞춘다.
    """
    if format_settings is None:
        print(f"[OutputCompat][FAIL] {label}format_settings is None")
        return False

    fmt = str(file_format).upper()
    ok = True

    _set_media_type_for_file_format(format_settings, fmt, label=label)

    try:
        format_settings.file_format = fmt
    except TypeError:
        # media_type이 꼬였거나 예외적인 빌드일 때, 가능한 media_type 전부 돌면서 재시도.
        applied = False
        if hasattr(format_settings, "media_type"):
            for media_type in _enum_identifiers(format_settings, "media_type"):
                try:
                    format_settings.media_type = media_type
                    format_settings.file_format = fmt
                    applied = True
                    break
                except Exception:
                    continue
        if not applied:
            ok = False
            print(f"[OutputCompat][FAIL] {label}file_format='{fmt}' 적용 실패")
    except Exception as e:
        ok = False
        print(f"[OutputCompat][FAIL] {label}file_format='{fmt}' ({e})")

    # file_format 설정 후에 세부 옵션 적용. 포맷별 지원 안 되는 enum은 조용히 스킵.
    if color_mode is not None:
        _set_enum_if_available(format_settings, "color_mode", str(color_mode).upper(), label=label)
    if color_depth is not None:
        _set_enum_if_available(format_settings, "color_depth", str(color_depth), label=label)
    if exr_codec is not None and hasattr(format_settings, "exr_codec"):
        _set_enum_if_available(format_settings, "exr_codec", str(exr_codec).upper(), label=label)
    if compression is not None and hasattr(format_settings, "compression"):
        try:
            format_settings.compression = int(compression)
        except Exception as e:
            print(f"[OutputCompat][WARN] {label}compression='{compression}' 적용 실패: {e}")

    return ok


def set_output_png(format_settings, alpha=False, label=""):
    return set_output_image_format(
        format_settings,
        'PNG',
        color_mode='RGBA' if alpha else 'RGB',
        color_depth='8',
        label=label,
    )


def set_output_exr_multilayer(format_settings, label=""):
    return set_output_image_format(
        format_settings,
        'OPEN_EXR_MULTILAYER',
        color_mode='RGBA',
        color_depth='16',
        exr_codec='PXR24',
        label=label,
    )



# -------------------------------------------------------------------
# ✅ Blender 4.1~5.1 Compositor NodeTree Compatibility
# -------------------------------------------------------------------
def get_scene_compositor_tree(scene=None, create=False, name=None):
    """
    Blender 4.x / 5.x 공용 Compositor NodeTree getter.

    Blender 4.x:
      - scene.use_nodes / scene.node_tree 사용

    Blender 5.x:
      - scene.node_tree 제거됨
      - scene.compositing_node_group 사용
    """
    if scene is None:
        scene = bpy.context.scene

    # Blender 5.0+
    if hasattr(scene, "compositing_node_group"):
        tree = getattr(scene, "compositing_node_group", None)
        if tree is None and create:
            tree_name = name or f"{scene.name}_Compositing"
            try:
                tree = bpy.data.node_groups.new(name=tree_name, type='CompositorNodeTree')
                scene.compositing_node_group = tree
                print(f"[CompositorCompat] Created compositing_node_group: {tree.name}")
            except Exception as e:
                print(f"[CompositorCompat][WARN] compositing_node_group 생성 실패: {e}")
                return None
        return tree

    # Blender 4.x
    if create and hasattr(scene, "use_nodes"):
        try:
            scene.use_nodes = True
        except Exception as e:
            print(f"[CompositorCompat][WARN] scene.use_nodes=True 실패: {e}")

    return getattr(scene, "node_tree", None)


def set_file_output_node_base_path(node, base_path, label=""):
    """File Output 노드 경로를 버전 차이를 감안해 안전하게 설정."""
    if node is None:
        return False

    if hasattr(node, "base_path"):
        try:
            node.base_path = base_path
            return True
        except Exception as e:
            print(f"[CompositorCompat][WARN] {label}base_path 설정 실패: {e}")

    if hasattr(node, "directory"):
        try:
            node.directory = base_path
            return True
        except Exception as e:
            print(f"[CompositorCompat][WARN] {label}directory 설정 실패: {e}")

    node_name = getattr(node, "name", "<unnamed>")
    node_rna = getattr(getattr(node, "bl_rna", None), "identifier", type(node).__name__)
    print(f"[CompositorCompat][WARN] {label}{node_name} ({node_rna}) 에 output path 속성이 없습니다.")
    return False


def set_scene_compositor_enabled(scene=None, enabled=True, create_tree=False):
    """Blender 4.x/5.x 공용 compositor 활성 처리. 5.x에서는 node group 방식만 안전하게 처리."""
    if scene is None:
        scene = bpy.context.scene

    if hasattr(scene, "use_nodes"):
        try:
            scene.use_nodes = bool(enabled)
        except Exception as e:
            print(f"[CompositorCompat][WARN] scene.use_nodes={enabled} 실패: {e}")

    if enabled and (create_tree or hasattr(scene, "compositing_node_group")):
        return get_scene_compositor_tree(scene, create=create_tree)

    return get_scene_compositor_tree(scene, create=False)


def set_nested_property(target_obj, key_path, value):
    """
    점(.)으로 구분된 경로를 타고 들어가서 값을 설정하는 똑똑한 함수
    예: set_nested_property(scene.render, "image_settings.file_format", "OPEN_EXR")
    """
    try:
        # 경로 분해 (예: ['image_settings', 'file_format'])
        path = key_path.split('.')
        current_obj = target_obj
        
        # 마지막 전까지 객체 타고 들어가기
        for p in path[:-1]:
            current_obj = getattr(current_obj, p)
        
        # 마지막 속성 이름
        prop_name = path[-1]
        
        # 속성이 실제로 있는지 확인 후 설정
        if hasattr(current_obj, prop_name):
            # Blender 5.x: ImageFormatSettings.file_format은 media_type 선세팅 필요
            if prop_name == "file_format" and hasattr(current_obj, "file_format"):
                set_output_image_format(current_obj, value, label=f"{key_path}: ")
            else:
                # 데이터 타입 자동 변환 (블렌더가 웬만하면 알아서 처리함)
                setattr(current_obj, prop_name, value)
            # print(f"  [OK] {key_path} = {value}") # 디버깅용
        else:
            print(f"  [SKIP] 존재하지 않는 속성: {prop_name} (in {key_path})")
            
    except Exception as e:
        print(f"  [FAIL] 설정 실패: {key_path} = {value} ({e})")

def load_project_render_settings(context, apply_render_settings=True, apply_view_layer_settings=True):
    scene = context.scene

    json_path = get_project_json_path("renderSetting.json")

    if not json_path:
        print("[WARN] 프로젝트 경로를 찾을 수 없습니다.")
        return False
    
    if not os.path.exists(json_path):
        print(f"[WARN] 렌더 세팅 파일 없음: {json_path}")
        return False

    print(f"[Build] JSON 세팅 로드: {json_path}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] JSON 파싱 에러: {e}")
        return False

    if not apply_render_settings:
        data = dict(data)
        data.pop("view_settings", None)
        data.pop("eevee_settings", None)
        data.pop("render_settings", None)

    # -------------------------------------------------------
    # [핵심] 반복문으로 자동 매핑
    # -------------------------------------------------------
    
    mapping = {
        "view_settings": scene.view_settings,
        "eevee_settings": scene.eevee,
        "render_settings": scene.render,
    }

    for section_name, target_obj in mapping.items():
        if section_name in data:
            for key, value in data[section_name].items():
                if section_name == "eevee_settings" and scene.render.engine != 'BLENDER_EEVEE':
                    continue
                
                # 스마트 설정 함수 호출
                set_nested_property(target_obj, key, value)

    # -------------------------------------------------------
    # 특수 로직들
    # -------------------------------------------------------

    # 1. View Layers (없으면 자동 생성)
    if apply_view_layer_settings and "view_layer_settings" in data:
        for vl_name, is_enabled in data["view_layer_settings"].items():
            vl = scene.view_layers.get(vl_name)
            if not vl:
                vl = scene.view_layers.new(name=vl_name)
            vl.use = is_enabled

    # 2. Compositor Nodes
    if data.get("use_compositor") and "nodes" in data:
        scene.render.use_compositing = False
        set_scene_compositor_enabled(scene, False)
        # tree = scene.node_tree
        
        # for node_data in data["nodes"]:
            # if node_data["type"] == "CompositorNodeRLayers":
                # layer_name = node_data.get("layer_name")
                
                # if layer_name and layer_name not in scene.view_layers:
                    # scene.view_layers.new(name=layer_name)

                # node = None
                # for n in tree.nodes:
                    # if n.type == 'R_LAYERS' and n.layer == layer_name:
                        # node = n
                        # break
                
                # if not node:
                    # node = tree.nodes.new('CompositorNodeRLayers')
                    # node.layer = layer_name
                
                # if "location" in node_data:
                    # node.location = node_data["location"]
                # if "mute" in node_data:
                    # node.mute = node_data["mute"]

    # 3. 기타 (🔥 여기서 200%로 튀던 버그 완벽 차단 🔥)
    if "resolution_scale" in data:
        # 기존: scene.render.resolution_percentage = int(data["resolution_scale"] * 100)
        scene.render.resolution_percentage = 100
    else:
        scene.render.resolution_percentage = 100

    if data.get("linkClass", False):
        pass

    print("[Build] 렌더 세팅 적용 완료.")
    return True


def get_base_filepath(scene):
    """지정된 씬 번호와 컷 번호를 사용하여 기본 파일 경로를 반환합니다."""
    my_tool = scene.my_tool
    scene_number = my_tool.scene_number
    cut_number = my_tool.cut_number
    base_path = get_project_output_path(scene_number, cut_number)
    default_version = "v001"

    # 해당 경로에 있는 모든 버전 넘버 찾기
    if os.path.exists(base_path):
        versions = [int(re.search(r"v(\d{3})", item).group(1)) for item in os.listdir(base_path) if re.search(r"v(\d{3})", item)]
        
        # 가장 높은 버전 넘버 찾기
        if versions:
            latest_version = max(versions)
            default_version = f"v{str(latest_version + 1).zfill(3)}"

    # os.path.join을 사용하여 original_path를 구성합니다.
    original_path = os.path.join(base_path, default_version, f"{scene_number}_{cut_number}_")

    # os.path.join을 사용하여 new_path를 구성합니다.
    new_path = os.path.join(base_path, default_version)

    return original_path, new_path, default_version


def find_collection_in_view_layer(collection_name, view_layer):
    """
    뷰 레이어에서 지정된 이름의 컬렉션을 찾아 반환합니다.
    """
    for layer_coll in view_layer.layer_collection.children:
        if layer_coll.collection.name == collection_name:
            return layer_coll

def apply_collection_properties_recursive(layer_collection, property_name, property_value):
    """
    재귀적으로 컬렉션과 하위 컬렉션에 속성을 적용합니다.
    """
    setattr(layer_collection, property_name, property_value)
    for child in layer_collection.children:
        apply_collection_properties_recursive(child, property_name, property_value)

def set_layer_collection_properties(layer_collection, holdout=False, indirect_only=False, exclude=False):
    layer_collection.holdout = holdout
    layer_collection.indirect_only = indirect_only
    layer_collection.exclude = exclude

def toggle_collection_properties(collection, property_name):
    """컬렉션의 속성을 토글합니다."""
    setattr(collection, property_name, not getattr(collection, property_name))

def set_and_restore_view_layer_properties(context, scene, view_layer, collection, properties):
    """
    뷰 레이어와 컬렉션의 속성을 설정하고 복원합니다.

    :param context: Blender 컨텍스트
    :param scene: 현재 씬
    :param view_layer: 대상 뷰 레이어 이름
    :param collection: 대상 컬렉션 이름
    :param properties: {"exclude": bool, "holdout": bool, "indirect_only": bool} 형태의 딕셔너리
    """
    # 1. 현재 뷰 레이어 저장
    current_view_layer = context.window.view_layer

    # 2. 대상 뷰 레이어로 변경
    target_view_layer_obj = scene.view_layers[view_layer]
    # print(f"Changing view layer to: {view_layer}")
    context.window.view_layer = target_view_layer_obj

    # 3. 현재 엑티브된 뷰 레이어 출력
    # print(f"Current active view layer: {context.window.view_layer.name}")

    # 4. 컬렉션 속성 설정 전 디버깅 메시지
    # print(f"Before applying properties - Target collection: {collection}")

    # 5. 컬렉션 속성 설정
    target_col = find_collection_in_view_layer(collection, target_view_layer_obj)
    if target_col:
        # 속성 설정
        for prop_name, prop_value in properties.items():
            setattr(target_col, prop_name, prop_value)
    else:
        print(f"Collection not found: {collection}")

    # 6. 컬렉션 속성 설정 후 디버깅 메시지
    # print(f"After applying properties - Target collection: {collection}")

    # 7. 원래의 뷰 레이어로 복원
    # print(f"Restoring view layer to: {current_view_layer.name}")
    context.window.view_layer = current_view_layer
    
def get_project_settings_path():
    return get_project_json_path("renderSetting.json")

def load_settings():
    settings_path = get_project_settings_path()
    try:
        with open(settings_path, 'r', encoding='utf-8') as file: # encoding 추가 권장
            return json.load(file)
    except FileNotFoundError:
        # self.report는 Operator 클래스 안에서만 쓸 수 있습니다.
        # 여기서는 콘솔에 출력하는 것으로 대체합니다.
        print(f"[ERROR] 설정 파일을 찾을 수 없습니다: {settings_path}")
        return {}
    except json.JSONDecodeError:
        print(f"[ERROR] 설정 파일 형식이 잘못되었습니다: {settings_path}")
        return {}
    except Exception as e:
        print(f"[ERROR] 설정 로드 중 알 수 없는 오류: {e}")
        return {}

def _disable_default_view_layer(scene):
    """?? ViewLayer? ???? ???? ??"""
    vl = scene.view_layers.get("ViewLayer")
    if vl:
        vl.use = False
        print("[SF] ?? ViewLayer ?? OFF ??")
    else:
        print("[SF][WARN] ?? ViewLayer? ?? ? ????.")


def setup_render_view_layers(context, scene):
    if "ch_vl" not in scene.view_layers:
        scene.view_layers.new(name="ch_vl")
    set_and_restore_view_layer_properties(context, scene, "ch_vl", "ch_col", {"exclude": False, "holdout": False, "indirect_only": False})
    set_and_restore_view_layer_properties(context, scene, "ch_vl", "ch_blocker_col", {"exclude": False, "holdout": True, "indirect_only": False})
    set_and_restore_view_layer_properties(context, scene, "ch_vl", "bg_col", {"exclude": True, "holdout": True, "indirect_only": True})
    set_and_restore_view_layer_properties(context, scene, "ch_vl", "prop_col", {"exclude": True, "holdout": True, "indirect_only": True})

    if "bg_vl" not in scene.view_layers:
        scene.view_layers.new(name="bg_vl")
    set_and_restore_view_layer_properties(context, scene, "bg_vl", "ch_col", {"exclude": True, "holdout": False, "indirect_only": True})
    set_and_restore_view_layer_properties(context, scene, "bg_vl", "ch_blocker_col", {"exclude": True, "holdout": False, "indirect_only": False})
    set_and_restore_view_layer_properties(context, scene, "bg_vl", "bg_col", {"exclude": False, "holdout": False, "indirect_only": False})
    set_and_restore_view_layer_properties(context, scene, "bg_vl", "prop_col", {"exclude": False, "holdout": False, "indirect_only": False})

    if "lightmask_vl" not in scene.view_layers:
        scene.view_layers.new(name="lightmask_vl")
    set_and_restore_view_layer_properties(context, scene, "lightmask_vl", "lightmask_col", {"exclude": False, "holdout": False, "indirect_only": False})
    set_and_restore_view_layer_properties(context, scene, "lightmask_vl", "ch_col", {"exclude": True, "holdout": True, "indirect_only": True})
    set_and_restore_view_layer_properties(context, scene, "lightmask_vl", "ch_blocker_col", {"exclude": True, "holdout": True, "indirect_only": True})
    set_and_restore_view_layer_properties(context, scene, "lightmask_vl", "bg_col", {"exclude": True, "holdout": True, "indirect_only": True})
    set_and_restore_view_layer_properties(context, scene, "lightmask_vl", "prop_col", {"exclude": True, "holdout": True, "indirect_only": True})

    if "ViewLayer" in scene.view_layers:
        bpy.context.window.view_layer = bpy.context.scene.view_layers["ViewLayer"]


def apply_view_layer_render_pass_settings(scene):
    if "ViewLayer" in scene.view_layers:
        scene.view_layers["ViewLayer"].use_pass_cryptomatte_material = True
        scene.view_layers["ViewLayer"].use_pass_cryptomatte_object = True
        scene.view_layers["ViewLayer"].use_pass_z = True

    if "ch_vl" in scene.view_layers:
        scene.view_layers["ch_vl"].use_pass_cryptomatte_material = True
        scene.view_layers["ch_vl"].use_pass_cryptomatte_asset = True
        scene.view_layers["ch_vl"].use_pass_cryptomatte_object = True
        scene.view_layers["ch_vl"].use_pass_z = True

    if "bg_vl" in scene.view_layers:
        scene.view_layers["bg_vl"].use_pass_cryptomatte_material = True
        scene.view_layers["bg_vl"].use_pass_cryptomatte_object = True
        scene.view_layers["bg_vl"].use_pass_z = True

    if "lightmask_vl" in scene.view_layers:
        scene.view_layers["lightmask_vl"].use_pass_cryptomatte_material = False
        scene.view_layers["lightmask_vl"].use_pass_z = True

    _disable_default_view_layer(scene)


def _sync_build_scene_all_flags(operator, context):
    value = bool(getattr(operator, "toggle_all_build", False))
    operator.apply_scene_settings = value
    operator.apply_render_settings = value
    operator.apply_view_layer_settings = value
    operator.apply_render_pass_settings = value


class SF_OT_ViewLayerSetupOperator(bpy.types.Operator):
    """? ??? ?? ? ??"""
    bl_idname = "sf.view_layer_setup"
    bl_label = "View Layer Setup"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        setup_render_view_layers(context, scene)
        apply_view_layer_render_pass_settings(scene)
        self.report({'INFO'}, "View layers created and configured.")
        return {'FINISHED'}


class SF_OT_BuildSceneOperator(bpy.types.Operator):
    bl_idname = "sf.build_scene_operator"
    bl_label = "Build Scene"

    toggle_all_build: bpy.props.BoolProperty(name="ALL", default=False, update=_sync_build_scene_all_flags)
    apply_scene_settings: bpy.props.BoolProperty(name="Scene Settings", default=True)
    apply_render_settings: bpy.props.BoolProperty(name="Render Settings", default=True)
    apply_view_layer_settings: bpy.props.BoolProperty(name="ViewLayer Settings", default=False)
    apply_render_pass_settings: bpy.props.BoolProperty(name="Render Pass Settings", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        flow.prop(self, "toggle_all_build")
        flow.prop(self, "apply_scene_settings")
        flow.prop(self, "apply_render_settings")
        flow.prop(self, "apply_view_layer_settings")
        flow.prop(self, "apply_render_pass_settings")

    def execute(self, context):
        if not any([
            self.apply_scene_settings,
            self.apply_render_settings,
            self.apply_view_layer_settings,
            self.apply_render_pass_settings,
        ]):
            self.report({'WARNING'}, "No Build Scene options selected.")
            return {'CANCELLED'}

        if self.apply_scene_settings:
            self.setup_scene_structure(context)

        settings = None
        if self.apply_render_settings:
            settings = self.load_settings()
            if settings:
                self.apply_settings(settings, apply_render_settings=True, apply_view_layer_settings=False)
            else:
                return {'CANCELLED'}
            set_output_exr_multilayer(context.scene.render.image_settings, label="Scene Build: ")
            load_project_render_settings(context, apply_render_settings=True, apply_view_layer_settings=False)
            context.scene.render.resolution_percentage = 100

        if self.apply_view_layer_settings:
            setup_render_view_layers(context, context.scene)
            load_project_render_settings(context, apply_render_settings=False, apply_view_layer_settings=True)

        if self.apply_render_pass_settings:
            apply_view_layer_render_pass_settings(context.scene)

        self.report({'INFO'}, "Scene Build Complete")
        return {'FINISHED'}

    def setup_scene_structure(self, context):
        my_tool = context.scene.my_tool
        scene = context.scene
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        project_prefix = get_project_prefix()
        project_name = get_current_project_name()
        scene.name = f"{project_prefix}_{scene_number}_{cut_number}"

        if "Collection" in bpy.data.collections:
            for col in list(bpy.data.collections["Collection"].children):
                bpy.data.collections.remove(col)
            bpy.data.collections.remove(bpy.data.collections["Collection"])

        bpy.ops.sf.import_scene_camera()

        categories = ["ch", "ch_blocker", "prop", "bg", "lightmask"]
        for category in categories:
            category_name = f"{category}_col"
            if category_name not in scene.collection.children:
                new_col = bpy.data.collections.new(category_name)
                scene.collection.children.link(new_col)

        if context.space_data and context.space_data.type == 'VIEW_3D':
            context.space_data.shading.show_backface_culling = True
        else:
            print("This operation is only valid in the 3D View.")

        set_scene_compositor_enabled(context.scene, True, create_tree=False)
        self.enable_outliner_restrict_columns()

        get_base_filepath(scene)
        bpy.ops.sf.generate_operator()
        bpy.ops.sf.version_operator(increment=-999)
        self.apply_scene_resolution(scene, project_prefix, scene_number, cut_number)

    def enable_outliner_restrict_columns(self):
        try:
            outliner_area = next(a for a in bpy.context.screen.areas if a.type == "OUTLINER")
            space = outliner_area.spaces
            outliner_attrs = [
                "show_restrict_column_enable",
                "show_restrict_column_select",
                "show_restrict_column_hide",
                "show_restrict_column_viewport",
                "show_restrict_column_render",
                "show_restrict_column_holdout",
                "show_restrict_column_indirect_only",
            ]
            for attr in outliner_attrs:
                if hasattr(space, attr):
                    setattr(space, attr, True)
        except StopIteration:
            pass

    def apply_scene_resolution(self, scene, project_prefix, scene_number, cut_number):
        cache_context = resolve_cache_context(scene_number, cut_number, bpy.context, get_current_project_name())
        scene_token = cache_context["scene_token"] or scene_number
        cut_token = cache_context["cut_token"] or cut_number
        json_file_name = f"{project_prefix}_{scene_token}_{cut_token}_camera_data.json"
        full_json_path = os.path.join(cache_context["cache_dir"], json_file_name)

        camera_data = {}
        if os.path.exists(full_json_path):
            with open(full_json_path, 'r') as json_file:
                camera_data = json.load(json_file)

        json_w = camera_data.get('resolutionX')
        json_h = camera_data.get('resolutionY')

        if json_w and json_h:
            if json_w < 2500:
                final_w = int(json_w * 2)
                final_h = int(json_h * 2)
                print(f"[INFO] 1/2 ??? ??? ???. ??? 2? ????: {final_w}x{final_h}")
            else:
                final_w = int(json_w)
                final_h = int(json_h)
        else:
            if project_prefix == "DSC":
                final_w, final_h = 4096, 1716
            elif project_prefix == "ttm":
                final_w, final_h = 3840, 1634
            else:
                final_w, final_h = 1920, 1080
            print(f"[WARN] JSON ??? ??? ??. ???? ?? ??? ?? ??: {final_w}x{final_h}")

        if final_h % 2 != 0:
            final_h += 1
        if final_w % 2 != 0:
            final_w += 1

        scene.render.resolution_x = final_w
        scene.render.resolution_y = final_h

    def get_project_settings_path(self):
        return get_project_json_path("renderSetting.json")

    def load_settings(self):
        settings_path = self.get_project_settings_path()
        try:
            with open(settings_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            self.report({'WARNING'}, f"renderSetting.json 없음, 기본 설정으로 진행합니다: {settings_path}")
            return {}
        except json.JSONDecodeError:
            self.report({'WARNING'}, f"renderSetting.json 형식이 잘못되어 기본 설정으로 진행합니다: {settings_path}")
            return {}

    def clear_all_nodes(self, node_tree):
        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

    def add_render_layer_node(self, node_tree, layer_name, location):
        render_layer_node = node_tree.nodes.new(type='CompositorNodeRLayers')
        render_layer_node.layer = layer_name
        render_layer_node.location = location

    def apply_settings(self, settings, apply_render_settings=True, apply_view_layer_settings=True):
        scene = bpy.context.scene
        eevee = scene.eevee
        cycles = scene.cycles
        render = scene.render

        if apply_render_settings:
            render_settings = settings.get("render_settings", {})
            for setting, value in render_settings.items():
                try:
                    set_nested_property(render, setting, value)
                except (AttributeError, TypeError, ValueError) as e:
                    print(f"Render ?? ?? ? ?? ??: {setting} = {value} - {e}")
                    continue

        if apply_view_layer_settings:
            view_layer_settings = settings.get("view_layer_settings", {})
            for layer_name, use in view_layer_settings.items():
                if layer_name in scene.view_layers:
                    scene.view_layers[layer_name].use = use
                else:
                    print(f"? ??? '{layer_name}'? ?? ? ????.")

        scene.unit_settings.length_unit = 'CENTIMETERS'

        if apply_render_settings:
            eevee_settings = settings.get("eevee_settings", {})
            for setting, value in eevee_settings.items():
                try:
                    setattr(eevee, setting, value)
                except (AttributeError, TypeError, ValueError):
                    continue

            cycles_settings = settings.get("cycles_settings", {})
            for setting, value in cycles_settings.items():
                try:
                    setattr(cycles, setting, value)
                except (AttributeError, TypeError, ValueError):
                    continue

            try:
                cycles.device = 'GPU'
                cycles.preview_adaptive_threshold = 1
                cycles.preview_samples = 16
                cycles.adaptive_threshold = 0.5
                cycles.samples = 30
                cycles.use_preview_denoising = True
                cycles.preview_denoiser = 'OPTIX'
                cycles.denoiser = 'OPTIX'
                cycles.use_denoising = True
                cycles.sampling_pattern = 'BLUE_NOISE'
                cycles.transparent_max_bounces = 50
                cycles.volume_bounces = 1
                cycles.transmission_bounces = 8
                cycles.diffuse_bounces = 1
                cycles.glossy_bounces = 5
                cycles.sample_clamp_direct = 0
                cycles.sample_clamp_indirect = 1
                cycles.texture_limit = '1024'
                cycles.texture_limit_render = '2048'
                cycles.caustics_reflective = False
                cycles.caustics_refractive = False
                cycles.use_fast_gi = True
                cycles.fast_gi_method = 'REPLACE'

                if scene.world and scene.world.light_settings:
                    scene.world.light_settings.ao_factor = 0
                    scene.world.light_settings.distance = 0.1

                render.use_simplify = True
                render.simplify_subdivision_render = 2
                render.simplify_subdivision = 0
                render.film_transparent = True
            except (AttributeError, TypeError, ValueError) as e:
                print(f"Cycles ?? ?? ?? ? ?? ??: {e}")

            engine = scene.render.engine
            if engine in {"BLENDER_EEVEE_GOO", "BLENDER_WORKBENCH_GOO"}:
                scene.view_settings.view_transform = "Standard"
            else:
                try:
                    parts = scene.name.split("_")
                    sn = int(parts[1]) if len(parts) > 1 else int(getattr(bpy.context.scene.my_tool, "scene_number", 0))
                except Exception:
                    sn = int(getattr(bpy.context.scene.my_tool, "scene_number", 0))

                if sn == 10:
                    scene.view_settings.view_transform = "Filmic"
                elif sn == 20:
                    scene.view_settings.view_transform = "Standard"
                elif sn >= 30:
                    if "Khronos PBR Neutral" in bpy.context.scene.display_settings.display_device or True:
                        try:
                            scene.view_settings.view_transform = "Khronos PBR Neutral"
                        except TypeError:
                            scene.view_settings.view_transform = "Standard"

################################################################
#########################Scnene Check ##########################
################################################################
# [cleanup] duplicate update/get_scene helpers removed.

class SF_OT_GenerateOperator(bpy.types.Operator):
    """Cache 폴더에서 USD를 읽어와 어셋 리스트를 생성"""
    bl_idname = "sf.generate_operator"
    bl_label = "Generate from Cache"

    def execute(self, context):
        scene = context.scene
        project_name = get_current_project_name()
        project_prefix = get_project_prefix(project_name)
        
        # 1. 씬/컷 번호 가져오기
        scene_number = scene.my_tool.scene_number
        cut_number = scene.my_tool.cut_number

        # 2. 프로젝트별 올바른 경로 가져오기 (이 부분이 핵심 수정 사항)
        # 기존: get_usd_path()가 S드라이브를 강제하던 문제 해결
        base_path = get_project_paths(project_name)  # 예: "T:\" for THE_TRAP
        if not base_path:
            self.report({'ERROR'}, "Project Path를 찾을 수 없습니다. Project 설정을 확인하세요.")
            return {'CANCELLED'}

        # 3. 실제 캐시 디렉토리 구성
        # 경로: T:\scenes\0010\0010\ren\cache
        cache_dir = resolve_cache_context(scene_number, cut_number, context, project_name)["cache_dir"]

        if not os.path.exists(cache_dir):
            self.report({'WARNING'}, f"Cache 폴더가 없습니다: {cache_dir}")
            # 폴더가 없으면 리스트를 비우고 종료
            scene.sf_file_categories.clear()
            return {'CANCELLED'}

        found_assets = {}

        # 4. 파일 스캔 시작
        try:
            files = os.listdir(cache_dir)
        except Exception as e:
            self.report({'ERROR'}, f"폴더 읽기 실패: {e}")
            return {'CANCELLED'}

        for file in files:
            # 확장자가 .usd 인지 확인
            if not file.endswith(".usd"):
                continue
                
            # 파일명 분해: prefix_scene_cut_category_assetname.usd
            # 예: ttm_0010_0010_ch_hero.usd
            parts = file.split('_')
            
            # 최소한의 길이 체크 (prefix, scene, cut, category, name... 5개 이상)
            # 그리고 현재 프로젝트 접두사(ttm 등)와 일치하는지 확인
            if len(parts) >= 5 and parts[0] == project_prefix:
                
                # 카테고리 (ch, bg, prop 등) - 4번째 요소 (인덱스 3)
                category_name = parts[3]

                # 어셋 이름 추출 (chage_1 등 언더바 포함 이름 대응)
                asset_name = '_'.join(parts[4:]).replace('.usd', '')

                # 딕셔너리에 수집
                if category_name not in found_assets:
                    found_assets[category_name] = []

                if asset_name not in found_assets[category_name]:
                    found_assets[category_name].append(asset_name)

        # 5. UI 리스트 갱신
        scene.sf_file_categories.clear()
        
        # 카테고리 이름순 정렬하여 UI 생성
        for category_name in sorted(found_assets.keys()):
            category = scene.sf_file_categories.add()
            category.name = category_name
            
            # 어셋 이름순 정렬
            for item_name in sorted(found_assets[category_name]):
                new_item = category.items.add()
                new_item.name = item_name
                new_item.is_selected = False

        total_count = sum(len(v) for v in found_assets.values())
        
        if total_count == 0:
            self.report({'WARNING'}, f"폴더는 찾았으나 매칭되는 USD 파일이 없습니다.\n경로: {cache_dir}\n접두사: {project_prefix}")
        else:
            self.report({'INFO'}, f"총 {total_count}개 어셋 로드됨 (Path: {base_path})")
            
        return {'FINISHED'}


bpy.types.Scene.sf_scene_number = bpy.props.StringProperty(
    name="Scene Number",
    default=""
)

bpy.types.Scene.sf_cut_number = bpy.props.StringProperty(
    name="Cut Number",
    default=""
)



        
################################################################
#########################Link Operation#########################
################################################################

class SF_OT_LinkSelectedOperator(bpy.types.Operator):
    bl_idname = "sf.link_selected_operator"
    bl_label = "Link Selected"

    def execute(self, context):
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        bpy.context.window.view_layer = bpy.context.scene.view_layers["ViewLayer"]
        selected_assets = [item.name for category in context.scene.sf_file_categories for item in category.items if item.is_selected]
        for asset_name in selected_assets:
            self.link_asset(asset_name, context, scene_number, cut_number)

        return {'FINISHED'}

    def link_asset(self, asset_name, context, scene_number, cut_number):
        cache_file_path = self.get_cache_file_path(asset_name, scene_number, cut_number, context)

        # USD 파일 임포트 및 생성된 오브젝트 삭제
        self.import_and_remove_usd(cache_file_path)

        # 어셋의 컬렉션 내의 모든 메쉬에 대해 작업 수행
        asset_col = bpy.data.collections.get(f"{asset_name}_col")
        if asset_col:
            category_name = self.get_category_name(asset_name)
            for obj in asset_col.objects:
                if obj.type == 'MESH':
                    self.apply_cache_to_mesh(obj, asset_name, scene_number, cut_number, category_name)

    def get_cache_file_path(self, asset_name, scene_number, cut_number, context):
        category_name = self.get_category_name(asset_name)
        project_name = get_current_project_name()
        return get_usd_path(scene_number, cut_number, asset_name, project_name, category_name)
        project_prefix = get_project_prefix()  # 현재 프로젝트의 식별자를 얻습니다.
        cache_file_format = f"{project_prefix}_{scene_number}_{cut_number}_{category_name}_{asset_name}.usd"

        return os.path.join(get_cache_path(scene_number, cut_number), cache_file_format)


    def import_and_remove_usd(self, file_path):
        # USD 파일 임포트
        safe_usd_import(filepath=file_path, relative_path=True, import_meshes=False, import_subdiv=False, set_frame_range=False)
        # 임포트된 모든 객체를 확인
        imported_objects = bpy.context.selected_objects

        # 메시 캐시가 아닌 객체들을 식별하여 삭제
        for obj in imported_objects:
            if not self.is_mesh_cache_object(obj):
                bpy.data.objects.remove(obj, do_unlink=True)

    def is_mesh_cache_object(self, obj):
        # 객체가 메시 캐시를 포함하는지 확인
        for mod in obj.modifiers:
            if mod.type == 'MESH_SEQUENCE_CACHE':
                return True
        return False

    def find_full_object_path(self, obj):
        path = obj.name.split('.')[0]
        current_obj = obj

        while current_obj.parent:
            current_obj = current_obj.parent
            # 모든 이름에서 '.001', '.002' 등을 제거
            current_obj_name = current_obj.name.split('.')[0]
            path = f"{current_obj_name}/{path}"

        return f"/{path}"



    def apply_cache_to_mesh(self, obj, asset_name, scene_number, cut_number, category_name):
        prefix = get_project_prefix()
        project = bpy.context.scene.my_project_settings.projects

        usd_filename = f"{prefix}_{scene_number}_{cut_number}_{category_name}_{asset_name}.usd"
        usd_path = get_usd_path(scene_number, cut_number, asset_name, project, category_name)

        # 오브젝트에 기존 MeshSequenceCache 모디파이어만 갱신
        msc = None
        for mod in obj.modifiers:
            if mod.type == 'MESH_SEQUENCE_CACHE':
                msc = mod
                break

        if not msc:
            print(f"[SKIP] {obj.name}: MeshSequenceCache 모디파이어가 없어 경로만 갱신하지 못함")
            return

        if not msc.cache_file:
            print(f"[SKIP] {obj.name}: 기존 cache_file 데이터블록이 없어 경로만 갱신하지 못함")
            return

        msc.cache_file.name = usd_filename
        msc.cache_file.filepath = usd_path
        msc.read_data = {'VERT', 'UV', 'COLOR'}


        

        
    def get_category_name(self, asset_name):
        # 동적으로 이름 목록을 가져오기
        character_names = get_character_names()
        bg_names = get_bg_names()
        prop_names = get_prop_names()

        # 기존 카테고리 결정 로직
        if asset_name in character_names:
            return "ch"
        elif asset_name in bg_names:
            return "bg"
        elif asset_name in prop_names:
            return "prop"
        else:
            return "prop"





# 캐시 파일 링킹에 사용되는 공통 코드
def link_cache_files(context, scene_number, cut_number, selected_only=False):
    scene = context.scene
    project_prefix = get_project_prefix()  # 현재 프로젝트의 식별자를 얻습니다.
    cache_file_format = f"//cache\\{project_prefix}_{{}}_{{}}_"  # 예: 프로젝트 식별자_0010_0010_
    scene_number = my_tool.scene_number
    cut_number = my_tool.cut_number

    for category in context.scene.sf_file_categories:
        for item in category.items:
            if item.is_selected or not selected_only:
                cache_file_name = f"{item.name}.usd"
                cache_file_path = cache_file_format.format(scene_number, cut_number) + cache_file_name

                if os.path.exists(cache_file_path):
                    # 캐시 파일이 존재하는 경우, 파일을 연결합니다.
                    bpy.data.cache_files[cache_file_name].filepath = cache_file_path
                else:
                    context.report({'WARNING'}, f"Cache file not found: {cache_file_name}")
                    
class SF_OT_LinkCharacterLights1(bpy.types.Operator):
    bl_idname = "object.sf_link_character_lights1"
    bl_label = "Link Character Lights"
    bl_options = {'REGISTER', 'UNDO'}                    

    def execute(self, context):
        filepath1 = bpy.context.blend_data.filepath
        asset_name = os.path.splitext(os.path.basename(filepath1))[0].split("_")[0]
        target_collection_name = f"{asset_name}_light_col"
        
        # 지정된 이름을 가진 컬렉션을 찾습니다.
        target_collection = bpy.data.collections.get(target_collection_name)
        
        if target_collection:
           
            # 컬렉션 내의 모든 라이트 오브젝트를 찾아 라이트 그룹을 적용합니다.
            for obj in target_collection.objects:
                
                if obj.type == 'LIGHT':
                    
                    # 라이트의 라이트 그룹 설정을 조정합니다.
                    obj.data.light_groups.use_default = False  # 기본 라이트 그룹 사용 비활성화
                    
                    # 기존의 모든 라이트 그룹을 삭제합니다.
                    obj.data.light_groups.groups.clear()
                    
                    # 새로운 라이트 그룹을 추가합니다.
                    new_group = obj.data.light_groups.groups.add()
                    new_group.name = f"{asset_name}_lgt"  # 라이트 그룹 이름 변경
                else:
                    print(f"오브젝트 '{obj.name}'는 라이트가 아닙니다.")
        else:
            print(f"컬렉션 '{target_collection_name}'를 찾을 수 없습니다.")
            
        return {'FINISHED'}
        
class SF_OT_LinkAllOperator(bpy.types.Operator):
    bl_idname = "sf.link_all_operator"
    bl_label = "Link All"

    def execute(self, context):
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number

        link_cache_files(context, scene_number, cut_number, selected_only=False)
        return {'FINISHED'}

################################################################
#########################Import Operation#######################
################################################################
       
       
## 이 스크립트는 씬에 있는 모든 메터리얼의 이름에서 네임스페이스와 서피스를 제거한 후 임시 메모리에 저장합니다.
## USD로 불러온 메터리얼은 네임스페이스를 떼고, MIA_를 MA_로 변환합니다.
## USD메터리얼을 씬 안의 메터리얼과 매칭해 같은 이름의 메터리얼로 교체합니다.
## 다시말해 USD로 불러온 메터리얼을 씬의 메터리얼로 교체하는 스크립트 입니다.

def replace_usd_materials_with_existing(asset_name: str):
    """선택된 오브젝트들 중 MESH에 대해 기존 material로 교체"""

    for obj in bpy.context.selected_objects:
        if obj.type != 'MESH':
            continue

        for i, slot in enumerate(obj.material_slots):
            mat = slot.material
            if not mat:
                continue

            mat_name = mat.name.replace("MIA_", "MI_").replace(":", "_").replace(".", "_")
            existing_mat = bpy.data.materials.get(mat_name)

            if existing_mat and existing_mat != mat:
                print(f"[MaterialSwitch] {obj.name} : {mat.name} → {existing_mat.name}")
                obj.material_slots[i].material = existing_mat

def sanitize_material_name(raw_name):
    """
    MIA/네임스페이스/버전 등 불필요한 부분 제거하고 MI_ 접두어로 정제된 메터리얼 이름 반환
    예: 'FenceRoadE01:MIA_FenceRoadE1.001' → 'MI_FenceRoadE1'
    """
    name = raw_name

    if 'MIA_' in name:
        name = 'MIA_' + name.split('MIA_')[-1]
    name = name.replace("MIA_", "MI_")

    if ':' in name:
        name = name.split(':')[-1]
    if '.' in name:
        name = '.'.join(name.split('.')[:-1])

    return name


def apply_matching_materials(obj):
    materials = bpy.data.materials
    non_matching_materials = []

    # 씬 내 메터리얼들을 정제된 이름으로 맵핑
    processed_materials = {}
    for mat in materials:
        processed_name = sanitize_material_name(mat.name)
        processed_materials[processed_name] = mat

    for slot in obj.material_slots:
        sanitized_name = sanitize_material_name(slot.name)

        if sanitized_name in processed_materials:
            slot.material = processed_materials[sanitized_name]
        else:
            if slot.material is not None:
                old_name = slot.material.name
                try:
                    slot.material.name = sanitized_name
                    print(f"[Material Rename] {old_name} → {sanitized_name}")
                except Exception as e:
                    print(f"[Error] Failed to rename {old_name} → {sanitized_name}: {e}")
            else:
                print(f"[Warning] No material in slot '{slot.name}' (object: {obj.name})")

            non_matching_materials.append(sanitized_name)

    if non_matching_materials:
        print("No matching materials found for:")
        for mat_name in non_matching_materials:
            print(f"- {mat_name}")

            
            
def add_render_layer_node(tree, layer_name, location, mute=False):
    # 현재 활성 씬을 사용
    current_scene = bpy.context.scene
    base_path = get_project_paths()
    render_layer_node = None
    for node in tree.nodes:
        if isinstance(node, bpy.types.CompositorNodeRLayers) and node.layer == layer_name:
            render_layer_node = node
            break
    
    if not render_layer_node:
        render_layer_node = tree.nodes.new(type='CompositorNodeRLayers')
        render_layer_node.location = location
        render_layer_node.layer = layer_name
        render_layer_node.scene = current_scene  # 현재 씬을 노드의 씬으로 지정

    # 렌더 레이어 노드 활성화/비활성화 설정
    render_layer_node.mute = mute
    
    # 파일 출력 노드 생성 및 연결
    output_node = tree.nodes.new(type='CompositorNodeOutputFile')
    output_node.location = (500, location[1])  # 옆에 위치
    output_node.mute = mute  # 출력 노드도 동일하게 mute 설정
    
    # 렌더링 파일 경로 설정
    values = get_base_filepath(current_scene)
    _, new_path, _ = values
    set_file_output_node_base_path(output_node, new_path, label=f"FileOutput {layer_name}: ")
    
    # 파일 포맷 및 컬러 설정
    set_output_png(output_node.format, alpha=True, label=f"FileOutput {layer_name}: ")
    
    # 파일 서브패스 설정
    my_tool = current_scene.my_tool  # 현재 씬의 사용자 정의 속성 사용
    scene_number = my_tool.scene_number  # 씬 번호
    cut_number = my_tool.cut_number  # 컷 번호
    output_node.file_slots[0].path = f"{scene_number}_{cut_number}_{layer_name}_"
    tree.links.new(render_layer_node.outputs['Image'], output_node.inputs[0])


def add_kuwa_layer_node(tree, layer_name, location):
    current_scene = bpy.context.scene
    base_path, new_path, _ = get_base_filepath(current_scene)  # new_path 초기화

    # 렌더 레이어 노드 찾기 또는 생성
    render_layer_node = None
    for node in tree.nodes:
        if isinstance(node, bpy.types.CompositorNodeRLayers) and node.layer == layer_name:
            render_layer_node = node  # 이미 존재하는 노드 찾기
            break

    if render_layer_node is None:
        render_layer_node = tree.nodes.new(type='CompositorNodeRLayers')
        render_layer_node.location = location
        render_layer_node.layer = layer_name
        render_layer_node.scene = current_scene

    # Kuwahara 필터 노드 생성 및 연결
    kuwahara_node = None
    for node in tree.nodes:
        if isinstance(node, bpy.types.CompositorNodeKuwahara) and node.inputs[0].is_linked:
            if node.inputs[0].links[0].from_node == render_layer_node:
                kuwahara_node = node  # 이미 존재하는 Kuwahara 노드 찾기
                break

    if kuwahara_node is None:
        kuwahara_node = tree.nodes.new(type='CompositorNodeKuwahara')
        kuwahara_node.location = (300, location[1])
        # kuwahara_node.size = 8
        kuwahara_node.inputs[1].default_value = 8
        kuwahara_node.use_high_precision = True

        
        
        tree.links.new(render_layer_node.outputs['Image'], kuwahara_node.inputs[0])



    # 파일 출력 노드 생성 및 연결
    output_node = None
    output_path_suffix = f"{layer_name}_kuwa_"
    for node in tree.nodes:
        if isinstance(node, bpy.types.CompositorNodeOutputFile):
            if node.file_slots[0].path.endswith(output_path_suffix):
                output_node = node  # 이미 존재하는 파일 출력 노드 찾기
                break

    if output_node is None:
        output_node = tree.nodes.new(type='CompositorNodeOutputFile')
        output_node.location = (500, location[1])
        set_file_output_node_base_path(output_node, new_path, label=f"FileOutput {layer_name}: ")
        set_output_png(output_node.format, alpha=True, label=f"FileOutput {layer_name}: ")
        my_tool = current_scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        output_node.file_slots[0].path = f"{scene_number}_{cut_number}_{output_path_suffix}"
        tree.links.new(kuwahara_node.outputs['Image'], output_node.inputs[0])





def add_layer_node(tree, layer_name, location, node_type='RLayers', post_process_type=None, settings=None):
    current_scene = bpy.context.scene
    _, new_path, _ = get_base_filepath(current_scene)

    # Find or create the render layer node
    layer_node = None
    for node in tree.nodes:
        if isinstance(node, bpy.types.CompositorNodeRLayers) and node.layer == layer_name:
            layer_node = node
            break

    if layer_node is None:
        layer_node = tree.nodes.new(type='CompositorNodeRLayers')
        layer_node.location = location
        layer_node.layer = layer_name
        layer_node.scene = current_scene

    # Additional node processing
    if post_process_type:
        process_node = tree.nodes.new(type=post_process_type)
        process_node.location = (location[0] + 300, location[1])

        if settings:
            for key, value in settings.items():
                if hasattr(process_node.format, key):  # Check if the key is an attribute of the format object
                    if key == "file_format":
                        set_output_image_format(process_node.format, value, label=f"FileOutput {layer_name}: ")
                    else:
                        setattr(process_node.format, key, value)
                elif key not in ['subpath_suffix']:  # Ignore special keys that are handled separately
                    setattr(process_node, key, value)

        if post_process_type == 'CompositorNodeOutputFile':
            set_file_output_node_base_path(process_node, new_path, label=f"{post_process_type}: ")
            scene_number = current_scene.my_tool.scene_number
            cut_number = current_scene.my_tool.cut_number
            subpath = settings.get('subpath_suffix', '')  # Retrieve the subpath suffix if provided
            # Apply the customized file path to the file slot
            process_node.file_slots[0].path = f"{scene_number}_{cut_number}_{layer_name}_{subpath}"

        tree.links.new(layer_node.outputs['Image'], process_node.inputs[0])

class SF_OT_LinkRimToNode1(bpy.types.Operator):
    bl_idname = "object.link_rim_to_node1"
    bl_label = "Link Rim to Node"

    def execute(self, context):
        selected_characters = [item.name for category in context.scene.sf_file_categories for item in category.items if item.is_selected]

        for asset_name in selected_characters:
            light_obj_name = f"{asset_name}_light"
            light_obj = bpy.data.objects.get(light_obj_name)

            if not light_obj:
                self.report({'WARNING'}, f"{light_obj_name} object not found, skipping...")
                continue

            # rim01과 rim02 오브젝트를 모두 찾음
            rim_objects = []
            for child in light_obj.children:
                if "rim01" in child.name or "rim02" in child.name:
                    rim_objects.append(child)

            if not rim_objects:
                self.report({'WARNING'}, f"No rim01 or rim02 objects found under {light_obj_name}, skipping...")
                continue

            for rim_object in rim_objects:
                if rim_object.users > 0 and (rim_object.library is None or rim_object.library is not None):
                    for material in bpy.data.materials:
                        if material.use_nodes and material.name.startswith(f"MI_{asset_name}_"):
                            nodes = material.node_tree.nodes
                            links = material.node_tree.links

                            for node in nodes:
                                if node.type == 'GROUP' and node.node_tree and node.node_tree.name.startswith('SF_Toon_Logic'):
                                    input_index = 53 if "rim01" in rim_object.name else 54
                                    if 0 <= input_index < len(node.inputs):
                                        input_socket = node.inputs[input_index]
                                        existing_links = list(input_socket.links)
                                        for link in existing_links:
                                            links.remove(link)

                                        # 텍스처 코디네이트 노드 생성 및 링크
                                        tc_node = nodes.new(type='ShaderNodeTexCoord')
                                        tc_node.object = rim_object
                                        links.new(tc_node.outputs['Object'], input_socket)

                                        print(f"성공: {rim_object.name}에 대한 텍스처 코디네이트 노드가 생성되고 연결되었습니다.")
                                    else:
                                        print(f"실패: 입력 인덱스 '{input_index}'가 범위를 벗어났습니다.")

                            self.remove_unused_nodes_from_material(material)

        return {'FINISHED'}
        
    def remove_unused_nodes_from_material(self, material):
        if material.use_nodes:
            nodes = material.node_tree.nodes
            links = material.node_tree.links

            # Collect all 'Texture Coordinate' nodes that are not connected to any other nodes
            unused_tex_coord_nodes = [
                node for node in nodes
                if node.type == 'TEX_COORD' and not any(link.from_node == node or link.to_node == node for link in links)
            ]

            # Delete all unused 'Texture Coordinate' nodes
            for node in unused_tex_coord_nodes:
                nodes.remove(node)

class LinkClass(bpy.types.Operator):
    bl_idname = "sf.link_class"
    bl_label = "Link Collection"

    def execute(self, context):
        scene = context.scene
        if scene.get('ch_processed'):
            # 'ch' 카테고리가 이미 처리되었다면 관련 로직을 건너뛰기
            return {'FINISHED'}
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        ch_scene = bpy.context.scene
        
        settings = load_settings()     
        link_class = settings.get('linkClass', False)
        
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    blend_file_path = self.get_blend_file_path(asset_name, category.name, scene_number, cut_number)
                    self.append_materials_and_collection_from_blend(context, blend_file_path, asset_name, category.name)
                    asset_col_name = f"{asset_name}_col"

                    if link_class:
                        if category.name == 'ch':
                            self.add_solidify_to_collection_objects(blend_file_path, asset_col_name)
                            self.update_mesh_data_from_blend(blend_file_path, asset_col_name)
                            self.add_properties_and_link(asset_name)  # 새로 추가한 기능
                            bpy.ops.sf.updatelightposition_class()
        return {'FINISHED'}

    def add_properties_and_link(self, asset_name):
        # bpy.ops.object.sf_add_properties_and_link1()
        # asset_name이 유효한지 확인 (빈 문자열이 아닌지)
        if not asset_name or not asset_name.strip():
            self.report({'ERROR'}, "Asset name is invalid or empty.")
            return

        try:
            # 필요한 데이터가 유효하다면 연산자 호출
            bpy.ops.object.sf_add_properties_and_link1()
        except RuntimeError as e:
            # 오류 발생 시 적절한 에러 메시지를 출력
            self.report({'ERROR'}, f"Error occurred: {str(e)}")



    def remove_existing_properties(self, obj):
        for prop_name in list(obj.keys()):
            del obj[prop_name]

    def add_custom_properties(self, obj, properties_info):
        for prop_name, default, prop_type, _, min_val, max_val, soft_min, soft_max in properties_info:
            obj[prop_name] = default
            # 프로퍼티 매니저 업데이트 보장
            obj.id_properties_ensure()
            property_manager = obj.id_properties_ui(prop_name)
            if prop_type == "COLOR":
                property_manager.update(min=min_val, max=max_val, soft_min=soft_min, soft_max=soft_max, subtype='COLOR', default=default)
            elif prop_type == "FLOAT":
                property_manager.update(min=min_val, max=max_val, soft_min=soft_min, soft_max=soft_max, subtype='NONE', default=default)

    def get_blend_file_path(self, asset_name, category_name, scene_number, cut_number):
        project_name = get_current_project_name()
        base_path = get_project_paths(project_name)
        return os.path.join(base_path, "assets", category_name, asset_name, "mod", f"{asset_name}.blend")


    def append_materials_and_collection_from_blend(self, context, blend_file_path, asset_name, category_name):
        light_col_name = f"{asset_name}_light_col"
        light_obj_name = f"{asset_name}_light"

        # 현재 씬에서 해당 이름의 컬렉션이나 Empty 오브젝트가 이미 존재하는지 확인
        existing_collection = bpy.data.collections.get(light_col_name)
        existing_empty = bpy.data.objects.get(light_obj_name)

        # 이미 존재한다면 로드 및 링크 프로세스를 스킵
        if existing_collection or (existing_empty and existing_empty.type == 'EMPTY'):
            print(f"{light_col_name} or {light_obj_name} already exists. Skipping load.")
            return

        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                    # data_to.materials = data_from.materials
                    data_to.worlds = data_from.worlds
                    if category_name in ['bg', 'ch', 'prop']:  # 'bg'와 'ch' 두 경우를 모두 처리
                        light_col_name = f"{asset_name}_light_col"
                        if light_col_name in data_from.collections:
                            data_to.collections = [light_col_name]

                        # 직접 링크 방식을 사용하여 컬렉션을 현재 레이어에 링크
                        self.link_collection_to_active_layer(context, light_col_name)

        # 'bg' 또는 'ch' 카테고리에 따라 적절한 상위 컬렉션에 링크
        if category_name in ['bg', 'ch', 'prop']:
            target_col_name = f"{category_name}_col"  # 'bg_col' 또는 'ch_col'
            target_col = bpy.context.scene.collection.children.get(target_col_name)
            if target_col:
                for col in data_to.collections:
                    target_col.children.link(col)


    def link_collection_to_active_layer(self, context, collection_name):
        # 현재 활성 뷰 레이어를 가져옴
        active_layer = context.view_layer

        # 링크하려는 컬렉션을 찾음
        collection = bpy.data.collections.get(collection_name)

        # 컬렉션이 존재하고 아직 링크되지 않았다면 링크
        if collection and collection_name not in context.scene.collection.children:
            active_layer.active_layer_collection.collection.children.link(collection)
            print(f"{collection_name} collection linked to the active layer.")
                
    def add_solidify_to_collection_objects(self, blend_file_path, target_collection_name):
        print(f"Starting process for blend file: {blend_file_path} and target collection: {target_collection_name}")
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects]
            print(f"Objects loaded from blend file: {len(data_to.objects)}")

        target_collection = bpy.data.collections.get(target_collection_name)
        if not target_collection:
            print(f"Collection '{target_collection_name}' not found.")
            return
        else:
            print(f"Found target collection '{target_collection_name}' with {len(target_collection.objects)} objects.")

        for obj in target_collection.objects:
            if obj.type == 'MESH':
                # print(f"Processing object: {obj.name}")
                base_name = obj.name.split('.')[0]
                blend_obj = next((o for o in data_to.objects if o.name.split('.')[0] == base_name), None)

                if blend_obj and any(mod.name.startswith('LBS') for mod in blend_obj.modifiers):
                    print(f"'LBS' modifier found on blend object: {blend_obj.name}")
                    
                    # 'Solidify' 모디파이어 추가 및 설정
                    solidify_modifier = obj.modifiers.get("Solidify")
                    if not solidify_modifier:
                        print(f"Adding 'Solidify' modifier to object: {obj.name}")
                        solidify_modifier = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
                    solidify_modifier.thickness = 0.1
                    solidify_modifier.offset = 1
                    solidify_modifier.use_flip_normals = True

                    # 버텍스 그룹 설정
                    vg_name = "LBS Solidify Outline"
                    if vg_name in obj.vertex_groups:
                        print(f"Vertex group '{vg_name}' found in object: {obj.name}")
                        solidify_modifier.vertex_group = vg_name
                    else:
                        print(f"Vertex group '{vg_name}' not found in object: {obj.name}, attempting to create.")
                        vg = obj.vertex_groups.new(name=vg_name)
                        solidify_modifier.vertex_group = vg.name

                    solidify_modifier.invert_vertex_group = True
                    solidify_modifier.use_quality_normals = True
                    solidify_modifier.thickness_clamp = 5
                    solidify_modifier.material_offset = -10
                    print(f"'Solidify' modifier added and configured for '{obj.name}'.")
                    
                    # 여기서 'LBS' 머티리얼이 이미 존재하는지 확인
                    if any(mat.name.startswith('LBS') for mat in obj.data.materials):
                        print(f"'LBS' material already exists on {obj.name}, skipping to next object.")
                        continue  # 이미 'LBS' 머티리얼이 존재하면, 다음 오브젝트로 넘어갑니다.

                    # 'LBS' 머티리얼 적용 로직
                    if blend_obj.material_slots:
                        lbs_material = blend_obj.material_slots[0].material
                        if lbs_material:
                            print(f"Found 'LBS' material: {lbs_material.name} for object: {obj.name}")
                            # 기존 머티리얼 인덱스 저장
                            original_mat_indices = [poly.material_index for poly in obj.data.polygons]
                            # 기존 머티리얼 저장
                            original_materials = [mat for mat in obj.data.materials]
                            # 'LBS' 머티리얼 추가
                            print(f"Applying 'LBS' material: {lbs_material.name} to object: {obj.name}")
                            obj.data.materials.clear()
                            obj.data.materials.append(lbs_material)
                            # 기존 머티리얼을 다시 추가
                            for mat in original_materials:
                                obj.data.materials.append(mat)
                            # 폴리곤에 대한 머티리얼 인덱스 업데이트
                            for poly, original_index in zip(obj.data.polygons, original_mat_indices):
                                poly.material_index = min(original_index + 1, len(obj.data.materials)-1)



    def update_mesh_data_from_blend(self, blend_file_path, asset_col_name):
        try:
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                data_to.objects = data_from.objects
                if not data_to.objects: 
                    raise ValueError(f"No objects were loaded from the blend file: {blend_file_path}")
            print(f"Loading blend file from: {blend_file_path}")
        except ValueError as e:
            print(e)  
        except OSError as e:
            print(f"Failed to open blend file: {e}")  
        except RuntimeError as e:
            print(f"Failed to load blend file: {e}")  
        else:
            print(f"Target mesh name to find: {asset_col_name}")
            target_collection = bpy.data.collections.get(asset_col_name)
            if target_collection:
                for obj in target_collection.objects:
                    if obj.type == 'MESH':
                        matching_object = next((o for o in data_to.objects if o.name.split('.')[0] == obj.name.split('.')[0]), None)
                        if matching_object and matching_object.type == 'MESH':
                            # Vertex groups transfer
                            obj.vertex_groups.clear()
                            for vg in matching_object.vertex_groups:
                                new_vg = obj.vertex_groups.new(name=vg.name)
                                for vert_index in range(len(matching_object.data.vertices)):
                                    try:
                                        weight = vg.weight(vert_index)
                                        new_vg.add([vert_index], weight, 'REPLACE')
                                    except RuntimeError:
                                        # Ignore vertices that are not in the group
                                        pass
                            print(f"Transferred vertex groups for object: {obj.name}")
                            
                            # Mask modifier transfer
                            for mod in matching_object.modifiers:
                                if mod.type == 'MASK':
                                    # 새로운 Mask 모디파이어 추가
                                    new_mod = obj.modifiers.new(name=mod.name, type='MASK')
                                    
                                    # 기존 모디파이어의 속성 복사
                                    new_mod.vertex_group = mod.vertex_group
                                    new_mod.invert_vertex_group = mod.invert_vertex_group
                                    new_mod.show_viewport = mod.show_viewport
                                    new_mod.show_render = mod.show_render
                                    
                                    print(f"Transferred 'Mask' modifier from {matching_object.name} to {obj.name}")
                        else:
                            print(f"No matching object in blend file for: {obj.name}")

            else:
                print(f"Collection '{asset_col_name}' not found in the current scene.")
            return {'FINISHED'}

        return {'CANCELLED'}
        
class SF_OT_CopyDropletGeneratorOperator(bpy.types.Operator):
    """Copy Droplet Generator Modifiers, Geometry Nodes, and Material"""
    bl_idname = "sf.copy_droplet_generator"
    bl_label = "Copy Droplet Generator Modifier"

    def execute(self, context):
        scene = context.scene
        if scene.get('ch_processed'):
            return {'FINISHED'}
        
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        ch_scene = bpy.context.scene
        
        settings = load_settings()     
        link_class = settings.get('linkClass', False)
        
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    blend_file_path = self.get_blend_file_path(asset_name, category.name, scene_number, cut_number)
                    self.append_materials_and_collection_from_blend(context, blend_file_path, asset_name, category.name)
                    asset_col_name = f"{asset_name}_col"

                    if link_class:
                        if category.name == 'ch':
                            self.copy_droplets_modifiers(blend_file_path, asset_col_name)
                            self.copy_droplet_generator_geometry_nodes(blend_file_path, asset_col_name)
                            self.copy_droplet_material(asset_col_name)
                            bpy.ops.sf.updatelightposition_class()

                            # 🔥 Droplets 중복 제거 로직 추가
                            target_collection = bpy.data.collections.get(asset_col_name)
                            if target_collection:
                                for obj in target_collection.objects:
                                    if obj.type == 'MESH':
                                        self.clean_duplicate_droplets_modifiers(obj)  # 🔥 추가된 클리너
        return {'FINISHED'}

    def get_blend_file_path(self, asset_name, category_name, scene_number, cut_number):
        base_path = get_project_paths()
        return os.path.join(base_path, "assets", category_name, asset_name, "mod", f"{asset_name}.blend")

    def append_materials_and_collection_from_blend(self, context, blend_file_path, asset_name, category_name):
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.worlds = data_from.worlds
            if category_name in ['bg', 'ch', 'prop']:
                light_col_name = f"{asset_name}_light_col"
                if light_col_name in data_from.collections:
                    data_to.collections = [light_col_name]
                self.link_collection_to_active_layer(context, light_col_name)

    def link_collection_to_active_layer(self, context, collection_name):
        active_layer = context.view_layer
        collection = bpy.data.collections.get(collection_name)
        if collection and collection_name not in context.scene.collection.children:
            active_layer.active_layer_collection.collection.children.link(collection)

    def copy_droplets_modifiers(self, blend_file_path, target_collection_name):
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects

        target_collection = bpy.data.collections.get(target_collection_name)
        if not target_collection:
            self.report({'WARNING'}, f"Collection '{target_collection_name}' not found.")
            return
        
        for obj in target_collection.objects:
            if obj.type == 'MESH':
                # ✅ 중복 방지: Droplets 모디파이어가 이미 있으면 추가하지 않음
                if self.modifier_exists(obj, 'Droplets'):
                    print(f"⚠️ Skipping {obj.name} because Droplets modifier already exists.")
                    continue

                matching_object = next((o for o in data_to.objects if o.name.split('.')[0] == obj.name.split('.')[0]), None)
                if matching_object:
                    for mod in matching_object.modifiers:
                        if mod.name.startswith('Droplets'):
                            new_mod = obj.modifiers.new(name=mod.name, type=mod.type)
                            self.copy_modifier_properties(mod, new_mod)
                            self.copy_droplet_modifier_inputs(mod, new_mod)


    def copy_modifier_properties(self, source_mod, target_mod):
        for prop in source_mod.rna_type.properties:
            if prop.is_readonly:
                continue

            attr_name = prop.identifier
            try:
                source_value = getattr(source_mod, attr_name)
                setattr(target_mod, attr_name, source_value)
            except AttributeError:
                print(f"❌ AttributeError: {attr_name} cannot be copied from {source_mod.name}")
            except Exception as e:
                print(f"❌ Failed to copy attribute '{attr_name}' from {source_mod.name} to {target_mod.name}: {e}")

    def copy_droplet_modifier_inputs(self, source_mod, target_mod):
        input_values = {}
        
        for i in range(50):
            input_name = f"Input_{i}"
            try:
                if input_name in source_mod:
                    input_values[input_name] = source_mod[input_name]
            except KeyError:
                continue

        for input_name, input_value in input_values.items():
            try:
                if input_name in target_mod:
                    target_mod[input_name] = input_value
            except KeyError:
                print(f"❌ KeyError: {input_name} not found in {target_mod.name}")
            except Exception as e:
                print(f"❌ Failed to copy input '{input_name}' from {source_mod.name} to {target_mod.name}: {e}")

    def copy_droplet_generator_geometry_nodes(self, blend_file_path, target_collection_name):
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects

        target_collection = bpy.data.collections.get(target_collection_name)
        if not target_collection:
            self.report({'WARNING'}, f"Collection '{target_collection_name}' not found.")
            return
        
        for obj in target_collection.objects:
            if obj.type == 'MESH':
                if any(mod.name.startswith('DropletGenerator') for mod in obj.modifiers):
                    print(f"⚠️ Skipping {obj.name} because DropletGenerator modifier already exists.")
                    continue
                
                matching_object = next((o for o in data_to.objects if o.name.split('.')[0] == obj.name.split('.')[0]), None)
                if matching_object:
                    for mod in matching_object.modifiers:
                        if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith('DropletGenerator'):
                            new_mod = obj.modifiers.new(name=mod.name, type='NODES')
                            new_mod.node_group = mod.node_group

    def copy_droplet_material(self, asset_col_name):
        target_collection = bpy.data.collections.get(asset_col_name)
        if not target_collection:
            self.report({'WARNING'}, f"Collection '{asset_col_name}' not found.")
            return
        
        droplet_material = bpy.data.materials.get("DropletMat")
        if not droplet_material:
            self.report({'WARNING'}, "DropletMat material not found.")
            return
        
        for obj in target_collection.objects:
            if obj.type == 'MESH':
                material_names = [mat.name for mat in obj.data.materials if mat]
                if droplet_material.name not in material_names:
                    obj.data.materials.append(droplet_material)

    def modifier_exists(self, obj, modifier_name):
        """ 🔥 Droplets 모디파이어가 이미 존재하는지 확인 """
        for mod in obj.modifiers:
            if mod.name == modifier_name and mod.type == 'NODES':
                print(f"✅ {obj.name}에 이미 {modifier_name} 모디파이어가 존재합니다.")
                return True
        return False

    def clean_duplicate_droplets_modifiers(self, obj):
        """ 🔥 Droplets.001, Droplets.002와 같은 중복 모디파이어 삭제 """
        droplet_modifiers = [mod for mod in obj.modifiers if mod.name.startswith('Droplets')]
        
        # Droplets 이름의 모디파이어 중 첫 번째만 남기고 나머지는 삭제
        if len(droplet_modifiers) > 1:
            print(f"🗑️ Cleaning up duplicate Droplets modifiers on {obj.name}")
            for mod in droplet_modifiers[1:]:  # 첫 번째(Droplets) 제외하고 모두 삭제
                print(f"🗑️ Removing duplicate Droplets modifier: {mod.name} from {obj.name}")
                obj.modifiers.remove(mod)

                    
class SF_OT_RemoveDropletGeneratorOperator(bpy.types.Operator):
    """Remove Droplet Generator Modifiers, Geometry Nodes, and Material"""
    bl_idname = "sf.remove_droplet_generator"
    bl_label = "Remove Droplet Generator Modifier"

    def execute(self, context):
        scene = context.scene
        if not scene:
            self.report({'ERROR'}, "Scene not found.")
            return {'CANCELLED'}
        
        my_tool = context.scene.my_tool
        
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    asset_col_name = f"{asset_name}_col"
                    
                    self.remove_droplets_modifiers(asset_col_name)
                    self.remove_droplet_generator_geometry_nodes(asset_col_name)
                    self.remove_droplet_material(asset_col_name)
        
        return {'FINISHED'}

    def remove_droplets_modifiers(self, asset_col_name):
        """Remove Droplets modifiers from objects in the target collection."""
        target_collection = bpy.data.collections.get(asset_col_name)
        if not target_collection:
            self.report({'WARNING'}, f"Collection '{asset_col_name}' not found.")
            return
        
        for obj in target_collection.objects:
            if obj.type == 'MESH':
                modifiers_to_remove = [mod for mod in obj.modifiers if mod.name.startswith('Droplets')]
                for mod in modifiers_to_remove:
                    mod_name = mod.name  # 🔥 모디파이어 이름을 먼저 저장
                    obj.modifiers.remove(mod)  # 🗑️ 모디파이어 삭제
                    print(f"🗑 Removed Droplets modifier: {mod_name} from {obj.name}")  # 🔥 삭제 후에는 이름을 사용

    def remove_droplet_generator_geometry_nodes(self, asset_col_name):
        """Remove Droplet Generator Geometry Nodes modifiers."""
        target_collection = bpy.data.collections.get(asset_col_name)
        if not target_collection:
            self.report({'WARNING'}, f"Collection '{asset_col_name}' not found.")
            return
        
        for obj in target_collection.objects:
            if obj.type == 'MESH':
                modifiers_to_remove = [
                    mod for mod in obj.modifiers 
                    if mod.type == 'NODES' and mod.node_group.name.startswith('DropletGenerator')
                ]
                for mod in modifiers_to_remove:
                    mod_name = mod.name  # 🔥 모디파이어 이름을 먼저 저장
                    obj.modifiers.remove(mod)  # 🗑️ 모디파이어 삭제
                    print(f"🗑 Removed Geometry Nodes modifier: {mod_name} from {obj.name}")  # 🔥 삭제 후에는 이름을 사용

    def remove_droplet_material(self, asset_col_name):
        """Remove DropletMat material from objects in the target collection."""
        target_collection = bpy.data.collections.get(asset_col_name)
        if not target_collection:
            self.report({'WARNING'}, f"Collection '{asset_col_name}' not found.")
            return
        
        droplet_material = bpy.data.materials.get("DropletMat")
        if not droplet_material:
            self.report({'WARNING'}, "DropletMat material not found.")
            return
        
        for obj in target_collection.objects:
            if obj.type == 'MESH':
                material_names = [mat.name for mat in obj.data.materials if mat]  # 🔥 메터리얼 이름을 가져옵니다.
                if droplet_material.name in material_names:  # 🔥 이름으로 비교
                    index = obj.data.materials.find(droplet_material.name)
                    if index != -1:  # 🔥 올바른 인덱스를 찾았는지 확인
                        obj.data.materials.pop(index=index)  # 🗑️ 메터리얼 삭제 (키워드 인자 사용)
                        print(f"🗑 Removed DropletMat material from {obj.name}")
                        
                        
class UpdateLightPosition(bpy.types.Operator):
    bl_idname = "sf.updatelightposition_class"
    bl_label = "Update Light Position"
    
    def execute(self, context):
        scene = context.scene
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        ch_scene = bpy.context.scene
        
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    asset_col_name = f"{asset_name}_col"                  
                    if category.name == 'ch':
                        self.update_light_position_based_on_meshes(asset_name)
        return {'FINISHED'}
        
    def update_light_position_based_on_meshes(self, asset_name):
        asset_col_name = f"{asset_name}_col"  # 어셋의 메인 컬렉션 이름
        asset_col = bpy.data.collections.get(asset_col_name)
        if not asset_col:
            print(f"{asset_col_name} 컬렉션을 찾을 수 없습니다.")
            return

        meshes = [obj for obj in asset_col.objects if obj.type == 'MESH']
        if not meshes:
            print(f"{asset_col_name} 내에 메쉬 객체가 없습니다.")
            return

        # 바운딩 박스의 모든 코너들을 월드 좌표로 계산
        world_corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]

        # 중심 위치 계산
        avg_loc = sum(world_corners, start=Vector((0,0,0))) / len(world_corners)
        
        # 가장 낮은 Z 위치 계산
        lowest_z = min(world_corners, key=lambda pt: pt.z).z

        light_obj_name = f"{asset_name}_light"
        light_obj = bpy.data.objects.get(light_obj_name)
        if not light_obj or light_obj.type != 'EMPTY':
            print(f"{light_obj_name} 이름의 Empty 오브젝트를 찾을 수 없습니다.")
            return

        # light_obj 오브젝트 위치를 업데이트 (X, Y는 중심 위치, Z는 가장 낮은 지점)
        light_obj.location.x = avg_loc.x
        light_obj.location.y = avg_loc.y
        light_obj.location.z = lowest_z
        print(f"{light_obj_name} 오브젝트 위치가 업데이트되었습니다. (X: {avg_loc.x}, Y: {avg_loc.y}, Z: {lowest_z})")


                   
class SubdivideClass(bpy.types.Operator):
    bl_idname = "sf.subdivide_class"
    bl_label = "Subdivide Mesh"

    def execute(self, context):
        scene = context.scene
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:  # 사용자가 선택한 어셋만 고려
                    self.apply_subdivision_to_selected_assets(context)
        return {'FINISHED'}

    def apply_subdivision_to_selected_assets(self, context):
        for obj in bpy.data.objects:
            print(f"Checking object: {obj.name}, type: {obj.type}")
            if obj.type == 'MESH' and not obj.name.endswith('_ns_geo'):
                print(f"Applying subdivision to: {obj.name}")
                self.apply_subdivision(obj)
            elif obj.name.endswith('_ns_geo'):
                print(f"Subdivision not applied to: {obj.name} because it ends with '_ns_geo'")
            else:
                print(f"Subdivision not applied to: {obj.name} because it's not a mesh")

    def apply_subdivision(self, obj):
        if not any(mod.type == 'SUBSURF' for mod in obj.modifiers):
            mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
            mod.levels = 2  
            mod.render_levels = 2
            mod.boundary_smooth = 'PRESERVE_CORNERS'

            print(f"Subdivision applied to: {obj.name}")
        else:
            print(f"Subdivision not applied to: {obj.name} because it already has a subdivision modifier")        


class unSubdivideClass(bpy.types.Operator):
    bl_idname = "sf.unsubdivide_class"
    bl_label = "Un-Subdivide Mesh"

    def execute(self, context):
        self.remove_subdivision_from_all_assets()
        return {'FINISHED'}

    def remove_subdivision_from_all_assets(self):
        for obj in bpy.data.objects:
            print(f"Checking object: {obj.name}, type: {obj.type}")
            if obj.type == 'MESH' and not obj.name.endswith('_ns_geo'):
                print(f"Removing subdivision from: {obj.name}")
                self.remove_subdivision(obj)
            elif obj.name.endswith('_ns_geo'):
                print(f"Subdivision not removed from: {obj.name} because it ends with '_ns_geo'")
            else:
                print(f"Subdivision not removed from: {obj.name} because it's not a mesh")

    def remove_subdivision(self, obj):
        subsurf_modifiers = [mod for mod in obj.modifiers if mod.type == 'SUBSURF']
        if subsurf_modifiers:
            for mod in subsurf_modifiers:
                obj.modifiers.remove(mod)
                print(f"Subdivision removed from: {obj.name}")
        else:
            print(f"No subdivision modifier found on: {obj.name}")


class SF_OT_ClearCustomNormalOperator(bpy.types.Operator):
    bl_idname = "sf.clear_custom_normal_operator"
    bl_label = "Clear Custom Split Normals"
    
    def clear_custom_split_normals_and_disable_auto_smooth(self):
        # 원래 활성 오브젝트를 저장
        original_active = bpy.context.view_layer.objects.active

        # 현재 씬의 모든 오브젝트를 반복
        for obj in bpy.context.scene.objects:
            # 오브젝트 타입이 'MESH'인 경우에만 작업 수행
            if obj.type == 'MESH':
                # 해당 메시를 활성 오브젝트로 설정
                bpy.context.view_layer.objects.active = obj
                # 오브젝트를 선택 상태로 만듦
                obj.select_set(True)
                
                # 커스텀 스플릿 노멀 데이터 지우기
                bpy.ops.mesh.customdata_custom_splitnormals_clear()
                
                # 자동 스무딩 비활성화
                obj.data.use_auto_smooth = False
                
                # 다음 오브젝트를 위해 현재 오브젝트 선택 해제
                obj.select_set(False)

        # 원래 활성 오브젝트로 복원
        bpy.context.view_layer.objects.active = original_active

    def execute(self, context):
        self.clear_custom_split_normals_and_disable_auto_smooth()
        return {'FINISHED'}


import bpy

import bpy

class SF_OT_LinkLightProperties(bpy.types.Operator):
    """UI에서 선택한 어셋의 _light 속성을 
    _v03 노드에 드라이버로 연결"""
    bl_idname = "object.sf_link_light_properties"
    bl_label = "Link Light Properties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        processed_assets = []

        for category in scene.sf_file_categories:
            for item in category.items:
                if not item.is_selected:
                    continue

                asset_name = item.name
                light_obj = bpy.data.objects.get(f"{asset_name}_light")
                collection = bpy.data.collections.get(f"{asset_name}_col")

                if not light_obj or not collection:
                    self.report({'WARNING'}, f"{asset_name}: light 또는 _col 컬렉션 없음, 스킵")
                    continue

                # 커스텀 프로퍼티 값 준비
                ambient_col = tuple(light_obj.get("P01_Ambient_Color", (1,1,1,1)))
                shadow_col  = tuple(light_obj.get("P02_Shadow_Color", (1,1,1,1)))
                ambient_val = float(ambient_col[0])
                line_val    = float(light_obj.get("P30_Line_Thickness", 0.1))

                # 컬렉션 하위 메쉬 순회
                for obj in collection.all_objects:
                    if obj.type != 'MESH':
                        continue
                    for slot in obj.material_slots:
                        mat = slot.material
                        if not mat or not mat.node_tree:
                            continue
                        for node in mat.node_tree.nodes:
                            # if node.type == "GROUP" and node.node_tree and node.node_tree.name == "SF_Toon_v03":
                            if node.type == 'GROUP' and node.node_tree and node.node_tree.name.startswith('SF_Toon_'):                                
                                self.apply_and_link(mat, node, light_obj, ambient_val, ambient_col, shadow_col, line_val)

                processed_assets.append(asset_name)

        if not processed_assets:
            self.report({'ERROR'}, "선택된 어셋 없음")
            return {'CANCELLED'}
        else:
            self.report({'INFO'}, f"{', '.join(processed_assets)} 처리 완료")
            return {'FINISHED'}

    # ---------------- 유틸 함수 ----------------
    def clear_links_and_drivers(self, mat, socket):
        if socket.is_linked:
            socket.links.clear()
        ad = mat.node_tree.animation_data
        if ad and ad.drivers:
            path = socket.path_from_id() + ".default_value"
            for fcurve in list(ad.drivers):
                if fcurve.data_path == path:
                    mat.node_tree.driver_remove(fcurve.data_path, fcurve.array_index)

    def add_driver(self, mat, socket, obj, prop_name, is_color=False):
        path = socket.path_from_id() + ".default_value"
        if is_color:
            for i in range(4):
                fcurve = mat.node_tree.driver_add(path, i)
                drv = fcurve.driver
                drv.type = 'AVERAGE'
                var = drv.variables.new()
                var.name = "var"
                var.targets[0].id = obj
                var.targets[0].data_path = f'["{prop_name}"][{i}]'
        else:
            fcurve = mat.node_tree.driver_add(path)
            drv = fcurve.driver
            drv.type = 'AVERAGE'
            var = drv.variables.new()
            var.name = "var"
            var.targets[0].id = obj
            var.targets[0].data_path = f'["{prop_name}"]'

    def apply_and_link(self, mat, node, light_obj, ambient_val, ambient_col, shadow_col, line_val):
        # --Ambient
        if "--Ambient" in node.inputs:
            s = node.inputs["--Ambient"]
            self.clear_links_and_drivers(mat, s)
            s.default_value = ambient_col
            self.add_driver(mat, s, light_obj, "P01_Ambient_Color", is_color=True)

        # --Shadow Multiply
        if "--Shadow Multiply" in node.inputs:
            s = node.inputs["--Shadow Multiply"]
            self.clear_links_and_drivers(mat, s)
            s.default_value = shadow_col
            self.add_driver(mat, s, light_obj, "P02_Shadow_Color", is_color=True)

        # Line Size(Overall)
        if "Line Size(Overall)" in node.inputs:
            s = node.inputs["Line Size(Overall)"]
            self.clear_links_and_drivers(mat, s)
            s.default_value = line_val
            self.add_driver(mat, s, light_obj, "P30_Line_Thickness", is_color=False)


class SF_OT_AddPropertiesAndLink1(bpy.types.Operator):
    bl_idname = "object.sf_add_properties_and_link1"
    bl_label = "Add Properties and Link to Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number

        success_count = 0
        linethickness_prop = "P30_Line_Thickness"
        properties_info = self.get_properties_info()
        if not properties_info:
            self.report({'ERROR'}, "Failed to load properties info.")
            return {'CANCELLED'}

        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    collection_name = f"{asset_name}_col"
                    light_obj_name = f"{asset_name}_light"
                    light_obj = bpy.data.objects.get(light_obj_name)

                    if not light_obj:
                        self.report({'WARNING'}, f"{light_obj_name} object not found, skipping...")
                        continue

                    self.remove_existing_drivers(collection_name)
                    self.remove_existing_properties(light_obj)
                    self.add_custom_properties(light_obj, properties_info)
                    self.add_drivers_to_materials(collection_name, light_obj, properties_info)
                    parent_obj = bpy.data.objects.get(asset_name)
                    self.process_all_meshes(parent_obj, light_obj, linethickness_prop)
                    # self.link_rim_to_node(context, asset_name)
                    
                    #모든 메터리얼에 대한 'Texture Coordinate' 노드 제거
                    for mat in bpy.data.materials:
                        self.remove_unlinked_tex_coord_nodes(mat)
                    
                    success_count += 1

        if success_count == 0:
            self.report({'ERROR'}, "No valid characters found to process")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Processed {success_count} characters successfully.")
        return {'FINISHED'}

    def get_properties_info(self):
        file_path = 'T:/_json/get_properties_info.json'
        try:
            with open(file_path, 'r') as infile:
                return json.load(infile)
        except Exception as e:
            print(f"Error loading properties info from {file_path}: {e}")
            return []

    def remove_existing_drivers(self, collection_name):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            print(f"Collection '{collection_name}' not found")
            return

        for obj in collection.objects:
            if obj.type == 'MESH' and obj.data.materials:
                for mat in obj.data.materials:
                    if mat.use_nodes and mat.node_tree and mat.node_tree.animation_data:
                        drivers_to_remove = []
                        for driver in mat.node_tree.animation_data.drivers:
                            drivers_to_remove.append(driver.data_path)  # Collecting drivers before removal

                        for driver_path in drivers_to_remove:
                            try:
                                mat.node_tree.driver_remove(driver_path)
                                print(f"Successfully removed driver at {driver_path}")
                            except Exception as e:
                                print(f"Failed to remove driver at {driver_path}: {e}")

    def remove_existing_properties(self, obj):
        for prop_name in list(obj.keys()):
            del obj[prop_name]

    def add_custom_properties(self, obj, properties_info):
        obj.id_properties_ensure()  # Ensure the property manager is updated
        for prop_info in properties_info:
            prop_name = prop_info['name']
            default = prop_info['default']
            prop_type = prop_info['type']
            min_val = prop_info.get('min', 0)  # Default values for min, max if not provided
            max_val = prop_info.get('max', 1)
            soft_min = prop_info.get('soft_min', min_val)  # Use min_val if soft_min is not provided
            soft_max = prop_info.get('soft_max', max_val)  # Use max_val if soft_max is not provided

            # Set default value and type directly on the object
            obj[prop_name] = default

            # Update the property manager settings
            property_manager = obj.id_properties_ui(prop_name)
            if prop_type == "COLOR":
                property_manager.update(min=min_val, max=max_val, soft_min=soft_min, soft_max=soft_max, subtype='COLOR')
            elif prop_type == "FLOAT":
                property_manager.update(min=min_val, max=max_val, soft_min=soft_min, soft_max=soft_max, subtype='NONE')

            # After updating property_manager, ensure the default value is set correctly, especially for COLOR type
            obj[prop_name] = default
            
    def add_drivers_to_materials(self, collection_name, light_obj, properties_info):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            print(f"Collection '{collection_name}' not found")
            return

        for obj in collection.objects:
            if obj.type == 'MESH' and obj.data.materials:
                for mat in obj.data.materials:
                    if mat.use_nodes:
                        for node in mat.node_tree.nodes:
                            if node.type == 'GROUP' and node.node_tree and node.node_tree.name == "SF_Toon_Logic":
                                for prop_info in properties_info:
                                    prop_name = prop_info['name']
                                    default = prop_info['default']
                                    prop_type = prop_info['type']
                                    input_idx = prop_info['index']
                                    self.add_driver_to_material(mat, node, prop_name, default, prop_type, input_idx, light_obj)
                               

    def add_driver_to_material(self, mat, node, prop_name, default, prop_type, input_idx, light_obj):
        # 노드와 해당 인덱스의 입력이 유효한지 확인
        node_input = node.inputs[input_idx] if input_idx < len(node.inputs) else None
        if node_input:
            path = f'nodes["{node.name}"].inputs[{input_idx}].default_value'
            if prop_type == "COLOR":
                for idx in range(4):  # RGBA 채널에 대해
                    fcurve = mat.node_tree.driver_add(path, idx)
                    self.setup_driver(fcurve, light_obj, prop_name, idx)
            elif prop_type == "FLOAT":
                fcurve = mat.node_tree.driver_add(path)
                self.setup_driver([fcurve], light_obj, prop_name)
        else:
            print(f"Node '{node.name}' does not have an input at index {input_idx}")


    def setup_driver(self, fcurves, obj, prop_name, idx=None):
        if not isinstance(fcurves, list):
            fcurves = [fcurves]
        for fcurve in fcurves:
            driver = fcurve.driver
            driver.type = 'AVERAGE'
            var = driver.variables.new()
            var.targets[0].id = obj
            if idx is not None:
                var.targets[0].data_path = f'["{prop_name}"][{idx}]'
            else:
                var.targets[0].data_path = f'["{prop_name}"]'

    def add_driver_to_modifier_thickness(self, target_obj, modifier_name, driver_source, linethickness_prop):
        # 드라이버를 추가할 솔리디파이 모디파이어의 thickness 속성을 찾습니다.
        modifier = target_obj.modifiers.get(modifier_name)
        if modifier and modifier.type == 'SOLIDIFY':
            # 드라이버가 이미 존재하는지 확인하고, 있다면 제거합니다.
            if target_obj.animation_data and target_obj.animation_data.drivers:
                # 모든 드라이버를 순회합니다.
                for fcurve in target_obj.animation_data.drivers:
                    # 해당 모디파이어의 thickness 속성에 대한 드라이버를 찾습니다.
                    if fcurve.data_path == f'modifiers["{modifier_name}"].thickness':
                        # 해당 드라이버를 제거합니다.
                        target_obj.driver_remove(fcurve.data_path)

            # 드라이버 설정
            fcurve = target_obj.driver_add(f'modifiers["{modifier_name}"].thickness')
            driver = fcurve.driver
            driver.type = 'AVERAGE'

            var = driver.variables.new()
            var.name = 'var'
            var.targets[0].id = driver_source
            var.targets[0].data_path = f'["{linethickness_prop}"]'
        else:
            self.report({'WARNING'}, "Modifier not found or not a Solidify modifier.")


    def process_all_meshes(self, parent_obj, driver_source, linethickness_prop):
        # parent_obj 하위의 모든 오브젝트를 순회합니다.
        for obj in parent_obj.children:
            # 메쉬 타입의 오브젝트만 처리합니다.
            if obj.type == 'MESH':
                # 모든 솔리디파이 모디파이어에 대해 드라이버를 추가합니다.
                for modifier in obj.modifiers:
                    if modifier.type == 'SOLIDIFY':
                        self.add_driver_to_modifier_thickness(obj, modifier.name, driver_source, linethickness_prop)
            # 재귀적으로 하위 오브젝트 처리
            self.process_all_meshes(obj, driver_source, linethickness_prop)
            
    def find_active_rim_object(self, asset_name):
        # Find the parent Empty object
        parent_name = f"{asset_name}_light"
        parent_obj = bpy.data.objects.get(parent_name)
        if not parent_obj:
            print(f"Parent object '{parent_name}' not found.")
            return None

        # Check for active object among the children
        for child in parent_obj.children:
            if child.name.startswith(f"{asset_name}_rim") and child.select_get():
                return child

        print("No active rim object found under the specified parent.")
        return None

    def find_all_mesh_objects(self, collection, max_depth=10):
        """
        주어진 컬렉션과 하위 컬렉션에 포함된 모든 메쉬 오브젝트를 반환합니다.
        최대 탐색 깊이를 max_depth로 제한합니다.
        """
        mesh_objects = []

        def recurse_collection(col, depth):
            if depth > max_depth:
                return
            for obj in col.objects:
                if obj.type == 'MESH':
                    mesh_objects.append(obj)
            for sub_col in col.children:
                recurse_collection(sub_col, depth + 1)

        recurse_collection(collection, 0)
        return mesh_objects


    def link_rim_to_node(self, context, asset_name):
        print(f"시작: {asset_name}에 대한 림 오브젝트를 찾는 중...")

        # 활성 림 오브젝트 검색
        active_rim_obj = self.find_active_rim_object(asset_name)
        if not active_rim_obj:
            print("실패: 활성 림 오브젝트를 찾을 수 없습니다.")
            return
        else:
            print(f"성공: 활성 림 오브젝트 '{active_rim_obj.name}'를 찾았습니다.")

        # 재료 컬렉션 검색
        material_collection_name = f"{asset_name}_col"
        print(f"재료 컬렉션 '{material_collection_name}'를 검색 중...")
        material_collection = bpy.data.collections.get(material_collection_name)
        if not material_collection:
            print(f"실패: 재료 컬렉션 '{material_collection_name}'을 찾을 수 없습니다.")
            return
        else:
            print(f"성공: 재료 컬렉션 '{material_collection_name}'을 찾았습니다.")

        # 재료 컬렉션 내 모든 메쉬 오브젝트 가져오기
        all_mesh_objects = self.find_all_mesh_objects(material_collection, max_depth=10)
        print(f"성공: 재료 컬렉션 내 총 {len(all_mesh_objects)}개의 메쉬 오브젝트를 찾았습니다.")

        # 림 오브젝트와 재료 컬렉션의 메쉬 오브젝트들 연결
        for obj in all_mesh_objects:
            if obj.data.materials:
                for mat in obj.data.materials:
                    if mat.use_nodes:
                        nodes = mat.node_tree.nodes
                        links = mat.node_tree.links
                        print(f"노드 수정 중: 재료 '{mat.name}'...")
                        for node in nodes:
                            if node.type == 'GROUP' and node.node_tree and node.node_tree.name.startswith('SF_Toon_Logic'):
                                rim_name = active_rim_obj.name[len(asset_name)+1:]
                                input_index = 53 if "rim01" in rim_name else 54

                                if 0 <= input_index < len(node.inputs):
                                    input_socket = node.inputs[input_index]
                                    # 기존 링크 제거
                                    existing_links = list(input_socket.links)
                                    for link in existing_links:
                                        links.remove(link)

                                    # 새 텍스처 좌표 노드 생성 및 링크
                                    tc_node = nodes.new(type='ShaderNodeTexCoord')
                                    tc_node.object = active_rim_obj
                                    links.new(tc_node.outputs['Object'], input_socket)
                                    print(f"성공: '{rim_name}'에 대한 노드 연결 완료.")
                                else:
                                    print(f"실패: 입력 인덱스 '{input_index}'가 범위를 벗어났습니다.")
                    else:
                        print(f"노드 사용 안함: 재료 '{mat.name}'는 노드를 사용하지 않습니다.")
            else:
                print(f"오류: '{obj.name}' 오브젝트는 메터리얼이 없습니다.")



    def remove_unlinked_tex_coord_nodes(self, material):
        if material.node_tree:
            for node in material.node_tree.nodes:
                # 'Texture Coordinate' 노드이고, 어떤 출력도 연결되지 않은 경우
                if node.type == 'TEX_COORD' and not any(output.is_linked for output in node.outputs):
                    # 노드 삭제
                    material.node_tree.nodes.remove(node)

# (클래스 등록 목록 위에 추가)

class SF_OT_ImportModePopup(bpy.types.Operator):
    """'Append'와 'Link' 임포트 방식 중 하나를 선택하는 팝업 메뉴를 띄웁니다."""
    bl_idname = "sf.import_mode_popup"
    bl_label = "임포트 방식 선택"

    def execute(self, context):
        # 이 오퍼레이터는 메뉴만 띄우므로 직접 실행하는 로직은 없습니다.
        return {'FINISHED'}

    def invoke(self, context, event):
        # 팝업 메뉴를 그리는 함수를 정의합니다.
        def draw(self, context):
            layout = self.layout
            layout.label(text="어떤 방식으로 에셋을 가져올까요?")
            
            # 'Append (Legacy USD)' 버튼: 누르면 import_mode='APPEND'로 실행
            op_append = layout.operator("sf.import_selected_operator", text="Append (Legacy USD)", icon='APPEND_BLEND')
            op_append.import_mode = 'APPEND'

            # 'Link + Override' 버튼: 누르면 import_mode='LINK'로 실행
            op_link = layout.operator("sf.import_selected_operator", text="Link + Override", icon='LINK_BLEND')
            op_link.import_mode = 'LINK'

        # 정의한 draw 함수를 사용하여 팝업 메뉴를 화면에 표시
        context.window_manager.popup_menu(draw, title=self.bl_label, icon='QUESTION')
        return {'FINISHED'}
# 기존 SF_OT_ImportSelectedOperator 클래스를 아래 내용으로 전체 교체하세요.

class SF_OT_ImportSelectedOperator(bpy.types.Operator):
    bl_idname = "sf.import_selected_operator"
    bl_label = "Import Selected"
    bl_options = {'REGISTER', 'UNDO'}
    
    # 팝업에서 선택한 모드를 전달받기 위한 속성
    import_mode: bpy.props.EnumProperty(
        name="Import Mode",
        items=[('APPEND', "Append", "Original USD import method"),
               ('LINK', "Link", "Link collection and create override")],
        default='APPEND'
    )

    def execute(self, context):
        print(f"--- [SF Import] Start Mode: {self.import_mode} ---")
        
        scene = context.scene
        # 1. 선택된 아이템이 있는지 먼저 확인 (통합 체크)
        selected_items = []
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    selected_items.append((category, item))

        if not selected_items:
            self.report({'WARNING'}, "선택된 어셋이 없습니다! (리스트의 체크박스를 확인하세요)")
            print("[SF Import] No items selected.")
            return {'CANCELLED'}

        # 2. 모드에 따라 실행
        try:
            if self.import_mode == 'LINK':
                self.execute_link_mode(context, selected_items)
            else: # APPEND 모드
                self.execute_append_mode(context, selected_items)
        except Exception as e:
            self.report({'ERROR'}, f"임포트 중 에러 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        print("--- [SF Import] Finished ---")
        
        bpy.ops.sf.update_selected_operator_dsc()
        
        return {'FINISHED'}

    # -------------------------------------------------------------------
    # ▼ [모드 1] Append 방식
    # -------------------------------------------------------------------
    def execute_append_mode(self, context, selected_items):
        scene = context.scene
        project_name = get_current_project_name()
        base_path = get_project_paths(project_name)
        scene_num = scene.my_tool.scene_number
        cut_num = scene.my_tool.cut_number
        
        # 프로젝트 경로 체크
        if not base_path:
            self.report({'ERROR'}, "프로젝트 경로(Base Path)를 가져올 수 없습니다. Project 설정을 확인하세요.")
            return

        print(f"[SF Import] Base Path: {base_path}")

        # 선택된 아이템 순회
        for category, item in selected_items:
            # ch 카테고리는 Subdivision 적용 등 특수 로직이 있어서 구분
            is_ch = (category.name == "ch")
            self.process_selected_item_append(item, category, f"{category.name}_col", base_path, scene_num, cut_num, context, apply_subdivision=is_ch, project_name=project_name)

    def process_selected_item_append(self, item, category, category_col_name, base_path, scene_number, cut_number, context, apply_subdivision, project_name=None):
        import os
        asset_name = item.name
        asset_col_name = f"{asset_name}_col"
        
        # 캐시 디렉토리 경로 구성
        directory = resolve_cache_context(scene_number, cut_number, context, project_name)["cache_dir"]
        
        # 디렉토리 존재 여부 확인
        if not os.path.exists(directory):
            self.report({'ERROR'}, f"Cache 폴더를 찾을 수 없습니다: {directory}")
            return

        # USD 파일 찾기
        asset_file_path = find_asset_file_path(directory, asset_name)

        if not asset_file_path:
            self.report({'WARNING'}, f"USD 파일을 찾을 수 없음: {asset_name} (in {directory})")
            return

        print(f"[SF Import] Found USD: {asset_file_path}")

        blend_file_path = self.get_blend_file_path(base_path, category.name, asset_name, project_name=project_name)
        if not blend_file_path or not os.path.exists(blend_file_path):
            self.report({'WARNING'}, f"Published Blend not found: {asset_name}\nPath: {blend_file_path}")
            return

        append_published_asset_with_cache(
            blend_file_path,
            category.name,
            asset_name,
            context,
            usd_path=asset_file_path,
            usd_file_name=os.path.basename(asset_file_path),
        )
        
        # 후처리
        bpy.ops.sf.cleanup_orphans_combined1()
        
        if apply_subdivision: # 캐릭터인 경우
            self.apply_light_mask_to_collection(asset_col_name, context)
            self.apply_subdivision_to_meshes(asset_col_name)

    def append_materials_from_blend(self, blend_file_path, asset_name, category_name):
        try:
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                data_to.materials = data_from.materials
            # 이름 정리 (MIA_ 등)
            for mat in data_to.materials:
                if mat and '.' in mat.name: 
                    mat.name = mat.name.split('.')[0]
        except OSError:
            print(f"[SF Import Warning] Failed to load library: {blend_file_path}")

    def import_asset_from_usd(self, asset_file_path, category_col_name, asset_col_name, category_name, asset_name, context):
        # 컬렉션 구조 생성
        if category_col_name not in bpy.context.scene.collection.children:
            new_category_col = bpy.data.collections.new(category_col_name)
            bpy.context.scene.collection.children.link(new_category_col)
        category_col = bpy.context.scene.collection.children[category_col_name]

        if asset_col_name not in category_col.children:
            new_asset_col = bpy.data.collections.new(asset_col_name)
            category_col.children.link(new_asset_col)
        asset_col = category_col.children[asset_col_name]

        # USD 임포트
        # 활성 컬렉션 변경 (임포트될 위치)
        layer_col = context.view_layer.layer_collection
        target_layer_col = None
        
        # 재귀적으로 레이어 컬렉션 찾기
        def find_layer_col(lc, name):
            if lc.name == name: return lc
            for child in lc.children:
                res = find_layer_col(child, name)
                if res: return res
            return None

        cat_lc = find_layer_col(layer_col, category_col_name)
        if cat_lc:
            asset_lc = find_layer_col(cat_lc, asset_col_name)
            if asset_lc:
                context.view_layer.active_layer_collection = asset_lc

        # 실제 임포트 수행
        safe_usd_import(filepath=asset_file_path, relative_path=True, import_subdiv=False, set_frame_range=False)
        
        # 임포트 후 스케일 조정 및 머티리얼 적용
        for obj in asset_col.objects:
            if obj.parent is None:
                # USD 임포트 시 스케일이 100배 큰 경우가 많아 0.01로 줄임 (파이프라인 규칙인듯)
                obj.scale = (0.01, 0.01, 0.01)
            apply_matching_materials(obj)

        try:
            apply_cache_to_asset_geometry(
                asset_col,
                asset_name,
                asset_file_path,
                os.path.basename(asset_file_path),
                create_modifier=False,
                create_cache_file=False,
            )
        except Exception as e:
            print(f"[SF Import][WARN] Failed to auto-bind cache after USD import: {e}")

    # -------------------------------------------------------------------
    # ▼ [모드 2] Link 방식
    # -------------------------------------------------------------------
    def execute_link_mode(self, context, selected_items):
        base_path = get_project_paths()
        if not base_path:
             self.report({'ERROR'}, "Base Path Error")
             return

        for category, item in selected_items:
            self.process_selected_item_link(item, category, f"{category.name}_col", base_path, context)

    def process_selected_item_link(self, item, category, category_col_name, base_path, context):
        import os
        asset_name = item.name
        blend_file_path = self.get_blend_file_path(base_path, category.name, asset_name)

        if not blend_file_path or not os.path.exists(blend_file_path):
            self.report({'WARNING'}, f"링크할 원본 .blend 파일을 찾을 수 없습니다: {asset_name}\nPath: {blend_file_path}")
            return
            
        self.link_asset_collection(blend_file_path, category_col_name, asset_name, context)

    def link_asset_collection(self, blend_file_path, category_col_name, asset_name, context):
        asset_col_name = f"{asset_name}_col"
        try:
            with bpy.data.libraries.load(blend_file_path, link=True) as (data_from, data_to):
                if asset_col_name in data_from.collections:
                    data_to.collections = [asset_col_name]
                else:
                    self.report({'WARNING'}, f"파일 안에 '{asset_col_name}' 컬렉션이 없습니다: {os.path.basename(blend_file_path)}")
                    return None
        except Exception as e:
            self.report({'ERROR'}, f"파일 링크 실패: {e}")
            return None

        # 링크된 컬렉션을 씬에 인스턴스로 배치
        linked_collection = data_to.collections[0] # 위에서 로드한 컬렉션
        if not linked_collection: return

        # 상위 카테고리 컬렉션 확보
        if category_col_name not in bpy.data.collections:
            cat_col = bpy.data.collections.new(category_col_name)
            context.scene.collection.children.link(cat_col)
        else:
            cat_col = bpy.data.collections[category_col_name]

        # Collection Instance(Empty) 생성
        instance_empty = bpy.data.objects.new(asset_name, None)
        instance_empty.instance_type = 'COLLECTION'
        instance_empty.instance_collection = linked_collection
        instance_empty.scale = (0.01, 0.01, 0.01) # 스케일 보정

        cat_col.objects.link(instance_empty)

        # Library Override 적용
        try:
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = instance_empty
            instance_empty.select_set(True)
            bpy.ops.object.library_override_hierarchy_create(object=instance_empty, collection=instance_empty.instance_collection)
            print(f"[SF Import] Linked & Overridden: {asset_name}")
        except Exception as e:
            self.report({'ERROR'}, f"라이브러리 오버라이드 생성 실패: {e}")

    # -------------------------------------------------------------------
    # ▼ 공용 헬퍼
    # -------------------------------------------------------------------
    def get_blend_file_path(self, base_path, category_name, asset_name, project_name=None):
        import os
        # 일반 경로
        # category_name이 'ch'나 'bg' 등을 포함하는지 확인
        folder = "prop" # default
        if "ch" in category_name: folder = "ch"
        elif "bg" in category_name: folder = "bg"
        elif "prop" in category_name: folder = "prop"
        
        return get_asset_blend_path(category_name, asset_name, project_name)

    # (이하 apply_light_mask 등 메서드는 기존 코드의 로직이 길어서 생략했습니다. 
    #  클래스 내부에 `apply_light_mask_to_collection` 과 `apply_subdivision_to_meshes` 메서드가 
    #  기존 코드에 정의되어 있다면 그대로 두시거나, 아래에 복사해서 넣으시면 됩니다.)
    
    def apply_light_mask_to_collection(self, asset_col_name, context):
        # ... 기존 코드 복사 ...
        asset_col = bpy.data.collections.get(asset_col_name)
        if not asset_col: return
        mesh_objects = [obj for obj in asset_col.all_objects if obj.type == 'MESH']
        for obj in mesh_objects:
            if not hasattr(obj, "light_mask_applied") or not obj.get("light_mask_applied"):
                # 뷰레이어 체크 생략하고 강제 진행하거나 try-except
                try:
                    obj.select_set(True)
                    bpy.ops.object.apply_light_mask()
                    obj["light_mask_applied"] = True
                    obj.select_set(False)
                except:
                    pass
        if "ViewLayer" in bpy.context.scene.view_layers:
            context.window.view_layer = bpy.context.scene.view_layers["ViewLayer"]

    def apply_subdivision_to_meshes(self, asset_col_name):
        # ... 기존 코드 복사 ...
        asset_col = bpy.data.collections.get(asset_col_name)
        if not asset_col: return
        mesh_objects = [obj for obj in asset_col.all_objects if obj.type == 'MESH']
        for obj in mesh_objects:
            if "_ns_geo" not in obj.name:
                if "Subdivision" not in [mod.name for mod in obj.modifiers]:
                    subdivision_modifier = obj.modifiers.new(name="Subdivision", type='SUBSURF')
                    subdivision_modifier.levels = 1
                    subdivision_modifier.render_levels = 2

class SF_OT_ResetMaterialOperator(bpy.types.Operator):
    bl_idname = "sf.reset_material_operator"
    bl_label = "Reset Material"

    def execute(self, context):
        scene = context.scene
        bpy.context.window.view_layer = bpy.context.scene.view_layers["ViewLayer"]

        selected_assets = [item.name for category in scene.sf_file_categories for item in category.items if item.is_selected]
        for asset_name in selected_assets:
            light_obj_name = f"{asset_name}_light"
            light_obj = bpy.data.objects.get(light_obj_name)

            if not light_obj:
                self.report({'ERROR'}, f"Object {light_obj_name} not found.")
                continue

            category_name = next(cat.name for cat in scene.sf_file_categories if any(item.name == asset_name for item in cat.items))
            blend_file_path = self.get_blend_file_path(category_name, asset_name)

            self.reset_materials_and_keep_drivers(blend_file_path, asset_name, light_obj)

        return {'FINISHED'}

    def get_blend_file_path(self, category_name, asset_name):
        if "ch" in category_name:
            return os.path.join(get_character_dir(), asset_name, "mod", f"{asset_name}.blend")
        elif "bg" in category_name:
            return os.path.join(get_background_dir(), asset_name, "mod", f"{asset_name}.blend")
        elif "prop" in category_name:
            return os.path.join(get_prop_dir(), asset_name, "mod", f"{asset_name}.blend")
        return None

    def reset_materials_and_keep_drivers(self, blend_file_path, asset_name, light_obj):
        try:
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                data_to.materials = data_from.materials
                print(f"Materials from {blend_file_path} loaded successfully.")

            for mat in data_to.materials:
                if '.' in mat.name:
                    mat.name = mat.name.split('.')[0]

            asset_col_name = f"{asset_name}_col"
            asset_col = bpy.data.collections.get(asset_col_name)
            if not asset_col:
                print(f"Collection '{asset_col_name}' not found.")
                return

            for obj in asset_col.objects:
                if obj.type == 'MESH' and obj.data.materials:
                    for i, mat_slot in enumerate(obj.data.materials):
                        if mat_slot:
                            original_mat_name = mat_slot.name.split('.')[0]
                            new_mat = next((mat for mat in data_to.materials if mat.name == original_mat_name), None)
                            if new_mat:
                                obj.data.materials[i] = new_mat

            self.relink_drivers(light_obj, asset_col_name)

        except OSError as e:
            print(f"Error loading file {blend_file_path}: {e}")

    def relink_drivers(self, light_obj, asset_col_name):
        collection = bpy.data.collections.get(asset_col_name)
        if not collection:
            print(f"Collection '{asset_col_name}' not found")
            return

        properties_info = self.get_properties_info()
        if not properties_info:
            print("Failed to load properties info.")
            return

        for obj in collection.objects:
            if obj.type == 'MESH' and obj.data.materials:
                for mat in obj.data.materials:
                    if mat.use_nodes:
                        for node in mat.node_tree.nodes:
                            if node.type == 'GROUP' and node.node_tree and node.node_tree.name == "SF_Toon_Logic":
                                for prop_info in properties_info:
                                    prop_name = prop_info['name']
                                    default = prop_info['default']
                                    prop_type = prop_info['type']
                                    input_idx = prop_info['index']
                                    self.add_driver_to_material(mat, node, prop_name, default, prop_type, input_idx, light_obj)

    def get_properties_info(self):
        file_path = 'T:/_json/get_properties_info.json'
        try:
            with open(file_path, 'r') as infile:
                return json.load(infile)
        except Exception as e:
            print(f"Error loading properties info from {file_path}: {e}")
            return []

    def add_driver_to_material(self, mat, node, prop_name, default, prop_type, input_idx, light_obj):
        node_input = node.inputs[input_idx] if input_idx < len(node.inputs) else None
        if node_input:
            path = f'nodes["{node.name}"].inputs[{input_idx}].default_value'
            if prop_type == "COLOR":
                for idx in range(4):
                    fcurve = mat.node_tree.driver_add(path, idx)
                    self.setup_driver(fcurve, light_obj, prop_name, idx)
            elif prop_type == "FLOAT":
                fcurve = mat.node_tree.driver_add(path)
                self.setup_driver([fcurve], light_obj, prop_name)

    def setup_driver(self, fcurves, obj, prop_name, idx=None):
        if not isinstance(fcurves, list):
            fcurves = [fcurves]
        for fcurve in fcurves:
            driver = fcurve.driver
            driver.type = 'AVERAGE'
            var = driver.variables.new()
            var.targets[0].id = obj
            if idx is not None:
                var.targets[0].data_path = f'["{prop_name}"][{idx}]'
            else:
                var.targets[0].data_path = f'["{prop_name}"]'


class SF_OT_UpdateSelectedOperator(bpy.types.Operator):
    bl_idname = "sf.update_selected_operator"
    bl_label = "Update Selected"

    def execute(self, context):
        scene = context.scene
        my_tool = scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        base_path = get_project_paths()  # 파일 경로의 기본 부분
        
        # "ch" 카테고리에 있는 캐릭터의 MeshSequenceCache 경로 업데이트
        self.update_ch_category(scene, base_path, scene_number, cut_number)
        
        # 나머지 카테고리 처리
        self.update_other_categories(scene, base_path, scene_number, cut_number)

        return {'FINISHED'}
        
    def refresh_linked_libraries(self):
        # 모든 링크된 라이브러리를 반복
        for library in bpy.data.libraries:
            # 리프래시 메서드 호출
            library.reload()

    def update_ch_category(self, scene, base_path, scene_number, cut_number):
        for cache in bpy.data.cache_files.values():
            if "_ch_" in cache.name:
                parts = cache.name.split('_')
                if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                    parts[1] = scene_number
                    parts[2] = cut_number
                    new_name = '_'.join(parts)
                    new_filepath = os.path.join(base_path, "scenes", scene_number, cut_number, "ren", "cache", new_name)
                    cache.filepath = new_filepath
                    print(f"Updated cache file path for {cache.name} to {new_filepath}")
                    cache.name = new_name
                    print(f"Updated cache name to {new_name}")

    def update_other_categories(self, scene, base_path, scene_number, cut_number):
        for category in scene.sf_file_categories:
            if category.name != "ch":
                for item in category.items:
                    if item.is_selected:  # 아이템이 선택되었을 때만 처리
                        asset_col_name = f"{item.name}_col"
                        if bpy.data.collections.get(asset_col_name):
                            # 선택된 아이템에 대한 컬렉션의 오브젝트를 지우고
                            self.clear_collection(asset_col_name)
                            self.refresh_linked_libraries()
                            bpy.ops.sf.cleanup_orphans_combined1()
                            # 선택된 어셋을 다시 가져온다
                            bpy.ops.sf.import_selected_operator('INVOKE_DEFAULT')
        self.apply_matching_materials()
    
    def clear_collection(self, collection_name):
        collection = bpy.data.collections.get(collection_name)
        if collection:
            for obj in collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            print(f"Cleared all objects in collection: {collection_name}")

    def apply_matching_materials(self):
        materials = bpy.data.materials

        for obj in bpy.context.selected_objects:
            obj_data = obj.data
            if obj_data and hasattr(obj_data, "materials"):
                for i, slot in enumerate(obj.material_slots):
                    material_name = slot.name

                    # material_name에서 'MIA_'를 'MI_'로 대체합니다.
                    material_name = material_name.replace('MIA_', 'MI_')

                    # ':'를 기준으로 문자열을 분할하고 마지막 부분을 가져옵니다.
                    if ':' in material_name:
                        material_name = material_name.split(":")[-1]

                    # '.'를 기준으로 문자열을 분할하고 첫 번째 부분을 베이스 메터리얼 이름으로 사용합니다.
                    base_material_name = material_name.split(".")[0]

                    if base_material_name in materials:
                        mat = materials.get(base_material_name)
                        if mat is None:
                            mat = materials.new(name=base_material_name)
                        if obj_data.materials:
                            obj_data.materials[i] = mat
                        else:
                            obj_data.materials.append(mat)

class SF_OT_UpdateSelectedLightOperator(bpy.types.Operator):
    bl_idname = "sf.update_selected_light_operator"
    bl_label = "Update Selected Light"

    def execute(self, context):
        print("Starting operator execution...")
        scene = context.scene
        my_tool = scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        base_path = get_project_paths()  # 파일 경로의 기본 부분
        print(f"Base path acquired: {base_path}")
        print(f"Scene number: {scene_number}, Cut number: {cut_number}")

        # 나머지 카테고리 처리
        self.update_other_categories(scene, base_path, scene_number, cut_number)

        print("Finished operator execution.")
        return {'FINISHED'}
        
    def refresh_linked_libraries(self):
        print("Refreshing linked libraries...")
        for library in bpy.data.libraries:
            library.reload()
        print("All linked libraries refreshed.")

    def update_other_categories(self, scene, base_path, scene_number, cut_number):
        print("Updating other categories...")
        for category in scene.sf_file_categories:
            # print(f"Processing category: {category.name}")
            if category.name != "prop":
                for item in category.items:
                    asset_col_light_name = f"{item.name}_light_col"
                    if bpy.data.collections.get(asset_col_light_name):
                        print(f"Clearing collection: {asset_col_light_name}")
                        # self.clear_collection(asset_col_light_name)
                        self.delete_collection(asset_col_light_name)
                        self.refresh_linked_libraries()
                        bpy.ops.sf.cleanup_orphans_combined1()
                        print(f"Orphans cleaned up for: {asset_col_light_name}")
                        if item.is_selected:
                            print(f"Linking assets for: {item.name}")
                            bpy.ops.sf.link_class()
                    else:
                        print(f"No collection found for: {asset_col_light_name}")
    
    def delete_collection(self, collection_name):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            print(f"Collection '{collection_name}' not found.")
            return

        # Find all parent collections and unlink this collection
        all_collections = bpy.data.collections  # Get all collections in the data
        for parent in all_collections:  # Iterate over all collections
            if collection.name in parent.children:  # Check if the target collection is a child
                parent.children.unlink(collection)  # Unlink the target collection from the parent

        # Now that the collection is unlinked from all parents, check if it can be deleted
        if collection.users == 0:
            bpy.data.collections.remove(collection)
            print(f"Collection '{collection_name}' has been removed.")
        else:
            print(f"Collection '{collection_name}' still has users and was not removed.")



           
class SF_OT_ApplyLineArt(bpy.types.Operator):
    bl_idname = "sf.apply_line_art"
    bl_label = "Line Art"

    def execute(self, context):
        scene = context.scene
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        base_path = get_project_paths()

        for category in scene.sf_file_categories:
            category_col_name = f"{category.name}_col"

            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    asset_col_name = f"{asset_name}_col"
                    directory = os.path.join(base_path, scene_number, cut_number, "ren", "cache")
                    asset_file_path = find_asset_file_path(directory, asset_name)

                    # 지오메트리 노드 설정이 적용될 객체를 찾습니다.
                    asset_line_obj_name = f"{asset_name}_line"
                    asset_line_obj = bpy.data.objects.get(asset_line_obj_name)
                    
                    # 지오메트리 노드 설정을 적용합니다.
                    if asset_line_obj and asset_line_obj.type == 'MESH' and "GeometryNodes" in asset_line_obj.modifiers:
                        self.apply_geometry_nodes_settings(asset_line_obj, asset_col_name)

        return {'FINISHED'}
        

    def apply_geometry_nodes_settings(self, asset_line_obj, asset_col_name):
        # asset_line_obj가 메시 객체인지 확인
        if asset_line_obj and asset_line_obj.type == 'MESH':
            # Scene (input_1)에 어셋 이름에 기반한 컬렉션 지정
            if asset_col_name in bpy.data.collections:
                asset_line_obj.modifiers["GeometryNodes"]["Input_1"] = bpy.data.collections[asset_col_name]
            # Camera (input_5)에 현재 활성화된 카메라 지정
            if bpy.context.scene.camera:
                asset_line_obj.modifiers["GeometryNodes"]["Input_5"] = bpy.context.scene.camera  
            asset_line_obj.modifiers["GeometryNodes"]["Input_15"] = bpy.context.scene.input_15
            asset_line_obj.modifiers["GeometryNodes"]["Input_16"] = bpy.context.scene.input_16
            asset_line_obj.modifiers["GeometryNodes"]["Socket_0"] = True
            asset_line_obj.modifiers["GeometryNodes"]["Input_11"] = False
            asset_line_obj.modifiers["GeometryNodes"]["Input_20"] = False
            asset_line_obj.modifiers["GeometryNodes"]["Input_31"] = True
            asset_line_obj.modifiers["GeometryNodes"]["Input_10"] = True        
            # 레졸루션 X와 Y를 가져와 각각 지오메트리 노드에 적용
            asset_line_obj.modifiers["GeometryNodes"]["Input_4"] = bpy.context.scene.render.resolution_x
            asset_line_obj.modifiers["GeometryNodes"]["Input_3"] = bpy.context.scene.render.resolution_y
            
            # 씬 카메라의 FOV값을 가져와서 +10 한 다음 그 값을 radian으로 변환해 지오메트리 노드에 적용
        if bpy.context.scene.camera and bpy.context.scene.camera.data.type == 'PERSP':
            fov_in_radians = bpy.context.scene.camera.data.angle
            fov_in_degrees = fov_in_radians * (180 / math.pi)  # 라디안을 도로 변환
            fov_in_degrees += 10  # 10도를 더함
            asset_line_obj.modifiers["GeometryNodes"]["Input_48"] = fov_in_degrees  # 변환된 값을 적용

        
    def append_materials_and_collection_from_blend1(self, blend_file_path, asset_name, category_name):
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.materials = data_from.materials

        for mat in data_to.materials:
            if '.' in mat.name:
                mat.name = mat.name.split('.')[0]



    def import_asset(self, asset_file_path, category_col_name, asset_col_name, category_name, context):
        scene = context.scene

        # 카테고리 컬렉션 확인 및 생성
        category_col = bpy.data.collections.get(category_col_name)
        if not category_col:
            category_col = bpy.data.collections.new(category_col_name)
            scene.collection.children.link(category_col)

        # 어셋 컬렉션 확인 및 생성
        asset_col = category_col.children.get(asset_col_name)
        if not asset_col:
            asset_col = bpy.data.collections.new(asset_col_name)
            category_col.children.link(asset_col)

        # 컬렉션이 비활성화 되어있다면 활성화
        layer_collection = bpy.context.view_layer.layer_collection
        layer_collection = self.find_layer_collection(layer_collection, asset_col_name)
        if layer_collection and not layer_collection.collection.hide_viewport:
            layer_collection.collection.hide_viewport = False

        # 해당 컬렉션에 오브젝트가 없는 경우에만 임포트 진행
        if not asset_col.objects:
            # 파일 존재 여부 확인
            if not os.path.exists(asset_file_path):
                self.report({'ERROR'}, f"Asset file not found: {asset_file_path}")
                return {'CANCELLED'}

            # 파일 경로를 사용하여 어셋 임포트
            safe_usd_import(filepath=asset_file_path, relative_path=True, import_subdiv=False, set_frame_range=False)

            # 임포트된 어셋 중 루트 객체의 스케일 조정 및 머티리얼 적용
            for obj in asset_col.objects:
                if obj.parent is None:
                    obj.scale = (0.01, 0.01, 0.01)
                    self.apply_matching_materials(obj)
                    bpy.ops.sf.cleanup_orphans_combined1()

    def find_layer_collection(self, layer_collection, collection_name):
        """ Recursively find a layer collection by name """
        if layer_collection.name == collection_name:
            return layer_collection
        for child in layer_collection.children:
            result = self.find_layer_collection(child, collection_name)
            if result:
                return result
        return None

class SF_OT_updateMaterialOperator(bpy.types.Operator):
    bl_idname = "sf.update_materials"
    bl_label = "Update Materials from Blend File"
    bl_options = {'REGISTER', 'UNDO'}

    def apply_matching_materials(self, obj, materials_dict):
        for slot in obj.material_slots:
            mat = slot.material
            if mat:
                processed_name = mat.name
                if ':' in processed_name:
                    processed_name = processed_name.split(':')[-1]
                if '.' in processed_name:
                    processed_name = '.'.join(processed_name.split('.')[:-1])
                if processed_name in materials_dict:
                    slot.material = materials_dict[processed_name]

    def get_blend_file_path(self, asset_name, category_name, scene_number, cut_number):
        base_path = get_project_paths()
        return os.path.join(base_path, "assets", category_name, asset_name, "mod", f"{asset_name}.blend")

    def execute(self, context):
        scene = context.scene
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number

        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    asset_name = item.name
                    blend_file_path = self.get_blend_file_path(asset_name, category.name, scene_number, cut_number)
                    asset_col_name = f"{asset_name}_col"

                    # 어셋 컬렉션 확인
                    asset_col = bpy.data.collections.get(asset_col_name)
                    if not asset_col:
                        self.report({'ERROR'}, f"Collection '{asset_col_name}' not found.")
                        continue
                    
                    # 어셋 컬렉션 하위 모든 메쉬 객체의 메터리얼 별명 생성
                    material_alias_dict = {}
                    def get_mesh_objects_recursive(collection):
                        for obj in collection.objects:
                            if obj.type == 'MESH':
                                for slot in obj.material_slots:
                                    mat = slot.material
                                    if mat:
                                        processed_name = mat.name
                                        if ':' in processed_name:
                                            processed_name = processed_name.split(':')[-1]
                                        if '.' in processed_name:
                                            processed_name = '.'.join(processed_name.split('.')[:-1])
                                        material_alias_dict[processed_name] = mat
                            for child_col in collection.children:
                                get_mesh_objects_recursive(child_col)

                    get_mesh_objects_recursive(asset_col)

                    # 블렌드 파일에서 메터리얼 로드
                    materials_dict = {}
                    try:
                        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                            data_to.materials = data_from.materials
                        for mat in data_to.materials:
                            if mat:
                                processed_name = mat.name
                                if ':' in processed_name:
                                    processed_name = processed_name.split(':')[-1]
                                if '.' in processed_name:
                                    processed_name = '.'.join(processed_name.split('.')[:-1])
                                materials_dict[processed_name] = mat
                        print(f"Materials from {blend_file_path} loaded successfully.")
                    except Exception as e:
                        self.report({'ERROR'}, f"Failed to load materials from blend file: {str(e)}")
                        continue

                    # 어셋 컬렉션 하위 메쉬 객체에 메터리얼 적용
                    def apply_materials_recursive(collection):
                        for obj in collection.objects:
                            if obj.type == 'MESH':
                                self.apply_matching_materials(obj, materials_dict)
                        for child_col in collection.children:
                            apply_materials_recursive(child_col)
                    apply_materials_recursive(asset_col)
                    bpy.ops.object.sf_add_properties_and_link1()
        return {'FINISHED'}

class SF_OT_UpdateMaterialsOperator(bpy.types.Operator):
    bl_idname = "sf.update_materials_operator"
    bl_label = "Update Materials"

    def execute(self, context):
        base_path = get_project_paths()

        for category in context.scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:  # UI에서 사용자가 선택한 항목만 처리
                    asset_name = item.name
                    category_name = self.get_category_name(asset_name)
                    blend_file_path = os.path.join(base_path, "assets", category_name, asset_name, "mod", f"{asset_name}.blend")

                    if os.path.exists(blend_file_path):
                        self.update_materials_from_blend(context, blend_file_path, asset_name)
                    else:
                        self.report({'WARNING'}, f"Blend file not found for {asset_name}")

        print("Material update complete.")
        return {'FINISHED'}

    def update_materials_from_blend(self, context, blend_file_path, asset_name):
        """
        어셋의 Blend 파일에서 메터리얼을 어팬드하고, 해당 메터리얼로 교체합니다.
        """
        # Load original materials
        original_materials = self.append_materials_from_blend(blend_file_path)

        if not original_materials:
            self.report({'ERROR'}, f"No materials found in {blend_file_path}")
            return

        # Process materials in the scene
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self.replace_object_materials(obj, original_materials)
            else:
                print(f"Skipped {obj.name}: Not a mesh object.")

    def append_materials_from_blend(self, blend_file_path):
        """
        어팬드된 메터리얼 리스트를 반환합니다.
        """
        try:
            existing_materials = set(bpy.data.materials.keys())
            with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                data_to.materials = data_from.materials

            # Find newly appended materials
            new_materials = [bpy.data.materials[mat_name] for mat_name in bpy.data.materials.keys() if mat_name not in existing_materials]
            print(f"Appended materials: {[mat.name for mat in new_materials]}")
            return new_materials

        except Exception as e:
            print(f"Error appending materials from {blend_file_path}: {e}")
            return []

    def replace_object_materials(self, obj, original_materials):
        """
        오브젝트의 메터리얼을 원본 메터리얼로 교체합니다.
        """
        for slot in obj.material_slots:
            if not slot.material:
                continue

            scene_material_name = slot.material.name.split(".")[0].lower()  # 씬 메터리얼 이름의 앞부분
            matching_material = next(
                (mat for mat in original_materials if mat.name.split(".")[0].lower() == scene_material_name),
                None
            )

            if matching_material:
                print(f"Replacing material '{slot.material.name}' with '{matching_material.name}' on '{obj.name}'")
                slot.material = matching_material
            else:
                print(f"No matching material found for '{slot.material.name}' on '{obj.name}'")

    def get_category_name(self, asset_name):
        """
        어셋 이름을 기반으로 카테고리를 결정합니다.
        """
        character_names = get_character_names()
        bg_names = get_bg_names()
        prop_names = get_prop_names()

        if asset_name in character_names:
            return "ch"
        elif asset_name in bg_names:
            return "bg"
        elif asset_name in prop_names:
            return "prop"
        else:
            return "prop"


        
class SF_OT_ImportSceneCameraOperator(bpy.types.Operator):
    bl_idname = "sf.import_scene_camera"
    bl_label = "Import Scene Camera"

    def execute(self, context):
        scene = context.scene
        my_tool = scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        project_name = get_current_project_name()
        project_prefix = get_project_prefix(project_name)
        cache_context = resolve_cache_context(scene_number, cut_number, context, project_name)
        cache_dir = cache_context["cache_dir"]
        scene_token = cache_context["scene_token"]
        cut_token = cache_context["cut_token"]

        # 카메라 이름
        name_candidates = []
        for scene_candidate, cut_candidate in (
            (scene_number, cut_number),
            (scene_token, cut_token),
        ):
            scene_text = str(scene_candidate or "").strip()
            cut_text = str(cut_candidate or "").strip()
            if not scene_text or not cut_text:
                continue
            candidate = (
                f"{project_prefix}_{scene_text}_{cut_text}_cam",
                f"{project_prefix}_{scene_text}_{cut_text}_camera_data.json",
                f"{project_prefix}_cam_{scene_text}_{cut_text}",
            )
            if candidate not in name_candidates:
                name_candidates.append(candidate)

        cut_folder_text = str(cut_number or "").strip()
        if "_" in cut_folder_text:
            cut_parts = [part.strip() for part in cut_folder_text.split("_") if part.strip()]
            if len(cut_parts) >= 2:
                scene_text = cut_parts[0]
                cut_text = "_".join(cut_parts[1:])
                candidate = (
                    f"{project_prefix}_{scene_text}_{cut_text}_cam",
                    f"{project_prefix}_{scene_text}_{cut_text}_camera_data.json",
                    f"{project_prefix}_cam_{scene_text}_{cut_text}",
                )
                if candidate not in name_candidates:
                    name_candidates.append(candidate)

        camera_name = ""
        json_file_name = ""
        camera_name_scene = ""
        camera_file_path = ""
        full_json_path = ""

        for camera_name_candidate, json_name_candidate, scene_camera_candidate in name_candidates:
            candidate_camera_path = os.path.join(cache_dir, f"{camera_name_candidate}.fbx")
            candidate_json_path = os.path.join(cache_dir, json_name_candidate)
            if os.path.exists(candidate_camera_path) or os.path.exists(candidate_json_path):
                camera_name = camera_name_candidate
                json_file_name = json_name_candidate
                camera_name_scene = scene_camera_candidate
                camera_file_path = candidate_camera_path
                full_json_path = candidate_json_path
                break

        if not camera_file_path and name_candidates:
            camera_name, json_file_name, camera_name_scene = name_candidates[0]
            camera_file_path = os.path.join(cache_dir, f"{camera_name}.fbx")
            full_json_path = os.path.join(cache_dir, json_file_name)

        print(f"Camera file name: {camera_name}")
        print(f"Camera file path: {camera_file_path}")
        print(f"JSON file path: {full_json_path}")
        print(f"Scene camera name: {camera_name_scene}")

        # 기존 카메라 삭제
        if camera_name_scene in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[camera_name_scene], do_unlink=True)

        # FBX 가져오기
        if os.path.exists(camera_file_path):
            context.view_layer.active_layer_collection = context.view_layer.layer_collection
            bpy.ops.import_scene.fbx(filepath=camera_file_path, anim_offset=0.0)

            # 카메라 아닌 오브젝트 삭제
            imported_objects = [obj for obj in bpy.context.selected_objects if obj.type != 'CAMERA']
            for obj in imported_objects:
                bpy.data.objects.remove(obj, do_unlink=True)

            # 카메라 속성 세팅
            imported_cameras = [obj for obj in bpy.context.selected_objects if obj.type == 'CAMERA']
            if imported_cameras:
                camera = imported_cameras[0]
                camera.name = camera_name_scene
            else:
                camera = bpy.data.objects.get(camera_name_scene)
            if camera is not None:
                scene.camera = camera
                camera.data.passepartout_alpha = 1
                camera.data.clip_start = 0.05
                camera.data.clip_end = 50
                camera.data.sensor_fit = 'HORIZONTAL'

            # 🔥 JSON 읽기 및 1/2 해상도 완벽 보정 로직 🔥
            if os.path.exists(full_json_path):
                with open(full_json_path, 'r') as json_file:
                    camera_data = json.load(json_file)

                    # 프레임 범위 적용
                    scene.frame_start = int(camera_data.get('minTime', scene.frame_start))
                    scene.frame_end = int(camera_data.get('maxTime', scene.frame_end))

                    json_w = camera_data.get('resolutionX')
                    json_h = camera_data.get('resolutionY')

                    if json_w and json_h:
                        if json_w < 2500:
                            final_w = int(json_w * 2)
                            final_h = int(json_h * 2)
                        else:
                            final_w = int(json_w)
                            final_h = int(json_h)
                    else:
                        if project_prefix == "DSC":
                            final_w, final_h = 4096, 1716
                        elif project_prefix == "ttm":
                            final_w, final_h = 3840, 1634
                        else:
                            final_w, final_h = 1920, 1080

                    # 홀수 보정
                    if final_h % 2 != 0:
                        final_h += 1
                    if final_w % 2 != 0:
                        final_w += 1

                    scene.render.resolution_x = final_w
                    scene.render.resolution_y = final_h
                    
                    # 🔥 [해상도 % 100% 고정]
                    scene.render.resolution_percentage = 100

                return {'FINISHED'}

        else:
            tried_paths = ", ".join(os.path.join(cache_dir, f"{candidate[0]}.fbx") for candidate in name_candidates)
            self.report({'WARNING'}, f"Camera file not found: {camera_file_path} | tried: {tried_paths}")

        return {'FINISHED'}


# ---- publish 경로: 항상 base_name 기준으로 만듦 ----
def get_published_blend_path(project, category, asset_name):
    base_name = get_asset_base_name(asset_name)

    # 기존 프로젝트별 루트 규칙을 유지 (필요 시 너희 파일의 기존 로직으로 교체)
    if project == 'DSC' or project == 'dsc':
        base = "S:/assets"
    elif project == 'BTS':
        base = "B:/assets"        
    elif project == 'THE_TRAP':
        base = "T:/assets"
    elif project == 'ARBOBION':
        base = "A:/assets"
    elif project == 'FUZZ':
        base = "Z:/assets"        
    else:
        base = "S:/assets"  # fallback

    # 파이프라인 규칙: assets/<카테고리>/<어셋>/mod/<어셋>.blend
    return os.path.join(base, category, base_name, "mod", f"{base_name}.blend")


def _get_modifier_cache_object_paths(mod):
    """Return cache_file.object_paths as plain strings, safely."""
    cf = getattr(mod, 'cache_file', None)
    if not cf:
        return []

    try:
        paths = []
        for p in cf.object_paths:
            value = getattr(p, 'path', None) or getattr(p, 'object_path', None) or getattr(p, 'name', None)
            if value:
                paths.append(str(value))
        return paths
    except Exception:
        return []


def _cache_path_leaf(path):
    return path.rstrip('/').split('/')[-1]


def _normalize_cache_name_token(value):
    token = str(value or "").split(".")[0].strip().lower()
    token = re.sub(r'^(msh_|geo_|mesh_)', '', token)
    token = re.sub(r'(_geo)+$', '_geo', token)
    token = re.sub(r'(_mesh)+$', '_mesh', token)
    token = re.sub(r'[^a-z0-9_]+', '', token)
    return token


def _rank_cache_object_path(path, asset_name=None):
    """Lower score is better. Prefer the shallowest valid prim path."""
    normalized = path.rstrip('/')
    depth = normalized.count('/')
    score = depth

    if '/Looks/' in normalized:
        score += 1000
    if '/geo/' in normalized:
        score += 10
    if asset_name and f'/{asset_name}/geo/' in normalized:
        score += 5

    return score


def _find_best_cache_object_path(mod, obj_name, asset_name=None):
    """
    Look up an existing USD prim path from cache_file.object_paths by Blender object name.
    This never fabricates a new path string. It only returns one of the existing cache paths.
    """
    base_name = obj_name.split('.')[0]
    base_name_l = base_name.lower()
    normalized_base = _normalize_cache_name_token(base_name)
    paths = _get_modifier_cache_object_paths(mod)
    if not paths:
        return None

    # 1) Exact leaf-name match
    exact = [p for p in paths if _cache_path_leaf(p) == base_name]
    if exact:
        return sorted(exact, key=lambda p: _rank_cache_object_path(p, asset_name))[0]

    # 2) Case-insensitive exact leaf-name match
    exact_ci = [p for p in paths if _cache_path_leaf(p).lower() == base_name_l]
    if exact_ci:
        return sorted(exact_ci, key=lambda p: _rank_cache_object_path(p, asset_name))[0]

    # 3) Normalized leaf-name match for naming drift like jaw_geo_geo <-> jaw_geo
    normalized = [p for p in paths if _normalize_cache_name_token(_cache_path_leaf(p)) == normalized_base]
    if normalized:
        return sorted(normalized, key=lambda p: _rank_cache_object_path(p, asset_name))[0]

    # 4) Any path segment match, still preferring the shallowest valid prim path
    segment_matches = []
    for p in paths:
        segments = [_normalize_cache_name_token(part) for part in str(p).split('/') if part]
        if normalized_base and normalized_base in segments:
            segment_matches.append(p)

    if segment_matches:
        return sorted(segment_matches, key=lambda p: _rank_cache_object_path(p, asset_name))[0]

    return None


def _sync_modifier_object_path_from_cache(mod, obj_name, asset_name=None):
    """
    Update mod.object_path only when a matching path is found in cache_file.object_paths.
    If no match is found, keep the existing object_path untouched.
    """
    found_path = _find_best_cache_object_path(mod, obj_name, asset_name=asset_name)
    if not found_path:
        return False, getattr(mod, 'object_path', ''), getattr(mod, 'object_path', '')

    old_path = getattr(mod, 'object_path', '')
    if old_path != found_path:
        mod.object_path = found_path
    return True, old_path, found_path


def _get_name_base(value):
    if hasattr(value, "name"):
        value = value.name
    return str(value or "").split(".")[0]


def _iter_object_tree(root_obj):
    yield root_obj
    for child in getattr(root_obj, "children", []):
        yield from _iter_object_tree(child)


def _find_child_object_by_base_name(parent_obj, target_name):
    target_base = _get_name_base(target_name).lower()
    for child in getattr(parent_obj, "children", []):
        if _get_name_base(child).lower() == target_base:
            return child
    return None


def resolve_asset_geometry_root(collection, asset_name):
    if not collection:
        return None

    asset_base = _get_name_base(asset_name).lower()

    for obj in collection.all_objects:
        try:
            if obj.get("rr_role") == "geometry_root" and str(obj.get("rr_asset", "")).lower() == asset_base:
                return obj
        except Exception:
            pass

    top_level_asset_root = None
    for obj in collection.objects:
        if _get_name_base(obj).lower() == asset_base:
            top_level_asset_root = obj
            break

    if not top_level_asset_root:
        return None

    geometry_node = None
    for child in top_level_asset_root.children:
        child_base = _get_name_base(child).lower()
        if child_base in {"geometry", "geo"}:
            geometry_node = child
            break

    if not geometry_node:
        return None

    inner_asset_root = _find_child_object_by_base_name(geometry_node, asset_name)
    target_root = inner_asset_root or geometry_node

    try:
        target_root["rr_role"] = "geometry_root"
        target_root["rr_asset"] = _get_name_base(asset_name)
    except Exception:
        pass

    return target_root


def iter_asset_geometry_meshes(collection, asset_name):
    geometry_root = resolve_asset_geometry_root(collection, asset_name)
    if geometry_root:
        yielded = False
        for obj in _iter_object_tree(geometry_root):
            if getattr(obj, "type", None) == 'MESH':
                yielded = True
                yield obj
        if yielded:
            return

    for obj in collection.all_objects:
        if getattr(obj, "type", None) == 'MESH':
            yield obj


def ensure_mesh_sequence_cache_binding(obj, usd_path, usd_file_name, asset_name=None, create_modifier=False, create_cache_file=False):
    if getattr(obj, "type", None) != 'MESH':
        return None, None

    mod = next((m for m in obj.modifiers if m.type == 'MESH_SEQUENCE_CACHE'), None)
    if not mod and create_modifier:
        try:
            mod = obj.modifiers.new(name="MeshSequenceCache", type='MESH_SEQUENCE_CACHE')
            print(f"[MSC] Created MeshSequenceCache on {obj.name}")
        except Exception as e:
            print(f"[MSC][WARN] Failed to create modifier on {obj.name}: {e}")
            return None, None

    if not mod:
        return None, None

    cache_file = getattr(mod, "cache_file", None)
    unique_name = f"{usd_file_name}_{obj.name}"
    fallback_cache_name = getattr(cache_file, "name", None) or usd_file_name
    if cache_file is None:
        if not create_cache_file:
            return mod, None
        cache_file = get_or_create_cache_file(unique_name, usd_path, fallback_name=usd_file_name, log_name=obj.name)
    elif _cache_file_needs_refresh(cache_file, usd_path):
        cache_file = _refresh_modifier_cache_file(
            mod,
            usd_path,
            unique_name,
            fallback_name=fallback_cache_name,
            log_name=obj.name,
        ) or cache_file

    if not cache_file:
        return mod, None

    try:
        cache_file.name = unique_name
    except Exception:
        pass
    cache_file.filepath = usd_path
    mod.cache_file = cache_file

    try:
        mod.read_data = {'VERT', 'UV', 'COLOR'}
    except Exception:
        pass

    try:
        matched, old_path, new_path = _sync_modifier_object_path_from_cache(mod, obj.name, asset_name=asset_name)
        if not matched:
            print(f"[MSC][WARN] Prim Path fallback failed: {obj.name} | keeping {old_path}")
    except Exception as e:
        print(f"[MSC][WARN] Prim Path sync failed: {obj.name} ({e})")

    return mod, cache_file


def get_or_create_cache_file(name, usd_path, fallback_name=None, log_name=None):
    cache_file = bpy.data.cache_files.get(name)
    if cache_file:
        cache_file.filepath = usd_path
        return cache_file

    if fallback_name:
        cache_file = bpy.data.cache_files.get(fallback_name)
        if cache_file:
            cache_file.filepath = usd_path
            try:
                cache_file.name = name
            except Exception:
                pass
            return cache_file

    load_fn = getattr(bpy.data.cache_files, "load", None)
    if callable(load_fn):
        try:
            cache_file = load_fn(usd_path)
        except RuntimeError:
            cache_file = bpy.data.cache_files.get(fallback_name) if fallback_name else None
        except Exception as e:
            print(f"[MSC][WARN] Failed to load cache file for {log_name or name}: {e}")
            cache_file = None
        if cache_file:
            try:
                cache_file.name = name
            except Exception:
                pass
            cache_file.filepath = usd_path
            return cache_file

    new_fn = getattr(bpy.data.cache_files, "new", None)
    if callable(new_fn):
        try:
            cache_file = new_fn(name=name)
            cache_file.filepath = usd_path
            return cache_file
        except Exception as e:
            print(f"[MSC][WARN] Failed to create cache file for {log_name or name}: {e}")
            return None

    print(f"[MSC][WARN] Cache file API unavailable for {log_name or name}")
    return None


def _cache_file_needs_refresh(cache_file, usd_path):
    if not cache_file:
        return True
    current_path = str(getattr(cache_file, "filepath", "") or "").replace("\\", "/")
    target_path = str(usd_path or "").replace("\\", "/")
    if current_path != target_path:
        return True
    try:
        object_paths = [p.path for p in cache_file.object_paths if getattr(p, "path", None)]
        return not bool(object_paths)
    except Exception:
        return True


def _refresh_modifier_cache_file(mod, usd_path, unique_name, fallback_name=None, log_name=None):
    fresh_cache = get_or_create_cache_file(unique_name, usd_path, fallback_name=fallback_name, log_name=log_name)
    if fresh_cache:
        try:
            fresh_cache.filepath = usd_path
        except Exception:
            pass
        try:
            mod.cache_file = fresh_cache
        except Exception:
            pass
    return fresh_cache


def apply_cache_to_asset_geometry(collection, asset_name, usd_path, usd_file_name, create_modifier=False, create_cache_file=False):
    for obj in iter_asset_geometry_meshes(collection, asset_name):
        ensure_mesh_sequence_cache_binding(
            obj,
            usd_path,
            usd_file_name,
            asset_name=asset_name,
            create_modifier=create_modifier,
            create_cache_file=create_cache_file,
        )


def append_named_node_group_from_blend(blend_path, preferred_name):
    existing_group = bpy.data.node_groups.get(preferred_name)
    if existing_group:
        try:
            existing_group.use_fake_user = True
        except Exception:
            pass
        return existing_group

    loaded_group_name = None
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        matches = [name for name in data_from.node_groups if name == preferred_name]
        if not matches:
            matches = [name for name in data_from.node_groups if str(name).startswith(preferred_name)]
        if matches:
            loaded_group_name = matches[0]
            data_to.node_groups = [loaded_group_name]

    if loaded_group_name:
        group = bpy.data.node_groups.get(loaded_group_name)
        if group:
            try:
                group.use_fake_user = True
            except Exception:
                pass
            print(f"[P4] Appended node group: {loaded_group_name}")
        return group

    print(f"[P4][WARN] Node group not found in publish blend: {preferred_name}")
    return None


def append_published_asset_with_cache(blend_path, category_name, asset_name, context, usd_path=None, usd_file_name=""):
    target_col_name = f"{asset_name}_col"
    light_col_name = f"{asset_name}_light_col"
    p4_node_tree_name = f"{asset_name}_p4"

    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        cols_to_import = []
        if target_col_name in data_from.collections:
            cols_to_import.append(target_col_name)
        if light_col_name in data_from.collections:
            cols_to_import.append(light_col_name)
        data_to.collections = cols_to_import

    if not data_to.collections:
        raise ValueError(f"Collection not found in publish file: {target_col_name}")

    append_named_node_group_from_blend(blend_path, p4_node_tree_name)

    parent_col_name = f"{category_name}_col"
    parent_col = bpy.data.collections.get(parent_col_name)
    if not parent_col:
        parent_col = bpy.data.collections.new(parent_col_name)
        context.scene.collection.children.link(parent_col)

    bound_cache_name = usd_file_name or os.path.basename(str(usd_path or ""))
    for imported_col in data_to.collections:
        if not imported_col:
            continue
        if imported_col.name not in parent_col.children:
            parent_col.children.link(imported_col)
        if usd_path and "light" not in imported_col.name.lower():
            apply_cache_to_asset_geometry(
                imported_col,
                asset_name,
                usd_path,
                bound_cache_name,
                create_modifier=False,
                create_cache_file=False,
            )


def update_usd_cache(usd_path, objects):
    import os
    usd_path = usd_path.replace("\\", "/")
    usd_file_name = os.path.basename(usd_path)

    print(f"[DEBUG] update_usd_cache for {[obj.name for obj in objects]}")

    for obj in objects:
        if obj.type != 'MESH':
            continue

        print(f"[DEBUG] Updating: {obj.name}")

        mod = next((m for m in obj.modifiers if m.type == 'MESH_SEQUENCE_CACHE'), None)
        if not mod:
            print(f"[SKIP] No MeshSequenceCache on {obj.name}; existing modifier only policy.")
            continue

        cache = get_or_create_cache_file(usd_file_name, usd_path, fallback_name=usd_file_name, log_name=obj.name)
        if cache:
            mod.cache_file = cache

        if mod.cache_file:
            mod.cache_file.filepath = usd_path
            mod.cache_file.name = usd_file_name

        matched, old_path, new_path = _sync_modifier_object_path_from_cache(mod, obj.name)
        if matched:
            print(f"[✅] Cache linked to {obj.name} → {usd_path} | object_path={new_path}")
        else:
            print(f"[WARN] {obj.name}: matching object_path not found in cache_file.object_paths, keeping existing path: {old_path}")



class SF_MaterialSwitcherProperties(bpy.types.PropertyGroup):
    use_existing_materials: bpy.props.BoolProperty(
        name="Use Existing Materials",
        default=True
    )

    import_mode: bpy.props.EnumProperty(
        name="Import Mode",
        description="어셋 임포트 방식",
        items=[
            ('AS_NEW', "As New", "기존 어셋을 삭제하고 새로 불러오기"),
            ('USE_EXISTING', "Use Existing", "기존 어셋 유지, 머티리얼만 교체")
        ],
        default='USE_EXISTING'
    )
    
def get_usd_path(scene_number, cut_number, asset_name, project, category_name=None):
    project_name = normalize_project_name(project)
    prefix = get_project_prefix(project_name)

    # category_name이 비어있을 경우 기본값 보정
    if not category_name:
        category_name = "ch"

    cache_context = resolve_cache_context(scene_number, cut_number, bpy.context, project_name)
    cache_dir = cache_context["cache_dir"]
    scene_token = cache_context["scene_token"] or scene_number
    cut_token = cache_context["cut_token"] or cut_number
    usd_filename = f"{prefix}_{scene_token}_{cut_token}_{category_name}_{asset_name}.usd"
    return os.path.join(cache_dir, usd_filename).replace("\\", "/")

class SF_OT_ImportAndUpdateOperatorDSC(bpy.types.Operator):
    bl_idname = "sf.import_and_update_operator_dsc"
    bl_label = "Import and Update Asset (Final)"
    bl_description = "어셋이 없으면 Import하고, 있으면 USD 캐시를 갱신합니다."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import os
        scene = context.scene
        my_tool = scene.my_tool
        
        # 1. 프로젝트 설정
        try:
            project_name = get_current_project_name()
            prefix = get_project_prefix(project_name)
        except:
            project_name = "BTS"
            prefix = "BTS"

        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        updated_count = 0

        # 2. 선택된 어셋 처리
        for category in scene.sf_file_categories:
            for item in category.items:
                if not item.is_selected:
                    continue

                asset_name = item.name
                category_name = category.name

                # (A) USD 캐시 경로 계산
                usd_path = get_usd_path(scene_number, cut_number, asset_name, project_name, category_name)
                usd_filename = os.path.basename(usd_path)
                
                # USD 파일 존재 여부 확인
                has_usd = os.path.exists(usd_path)
                
                # 🔥 [수정 완료] 와일드카드 검색 시 정확한 카테고리와 어셋명 매칭 규칙 적용
                search_target = f"_{category_name}_{asset_name}.".lower()
                if not has_usd and os.path.exists(os.path.dirname(usd_path)):
                     for f in os.listdir(os.path.dirname(usd_path)):
                        if f.lower().endswith(".usd") and search_target in f.lower():
                            usd_path = os.path.join(os.path.dirname(usd_path), f).replace("\\", "/")
                            usd_filename = f
                            has_usd = True
                            break

                # (B) 컬렉션 확인
                asset_col_name = f"{asset_name}_col"
                asset_col = bpy.data.collections.get(asset_col_name)

                if not asset_col:
                    print(f"[Import] '{asset_name}' 씬에 없음 -> Import 시작")
                    blend_path = get_asset_blend_path(category_name, asset_name, project_name).replace("\\", "/")

                    if not os.path.exists(blend_path):
                        self.report({'ERROR'}, f"Source File Missing: {blend_path}")
                        print(f"[Fail] 소스 파일 없음: {blend_path}")
                        continue
                    
                    try:
                        self.append_and_link_cache_advanced(blend_path, category_name, asset_name, context, usd_path if has_usd else None, usd_filename)
                        updated_count += 1
                        print(f"[Success] '{asset_name}' Import & Sync 완료")
                    except Exception as e:
                        self.report({'ERROR'}, f"Import Failed: {asset_name} - {e}")
                        import traceback
                        traceback.print_exc()

                else:
                    print(f"[Update] '{asset_name}' 씬에 존재함 -> Cache Update")
                    if has_usd:
                        self.update_mesh_sequence_cache_recursive(asset_col, asset_name, usd_path, usd_filename)
                        updated_count += 1
                    else:
                        print(f"[Skip] USD 캐시가 없어서 업데이트 패스: {asset_name}")

        if updated_count > 0:
            self.report({'INFO'}, f"총 {updated_count}개 어셋 처리 완료")
        else:
            self.report({'WARNING'}, "처리된 어셋이 없습니다.")
            
        bpy.ops.sf.update_selected_operator_dsc()
        
        return {'FINISHED'}

    def append_and_link_cache_advanced(self, blend_path, cat_name, asset_name, context, usd_path, usd_file_name):
        target_col_name = f"{asset_name}_col"
        light_col_name = f"{asset_name}_light_col"
        
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            cols_to_import = []
            if target_col_name in data_from.collections:
                cols_to_import.append(target_col_name)
            if light_col_name in data_from.collections:
                cols_to_import.append(light_col_name)
            data_to.collections = cols_to_import

        if not data_to.collections:
            raise ValueError(f"파일 내에 '{target_col_name}' 컬렉션이 없습니다.")

        parent_col_name = f"{cat_name}_col"
        p_col = bpy.data.collections.get(parent_col_name)
        if not p_col:
            p_col = bpy.data.collections.new(parent_col_name)
            context.scene.collection.children.link(p_col)

        for imported_col in data_to.collections:
            if not imported_col: continue
            
            if imported_col.name not in p_col.children:
                p_col.children.link(imported_col)
            
            if usd_path and "light" not in imported_col.name:
                self.update_mesh_sequence_cache_recursive(imported_col, asset_name, usd_path, usd_file_name)

    def update_mesh_sequence_cache_recursive(self, collection, asset_name, usd_path, usd_file_name):
        for obj in iter_asset_geometry_meshes(collection, asset_name):
            self._apply_cache_to_object(obj, asset_name, usd_path, usd_file_name)

    def _get_existing_cache_file(self, obj):
        for m in obj.modifiers:
            if m.type == 'MESH_SEQUENCE_CACHE' and getattr(m, 'cache_file', None):
                return m.cache_file
        return None

    def _apply_cache_to_object(self, obj, asset_name, usd_path, usd_file_name):
        mod, cache_file = ensure_mesh_sequence_cache_binding(
            obj,
            usd_path,
            usd_file_name,
            asset_name=asset_name,
            create_modifier=False,
            create_cache_file=False,
        )
        if not mod:
            print(f"[SKIP] {obj.name}: 기존 MeshSequenceCache가 없어 갱신하지 않음")
            return
        if not cache_file:
            print(f"[SKIP] {obj.name}: 기존 cache_file이 없어 갱신하지 않음")
            
            
class SF_OT_ImportSelectedOperatorDSC(bpy.types.Operator):
    bl_idname = "sf.import_selected_operator_dsc"
    bl_label = "Import Selected (DSC Ver)"
    bl_description = "DSC용 퍼블리시 컬렉션 및 USD 캐시 자동 임포트"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        # layout.prop(self, "import_mode", expand=True)

    def execute(self, context):
        scene = context.scene
        my_tool = scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        project = "DSC"
        prefix = "DSC"

        for category in scene.sf_file_categories:
            for item in category.items:
                if not item.is_selected:
                    continue

                asset_name = item.name
                category_name = category.name
                main_col_name = f"{asset_name}_col"
                light_col_name = f"{asset_name}_light_col"
                collections_to_import = [main_col_name]
                if category_name == "ch":
                    collections_to_import.append(light_col_name)

                blend_path = get_published_blend_path(project, category_name, asset_name)
                usd_path = get_usd_path(scene_number, cut_number, asset_name, project)

                if os.path.exists(blend_path):
                    self.append_collections(blend_path, collections_to_import, category_name)
                    selected_objects = bpy.context.selected_objects[:]
                else:
                    self.report({'WARNING'}, f"⚠️ 퍼블리시/캐시 없음: {asset_name}")
                    continue

                self.ensure_collection_hierarchy(category_name, asset_name)
    
                for obj in selected_objects:
                    apply_matching_materials(obj)

        return {'FINISHED'}

    def delete_collections(self, collection_names):
        for col_name in collection_names:
            if col_name in bpy.data.collections:
                bpy.data.collections.remove(bpy.data.collections[col_name], do_unlink=True)

    def append_collections(self, blend_path, collection_names, category_name):
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            data_to.collections = [name for name in data_from.collections if name in collection_names]

        for col in data_to.collections:
            if col is None:
                continue

            target_col = bpy.data.collections.get(col.name)
            if not target_col:
                continue

            parent_col_name = f"{category_name}_col"
            parent_col = bpy.data.collections.get(parent_col_name)
            if not parent_col:
                parent_col = bpy.data.collections.new(parent_col_name)
                bpy.context.scene.collection.children.link(parent_col)

            if target_col.name not in parent_col.children:
                parent_col.children.link(target_col)

            if target_col.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(target_col)

    def import_usd(self, usd_path, asset_name):
        usd_args = {
            "filepath": usd_path,
            "import_materials": True,
            "import_usd_preview": False,
            "import_all_materials": False,
            "import_meshes": True,
            "read_mesh_uvs": True,
            "read_mesh_colors": True,
            "scale": 0.01,
        }

        if bpy.app.version >= (4, 4, 0):
            usd_args["apply_unit_conversion_scale"] = False

        safe_usd_import(**usd_args)

        bpy.context.view_layer.update()

        # 🔥 [수정 완료] 누락 방어
        imported_objs = [
            obj for obj in bpy.context.selected_objects
            if obj.name.split('.')[0].lower() == asset_name.lower()
        ]

        # Note: 원본 코드의 use_existing 변수 처리 관련 로직 방어를 위해 원본 구조 유지
        try:
            if not use_existing:
                col = bpy.data.collections.get(f"{asset_name}_col") or bpy.data.collections.new(f"{asset_name}_col")
                for obj in imported_objs:
                    for c in obj.users_collection:
                        c.objects.unlink(obj)
                    col.objects.link(obj)
        except NameError:
            pass

        return imported_objs

    def ensure_collection_hierarchy(self, category_name, asset_name):
        category_col_name = f"{category_name}_col"
        asset_col_name = f"{asset_name}_col"

        if category_col_name not in bpy.data.collections:
            category_col = bpy.data.collections.new(category_col_name)
            bpy.context.scene.collection.children.link(category_col)
        else:
            category_col = bpy.data.collections[category_col_name]

        if asset_col_name not in bpy.data.collections:
            asset_col = bpy.data.collections.new(asset_col_name)
        else:
            asset_col = bpy.data.collections[asset_col_name]

        if asset_col.name not in category_col.children:
            category_col.children.link(asset_col)

        if asset_col.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(asset_col)

# class SF_OT_UpdateSelectedOperatorDSC(bpy.types.Operator):
    # bl_idname = "sf.update_selected_operator_dsc"
    # bl_label = "Update Selected (DSC Ver)"
    # bl_description = (
        # "선택한 어셋의 USD 캐시 경로와 Parent Prim Path를 "
        # "씬/컷 기준으로 갱신합니다 (DSC 전용, 인스턴스 대응)"
    # )

    # def execute(self, context):
        # import os
        # scene = context.scene
        # my_tool = scene.my_tool
        # scene_number = my_tool.scene_number
        # cut_number = my_tool.cut_number
        # prefix = "DSC"
        # updated_count = 0

        # for category in scene.sf_file_categories:
            # for item in category.items:
                # if not item.is_selected:
                    # continue  # ✅ 선택된 애셋만 갱신

                # asset_name    = item.name                        # ex: partition
                # base_name     = get_asset_base_name(asset_name)  # ex: partition
                # category_name = category.name

                # usd_filename = f"{prefix}_{scene_number}_{cut_number}_{category_name}_{asset_name}.usd"
                # usd_path = os.path.join("S:/scenes", scene_number, cut_number, "ren", "cache", usd_filename)
                # usd_path = usd_path.replace("\\", "/")  # ✅ 경로 정리

                # found = False

                # # ----------------------------------------------------------
                # # Step 1: CacheFile 갱신 (asset_name 기준만!)
                # # ----------------------------------------------------------
                # for cache in bpy.data.cache_files:
                    # if cache.name == usd_filename:
                        # print(f"[UPDATE] 🔁 CacheFile: '{cache.name}' → {usd_path}")
                        # cache.filepath = usd_path
                        # cache.name = usd_filename
                        # updated_count += 1
                        # found = True
                        # break

                # # ----------------------------------------------------------
                # # Step 2: MeshSequenceCache 모디파이어 갱신 + Prim Path 교체
                # # ----------------------------------------------------------
                # for obj in bpy.data.objects:
                    # for mod in obj.modifiers:
                        # if mod.type == 'MESH_SEQUENCE_CACHE' and mod.cache_file:

                            # # ✅ CacheFile 독립 복제
                            # unique_name = f"{usd_filename}_{obj.name}"
                            # if unique_name not in bpy.data.cache_files:
                                # cf = mod.cache_file.copy()
                                # cf.name = unique_name
                                # cf.filepath = usd_path
                                # print(f"[NEW] CacheFile 복제 생성: {cf.name}")
                            # else:
                                # cf = bpy.data.cache_files[unique_name]
                                # cf.filepath = usd_path
                                # print(f"[REUSE] CacheFile 재사용: {cf.name}")

                            # mod.cache_file = cf

                            # # ✅ Prim Path 갱신
                            # try:
                                # old_path = mod.object_path
                                # parts = old_path.split('/')
                                # if len(parts) > 1:
                                    # parts[1] = asset_name
                                    # new_path = '/'.join(parts)
                                # else:
                                    # new_path = f"/{asset_name}"

                                # mod.object_path = new_path
                                # print(f"[UPDATE] 🪢 Prim Path: {obj.name} | {old_path} → {new_path}")
                            # except Exception as e:
                                # print(f"[WARN] Prim Path 갱신 실패: {obj.name} ({e})")

                            # updated_count += 1
                            # found = True



                # # ----------------------------------------------------------
                # # Step 3: base_name fallback (asset_name이 씬에 없을 때만)
                # # ----------------------------------------------------------
                # if not found:
                    # for cache in bpy.data.cache_files:
                        # if base_name in cache.name:
                            # print(f"[FALLBACK] 🔁 CacheFile base 매칭: '{cache.name}' → {usd_path}")
                            # cache.filepath = usd_path
                            # cache.name = usd_filename
                            # updated_count += 1
                            # found = True
                            # break

                # if not found:
                    # self.report({'WARNING'}, f"⚠️ 캐시 갱신 실패: {asset_name} → {usd_filename}")

        # # ----------------------------------------------------------
        # # 결과 메시지
        # # ----------------------------------------------------------
        # if updated_count == 0:
            # self.report({'WARNING'}, "선택된 어셋에 대해 갱신된 캐시가 없습니다.")
        # else:
            # self.report({'INFO'}, f"✅ 총 {updated_count}개의 캐시 경로/Prim Path를 갱신했습니다.")

        # return {'FINISHED'}

class SF_OT_UpdateSelectedOperatorDSC(bpy.types.Operator):
    bl_idname = "sf.update_selected_operator_dsc"
    bl_label = "Update Selected (Final Fix)"
    bl_description = "선택된 어셋(BG 포함)의 원본을 대조하여 정확한 메쉬에만 USD 캐시를 연결합니다."
    bl_options = {'REGISTER', 'UNDO'}

    def get_blend_file_path(self, base_path, asset_name, category_name):
        """원본 자산의 위치를 찾아오는 로직"""
        import os
        return os.path.join(base_path, "assets", category_name, asset_name, "mod", f"{asset_name}.blend").replace("\\", "/")


    def execute(self, context):
        import os
        scene = context.scene
        my_tool = scene.my_tool
        
        # 1. 프로젝트 설정
        try:
            config = get_current_config()
            base_path = config['drive']
            prefix = config['prefix']
        except:
            base_path = "B:/"
            prefix = "BTS"

        sn, cn = my_tool.scene_number, my_tool.cut_number
        cache_dir = os.path.join(base_path, "scenes", sn, cn, "ren", "cache").replace("\\", "/")
        updated_count = 0

        # UI 선택 어셋 수집
        selected_assets = []
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    selected_assets.append((category.name, item.name))

        if not selected_assets:
            self.report({'WARNING'}, "선택된 어셋이 없습니다.")
            return {'CANCELLED'}

        # 2. 각 어셋 처리
        for cat_name, asset_name in selected_assets:
            
            # (A) 원본 데이터 파일에서 메쉬 이름 추출
            blend_file_path = self.get_blend_file_path(base_path, asset_name, cat_name)
            valid_mesh_names = []
            
            if os.path.exists(blend_file_path):
                try:
                    with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
                        # 🔥 [수정 완료] .split('.') 추가!
                        valid_mesh_names = [name.split('.')[0] for name in data_from.objects]
                except Exception as e:
                    print(f"[WARN] 원본 파일을 읽지 못함: {e}")
            else:
                print(f"[WARN] 원본 파일을 찾을 수 없음: {blend_file_path}")

            # (B) 캐시 USD 경로 찾기
            exact_name = f"{prefix}_{sn}_{cn}_{cat_name}_{asset_name}.usd"
            usd_path = os.path.join(cache_dir, exact_name).replace("\\", "/")
            
            search_target = f"_{cat_name}_{asset_name}.".lower()
            if not os.path.exists(usd_path) and os.path.exists(cache_dir):
                for f in os.listdir(cache_dir):
                    if f.lower().endswith(".usd") and search_target in f.lower():
                        usd_path = os.path.join(cache_dir, f).replace("\\", "/")
                        exact_name = f
                        break
            
            if not os.path.exists(usd_path):
                print(f"[Fail] USD 캐시 없음: {asset_name}")
                continue

            # (C) 오브젝트 깐깐하게 필터링
            target_objs = []
            asset_col = bpy.data.collections.get(f"{asset_name}_col")
            
            if asset_col:
                for obj in asset_col.all_objects:
                    if obj.type == 'MESH':
                        # 🔥 [수정 완료] .split('.') 추가!
                        base_obj_name = obj.name.split('.')[0]
                        
                        if valid_mesh_names and base_obj_name in valid_mesh_names:
                            target_objs.append(obj)
                        elif not valid_mesh_names and base_obj_name.startswith(asset_name):
                            target_objs.append(obj)

            if not target_objs:
                print(f"[Fail] 원본과 일치하는 메쉬가 씬에 없음: {asset_name}")
                continue

            # (D) 모디파이어 안전 적용
            applied = False
            for obj in target_objs:
                mod = None
                for m in obj.modifiers:
                    if m.type == 'MESH_SEQUENCE_CACHE':
                        mod = m
                        break

                if not mod:
                    print(f"[SKIP] {obj.name}: MeshSequenceCache 모디파이어가 없어 캐시 경로만 갱신하지 못함")
                    continue

                cf = getattr(mod, 'cache_file', None)
                if not cf:
                    print(f"[SKIP] {obj.name}: 기존 cache_file 데이터블록이 없어 캐시 경로만 갱신하지 못함")
                    continue

                cf.name = exact_name
                cf.filepath = usd_path

                # USD Prim Path 보정: cache_file.object_paths에서 오브젝트 이름으로 검색
                try:
                    matched, old_path, new_path = _sync_modifier_object_path_from_cache(mod, obj.name, asset_name=asset_name)
                    if not matched:
                        print(f"[WARN] Prim Path 검색 실패: {obj.name} | 기존 경로 유지: {old_path}")
                except Exception as e:
                    print(f"[WARN] Prim Path 검색/적용 실패: {obj.name} ({e})")

                applied = True

                if applied:
                    updated_count += 1
                    print(f"[Success] {asset_name} 싱크 완료")

        self.report({'INFO'}, f"✅ 총 {updated_count}개 어셋 캐시 연결 완료")
        return {'FINISHED'}

################################################################
######################### Line Art #############################
################################################################
def _run_without_global_undo(callback):
    prefs = getattr(bpy.context, "preferences", None)
    edit_prefs = getattr(prefs, "edit", None)
    if edit_prefs is None or not hasattr(edit_prefs, "use_global_undo"):
        return callback()

    original = bool(edit_prefs.use_global_undo)
    try:
        if original:
            edit_prefs.use_global_undo = False
        return callback()
    finally:
        try:
            edit_prefs.use_global_undo = original
        except Exception:
            pass


def _modern_update_selected_operator_dsc_execute(self, context):
    def _execute_sync():
        scene = context.scene
        my_tool = scene.my_tool

        try:
            project_name = get_current_project_name()
        except Exception:
            project_name = "BTS"

        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        updated_count = 0

        selected_assets = []
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    selected_assets.append((category.name, item.name))

        if not selected_assets:
            self.report({'WARNING'}, "선택된 어셋이 없습니다.")
            return {'CANCELLED'}

        for cat_name, asset_name in selected_assets:
            usd_path = get_usd_path(scene_number, cut_number, asset_name, project_name, cat_name)
            usd_filename = os.path.basename(usd_path)
            has_usd = os.path.exists(usd_path)

            search_target = f"_{cat_name}_{asset_name}.".lower()
            usd_dir = os.path.dirname(usd_path)
            if not has_usd and os.path.exists(usd_dir):
                for f in os.listdir(usd_dir):
                    if f.lower().endswith(".usd") and search_target in f.lower():
                        usd_path = os.path.join(usd_dir, f).replace("\\", "/")
                        usd_filename = f
                        has_usd = True
                        break

            if not has_usd:
                print(f"[Skip] USD cache not found: {asset_name} -> {usd_path}")
                continue

            asset_col = bpy.data.collections.get(f"{asset_name}_col")
            if not asset_col:
                print(f"[Skip] Collection not found: {asset_name}_col")
                continue

            before_count = updated_count
            for obj in iter_asset_geometry_meshes(asset_col, asset_name):
                mod, cache_file = ensure_mesh_sequence_cache_binding(
                    obj,
                    usd_path,
                    usd_filename,
                    asset_name=asset_name,
                    create_modifier=False,
                    create_cache_file=False,
                )
                if not mod or not cache_file:
                    continue
                updated_count += 1

            if updated_count == before_count:
                print(f"[Skip] No existing MeshSequenceCache/cache_file found to refresh: {asset_name}")

        if updated_count == 0:
            self.report({'WARNING'}, "갱신된 캐시가 없습니다.")
        else:
            self.report({'INFO'}, f"총 {updated_count}개 어셋 캐시 연결 완료")
        return {'FINISHED'}

    return _run_without_global_undo(_execute_sync)


SF_OT_UpdateSelectedOperatorDSC.execute = _modern_update_selected_operator_dsc_execute
SF_OT_UpdateSelectedOperatorDSC.bl_options = {'REGISTER'}


def get_latest_black_material():
    # "Black."으로 시작하는 재료 중 가장 최신의 것을 찾아 반환
    black_materials = [mat for mat in bpy.data.materials if mat.name.startswith("Black.")]
    black_materials.sort(key=lambda m: m.name, reverse=True)
    return black_materials[0] if black_materials else None


class LineArtGenerator(bpy.types.Operator):
    """Generate Line Art"""
    bl_idname = "object.line_art_generator"
    bl_label = "Generate Line Art"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        create_line_art_with_single_modifier()
        return {'FINISHED'}

class LineArtPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Line Art Generator"
    bl_idname = "OBJECT_PT_line_art"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator(LineArtGenerator.bl_idname)



################################################################
######################### Extras ###############################
################################################################



class SF_CleanupOrphansCombined(bpy.types.Operator):
    bl_idname = "sf.cleanup_orphans_combined1"
    bl_label = "Clean Up Orphans (Combined)"

    def execute(self, context):
        # 첫 번째 조건: 로컬 및 링크드 데이터 블록 모두 정리하지 않음
        bpy.ops.outliner.orphans_purge(do_recursive=True, do_local_ids=False, do_linked_ids=False)

        # 두 번째 조건: 로컬 데이터 블록만 정리
        bpy.ops.outliner.orphans_purge(do_recursive=True, do_local_ids=True, do_linked_ids=False)

        # 세 번째 조건: 링크드 데이터 블록만 정리
        bpy.ops.outliner.orphans_purge(do_recursive=True, do_local_ids=False, do_linked_ids=True)
        # node_group_linker = NodeGroupLinker("SF_paint", r"M:\e_utility\blender\shaders\sf_paint.blend")
        # node_group_linker.link_node_group()  # 노드 그룹 링크
        # node_group_linker.update_materials()  # 메터리얼 업데이트
        bpy.ops.object.delete_all_fake_users()
        return {'FINISHED'}
        
def get_latest_file_version(scene_number, cut_number):
    # 글로벌 변수 base_path를 직접 사용합니다.
    base_path = get_project_paths()
    full_path = os.path.join(base_path, "scenes", str(scene_number), str(cut_number), "ren")
    if not os.path.exists(full_path):
        return "No Render File"

    # 파일 목록 가져오기
    files = os.listdir(base_path)
    project_prefix = get_project_prefix()  # 현재 프로젝트의 식별자를 얻습니다.

    # 정규 표현식 패턴 설정
    pattern = re.compile(rf"{re.escape(project_prefix)}_" + re.escape(scene_number) + r"_" + re.escape(cut_number) + r"_ren_v(\d+)")

    versions = []

    for file in files:
        match = pattern.match(file)
        if match:
            versions.append(int(match.group(1)))

    if not versions:
        return "No Render File"

    latest_version = max(versions)
    return f"v{str(latest_version).zfill(3)}"


def is_root_work_dir_name(work_dir_name):
    return str(work_dir_name or "").strip() in {"", ".", "./", "\\"}


def get_scene_save_directory(scene_number, cut_number, project_name=None):
    project_name = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    base_path = build_browser_base_path(scene_number, cut_number, project_name)
    work_dir_name = get_project_ren_dir_name(project_name)
    if is_root_work_dir_name(work_dir_name):
        return base_path
    return os.path.join(base_path, work_dir_name)


def build_scene_save_file_stem(scene_number, cut_number, project_name=None):
    project_name = get_current_project_name() if project_name is None else normalize_project_name(project_name)
    project_prefix = get_project_prefix(project_name)
    scene_token = str(scene_number or "").strip()
    cut_token = str(cut_number or "").strip()
    work_dir_name = get_project_ren_dir_name(project_name)

    if get_scene_identifier_mode(project_name) == "filename" or is_root_work_dir_name(work_dir_name):
        return f"{project_prefix}_{scene_token}_{cut_token}_"
    return f"{project_prefix}_{scene_token}_{cut_token}_{work_dir_name}_"


def build_scene_save_filename(scene_number, cut_number, version="v000", project_name=None):
    return f"{build_scene_save_file_stem(scene_number, cut_number, project_name)}{version}.blend"
    

class SF_SaveRenderScene(bpy.types.Operator):
    bl_idname = "sf.save_render_scene"
    bl_label = "Save Render Scene"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        scene = context.scene
        my_tool = scene.my_tool
        self.scene_number = my_tool.scene_number if my_tool else 'default'
        self.cut_number = my_tool.cut_number if my_tool else 'default'
        base_path = get_project_paths()

        self.base_path = os.path.join(base_path, "scenes", self.scene_number, self.cut_number, "ren")
        project_prefix = get_project_prefix()  # 현재 프로젝트의 식별자를 얻습니다.
        self.file_name = f"{project_prefix}_{self.scene_number}_{self.cut_number}_ren_v000.blend"

        self.full_path = os.path.join(self.base_path, self.file_name)

        if os.path.exists(self.full_path):
            # 파일이 이미 존재하는 경우, 사용자에게 덮어쓰기 여부를 묻는다.
            return context.window_manager.invoke_confirm(self, event)
        else:
            return self.execute(context)

    def execute(self, context):
        # 디렉터리 생성 (경로가 존재하지 않는 경우)
        # os.makedirs(self.base_path, exist_ok=True)

        # 현재 씬을 self.full_path로 저장
        try:
            bpy.ops.wm.save_as_mainfile(filepath=self.full_path)
            self.report({'INFO'}, f"Scene saved to {self.full_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save scene: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}




# 버전 정보를 유지하기 위한 전역 변수
def _sf_save_render_scene_invoke(self, context, event):
    scene = context.scene
    my_tool = scene.my_tool
    self.scene_number = my_tool.scene_number if my_tool else 'default'
    self.cut_number = my_tool.cut_number if my_tool else 'default'
    self.project_name = get_current_project_name()
    self.base_path = get_scene_save_directory(self.scene_number, self.cut_number, self.project_name)
    self.file_name = build_scene_save_filename(self.scene_number, self.cut_number, "v000", self.project_name)
    self.full_path = os.path.join(self.base_path, self.file_name)

    if os.path.exists(self.full_path):
        return context.window_manager.invoke_confirm(self, event)
    return self.execute(context)


def _sf_save_render_scene_execute(self, context):
    os.makedirs(self.base_path, exist_ok=True)

    try:
        bpy.ops.wm.save_as_mainfile(filepath=self.full_path)
        self.report({'INFO'}, f"Scene saved to {self.full_path}")
    except Exception as e:
        self.report({'ERROR'}, f"Failed to save scene: {e}")
        return {'CANCELLED'}

    return {'FINISHED'}


SF_SaveRenderScene.invoke = _sf_save_render_scene_invoke
SF_SaveRenderScene.execute = _sf_save_render_scene_execute


current_version = 1

def update_version(context, increment):
    global current_version  # 전역 변수 사용 선언

    # 현재 씬의 기본 파일 경로, 최신 버전(+1), 그리고 기본 버전 가져오기
    original_path, new_path, default_version = get_base_filepath(context.scene)
    base_path = get_project_paths()
    
    if increment == -999:  # "Current" 버튼을 누른 경우
        current_version = int(default_version[1:])
    else:
        # "Dn" 버튼을 누르면 버전이 1이 될 때까지 계속 내려가고, "Up" 버튼을 누르면 버전이 계속 올라가는 것
        if increment < 0:  # "Dn" 버튼을 누른 경우
            current_version = max(1, current_version + increment)
        else:  # "Up" 버튼을 누른 경우
            current_version += increment

    new_version = f"v{str(current_version).zfill(3)}"

    # 파일 경로 업데이트
    context.scene.render.filepath = re.sub(default_version, new_version, original_path)

    # 씬 안의 모든 File Output 노드 경로 수정
    # Blender 4.x: scene.node_tree
    # Blender 5.x: scene.compositing_node_group
    tree = get_scene_compositor_tree(context.scene, create=False)
    if tree:
        for node in tree.nodes:
            if node.type == 'OUTPUT_FILE':
                set_file_output_node_base_path(
                    node,
                    re.sub(default_version, new_version, new_path),
                    label="update_version: ",
                )


class SF_OT_VersionOperator(bpy.types.Operator):
    bl_idname = "sf.version_operator"
    bl_label = "Version Operator"
    increment: bpy.props.IntProperty()

    def execute(self, context):
        update_version(context, self.increment)
        return {'FINISHED'}

# class IncrementalSaveOperator(Operator):
    # bl_idname = "scene.incremental_save"
    # bl_label = "Incremental Save"

    # def execute(self, context):
        # # 현재 파일의 경로와 이름을 가져옵니다.
        # current_filepath = bpy.data.filepath

        # # 'Incremental Save'를 수행합니다.
        # bpy.ops.wm.save_mainfile(filepath=current_filepath, incremental=True)

        # self.report({'INFO'}, "Incremental save completed.")
        # return {'FINISHED'}
        
class IncrementalSaveOperator(bpy.types.Operator):
    bl_idname = "scene.incremental_save"
    bl_label = "Incremental Save"

    def execute(self, context):
        filepath = bpy.data.filepath
        if not filepath:
            self.report({'ERROR'}, "현재 저장된 .blend 파일이 없습니다.")
            return {'CANCELLED'}

        next_filepath = build_incremental_save_filepath(filepath)
        if not next_filepath:
            self.report({'ERROR'}, "다음 인크리멘탈 파일 경로를 만들 수 없습니다.")
            return {'CANCELLED'}

        bpy.ops.wm.save_as_mainfile(filepath=next_filepath, copy=False)
        self.report({'INFO'}, f"Saved incremental file: {os.path.basename(next_filepath)}")
        return {'FINISHED'}


def build_incremental_save_filepath(filepath, suffix_override=None):
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    stem, extension = os.path.splitext(filename)

    match = re.search(r"(?i)^(.*?)(v(\d{3}))(?:_([^.]+))?$", stem)
    if not match:
        return None

    prefix_part = match.group(1)
    current_suffix = match.group(4) or ""
    desired_suffix = current_suffix if suffix_override is None else str(suffix_override).strip()

    pattern = re.compile(rf"(?i)^{re.escape(prefix_part)}v(\d{{3}})(?:_([^.]+))?{re.escape(extension)}$")
    highest_version = 0

    if os.path.exists(directory):
        for file_name in os.listdir(directory):
            matched = pattern.match(file_name)
            if not matched:
                continue
            file_suffix = matched.group(2) or ""
            if file_suffix != desired_suffix:
                continue
            highest_version = max(highest_version, int(matched.group(1)))

    next_version = highest_version + 1 if highest_version else int(match.group(3)) + 1
    version_text = f"v{next_version:03d}"
    new_stem = f"{prefix_part}{version_text}"
    if desired_suffix:
        new_stem += f"_{desired_suffix}"

    return os.path.join(directory, new_stem + extension)


ADDON_PATH = "M:/RND/SFtools/2023/render/rrRender.py"
ADDON_NAME = "rrRender"

class WM_OT_ReinstallAddon1(bpy.types.Operator):
    bl_label = "Reinstall Addon1"
    bl_idname = "wm.reinstall_addon_operator1"

    def execute(self, context):
        try:
            self.reinstall_addon(context)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}

    def reinstall_addon(self, context):
        # Get the user scripts path for addons
        user_scripts_path = bpy.utils.user_resource('SCRIPTS')
        if not user_scripts_path:
            self.report({'ERROR'}, "User scripts path could not be determined.")
            raise Exception("User scripts path could not be determined.")
        
        # Define the destination path
        dest_path = os.path.join(user_scripts_path, "addons", os.path.basename(ADDON_PATH))

        # Copy the addon file
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy(ADDON_PATH, dest_path)
            self.report({'INFO'}, f"Successfully copied {os.path.basename(ADDON_PATH)} to {dest_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy {os.path.basename(ADDON_PATH)}: {e}")
            raise Exception(f"Failed to copy {os.path.basename(ADDON_PATH)}: {e}")

        # Reload the addon
        self.reload_addon(context)


    def reload_addon(self, context):
        if ADDON_NAME in bpy.context.preferences.addons:
            bpy.ops.preferences.addon_disable(module=ADDON_NAME)
            self.report({'INFO'}, f"Disabled {ADDON_NAME}")

        # Ensure the addon module is not loaded
        if ADDON_NAME in sys.modules:
            del sys.modules[ADDON_NAME]
            self.report({'INFO'}, f"Removed {ADDON_NAME} from sys.modules")

        # Load the addon module again
        try:
            bpy.ops.preferences.addon_enable(module=ADDON_NAME)
            self.report({'INFO'}, f"Enabled {ADDON_NAME}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to reload {ADDON_NAME}: {e}")
            raise Exception(f"Failed to reload {ADDON_NAME}: {e}")




# 프리셋 선택을 위한 EnumProperty 정의
def preset_items(self, context):
    # 'floor0F', 'floor1F', ...의 형식으로 이름 지정
    return [(f"floor{i}F", f"floor {i}F", f"Apply floor {i}F preset") for i in range(8)]

bpy.types.Scene.preset_selection = bpy.props.EnumProperty(
    name="Preset",
    description="Select a preset to apply",
    items=preset_items
)

class SF_OT_ApplyPreset(bpy.types.Operator):
    bl_label = "Apply Preset"
    bl_idname = "sf.apply_preset"

    preset_name: bpy.props.StringProperty()  # UI에서 선택된 프리셋 이름
    asset_names: bpy.props.StringProperty()  # 콤마로 구분된 선택된 어셋 이름들

    def execute(self, context):
        print("Starting execution of SF_OT_ApplyPreset")
        
        base_path = get_project_paths()
        asset_names_list = self.asset_names.split(',')  # 문자열을 리스트로 변환
        json_file_path = os.path.join(base_path, "_json", f"{self.preset_name}_preset.json")
        blend_file_path = ""  # 초기화
        self.delete_unused_worlds()
        print("json_file_path:", json_file_path)
        
        try:
            with open(json_file_path, 'r') as file:
                preset_data = json.load(file)
            blend_file_path = os.path.join(base_path, "assets", "bg", self.preset_name, "mod", f"{self.preset_name}.blend")
            print("Blend file path:", blend_file_path)
        except Exception as e:
            print(f"Error before setting blend_file_path: {e}")
            self.report({'ERROR'}, f"Failed to load preset data: {e}")
            return {'CANCELLED'}

        if not blend_file_path:
            print("blend_file_path not set due to previous error")
            return {'CANCELLED'}

        for asset_name in asset_names_list:
            light_object_name = f"{asset_name}_light"
            light_object = bpy.data.objects.get(light_object_name)
            if light_object:
                for prop_name, value in preset_data.get(asset_name, {}).items():
                    light_object[prop_name] = value
        # self.append_world(blend_file_path, f"{self.preset_name}_world", context)
        loaded_world = self.append_world(blend_file_path, f"{self.preset_name}_world", context)
        self.set_world_to_scene(loaded_world)
        self.delete_unused_worlds()
        _disable_default_view_layer(bpy.context.scene)
        
        return {'FINISHED'}

    def append_world(self, blend_path, world_name, context):
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            if world_name in data_from.worlds:
                data_to.worlds = [world_name]
                print(f"World '{world_name}' loaded successfully from '{blend_path}'")
            else:
                print(f"World '{world_name}' not found in '{blend_path}'")
                return None
        return bpy.data.worlds.get(world_name)
        
    def set_world_to_scene(self, world):
        if world:
            bpy.context.scene.world = world
            print(f"World '{world.name}' is now set as the current scene world.")
        else:
            print("No world loaded to set to the scene.")
            
    def delete_unused_worlds(self):
        # 사용 중인 월드를 제외하고 모든 월드 삭제
        used_worlds = set(scene.world for scene in bpy.data.scenes if scene.world)
        all_worlds = set(bpy.data.worlds)
        # 사용 중이지 않은 월드만 삭제
        for world in all_worlds - used_worlds:
            bpy.data.worlds.remove(world, do_unlink=True)


# 렌더 세팅을 적용하는 연산자
class SF_OT_RenderSetting(bpy.types.Operator):
    bl_idname = "scene.render_setting"
    bl_label = "Apply Render Setting"

    mode: bpy.props.StringProperty()  # 'Preview' 또는 'Best' 설정을 위한 매개변수

    def execute(self, context):
        sc = context.scene
        engine = sc.render.engine

        # ------------------------------
        # EEVEE & EEVEE Next
        # ------------------------------
        if engine in {'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
            ee = getattr(sc, "eevee", None)

            if self.mode == 'Preview':
                try:
                    ee.shadow_cube_resolution = 4096
                    ee.use_shadow_high_bitdepth = False
                    sc.render.use_high_quality_normals = False
                    ee.taa_samples = 16
                    ee.gtao_quality = 1
                except AttributeError:
                    pass

            elif self.mode == 'Best':
                try:
                    # bpy.ops.sf.subdivide_class()
                    ee.shadow_cube_resolution = 4096
                    ee.use_shadow_high_bitdepth = True
                    sc.render.use_high_quality_normals = False
                    ee.taa_samples = 30
                    # bpy.ops.sf.subdivide_class()
                    ee.taa_render_samples = 30
                    ee.use_overscan = True
                    ee.overscan_size = 20
                    ee.ssr_border_fade = 0.001
                    ee.gtao_quality = 1
                except AttributeError:
                    pass

            else:
                self.report({'ERROR'}, f"Unknown mode: {self.mode}")
                return {'CANCELLED'}

        # ------------------------------
        # Cycles
        # ------------------------------
        elif engine == 'CYCLES':
            cy = getattr(sc, "cycles", None)

            if self.mode == 'Preview':
                try:
                    cy.samples = 64
                    cy.use_adaptive_sampling = True
                    cy.use_preview_denoising = True
                except AttributeError:
                    pass

            elif self.mode == 'Best':
                try:
                    cy.samples = 64
                    cy.use_adaptive_sampling = True
                    cy.use_preview_denoising = True
                except AttributeError:
                    pass

            else:
                self.report({'ERROR'}, f"Unknown mode: {self.mode}")
                return {'CANCELLED'}

        # ------------------------------
        # Other Engine
        # ------------------------------
        else:
            self.report({'WARNING'}, f"지원하지 않는 렌더 엔진: {engine}")
            return {'CANCELLED'}

        return {'FINISHED'}



  
class SF_OT_RefreshDriverDependencies(bpy.types.Operator):
    """Refresh Driver Dependencies"""
    bl_idname = "scene.refresh_driver_dependencies"
    bl_label = "Refresh Driver Dependencies"

    def execute(self, context):
        # 강제로 의존성 그래프 업데이트
        bpy.context.view_layer.update()
        self.report({'INFO'}, "Driver dependencies refreshed.")
        # bpy.ops.object.sf_add_properties_and_link1()
        # bpy.ops.object.sf_link_character_lights1()
        bpy.ops.object.link_rim_to_node1()
        # bpy.ops.sf.updatelightposition_class()
        return {'FINISHED'}


class SF_OT_GetSelectedAssetsOperator(bpy.types.Operator):
    bl_idname = "sf.get_selected_assets_operator"
    bl_label = "Get Selected Assets"

    @classmethod
    def poll(cls, context):
        return context.scene.sf_file_categories is not None

    def execute(self, context):
        all_assets = []
        ch_assets = []
        bg_assets = []
        prop_assets = []

        for category in context.scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    all_assets.append(item.name)
                    if category.name == 'ch':
                        ch_assets.append(item.name)
                    elif category.name == 'bg':
                        bg_assets.append(item.name)
                    elif category.name == 'prop':
                        prop_assets.append(item.name)


        # 필요에 따라 정보를 다른 방식으로 사용할 수 있습니다.
        return {'FINISHED'}

class SF_OT_SetStaticBG(bpy.types.Operator):
    bl_idname = "sf.set_static_bg"
    bl_label = "Set Static Background"

    def execute(self, context):
        scene = context.scene
        bg_vl = scene.view_layers.get('bg_vl')
        if bg_vl:
            # Ensure animation data exists
            if scene.animation_data and scene.animation_data.action:
                # Clear existing keyframes if any
                fcurves = [fcurve for fcurve in scene.animation_data.action.fcurves if fcurve.data_path == "view_layers[\"bg_vl\"].use"]
                for fcurve in fcurves:
                    scene.animation_data.action.fcurves.remove(fcurve)

            # Set the 'use' property to True
            bg_vl.use = True
            scene.frame_step = 1
        else:
            self.report({'WARNING'}, "ViewLayer 'bg_vl' not found")

        return {'FINISHED'}


class SF_OT_SetMovingBG(bpy.types.Operator):
    bl_idname = "sf.set_moving_bg"
    bl_label = "Set Moving Background"

    def execute(self, context):
        scene = context.scene
        bg_vl = scene.view_layers.get('bg_vl')
        if bg_vl:
            # Ensure animation data exists
            if scene.animation_data and scene.animation_data.action:
                # Clear existing keyframes if any
                fcurves = [fcurve for fcurve in scene.animation_data.action.fcurves if fcurve.data_path == "view_layers[\"bg_vl\"].use"]
                for fcurve in fcurves:
                    scene.animation_data.action.fcurves.remove(fcurve)

            # Set the 'use' property to True
            bg_vl.use = True
            scene.frame_step = 1
        else:
            self.report({'WARNING'}, "ViewLayer 'bg_vl' not found")

        return {'FINISHED'}

class SF_OT_SetViewLayerMode(bpy.types.Operator):
    bl_idname = "sf.set_view_layer_mode"
    bl_label = "Set View Layer Mode"
    
    mode: bpy.props.StringProperty()
    
    def add_suffix_to_filepath(self, suffix):
        scene = bpy.context.scene
        filepath = scene.render.filepath

        # 이미 접미사가 있는지 확인하고 제거
        filepath = filepath.replace("ch_", "").replace("bg_", "")

        # 새로운 접미사 추가
        filepath += suffix

        scene.render.filepath = filepath
    
    def execute(self, context):
        if self.mode == "ch_only":
            self.set_ch_only(context)
        elif self.mode == "bg_only":
            self.set_bg_only(context)
        elif self.mode == "all":
            self.set_all(context)
        elif self.mode == "viewlayer":
            self.set_viewlayer(context)
        
        return {'FINISHED'}
    
    def set_ch_only(self, context):
        scene = context.scene
        for vl in scene.view_layers:
            vl.use = vl.name.startswith('ch')
        scene.frame_step = 1
        self.disable_specific_view_layer(context, 'ViewLayer')
        self.add_suffix_to_filepath("ch_")
        
    def set_bg_only(self, context):
        scene = context.scene
        for vl in scene.view_layers:
            vl.use = not vl.name.startswith('ch')
        scene.frame_step = 1
        self.disable_specific_view_layer(context, 'ViewLayer')
        self.add_suffix_to_filepath("bg_")
        
    def set_all(self, context):
        scene = context.scene
        for vl in scene.view_layers:
            vl.use = True
        scene.frame_step = 1
        self.disable_specific_view_layer(context, 'ViewLayer')

        filepath = scene.render.filepath
        # "ch_" 또는 "bg_" 접미사가 있는 경우 제거
        if filepath.endswith("ch_") or filepath.endswith("bg_"):
            filepath = filepath[:-3]
        scene.render.filepath = filepath
        
    def set_viewlayer(self, context):
        scene = context.scene
        for vl in scene.view_layers:
            # 'ViewLayer' 뷰 레이어만 사용하고, 나머지는 사용하지 않도록 설정
            if vl.name == 'ViewLayer':
                vl.use = True
            else:
                vl.use = False
        scene.frame_step = 1

        filepath = scene.render.filepath
        # "ch_" 또는 "bg_" 접미사가 있는 경우 제거
        if filepath.endswith("ch_") or filepath.endswith("bg_"):
            filepath = filepath[:-3]
        scene.render.filepath = filepath

        
    def disable_specific_view_layer(self, context, layer_name):
        vl = context.scene.view_layers.get(layer_name)
        if vl:
            vl.use = False
            
import subprocess

def get_deadline_command():
    """이 함수는 Deadline의 명령 실행 파일 경로를 찾습니다."""
    deadline_bin = os.getenv('DEADLINE_PATH', '')
    if not deadline_bin and os.path.exists("/Users/Shared/Thinkbox/DEADLINE_PATH"):
        with open("/Users/Shared/Thinkbox/DEADLINE_PATH") as f:
            deadline_bin = f.read().strip()
    return os.path.join(deadline_bin, "deadlinecommand")


class SubmitBlenderToDeadline(bpy.types.Operator):
    """Blender 작업을 Deadline에 제출합니다."""
    bl_idname = "wm.submit_blender_to_deadline"
    bl_label = "Submit Blender to Deadline"

    def execute(self, context):
        import os, subprocess
        sc = context.scene

        try:
            bpy.ops.sf.set_light_bounces()
            print("[SUBMIT] SF_OT_SetLightBounces 실행 완료")
        except Exception as e:
            print(f"[SUBMIT ERROR] LightBounces 실행 실패: {e}")

        # --- 렌더링 설정 ---
        bpy.ops.file.make_paths_absolute()
        bpy.ops.scene.render_setting(mode='Best')

        # --- 씬 파일/프레임 범위/출력 경로/스레드 수 ---
        scene_file = bpy.data.filepath
        frame_range = f"{sc.frame_start}-{sc.frame_end}"
        output_path = sc.render.filepath
        threads = sc.render.threads if sc.render.threads_mode != 'AUTO' else 0
        platform = str(bpy.app.build_platform)

        # --- 외부 라이브러리 경로 치환 ---
        bpy.ops.object.replace_botaniq_library_path()
        bpy.ops.object.replace_sanctus_library_path()

        # --- Blender 버전에 따른 드롭다운 선택 ---
        major, minor, patch = bpy.app.version
        blender_version_str = f"{major}.{minor}"

        version_string = str(bpy.app.version_string).lower()
        build_info_raw = bpy.app.build_branch
        if isinstance(build_info_raw, bytes):
            build_info = build_info_raw.decode(errors="ignore").lower()
        else:
            build_info = str(build_info_raw).lower()

        if "goo" in version_string or "goo" in build_info:
            blender_version = "GOO"
        # elif "ssgi" in version_string or "ssgi" in build_info:
            # blender_version = "SSGI"
        # elif blender_version_str == "4.2":
            # blender_version = "42"
        elif blender_version_str == "4.3":
            blender_version = "43"
        elif blender_version_str == "4.5":
            blender_version = "45"
        else:
            blender_version = "43"  # fallback

        print(f"[INFO] Blender 실행 버전 감지: {bpy.app.version_string} ({build_info}) → Deadline 드롭다운 '{blender_version}' 선택")

        # --- Deadline 제출 인자 구성 ---
        script_file = self.get_repository_file_path("scripts/Submission/BlenderSubmission.py")

        args = [
            get_deadline_command(),
            "-ExecuteScript",
            script_file,
            scene_file,
            frame_range,
            output_path,
            str(threads),
            platform,
            blender_version
        ]

        print(f"Submitting to Deadline with Blender version: {blender_version}")
        subprocess.Popen(args)

        # --- 씬 저장 ---
        bpy.ops.wm.save_mainfile()
        return {'FINISHED'}

    def get_repository_file_path(self, subdir):
        """Deadline 리포지토리에서 특정 파일의 경로를 가져옵니다."""
        import subprocess
        args = [get_deadline_command(), "-GetRepositoryFilePath", subdir]
        output = subprocess.check_output(args).decode().strip()
        return output.replace("\\", "/")




def camera_has_movement(camera):
    if not camera or not camera.animation_data or not camera.animation_data.action:
        return False

    has_movement = False
    loc_fcurves = [camera.animation_data.action.fcurves.find(data_path) for data_path in ("location", "rotation_euler", "rotation_quaternion")]
    loc_fcurves = [fcurve for fcurve in loc_fcurves if fcurve]

    # 각 변환 키프레임을 비교하여 실제 움직임이 있는지 확인
    for fcurve in loc_fcurves:
        if len(fcurve.keyframe_points) > 1:
            keyframe_values = [point.co[1] for point in fcurve.keyframe_points]
            if len(set(keyframe_values)) > 1:  # 중복된 값을 제외하고 값이 하나 이상이면 움직임이 있다
                has_movement = True
                break

    return has_movement

class CameraMovementFrameRangeOperator(bpy.types.Operator):
    bl_idname = "frame.set_camera_movement_frame_range"
    bl_label = "Set Camera Movement Frame Range"

    def execute(self, context):
        scene = context.scene
        camera = scene.camera

        if camera_has_movement(camera):
            # 카메라의 움직임이 있는 경우
            loc_fcurves = [camera.animation_data.action.fcurves.find(data_path) for data_path in ("location", "rotation_euler", "rotation_quaternion")]
            loc_fcurves = [fcurve for fcurve in loc_fcurves if fcurve]

            # 움직임이 시작되는 첫 번째 프레임 찾기
            start_frame = min([min(fcurve.keyframe_points, key=lambda point: point.co[0]).co[0] for fcurve in loc_fcurves])

            # 움직임이 끝나는 마지막 프레임 찾기
            end_frame = max([max(fcurve.keyframe_points, key=lambda point: point.co[0]).co[0] for fcurve in loc_fcurves])

            # 프레임 레인지 설정 (부동 소수점을 정수로 변환)
            scene.frame_start = int(start_frame)
            scene.frame_end = int(end_frame)
            print("Camera movement frame range set: {} - {}".format(int(start_frame), int(end_frame)))
        else:
            print("Camera has no movement.")

        return {'FINISHED'}


class FrameRangeOperator(bpy.types.Operator):
    bl_idname = "frame.range_operator"
    bl_label = "Frame Range Operator"

    option: bpy.props.StringProperty(default="FULL")

    def set_frame_range_from_json(self, json_file_path):
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as json_file:
                camera_data = json.load(json_file)
                scene = bpy.context.scene
                scene.frame_start = int(camera_data.get('minTime', scene.frame_start))
                scene.frame_end = int(camera_data.get('maxTime', scene.frame_end))
                print("Frame range set from JSON: {} - {}".format(scene.frame_start, scene.frame_end))
        else:
            print("JSON file not found.")

    def set_current_frame_range(self):
        scene = bpy.context.scene
        scene.frame_start = scene.frame_current
        scene.frame_end = scene.frame_current
        print("Frame range set to current frame ({})".format(scene.frame_current))

    def execute(self, context):
        scene = context.scene
        my_tool = context.scene.my_tool
        scene_number = my_tool.scene_number
        cut_number = my_tool.cut_number
        base_path = get_project_paths()
        project_prefix = get_project_prefix()  # 현재 프로젝트의 식별자를 얻습니다.

        # JSON 파일 이름 설정
        json_file_name = f"{project_prefix}_{scene_number}_{cut_number}_camera_data.json"

        # JSON 파일 전체 경로 설정
        full_json_path = os.path.join(os.path.join(base_path, "scenes", scene_number, cut_number, "ren", "cache"), json_file_name)

        if self.option == "FULL":
            self.set_frame_range_from_json(full_json_path)
        elif self.option == "CURRENT":
            self.set_current_frame_range()

        return {'FINISHED'}

class SimpleSceneProps(bpy.types.PropertyGroup):
    # 드롭다운 메뉴를 위한 EnumProperty 설정, 순서 변경
    mode_items = [
        ('all', "BG + CH", "", 'PLAY', 0),
        ('ch_only', "Ch Only", "", 'OUTLINER_OB_ARMATURE', 1),
        ('bg_only', "Bg Only", "", 'FILE_IMAGE', 2),
        ('viewlayer', "ViewLayer", "", 'RENDERLAYERS', 3),
    ]
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=mode_items,
        default='all',
        update=lambda self, context: self.update_mode()
    )

    def update_mode(self):
        mode = self.mode
        print(f"Mode set to: {mode}")
        # 해당 모드에 대한 실제 로직을 호출합니다.
        bpy.ops.sf.set_view_layer_mode(mode=mode)

######################################################################
###########################Light Mask    #############################
######################################################################

class OBJECT_OT_apply_light_mask(bpy.types.Operator):
    bl_idname = "object.apply_light_mask"
    bl_label = "Apply Light Mask"
    
    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self.create_light_mask(obj, "lightmask_col", "MI_lightmask")
            else:
                print(f"Skipped {obj.name}: Not a mesh object.")
        
        if "lightmask_vl" not in bpy.context.scene.view_layers:
            self.create_view_layer("ViewLayer", "lightmask_vl", "lightmask_col")
        
        self.setup_lightmask_view_layer("lightmask_vl", "lightmask_col")
        self.deactivate_lightmask_col_in_other_layers("lightmask_vl", "lightmask_col")
        return {'FINISHED'}
    
    def create_light_mask(self, obj, collection_name, material_name):
        light_mask_name = obj.name + "_lightmask"
        if light_mask_name in bpy.data.objects:
            print("Light mask object already exists.")
            return
        
        obj_copy = obj.copy()
        obj_copy.data = obj.data.copy()
        obj_copy.name = light_mask_name
        
        self.disable_solidify_modifier(obj_copy)
        self.apply_material(obj_copy, material_name)
        
        self.setup_collection(collection_name)
        collection = bpy.data.collections.get(collection_name)
        if obj_copy.name not in collection.objects:
            collection.objects.link(obj_copy)

        self.create_lights(collection_name)

    def disable_solidify_modifier(self, obj):
        for mod in obj.modifiers:
            if mod.type == 'SOLIDIFY':
                mod.show_render = False
                mod.show_viewport = False

    def apply_material(self, obj, material_name):
        # Remove all existing materials
        obj.data.materials.clear()

        # Get or create the material
        mat = bpy.data.materials.get(material_name)
        if not mat:
            mat = self.create_material(material_name)

        # Assign the material
        obj.data.materials.append(mat)

    def create_material(self, material_name):
        # Load the material from an external Blender file
        filepath = "M:/RND/SFtools/2025/lookdev/blend/ldvLight_v03.blend"
        material_path = os.path.join(filepath, "Material", material_name)
        
        # Check if the material already exists in the current scene
        mat = bpy.data.materials.get(material_name)
        if mat:
            print(f"Material {material_name} already exists in the scene.")
            return mat
        
        # Append the material from the external file if it's not already loaded
        if material_name not in bpy.data.materials:
            try:
                bpy.ops.wm.append(filepath=material_path, directory=os.path.join(filepath, "Material"), filename=material_name)
                mat = bpy.data.materials.get(material_name)
                if mat:
                    print(f"Successfully appended material: {material_name}")
                else:
                    print(f"Failed to append material {material_name}")
                    return None
            except Exception as e:
                print(f"Error appending material {material_name}: {e}")
                return None
        
        return mat

    def create_lights(self, collection_name):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)
        
        light_properties = [
            ("lgtRed", (1.0, 0.0, 0.0)),
            ("lgtGreen", (0.0, 1.0, 0.0)),
            ("lgtBlue", (0.0, 0.0, 1.0))
        ]
        
        for light_name, color in light_properties:
            if light_name not in bpy.data.objects:
                light_data = bpy.data.lights.new(name=light_name, type='SUN')
                light_object = bpy.data.objects.new(name=light_name, object_data=light_data)
                collection.objects.link(light_object)
                light_data.color = color
                light_data.energy = 3  # Set power to 100
                for attr_name, value in (
                    ("specular_factor", 0),
                    ("volume_factor", 0),
                    ("shadow_soft_size", 0.15),
                    ("cutoff_distance", 1.0),
                    ("use_shadow", True),
                    ("shadow_cascade_max_distance", 8),
                    ("shadow_buffer_bias", 0.03),
                    ("use_contact_shadow", False),
                ):
                    if hasattr(light_data, attr_name):
                        try:
                            setattr(light_data, attr_name, value)
                        except Exception:
                            pass
        # bpy.data.objects["lgtRed"].hide_viewport = False
        # bpy.data.objects["lgtRed"].hide_render = False

        # bpy.data.objects["lgtGreen"].hide_viewport = True
        # bpy.data.objects["lgtGreen"].hide_render = True

        # bpy.data.objects["lgtBlue"].hide_viewport = True
        # bpy.data.objects["lgtBlue"].hide_render = True

    def setup_collection(self, collection_name):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

    def create_view_layer(self, base_layer_name, new_layer_name, collection_name):
        base_layer = bpy.context.view_layer
        bpy.ops.scene.view_layer_add()
        new_layer = bpy.context.view_layer
        new_layer.name = new_layer_name

        for layer_collection in new_layer.layer_collection.children:
            if layer_collection.name != collection_name:
                layer_collection.exclude = True
            else:
                layer_collection.exclude = False

    def setup_lightmask_view_layer(self, light_mask_layer_name, collection_name):
        for scene_layer in bpy.context.scene.view_layers:
            if scene_layer.name == light_mask_layer_name:
                for layer_collection in scene_layer.layer_collection.children:
                    if layer_collection.name != collection_name:
                        layer_collection.exclude = True
                    else:
                        layer_collection.exclude = False

    def deactivate_lightmask_col_in_other_layers(self, light_mask_layer_name, collection_name):
        for scene_layer in bpy.context.scene.view_layers:
            if scene_layer.name != light_mask_layer_name:
                for layer_collection in scene_layer.layer_collection.children:
                    if layer_collection.name == collection_name:
                        layer_collection.exclude = True

import bpy
import os

class OBJECT_OT_update_light_mask(bpy.types.Operator):
    bl_idname = "object.update_light_mask"
    bl_label = "Update Light Mask"
    
    def execute(self, context):
        light_material_name = "MI_lightmask"

        # Always create or replace the existing material
        light_mat = self.create_new_material(light_material_name)

        if not light_mat:
            self.report({'ERROR'}, "Could not find or load the material.")
            return {'CANCELLED'}

        # Replace the materials for all selected mesh objects
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self.replace_matching_materials(obj, light_material_name, light_mat)
            else:
                print(f"Skipped {obj.name}: Not a mesh object.")
        
        print("Light mask material update complete.")
        return {'FINISHED'}

    def create_new_material(self, material_name):
        """
        Always append a new material from the external Blender file and return it.
        """
        filepath = os.path.normpath(r"M:\RND\SFtools\2025\lookdev\blend\ldvLight_v03.blend")
        try:
            # Track existing materials
            existing_materials = set(bpy.data.materials.keys())

            # Append the material
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                matching_materials = [mat for mat in data_from.materials if mat.lower() == material_name.lower()]
                if matching_materials:
                    data_to.materials = [matching_materials[0]]
                    print(f"Appending material: {matching_materials[0]}")
                else:
                    print(f"Error: Material '{material_name}' not found in the file.")
                    return None

            # Find newly appended material
            for mat_name in bpy.data.materials.keys():
                if mat_name not in existing_materials:
                    mat = bpy.data.materials[mat_name]
                    print(f"Newly appended material: {mat.name}")
                    return mat

        except Exception as e:
            print(f"Error appending material {material_name}: {e}")
            return None

        print("Failed to append or identify the new material.")
        return None

    def replace_matching_materials(self, obj, material_prefix, new_material):
        """
        Replace materials in the given object that start with the specified prefix.
        """
        for slot in obj.material_slots:
            if slot.material and slot.material.name.startswith(material_prefix):
                print(f"Replacing material {slot.material.name} with {new_material.name} on object {obj.name}")
                slot.material = new_material


class OBJECT_OT_remove_light_mask(bpy.types.Operator):
    bl_idname = "object.remove_light_mask"
    bl_label = "Remove Light Mask"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_objects = context.selected_objects

        # Remove "_lightmask" objects from the selected objects
        for obj in selected_objects:
            if obj.name.endswith("_lightmask"):
                obj_name = obj.name  # Store the name before deletion
                bpy.data.objects.remove(obj)
                print(f"Removed light mask object: {obj_name}")

        # Check and remove the lightmask collection if it's empty
        target_collection_name = "lightmask_col"
        target_collection = bpy.data.collections.get(target_collection_name)
        
        if target_collection:
            # Clean up light group settings for lights in the collection
            for obj in list(target_collection.objects):  # Use a list to avoid modification during iteration
                if obj.type == 'LIGHT':
                    obj.data.light_groups.use_default = True  # Enable default light groups
                    obj.data.light_groups.groups.clear()  # Clear all light groups
                else:
                    print(f"Object '{obj.name}' is not a light.")

            # Remove the collection if empty
            if not target_collection.objects:
                bpy.data.collections.remove(target_collection)
                print(f"Removed empty collection: {target_collection_name}")
        else:
            print(f"Collection '{target_collection_name}' not found.")

        return {'FINISHED'}


class OBJECT_OT_make_shared_unique_material(bpy.types.Operator):
    bl_idname = "object.make_shared_unique_material"
    bl_label = "Make Shared Unique Material"
    bl_description = "Create a single-user copy of the material and assign it to selected objects"

    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected!")
            return {'CANCELLED'}

        # Check the first selected object's material
        if not selected_objects[0].data.materials:
            self.report({'WARNING'}, "Selected objects have no materials!")
            return {'CANCELLED'}

        # Use the material of the first object as a base
        base_material = selected_objects[0].data.materials[0]

        # Create a single-user copy of the material
        unique_material = base_material.copy()
        unique_material.name = f"{base_material.name}_unique"

        # Assign the unique material to all selected objects
        for obj in selected_objects:
            if obj.data.materials:
                obj.data.materials.clear()  # Remove existing materials
            obj.data.materials.append(unique_material)

        self.report({'INFO'}, f"Unique material '{unique_material.name}' assigned to {len(selected_objects)} objects.")
        return {'FINISHED'}

######################################################################
###########################Caustics Mask #############################
######################################################################
class OBJECT_OT_apply_caustics_mask(bpy.types.Operator):
    bl_idname = "object.apply_caustics_mask"
    bl_label = "Apply Caustics Mask"
    
    def execute(self, context):
        # 컬렉션을 먼저 설정합니다
        self.setup_collection("caustic_col")

        # 그 다음 메터리얼을 생성합니다
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self.create_caustics_mask(obj, "caustic_col", "MI_causticsmask")
            else:
                print(f"Skipped {obj.name}: Not a mesh object.")
        
        # 마지막으로 뷰 레이어를 설정합니다
        if "caustic_vl" not in bpy.context.scene.view_layers:
            self.create_view_layer("ViewLayer", "caustic_vl", "caustic_col")
        
        self.setup_caustics_view_layer("caustic_vl", "caustic_col")
        self.deactivate_caustic_col_in_other_layers("caustic_vl", "caustic_col")
        
        return {'FINISHED'}
    
    def create_caustics_mask(self, obj, collection_name, material_name):
        caustics_mask_name = obj.name + "_cMask"
        if caustics_mask_name in bpy.data.objects:
            print("Caustics mask object already exists.")
            return
        
        obj_copy = obj.copy()
        obj_copy.data = obj.data.copy()
        obj_copy.name = caustics_mask_name
        
        self.disable_solidify_modifier(obj_copy)
        self.apply_material(obj_copy, material_name)
        
        self.setup_collection(collection_name)
        collection = bpy.data.collections.get(collection_name)
        if obj_copy.name not in collection.objects:
            collection.objects.link(obj_copy)

    def disable_solidify_modifier(self, obj):
        for mod in obj.modifiers:
            if mod.type == 'SOLIDIFY':
                mod.show_render = False
                mod.show_viewport = False

    def apply_material(self, obj, material_name):
        # Remove all existing materials
        obj.data.materials.clear()

        # Get or create the material
        mat = bpy.data.materials.get(material_name)
        if not mat:
            mat = self.create_material(material_name)

        # Assign the material
        obj.data.materials.append(mat)

        # Add Caustics_Range to caustic_col collection
        caustics_range_obj = bpy.data.objects.get("Caustics_Range")
        collection = bpy.data.collections.get("caustic_col")
        if caustics_range_obj and collection:
            if caustics_range_obj.name not in collection.objects:
                collection.objects.link(caustics_range_obj)


    def create_material(self, material_name):
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # Append the caustics shader node group from external blend file
        try:
            bpy.ops.wm.append(
                filepath="T:/assets/library/shader/floor2F_Water.blend",
                directory="T:/assets/library/shader/floor2F_Water.blend/NodeTree",
                filename="SF_CausticsShader"
            )
            caustics_shader = nodes.new(type='ShaderNodeGroup')
            caustics_shader.node_tree = bpy.data.node_groups['SF_CausticsShader']

            # Create material output node
            material_output = nodes.new(type='ShaderNodeOutputMaterial')

            # Set node positions
            caustics_shader.location = (0, 0)
            material_output.location = (200, 0)

            # Link caustics shader directly to the material output
            links.new(caustics_shader.outputs['Shader'], material_output.inputs['Surface'])

            # Set caustics shader properties
            caustics_shader.inputs['Strength'].default_value = 8
            caustics_shader.inputs['Scale'].default_value = 0.35
        except KeyError:
            self.report({'ERROR'}, "SF_CausticsShader node group not found in the specified blend file.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to append the node group: {str(e)}")

        return mat

    def setup_collection(self, collection_name):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

    def create_view_layer(self, base_layer_name, new_layer_name, collection_name):
        base_layer = bpy.context.view_layer
        bpy.ops.scene.view_layer_add()
        new_layer = bpy.context.view_layer
        new_layer.name = new_layer_name

        for layer_collection in new_layer.layer_collection.children:
            if layer_collection.name != collection_name:
                layer_collection.exclude = True
            else:
                layer_collection.exclude = False

    def setup_caustics_view_layer(self, caustics_mask_layer_name, collection_name):
        for scene_layer in bpy.context.scene.view_layers:
            if scene_layer.name == caustics_mask_layer_name:
                for layer_collection in scene_layer.layer_collection.children:
                    if layer_collection.name != collection_name:
                        layer_collection.exclude = True
                    else:
                        layer_collection.exclude = False

    def deactivate_caustic_col_in_other_layers(self, caustics_mask_layer_name, collection_name):
        for scene_layer in bpy.context.scene.view_layers:
            if scene_layer.name != caustics_mask_layer_name:
                for layer_collection in scene_layer.layer_collection.children:
                    if layer_collection.name == collection_name:
                        layer_collection.exclude = True


class OBJECT_OT_remove_caustics_mask(bpy.types.Operator):
    bl_idname = "object.remove_caustics_mask"
    bl_label = "Remove Caustics Mask"

    def execute(self, context):
        for obj in context.selected_objects:
            if obj:
                if obj.name.endswith("_cMask") or obj.name.endswith(".001"):
                    bpy.data.objects.remove(obj)
        
        # Check and remove the caustics collection if it's empty
        target_collection_name = "caustic_col"
        target_collection = bpy.data.collections.get(target_collection_name)
        
        if target_collection:
            for obj in target_collection.objects:
                if obj.type == 'LIGHT':
                    obj.data.light_groups.use_default = True  # Enable use of default light group
                    obj.data.light_groups.groups.clear()  # Remove all light groups
                else:
                    print(f"Object '{obj.name}' is not a light.")
            
            if not target_collection.objects:
                bpy.data.collections.remove(target_collection)
                print(f"Collection '{target_collection_name}' removed.")
        else:
            print(f"Collection '{target_collection_name}' not found.")

        # Check if caustic_col is removed and if so, remove the caustics_vl view layer
        if not bpy.data.collections.get(target_collection_name):
            view_layer_name = "caustics_vl"
            base_layer_name = "ViewLayer"
            bpy.context.window.view_layer = bpy.context.scene.view_layers.get(base_layer_name)
            for view_layer in bpy.context.scene.view_layers:
                if view_layer.name == view_layer_name:
                    bpy.context.scene.view_layers.remove(view_layer)
                    print(f"View layer '{view_layer_name}' removed.")
                    break
        
        return {'FINISHED'}




######################################################################
###########################Shadow Catcher#############################
######################################################################

class OBJECT_OT_apply_shadow_catcher(bpy.types.Operator):
    bl_idname = "object.apply_shadow_catcher"
    bl_label = "Apply Shadow Catcher"
    
    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self.create_shadow_catcher(obj.name, "ch_shadow_col", "MI_shadow")
            else:
                print(f"Skipped {obj.name}: Not a mesh object.")
        return {'FINISHED'}
    
    def create_shadow_catcher(self, obj_name, collection_name, material_name):
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            print("Object not found.")
            return
        
        shadow_name = obj_name + "_shadow"
        if shadow_name in bpy.data.objects:
            print("Shadow object already exists.")
            return
        
        obj_copy = obj.copy()
        obj_copy.data = obj.data.copy()
        obj_copy.name = shadow_name
        
        mat = self.create_material(material_name)
        if not obj_copy.material_slots:
            obj_copy.data.materials.append(mat)
        else:
            obj_copy.material_slots[0].material = mat
        
        self.setup_collection(collection_name, bpy.context.scene.view_layers)
        collection = bpy.data.collections.get(collection_name)
        if obj_copy.name not in collection.objects:
            collection.objects.link(obj_copy)

    # def create_material(self, material_name):
        # mat = bpy.data.materials.get(material_name)
        # if not mat:
            # mat = bpy.data.materials.new(name=material_name)
            # mat.use_nodes = True
            # nodes = mat.node_tree.nodes
            # links = mat.node_tree.links
            # nodes.clear()

            # trans_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
            # trans_bsdf.location = (-300, 0)
            # diffuse_bsdf = nodes.new(type='ShaderNodeBsdfDiffuse')
            # diffuse_bsdf.location = (-600, 200)
            # shader_to_rgb = nodes.new(type='ShaderNodeShaderToRGB')
            # shader_to_rgb.location = (-300, 200)
            # color_ramp = nodes.new(type='ShaderNodeValToRGB')
            # color_ramp.location = (0, 200)
            # mix_shader = nodes.new(type='ShaderNodeMixShader')
            # mix_shader.location = (300, 0)
            # material_output = nodes.new(type='ShaderNodeOutputMaterial')
            # material_output.location = (600, 0)
            # shader_info = nodes.new(type='ShaderNodeShaderInfo')
            # shader_info.location = (-600, -200)

            # diffuse_bsdf.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            # color_ramp.color_ramp.elements[0].position = 0.845
            # color_ramp.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
            # color_ramp.color_ramp.elements[1].position = 1.0
            # color_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)

            # links.new(shader_info.outputs['Cast Shadow'], color_ramp.inputs['Fac'])
            # links.new(color_ramp.outputs['Color'], mix_shader.inputs['Fac'])
            # links.new(trans_bsdf.outputs['BSDF'], mix_shader.inputs[1])
            # links.new(mix_shader.outputs['Shader'], material_output.inputs['Surface'])

            # mat.blend_method = 'BLEND'
        
        # return mat
    def create_material(self, material_name):
        # Load the material from an external Blender file
        filepath = "M:/RND/SFtools/2025/lookdev/blend/ldvLight_v03.blend"
        material_name = "MI_shadow"
        
        # Check if the material already exists in the current scene
        mat = bpy.data.materials.get(material_name)
        if mat:
            print(f"Material {material_name} already exists in the scene.")
            return mat
        
        # Append the material from the external file if it's not already loaded
        if material_name not in bpy.data.materials:
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                if material_name in data_from.materials:
                    data_to.materials = [material_name]
                else:
                    print(f"Material {material_name} not found in {filepath}")
                    return None
        
        # Return the material
        mat = bpy.data.materials.get(material_name)
        if not mat:
            print(f"Failed to load material {material_name}")
            return None
        
        return mat

    def setup_collection(self, collection_name, view_layers):
        collection = bpy.data.collections.get(collection_name)
        if not collection:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

        for layer in view_layers:
            layer_collection = layer.layer_collection.children.get(collection_name)
            if layer_collection is None:
                layer_collection = layer.layer_collection.children.new(collection_name)
            
            if layer.name.startswith('ch'):
                layer_collection.exclude = False
            elif layer.name.startswith('bg'):
                layer_collection.exclude = True
            else:
                layer_collection.exclude = True
                
class OBJECT_OT_update_shadow_material(bpy.types.Operator):
    bl_idname = "object.update_shadow_material"
    bl_label = "Update Shadow Material"
    
    def execute(self, context):
        shadow_material_name = "MI_shadow"

        shadow_mat = self.get_material(shadow_material_name)

        if not shadow_mat:
            self.report({'ERROR'}, "Could not find or load the material.")
            return {'CANCELLED'}

        # Replace the materials for all selected mesh objects
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self.replace_matching_materials(obj, shadow_material_name, shadow_mat)
            else:
                print(f"Skipped {obj.name}: Not a mesh object.")
        
        return {'FINISHED'}

    def get_material(self, material_name):
        # Use the create_material method to get the material
        filepath = "M:/RND/SFtools/2025/lookdev/blend/ldvLight_v03.blend"
        if material_name not in bpy.data.materials:
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                if material_name in data_from.materials:
                    data_to.materials = [material_name]
                else:
                    print(f"Material {material_name} not found in {filepath}")
                    return None
        return bpy.data.materials.get(material_name)

    def replace_matching_materials(self, obj, material_prefix, new_material):
        for i, mat in enumerate(obj.data.materials):
            if mat and mat.name.startswith(material_prefix):
                print(f"Replacing material {mat.name} with {new_material.name} on object {obj.name}")
                obj.data.materials[i] = new_material


class OBJECT_OT_remove_shadow_catcher(bpy.types.Operator):
    bl_idname = "object.remove_shadow_catcher"
    bl_label = "Remove Shadow Catcher"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.name.endswith("_shadow"):
            bpy.data.objects.remove(obj)
            # Remove object from collection if needed
        return {'FINISHED'}

################################################################
##################   CH_BLOCKER   ##############################
################################################################

class OBJECT_OT_apply_blocker(bpy.types.Operator):
    bl_idname = "object.apply_blocker"
    bl_label = "Apply Blocker"
    
    def execute(self, context):
        for obj in context.selected_objects:
            self.create_blocker(obj.name, "ch_blocker_col", "MI_ch_blocker")
        return {'FINISHED'}
    
    def create_blocker(self, obj_name, collection_name, material_name):
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            print("Object not found.")
            return
        
        blocker_name = obj_name + "_blocker"
        if blocker_name in bpy.data.objects:
            print("Blocker object already exists.")
            return
        
        obj_copy = obj.copy()
        obj_copy.data = obj.data.copy()
        obj_copy.name = blocker_name
        
        # Create and assign the material
        mat = self.create_material(material_name)
        obj_copy.data.materials.clear()
        obj_copy.data.materials.append(mat)
        
        # Link the object to the existing collection
        collection = bpy.data.collections.get(collection_name)
        if collection and obj_copy.name not in collection.objects:
            collection.objects.link(obj_copy)

    def create_material(self, material_name):
        mat = bpy.data.materials.get(material_name)
        if not mat:
            mat = bpy.data.materials.new(name=material_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()

            trans_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
            material_output = nodes.new(type='ShaderNodeOutputMaterial')
            
            links.new(trans_bsdf.outputs['BSDF'], material_output.inputs['Surface'])
            
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'NONE'
        
        return mat


class OBJECT_OT_remove_blocker(bpy.types.Operator):
    bl_idname = "object.remove_blocker"
    bl_label = "Remove Blocker"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.name.endswith("_blocker"):
            bpy.data.objects.remove(obj)
            # Remove object from collection if needed
        return {'FINISHED'}
        
########################bake to shape key##################################        
        
def create_base_mesh(original_obj):
    # Duplicate the original object and convert to mesh with keep_original=True
    bpy.ops.object.select_all(action='DESELECT')
    original_obj.select_set(True)
    bpy.context.view_layer.objects.active = original_obj
    bpy.ops.object.convert(target='MESH', keep_original=True)
    base_obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = base_obj

    # Set base object name to the original object name with _cloth suffix
    base_obj.name = f"{original_obj.name}_baked"

    # Rename the original object with _orig suffix
    original_obj.name = f"{original_obj.name}_orig"
    
    return base_obj

def copy_modifiers(source_obj, target_obj, modifier_types):
    for modifier in source_obj.modifiers:
        if modifier.type in modifier_types:
            bpy.context.view_layer.objects.active = source_obj
            source_obj.select_set(True)
            target_obj.select_set(True)
            bpy.ops.object.modifier_copy_to_selected(modifier=modifier.name)
            target_obj.select_set(False)

def bake_shape_key_animation(base_obj, original_obj):
    # Ensure the base object has shape keys, create one if it does not
    if not base_obj.data.shape_keys:
        base_obj.shape_key_add(name="Basis")

    # Use the base object name as the shape key prefix
    shape_key_prefix = base_obj.data.name

    # Use current frame range
    frame_start = bpy.context.scene.frame_start
    frame_end = bpy.context.scene.frame_end

    # Create shape keys for each frame
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)

        # Duplicate and convert the original object to mesh with keep_original=True
        bpy.ops.object.select_all(action='DESELECT')
        original_obj.select_set(True)
        bpy.context.view_layer.objects.active = original_obj
        bpy.ops.object.convert(target='MESH', keep_original=True)
        frame_obj = bpy.context.selected_objects[0]
        bpy.context.view_layer.objects.active = frame_obj

        # Ensure the number of vertices matches before creating the shape key
        if len(frame_obj.data.vertices) == len(base_obj.data.vertices):
            # Create a new shape key
            shape_key_name = f"{shape_key_prefix}_Frame_{frame}"
            new_shape_key = base_obj.shape_key_add(name=shape_key_name, from_mix=False)

            # Transfer the frame mesh shape to the new shape key
            base_mesh = base_obj.data
            frame_mesh = frame_obj.data
            for vert_base, vert_frame in zip(base_mesh.vertices, frame_mesh.vertices):
                new_shape_key.data[vert_base.index].co = vert_frame.co
            
            # Keyframe the shape key value to 1 at the current frame
            new_shape_key.value = 1.0
            new_shape_key.keyframe_insert(data_path="value", frame=frame)

            # Keyframe the shape key value to 0 at the previous and next frames
            if frame > frame_start:
                new_shape_key.value = 0.0
                new_shape_key.keyframe_insert(data_path="value", frame=frame-1)
            if frame < frame_end:
                new_shape_key.value = 0.0
                new_shape_key.keyframe_insert(data_path="value", frame=frame+1)
        else:
            print(f"Vertex count mismatch at frame {frame}: frame object has {len(frame_obj.data.vertices)} vertices, but base mesh has {len(base_obj.data.vertices)} vertices.")

        # Remove the frame object
        bpy.data.objects.remove(frame_obj, do_unlink=True)

    # Hide the original object in viewport and render
    original_obj.hide_viewport = True
    original_obj.hide_render = True

    # Copy solidify modifiers from the original object to the base object
    copy_modifiers(original_obj, base_obj, {'SOLIDIFY'})

    print(f"Shape key animation baked for {base_obj.name}.")

class BakeShapeKeysOperator(bpy.types.Operator):
    bl_idname = "object.bake_shape_keys"
    bl_label = "Bake Shape Keys"

    def execute(self, context):
        original_objects = context.selected_objects

        if original_objects:
            for original_obj in original_objects:
                if original_obj.type == 'MESH':
                    # Disable subdivision and solidify modifiers completely
                    original_modifiers = []
                    for modifier in original_obj.modifiers:
                        if modifier.type in {'SUBSURF', 'SOLIDIFY'}:
                            original_modifiers.append((modifier, modifier.show_viewport, modifier.show_render))
                            modifier.show_viewport = False
                            modifier.show_render = False

                    # Create base mesh
                    base_obj = create_base_mesh(original_obj)
                    
                    # Bake shape key animation
                    bake_shape_key_animation(base_obj, original_obj)

                    # Restore subdivision and solidify modifiers
                    for modifier, show_viewport, show_render in original_modifiers:
                        modifier.show_viewport = show_viewport
                        modifier.show_render = show_render
                else:
                    self.report({'WARNING'}, f"{original_obj.name} is not a mesh object.")
        else:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        return {'FINISHED'}



class DeleteNonVisibleMeshesOperator(bpy.types.Operator):
    bl_idname = "object.delete_non_visible_meshes"
    bl_label = "Delete Non-Visible Meshes"
    bl_description = "Delete all non-visible mesh objects. Are you sure?"

    # UI 그리기 함수 (확인용 팝업)
    def draw(self, context):
        layout = self.layout
        layout.label(text="Delete all non-visible mesh objects?")  # 확인 메시지 표시

    # 팝업을 띄우는 함수
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)  # 확인용 팝업을 띄움

    # OK 버튼을 눌렀을 때 실행되는 함수
    def execute(self, context):
        # 보이는 메시 오브젝트의 이름을 모아두기
        visible_objects = {obj.name for obj in bpy.context.visible_objects if obj.type == 'MESH'}

        # 삭제할 오브젝트 목록을 먼저 생성 (이름을 저장)
        objects_to_delete = [obj.name for obj in bpy.data.objects if obj.type == 'MESH' and obj.name not in visible_objects]

        # 모든 오브젝트 삭제
        for obj_name in objects_to_delete:
            obj = bpy.data.objects.get(obj_name)  # 안전하게 오브젝트를 다시 참조
            if obj:
                bpy.data.objects.remove(obj, do_unlink=True)
                self.report({'INFO'}, f"Deleted: {obj_name}")

        self.report({'INFO'}, "All non-visible mesh objects have been deleted.")
        return {'FINISHED'}


# 기존의 함수 정의
def replace_botaniq_library_path():
    keyword = "botaniq_lite"
    new_prefix = "m:\\e_utility\\blender\\add_on\\botaniq\\"

    # 라이브러리 파일 경로 변경
    for lib in bpy.data.libraries:
        if keyword in lib.filepath:
            # botaniq_lite 앞부분만 변경
            botaniq_index = lib.filepath.find(keyword)
            new_filepath = new_prefix + lib.filepath[botaniq_index:]
            print(f"Old Library Path: {lib.filepath}")
            print(f"New Library Path: {new_filepath}")
            lib.filepath = new_filepath

    print("Botaniq library path replacement complete.")

def replace_botaniq_texture_path():
    keyword = "botaniq_lite"
    new_prefix = "m:\\e_utility\\blender\\add_on\\botaniq\\"

    # 텍스처 파일 경로 변경
    for img in bpy.data.images:
        if img.filepath and keyword in img.filepath:
            # botaniq_lite 앞부분만 변경
            botaniq_index = img.filepath.find(keyword)
            new_filepath = new_prefix + img.filepath[botaniq_index:]
            print(f"Old Texture Path: {img.filepath}")
            print(f"New Texture Path: {new_filepath}")
            img.filepath = new_filepath

    print("Botaniq texture path replacement complete.")

# 오퍼레이터 정의
class ReplaceBotaniqLibraryPathOperator(bpy.types.Operator):
    bl_idname = "object.replace_botaniq_library_path"
    bl_label = "Replace Botaniq Library and Texture Paths"
    bl_description = "Replace botaniq_lite paths in the library and textures with a new path."

    # 버튼을 눌렀을 때 실행되는 함수
    def execute(self, context):
        replace_botaniq_library_path()
        replace_botaniq_texture_path()
        self.report({'INFO'}, "Botaniq library and texture paths have been replaced.")
        return {'FINISHED'}



def replace_sanctus_library_path():
    keyword = "Sanctus-Library"
    new_prefix = "m:\\e_utility\\blender\\add_on\\"

    # 라이브러리 경로 변경
    for lib in bpy.data.libraries:
        if keyword in lib.filepath:
            sanctus_index = lib.filepath.find(keyword)
            new_filepath = new_prefix + lib.filepath[sanctus_index:]
            print(f"Old Library Path: {lib.filepath}")
            print(f"New Library Path: {new_filepath}")
            lib.filepath = new_filepath
    
    # 이미지 경로 변경
    for image in bpy.data.images:
        if image.filepath and keyword in image.filepath:
            sanctus_index = image.filepath.find(keyword)
            new_filepath = new_prefix + image.filepath[sanctus_index:]
            print(f"Old Image Path: {image.filepath}")
            print(f"New Image Path: {new_filepath}")
            image.filepath = new_filepath
    
    # 메쉬에 포함된 외부 파일 경로 변경 (예: alembic이나 다른 외부 파일을 사용하는 경우)
    for mesh in bpy.data.meshes:
        if mesh.library and keyword in mesh.library.filepath:
            sanctus_index = mesh.library.filepath.find(keyword)
            new_filepath = new_prefix + mesh.library.filepath[sanctus_index:]
            print(f"Old Mesh Library Path: {mesh.library.filepath}")
            print(f"New Mesh Library Path: {new_filepath}")
            mesh.library.filepath = new_filepath

    print("Sanctus library path replacement complete.")

class ReplacesanctusLibraryPathOperator(bpy.types.Operator):
    bl_idname = "object.replace_sanctus_library_path"
    bl_label = "Replace Sanctus Library Path"
    bl_description = "Replace Sanctus-Library paths in the libraries, images, and meshes with a new path."

    def execute(self, context):
        replace_sanctus_library_path()
        self.report({'INFO'}, "Sanctus library paths have been replaced.")
        return {'FINISHED'}


class SetCyclesRenderSettings(bpy.types.Operator):
    bl_idname = "render.set_cycles_render_settings"
    bl_label = "Set Cycles Render Settings"
    
    def execute(self, context):
        # Render settings
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        # scene.cycles.sample_clamp_indirect = 1
        scene.cycles.caustics_refractive = False
        scene.cycles.caustics_reflective = False
        scene.cycles.adaptive_threshold = 0.03
        scene.cycles.use_denoising = False
        scene.cycles.samples = 128
        
        # Add Denoising Data to view layers that are used for rendering
        for view_layer in scene.view_layers:
            if view_layer.use:  # Check if the view layer is set to be used for rendering
                view_layer.cycles.denoising_store_passes = True  # Enable Denoising Data pass
                view_layer.use_pass_vector = True

        self.report({'INFO'}, "Cycles settings applied and Denoising Data added to view layers.")
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(SetCyclesRenderSettings.bl_idname)

class DeleteAllFakeUsersOperator(bpy.types.Operator):
    bl_idname = "object.delete_all_fake_users"
    bl_label = "Delete All Fake Users"
    bl_description = "Delete all data blocks with Fake Users set."

    def execute(self, context):
        # 모든 페이크 유저가 설정된 데이터 블록을 삭제하는 함수
        data_blocks = [
            bpy.data.meshes, bpy.data.materials, bpy.data.textures,
            bpy.data.images, bpy.data.curves, bpy.data.lights
        ]
        
        for data in data_blocks:
            # 삭제할 블록을 미리 리스트로 저장
            blocks_to_delete = [block for block in data if block.use_fake_user]
            
            for block in blocks_to_delete:
                try:
                    # 데이터 블록이 삭제 가능한지 다시 확인
                    if block and block.use_fake_user:
                        data.remove(block)
                        print(f"{block.name} 페이크 유저 삭제 완료.")
                except ReferenceError:
                    # 이미 삭제된 블록에 대한 참조 오류 발생 시 건너뜀
                    pass
                except Exception as e:
                    print(f"{block.name} 삭제 실패: {e}")
        
        self.report({'INFO'}, "All fake user data blocks deleted.")
        return {'FINISHED'}

class NodeGroupLinkerOperator(bpy.types.Operator):
    bl_idname = "object.node_group_linker"
    bl_label = "Node Group Linker Operator"
    bl_description = "Link node group from an external library and update materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            node_group_linker = NodeGroupLinker("SF_paint", r"M:\e_utility\blender\shaders\sf_paint.blend")
            node_group_linker.link_node_group()
            node_group_linker.update_materials()
            
            self.report({'INFO'}, "Node group linked and materials updated successfully.")
        except Exception as e:
            self.report({'WARNING'}, f"An error occurred: {e}")
        return {'FINISHED'}

class NodeGroupLinker:
    def __init__(self, node_group_name, library_filepath):
        self.node_group_name = node_group_name.lower()  # 대소문자 구분 제거
        self.library_filepath = library_filepath
        self.linked_node_group = None

    def link_node_group(self):
        try:
            print(f"Attempting to load node group: {self.node_group_name} from {self.library_filepath}")
            with bpy.data.libraries.load(self.library_filepath, link=True) as (data_from, data_to):
                if self.node_group_name in [ng.lower() for ng in data_from.node_groups]:
                    data_to.node_groups = [self.node_group_name]
                    print(f"Node group '{self.node_group_name}' found and linked.")
                else:
                    print(f"Node group '{self.node_group_name}' not found in the library.")
                    raise Exception(f"Failed to load '{self.node_group_name}' from '{self.library_filepath}'.")
            
            # 링크된 노드 그룹 찾기
            for node_group in bpy.data.node_groups:
                if (node_group.library and 
                    node_group.library.filepath == self.library_filepath and 
                    node_group.name.lower() == self.node_group_name):
                    self.linked_node_group = node_group
                    print(f"Linked node group found: {self.linked_node_group}")
                    break
            
            if not self.linked_node_group:
                raise Exception(f"Failed to find linked node group '{self.node_group_name}' in the current scene.")

        except Exception as e:
            print(f"Error in linking node group: {e}")

    def update_materials(self):
        try:
            selected_objects = bpy.context.selected_objects
            updated_materials = 0
            for obj in selected_objects:
                if obj.type == 'MESH':  # 메쉬 오브젝트만 처리
                    for slot in obj.material_slots:
                        material = slot.material
                        if material and material.node_tree:
                            for node in material.node_tree.nodes:
                                if node.type == 'GROUP' and node.node_tree:
                                    # 대소문자 구분 없이 `SF_paint`가 포함된 노드 그룹을 찾고 교체
                                    if self.node_group_name in node.node_tree.name.lower():
                                        print(f"Found node: {node.name} with node tree: {node.node_tree.name}")
                                        node.node_tree = self.linked_node_group  # 노드 그룹 교체
                                        updated_materials += 1
                                        print(f"Updated material '{material.name}' with new node group.")
            
            # 결과 보고
            if updated_materials > 0:
                print(f"Updated {updated_materials} materials with '{self.node_group_name}' node group from '{self.library_filepath}'.")
            else:
                print(f"No materials found that use a node group containing '{self.node_group_name}' in the selected objects.")

        except Exception as e:
            print(f"Error in updating materials: {e}")




def set_scene_settings():
    """씬 및 Outliner 설정 변경"""
    # Outliner 설정
    for area in bpy.context.screen.areas:
        if area.type == 'OUTLINER':
            space = area.spaces.active
            space.show_restrict_column_viewport = True
            space.show_restrict_column_select = True
            space.show_restrict_column_holdout = True
            space.show_restrict_column_indirect_only = True

    # # Scene 단위 설정
    # scene = bpy.context.scene
    # if scene.unit_settings.length_unit != 'CENTIMETERS':
        # scene.unit_settings.length_unit = 'CENTIMETERS'

class OBJECT_OT_make_2com(bpy.types.Operator):
    bl_idname = "object.make_2com"
    bl_label = "Make 2com"
    bl_description = "Apply 2 comma animation with step modifier"
    bl_options = {'REGISTER', 'UNDO'}

    def get_action_fcurves(self, action, animation_data=None):
        if not action:
            return []

        fcurves = getattr(action, "fcurves", None)
        if fcurves is not None:
            return fcurves

        layers = getattr(action, "layers", None)
        if not layers:
            return []

        action_slot = getattr(animation_data, "action_slot", None) if animation_data else None
        for layer in layers:
            for strip in getattr(layer, "strips", []):
                channelbag = None

                if action_slot and hasattr(strip, "channelbag"):
                    try:
                        channelbag = strip.channelbag(action_slot)
                    except Exception:
                        channelbag = None

                if channelbag is None:
                    maybe_channelbag = getattr(strip, "channelbag", None)
                    if maybe_channelbag and not callable(maybe_channelbag):
                        channelbag = maybe_channelbag

                fcurves = getattr(channelbag, "fcurves", None) if channelbag else None
                if fcurves is not None:
                    return fcurves

        return []

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "No objects selected.")
            return {'CANCELLED'}

        step_value = 2
        offset_value = 1

        for obj in selected_objects:
            has_cache = False
            has_shape_keys = False

            # 처리: Mesh Sequence Cache
            modifier = obj.modifiers.get("MeshSequenceCache")
            if modifier:
                cache_file = modifier.cache_file
                if cache_file:
                    # Override Frame 활성화
                    cache_file.override_frame = True

                    # 기존 키프레임 제거
                    if cache_file.animation_data and cache_file.animation_data.action:
                        action = cache_file.animation_data.action
                        for fcurve in list(self.get_action_fcurves(action, cache_file.animation_data)):
                            # 기존 모디파이어 제거
                            for fmod in list(fcurve.modifiers):
                                fcurve.modifiers.remove(fmod)

                            try:
                                self.get_action_fcurves(action, cache_file.animation_data).remove(fcurve)
                            except Exception:
                                pass

                    # 새로운 키프레임 추가
                    scene = context.scene
                    start_frame = scene.frame_start
                    end_frame = scene.frame_end

                    cache_file.frame = start_frame
                    cache_file.keyframe_insert(data_path="frame", frame=start_frame)
                    cache_file.frame = end_frame
                    cache_file.keyframe_insert(data_path="frame", frame=end_frame)

                    # 키프레임을 리니어로 설정
                    if cache_file.animation_data and cache_file.animation_data.action:
                        for fcurve in self.get_action_fcurves(cache_file.animation_data.action, cache_file.animation_data):
                            for keyframe in fcurve.keyframe_points:
                                keyframe.interpolation = 'LINEAR'

                            # Step Modifier 추가
                            fmod = fcurve.modifiers.new(type='STEPPED')
                            fmod.frame_step = step_value
                            fmod.frame_offset = offset_value

                    has_cache = True

            # 처리: Shape Keys
            if obj.data and obj.data.shape_keys:
                shape_keys = obj.data.shape_keys.key_blocks
                for shape_key in shape_keys:
                    animation_data = shape_key.id_data.animation_data if shape_key.id_data else None
                    action = animation_data.action if animation_data else None
                    if action:
                        for fcurve in self.get_action_fcurves(action, animation_data):
                            # 기존 Step Modifier 제거
                            for fmod in list(fcurve.modifiers):
                                if fmod.type == 'STEPPED':
                                    fcurve.modifiers.remove(fmod)

                            # Step Modifier 추가
                            fmod = fcurve.modifiers.new(type='STEPPED')
                            fmod.frame_step = step_value
                            fmod.frame_offset = offset_value

                        has_shape_keys = True

            # 처리 결과 확인
            if not has_cache and not has_shape_keys:
                self.report({'WARNING'}, f"Object '{obj.name}' has no Mesh Sequence Cache or Shape Keys.")

        self.report({'INFO'}, "Make 2com applied successfully.")
        return {'FINISHED'}

# 오퍼레이터: Del 2com
class OBJECT_OT_del_2com(bpy.types.Operator):
    bl_idname = "object.del_2com"
    bl_label = "Del 2com"
    bl_description = "Remove 2 comma animation and modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    def get_action_fcurves(self, action, animation_data=None):
        if not action:
            return []

        fcurves = getattr(action, "fcurves", None)
        if fcurves is not None:
            return fcurves

        layers = getattr(action, "layers", None)
        if not layers:
            return []

        action_slot = getattr(animation_data, "action_slot", None) if animation_data else None
        for layer in layers:
            for strip in getattr(layer, "strips", []):
                channelbag = None

                if action_slot and hasattr(strip, "channelbag"):
                    try:
                        channelbag = strip.channelbag(action_slot)
                    except Exception:
                        channelbag = None

                if channelbag is None:
                    maybe_channelbag = getattr(strip, "channelbag", None)
                    if maybe_channelbag and not callable(maybe_channelbag):
                        channelbag = maybe_channelbag

                fcurves = getattr(channelbag, "fcurves", None) if channelbag else None
                if fcurves is not None:
                    return fcurves

        return []

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "No objects selected.")
            return {'CANCELLED'}

        for obj in selected_objects:
            # 처리: Mesh Sequence Cache
            modifier = obj.modifiers.get("MeshSequenceCache")
            if modifier:
                cache_file = modifier.cache_file
                if cache_file:
                    # Override Frame 끄기
                    cache_file.override_frame = False

                    # F-Curve 및 키프레임 제거
                    if cache_file.animation_data and cache_file.animation_data.action:
                        action = cache_file.animation_data.action
                        fcurves = self.get_action_fcurves(action, cache_file.animation_data)
                        for fcurve in list(fcurves):
                            try:
                                fcurves.remove(fcurve)
                            except Exception:
                                pass

            # 처리: Shape Key Modifiers
            if obj.data and obj.data.shape_keys:
                shape_keys = obj.data.shape_keys.key_blocks
                for shape_key in shape_keys:
                    animation_data = shape_key.id_data.animation_data if shape_key.id_data else None
                    action = animation_data.action if animation_data else None
                    if action:
                        for fcurve in self.get_action_fcurves(action, animation_data):
                            # Step Modifier 제거 (키프레임은 유지)
                            for fmod in list(fcurve.modifiers):
                                if fmod.type == 'STEPPED':
                                    fcurve.modifiers.remove(fmod)

        self.report({'INFO'}, "Del 2com applied successfully.")
        return {'FINISHED'}

class OBJECT_OT_instance_solidify(bpy.types.Operator):
    bl_idname = "object.instance_solidify"
    bl_label = "Instance Copy & Solidify"
    bl_description = "Create an instance copy, parent it to original, link material to object, rename it, and apply solidify"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects

        if not selected_objects:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}

        for obj in selected_objects:
            # 선택한 오브젝트를 활성화
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.duplicate_move_linked(OBJECT_OT_duplicate={"linked": True})

            # 복제된 인스턴스 선택
            new_obj = context.object  # 방금 복제된 오브젝트

            # 새로운 이름 설정: 원본 오브젝트 이름 + "_shell"
            new_obj.name = obj.name + "_shell"

            # 복제된 오브젝트를 원본 오브젝트의 하위(페어런트)로 설정
            new_obj.parent = obj

            # 첫 번째 메터리얼 슬롯이 존재하면 Object로 링크 변경
            if new_obj.material_slots:
                new_obj.material_slots[0].link = 'OBJECT'

            # 솔리디파이 모디파이어 추가
            solidify = new_obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            solidify.offset = 0.1
            solidify.thickness = 0.01
            
        return {'FINISHED'}

class OBJECT_OT_remove_shell(bpy.types.Operator):
    bl_idname = "object.remove_shell"
    bl_label = "Remove Shell Objects"
    bl_description = "Remove all child objects that end with _shell, including the selected object if it also ends with _shell"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects

        if not selected_objects:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}

        for obj in selected_objects:
            # 만약 선택한 오브젝트 자체가 '_shell'로 끝난다면 삭제
            if obj.name.endswith("_shell"):
                bpy.data.objects.remove(obj, do_unlink=True)
                continue  # 이미 삭제된 경우 하위 오브젝트는 검사할 필요 없음

            # obj의 하위 오브젝트 중 '_shell'로 끝나는 오브젝트 삭제
            if obj.children:
                for child in obj.children[:]:  # 리스트 복사로 안전하게 삭제
                    if child.name.endswith("_shell"):
                        bpy.data.objects.remove(child, do_unlink=True)

        return {'FINISHED'}

def run_set_scene_from_file(dummy):
    bpy.ops.sf.set_scene_from_file()
    
def register_scene_loader_handler():
    return

    
class SF_OT_SetSceneFromFile(bpy.types.Operator):
    bl_idname = "sf.set_scene_from_file"
    bl_label = "Set Scene from File"

    def execute(self, context):
        import os, re, bpy
        scene = context.scene
        my_tool = scene.my_tool
        project_settings = scene.my_project_settings

        filepath = bpy.data.filepath
        if not filepath:
            self.report({'WARNING'}, "저장된 .blend 파일이 없습니다.")
            return {'CANCELLED'}

        if sync_browser_to_filepath(context, filepath, save_state=True):
            self.report({'INFO'}, "현재 열린 파일 기준으로 브라우저를 동기화했습니다.")
            return {'FINISHED'}

        filename = os.path.basename(filepath)

        # 예: DSC_0040_0060_ren_v003_line.blend
        #     └proj  └scn  └cut  └(중간토큰들) └버전 └접미사(옵션)
        m = re.match(
            r"([A-Za-z]+)_(\d{4})_(\d{4})(?:_[A-Za-z0-9]+)*_(v\d{3})(?:_([A-Za-z0-9]+))?\.blend",
            filename
        )
        if not m:
            self.report({'WARNING'}, f"파일명에서 정보를 추출할 수 없습니다: {filename}")
            return {'CANCELLED'}

        project, scene_number, cut_number, version, suffix = m.groups()
        project = project.upper()
        suffix = suffix or ""           # 예: "line" 또는 ""

        # 프로젝트 체크
        valid_projects = {'DSC', 'THE_TRAP', 'ARBOBION', 'FUZZ', 'BTS'}
        if project not in valid_projects:
            self.report({'WARNING'}, f"알 수 없는 프로젝트: {project}")
            return {'CANCELLED'}

        # 값 적용
        project_settings.projects = project
        my_tool.scene_number = scene_number
        my_tool.cut_number = cut_number

        # --- 핵심: blend_file Enum은 'v003'만 넣는다 (접미사는 버전이 아님)
        target_ver = version  # e.g. 'v003'

        # Enum 안전 세팅: enum에 'v003'이 없다면 'v003_*' 중 하나로 fallback
        try:
            my_tool.blend_file = target_ver
        except TypeError:
            # enum 목록 조회
            enum_prop = my_tool.bl_rna.properties['blend_file']
            enum_keys = [it.identifier for it in enum_prop.enum_items]
            # 정확히 일치하면 재시도
            if target_ver in enum_keys:
                my_tool.blend_file = target_ver
            else:
                # v003_* 중 가장 근접한 것 선택 (예: v003_line)
                candidates = [k for k in enum_keys if k.startswith(target_ver + "_")]
                if candidates:
                    my_tool.blend_file = candidates[0]
                else:
                    self.report({'WARNING'},
                        f"'{target_ver}' 버전을 enum에서 찾을 수 없습니다. 사용 가능: {enum_keys}")
                    # 그래도 나머지 정보는 셋업
                    self.report({'INFO'},
                        f"프로젝트:{project} 씬:{scene_number} 컷:{cut_number} (버전 세팅 생략)")
                    return {'FINISHED'}

        # (선택) 접미사를 어딘가에 저장하고 싶다면 여기서:
        #   - my_tool.output_suffix 같은 StringProperty가 있다면:
        # try:
        #     my_tool.output_suffix = suffix  # 'line' 등
        # except Exception:
        #     pass

        save_recent_browser_state(context, force=True)

        self.report({'INFO'},
            f"프로젝트:{project}, 씬:{scene_number}, 컷:{cut_number}, 버전:{target_ver}"
            + (f", 접미사:{suffix}" if suffix else "")
        )
        return {'FINISHED'}


def disable_line_nodes_in_materials(obj):
    """해당 메쉬의 모든 머티리얼에서 Line Intensity / Line Style 노드를 0으로 세팅"""
    for mat in obj.data.materials:
        if not (mat and mat.use_nodes and mat.node_tree):
            continue
        for node in mat.node_tree.nodes:
            # Float/Value 노드 타입만 체크
            if node.type == 'VALUE':
                if node.label in ["Line Intensity", "Line Style"]:
                    node.outputs[0].default_value = 0.0
                    print(f"[INFO] {obj.name}: {mat.name} → {node.label} 값 0으로 변경")


def convert_vgroup_to_color(obj, color_name="ToonkitLineID"):
    """버텍스 그룹 → 컬러 어트리뷰트 변환 (없어도 생성, 변환 실패 시 0으로 채움)"""
    if obj.type != 'MESH':
        return False

    mesh = obj.data

    # ToonkitLineID 없으면 새로 생성 (BYTE_COLOR, POINT)
    if color_name not in mesh.color_attributes:
        mesh.color_attributes.new(name=color_name, type='BYTE_COLOR', domain='POINT')

    color_layer = mesh.color_attributes[color_name]

    # === Case 1: 버텍스 그룹 없음 ===
    if not obj.vertex_groups:
        for i in range(len(color_layer.data)):
            color_layer.data[i].color = (0.0, 0.0, 0.0, 1.0)
        print(f"[INFO] {obj.name}: 버텍스 그룹 없음 → '{color_name}' 0으로 채움")
        return True

    # === Case 2: 활성 그룹 없음 ===
    vg = obj.vertex_groups.active
    if not vg:
        for i in range(len(color_layer.data)):
            color_layer.data[i].color = (0.0, 0.0, 0.0, 1.0)
        print(f"[INFO] {obj.name}: 활성 버텍스 그룹 없음 → '{color_name}' 0으로 채움")
        return True

    # === Case 3: 변환 성공 (Grayscale: R=G=B=weight) ===
    for i, v in enumerate(mesh.vertices):
        try:
            w = vg.weight(i)
        except RuntimeError:
            w = 0.0
        color_layer.data[i].color = (w, w, w, 1.0)

    print(f"[INFO] {obj.name}: 버텍스 그룹 '{vg.name}' → '{color_name}' 변환 완료 (Grayscale)")
    return True



def set_onlylines_for_special_mesh(obj):
    """메쉬 이름 조건에 따라 OnlyLines 값을 0/1로 설정"""
    keywords = ["eyebrow", "eyelash", "tongue", "toungue"]
    target = any(k in obj.name.lower() for k in keywords)  # 조건 맞으면 True → 1, 아니면 0

    changed = 0
    for mat in obj.data.materials:
        if not (mat and mat.use_nodes and mat.node_tree):
            continue

        for node in mat.node_tree.nodes:
            if node.type == 'GROUP':
                for inp in node.inputs:
                    if inp.name == "OnlyLines":
                        inp.default_value = int(1 if target else 0)
                        print(f"[INFO] {obj.name}: {mat.name} {node.name}.OnlyLines = {int(target)}")
                        changed += 1
    return changed > 0


# 고정할 옵션과 값 (여기만 수정하면 됨)
FIXED_LINE_OPTIONS = {
    "Core": 0,
    "Use Global": 0,
    "UseObj": 0,
    "Relative": 0,
    "UseSilluette": 1,
    "UseMatIdx": 0,
    "UseDepth": 0,
    "NormalLimit": 0.4,
    "Line Size": 0.085,
}

def force_fixed_line_options(obj):
    """모든 메터리얼에서 지정된 옵션들을 고정값으로 세팅"""
    changed = 0

    for mat in obj.data.materials:
        if not (mat and mat.use_nodes and mat.node_tree):
            continue

        for node in mat.node_tree.nodes:
            if node.type == 'GROUP':
                for inp in node.inputs:
                    if inp.name in FIXED_LINE_OPTIONS:
                        inp.default_value = FIXED_LINE_OPTIONS[inp.name]
                        print(f"[INFO] {obj.name}: {mat.name} {node.name}.{inp.name} → {FIXED_LINE_OPTIONS[inp.name]} 고정")
                        changed += 1
    return changed



def disable_special_mesh_object(obj):
    """특수 키워드 또는 네이밍 규칙(sn_geo)인 경우 오브젝트 숨김 처리"""
    if not obj or obj.type != 'MESH':
        return False

    name_l = obj.name.lower()
    keywords = ["eyebrow", "eyelash", "eye", "tongue", "toungue"]

    # 0) 네이밍 규칙: 'sn_'가 'geo' 앞에 붙은 형태 → 예: *_sn_geo
    if "sn_geo" in name_l:
        obj.hide_viewport = True
        obj.hide_render = True
        print(f"[INFO] {obj.name}: 'sn_geo' 네이밍 규칙 감지 → 숨김 처리됨")
        return True

    # 1) 이름 기반 키워드 체크
    if any(k in name_l for k in keywords):
        obj.hide_viewport = True
        obj.hide_render = True
        print(f"[INFO] {obj.name}: 키워드 기반 숨김 처리됨")
        return True

    return False


def normalize_version_to_line(filepath: str):
    """경로에서 v### 또는 v###_* 형태를 v###_line으로 교체"""
    import os, re
    parts = re.split(r'[\\/]', filepath)
    for i, p in enumerate(parts):
        m = re.match(r'^(v\d{3})', p, re.IGNORECASE)
        if m:
            base = m.group(1).lower()   # v001
            parts[i] = f"{base}_line"   # v001_line
            return os.path.normpath(os.sep.join(parts))
    return filepath

def find_layer_collection_by_collection_name(layer_collection, collection_name):
    if layer_collection.collection.name == collection_name:
        return layer_collection

    for child in layer_collection.children:
        found = find_layer_collection_by_collection_name(child, collection_name)
        if found:
            return found

    return None

def set_layer_collection_holdout_recursive(layer_collection, value=True):
    layer_collection.holdout = value
    for child in layer_collection.children:
        set_layer_collection_holdout_recursive(child, value)

from bpy.props import EnumProperty

class SF_OT_UpdateToCyclesIndependent(bpy.types.Operator):
    bl_idname = "object.sf_update_to_cycles_independent"
    bl_label = "Make Outline Scene"
    bl_description = "EEVEE 세팅 + chOutline 생성 + ViewLayer 선택 옵션"
    bl_options = {'REGISTER'}

    layer_choice: EnumProperty(
        name="Target ViewLayer",
        description="Choose which ViewLayer to activate",
        items=[
            ('SELECTED', "Selected Layer", "Keep current active ViewLayer"),
            ('CH', "ch_vl auto select", "Switch to ch_vl, or fallback to first containing 'ch'")
        ],
        default='CH'
    )

    def invoke(self, context, event):
        # 이걸 쓰면 드롭다운이 아니라 라디오 버튼으로 나옴
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Which ViewLayer to use?")
        layout.prop(self, "layer_choice", expand=True)  # 👈 expand=True → 라디오 버튼 표시

    def execute(self, context):
        scene = context.scene

        if self.layer_choice == 'CH':
            target_vl = None
            for vl in scene.view_layers:
                if vl.name == "ch_vl":
                    target_vl = vl
                    break
            if not target_vl:
                for vl in scene.view_layers:
                    if "ch" in vl.name.lower():
                        target_vl = vl
                        break
            if target_vl:
                bpy.context.window.view_layer = target_vl
                self.report({'INFO'}, f"ViewLayer 활성화: {target_vl.name}")
            else:
                self.report({'WARNING'}, "조건에 맞는 뷰레이어 없음, 기존 상태 유지")
        else:
            self.report({'INFO'}, "현재 선택된 ViewLayer 유지")
            
        sc = context.scene
        scene = context.scene


        # --- A. ViewLayer 이름 보정 ---
        active_vl = bpy.context.window.view_layer
        if not any(vl.name.startswith("line") for vl in scene.view_layers):
            old = active_vl.name
            active_vl.name = "line_vl"
            print(f"[INFO] ViewLayer '{old}' → 'line_vl'")
        else:
            print("[INFO] 'line*' ViewLayer 존재 → 이름 변경 생략")
            
            
        # --- B. Current 버튼 실행 ---
        try:
            bpy.ops.sf.version_operator(increment=-999)
            print("[INFO] Current 버튼 실행 완료")
        except Exception as e:
            self.report({'WARNING'}, f"Current 버튼 실행 실패: {e}")

        # --- B2. Output Path 'line' 버튼 실행 ---
        try:
            bpy.ops.sf.set_output_path(prefix="line")
            print("[INFO] Output Path 'line' 버튼 실행 완료")
        except Exception as e:
            self.report({'WARNING'}, f"Output Path 'line' 버튼 실행 실패: {e}")


        # --- C. EEVEE 세팅 ---
        available_engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
        if 'BLENDER_EEVEE_NEXT' in available_engines:
            sc.render.engine = 'BLENDER_EEVEE_NEXT'
        else:
            sc.render.engine = 'BLENDER_EEVEE'
        bpy.context.scene.view_settings.view_transform = 'Standard'
        print(f"[INFO] EEVEE 세팅 완료: {sc.render.engine}")

        line_vl = scene.view_layers.get("line_vl")
        if line_vl:
            current_vl = bpy.context.window.view_layer
            bpy.context.window.view_layer = line_vl
            ch_layer_col = find_layer_collection_by_collection_name(line_vl.layer_collection, "ch_col")
            if ch_layer_col:
                set_layer_collection_holdout_recursive(ch_layer_col, True)
                print("[INFO] line_vl ch_col and children holdout ON")
            else:
                print("[WARN] line_vl에서 ch_col LayerCollection을 찾지 못했습니다.")
            bpy.context.window.view_layer = current_vl

        # --- D. chOutline_col + chOutline 생성 ---
        outline_col_name = "chOutline_col"
        outline_obj_name = "chOutline"

        root_col = context.scene.collection
        outline_col = bpy.data.collections.get(outline_col_name)
        if not outline_col:
            outline_col = bpy.data.collections.new(outline_col_name)
            root_col.children.link(outline_col)

        if not bpy.data.objects.get(outline_obj_name):
            prev_layer_collection = context.view_layer.active_layer_collection

            # 레이어콜렉션 찾기
            def find_layer_collection(layer_collection, target_name):
                if layer_collection.collection.name == target_name:
                    return layer_collection
                for child in layer_collection.children:
                    found = find_layer_collection(child, target_name)
                    if found:
                        return found
                return None

            out_layer = find_layer_collection(context.view_layer.layer_collection, outline_col_name)
            if out_layer:
                context.view_layer.active_layer_collection = out_layer

            # 라인아트 GP 생성 (컬렉션 기반)
            bpy.ops.object.gpencil_add(
                align='WORLD',
                location=(0, 0, 0),
                scale=(1, 1, 1),
                type='LRT_COLLECTION'
            )
            gp_obj = bpy.context.object
            gp_obj.name = outline_obj_name

            # 반드시 chOutline_col 안에 배치
            if gp_obj.name not in outline_col.objects:
                outline_col.objects.link(gp_obj)
                context.scene.collection.objects.unlink(gp_obj)

            # outlineDel 버텍스 그룹 추가
            if "outlineDel" not in gp_obj.vertex_groups.keys():
                gp_obj.vertex_groups.new(name="outlineDel")

            # Line Art 모디파이어 세팅
            mod = gp_obj.grease_pencil_modifiers.get("Line Art")
            if mod:
                mod.source_type = 'COLLECTION'
                
                ch_col = bpy.data.collections.get("ch_col")
                if ch_col:
                    mod.source_collection = ch_col
                    print(f"[INFO] Line Art 소스 → {ch_col.name}")
                else:
                    print("[WARN] ch_col 컬렉션을 찾지 못했습니다.")
                
                # mod.source_collection = context.scene.collection
                mod.target_layer = "Lines"
                mod.thickness = 1
                mod.opacity = 1
                mod.use_contour = True
                mod.silhouette_filtering = 'NONE'
                mod.use_intersection = False
                mod.use_crease = True
                mod.use_material = False
                mod.use_edge_mark = True
                mod.use_loose = True
                mod.use_light_contour = False
                mod.use_shadow = False
                mod.use_overlap_edge_type_support = True
                mod.source_vertex_group = "outlineDel"
                mod.use_output_vertex_group_match_by_name = True

            # Opacity 모디파이어 추가
            bpy.context.view_layer.objects.active = gp_obj
            bpy.ops.object.gpencil_modifier_add(type='GP_OPACITY')
            op_mod = gp_obj.grease_pencil_modifiers.get("Opacity")
            if op_mod:
                op_mod.use_weight_factor = True
                op_mod.modify_color = 'STROKE'
                op_mod.vertex_group = "outlineDel"
                op_mod.invert_vertex = True

            # GP 데이터 세팅
            gp_obj.data.stroke_thickness_space = 'SCREENSPACE'
            gp_obj.data.pixel_factor = 2

            # 원래 활성 콜렉션 복원
            context.view_layer.active_layer_collection = prev_layer_collection

        print("[INFO] Outline Scene 생성 완료")

        # --- D2. Outline Grease Pencil Material Base Color 화이트로 변경 ---
        gp_obj = bpy.data.objects.get("chOutline")
        if gp_obj and gp_obj.type == 'GPENCIL':
            if gp_obj.data.materials:
                for mat in gp_obj.data.materials:
                    if mat and mat.grease_pencil:  # GPencil 전용 재질
                        style = mat.grease_pencil
                        style.color = (1.0, 1.0, 1.0, 1.0)  # Stroke/Base Color → White
                        print(f"[INFO] Grease Pencil Material '{mat.name}' Base Color → White")
            else:
                print("[WARN] chOutline 오브젝트에 머티리얼이 없음")
        else:
            print("[WARN] chOutline GP 오브젝트를 찾을 수 없음")

        # --- E. 특정 매쉬들 하이드 처리 ---
        hide_keywords = ["eye", "tooth", "teeth", "tongue", "toungue", "cornea"]
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                name_lower = obj.name.lower()
                if any(k in name_lower for k in hide_keywords):
                    obj.hide_viewport = True
                    obj.hide_render = True
                    print(f"[INFO] 숨김 처리: {obj.name}")
        # --- F. MeshSequenceCache 모디파이어 세팅 ---
        updated_cache_count = 0
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            msc = obj.modifiers.get("MeshSequenceCache")
            if msc:
                msc.read_data = {'VERT', 'UV', 'COLOR'}
                updated_cache_count += 1
        # print(f"[INFO] MeshSequenceCache 업데이트: {updated_cache_count}개")

        # --- F0. 출력 포맷 강제 변경 ---
        set_output_png(sc.render.image_settings, alpha=False, label="Outline Output: ")
        print("[INFO] 출력 포맷: PNG (RGB)")

        # --- F. 출력 경로 처리 ---
        try:
            sc.render.filepath = normalize_version_to_line(sc.render.filepath)
            my_tool = scene.my_tool if hasattr(scene, "my_tool") else None
            if my_tool:
                scene_number = my_tool.scene_number
                cut_number = my_tool.cut_number
                dirpath = os.path.dirname(sc.render.filepath)
                new_filename = f"{scene_number}_{cut_number}_line_"
                sc.render.filepath = os.path.join(dirpath, new_filename)
            print(f"[INFO] 출력 경로 갱신: {sc.render.filepath}")
        except Exception as e:
            print(f"[WARN] 출력 경로 정규화 중 오류: {e}")
            
        # --- G. ViewLayer 렌더 활성화 제어 ---
        for vl in scene.view_layers:
            if "line" in vl.name.lower():
                vl.use = True
                print(f"[INFO] ViewLayer '{vl.name}' → Render ON")
            else:
                vl.use = False
                print(f"[INFO] ViewLayer '{vl.name}' → Render OFF")

        return {'FINISHED'}

import bpy

class SF_OT_BakeOutline(bpy.types.Operator):
    """chOutline 라인아트를 Bake하고, 뷰포트 표시 및 출력 설정을 정리합니다"""
    bl_idname = "object.sf_bake_outline"
    bl_label = "Bake Outline"
    bl_description = "chOutline 라인아트 Bake 후 ViewLayer에서 ch_col 컬렉션 비활성화 및 출력 포맷 변경"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        # 실행 전에 확인 팝업
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        sc = context.scene
        outline_obj_name = "chOutline"
        outline_obj = bpy.data.objects.get(outline_obj_name)

        # --- 대상 오브젝트 확인 ---
        if not outline_obj or outline_obj.type != 'GPENCIL':
            self.report({'ERROR'}, f"Grease Pencil 오브젝트 '{outline_obj_name}'을(를) 찾을 수 없습니다.")
            return {'CANCELLED'}

        # --- Line Art → Stroke Bake ---
        try:
            bpy.context.view_layer.objects.active = outline_obj
            bpy.ops.object.lineart_bake_strokes()
            self.report({'INFO'}, f"{outline_obj_name} 베이크 완료")
        except Exception as e:
            self.report({'ERROR'}, f"Line Art Bake 실패: {e}")
            return {'CANCELLED'}

        # --- 출력 포맷 PNG + RGB ---
        set_output_png(sc.render.image_settings, alpha=False, label="Outline Output: ")
        print("[INFO] 출력 포맷: PNG (RGB)")

        # --- ViewLayer에서 ch_col 컬렉션 비활성화 ---
        def find_layer_collection(layer_collection, target_name):
            if layer_collection.collection.name == target_name:
                return layer_collection
            for child in layer_collection.children:
                found = find_layer_collection(child, target_name)
                if found:
                    return found
            return None

        layer_col = find_layer_collection(context.view_layer.layer_collection, "ch_col")
        if layer_col:
            layer_col.exclude = True
            print("[INFO] ViewLayer에서 'ch_col' 컬렉션 비활성화 완료")
        else:
            self.report({'WARNING'}, "현재 ViewLayer에서 'ch_col' 컬렉션을 찾지 못했습니다.")

        return {'FINISHED'}

class SF_OT_ClearBakeOutline(bpy.types.Operator):
    """Bake된 라인아트를 지우고 원래 Line Art 모디파이어 상태로 되돌립니다"""
    bl_idname = "object.sf_clear_bake_outline"
    bl_label = "Clear Bake Outline"
    bl_description = "chOutline 오브젝트의 베이크된 Stroke를 제거하고 'ch_col' 컬렉션을 다시 활성화합니다."
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        # 실행 전에 확인 팝업
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        outline_obj_name = "chOutline"
        outline_obj = bpy.data.objects.get(outline_obj_name)

        # --- 대상 오브젝트 확인 ---
        if not outline_obj or outline_obj.type != 'GPENCIL':
            self.report({'ERROR'}, f"Grease Pencil 오브젝트 '{outline_obj_name}'을(를) 찾을 수 없습니다.")
            return {'CANCELLED'}

        # --- Clear Bake 실행 ---
        try:
            bpy.context.view_layer.objects.active = outline_obj
            bpy.ops.object.lineart_clear()
            self.report({'INFO'}, f"{outline_obj_name} Clear Bake 완료")
        except Exception as e:
            self.report({'ERROR'}, f"Clear Bake 실패: {e}")
            return {'CANCELLED'}

        # --- ViewLayer에서 ch_col 컬렉션 다시 켜기 ---
        def find_layer_collection(layer_collection, target_name):
            if layer_collection.collection.name == target_name:
                return layer_collection
            for child in layer_collection.children:
                found = find_layer_collection(child, target_name)
                if found:
                    return found
            return None

        layer_col = find_layer_collection(context.view_layer.layer_collection, "ch_col")
        if layer_col:
            layer_col.exclude = False
            print("[INFO] ViewLayer에서 'ch_col' 컬렉션 다시 활성화 완료")
        else:
            self.report({'WARNING'}, "현재 ViewLayer에서 'ch_col' 컬렉션을 찾지 못했습니다.")

        return {'FINISHED'}

def _sync_reset_to_pub_all_flags(operator, context):
    value = bool(getattr(operator, "toggle_all", False))
    operator.replace_lights = value
    operator.replace_mesh = value
    operator.replace_materials = value
    operator.replace_modifiers = value
    operator.replace_texture_links = value

class SF_OT_UpdateFromPublish(bpy.types.Operator):
    bl_idname = "sf.update_from_publish"
    bl_label = "Update From Publish (Smart)"
    bl_description = "기존 어셋을 삭제하고 최신 소스 파일(mod)로 교체(Re-Import)합니다"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_all: bpy.props.BoolProperty(name="ALL", default=False, update=_sync_reset_to_pub_all_flags)
    replace_lights: bpy.props.BoolProperty(name="Lights", default=False)
    replace_mesh: bpy.props.BoolProperty(name="Mesh", default=True)
    replace_materials: bpy.props.BoolProperty(name="Material", default=True)
    replace_modifiers: bpy.props.BoolProperty(name="Modifier", default=True)
    replace_texture_links: bpy.props.BoolProperty(name="Texture", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)
        grid.prop(self, "toggle_all")
        grid.prop(self, "replace_lights")
        grid.prop(self, "replace_mesh")
        grid.prop(self, "replace_materials")
        grid.prop(self, "replace_modifiers")
        grid.prop(self, "replace_texture_links")

    def execute(self, context):
        scene = context.scene
        updated_count = 0

        # 1. 전역 설정에서 경로 및 접두사 로드 (BTS 지원)
        base_drive = get_project_paths() # "B:\", "S:\" 등
        prefix = get_project_prefix()    # "BTS", "DSC" 등
        
        if not base_drive:
            self.report({'ERROR'}, "프로젝트 경로를 찾을 수 없습니다.")
            return {'CANCELLED'}

        selected_items = []
        for category in scene.sf_file_categories:
            for item in category.items:
                if item.is_selected:
                    selected_items.append((category.name, item.name))

        if not selected_items:
            self.report({'WARNING'}, "선택된 어셋이 없습니다.")
            return {'CANCELLED'}

        # 2. 각 어셋에 대해 '삭제 후 재임포트' 수행
        for cat_name, asset_name in selected_items:
            print(f"--- [Reset to Pub] {asset_name} ({cat_name}) ---")
            preserved_modifiers = None

            if self.replace_mesh and not self.replace_modifiers:
                preserved_modifiers = self.snapshot_collection_modifiers(asset_name)

            # (1) 퍼블리시(Source Mod) 파일 경로 구성
            folder_map = cat_name # 'ch', 'bg', 'prop'
            
            blend_path = os.path.join(base_drive, "assets", folder_map, asset_name, "mod", f"{asset_name}.blend")
            
            if not os.path.exists(blend_path):
                print(f"[Error] 파일을 찾을 수 없음: {blend_path}")
                self.report({'WARNING'}, f"파일 없음: {blend_path}")
                continue

            # (2) USD 캐시 경로 구성 (임포트 후 자동 연결용)
            sn = scene.my_tool.scene_number
            cn = scene.my_tool.cut_number
            cache_dir = os.path.join(base_drive, "scenes", sn, cn, "ren", "cache").replace("\\", "/")
            
            usd_file_name = f"{prefix}_{sn}_{cn}_{cat_name}_{asset_name}.usd"
            usd_path = os.path.join(cache_dir, usd_file_name).replace("\\", "/")
            
            # 와일드카드 검색 시 정확한 카테고리와 어셋명 매칭 규칙 적용
            search_target = f"_{cat_name}_{asset_name}.".lower()
            if not os.path.exists(usd_path) and os.path.exists(cache_dir):
                for f in os.listdir(cache_dir):
                    if f.lower().endswith(".usd") and search_target in f.lower():
                        usd_path = os.path.join(cache_dir, f).replace("\\", "/")
                        usd_file_name = f
                        break

            try:
                if self.replace_mesh or self.replace_lights:
                    self.reimport_asset(
                        blend_path,
                        cat_name,
                        asset_name,
                        context,
                        usd_path,
                        usd_file_name,
                        replace_mesh=self.replace_mesh,
                        replace_lights=self.replace_lights,
                        replace_modifiers=self.replace_modifiers,
                    )

                    if self.replace_mesh and not self.replace_materials:
                        self.rebind_collection_materials_to_existing_scene(asset_name)

                    if preserved_modifiers:
                        self.restore_collection_modifiers(asset_name, preserved_modifiers)

                if self.replace_modifiers and not self.replace_mesh:
                    published_modifiers = self.snapshot_collection_modifiers_from_blend(blend_path, asset_name)
                    if published_modifiers:
                        self.restore_collection_modifiers(asset_name, published_modifiers)

                if self.replace_materials:
                    self.update_asset_materials(
                        context,
                        blend_path,
                        asset_name,
                        preserve_texture_links=not self.replace_texture_links,
                    )

                updated_count += 1
            except Exception as e:
                print(f"[Error] {asset_name} 업데이트 실패: {e}")

        self.report({'INFO'}, f"총 {updated_count}개 어셋 최신화 완료 (Delete & Re-Import)")
        return {'FINISHED'}

    def delete_collection_recursive(self, collection):
        if not collection:
            return

        for child in list(collection.children):
            self.delete_collection_recursive(child)

        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        bpy.data.collections.remove(collection)

    def delete_asset_collections(self, asset_name, replace_mesh=True, replace_lights=True):
        """옵션에 따라 기존 컬렉션을 삭제"""
        suffixes = []
        if replace_mesh:
            suffixes.append("_col")
        if replace_lights:
            suffixes.append("_light_col")

        for suffix in suffixes:
            col = bpy.data.collections.get(asset_name + suffix)
            if col:
                self.delete_collection_recursive(col)

    def get_modifier_target_key(self, obj):
        return obj.name.split(".")[0]

    def snapshot_collection_modifiers(self, asset_name):
        asset_col = bpy.data.collections.get(f"{asset_name}_col")
        if not asset_col:
            return {}

        return self.snapshot_modifiers_for_collection(asset_col, asset_name=asset_name)

    def snapshot_modifiers_for_collection(self, collection, asset_name=None):
        snapshot = {}
        objects = iter_asset_geometry_meshes(collection, asset_name) if asset_name else collection.all_objects
        for obj in objects:
            if obj.type != 'MESH':
                continue

            key = self.get_modifier_target_key(obj)
            modifier_data = []

            for mod in obj.modifiers:
                item = {
                    "name": mod.name,
                    "type": mod.type,
                    "properties": {},
                }

                for prop in mod.bl_rna.properties:
                    identifier = prop.identifier
                    if identifier in {"name", "type", "rna_type"} or prop.is_readonly:
                        continue

                    try:
                        value = getattr(mod, identifier)
                    except Exception:
                        continue

                    try:
                        if hasattr(value, "copy"):
                            value = value.copy()
                        elif isinstance(value, (list, tuple)):
                            value = tuple(value)
                    except Exception:
                        pass

                    item["properties"][identifier] = value

                modifier_data.append(item)

            snapshot[key] = modifier_data

        return snapshot

    def snapshot_collection_modifiers_from_blend(self, blend_path, asset_name):
        target_col_name = f"{asset_name}_col"

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            if target_col_name not in data_from.collections:
                return {}
            data_to.collections = [target_col_name]

        imported_col = next((col for col in data_to.collections if col), None)
        if not imported_col:
            return {}

        snapshot = self.snapshot_modifiers_for_collection(imported_col, asset_name=asset_name)
        self.delete_collection_recursive(imported_col)
        return snapshot

    def restore_collection_modifiers(self, asset_name, snapshot):
        asset_col = bpy.data.collections.get(f"{asset_name}_col")
        if not asset_col or not snapshot:
            return

        for obj in iter_asset_geometry_meshes(asset_col, asset_name):
            if obj.type != 'MESH':
                continue

            key = self.get_modifier_target_key(obj)
            modifier_data = snapshot.get(key)
            if modifier_data is None:
                continue

            while obj.modifiers:
                obj.modifiers.remove(obj.modifiers[0])

            for item in modifier_data:
                try:
                    new_mod = obj.modifiers.new(name=item["name"], type=item["type"])
                except Exception as e:
                    print(f"[ModifierRestore][SKIP] {obj.name}/{item['name']}: {e}")
                    continue

                for identifier, value in item["properties"].items():
                    try:
                        setattr(new_mod, identifier, value)
                    except Exception:
                        continue

    def reimport_asset(self, blend_path, cat_name, asset_name, context, usd_path, usd_file_name, replace_mesh=True, replace_lights=True, replace_modifiers=True):
        """Source Blend에서 컬렉션을 가져오고 USD를 연결"""
        target_col_name = f"{asset_name}_col"
        light_col_name = f"{asset_name}_light_col"

        self.delete_asset_collections(asset_name, replace_mesh=replace_mesh, replace_lights=replace_lights)
        
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            wanted = []
            if replace_mesh:
                wanted.append(target_col_name)
            if replace_lights:
                wanted.append(light_col_name)
            cols = [c for c in data_from.collections if c in wanted]
            data_to.collections = cols
            
        parent_col_name = f"{cat_name}_col"
        p_col = bpy.data.collections.get(parent_col_name)
        if not p_col:
            p_col = bpy.data.collections.new(parent_col_name)
            context.scene.collection.children.link(p_col)
            
        for col in data_to.collections:
            if col:
                p_col.children.link(col)
                if replace_mesh and replace_modifiers and col.name == target_col_name and usd_path and os.path.exists(usd_path):
                    apply_cache_to_asset_geometry(
                        col,
                        asset_name,
                        usd_path,
                        usd_file_name,
                        create_modifier=False,
                        create_cache_file=False,
                    )

    def update_asset_materials(self, context, blend_file_path, asset_name, preserve_texture_links=False):
        asset_col = bpy.data.collections.get(f"{asset_name}_col")
        if not asset_col:
            print(f"[MaterialUpdate][SKIP] {asset_name}_col not found.")
            return

        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.materials = data_from.materials

        loaded_materials = [mat for mat in data_to.materials if mat]
        if not loaded_materials:
            print(f"[MaterialUpdate][SKIP] no materials loaded from {blend_file_path}")
            return

        materials_dict = {}
        for mat in loaded_materials:
            processed_name = mat.name.split(".")[0].lower()
            materials_dict[processed_name] = mat

        def walk_collection(col):
            for obj in col.objects:
                if obj.type != 'MESH':
                    continue
                if preserve_texture_links:
                    self.update_object_material_values_only(obj, materials_dict)
                else:
                    self.replace_object_materials(obj, loaded_materials)
            for child in col.children:
                walk_collection(child)

        walk_collection(asset_col)

    def rebind_collection_materials_to_existing_scene(self, asset_name):
        asset_col = bpy.data.collections.get(f"{asset_name}_col")
        if not asset_col:
            return

        def walk_collection(col):
            for obj in col.objects:
                if obj.type == 'MESH':
                    apply_matching_materials(obj)
            for child in col.children:
                walk_collection(child)

        walk_collection(asset_col)

    def replace_object_materials(self, obj, original_materials):
        for slot in obj.material_slots:
            if not slot.material:
                continue

            scene_material_name = slot.material.name.split(".")[0].lower()
            matching_material = next(
                (mat for mat in original_materials if mat.name.split(".")[0].lower() == scene_material_name),
                None
            )

            if matching_material:
                slot.material = matching_material

    def update_object_material_values_only(self, obj, source_materials):
        for slot in obj.material_slots:
            if not slot.material:
                continue

            scene_material_name = slot.material.name.split(".")[0].lower()
            source_mat = source_materials.get(scene_material_name)
            if not source_mat:
                continue

            self.copy_material_values_preserve_links(slot.material, source_mat)

    def copy_material_values_preserve_links(self, target_mat, source_mat):
        if not (target_mat and source_mat and target_mat.use_nodes and source_mat.use_nodes):
            return
        if not (target_mat.node_tree and source_mat.node_tree):
            return

        target_nodes = {node.name: node for node in target_mat.node_tree.nodes}

        for source_node in source_mat.node_tree.nodes:
            target_node = target_nodes.get(source_node.name)
            if not target_node or target_node.type != source_node.type:
                continue

            for attr_name in ("mute", "hide", "label"):
                if hasattr(target_node, attr_name) and hasattr(source_node, attr_name):
                    try:
                        setattr(target_node, attr_name, getattr(source_node, attr_name))
                    except Exception:
                        pass

            for src_input, dst_input in zip(getattr(source_node, "inputs", []), getattr(target_node, "inputs", [])):
                if dst_input.is_linked:
                    continue
                if not hasattr(src_input, "default_value") or not hasattr(dst_input, "default_value"):
                    continue
                try:
                    src_value = src_input.default_value
                    if isinstance(src_value, (float, int, bool, str)):
                        dst_input.default_value = src_value
                    else:
                        dst_input.default_value = tuple(src_value)
                except Exception:
                    pass

    def apply_cache(self, collection, asset_name, usd_path, usd_file_name):
        return apply_cache_to_asset_geometry(
            collection,
            asset_name,
            usd_path,
            usd_file_name,
            create_modifier=False,
            create_cache_file=False,
        )
        for obj in iter_asset_geometry_meshes(collection, asset_name):
                # 엠티 하위인지 확인 (오타 수정된 안전장치)
                is_real_mesh = False
                curr = obj.parent
                while curr:
                    name_parts = curr.name.split('.')
                    base_name = name_parts
                    if base_name == asset_name:
                        is_real_mesh = True
                        break
                    curr = curr.parent

                if is_real_mesh:
                    # 🔥 [완벽 복구] 원래 모디파이어가 있는 애들만 찾아서 갱신! (새로 만들지 않음)
                    for mod in obj.modifiers:
                        if mod.type == 'MESH_SEQUENCE_CACHE':
                            unique_name = f"{usd_file_name}_{obj.name}"
                            cf = get_or_create_cache_file(unique_name, usd_path, fallback_name=usd_file_name, log_name=obj.name)
                            if not cf:
                                continue
                            cf.name = unique_name
                            cf.filepath = usd_path
                            mod.cache_file = cf
                            
                            # 프림 패스 보정
                            if mod.object_path and '/' in mod.object_path:
                                parts = mod.object_path.split('/')
                                if len(parts) > 1:
                                    parts = asset_name
                                    mod.object_path = '/'.join(parts)
                                    
class SF_OT_SetOutputPath(bpy.types.Operator):
    bl_idname = "sf.set_output_path"
    bl_label = "Set Output Path"

    prefix: bpy.props.StringProperty(name="Prefix", default="")  # 사용자 입력 프리픽스
    suffix: bpy.props.EnumProperty(
        name="Suffix",
        description="Output suffix",
        items=[
            ('default', "Default", ""),
            ('ch', "ch", ""),
            ('bg', "bg", ""),
            ('line', "line", ""),
            ('prop', "prop", ""),
            ('mask', "mask", ""),
            ('chCol', "chCol", ""),
        ],
        default='default'
    )
    custom_suffix: bpy.props.StringProperty(name="Custom Suffix", default="")

    def execute(self, context):
        import os, re
        sc = context.scene

        # 🔹 블렌드 파일 이름에서 씬 / 컷 번호 추출
        blend_name = os.path.basename(bpy.data.filepath)
        match = re.search(r"(\d{4})_(\d{4})", blend_name)
        if not match:
            self.report({'WARNING'}, f"Cannot find scene/cut in filename: {blend_name}")
            return {'CANCELLED'}

        scene_number, cut_number = match.groups()

        # 기존 렌더 경로
        filepath = sc.render.filepath
        if not filepath:
            self.report({'WARNING'}, "Output path is empty")
            return {'CANCELLED'}

        prefix_value = str(getattr(self, "prefix", "") or "").strip()
        custom_suffix_value = str(getattr(self, "custom_suffix", "") or "").strip()
        suffix_value = str(getattr(self, "suffix", "default") or "default").strip()

        if custom_suffix_value:
            suffix_str = custom_suffix_value
        elif prefix_value:
            suffix_str = prefix_value
        elif suffix_value == 'default':
            suffix_str = ""
        else:
            suffix_str = suffix_value

        new_filepath = build_incremental_save_filepath(filepath, suffix_override=suffix_str)
        if not new_filepath:
            self.report({'WARNING'}, "?뚯씪紐낆뿉??踰꾩쟾??李얠쓣 ???놁뒿?덈떎.")
            return {'CANCELLED'}

        new_filename = os.path.basename(new_filepath)
        bpy.ops.wm.save_as_mainfile(filepath=new_filepath, copy=False)
        self.report({'INFO'}, f"Saved as {new_filename}")
        return {'FINISHED'}

        dirpath = os.path.dirname(filepath)

        # 버전 추출 (예: v001)
        match = re.search(r"(v\d{3})", dirpath)
        if not match:
            self.report({'WARNING'}, "Version not found in path")
            return {'CANCELLED'}

        version = match.group(1)
        new_version = f"{version}_{self.prefix}" if self.prefix else version

        # 경로 재구성
        new_filename = f"{scene_number}_{cut_number}_{self.prefix}_" if self.prefix else f"{scene_number}_{cut_number}_"
        new_dirpath = re.sub(r"(v\d{3}.*)$", new_version, dirpath)

        new_path = os.path.join(new_dirpath, new_filename)
        sc.render.filepath = new_path

        # 🔹 line 전용 PNG 강제 세팅
        if self.prefix == "line":
            set_output_png(sc.render.image_settings, alpha=False, label="Output Path line: ")
        else:
            set_output_exr_multilayer(sc.render.image_settings, label="Output Path EXR: ")

        self.report({'INFO'}, f"Output path set from filename: {new_path}")
        return {'FINISHED'}



class SF_OT_SetOutputPath(bpy.types.Operator):
    bl_idname = "sf.set_output_path"
    bl_label = "Set Output Path"

    prefix: bpy.props.StringProperty(name="Prefix", default="")
    suffix: bpy.props.EnumProperty(
        name="Suffix",
        description="Output suffix",
        items=[
            ('default', "Default", ""),
            ('ch', "ch", ""),
            ('bg', "bg", ""),
            ('line', "line", ""),
            ('prop', "prop", ""),
            ('mask', "mask", ""),
            ('chCol', "chCol", ""),
        ],
        default='default'
    )
    custom_suffix: bpy.props.StringProperty(name="Custom Suffix", default="")

    def execute(self, context):
        import os, re

        sc = context.scene
        filepath = sc.render.filepath
        if not filepath:
            self.report({'WARNING'}, "Output path is empty")
            return {'CANCELLED'}

        prefix_value = str(getattr(self, "prefix", "") or "").strip()
        custom_suffix_value = str(getattr(self, "custom_suffix", "") or "").strip()
        suffix_value = str(getattr(self, "suffix", "default") or "default").strip()

        if custom_suffix_value:
            suffix_str = custom_suffix_value
        elif prefix_value:
            suffix_str = prefix_value
        elif suffix_value == 'default':
            suffix_str = ""
        else:
            suffix_str = suffix_value

        dirpath = os.path.dirname(filepath)
        version_source = dirpath if re.search(r"(v\d{3})", dirpath) else bpy.data.filepath
        match = re.search(r"(v\d{3})", version_source)
        if not match:
            self.report({'WARNING'}, "파일명에서 버전을 찾을 수 없습니다.")
            return {'CANCELLED'}

        my_tool = getattr(context.scene, "my_tool", None)
        scene_number = str(getattr(my_tool, "scene_number", "") or "")
        cut_number = str(getattr(my_tool, "cut_number", "") or "")
        if not scene_number or not cut_number:
            blend_name = os.path.basename(bpy.data.filepath)
            scene_cut_match = re.search(r"(\d{4})_(\d{4})", blend_name)
            if scene_cut_match:
                scene_number, cut_number = scene_cut_match.groups()

        version = match.group(1)
        new_version = f"{version}_{suffix_str}" if suffix_str else version
        new_dirpath = re.sub(r"(v\d{3}.*)$", new_version, dirpath)

        if scene_number and cut_number:
            new_filename = f"{scene_number}_{cut_number}_{suffix_str}_" if suffix_str else f"{scene_number}_{cut_number}_"
        else:
            new_filename = f"{suffix_str}_" if suffix_str else ""

        new_path = os.path.join(new_dirpath, new_filename)
        sc.render.filepath = new_path

        if suffix_str == "line":
            set_output_png(sc.render.image_settings, alpha=False, label="Output Path line: ")
        else:
            set_output_exr_multilayer(sc.render.image_settings, label="Output Path EXR: ")

        self.report({'INFO'}, f"Output path set: {new_path}")
        return {'FINISHED'}


class SF_OT_SetOutputPath(bpy.types.Operator):
    bl_idname = "sf.set_output_path"
    bl_label = "Set Output Path"

    prefix: bpy.props.StringProperty(name="Prefix", default="")
    suffix: bpy.props.EnumProperty(
        name="Suffix",
        description="Output suffix",
        items=[
            ('default', "Default", ""),
            ('ch', "ch", ""),
            ('bg', "bg", ""),
            ('line', "line", ""),
            ('prop', "prop", ""),
            ('mask', "mask", ""),
            ('chCol', "chCol", ""),
        ],
        default='default'
    )
    custom_suffix: bpy.props.StringProperty(name="Custom Suffix", default="")

    def execute(self, context):
        import os, re

        sc = context.scene
        prefix_value = str(getattr(self, "prefix", "") or "").strip()
        custom_suffix_value = str(getattr(self, "custom_suffix", "") or "").strip()
        suffix_value = str(getattr(self, "suffix", "default") or "default").strip()

        if custom_suffix_value:
            suffix_str = custom_suffix_value
        elif prefix_value:
            suffix_str = prefix_value
        elif suffix_value == 'default':
            suffix_str = ""
        else:
            suffix_str = suffix_value

        my_tool = getattr(context.scene, "my_tool", None)
        scene_number = str(getattr(my_tool, "scene_number", "") or "")
        cut_number = str(getattr(my_tool, "cut_number", "") or "")
        if not scene_number or not cut_number:
            blend_name = os.path.basename(bpy.data.filepath)
            scene_cut_match = re.search(r"(\d{4})_(\d{4})", blend_name)
            if scene_cut_match:
                scene_number, cut_number = scene_cut_match.groups()

        filepath = sc.render.filepath
        dirpath = os.path.dirname(filepath) if filepath else ""

        version_match = None
        for candidate in (dirpath, filepath, bpy.data.filepath):
            if candidate:
                version_match = re.search(r"(v\d{3})", candidate)
            if version_match:
                break

        if version_match:
            version = version_match.group(1)
        else:
            try:
                version = f"v{int(current_version):03d}"
            except Exception:
                version = "v001"

        version_folder = f"{version}_{suffix_str}" if suffix_str else version
        if dirpath and re.search(r"(v\d{3}[^/\\\\]*)$", dirpath):
            new_dirpath = re.sub(r"(v\d{3}[^/\\\\]*)$", version_folder, dirpath)
        else:
            base_output_dir = get_project_output_path(scene_number or "0000", cut_number or "0000")
            new_dirpath = os.path.join(base_output_dir, version_folder)

        if scene_number and cut_number:
            new_filename = f"{scene_number}_{cut_number}_{suffix_str}_" if suffix_str else f"{scene_number}_{cut_number}_"
        else:
            new_filename = f"{suffix_str}_" if suffix_str else ""

        new_path = os.path.join(new_dirpath, new_filename)
        sc.render.filepath = new_path

        if suffix_str == "line":
            set_output_png(sc.render.image_settings, alpha=False, label="Output Path line: ")
        else:
            set_output_exr_multilayer(sc.render.image_settings, label="Output Path EXR: ")

        self.report({'INFO'}, f"Output path set: {new_path}")
        return {'FINISHED'}


class SF_OT_SaveIncrementalSuffix(bpy.types.Operator):
    bl_idname = "sf.save_incremental_suffix"
    bl_label = "Incremental Save"

    suffix_items = [
        ('default', "Default", "No suffix (just v002)"),
        ('ch', "ch", "Character"),
        ('bg', "bg", "Background"),
        ('prop', "prop", "Prop"),
        ('mask', "mask", "Mask"),
        ('line', "line", "Line"),
    ]
    suffix: bpy.props.EnumProperty(
        name="Suffix",
        description="Choose suffix for new version",
        items=suffix_items,
        default='default'
    )

    custom_suffix: bpy.props.StringProperty(
        name="Custom",
        description="Custom suffix (if not empty, overrides above)",
        default=""
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        # 1줄: Default / ch / bg
        row = layout.row(align=True)
        row.prop_enum(self, "suffix", 'default')
        row.prop_enum(self, "suffix", 'ch')
        row.prop_enum(self, "suffix", 'bg')

        # 2줄: prop / mask / line
        row = layout.row(align=True)
        row.prop_enum(self, "suffix", 'prop')
        row.prop_enum(self, "suffix", 'mask')
        row.prop_enum(self, "suffix", 'line')

        # 3줄: 항상 표시되는 Custom 입력칸
        row = layout.row(align=True)
        row.label(text="Custom:")
        row.prop(self, "custom_suffix", text="")

    def execute(self, context):
        filepath = bpy.data.filepath
        if not filepath:
            self.report({'WARNING'}, "현재 파일이 저장되지 않았습니다.")
            return {'CANCELLED'}

        dirpath = os.path.dirname(filepath)
        filename = os.path.basename(filepath)

        # 버전 찾기
        match = re.search(r"(v\d{3})", filename)
        if not match:
            self.report({'WARNING'}, "파일명에서 버전을 찾을 수 없습니다.")
            return {'CANCELLED'}

        version_str = match.group(1)  # "v001"
        version_num = int(version_str[1:])
        new_version_str = f"v{version_num+1:03d}"

        # suffix 결정
        if self.custom_suffix.strip():
            suffix_str = self.custom_suffix.strip()
        elif self.suffix == 'default':
            suffix_str = ""
        else:
            suffix_str = self.suffix

        new_version_full = f"{new_version_str}_{suffix_str}" if suffix_str else new_version_str

        # 새 파일명
        new_filename = re.sub(r"v\d{3}.*\.blend$", new_version_full + ".blend", filename)
        new_filepath = os.path.join(dirpath, new_filename)

        bpy.ops.wm.save_as_mainfile(filepath=new_filepath, copy=False)

        self.report({'INFO'}, f"Saved as {new_filename}")
        return {'FINISHED'}

library_path = os.path.normpath(r"M:\RND\SFtools\2025\lookdev\blend\SF_Paint.blend")
target_group_name = "SF_Paint"

# --------------------------------------------------------
# 기능 1: SF_Paint 노드그룹 링크 + 교체
# --------------------------------------------------------
def ensure_linked_group():
    for ng in bpy.data.node_groups:
        if ng.library and ng.name == target_group_name:
            libpath = os.path.normpath(bpy.path.abspath(ng.library.filepath))
            if libpath == library_path:
                return ng

    directory = library_path + "\\NodeTree\\"
    filepath = directory + target_group_name

    bpy.ops.wm.link(
        filepath=filepath,
        directory=directory,
        filename=target_group_name,
        link=True
    )

    for ng in bpy.data.node_groups:
        if ng.library and ng.name.startswith(target_group_name):
            libpath = os.path.normpath(bpy.path.abspath(ng.library.filepath))
            if libpath == library_path:
                return ng
    return None

def relink_sf_paint_nodes():
    linked_group = ensure_linked_group()
    if not linked_group:
        return 0

    replaced_count = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "GROUP" and node.node_tree:
                if node.node_tree.name.lower().startswith("sf_paint"):
                    node.node_tree = linked_group
                    replaced_count += 1
    return replaced_count

# --------------------------------------------------------
# 기능 2: Alpha Hashed → Opaque 변환
# --------------------------------------------------------
def set_alpha_hashed_to_opaque():
    count = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        if hasattr(mat, "blend_method") and mat.blend_method == 'HASHED':
            mat.blend_method = 'OPAQUE'
            count += 1
    return count

# --------------------------------------------------------
# 통합 실행 오퍼레이터
# --------------------------------------------------------
class SF_OT_AllInOne(bpy.types.Operator):
    """SF_Paint 교체 + Alpha Hashed → Opaque 변환"""
    bl_idname = "sf.all_in_one"
    bl_label = "Fix Paint + Opaque"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        paint_count = relink_sf_paint_nodes()
        opaque_count = set_alpha_hashed_to_opaque()
        self.report({'INFO'}, f"SF_Paint {paint_count}개 교체, 머티리얼 {opaque_count}개 변경")
        return {'FINISHED'}

def get_render_preset_json_path(project_name=None):
    """
    현재 프로젝트 기준 renderPreset.json 경로 반환
    예:
        THE_TRAP -> T:/_json/renderPreset.json
        DSC      -> S:/_json/renderPreset.json
        FUZZ     -> Z:/_json/renderPreset.json
    """
    return get_project_json_path("renderPreset.json", project_name)


_render_preset_cache = {}
_render_preset_missing_warned = set()


def load_render_presets(project_name=None):
    """
    현재 프로젝트의 _json/renderPreset.json 을 읽어 프리셋 딕셔너리 반환
    """
    json_path = get_render_preset_json_path(project_name)

    if not json_path:
        print("[RenderPreset] 프로젝트 경로를 찾을 수 없습니다.")
        return {}

    if not os.path.exists(json_path):
        print(f"[RenderPreset] renderPreset.json 없음: {json_path}")
        return {}

    try:
        mtime = os.path.getmtime(json_path)
        cached = _render_preset_cache.get(json_path)
        if cached and cached.get("mtime") == mtime:
            return dict(cached.get("data", {}))

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            print(f"[RenderPreset] JSON 최상위 구조가 dict가 아닙니다: {json_path}")
            return {}

        _render_preset_cache[json_path] = {
            "mtime": mtime,
            "data": dict(data),
        }
        return dict(data)

    except Exception as e:
        print(f"[RenderPreset] JSON 불러오기 실패: {json_path} / {e}")
        return {}


def load_render_presets(project_name=None):
    json_path = get_render_preset_json_path(project_name)

    if not json_path:
        print("[RenderPreset] 프로젝트 경로를 찾을 수 없습니다.")
        return {}

    if not os.path.exists(json_path):
        if json_path not in _render_preset_missing_warned:
            print(f"[RenderPreset] renderPreset.json 없음: {json_path}")
            _render_preset_missing_warned.add(json_path)
        return {}

    try:
        mtime = os.path.getmtime(json_path)
        cached = _render_preset_cache.get(json_path)
        if cached and cached.get("mtime") == mtime:
            return dict(cached.get("data", {}))

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            print(f"[RenderPreset] JSON 최상위 구조가 dict가 아닙니다: {json_path}")
            return {}

        _render_preset_cache[json_path] = {
            "mtime": mtime,
            "data": dict(data),
        }
        if json_path in _render_preset_missing_warned:
            _render_preset_missing_warned.discard(json_path)
        return dict(data)

    except Exception as e:
        print(f"[RenderPreset] JSON 불러오기 실패: {json_path} / {e}")
        return {}


def get_preset_items(self, context):
    """
    현재 프로젝트 기준 프리셋 목록을 EnumProperty 아이템으로 반환
    """
    presets = load_render_presets()
    items = [(key, key, f"Apply {key} render preset") for key in presets.keys()]
    return items if items else [("NONE", "None", "No presets found")]


class SF_OT_ApplyRenderPresets(bpy.types.Operator):
    """선택한 Render Preset 적용"""
    bl_idname = "sf.apply_render_presets"
    bl_label = "Apply Render Presets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        presets = load_render_presets()
        preset_name = scene.render_preset_enum

        if preset_name == "NONE":
            self.report({'ERROR'}, "적용할 Render Preset이 없습니다.")
            return {'CANCELLED'}

        if preset_name not in presets:
            self.report({'ERROR'}, f"{preset_name} 프리셋을 찾을 수 없습니다.")
            return {'CANCELLED'}

        preset = presets[preset_name]
        self.apply_preset(context, preset_name, preset)
        self.report({'INFO'}, f"{preset_name} 프리셋 적용 완료")
        return {'FINISHED'}

    def apply_preset(self, context, preset_name, preset):
        scene = context.scene
        render_settings = preset.get("render_settings", {})

        # --- 일반 render_settings 적용 ---
        for key, value in render_settings.items():
            try:
                set_nested_property(scene, key, value)
            except Exception as e:
                print(f"[WARN] {key} 적용 실패: {e}")



class SF_OT_SetLightBounces(bpy.types.Operator):
    """씬의 모든 라이트의 max_bounces 값을 1024로 설정"""
    bl_idname = "sf.set_light_bounces"
    bl_label = "Set Light Bounces to 1024"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                try:
                    obj.data.cycles.max_bounces = 1024
                    count += 1
                except AttributeError:
                    # 라이트 타입에 따라 cycles 속성이 없을 수도 있음
                    self.report({'WARNING'}, f"{obj.name}에는 cycles.max_bounces 속성이 없음")
        self.report({'INFO'}, f"{count}개의 라이트를 1024로 설정 완료")
        return {'FINISHED'}

# =========================
# Make Color Pass Operator
# =========================
import bpy
from bpy.props import EnumProperty

class SF_OT_MakeColorPass(bpy.types.Operator):
    bl_idname = "sf.make_color_pass"
    bl_label  = "Make Color Pass"
    bl_options = {'REGISTER', 'UNDO'}

    layer_choice: EnumProperty(
        name="Target ViewLayer",
        items=[
            ('SELECTED', "Selected Layer", "현재 활성 레이어 유지"),
            ('RENAME',   "Rename ch_vl → chCol_vl", "ch_vl의 이름만 chCol_vl로 변경"),
        ],
        default='RENAME',
    )

    # --- 헬퍼: RGBA 커스텀 프로퍼티 강제 (Linear Float Array + UI COLOR) ---
    def _ensure_color_idprop_rgba(self, id_block, key, rgba=(1.0,1.0,1.0,1.0)):
        try:
            need_reset = True
            if hasattr(id_block, "keys") and (key in id_block.keys()):
                v = id_block[key]
                if isinstance(v, (list, tuple)) and len(v) in (3, 4):
                    need_reset = False

            if need_reset:
                try:
                    if key in id_block.keys():
                        del id_block[key]
                except Exception:
                    pass
                id_block[key] = (float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
            else:
                if len(id_block[key]) == 3:
                    id_block[key] = (float(rgba[0]), float(rgba[1]), float(rgba[2]))
                else:
                    id_block[key] = (float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))

            try:
                ui = id_block.id_properties_ui(key)
                ui.update(subtype='COLOR', min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, default=id_block[key])
            except Exception:
                pass
        except Exception as e:
            print(f"[WARN] _ensure_color_idprop_rgba failed on {getattr(id_block,'name',type(id_block))}.{key}: {e}")

    # --- 헬퍼: 모든 머티리얼 'Shadow Color' 입력 화이트 ---
    def _set_all_shadow_color_inputs_white(self):
        WHITE4 = (1.0, 1.0, 1.0, 1.0)
        cnt = 0
        for mat in bpy.data.materials:
            if not (mat and mat.use_nodes and mat.node_tree):
                continue
            for node in mat.node_tree.nodes:
                for inp in getattr(node, "inputs", []):
                    if inp.name == "Shadow Color" and hasattr(inp, "default_value"):
                        try:
                            inp.default_value = WHITE4
                            cnt += 1
                        except Exception as e:
                            print(f"[WARN] Shadow Color set failed on {mat.name}/{node.name}: {e}")
        print(f"[INFO] Shadow Color inputs set to white: {cnt}")

    def execute(self, context):
        sc = context.scene

        # 1) ch_vl → chCol_vl 이름만 변경(복제 금지)
        if getattr(self, "layer_choice", "RENAME") == 'RENAME':
            vls = sc.view_layers
            if "ch_vl" in vls:
                if "chCol_vl" in vls:
                    context.window.view_layer = vls["chCol_vl"]
                else:
                    vls["ch_vl"].name = "chCol_vl"
                    context.window.view_layer = vls["chCol_vl"]
            else:
                if "chCol_vl" in vls:
                    context.window.view_layer = vls["chCol_vl"]
                else:
                    new_vl = vls.new(name="chCol_vl")
                    context.window.view_layer = new_vl

        # 2) 커스텀 프로퍼티(Linear RGBA) 화이트로 강제
        WHITE4 = (1.0, 1.0, 1.0, 1.0)
        COLOR_KEYS = ("P02_Shadow_Color", "P01_Ambient_Color")

        for obj in bpy.data.objects:
            for k in COLOR_KEYS:
                self._ensure_color_idprop_rgba(obj, k, WHITE4)
        for k in COLOR_KEYS:
            self._ensure_color_idprop_rgba(sc, k, WHITE4)
        for w in bpy.data.worlds:
            for k in COLOR_KEYS:
                self._ensure_color_idprop_rgba(w, k, WHITE4)
        # 1.5) lightmask_vl 렌더 제외 (비활성화)
        for vl in sc.view_layers:
            if vl.name.startswith("chCol_"):
                vl.use = True
                print(f"[DEBUG] ViewLayer {vl.name} → ON")
            else:
                vl.use = False
                print(f"[DEBUG] ViewLayer {vl.name} → OFF") 
               
        # 2-추가) 머티리얼 노드 'Shadow Color' 소켓 화이트
        self._set_all_shadow_color_inputs_white()

        # 3) Output File Version - Current
        try:
            bpy.ops.sf.version_operator(increment=-999)
        except Exception as e:
            self.report({'WARNING'}, f"Version(Current) 실패: {e}")

        # 4) Output Path Settings - Custom='chCol' 적용
        try:
            if hasattr(sc, "my_tool"):
                sc.my_tool.custom_prefix = "chCol"
        except Exception:
            pass
        try:
            bpy.ops.sf.set_output_path(prefix="chCol")
        except Exception as e:
            self.report({'WARNING'}, f"Output Path 적용 실패: {e}")

        # 5) PNG 강제
        try:
            set_output_png(sc.render.image_settings, alpha=False, label="Color Pass: ")
        except Exception as e:
            self.report({'WARNING'}, f"PNG 설정 실패: {e}")

        self.report({'INFO'}, "Color Pass 완료: ch_vl→chCol_vl(이름만), 컬러/쉐도우 화이트, chCol 출력, PNG")
        return {'FINISHED'}

TARGET_PREFIX = "SF_Paint"

def _norm(s: str) -> str:
    return (s or "").lower().replace(" ", "").replace("_", "")

def _find_input(node, target_name: str):
    # 1) 정확히 일치
    if target_name in node.inputs:
        return node.inputs[target_name]

    # 2) 정규화 비교 (공백/언더스코어/대소문자 무시)
    tn = _norm(target_name)
    for s in node.inputs:
        if _norm(getattr(s, "name", "")) == tn:
            return s
    return None

def set_group_inputs_in_nodetree(nt, visited, target_prefix, value_map):
    """
    value_map 예:
      {"Strength": 0.2, "Mask_Int": 1.0, "Brusk_Int": 0.02, "Noise Int": 0.02}
    """
    if not nt:
        return 0

    nt_id = nt.as_pointer()
    if nt_id in visited:
        return 0
    visited.add(nt_id)

    changed = 0

    for node in nt.nodes:
        # 타겟 그룹 처리
        if node.type == 'GROUP' and node.node_tree and node.node_tree.name.startswith(target_prefix):
            for input_name, v in value_map.items():
                sock = _find_input(node, input_name)
                if sock is not None and hasattr(sock, "default_value"):
                    try:
                        sock.default_value = float(v)
                        changed += 1
                    except Exception:
                        pass

        # 중첩 그룹 재귀
        if node.type == 'GROUP' and node.node_tree:
            changed += set_group_inputs_in_nodetree(node.node_tree, visited, target_prefix, value_map)

    return changed



class SF_OT_ApplySFpaintGlobalControl(bpy.types.Operator):
    bl_idname = "sf.apply_sfpaint_global_control"
    bl_label = "Apply SFpaint Global Control"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        strength = float(context.scene.my_tool.sfpaint_emission_strength)
        mask_int = float(context.scene.my_tool.sfpaint_mask_int)
        brusk_int = float(context.scene.my_tool.sfpaint_brusk_int)
        noise_int = float(context.scene.my_tool.sfpaint_noise_int)

        value_map = {
            "Strength": strength,
            "Mask_Int": mask_int,
            "Brusk_Int": brusk_int,
            "Noise Int": noise_int,
        }

        visited = set()
        total_changed = 0
        for mat in bpy.data.materials:
            if not mat or not mat.use_nodes or not mat.node_tree:
                continue
            total_changed += set_group_inputs_in_nodetree(mat.node_tree, visited, TARGET_PREFIX, value_map)

        self.report({'INFO'}, f"[SF_Paint] updated sockets: {total_changed}")
        return {'FINISHED'}




import bpy

class SF_OT_ClearSelectedMaterials(bpy.types.Operator):
    bl_idname = "sf.clear_selected_materials"
    bl_label = "Clear Materials from Selected"
    bl_description = "선택된 오브젝트의 모든 메터리얼 슬롯을 제거합니다"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected = bpy.context.selected_objects
        if not selected:
            self.report({'INFO'}, "선택된 오브젝트가 없습니다.")
            return {'CANCELLED'}

        cleared_count = 0
        for obj in selected:
            if obj.type == 'MESH':
                obj.data.materials.clear()
                cleared_count += 1
                print(f"[OK] {obj.name} → 메터리얼 제거됨")

        self.report({'INFO'}, f"{cleared_count}개 오브젝트에서 메터리얼 제거 완료")
        return {'FINISHED'}
        
class SF_OT_ClearSelectedMaterialsPopup(bpy.types.Operator):
    bl_idname = "sf.clear_selected_materials_popup"
    bl_label = "Delete Materials on Selected"
    bl_description = "선택된 오브젝트의 모든 머티리얼을 삭제합니다 (확인 팝업 포함)"

    def invoke(self, context, event):
        # Blender 기본 확인 팝업 띄우기
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        # 실제 삭제 로직은 기존 오퍼레이터 호출
        bpy.ops.sf.clear_selected_materials('INVOKE_DEFAULT')
        self.report({'INFO'}, "✅ 선택한 오브젝트의 머티리얼이 모두 삭제되었습니다.")
        return {'FINISHED'}

class SF_OT_SetOutputFormat(bpy.types.Operator):
    bl_idname = "sf.set_output_format"
    bl_label = "Set Output Format"
    bl_description = "렌더 출력 포맷을 원클릭으로 설정합니다"

    format_type: bpy.props.StringProperty()

    def execute(self, context):
        sc = context.scene.render.image_settings

        if self.format_type == 'EXR':
            set_output_exr_multilayer(sc, label="Output Button EXR: ")
            self.report({'INFO'}, "Output Format: EXR Multilayer (RGBA, 16-bit)")

        elif self.format_type == 'PNG':
            set_output_png(sc, alpha=False, label="Output Button PNG: ")
            self.report({'INFO'}, "Output Format: PNG (RGB, 8-bit)")

        elif self.format_type == 'PNG_ALPHA':
            set_output_png(sc, alpha=True, label="Output Button PNG Alpha: ")
            self.report({'INFO'}, "Output Format: PNG with Alpha (RGBA, 8-bit)")

        return {'FINISHED'}

class SF_OT_DeleteSolidifyLine(bpy.types.Operator):
    bl_idname = "sf.delete_solidify_line"
    bl_label = "Delete Solidify Line"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        removed = []
        checked = 0

        print("\n" + "=" * 80)
        print("🔥 Solidify Modifier Flip ON 제거 시작")
        print(f"Scene: {scene.name}")
        print("=" * 80)

        for obj in scene.objects:
            if obj.type != 'MESH':
                continue

            for mod in list(obj.modifiers):
                if mod.type != 'SOLIDIFY':
                    continue

                checked += 1

                obj_name = obj.name
                mod_name = mod.name
                flip_on = bool(getattr(mod, "use_flip_normals", False))

                print(f"[CHECK] Object: {obj_name} / Modifier: {mod_name} / Flip: {flip_on}")

                if flip_on:
                    removed.append((obj_name, mod_name))
                    obj.modifiers.remove(mod)
                    print(f"  ✅ REMOVED: {obj_name} -> {mod_name}")

        print("=" * 80)
        print(f"검사한 Solidify Modifier 수: {checked}")
        print(f"삭제한 Modifier 수: {len(removed)}")

        if removed:
            print("\n삭제 목록:")
            for obj_name, mod_name in removed:
                print(f" - {obj_name} / {mod_name}")
        else:
            print("삭제할 Flip ON Solidify Modifier가 없습니다.")

        print("🔥 Solidify Modifier Flip ON 제거 완료")
        print("=" * 80 + "\n")

        self.report({'INFO'}, f"Delete Solidify Line 완료: {len(removed)}개 삭제")
        return {'FINISHED'}


################################################################
#########################UI#####################################
################################################################

# Scene Browser Panel (이건 기존처럼 단독 아코디언으로 유지)
class SF_PT_SceneBrowser(bpy.types.Panel):
    bl_label = "Scene Browser"
    bl_idname = "SF_PT_scene_browser"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SF_Render"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        my_tool = context.scene.my_tool
        project_settings = context.scene.my_project_settings

        box = layout.box()

        global last_mtime
        mtime = os.path.getmtime(SCRIPT_PATH) if os.path.exists(SCRIPT_PATH) else None
        script_path = os.path.abspath(__file__)
        last_modified = "File not found"
        try:
            mod_time = os.path.getmtime(script_path)
            last_modified = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
        except OSError:
            pass

        row = layout.row()  
        row.scale_y = 0.8
        row.scale_x = 1
        row.alignment = 'CENTER'
        row.label(text=last_modified)         
        row.label(text="Storyfarm")

        row = box.row()        
        if last_mtime and mtime and mtime > last_mtime:
            row.alert = True
            row.scale_y = 1.6
            row.operator("dev.reload_rrrender", icon="FILE_REFRESH")
        else:
            row.scale_y = 1.6
            row.operator("dev.reload_rrrender", icon="FILE_REFRESH")
            
           
                      
        if can_show_deploy_tools():
            row = box.row()
            row.scale_y = 1.2
            row.operator("dev.deploy_rrrender", icon="EXPORT")

        row = box.row()
        row.prop(project_settings, "projects", text="Project")       
        row.operator("sf.refresh_scene_and_cut_cache", text="", icon="FILE_REFRESH")
        row.operator("sf.project_path_settings_popup", text="", icon="PREFERENCES")
        row.operator("sf.validate_project", text="", icon="CHECKMARK")
        row = box.row()
        row.prop(my_tool, "scene_number", text=get_browser_level_label(1))
        row.operator("sf.refresh_scene_and_cut_cache", text="", icon="FILE_REFRESH")
        if get_browser_level_definition(2):
            row = box.row()
            row.prop(my_tool, "cut_number", text=get_browser_level_label(2))
            row.operator("sf.refresh_scene_and_cut_cache", text="", icon="FILE_REFRESH")
        for index in range(3, MAX_BROWSER_LEVELS + 1):
            level = get_browser_level_definition(index)
            if not level:
                continue
            row = box.row()
            row.prop(my_tool, f"browser_level_{index}", text=get_browser_level_label(index))
            row.operator("sf.refresh_scene_and_cut_cache", text="", icon="FILE_REFRESH")
        row = box.row()
        row.prop(my_tool, "blend_file")
        row.operator("file.open_cut_folder", text="", icon='FILE_FOLDER')
        row = box.row()
        row.scale_y = 1.3
        row.operator("file.open_file", text="Open") 
        row = box.row()
        row.operator("sf.save_render_scene", text="Save as v000")
        row.operator("sf.save_incremental_suffix", text="Incremental Save")
        
        # row = box.row(align=True)      
        # row.operator("sf.set_scene_from_file", text="Set Browser at Current Scene")    
        set_scene_settings()





# ==============================================================================
# ▼ 여기서부터 탭(Tab) 구성을 위한 '헬퍼 클래스'들 입니다. (기존 클래스 내용 100% 복붙)
# ==============================================================================

# --- [1. BUILD] Scene 구성 및 어셋 관리 ---
class SF_UI_BuildTab:
    @staticmethod
    def draw(layout, context):
        scene = context.scene
        
        box_main = layout.box()
        filename = os.path.basename(bpy.data.filepath) if bpy.data.filepath else "Untitled"
        box_main.label(text=filename, icon='FILE_BLEND')    
        
        row = box_main.row(align=True)        
        row.scale_y = 1.3
        row.operator("sf.build_scene_operator", text="Build Scene", icon='MOD_BUILD')

        row = box_main.row(align=True)
        row.prop(scene, "render_preset_enum", text="Preset")
        row.scale_x = 2
        row.operator("sf.apply_render_presets", text="", icon='CHECKMARK')
        
        box_list = layout.box()
        row_h = box_list.row(align=True)
        left_side = row_h.row(align=True)
        left_side.alignment = 'LEFT'
        left_side.label(text="Asset List", icon='ASSET_MANAGER')
        row_h.label(text="") 
        right_side = row_h.row(align=True)
        right_side.alignment = 'RIGHT'
        right_side.operator("sf.toggle_all_operator", text="", icon='CHECKBOX_HLT')
        right_side.operator("sf.generate_operator", text="", icon='FILE_REFRESH')
        right_side.operator("sf.import_scene_camera", text="", icon='VIEW_CAMERA')

        sorted_categories = sorted(scene.sf_file_categories, key=lambda cat: cat.name)
        if sorted_categories:
            # 💡 [핵심] 박스 간의 여백을 없애기 위해 align=True 컬럼으로 한 번 감싸줍니다.
            categories_col = box_list.column(align=True)
            
            for category in sorted_categories:
                cat_container = categories_col.box()
                split = cat_container.split(factor=0.1, align=True) 
                
                col1 = split.column(align=True)
                col1.alignment = 'LEFT'
                display_name = "PR" if category.name.upper() == "PROP" else category.name.upper()
                op = col1.operator("sf.toggle_category_operator", text=display_name, emboss=False)
                op.category_name = category.name
                
                col2 = split.column(align=True)
                col2.scale_y = 1.0
                sorted_items = sorted(category.items, key=lambda item: item.name)
                for i in range(0, len(sorted_items), 2):
                    item_row = col2.row(align=True)
                    for j in range(2):
                        if i + j < len(sorted_items):
                            item = sorted_items[i + j]
                            item_row.prop(item, "is_selected", text=item.name, toggle=True)
                        else:
                            item_row.label(text="")
        else:
            box_list.label(text="No Assets Generated.", icon='INFO')
            
        row_imp = box_list.row(align=True)
        row_imp.scale_y = 1.7
        project = scene.my_project_settings.projects
        if project in ['DSC', 'THE_TRAP', 'ARBOBION', 'BTS']:
            row_imp.operator("sf.import_and_update_operator_dsc", text="IMPORT ASSET", icon='IMPORT')
        else:
            row_imp.operator("sf.import_selected_operator", text="IMPORT (Legacy)", icon='IMPORT')

        box_update = layout.box()
        box_update.label(text="Update Asset", icon='FILE_REFRESH')
        row = box_update.row(align=True)
        row.scale_y = 1.3
        row.operator("sf.update_selected_operator_dsc", text="Sync Cache", icon='FILE_REFRESH')
        row.operator("sf.update_from_publish", text="Reset to Pub", icon='FILE_BACKUP')
        
        box_tools = layout.box()        
        # box_update = layout.box()
        box_tools.label(text="Shader Tools", icon='SHADING_RENDERED')
        row = box_tools.row(align=True)
        row.scale_y = 1.3
        row.operator("sf.all_in_one", text="ReCore Mat", icon='SHADING_RENDERED')
        row.operator("object.sf_link_light_properties", text="ReLink Light", icon='DRIVER')

        # box_tools = layout.box()
        # icon = 'TRIA_DOWN' if scene.sf_show_advanced else 'TRIA_RIGHT'
        # box_tools.prop(scene, "sf_show_advanced", icon=icon, text="Tools", emboss=False)

        # if scene.sf_show_advanced:



# --- [2. OUTPUT] 렌더 범위 ~ 렌더 프리셋 ---
class SF_UI_OutputTab:
    @staticmethod
    def draw(layout, context):
        scene = context.scene
        
        box = layout.box()
        box.label(text="Render Range", icon='PREVIEW_RANGE')
        row = box.row(align=True)
        row.operator("frame.range_operator", text="Full").option = "FULL"
        row.operator("frame.range_operator", text="Current Still").option = "CURRENT"

        box = layout.box()
        box.label(text="Output File Version", icon='FILE_NEW')
        row = box.row(align=True)
        row.operator("sf.version_operator", text="Dn").increment = -1
        row.operator("sf.version_operator", text="Current").increment = -999
        row.operator("sf.version_operator", text="Up").increment = 1
        
        box = layout.box()
        box.label(text="Output Path Settings", icon='FILE_FOLDER')
        row = box.row(align=True)
        row.operator("sf.set_output_path", text="ch").prefix = "ch"
        row.operator("sf.set_output_path", text="bg").prefix = "bg"
        row.operator("sf.set_output_path", text="line").prefix = "line"
        row.operator("sf.set_output_path", text="prop").prefix = "prop"
        row = box.row(align=True)
        row.prop(context.scene.my_tool, "custom_prefix", text="Custom")
        row.operator("sf.set_output_path", text="", icon='CHECKMARK').prefix = context.scene.my_tool.custom_prefix
        
        row_format = box.row(align=True)
        row_format.operator("sf.set_output_format", text="EXR").format_type = 'EXR'
        row_format.operator("sf.set_output_format", text="PNG").format_type = 'PNG'
        row_format.operator("sf.set_output_format", text="PNG (Alpha)").format_type = 'PNG_ALPHA'
 
        box_preset = layout.box()
        box_preset.label(text="Render Presets", icon='PRESET')
        row = box_preset.row(align=True)
        row.operator("render.set_cycles_render_settings", text="Denoise")
        row = box_preset.row(align=True)
        row.operator("sf.set_light_bounces", text="Fix Light Bounce to 1024")

        box_render = layout.box()
        box_render.label(text="Rendering", icon='RESTRICT_RENDER_OFF')
        row_submit = box_render.row()
        row_submit.scale_y = 1.5
        row_submit.operator("wm.submit_blender_to_deadline", text="Submit to Deadline")




# --- [3. CACHE] 애니메이션 및 캐시 (위치 변경!) ---
class SF_UI_CacheTab:
    @staticmethod
    def draw(layout, context):
        box_ani = layout.box()
        box_ani.label(text="2 Comma Ani", icon='ANIM_DATA')
        row = box_ani.row(align=True)
        row.operator("object.make_2com", text="Make 2Com")
        row.operator("object.del_2com", text="Del 2Com")

        box_cash = layout.box()
        box_cash.label(text="Cash Tools", icon='SHAPEKEY_DATA')
        row = box_cash.row(align=True)
        row.operator("object.bake_shape_keys", text="Bake to ShapeKey")


# --- [4. MASK / PASS] 마스크들과 패스 생성 통합 (위치 변경!) ---
class SF_UI_MaskPassTab:
    @staticmethod
    def draw(layout, context):
        scene = context.scene

        box = layout.box()
        box.label(text="Light Mask", icon='LIGHT')
        row = box.row(align=True)
        row.operator("object.apply_light_mask", text="Add")
        row.operator("object.update_light_mask", text="Update")
        row.operator("object.remove_light_mask", text="Remove")
        row = box.row(align=True)     
        row.operator("object.make_shared_unique_material", text="Material Unique Selected")

        box = layout.box()
        box.label(text="Caustics Mask", icon='MOD_FLUIDSIM')
        row = box.row(align=True)
        row.operator("object.apply_caustics_mask", text="Add")
        row.operator("object.remove_caustics_mask", text="Remove")

        box = layout.box()
        box.label(text="Color Pass", icon='COLOR')        
        row_pass = box.row()
        row_pass.scale_y = 1.3
        row_pass.operator("sf.make_color_pass", text="Make Color Pass")
        
        box = layout.box()
        box.label(text="Set Ch Blocker", icon='MESH_CUBE')
        row = box.row(align=True)
        row.operator("object.apply_blocker", text="Add")
        row.operator("object.remove_blocker", text="Remove")

        box = layout.box()
        box.label(text="Set Shadow Catcher", icon='SHADING_RENDERED')
        row = box.row(align=True)
        row.operator("object.apply_shadow_catcher", text="Add")
        row.operator("object.remove_shadow_catcher", text="Remove")


# --- [5. OUTLINE] 라인 작업 ---
class SF_UI_OutlineTab:
    @staticmethod
    def draw(layout, context):
        box = layout.box()
        box.label(text="SF_OutputLine", icon="GREASEPENCIL")
        row = box.row(align=True)
        row.operator("object.sf_update_to_cycles_independent", text="Make Outline")  
        row = box.row(align=True)
        row.operator("object.sf_bake_outline", text="Bake Outline")
        row.operator("object.sf_clear_bake_outline", text="Clear Bake")


# --- [6. TOOLS] 클린업 툴 & SFpaint ---
class SF_UI_ToolsTab:
    @staticmethod
    def draw(layout, context):
        scene = context.scene
        
        # (상단 CleanUp Tools 박스 등은 그대로 유지)
        box = layout.box()
        box.label(text="CleanUp Tools", icon='BRUSH_DATA')
        row = box.row(align=True)
        row.operator("sf.subdivide_class", text="SubdivAll")
        row.operator("sf.unsubdivide_class", text="UnSubdivAll")
        row = box.row(align=True)  
        row.operator("sf.cleanup_orphans_combined1", text="CleanUp Mat") 
        row.operator("object.delete_non_visible_meshes", text="Del Invisible")
        row = box.row(align=True)           
        row.operator("sf.clear_selected_materials_popup", text="Delete Material on Selected", icon='TRASH') 
        row.operator("sf.delete_solidify_line", text="Delete Solidify Line", icon='TRASH')
        row = box.row(align=True)   
        row.operator("object.replace_botaniq_library_path", text="RePath Botaniq")
        row.operator("object.replace_sanctus_library_path", text="RePath sanctus")        

        # 🔥 여기서부터 수정된 SFpaint Global Control 부분 🔥
        box_paint = layout.box()
        icon = 'TRIA_DOWN' if scene.sf_show_sfpaint_global else 'TRIA_RIGHT'
        box_paint.prop(scene, "sf_show_sfpaint_global", text="SFpaint Global Control", icon=icon, emboss=False)

        if scene.sf_show_sfpaint_global:
            # 1. 수치 입력칸 4개 깔끔하게 정렬
            row = box_paint.row(align=True)
            row.label(text="Emit")
            row.prop(context.scene.my_tool, "sfpaint_emission_strength", text="")

            row = box_paint.row(align=True)
            row.label(text="Mask_Int")
            row.prop(context.scene.my_tool, "sfpaint_mask_int", text="")

            row = box_paint.row(align=True)
            row.label(text="Brusk_Int")
            row.prop(context.scene.my_tool, "sfpaint_brusk_int", text="")

            row = box_paint.row(align=True)
            row.label(text="Noise Int")
            row.prop(context.scene.my_tool, "sfpaint_noise_int", text="")

            # 2. 맨 아래에 전체 적용(Apply) 버튼을 크고 시원하게 배치!
            box_paint.separator(factor=0.5)
            row_apply = box_paint.row()
            row_apply.scale_y = 1.3
            row_apply.operator("sf.apply_sfpaint_global_control", text="Apply All SFpaint Settings", icon='CHECKMARK')

        box_sticky = layout.box()
        box_sticky.label(text="StickyGP", icon='GREASEPENCIL')
        row = box_sticky.row()
        row.scale_y = 1.3
        row.operator("sf.sticky_gp_auto_setup", text="Auto Setup")
        row = box_sticky.row(align=True)
        row.scale_y = 1.3
        row.operator("sf.sticky_gp_stick", text="Stick")
        row.operator("sf.sticky_gp_unstick", text="Unstick")


# ==============================================================================
# ▼ 메인 탭 패널 (Render Tools)
# ==============================================================================
class SF_PT_MainTabPanel(bpy.types.Panel):
    bl_label = "Render Tools"
    bl_idname = "SF_PT_main_tab_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SF_Render"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        col = layout.column(align=True)
        
        # --- 1행 (CACHE를 위로 올림) ---
        row1 = col.row(align=True)
        row1.scale_y = 1.6
        row1.prop_enum(scene, "sf_active_tab", 'BUILD')
        row1.prop_enum(scene, "sf_active_tab", 'OUTPUT')
        row1.prop_enum(scene, "sf_active_tab", 'CACHE') 
        
        # --- 2행 (MASK_PASS를 아래로 내림) ---
        row2 = col.row(align=True)
        row2.scale_y = 1.6
        row2.prop_enum(scene, "sf_active_tab", 'MASK_PASS') 
        row2.prop_enum(scene, "sf_active_tab", 'OUTLINE')
        row2.prop_enum(scene, "sf_active_tab", 'TOOLS')
        
        layout.separator(factor=0.5)
        
        # 선택된 탭 분기
        tab = scene.sf_active_tab
        if tab == 'BUILD':
            SF_UI_BuildTab.draw(layout, context)
        elif tab == 'OUTPUT':
            SF_UI_OutputTab.draw(layout, context)
        elif tab == 'MASK_PASS':
            SF_UI_MaskPassTab.draw(layout, context)
        elif tab == 'CACHE':
            SF_UI_CacheTab.draw(layout, context)
        elif tab == 'OUTLINE':
            SF_UI_OutlineTab.draw(layout, context)
        elif tab == 'TOOLS':
            SF_UI_ToolsTab.draw(layout, context)
           
# 아이템 객체 정의
class FileNameItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    is_selected: bpy.props.BoolProperty(name="Is Selected", default=True)
    exist_in_scene: bpy.props.BoolProperty(name="Exist in Scene", default=False)

# 카테고리 객체 정의
class FileCategory(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    items: bpy.props.CollectionProperty(type=FileNameItem)
    is_selected: bpy.props.BoolProperty(name="Select All", default=False)

# 카테고리 선택 시 모든 아이템을 선택/해제하는 연산자 정의
class SF_OT_ToggleCategory(bpy.types.Operator):
    bl_idname = "sf.toggle_category_operator"
    bl_label = "Toggle Category Selection"
    
    category_name: bpy.props.StringProperty()
    
    def execute(self, context):
        category = next((cat for cat in context.scene.sf_file_categories if cat.name == self.category_name), None)
        if category:
            new_state = not category.is_selected
            category.is_selected = new_state
            for item in category.items:
                item.is_selected = new_state
        return {'FINISHED'}

# 모든 항목 선택/해제 연산자 정의
class SF_OT_ToggleAllOperator(bpy.types.Operator):
    bl_idname = "sf.toggle_all_operator"
    bl_label = "Toggle All"
    
    def execute(self, context):
        all_selected = all(item.is_selected for category in context.scene.sf_file_categories for item in category.items)
        
        for category in context.scene.sf_file_categories:
            for item in category.items:
                item.is_selected = not all_selected
        return {'FINISHED'}

def auto_set_browser_fields():
    import bpy, os
    filepath = (_pending_browser_focus_filepath or bpy.data.filepath).replace("\\", "/")
    if not filepath:
        return

    if sync_browser_to_filepath(bpy.context, filepath, save_state=True):
        schedule_browser_sync(filepath, delay=0.2)
        return

    scene_number = ""
    cut_number = ""
    level_values = extract_browser_level_values_from_root_relative_path(filepath)
    if level_values:
        scene_number = level_values[0] if len(level_values) >= 1 else ""
        cut_number = level_values[1] if len(level_values) >= 2 else scene_number

    if not scene_number or not cut_number:
        scene_root_name = re.escape(get_project_scene_root_dir().strip("/\\"))
        work_dirs_pattern = "|".join(re.escape(name.strip("/\\")) for name in get_scene_work_dir_names())
        path_match = re.search(rf"/{scene_root_name}/([^/]+)/([^/]+)/({work_dirs_pattern})/", filepath)
        if path_match:
            scene_number, cut_number, _work_dir_name = path_match.groups()
        else:
            file_match = re.search(rf"_([0-9]{{4}})_([0-9]{{4}})_({work_dirs_pattern})_", os.path.basename(filepath))
            if file_match:
                scene_number, cut_number, _work_dir_name = file_match.groups()

    if not scene_number or not cut_number:
        return

    blend_file_name = os.path.basename(filepath)                 # DSC_0100_0230_ren_v002_ch.blend
    blend_file_noext = os.path.splitext(blend_file_name)[0]      # DSC_0100_0230_ren_v002_ch

    print(f"[INFO] 현재 파일 기준 자동 설정 → scene: {scene_number}, cut: {cut_number}, file: {blend_file_name}")

    scene = bpy.context.scene
    if hasattr(scene, "my_tool"):
        props = scene.my_tool
        safe_set_enum_property(props, "scene_number", get_cached_scenes(), preferred_value=scene_number, fallback_identifier="NO_SCENES")
        safe_set_enum_property(props, "cut_number", get_cached_cuts(scene_number), preferred_value=cut_number, fallback_identifier="NO_CUTS")
        for index in range(3, MAX_BROWSER_LEVELS + 1):
            level_items = get_browser_level_items(index, bpy.context)
            preferred_value = level_values[index - 1] if len(level_values) >= index else ""
            safe_set_enum_property(props, f"browser_level_{index}", level_items, preferred_value=preferred_value, fallback_identifier=f"NO_LEVEL{index}")

        # --- blend_file Enum 값 파싱 ---
        enum_value = find_blend_file_enum_value(scene_number, cut_number, bpy.data.filepath, bpy.context)

        # --- 실제 Enum 목록에 있는 경우만 대입 ---
        if enum_value:
            props.blend_file = enum_value
            print(f"[AUTOSET] blend_file set to '{enum_value}'")
        else:
            set_blend_file_to_first_available(bpy.context)
            print(f"[AUTOSET][WARN] blend file enum could not be resolved for '{blend_file_name}'")

        save_recent_browser_state(force=True)


class SF_OT_DisableOutline(bpy.types.Operator):
    bl_idname = "sf.disable_outline"
    bl_label = "Disable SF_Outline"
    bl_description = "씬 내 모든 SF_Outline 모디파이어 끄기"

    def execute(self, context):
        count = 0
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.name == "SF_Outline":
                    mod.show_viewport = False
                    mod.show_render = False
                    count += 1
        self.report({'INFO'}, f"Disabled {count} SF_Outline modifiers.")
        return {'FINISHED'}


# 🔹 SF_Outline 모디파이어 켜기
class SF_OT_EnableOutline(bpy.types.Operator):
    bl_idname = "sf.enable_outline"
    bl_label = "Enable SF_Outline"
    bl_description = "씬 내 모든 SF_Outline 모디파이어 켜기"

    def execute(self, context):
        count = 0
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.name == "SF_Outline":
                    mod.show_viewport = True
                    mod.show_render = True
                    count += 1
        self.report({'INFO'}, f"Enabled {count} SF_Outline modifiers.")
        return {'FINISHED'}


def run_sticky_gp_modifier(context, unstick=False):
    obj = context.object
    if not obj or obj.type not in {'GREASEPENCIL', 'GPENCIL'}:
        return False, "Grease Pencil object is not selected."

    source_mod = None
    for mod in obj.modifiers:
        node_group = getattr(mod, "node_group", None)
        if node_group and node_group.name.startswith(STICKY_GP_STORE_GROUP):
            source_mod = mod
            break

    if source_mod is None:
        for mod in obj.modifiers:
            node_group = getattr(mod, "node_group", None)
            if node_group and "store" in node_group.name.lower() and "Socket_3" in mod.keys():
                source_mod = mod
                break

    if source_mod is None:
        return False, "StickyGP Store UVs modifier was not found."

    override = context.copy()
    override["object"] = obj
    override["active_object"] = obj
    override["modifier"] = source_mod

    try:
        before_names = {mod.name for mod in obj.modifiers}
        with context.temp_override(**override):
            bpy.ops.object.modifier_copy(modifier=source_mod.name)

        copied_mod = None
        for mod in reversed(obj.modifiers):
            if mod.name not in before_names:
                copied_mod = mod
                break
        copied_mod = copied_mod or obj.modifiers[-1]

        if "Socket_3" not in copied_mod.keys():
            return False, "StickyGP modifier does not have Socket_3."

        copied_mod["Socket_3"] = bool(unstick)
        copied_mod.show_viewport = True
        if getattr(copied_mod, "node_group", None):
            copied_mod.node_group.interface_update(context)

        with context.temp_override(object=obj, active_object=obj):
            bpy.ops.object.modifier_apply(modifier=copied_mod.name)
    except Exception as e:
        return False, f"StickyGP failed: {e}"

    return True, "StickyGP Unstick complete." if unstick else "StickyGP Stick complete."


STICKY_GP_STORE_GROUP = "GN-stickyGP-store_uvs"
STICKY_GP_DEFORM_GROUP = "GN-stickyGP-deform"
STICKY_GP_TEMPLATE_PATHS = [
    r"C:\_json\stickyGP.blend",
    r"C:\_json\StickyGP.blend",
    r"C:\_json\rrRender_stickyGP.blend",
]


def find_sticky_gp_node_group(group_name):
    group = bpy.data.node_groups.get(group_name)
    if group:
        return group

    group_name_lower = group_name.lower()
    for node_group in bpy.data.node_groups:
        if group_name_lower in node_group.name.lower():
            return node_group

    return None


def append_sticky_gp_node_group_from_template(group_name):
    for template_path in STICKY_GP_TEMPLATE_PATHS:
        if not os.path.exists(template_path):
            continue

        try:
            with bpy.data.libraries.load(template_path, link=False) as (data_from, data_to):
                if group_name in data_from.node_groups:
                    data_to.node_groups = [group_name]
                else:
                    matches = [name for name in data_from.node_groups if group_name.lower() in name.lower()]
                    if not matches:
                        continue
                    data_to.node_groups = [matches[0]]

            group = find_sticky_gp_node_group(group_name)
            if group:
                print(f"[StickyGP] Appended node group '{group.name}' from {template_path}")
                return group
        except Exception as e:
            print(f"[StickyGP][WARN] Failed to append '{group_name}' from {template_path}: {e}")

    return None


def ensure_sticky_gp_node_group(group_name):
    return find_sticky_gp_node_group(group_name) or append_sticky_gp_node_group_from_template(group_name)


def set_nodes_modifier_input(modifier, input_name, value):
    node_group = getattr(modifier, "node_group", None)
    if not node_group:
        return False

    input_name_lower = input_name.lower()
    interface_items = getattr(getattr(node_group, "interface", None), "items_tree", [])
    for item in interface_items:
        if getattr(item, "item_type", None) != 'SOCKET':
            continue
        if getattr(item, "in_out", None) != 'INPUT':
            continue
        if getattr(item, "name", "").lower() != input_name_lower:
            continue

        identifier = getattr(item, "identifier", "")
        if not identifier:
            continue
        try:
            modifier[identifier] = value
            return True
        except Exception:
            continue

    return False


def ensure_sticky_gp_target_collection(mesh_objects):
    base_name = mesh_objects[0].name if mesh_objects else "Target"
    collection_name = f"StickyGP_Target_{base_name}"
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    for obj in mesh_objects:
        if obj.name not in collection.objects:
            collection.objects.link(obj)

    return collection


def get_or_create_sticky_gp_object(context, target_name):
    gp_types = {'GREASEPENCIL', 'GPENCIL'}
    if context.object and context.object.type in gp_types:
        return context.object

    for obj in context.selected_objects:
        if obj.type in gp_types:
            return obj

    gp_name = f"StickyGP_{target_name}"
    existing = bpy.data.objects.get(gp_name)
    if existing and existing.type in gp_types:
        return existing

    try:
        bpy.ops.object.grease_pencil_add(type='EMPTY', align='WORLD', location=(0, 0, 0))
    except Exception:
        bpy.ops.object.gpencil_add(type='EMPTY', align='WORLD', location=(0, 0, 0))

    gp_obj = bpy.context.object
    gp_obj.name = gp_name
    return gp_obj


def ensure_sticky_gp_modifier(gp_obj, node_group, modifier_name, target_collection):
    modifier = None
    for mod in gp_obj.modifiers:
        if getattr(mod, "node_group", None) == node_group:
            modifier = mod
            break

    if modifier is None:
        modifier = gp_obj.modifiers.new(name=modifier_name, type='NODES')
        modifier.node_group = node_group

    if not set_nodes_modifier_input(modifier, "Collection", target_collection):
        print(f"[StickyGP][WARN] Could not set Collection input on {modifier.name}")
    modifier.show_viewport = True
    return modifier


class SF_OT_StickyGPAutoSetup(bpy.types.Operator):
    bl_idname = "sf.sticky_gp_auto_setup"
    bl_label = "StickyGP - Auto Setup"
    bl_description = "Create StickyGP target collection and add StickyGP modifiers automatically"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not mesh_objects:
            self.report({'ERROR'}, "Select at least one mesh target.")
            return {'CANCELLED'}

        store_group = ensure_sticky_gp_node_group(STICKY_GP_STORE_GROUP)
        deform_group = ensure_sticky_gp_node_group(STICKY_GP_DEFORM_GROUP)
        if not store_group or not deform_group:
            self.report({'ERROR'}, "StickyGP node groups were not found. Put stickyGP.blend in C:\\_json or create the node groups in this scene.")
            return {'CANCELLED'}

        target_collection = ensure_sticky_gp_target_collection(mesh_objects)
        gp_obj = get_or_create_sticky_gp_object(context, mesh_objects[0].name)

        store_mod = ensure_sticky_gp_modifier(gp_obj, store_group, "StickyGP Store UVs", target_collection)
        deform_mod = ensure_sticky_gp_modifier(gp_obj, deform_group, "StickyGP Deform", target_collection)

        try:
            gp_obj.modifiers.move(gp_obj.modifiers.find(store_mod.name), 0)
            gp_obj.modifiers.move(gp_obj.modifiers.find(deform_mod.name), len(gp_obj.modifiers) - 1)
        except Exception as e:
            print(f"[StickyGP][WARN] Could not reorder modifiers: {e}")

        bpy.ops.object.select_all(action='DESELECT')
        gp_obj.select_set(True)
        context.view_layer.objects.active = gp_obj

        self.report({'INFO'}, f"StickyGP ready: {gp_obj.name} -> {target_collection.name}")
        return {'FINISHED'}


class SF_OT_StickyGPStick(bpy.types.Operator):
    bl_idname = "sf.sticky_gp_stick"
    bl_label = "StickyGP - Stick"
    bl_description = "Stick selected Grease Pencil strokes with the StickyGP modifier"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type in {'GREASEPENCIL', 'GPENCIL'}

    def execute(self, context):
        ok, message = run_sticky_gp_modifier(context, unstick=False)
        self.report({'INFO'} if ok else {'ERROR'}, message)
        return {'FINISHED'} if ok else {'CANCELLED'}


class SF_OT_StickyGPUnstick(bpy.types.Operator):
    bl_idname = "sf.sticky_gp_unstick"
    bl_label = "StickyGP - Unstick"
    bl_description = "Unstick selected Grease Pencil strokes with the StickyGP modifier"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type in {'GREASEPENCIL', 'GPENCIL'}

    def execute(self, context):
        ok, message = run_sticky_gp_modifier(context, unstick=True)
        self.report({'INFO'} if ok else {'ERROR'}, message)
        return {'FINISHED'} if ok else {'CANCELLED'}


################################################################
######################### Register #############################
################################################################
bpy.types.Scene.input_15 = bpy.props.FloatProperty(name="Input 15", default=0.001)
bpy.types.Scene.input_16 = bpy.props.FloatProperty(name="Input 16", default=0.08)


# ✅ 등록할 클래스 리스트
# ✅ 등록할 클래스 리스트 정리
classes = [
    OBJECT_OT_make_2com,
    OBJECT_OT_del_2com,
    SF_OT_GenerateOperator,
    SF_OT_LinkSelectedOperator,
    SF_OT_LinkAllOperator,
    SF_OT_ImportSelectedOperator,
    SF_OT_ToggleAllOperator,
    SF_OT_BuildSceneOperator,
    FileNameItem,
    FileCategory,
    SF_OT_ImportSceneCameraOperator,
    SF_CleanupOrphansCombined,
    SF_SaveRenderScene,
    SF_OT_UpdateMaterialsOperator,
    LinkClass,
    SubdivideClass,
    SF_OT_VersionOperator,
    IncrementalSaveOperator,
    LineArtGenerator,
    SF_OT_ApplyLineArt,
    MyProperties,
    SF_ProjectPathSettings,
    SF_OT_ProjectPathSettingsPopup,
    SF_OT_PickProjectPath,
    SF_OT_NewProjectPopup,
    SF_OT_ValidateProject,
    OpenSceneFolderOperator,
    OpenCutFolderOperator,
    OpenFileOperator,
    AppendSceneOperator,
    WM_OT_ReinstallAddon1,
    SF_OT_ApplyPreset,
    SF_OT_RenderSetting,
    SF_PT_SceneBrowser,
    SF_PT_MainTabPanel, # 👈 3개 대신 이거 하나만 등록! (Main Tools -> Render Tools)
    SF_OT_SaveProjectPathSettings,
    SF_OT_ReloadProjectPathSettings,
    SF_OT_ResetProjectPathSettings,
    SF_OT_RefreshDriverDependencies,
    SF_OT_GetSelectedAssetsOperator,
    MyProjectSettings1,
    SF_OT_UpdateSelectedOperator,
    SF_OT_UpdateSelectedLightOperator,
    SF_OT_ClearCustomNormalOperator,
    UpdateLightPosition,
    SF_OT_SetStaticBG,
    SF_OT_SetMovingBG,
    SF_OT_AddPropertiesAndLink1,
    SF_OT_LinkCharacterLights1,
    SF_OT_LinkRimToNode1,
    SF_OT_SetViewLayerMode,
    SubmitBlenderToDeadline,
    FrameRangeOperator,
    CameraMovementFrameRangeOperator,
    SimpleSceneProps,
    OBJECT_OT_apply_shadow_catcher,
    OBJECT_OT_remove_shadow_catcher,
    SF_OT_ResetMaterialOperator,
    SF_OT_updateMaterialOperator,
    OBJECT_OT_apply_blocker,
    OBJECT_OT_remove_blocker,
    OBJECT_OT_remove_light_mask,
    OBJECT_OT_apply_light_mask,
    SF_OT_ApplyRenderPresets,
    BakeShapeKeysOperator,
    OBJECT_OT_apply_caustics_mask,
    OBJECT_OT_remove_caustics_mask,
    SF_OT_ToggleCategory,
    DeleteNonVisibleMeshesOperator,
    ReplaceBotaniqLibraryPathOperator,
    ReplacesanctusLibraryPathOperator,
    SetCyclesRenderSettings,
    unSubdivideClass,
    DeleteAllFakeUsersOperator,
    NodeGroupLinkerOperator,
    OBJECT_OT_make_shared_unique_material,
    OBJECT_OT_update_light_mask,
    OBJECT_OT_update_shadow_material,
    SF_OT_CopyDropletGeneratorOperator,
    SF_OT_RemoveDropletGeneratorOperator,
    OBJECT_OT_instance_solidify,
    SF_OT_UpdateSelectedOperatorDSC,
    SF_OT_ImportSelectedOperatorDSC,
    SF_OT_RefreshSceneAndCutCache,
    SF_MaterialSwitcherProperties, 
    SF_OT_ImportAndUpdateOperatorDSC,
    SF_OT_SetSceneFromFile,
    SF_OT_DisableOutline,
    SF_OT_EnableOutline,
    SF_OT_UpdateToCyclesIndependent,
    SF_OT_BakeOutline,
    SF_OT_UpdateFromPublish,
    SF_OT_SetOutputPath,
    SF_OT_SaveIncrementalSuffix,
    DEV_OT_reload_rrrender,
    DEV_OT_deploy_rrrender,
    SF_OT_ImportModePopup,
    SF_OT_LinkLightProperties,
    SF_OT_AllInOne,
    SF_OT_ClearBakeOutline,
    SF_OT_ViewLayerSetupOperator,
    SF_OT_SetLightBounces,
    SF_OT_MakeColorPass,
    SF_OT_ClearSelectedMaterials,
    SF_OT_ClearSelectedMaterialsPopup,
    SF_OT_ApplySFpaintGlobalControl,
    SF_OT_StickyGPAutoSetup,
    SF_OT_StickyGPStick,
    SF_OT_StickyGPUnstick,
    SF_OT_SetOutputFormat,
    SF_OT_DeleteSolidifyLine,
    OBJECT_OT_remove_shell
]

_auto_browser_timer = None
_recent_browser_state_timer = None  # 전역 변수로 선언

def register():
    ensure_project_config_loaded()
    # ✅ 1. 6개 탭 아이콘 및 순서 재배치 (CACHE ↔ MASK_PASS)
    bpy.types.Scene.sf_active_tab = bpy.props.EnumProperty(
        items=[
            ('BUILD', "Build", "Scene Build & Assets", 'MOD_BUILD', 0),
            ('OUTPUT', "Output", "Output & Render Settings", 'FILE_FOLDER', 1),
            ('CACHE', "Ani/Bake", "Cache & Animation Tools", 'PHYSICS', 2), # 👈 순서 변경됨
            ('MASK_PASS', "Mask/Pass", "Masks & Passes", 'RENDERLAYERS', 3), # 👈 순서 변경됨
            ('OUTLINE', "Outline", "Outline Settings", 'GREASEPENCIL', 4),
            ('TOOLS', "Tools", "Extra Tools", 'SETTINGS', 5)
        ],
        default='BUILD'
    )
        
    global _auto_browser_timer, _recent_browser_state_timer

    # ✅ 2. 모든 클래스 일괄 등록
    for cls in classes:
        bpy.utils.register_class(cls)

    # ✅ 3. Scene 프로퍼티 및 포인터 연결
    bpy.types.Scene.my_tool = bpy.props.PointerProperty(type=MyProperties)
    bpy.types.Scene.my_project_settings = bpy.props.PointerProperty(type=MyProjectSettings1)
    bpy.types.Scene.sf_project_paths = bpy.props.PointerProperty(type=SF_ProjectPathSettings)
    bpy.types.Scene.simple_scene_props = bpy.props.PointerProperty(type=SimpleSceneProps)
    bpy.types.Scene.sf_scene_number = bpy.props.StringProperty(name="Scene Number", default="0010")
    bpy.types.Scene.sf_cut_number = bpy.props.StringProperty(name="Cut Number", default="0010")
    bpy.types.Scene.sf_message = bpy.props.StringProperty(default="")
    bpy.types.Scene.sf_file_categories = bpy.props.CollectionProperty(type=FileCategory)
    bpy.types.Scene.sf_mat_switcher = bpy.props.PointerProperty(type=SF_MaterialSwitcherProperties)
    bpy.types.Scene.sf_show_advanced = bpy.props.BoolProperty(name="Show Tools", default=False)
    bpy.types.Scene.sf_show_sfpaint_global = bpy.props.BoolProperty(name="Show SFpaint Global Control", default=False)
    
    bpy.types.Scene.render_preset_enum = bpy.props.EnumProperty(
        name="Render Preset",
        description="Choose a render preset",
        items=get_preset_items
    )    

    # ✅ 4. 메뉴 및 핸들러 등록
    bpy.types.TOPBAR_MT_render.append(menu_func)

    try:
        load_project_path_settings_to_ui(bpy.context)
    except Exception as e:
        print(f"[ProjectConfig][WARN] UI init failed: {e}")

    _auto_browser_timer = bpy.app.timers.register(auto_set_browser_fields, first_interval=0.5)
    _recent_browser_state_timer = bpy.app.timers.register(restore_recent_browser_state, first_interval=0.8)
    register_scene_loader_handler()


def unregister():
    global _auto_browser_timer, _recent_browser_state_timer

    # ✅ 1. 타이머 완전 해제
    if _auto_browser_timer:
        try:
            bpy.app.timers.unregister(auto_set_browser_fields)
        except Exception:
            pass
        _auto_browser_timer = None

    if _recent_browser_state_timer:
        try:
            bpy.app.timers.unregister(restore_recent_browser_state)
        except Exception:
            pass
        _recent_browser_state_timer = None

    # ✅ 2. 메뉴 해제
    try:
        bpy.types.TOPBAR_MT_render.remove(menu_func)
    except Exception:
        pass

    # ✅ 3. 클래스 해제 (반드시 역순으로)
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    # ✅ 4. Scene 프로퍼티 찌꺼기 완벽 제거 (새로 만든 탭 변수 포함!)
    scene_props = [
        "sf_active_tab",      # <--- 새로 생긴 6개 탭 변수 삭제 추가!
        "my_tool",
        "my_project_settings",
        "sf_project_paths",
        "simple_scene_props",
        "sf_scene_number",
        "sf_cut_number",
        "sf_message",
        "sf_file_categories",
        "sf_mat_switcher",
        "sf_show_advanced",   # <--- 이것도 확실히 지워줍니다.
        "sf_show_sfpaint_global",
        "render_preset_enum",
    ]
    for prop_name in scene_props:
        if hasattr(bpy.types.Scene, prop_name):
            try:
                delattr(bpy.types.Scene, prop_name)
            except Exception:
                pass

    # ✅ 5. 핸들러 해제
    if run_set_scene_from_file in bpy.app.handlers.load_post:
        try:
            bpy.app.handlers.load_post.remove(run_set_scene_from_file)
        except Exception:
            pass


def load_post_handler(dummy):
    import bpy
    filepath = _pending_browser_focus_filepath or bpy.data.filepath
    if sync_browser_to_filepath(bpy.context, filepath, save_state=True):
        print(f"[LOAD] 브라우저 동기화 완료: {os.path.basename(filepath)}")
        schedule_browser_sync(filepath, delay=0.2)

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'PROPERTIES', 'VIEW_3D'}:
                    area.tag_redraw()
    else:
        print("[LOAD] 현재 파일 기준 브라우저 동기화 생략됨.")
# 핸들러 중복 방지 후 append
for h in bpy.app.handlers.load_post:
    if h.__name__ == 'load_post_handler':
        break
else:
    bpy.app.handlers.load_post.append(load_post_handler)


if __name__ == "__main__":

    register()
    unregister()
