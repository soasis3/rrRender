import maya.mel
def open_shared_project_setup_for_lookdev(*args):
    selected_project = ""
    try:
        if 'projectMenuName' in globals() and cmds.optionMenu(projectMenuName, exists=True):
            selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    except Exception:
        selected_project = ""

    if not PIPELINE_SHARED_AVAILABLE:
        cmds.warning("[rrLookdev Setup] Shared project setup app is unavailable.")
        return

    try:
        launch_project_setup_app("rrLookdev", selected_project, wait=True)
        refresh_projects_from_pipeline()
        if 'projectMenuName' in globals() and cmds.optionMenu(projectMenuName, exists=True):
            previous_project = normalize_project_selection(selected_project)
            clear_option_menu(projectMenuName)
            for project_name in projects.keys():
                cmds.menuItem(label=project_name)
            target_project = previous_project if previous_project in projects else next(iter(projects), "")
            if target_project:
                cmds.optionMenu(projectMenuName, e=True, value=target_project)
            update_category_menu()
            on_maya_dropdown_change()
    except Exception as exc:
        cmds.warning(f"[rrLookdev Setup] Failed to open shared setup app: {exc}")


import maya.cmds as cmds
import maya.mel as mel
import maya.cmds as mc
import json
import re
import os
import shutil
import sys
import imp
from functools import partial
# import blendRename
# import importlib
# importlib.reload(blendRename)
try:
    import blendRename
except ImportError:
    print("⚠️ blendRename 모듈을 찾을 수 없습니다. 일부 기능이 비활성화됩니다.")
    blendRename = None

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_MODULE_SEARCH_PATHS = [
    THIS_DIR,
    r"C:\Users\hwang\Desktop\codex\rrRender",
]
for search_path in SHARED_MODULE_SEARCH_PATHS:
    if search_path and os.path.isdir(search_path) and search_path not in sys.path:
        sys.path.append(search_path)

try:
    from pipeline_shared import get_project_root_map, launch_project_setup_app, normalize_project_name
    PIPELINE_SHARED_AVAILABLE = True
except Exception:
    get_project_root_map = None
    launch_project_setup_app = None
    normalize_project_name = None
    PIPELINE_SHARED_AVAILABLE = False


# 프로젝트 경로 설정
DEFAULT_PROJECTS = {
    "BTS": "B:/",
    "THE_TRAP": "T:/",
    "ARBO_BION": "A:/",
    "CKR": "K:/",
    "DSC": "S:/",
    "FUZZ": "Z:/",
    "COC": "S:/PROJECT/COC/02_Production/CHSetup/controller"
}
projects = dict(DEFAULT_PROJECTS)

COC_PROJECT = "COC"
COC_CATEGORY = "ch"
RR_LOOKDEV_LOCAL_PATH = r"C:\Users\hwang\Desktop\codex\rrRender\rrLookdev.py"
RR_LOOKDEV_DEPLOY_PATH = r"M:\RND\SFtools\2023\lookDev\rrLookdev.py"

# 정의된 카테고리
asset_cache = {
    "categories": ['ch', 'bg', 'prop'],
    "assets": {}
}

# ====== [ JSON 경로 ] ======
MAYA_STATE_PATH = os.path.join(os.path.expanduser("~"), "_json", "ldv_browser_state_maya.json")

def refresh_projects_from_pipeline():
    global projects
    if not PIPELINE_SHARED_AVAILABLE:
        projects = dict(DEFAULT_PROJECTS)
        return projects

    try:
        loaded = get_project_root_map("asset_root") or {}
        projects = loaded or dict(DEFAULT_PROJECTS)
    except Exception as exc:
        cmds.warning(f"[rrLookdev Setup] Failed to load pipeline config: {exc}")
        projects = dict(DEFAULT_PROJECTS)
    return projects


def normalize_project_selection(project_name):
    refresh_projects_from_pipeline()
    if PIPELINE_SHARED_AVAILABLE and normalize_project_name:
        normalized = normalize_project_name(project_name)
        if normalized in projects:
            return normalized
    if project_name in projects:
        return project_name
    upper_name = str(project_name or "").upper()
    for existing_name in projects.keys():
        if existing_name.upper() == upper_name:
            return existing_name
    return next(iter(projects), "")


refresh_projects_from_pipeline()

def is_coc_project(project):
    return project == COC_PROJECT

def get_category_list(project):
    if is_coc_project(project):
        return [COC_CATEGORY]
    return sorted(asset_cache["categories"])

def get_assets_root(project, category):
    base_path = get_project_path(project)
    if is_coc_project(project):
        return base_path
    return os.path.join(base_path, category)

def get_asset_folder_path(project, category, asset, process=None):
    base_path = get_project_path(project)
    if is_coc_project(project):
        return os.path.join(base_path, asset)
    if process == "Fin" or not process:
        return os.path.join(base_path, category, asset)
    return os.path.join(base_path, category, asset, process)

def get_asset_file_path(project, category, asset, process, selected_file=None):
    if is_coc_project(project):
        asset_folder = get_asset_folder_path(project, category, asset)
        if selected_file:
            return os.path.join(asset_folder, selected_file)
        return os.path.join(asset_folder, f"{asset}_rig_fin.mb")

    base_path = get_project_path(project)
    if process == "Fin":
        return os.path.join(base_path, category, asset, f"{asset}.mb")
    if selected_file:
        return os.path.join(base_path, category, asset, process, selected_file)
    return None

def get_scene_export_info(current_file_path):
    normalized_path = current_file_path.replace("\\", "/")
    path_parts = normalized_path.split("/")
    coc_root = get_project_path(COC_PROJECT).replace("\\", "/").rstrip("/")

    if normalized_path.lower().startswith(coc_root.lower() + "/"):
        rel_parts = normalized_path[len(coc_root):].strip("/").split("/")
        if len(rel_parts) >= 2:
            asset_name = rel_parts[0]
            final_dir = os.path.normpath(os.path.join(get_project_path(COC_PROJECT), asset_name, "mod", "usd"))
            return COC_PROJECT, COC_CATEGORY, asset_name, final_dir

    if len(path_parts) < 4:
        return None, None, None, None

    project_drive = path_parts[0]
    category = path_parts[2]
    asset_name = path_parts[3]
    final_dir = os.path.normpath(os.path.join(project_drive + "/", "assets", category, asset_name, "mod", "usd"))
    return project_drive, category, asset_name, final_dir

def find_coc_export_geo_node(asset_name):
    geometry_group = f"{asset_name}|Geometry"
    if not cmds.objExists(geometry_group):
        return None

    preferred_names = [
        f"{asset_name}_geo",
        f"{asset_name}_highM",
        f"{asset_name}_high",
        f"{asset_name}_model",
    ]
    for name in preferred_names:
        node = f"{geometry_group}|{name}"
        if cmds.objExists(node):
            return node

    children = cmds.listRelatives(geometry_group, children=True, type="transform", fullPath=True) or []
    scored = []
    for child in children:
        short_name = child.split("|")[-1]
        lowered = short_name.lower()
        if "old" in lowered or "backup" in lowered or "deform" in lowered:
            continue

        meshes = cmds.listRelatives(child, allDescendents=True, type="mesh", fullPath=True) or []
        if not meshes:
            continue

        score = 0
        if lowered.startswith(asset_name.lower()):
            score += 10
        if lowered.endswith("_geo"):
            score += 8
        if lowered.endswith("_highm") or lowered.endswith("_high"):
            score += 8
        scored.append((score, child))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    return children[0] if children else None


# ====== [ JSON 로드 & 저장 ] ======
def save_maya_ldv_state(project):
    os.makedirs(os.path.dirname(MAYA_STATE_PATH), exist_ok=True)
    state = {
        "project": project,
        "category": cmds.optionMenu(categoryMenuName, q=True, v=True),
        "asset": cmds.optionMenu(assetMenuName, q=True, v=True),
        "process": cmds.optionMenu(processMenuName, q=True, v=True),
        "file": cmds.optionMenu(fileMenuName, q=True, v=True)
    }
    with open(MAYA_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)



def load_maya_ldv_state():
    if os.path.exists(MAYA_STATE_PATH):
        with open(MAYA_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ====== [ 드롭다운 변경시 JSON 자동 저장 ] ======
def on_maya_dropdown_change(*args):
    project = cmds.optionMenu(projectMenuName, q=True, v=True)
    save_maya_ldv_state(project)


def pubAsset():
    ppPath = 'M:/RND/SFtools/2023/pipeline/'
    if os.path.exists(ppPath):
        sys.path.append(ppPath)
        try:
            import sfPublishAssets
            imp.reload(sfPublishAssets)
            sfPublishAssets.pubAsset()
            sfPublishAssets.backupAsset()
        except Exception as e:
            cmds.warning(f"[⚠️] pubAsset 실행 실패: {e}")
    else:
        cmds.warning("[⚠️] M드라이브가 없어서 pubAsset을 실행할 수 없습니다.")



# 파일 경로로부터 프로젝트, 카테고리, 어셋, 프로세스, 파일 이름을 파싱하는 함수
def get_project_path(project):
    """선택된 프로젝트의 경로를 반환합니다."""
    return projects.get(normalize_project_selection(project), "")

import maya.cmds as cmds
import os
import shutil
import json
import re


def find_all_file_textures(node_attr, depth=0):
    indent = "  " * depth
    textures = []
    connections = cmds.listConnections(node_attr, source=True, destination=False) or []
    # print(f"{indent}[TRACE] {node_attr} connections: {connections}")
    for n in connections:
        node_type = cmds.nodeType(n)
        print(f"{indent}  ↳ Connected node: {n} (type: {node_type})")
        if node_type == "file":
            textures.append(n)
        elif node_type in ["layeredTexture", "aiComposite"]:
            num_inputs = cmds.getAttr(f"{n}.inputs", size=True)
            print(f"{indent}    ↪ {node_type} {n} has {num_inputs} inputs")
            for i in range(num_inputs):
                textures.extend(find_all_file_textures(f"{n}.inputs[{i}].color", depth + 1))
        else:
            print(f"{indent}    ↪ Ignoring node type: {node_type}")
    return textures

def find_lowest_udim_texture(file_nodes):
    min_udim = float('inf')
    selected_tex = None
    for file_node in file_nodes:
        tex_path = cmds.getAttr(f"{file_node}.fileTextureName")
        print(f"    🔍 Found texture: {tex_path}")
        match = re.search(r'\.(\d{4})\.', tex_path)
        if match:
            udim = int(match.group(1))
            print(f"      ↳ UDIM detected: {udim}")
            if udim < min_udim:
                min_udim = udim
                selected_tex = tex_path
        else:
            print(f"      ↳ No UDIM pattern found.")
            if min_udim == float('inf'):
                selected_tex = tex_path
    print(f"    ✅ Lowest UDIM texture selected: {selected_tex}")
    return selected_tex

def make_udim_pattern_path(texture_path):
    return re.sub(r'\.(\d{4})\.', r'.<UDIM>.', texture_path)

def get_uv_data_from_file_node(file_node):
    uv_data = {}
    place2d_nodes = cmds.listConnections(f"{file_node}.coverage", source=True, destination=False, type="place2dTexture")
    if place2d_nodes:
        place2d = place2d_nodes[0]
        attrs = ["repeatU", "repeatV", "offsetU", "offsetV", "translateFrameU", "translateFrameV"]
        for attr in attrs:
            if cmds.attributeQuery(attr, node=place2d, exists=True):
                uv_data[attr] = cmds.getAttr(f"{place2d}.{attr}")
    return uv_data

def export_usd():
    import json
    import os
    import shutil
    import re
    import maya.cmds as cmds

    START_FRAME = 1
    END_FRAME = 5
    BEND_AMOUNT = 0.001   # 필요하면 0.01로 올려 테스트
    APPLY_BEND_FOR = ['ch', 'prop', 'bg']

    def _export_static_snapshot_usd(target_geo, usd_path, asset_name):
        usd_options = (
            f'exportUVs=1;'
            f'exportSkels=none;'
            f'exportSkin=none;'
            f'exportBlendShapes=0;'
            f'exportDisplayColor=0;'
            f'filterTypes=nurbsCurve;'
            f'exportColorSets=0;'
            f'defaultMeshScheme=none;'
            f'animation=0;'
            f'defaultUSDFormat=usdc;'
            f'exportInstances=1;'
            f'exportVisibility=1;'
            f'mergeTransformAndShape=1;'
            f'stripNamespaces=0;'
            f'parentScope=/{asset_name};'
        )
        cmds.select(target_geo, r=True)
        cmds.file(usd_path, force=True, options=usd_options, typ="USD Export", pr=True, es=True)

    def _combine_two_static_usd_to_animated(usd_f1, usd_f5, usd_out):
        from pxr import Usd, UsdGeom

        shutil.copy(usd_f1, usd_out)

        stage_out = Usd.Stage.Open(usd_out)
        stage_f1 = Usd.Stage.Open(usd_f1)
        stage_f5 = Usd.Stage.Open(usd_f5)

        if not stage_out or not stage_f1 or not stage_f5:
            raise RuntimeError("USD stage open failed")

        stage_out.SetStartTimeCode(START_FRAME)
        stage_out.SetEndTimeCode(END_FRAME)

        mesh_count = 0

        for prim in stage_out.Traverse():
            if prim.GetTypeName() != "Mesh":
                continue

            path = prim.GetPath()
            prim_f1 = stage_f1.GetPrimAtPath(path)
            prim_f5 = stage_f5.GetPrimAtPath(path)

            if not prim_f1 or not prim_f5:
                print(f"[WARN] mesh path missing in snapshot stages: {path}")
                continue

            mesh_out = UsdGeom.Mesh(prim)
            mesh_f1 = UsdGeom.Mesh(prim_f1)
            mesh_f5 = UsdGeom.Mesh(prim_f5)

            pts1 = mesh_f1.GetPointsAttr().Get()
            pts5 = mesh_f5.GetPointsAttr().Get()

            if pts1 is None or pts5 is None:
                print(f"[WARN] points missing on mesh: {path}")
                continue

            points_attr = mesh_out.GetPointsAttr()
            points_attr.Set(pts1, START_FRAME)
            points_attr.Set(pts5, END_FRAME)

            # normals도 있으면 같이 time sample
            normals1 = mesh_f1.GetNormalsAttr().Get()
            normals5 = mesh_f5.GetNormalsAttr().Get()
            if normals1 is not None and normals5 is not None:
                normals_attr = mesh_out.GetNormalsAttr()
                normals_attr.Set(normals1, START_FRAME)
                normals_attr.Set(normals5, END_FRAME)

            mesh_count += 1

        stage_out.GetRootLayer().Save()
        print(f"[DEBUG] animated USD mesh samples written: {mesh_count}")

    # ------------------------------------------------------------
    # 현재 파일 / 경로 파싱
    # ------------------------------------------------------------
    current_file_path = cmds.file(q=True, sn=True)
    if not current_file_path:
        cmds.warning("[❌] 현재 열린 Maya 파일이 없습니다.")
        return False
    project_drive, category, asset_name, final_dir = get_scene_export_info(current_file_path)
    path_parts = [project_drive]
    if not all([project_drive, category, asset_name, final_dir]):
        cmds.warning("[❌] 파일 경로가 올바르지 않습니다. (Project/assets/category/assetName 형식 필요)")
        return False

    project_drive = path_parts[0]   # 예: T:
    path_parts = [project_drive]
    print("\n" + "=" * 80)
    print("[USD EXPORT] START")
    print(f"[INFO] current file : {current_file_path}")
    print(f"[INFO] project drive: {project_drive}")
    print(f"[INFO] category     : {category}")
    print(f"[INFO] asset name   : {asset_name}")
    print("=" * 80)

    # mayaUsdPlugin 체크
    try:
        if cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
            print("[DEBUG] mayaUsdPlugin already loaded")
        else:
            cmds.loadPlugin("mayaUsdPlugin")
            print("[DEBUG] mayaUsdPlugin loaded")
    except Exception as e:
        cmds.warning(f"[❌] mayaUsdPlugin 로드 실패: {e}")
        return False

    if project_drive == COC_PROJECT:
        geo_node = find_coc_export_geo_node(asset_name)
        if not geo_node:
            cmds.warning(f"[?? '{asset_name}|Geometry' under export mesh group does not exist in the scene.")
            return False
    else:
        geo_node = asset_name + "|geo"
    if not cmds.objExists(geo_node):
        cmds.warning(f"[❌] '{geo_node}' does not exist in the scene.")
        return False

    print(f"[INFO] export geo node: {geo_node}")
    base_geo_name = geo_node.split("|")[-1]
    temp_original_name = base_geo_name + "_ORIGINAL_TEMP"

    # 혹시 남아있는 temp 제거
    if cmds.objExists(temp_original_name):
        try:
            cmds.delete(temp_original_name)
            print(f"[DEBUG] deleted leftover temp node: {temp_original_name}")
        except Exception as e:
            cmds.warning(f"[❌] leftover temp node 삭제 실패: {e}")
            return False

    # 원본 geo rename
    try:
        original_geo_renamed = cmds.rename(geo_node, temp_original_name)
        print(f"[DEBUG] original geo renamed: {geo_node} -> {original_geo_renamed}")
    except Exception as e:
        cmds.warning(f"[❌] geo rename 실패: {e}")
        return False

    # duplicate 생성
    try:
        duplicated_geo = cmds.duplicate(original_geo_renamed, rr=True, ic=True, name=base_geo_name)[0]
        print(f"[DEBUG] duplicated geo created: {duplicated_geo}")
    except Exception as e:
        cmds.warning(f"[❌] geo duplicate 실패: {e}")
        try:
            cmds.rename(temp_original_name, base_geo_name)
        except:
            pass
        return False

    try:
        cmds.parent(duplicated_geo, world=True)
        print("[DEBUG] duplicated geo parented to world")
    except:
        print("[DEBUG] duplicated geo already in world")

    if duplicated_geo != base_geo_name:
        if cmds.objExists(base_geo_name):
            try:
                cmds.delete(base_geo_name)
            except:
                pass
        duplicated_geo = cmds.rename(duplicated_geo, base_geo_name)
        print(f"[DEBUG] duplicated geo renamed to: {duplicated_geo}")

    # temp / final 경로
    temp_dir = os.path.expanduser("~/Documents/maya")
    os.makedirs(temp_dir, exist_ok=True)

    usd_name = f"{asset_name}.usd"
    temp_usd_f1 = os.path.normpath(os.path.join(temp_dir, f"{asset_name}__f1.usd"))
    temp_usd_f5 = os.path.normpath(os.path.join(temp_dir, f"{asset_name}__f5.usd"))
    temp_usd_anim = os.path.normpath(os.path.join(temp_dir, usd_name))

    if project_drive == COC_PROJECT:
        final_dir = os.path.normpath(os.path.join(get_project_path(COC_PROJECT), asset_name, "mod", "usd"))
    else:
        final_dir = os.path.normpath(os.path.join(project_drive + "/", "assets", category, asset_name, "mod", "usd"))
    os.makedirs(final_dir, exist_ok=True)

    final_usd = os.path.normpath(os.path.join(final_dir, usd_name))
    final_json = os.path.normpath(os.path.splitext(final_usd)[0] + ".json")

    print(f"[INFO] temp usd f1 : {temp_usd_f1}")
    print(f"[INFO] temp usd f5 : {temp_usd_f5}")
    print(f"[INFO] temp usd out: {temp_usd_anim}")
    print(f"[INFO] final usd   : {final_usd}")
    print(f"[INFO] final json  : {final_json}")

    bend = None
    handle = None

    # ------------------------------------------------------------
    # bend를 "애니메이션"으로 쓰지 않고, snapshot 2장만 뽑는다
    # ------------------------------------------------------------
    try:
        if category in APPLY_BEND_FOR:
            bend, handle = cmds.nonLinear(duplicated_geo, type="bend", name="Bend_Deform_TMP#")
            bend_attr = bend + ".curvature"
            print(f"[DEBUG] bend node   : {bend}")
            print(f"[DEBUG] bend handle : {handle}")

            # frame1 snapshot
            cmds.setAttr(bend_attr, 0.0)
            try:
                cmds.dgdirty(allPlugs=True)
            except:
                pass
            cmds.refresh(force=True)
            bbox_f1 = cmds.exactWorldBoundingBox(duplicated_geo)
            print(f"[DEBUG] snapshot f1 bbox : {bbox_f1}")
            _export_static_snapshot_usd(duplicated_geo, temp_usd_f1, asset_name)

            # frame5 snapshot
            cmds.setAttr(bend_attr, BEND_AMOUNT)
            try:
                cmds.dgdirty(allPlugs=True)
            except:
                pass
            cmds.refresh(force=True)
            bbox_f5 = cmds.exactWorldBoundingBox(duplicated_geo)
            print(f"[DEBUG] snapshot f5 bbox : {bbox_f5}")
            _export_static_snapshot_usd(duplicated_geo, temp_usd_f5, asset_name)

            if bbox_f1 == bbox_f5:
                print("[WARN] snapshot bbox도 동일함. 이 PC에서는 bend static 평가 자체도 의심해야 함.")

            # 두 static USD를 animated USD로 합치기
            _combine_two_static_usd_to_animated(temp_usd_f1, temp_usd_f5, temp_usd_anim)

        else:
            # bend 대상 아니면 그냥 static export
            _export_static_snapshot_usd(duplicated_geo, temp_usd_anim, asset_name)

    except Exception as e:
        cmds.warning(f"[❌] snapshot USD 생성 실패: {e}")
        return False

    if not os.path.exists(temp_usd_anim):
        cmds.warning(f"[❌] temp animated USD가 생성되지 않았습니다: {temp_usd_anim}")
        return False

    print(f"[DEBUG] temp animated USD exported: {temp_usd_anim}")

    # ------------------------------------------------------------
    # JSON 생성
    # ------------------------------------------------------------
    mesh_list = cmds.listRelatives(duplicated_geo, allDescendents=True, type="mesh", fullPath=True) or []
    result_data = {"meshes": []}

    cmds.progressWindow(
        title='LookDev Export',
        progress=0,
        status='Starting JSON export...',
        isInterruptable=False,
        maxValue=len(mesh_list)
    )

    for idx, mesh in enumerate(mesh_list):
        mesh_name = mesh.split("|")[-1]
        mesh_info = {"name": mesh_name, "materials": []}
        shading_grps = cmds.listConnections(mesh, type='shadingEngine') or []

        for sg in shading_grps:
            materials = cmds.ls(cmds.listConnections(sg + ".surfaceShader"), materials=True) or []

            for mat in materials:
                if category in ['bg', 'prop']:
                    mat_data = {
                        "name": mat,
                        "type": "basic",
                        "Diffuse": None,
                        "Alpha": None,
                        "Normal": None,
                        "textures": {"allTextures": [], "uv": {}}
                    }

                    for slot in ["color", "transparency", "normalCamera"]:
                        if cmds.attributeQuery(slot, node=mat, exists=True):
                            file_nodes = find_all_file_textures(f"{mat}.{slot}")
                            if file_nodes:
                                rep_tex = find_lowest_udim_texture(file_nodes)
                                if rep_tex:
                                    if slot == "color":
                                        mat_data["Diffuse"] = rep_tex
                                    elif slot == "transparency":
                                        mat_data["Alpha"] = rep_tex
                                    elif slot == "normalCamera":
                                        mat_data["Normal"] = rep_tex

                                    mat_data["textures"]["allTextures"].extend(
                                        [cmds.getAttr(f"{f}.fileTextureName") for f in file_nodes]
                                    )

                                    if not mat_data["textures"]["uv"]:
                                        mat_data["textures"]["uv"] = get_uv_data_from_file_node(file_nodes[0])
                            else:
                                try:
                                    rgb = cmds.getAttr(f"{mat}.{slot}")[0]
                                    color_val = [round(c, 4) for c in rgb]
                                    if slot == "color":
                                        mat_data["Diffuse"] = color_val
                                    elif slot == "transparency":
                                        mat_data["Alpha"] = color_val
                                except:
                                    pass

                    mesh_info["materials"].append(mat_data)

                else:
                    input_attrs = cmds.listAttr(mat, multi=True) or []
                    layer_indices = {}

                    for attr in input_attrs:
                        match = re.search(r"inputs\[(\d+)\]\.(\w+)", attr)
                        if match:
                            layer_indices.setdefault(int(match.group(1)), []).append(match.group(2))

                    mat_data = {"name": mat, "type": "layered_udim", "layers": []}

                    for i, slots in layer_indices.items():
                        layer_data = {"layer": i, "textures": {"allTextures": [], "uv": {}}}

                        for slot in slots:
                            all_file_nodes = find_all_file_textures(f"{mat}.inputs[{i}].{slot}")
                            if all_file_nodes:
                                representative_tex = find_lowest_udim_texture(all_file_nodes)
                                udim_path = make_udim_pattern_path(representative_tex)

                                if slot == "color":
                                    layer_data["Diffuse"] = udim_path
                                elif slot == "transparency":
                                    layer_data["Alpha"] = udim_path
                                else:
                                    layer_data[slot] = udim_path

                                layer_data["textures"]["allTextures"].extend(
                                    [cmds.getAttr(f"{f}.fileTextureName") for f in all_file_nodes]
                                )

                                if not layer_data["textures"]["uv"]:
                                    layer_data["textures"]["uv"] = get_uv_data_from_file_node(all_file_nodes[0])

                        if "Diffuse" in layer_data or "Alpha" in layer_data:
                            mat_data["layers"].append(layer_data)

                    mesh_info["materials"].append(mat_data)

        result_data["meshes"].append(mesh_info)
        cmds.progressWindow(edit=True, progress=idx + 1)

    cmds.progressWindow(endProgress=True)

    with open(final_json, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    print(f"🧾 JSON saved to: {final_json}")

    # final copy
    try:
        shutil.copy(temp_usd_anim, final_usd)
        print(f"✅ USD copied to: {final_usd}")
    except PermissionError:
        cmds.warning("블랜더가 열려있어서 USD를 덮어쓸 수 없습니다.")
    except Exception as e:
        cmds.warning(f"[⚠️] USD 파일 복사 실패: {e}")

    # 최소 원복
    if cmds.objExists(duplicated_geo):
        try:
            cmds.delete(duplicated_geo)
        except:
            pass

    if cmds.objExists(temp_original_name):
        try:
            if cmds.objExists(base_geo_name):
                try:
                    cmds.delete(base_geo_name)
                except:
                    pass
            cmds.rename(temp_original_name, base_geo_name)
        except:
            pass

    cmds.select(clear=True)

    print(f"✅ LookDev USD exported to: {final_usd}")
    print("=" * 80)
    print("[USD EXPORT] END")
    print("=" * 80 + "\n")
    return True

def export_usd_to_custom_folder():
    import json, os, shutil, re
    import maya.cmds as cmds

    # ✅ 1. 선택된 그룹 확인
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("그룹을 선택해주세요.")
        return False

    asset_group = sel[0]
    asset_name = asset_group.split("|")[-1]  # 그룹 이름 = 어셋 이름

    # ✅ 2. 하위에서 'geo' 그룹 찾기
    children = cmds.listRelatives(asset_group, children=True, type="transform", fullPath=True) or []
    geo_group = None
    for c in children:
        if c.split("|")[-1] == "geo":
            geo_group = c
            break

    if not geo_group:
        cmds.warning(f"'{asset_group}' 하위에 'geo' 그룹이 없습니다.")
        return False

    # ✅ 3. 임시 USD 저장 위치
    temp_dir = os.path.expanduser("~/Documents/maya")
    os.makedirs(temp_dir, exist_ok=True)
    usd_name = f"{asset_name}.usd"
    temp_usd = os.path.join(temp_dir, usd_name)

    # ✅ 4. 최종 저장 폴더 선택
    folder = cmds.fileDialog2(fm=3, dialogStyle=2, caption="Select Export Folder")
    if not folder:
        cmds.warning("폴더를 선택하지 않았습니다.")
        return False
    export_folder = folder[0]
    final_usd = os.path.join(export_folder, usd_name)
    final_json = os.path.splitext(final_usd)[0] + ".json"

    # ✅ 5. USD Export 옵션
    usd_options = (
        f'exportUVs=1;exportSkels=none;exportSkin=none;exportBlendShapes=0;'
        f'exportDisplayColor=0;filterTypes=nurbsCurve;exportColorSets=0;'
        f'defaultMeshScheme=none;animation=1;eulerFilter=0;staticSingleSample=0;'
        f'startTime=1;endTime=5;frameStride=1;frameSample=0.0;defaultUSDFormat=usdc;'
        f'exportInstances=1;exportVisibility=1;mergeTransformAndShape=1;stripNamespaces=0;'
        f'parentScope=/{asset_name};'
    )

    # ✅ 6. geo 하위 선택 후 Export
    cmds.select(geo_group, hi=True)
    cmds.file(temp_usd, force=True, options=usd_options, typ="USD Export", pr=True, es=True)

    try:
        shutil.copy(temp_usd, final_usd)
    except Exception as e:
        cmds.warning(f"[⚠️] USD 복사 실패: {e}")

    # ✅ 7. 간단한 JSON 저장 (메쉬 리스트)
    mesh_list = cmds.listRelatives(geo_group, allDescendents=True, type="mesh", fullPath=True) or []
    result_data = {"asset": asset_name, "meshes": [m.split("|")[-1] for m in mesh_list]}
    with open(final_json, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    cmds.select(clear=True)
    print(f"✅ USD Exported: {final_usd}")
    return True



def open_export_folder():
    # export_usd 함수와 비슷한 로직을 사용하여 폴더 경로를 구합니다.
    current_file_path = cmds.file(q=True, sn=True)
    project_drive, category, asset_name, export_folder_path = get_scene_export_info(current_file_path)
    if not export_folder_path:
        cmds.warning(f"Export path does not exist: {current_file_path}")
        return
    
    if os.path.exists(export_folder_path):
        os.startfile(export_folder_path)
    else:
        cmds.warning(f"Export path does not exist: {export_folder_path}")


def refresh_dropdowns():
    current_file_path = cmds.file(q=True, sn=True)
    if not current_file_path:
        # cmds.warning("현재 열린 파일이 없습니다.")
        return
    
    # 파일 경로에서 정보 추출
    path_parts = current_file_path.replace("\\", "/").split("/")
    project = path_parts[0][-1]  # 드라이브 문자
    category = path_parts[-4]
    asset = path_parts[-3]
    process = path_parts[-2]
    version = os.path.splitext(path_parts[-1])[0].split('_')[-1]
    
    # 프로젝트 매핑
    project_mapping = {v: k for k, v in projects.items()}
    project_name = project_mapping.get(f"{project}:/", "")

    # 드롭다운 메뉴 업데이트
    if project_name:
        cmds.optionMenu(projectMenuName, e=True, v=project_name)
    if category:
        cmds.optionMenu(categoryMenuName, e=True, v=category)
    if asset:
        cmds.optionMenu(assetMenuName, e=True, v=asset)
    if process:
        cmds.optionMenu(processMenuName, e=True, v=process)
    
    # 파일 메뉴 업데이트
    file_path = os.path.join(get_project_path(project_name), category, asset, process)
    update_file_menu(file_path)

def set_option_menu_value_safe(menu, value):
    items = cmds.optionMenu(menu, q=True, itemListLong=True) or []
    labels = [cmds.menuItem(item, q=True, label=True) for item in items]
    if value not in labels:
        cmds.menuItem(label=value, parent=menu)
    cmds.optionMenu(menu, e=True, value=value)

    
def parse_scene_path(path):
    normalized_path = path.replace("\\", "/")
    coc_root = get_project_path(COC_PROJECT).replace("\\", "/").rstrip("/")

    if normalized_path.lower().startswith(coc_root.lower() + "/"):
        rel_path = normalized_path[len(coc_root):].strip("/")
        rel_parts = [part for part in rel_path.split("/") if part]
        if len(rel_parts) >= 2:
            asset = rel_parts[0]
            version = os.path.splitext(rel_parts[-1])[0]
            return COC_PROJECT, COC_CATEGORY, asset, "Fin", version

    try:
        project_name = ""
        matched_root = ""
        for candidate_name, candidate_root in projects.items():
            root = str(candidate_root or "").replace("\\", "/").rstrip("/")
            if root and normalized_path.lower().startswith(root.lower() + "/") and len(root) > len(matched_root):
                project_name = candidate_name
                matched_root = root

        if not project_name:
            return None, None, None, None, None

        rel_path = normalized_path[len(matched_root):].strip("/")
        rel_parts = [part for part in rel_path.split("/") if part]
        if len(rel_parts) < 2:
            return None, None, None, None, None

        category = rel_parts[0]
        asset = rel_parts[1]
        process = rel_parts[2] if len(rel_parts) >= 3 else "Fin"
        version = os.path.splitext(rel_parts[-1])[0]

        return project_name, category, asset, process, version
    except Exception as e:
        cmds.warning(f"[Lookdev Parse] Path parse failed: {e}")
        return None, None, None, None, None

def update_dropdowns_from_scene_path(*args):
    current_file_path = cmds.file(q=True, sn=True)
    if not current_file_path:
        # cmds.warning("현재 열린 파일이 없습니다.")
        return

    # 🔁 여기서 새 함수 호출
    project, category, asset, process, version = parse_scene_path(current_file_path)
    if not all([project, category, asset, process, version]):
        return

    set_option_menu_value_safe(projectMenuName, project)
    set_option_menu_value_safe(categoryMenuName, category)
    set_option_menu_value_safe(assetMenuName, asset)
    set_option_menu_value_safe(processMenuName, process)

    clear_option_menu_items(fileMenuName)
    cmds.menuItem(parent=fileMenuName, label=version)


def incremental_save():
    change_description = cmds.textField(changeDescriptionField, query=True, text=True)  # 텍스트 필드의 내용을 가져옵니다.
    change_description = change_description.replace(" ", "_")  # 공백을 언더바로 교체합니다.

    current_file = cmds.file(q=True, sn=True)
    if not current_file:
        cmds.warning("No file is currently open.")
        return

    # 파일 이름에서 이전 변경사항을 제거하는 로직 추가
    # 예: check_rig_v030_material_wheel.mb -> check_rig_v030_wheel.mb
    base_name_pattern = re.compile(r"(.+)(_v\d+)(_.+)?(\.mb)$")
    match = base_name_pattern.search(current_file)
    if match:
        base_name = match.group(1)  # 기본 이름 (예: check_rig)
        version_str = match.group(2)  # 버전 (예: _v030)
        file_ext = match.group(4)  # 파일 확장자 (예: .mb)
        version_num = int(version_str[2:])  # 숫자 부분만 추출 (예: 30)
        new_version_num = version_num + 1  # 버전 1 증가
        new_version_str = "v" + str(new_version_num).zfill(3)  # 새 버전 문자열 (예: _v031)

        # 새로운 파일 이름 구성: 기본 이름 + 새 버전 + 변경사항 + 확장자
        new_file_name = f"{base_name}_{new_version_str}"
        if change_description:  # 변경사항이 입력되었다면 파일 이름에 추가
            new_file_name += f"_{change_description}"
        new_file_name += file_ext  # 파일 확장자 추가

        cmds.file(rename=new_file_name)
        cmds.file(save=True, type='mayaBinary')
        return new_file_name
    else:
        cmds.warning("Version information not found in file name.")
        return None

        
def get_latest_version_number(dir_path, base_filename):
    """주어진 디렉토리와 기본 파일 이름에서 가장 높은 버전 번호를 찾습니다."""
    version_pattern = re.compile(r'_v(\d+)')
    max_version = 0
    for filename in os.listdir(dir_path):
        if base_filename in filename:
            match = version_pattern.search(filename)
            if match:
                version_num = int(match.group(1))
                max_version = max(max_version, version_num)
    return max_version

def publish():
    new_file = incremental_save()  # 새로운 버전으로 파일 저장
    if new_file:
        # 파일 이름에서 어셋 이름 추출
        asset_name = os.path.basename(new_file).split("_")[0]
        # assets 디렉토리 경로를 기반으로 최종 파일 경로 설정
        final_dir = os.path.join("A:/assets/ch", asset_name)  # 예: A:/assets/ch/arbo
        final_file = os.path.join(final_dir, f"{asset_name}.mb")  # 예: A:/assets/ch/arbo/arbo.mb

        if not os.path.exists(final_dir):
            os.makedirs(final_dir)
        
        shutil.copy(new_file, final_file)  # 새 파일을 파이널 파일로 복사
        cmds.confirmDialog(title='Publish Complete', message=f'Published: {final_file}', button=['OK'])
    else:
        cmds.warning("Publish failed.")



def is_valid_asset(name):
    """유효한 어셋인지 확인합니다."""
    return not (name.startswith('.') or name.startswith('ttm_') or name.startswith('Presets') or 'presets' in name.lower() or 'light' in name.lower() or name.startswith('_') or 'omit' in name.lower() or '-' in name)

def clear_option_menu_items(option_menu):
    """주어진 optionMenu의 모든 menuItem을 제거합니다."""
    menu_items = cmds.optionMenu(option_menu, query=True, itemListLong=True)
    if menu_items:
        for item in menu_items:
            cmds.deleteUI(item)

def update_category_menu(*args):
    # 카테고리 갱신
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    clear_option_menu_items(categoryMenuName)
    categories = get_category_list(selected_project)
    for category in categories:
        cmds.menuItem(parent=categoryMenuName, label=category)

    # 카테고리가 바뀌었으니 어셋, 프로세스, 파일도 초기화
    clear_option_menu_items(assetMenuName)
    clear_option_menu_items(processMenuName)
    clear_option_menu_items(fileMenuName)

    # ✅ 자동으로 첫 번째 카테고리 선택
    if categories:
        cmds.optionMenu(categoryMenuName, e=True, value=categories[0])
        update_asset_menu()


def update_asset_menu(*args):
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    selected_category = cmds.optionMenu(categoryMenuName, query=True, value=True)
    assets_path = get_assets_root(selected_project, selected_category)
    assets = []

    if os.path.exists(assets_path):
        assets = sorted([f for f in os.listdir(assets_path) 
                         if os.path.isdir(os.path.join(assets_path, f)) and not f.startswith('.') and not f.startswith('_')],
                         key=lambda x: x.lower())
        clear_option_menu_items(assetMenuName)
        for asset in assets:
            cmds.menuItem(parent=assetMenuName, label=asset)
    else:
        clear_option_menu_items(assetMenuName)

    clear_option_menu_items(processMenuName)
    cmds.menuItem(parent=processMenuName, label="Fin")
    if not is_coc_project(selected_project):
        cmds.menuItem(parent=processMenuName, label="mod")
        cmds.menuItem(parent=processMenuName, label="rig")

    clear_option_menu_items(fileMenuName)

    if assets:
        first_asset = assets[0]
        set_option_menu_value_safe(assetMenuName, first_asset)
        update_process_menu()
        save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))  # ✅ 추가
        # print("[DEBUG] update_asset_menu 통해 상태 저장됨")

def update_process_menu():
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    selected_category = cmds.optionMenu(categoryMenuName, query=True, value=True)
    selected_asset = cmds.optionMenu(assetMenuName, query=True, value=True)
    base_path = get_project_path(selected_project)

    clear_option_menu_items(processMenuName)
    cmds.menuItem(parent=processMenuName, label="Fin")
    if not is_coc_project(selected_project):
        cmds.menuItem(parent=processMenuName, label="mod")
        cmds.menuItem(parent=processMenuName, label="rig")

    if is_coc_project(selected_project):
        set_option_menu_value_safe(processMenuName, "Fin")
        update_file_menu()
        save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))
        return

    fin_file_mb = os.path.join(base_path, selected_category, selected_asset, f"{selected_asset}.mb")
    fin_file_ma = os.path.join(base_path, selected_category, selected_asset, f"{selected_asset}.ma")

    selected_process = "Fin" if (os.path.exists(fin_file_mb) or os.path.exists(fin_file_ma)) else "mod"

    set_option_menu_value_safe(processMenuName, selected_process)
    update_file_menu()
    save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))
    # print("[DEBUG] update_process_menu 통해 상태 저장됨")

def update_file_menu(*args):
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    selected_category = cmds.optionMenu(categoryMenuName, query=True, value=True)
    selected_asset = cmds.optionMenu(assetMenuName, query=True, value=True)
    selected_process = cmds.optionMenu(processMenuName, query=True, value=True)

    base_path = get_project_path(selected_project)
    selected_file = cmds.optionMenu(fileMenuName, query=True, value=True) if cmds.optionMenu(fileMenuName, query=True, exists=True) else None
    if is_coc_project(selected_project):
        files_path = get_asset_folder_path(selected_project, selected_category, selected_asset)
        clear_option_menu_items(fileMenuName)
        if os.path.exists(files_path):
            files = sorted([f for f in os.listdir(files_path)
                            if os.path.isfile(os.path.join(files_path, f)) and (f.endswith(".mb") or f.endswith(".ma"))],
                           key=lambda x: os.path.getmtime(os.path.join(files_path, x)), reverse=True)
            for file in files:
                cmds.menuItem(parent=fileMenuName, label=file)
            if files:
                set_option_menu_value_safe(fileMenuName, files[0])
    elif selected_process == "Fin":
        files_path = os.path.join(base_path, selected_category, selected_asset)
        expected_file = f"{selected_asset}.mb"
        expected_file_ma = f"{selected_asset}.ma"

        clear_option_menu_items(fileMenuName)
        if os.path.exists(os.path.join(files_path, expected_file)):
            cmds.menuItem(parent=fileMenuName, label=expected_file)
            set_option_menu_value_safe(fileMenuName, expected_file)
        elif os.path.exists(os.path.join(files_path, expected_file_ma)):
            cmds.menuItem(parent=fileMenuName, label=expected_file_ma)
            set_option_menu_value_safe(fileMenuName, expected_file_ma)
    else:
        files_path = os.path.join(base_path, selected_category, selected_asset, selected_process)
        if os.path.exists(files_path):
            files = sorted([f for f in os.listdir(files_path)
                            if os.path.isfile(os.path.join(files_path, f)) and (f.endswith(".mb") or f.endswith(".ma"))],
                           key=lambda x: os.path.getmtime(os.path.join(files_path, x)), reverse=True)
            clear_option_menu_items(fileMenuName)
            for file in files:
                cmds.menuItem(parent=fileMenuName, label=file)
            if files:
                set_option_menu_value_safe(fileMenuName, files[0])
        else:
            clear_option_menu_items(fileMenuName)





def load_selected_asset(action):
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    selected_category = cmds.optionMenu(categoryMenuName, query=True, value=True)
    selected_asset = cmds.optionMenu(assetMenuName, query=True, value=True)
    selected_process = cmds.optionMenu(processMenuName, query=True, value=True)
    selected_file = cmds.optionMenu(fileMenuName, query=True, value=True) if cmds.optionMenu(fileMenuName, query=True, exists=True) else None
    
    base_path = get_project_path(selected_project)
    
    # 'Fin' 프로세스 선택 시 최종 파일 경로 구성
    if is_coc_project(selected_project):
        if selected_file:
            asset_path = get_asset_file_path(selected_project, selected_category, selected_asset, selected_process, selected_file)
        else:
            cmds.warning("No file selected.")
            return
    elif selected_process == 'Fin':
        asset_path = os.path.join(base_path, selected_category, selected_asset, f"{selected_asset}.mb")
    else:
        # 파일 메뉴에서 선택된 파일 확인
        if selected_file:
            asset_path = os.path.join(base_path, selected_category, selected_asset, selected_process, selected_file)
        else:
            # 'Fin' 이외의 프로세스 선택 시 파일 선택이 필요
            cmds.warning("No file selected.")
            return

    if os.path.exists(asset_path):
        if action == "open":
            cmds.file(asset_path, o=True, force=True, ignoreVersion=True)
        elif action == "reference":
            asset_name = selected_asset   # 드롭다운에서 고른 에셋 이름
            cmds.file(asset_path, r=True, namespace=asset_name, options="v=0")
        else:
            cmds.warning(f"Unsupported action: {action}")
    else:
        cmds.warning(f"Asset path does not exist: {asset_path}")



def get_materials_from_selected_objects():
    selectedObjects = cmds.ls(sl=True, dag=True, leaf=True, noIntermediate=True, shapes=True)
    
    materials = set()
    system_materials_assigned = False

    for obj in selectedObjects:
        shadingGrps = cmds.listConnections(obj, type='shadingEngine')
        if not shadingGrps:
            continue

        for shadingGrp in shadingGrps:
            mats = cmds.ls(cmds.listConnections(shadingGrp, source=True, destination=False), materials=True)
            for mat in mats:
                if mat in ["lambert1", "particleCloud1", "standardSurface1", "initialParticleSE", "initialShadingGroup"]:
                    system_materials_assigned = True
                else:
                    materials.add(mat)
                
    return list(materials), system_materials_assigned

def get_materials_from_selected_materials():
    selectedMaterials = cmds.ls(sl=True, materials=True)
    
    # 시스템 머터리얼과 shading 그룹들을 필터링 목록에 추가
    systemMaterialsAndGroups = ["lambert1", "particleCloud1", "standardSurface1", "initialParticleSE", "initialShadingGroup"]
    
    # 필터링 목록에 있는 머터리얼/그룹을 제외한 유효한 머터리얼들만 선택
    validMaterials = [mat for mat in selectedMaterials if mat not in systemMaterialsAndGroups]
    
    # validMaterials 리스트가 비어 있는지 확인
    system_materials_assigned = not validMaterials
    
    return validMaterials, system_materials_assigned

def is_referenced(node):
    try:
        return cmds.referenceQuery(node, isNodeReferenced=True)
    except RuntimeError:
        return False
        
# 히스토리 검사를 위한 함수
def has_unwanted_history(mesh):
    history = check_history(mesh)
    return bool(history)
    # generic_mesh_check(has_ngons)

def check_history(mesh):
    history_nodes = cmds.listHistory(mesh)
    if not history_nodes:
        return []
    # 제외할 히스토리 타입
    exclude_types = ['skinCluster', 'blendShape', 'tweak', 'blendWeighted', 'groupId', 'groupParts', 'mesh', 'animCurveUU', 'joint', 'transform', 'shadingEngine', 'objectSet', 'modelPanel']
    unwanted_history = []
    print(f"Mesh '{mesh}' History Nodes:")
    for node in history_nodes:
        node_type = cmds.nodeType(node)
        # exclude_types 리스트에 포함되지 않는 노드 타입만 출력 및 추가
        if node_type not in exclude_types:
            print(f"  Node: {node}, Type: {node_type}")
            unwanted_history.append({"node": node, "type": node_type})
        else:
            # 제외되는 히스토리 노드도 디버깅 목적으로 출력
            print(f"  Excluded Node: {node}, Type: {node_type}")
    return unwanted_history

def check_history_wrapper(*args):
    all_meshes = cmds.ls(type='mesh', long=True)
    meshes_with_history = []

    for mesh in all_meshes:
        if has_unwanted_history(mesh):
            meshes_with_history.append(mesh)

    if meshes_with_history:
        mesh_names = [cmds.listRelatives(mesh, parent=True)[0] for mesh in meshes_with_history]
        message = "히스토리가 있는 메쉬:\n" + "\n".join(mesh_names)
        result = cmds.confirmDialog(title='History Check Results', message=message, button=['OK'])
        cmds.select(meshes_with_history)
    else:
        cmds.warning('히스토리 이상 없습니다.')  # 경고 메시지로 결과 출력


def check_for_ngons(*args):
    ngon_meshes = []
    all_meshes = cmds.ls(type='mesh')
    
    for mesh in all_meshes:
        parent = cmds.listRelatives(mesh, parent=True, fullPath=True) or []
        if not parent:
            continue
        parent = parent[0]

        # 면을 순회하면서 면의 정점 수가 4개를 초과하는지 검사
        faceCount = cmds.polyEvaluate(parent, face=True)
        for i in range(faceCount):
            face = '{}.f[{}]'.format(parent, i)
            vertexCount = len(cmds.polyInfo(face, faceToVertex=True)[0].split()) - 2  # "FACE vtx1 vtx2 vtx3 ..."에서 처음 2개는 "FACE #"이므로 제외
            if vertexCount > 4:  # N-gon을 찾았다면
                ngon_meshes.append(parent)
                break  # 해당 메시에 대한 검사를 종료하고 다음 메시로 넘어갑니다.

    return ngon_meshes

def check_and_cleanup_ngons(*args):
    # 씬 내의 모든 메시를 찾고 선택합니다.
    all_meshes = cmds.ls(type='mesh')
    mesh_transforms = [cmds.listRelatives(mesh, parent=True)[0] for mesh in all_meshes if cmds.listRelatives(mesh, parent=True)]
    cmds.select(mesh_transforms)
    
    # Cleanup 조건에 맞는 메쉬가 있는지 검사합니다.
    cleanup_check_command = 'polyCleanupArgList 4 { "0","2","1","0","1","0","0","0","0","1e-05","0","1e-05","0","1e-05","0","-1","0","0" };'
    mel.eval(cleanup_check_command)
    
    selected_objects = cmds.ls(selection=True)
    if selected_objects:
        message = "다각형 조건에 맞는 메쉬가 발견되었습니다. 선택 작업을 실행하거나 클린업을 진행하시겠습니까?"
        result = cmds.confirmDialog(title='Cleanup Results', message=message, button=['Select', 'Clean Up', 'Cancel'], defaultButton='Select', cancelButton='Cancel', dismissString='Cancel')
        
        if result == 'Select':
            cleanup_command = 'expandPolyGroupSelection; polyCleanupArgList 4 { "0","2","1","0","1","0","0","0","0","1e-05","0","1e-05","0","1e-05","0","-1","0","0" };'
            mel.eval(cleanup_command)
        elif result == 'Clean Up':
            # 지정된 클린업 조건으로 메시를 클린업합니다.
            cleanup_command = 'expandPolyGroupSelection; polyCleanupArgList 4 { "0","1","1","0","1","0","0","0","0","1e-05","0","1e-05","0","1e-05","0","-1","0","0" };'
            mel.eval(cleanup_command)
    else:
        cmds.warning('다각형 이상 없습니다.')  # 경고 메시지로 결과 출력
        cmds.select(clear=True)



def check_and_fix_mesh_suffix(*args):
    # 모든 변환 노드를 가져옵니다.
    all_transforms = cmds.ls(type='transform', long=False)
    # 변환 노드 중에서 실제로 메쉬를 가진 노드만 필터링합니다.
    mesh_transforms = [transform for transform in all_transforms if cmds.listRelatives(transform, children=True, type='mesh')]

    incorrect_suffix_meshes = [mesh for mesh in mesh_transforms if not mesh.endswith('_geo')]
    corrected_mesh_names = []  # 변경된 이름을 저장할 리스트 추가

    if incorrect_suffix_meshes:
        message = "_geo가 붙어있지 않습니다. 명령을 선택하세요. :\n" + "\n".join(incorrect_suffix_meshes)
        result = cmds.confirmDialog(title='Mesh Suffix Check Results', message=message, button=['Select', 'Add', 'Cancel'], defaultButton='Add', cancelButton='Cancel', dismissString='Cancel')
        
        if result == 'Add':
            for mesh in incorrect_suffix_meshes:
                new_name = mesh + '_geo'
                corrected_name = cmds.rename(mesh, new_name)
                corrected_mesh_names.append(corrected_name)  # 변경된 이름을 리스트에 추가
        elif result == 'Select':
            cmds.select(incorrect_suffix_meshes)  # 선택된 메쉬를 하이라이트
        else:
            pass  # "Cancel"이 선택되면 아무 작업도 수행하지 않음
    else:
        cmds.warning('There are no meshes without the "_geo" suffix.')

    # 필요한 경우, 여기에서 corrected_mesh_names를 사용하여 수정된 메쉬를 선택하거나 다른 작업을 수행할 수 있습니다.



def run_cleanup_command_for_all_meshes(*args):
    all_meshes = cmds.ls(type='mesh')
    mesh_transforms = [
        cmds.listRelatives(mesh, parent=True, fullPath=True)[0]
        for mesh in all_meshes
        if cmds.listRelatives(mesh, parent=True)
    ]
    cmds.select(cmds.ls(mesh_transforms, long=True))

    cleanup_check_command = 'polyCleanupArgList 4 { "0","2","1","0","0","0","0","0","0","1e-05","0","1e-05","0","1e-05","0","1","0","0" };'
    mel.eval(cleanup_check_command)

    selected_objects = cmds.ls(selection=True)
    if selected_objects:
        message = "Cleanup 조건에 맞는 메쉬가 발견되었습니다. 선택 작업을 실행하거나 클린업을 진행하시겠습니까?"
        result = cmds.confirmDialog(
            title='Cleanup Results',
            message=message,
            button=['Select', 'Clean Up', 'Cancel'],
            defaultButton='Select',
            cancelButton='Cancel',
            dismissString='Cancel'
        )

        if result == 'Select':
            cleanup_command = 'expandPolyGroupSelection; polyCleanupArgList 4 { "0","2","1","0","1","0","0","0","0","1e-05","0","1e-05","0","1e-05","0","1","0","0" };'
            mel.eval(cleanup_command)
        elif result == 'Clean Up':
            cleanup_command = 'expandPolyGroupSelection; polyCleanupArgList 4 { "0","1","1","0","1","0","0","0","0","1e-05","0","1e-05","0","1e-05","0","1","0","0" };'
            mel.eval(cleanup_command)
    else:
        cmds.warning('넌매니폴드 이상 없습니다.')
        cmds.select(clear=True)


def is_mesh_or_group(node):
    """
    노드가 메쉬이거나 메쉬를 포함하는 그룹인지 확인합니다.
    """
    # 메쉬 직접 체크
    if cmds.nodeType(node) == 'transform':
        # 전체 경로를 포함한 shapes 조회
        shapes = cmds.listRelatives(node, children=True, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(shape) == 'mesh' for shape in shapes):
            return True  # 직접 메쉬를 포함하는 변환 노드

    # 그룹 체크: 메쉬를 자식으로 포함하는지 확인
    # 전체 경로를 사용하여 children 조회
    children = cmds.listRelatives(node, children=True, type='transform', fullPath=True) or []
    for child in children:
        # 재귀 호출 시 전체 경로 사용
        if is_mesh_or_group(child):
            return True

    return False  # 메쉬나 메쉬를 포함하는 그룹이 아님





def generic_mesh_check(check_function, title, message_if_found, message_if_not_found):
    all_meshes = cmds.ls(type='mesh', long=True)
    matching_meshes = [mesh for mesh in all_meshes if check_function(mesh) and not is_referenced(mesh)]
    if matching_meshes:
        mesh_names = [cmds.listRelatives(mesh, parent=True, path=True)[0] for mesh in matching_meshes]
        cmds.confirmDialog(title=title, message=message_if_found + "\n" + "\n".join(mesh_names), button=['OK'])
        cmds.select(matching_meshes)
    else:
        # 변경된 부분: 결과가 없을 경우 워닝 메시지 출력
        cmds.warning(message_if_not_found)
    pass
    
def find_non_frozen_transforms(*args):
    all_transform_nodes = cmds.ls(long=True, type='transform')
    print(f"Total transform nodes: {len(all_transform_nodes)}")

    valid_nodes = [node for node in all_transform_nodes if not is_referenced(node) and is_mesh_or_group(node)]
    print(f"Valid nodes (non-referenced, mesh or group): {len(valid_nodes)}")

    objects_with_non_frozen_transforms = []

    for node in valid_nodes:
        if any(abs(cmds.getAttr(node + '.' + attr)) > 1e-6 for attr in ['translateX', 'translateY', 'translateZ', 'rotateX', 'rotateY', 'rotateZ']) \
                or any(abs(cmds.getAttr(node + '.' + attr) - 1) > 1e-6 if 'scale' in attr else abs(cmds.getAttr(node + '.' + attr)) > 1e-6 for attr in ['scaleX', 'scaleY', 'scaleZ']):
            objects_with_non_frozen_transforms.append(node)

    print(f"Objects with non-frozen transforms: {len(objects_with_non_frozen_transforms)}")

    if objects_with_non_frozen_transforms:
        cmds.select(objects_with_non_frozen_transforms)
        object_names_list = []

        for obj in objects_with_non_frozen_transforms:
            # 전체 경로에서 오브젝트의 이름만 추출
            final_object_name = obj.split('|')[-1]  # '|' 기준으로 나눈 후, 가장 마지막 항목이 오브젝트의 이름
            object_names_list.append(final_object_name)
            print(f"Object to report: {final_object_name}")  # 최종 보고될 오브젝트 명 출력

        object_names = "\n".join(object_names_list)
        cmds.confirmDialog(title='Non-Frozen Transforms Found', message='프리즈가 안된 오브젝트가 존재합니다:\n' + object_names, button=['OK'])
    else:
        cmds.warning('프리즈 이상 없습니다.')
        cmds.select(clear=True)
    pass
    
def check_mesh_namespace(*args):
    def has_namespace(mesh):
        return ':' in mesh
    generic_mesh_check(has_namespace, '네임스페이스가 있는 메쉬 발견', '네임스페이스가 있는 메쉬:', '네임스페이스 이상 없습니다.')
    pass


def set_shading_group_name(get_materials_func):
    if not cmds.ls(sl=True):
        cmds.confirmDialog(title='Error', message='오브젝트 또는 메터리얼을 선택해 주세요', button=['OK'])
        return
    
    materials, system_materials_assigned = get_materials_func()
    
    if system_materials_assigned:
        cmds.confirmDialog(title='경고', message='오브젝트에 시스템 메터리얼(lambert1 등)이 할당되어 있습니다.', button=['OK'])
        return
    
    invalidMaterials = []

    for material in materials:
        if not material.startswith("MI_"):
            invalidMaterials.append(material)
            continue

        shadingGroups = cmds.listConnections(material, type="shadingEngine")
        if not shadingGroups:
            shadingGroups = []  # Ensure shadingGroups is always a list

        modifiedMaterialName = material.replace("MI_", "MIA_")
        
        for shadingGroup in shadingGroups:
            try:
                cmds.rename(shadingGroup, modifiedMaterialName)
            except RuntimeError as e:
                print(f"Could not rename {shadingGroup}: {e}")
                continue

    if invalidMaterials:
        errorMessage = "메터리얼 이름이 MI_로 시작하지 않습니다. 해당 메터리얼의 이름 앞에 MI를 적용할까요?\n\n"
        errorMessage += "\n".join(invalidMaterials)
        choice = cmds.confirmDialog(title='Error', message=errorMessage, button=['OK', 'Cancel'])

        if choice == "OK":
            for invalidMat in invalidMaterials:
                newMatName = "MI_" + invalidMat
                cmds.rename(invalidMat, newMatName)
                
                shadingGroups = cmds.listConnections(newMatName, type="shadingEngine")
                if not shadingGroups:
                    shadingGroups = []  # Ensure shadingGroups is always a list

                modifiedMaterialName = newMatName.replace("MI_", "MIA_")
                
                for shadingGroup in shadingGroups:
                    try:
                        cmds.rename(shadingGroup, modifiedMaterialName)
                    except RuntimeError as e:
                        print(f"Could not rename {shadingGroup}: {e}")
                        continue
    else:
        if get_materials_func == get_materials_from_selected_materials and not materials:
            cmds.confirmDialog(title='Error', message='메터리얼을 선택해 주세요', button=['OK'])
        else:
            cmds.confirmDialog(title='Success', message='이상 없습니다!', button=['OK'])

def check_uv_sets():
    all_meshes = cmds.ls(type='mesh', long=True)
    anomaly_objects = []
    incorrect_uvset_names = []
    
    for mesh in all_meshes:
        if is_referenced(mesh):
            continue

        obj = cmds.listRelatives(mesh, parent=True, path=True) or []
        if not obj:
            continue
        obj = obj[0]

        uv_sets = cmds.polyUVSet(obj, query=True, allUVSets=True) or []  # UV 세트가 없는 경우 빈 리스트를 반환하도록 수정
        if uv_sets and len(uv_sets) >= 2:  # uv_sets가 비어 있지 않은 경우에만 len 체크
            anomaly_objects.append(obj)

        if uv_sets and uv_sets[0] != 'map1':  # uv_sets가 비어 있지 않은 경우에만 첫 번째 요소 체크
            incorrect_uvset_names.append(obj)
    
    messages = []

    if anomaly_objects:
        messages.append(f'2개 이상의 UV set: {" , ".join(anomaly_objects)}')
    if incorrect_uvset_names:
        messages.append(f'첫 번째 UV set의 이름이 map1이 아님: {" , ".join(incorrect_uvset_names)}')

    if messages:
        message = "\n\n".join(messages)
        choice = cmds.confirmDialog(title='UV Set 검사 결과', message=message, button=['OK', 'Cancel'], defaultButton='OK', cancelButton='Cancel', dismissString='Cancel')
        
        if choice == 'OK':
            cmds.select(anomaly_objects + incorrect_uvset_names)
    else:
        cmds.warning("UV Set 이상 없습니다.")

def remove_namespace(obj_name):
    """네임스페이스를 제거하고 순수한 오브젝트 이름을 반환합니다."""
    return obj_name.split(":")[-1]
    
def check_material_and_sg_names():
    exclude_list = {"lambert1", "particleCloud1", "shaderGlow1", "standardSurface1", "initialParticleSE", "initialShadingGroup"}
    
    materials = cmds.ls(materials=True)
    shading_groups = cmds.ls(type='shadingEngine')
    materials = [remove_namespace(mat) for mat in materials if remove_namespace(mat) not in exclude_list]
    shading_groups = [remove_namespace(sg) for sg in shading_groups if remove_namespace(sg) not in exclude_list]

    incorrect_material_names = [mat for mat in materials if not mat.startswith('MI_')]
    incorrect_sg_names = [sg for sg in shading_groups if not sg.startswith('MIA_')]

    system_materials_assigned = check_assigned_system_materials()

    selection_list = incorrect_material_names + incorrect_sg_names + system_materials_assigned

    if incorrect_material_names or incorrect_sg_names or system_materials_assigned:
        result = cmds.confirmDialog(
            title='검사 결과',
            message='규칙을 따르지 않는 메터리얼/쉐이딩 그룹이 있거나 시스템 메터리얼이 할당된 오브젝트가 있습니다.\n선택하시겠습니까?',
            button=['Select', 'Cancel'],
            defaultButton='Select',
            cancelButton='Cancel',
            dismissString='Cancel'
        )

        if result == 'Select':
            cmds.select(selection_list, replace=True)
    else:
        cmds.warning("메터리얼 이상 없습니다.")

def check_assigned_system_materials():
    system_materials = ["lambert1", "particleCloud1", "shaderGlow1", "standardSurface1"]
    assigned_system_materials_objects = []

    # 모든 폴리곤 메쉬를 대상으로 루프
    all_meshes = cmds.ls(type='mesh', long=True)
    for mesh in all_meshes:
        transform_node = cmds.listRelatives(mesh, parent=True, fullPath=True) or []
        if not transform_node:
            continue
        transform_node = transform_node[0]
        shading_groups = cmds.listConnections(transform_node, type='shadingEngine') or []
        
        for sg in shading_groups:
            materials = cmds.ls(cmds.listConnections(sg + '.surfaceShader'), materials=True)
            for mat in materials:
                if mat in system_materials:
                    assigned_system_materials_objects.append(transform_node)
                    break
    
    return list(set(assigned_system_materials_objects))  # 중복 제거 후 반환
        
def is_material_modified(material):
    # 여기에는 시스템 머티리얼이 수정되었는지 확인하는 로직이 들어갑니다.
    # 예를 들어, 특정 속성이 기본값에서 변경되었는지 확인할 수 있습니다.
    # 이 함수는 True 또는 False를 반환해야 합니다.
    return False  # 임시로 False를 반환하도록 설정

def set_texture_max_resolution(value, *args):
    global last_selected_texture_resolution
    value = str(value)
    cmds.setAttr("hardwareRenderingGlobals.textureMaxResolution", int(value))
    last_selected_texture_resolution = value

def on_window_close():
    global last_selected_texture_resolution
    current_value = cmds.optionMenu(texture_option_menu, query=True, value=True)
    last_selected_texture_resolution = current_value
    
def reload_all_textures(*args):
    textures = cmds.ls(type='file')
    for texture in textures:
        file_path = cmds.getAttr(f'{texture}.fileTextureName')
        cmds.setAttr(f'{texture}.fileTextureName', file_path, type='string')
        


def setProjectFromDropdown(*args):
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    project_path = get_project_path(selected_project)
    
    if project_path:
        cmds.workspace(project_path, o=True)
        print(f'Project {selected_project} is now set to {project_path}')
    else:
        cmds.warning("Project path not found.")

def get_project_path(project):
    """선택된 프로젝트의 경로를 반환합니다."""
    return projects.get(normalize_project_selection(project), "")


import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om
import os

def remove_virus_nodes():
    removed = []

    keywords = ['fuckVirus', 'bleed_gene', 'vaccine', 'leukocyte']
    callbacks = ['CgAbBlastPanelOptChangeCallback', 'DCF_updateViewportList']

    # 1. scriptNode 제거
    for node in cmds.ls(type='script'):
        for attr in ['before', 'after']:
            if cmds.objExists(f"{node}.{attr}"):
                try:
                    content = cmds.getAttr(f"{node}.{attr}")
                    if any(k in content for k in keywords + callbacks):
                        cmds.lockNode(node, lock=False)
                        cmds.delete(node)
                        removed.append(f"scriptNode: {node}")
                        break
                except: continue

    # 2. expression 제거
    for node in cmds.ls(type='expression'):
        try:
            expr = cmds.getAttr(node + '.expression')
            if any(k in expr for k in keywords + callbacks):
                cmds.delete(node)
                removed.append(f"expression: {node}")
        except: continue

    # 3. scriptJob 제거
    for job in cmds.scriptJob(listJobs=True):
        if any(k in job for k in keywords + callbacks):
            try:
                job_id = int(job.split(":")[0])
                cmds.scriptJob(kill=job_id, force=True)
                removed.append(f"scriptJob: {job_id}")
            except: continue

    # 4. optionVar (deferredEvalString) 제거
    if cmds.optionVar(exists="deferredEvalString"):
        content = cmds.optionVar(q="deferredEvalString")
        if any(k in content for k in keywords + callbacks):
            cmds.optionVar(remove="deferredEvalString")
            removed.append("optionVar: deferredEvalString")

    # 5. modelPanel 콜백 제거
    for panel in cmds.getPanel(type="modelPanel"):
        try:
            cb = cmds.modelEditor(panel, q=True, editorChanged=True)
            if cb == "CgAbBlastPanelOptChangeCallback":
                cmds.modelEditor(panel, e=True, editorChanged="")
                removed.append(f"modelPanel: {panel} 콜백 제거")
        except: continue

    # 6. outlinerPanel 콜백 제거
    # for panel in cmds.getPanel(type="outlinerPanel") or []:
        # try:
            # sc = cmds.outlinerEditor(panel, q=True, selectCommand=True)
            # if sc:
                # cmds.outlinerPanel(panel, e=True, unParent=True)
                # removed.append(f"outlinerPanel: {panel} 제거됨")
        # except: continue
    # try:
        # if cmds.optionVar(exists="useScenePanelConfig") and cmds.optionVar(q="useScenePanelConfig") == 0:
            # mel.eval("$gOutlinerPanelNeedsInit = 1;")
        # mel.eval("initOutlinerPanel();")
    # except: pass

    # 7. UI 설정 저장 안 하도록
    cmds.file(uiConfiguration=False)

    # # # 8. 현재 씬 저장
    # try:
        # cmds.file(save=True, force=True)
        # removed.append("씬 저장 완료 ✅")
    # except:
        # removed.append("⚠ 씬 저장 실패 - 수동 저장 필요")

    # 결과 출력
    message = "다음 항목 정리됨:\n" + "\n".join(removed) if removed else "제거할 항목이 없습니다."
    cmds.confirmDialog(title="정리 완료", message=message, button=["OK"])


def remove_unknown_plugins():
    import maya.cmds as cmds

    removed = []

    # 1. 언노운 플러그인 제거
    unknown_plugins = cmds.unknownPlugin(q=True, list=True) or []
    for plugin in unknown_plugins:
        try:
            cmds.unknownPlugin(plugin, remove=True)
            removed.append(f"unknown: {plugin}")
        except:
            continue

    # 2. ngSkinTools2가 등록되어 있는 경우 처리
    plugin_name = "ngSkinTools2"
    all_plugins = cmds.pluginInfo(q=True, listPlugins=True) or []

    if plugin_name in all_plugins:
        if cmds.pluginInfo(plugin_name, query=True, loaded=True):
            try:
                cmds.unloadPlugin(plugin_name, force=True)
                removed.append(f"unloaded: {plugin_name}")
            except Exception as e:
                removed.append(f"⚠ failed to unload: {plugin_name} - {e}")
        try:
            cmds.pluginInfo(plugin_name, edit=True, autoload=False)
            removed.append(f"disabled autoload: {plugin_name}")
        except Exception as e:
            removed.append(f"⚠ failed to disable autoload: {plugin_name} - {e}")

    # 결과 메시지 출력
    if removed:
        message = "✔️ 다음 항목 제거/해제됨:\n\n" + "\n".join(removed)
    else:
        message = "✔️ 제거할 언노운 플러그인 또는 ngSkinTools2 없음"

    cmds.confirmDialog(title="플러그인 정리 결과", message=message, button=["OK"])




def rename_uv_sets_to_map1():
    selected_objs = cmds.ls(selection=True, dag=True, type='mesh')
    if not selected_objs:
        cmds.warning("메쉬 오브젝트를 선택해 주세요.")
        return

    for mesh in selected_objs:
        transform = cmds.listRelatives(mesh, parent=True, fullPath=True)[0]
        uv_sets = cmds.polyUVSet(transform, query=True, allUVSets=True) or []

        for uv in uv_sets:
            if uv != 'map1':
                try:
                    cmds.polyUVSet(transform, rename=True, uvSet=uv, newUVSet='map1')
                    print(f"{transform}: '{uv}' → 'map1'으로 변경됨")
                except RuntimeError as e:
                    print(f"{transform}: '{uv}' 이름 변경 실패 – {e}")

import maya.cmds as cmds
import re

def check_and_fix_duplicate_names(*args):
    all_transforms = cmds.ls(type='transform', long=True)
    short_name_map = {}
    duplicates = {}

    for full_path in all_transforms:
        short_name = full_path.split('|')[-1]
        short_name_map.setdefault(short_name, []).append(full_path)

    for name, paths in short_name_map.items():
        if len(paths) > 1:
            duplicates[name] = paths

    if not duplicates:
        cmds.confirmDialog(title="중복 없음", message="중복 이름이 없습니다.", button=["OK"])
        return

    # 중복 이름 리스트 보여주기
    dup_list = "\n".join(duplicates.keys())
    result = cmds.confirmDialog(
        title="중복 이름 발견",
        message=f"다음 이름들이 중복됩니다:\n\n{dup_list}\n\n어떻게 처리할까요?",
        button=["선택", "자동변경", "취소"],
        defaultButton="자동변경",
        cancelButton="취소",
        dismissString="취소"
    )

    if result == "선택":
        to_select = []
        for paths in duplicates.values():
            to_select.extend(paths)
        cmds.select(to_select)
        return

    elif result == "자동변경":
        for base_name, objects in duplicates.items():
            for i, obj in enumerate(objects):
                if i == 0:
                    continue  # 첫 번째는 유지
                match = re.match(r'^(.*?)(_\w+)?_geo$', base_name)
                if match:
                    prefix = match.group(1)
                    suffix = match.group(2) or ""
                    new_name = f"{prefix}{str(i+1).zfill(2)}{suffix}_geo"
                else:
                    new_name = f"{base_name}_{str(i+1).zfill(2)}"

                try:
                    renamed = cmds.rename(obj, new_name)
                    print(f"{obj} → {renamed}")
                except Exception as e:
                    print(f"⚠️ {obj} 이름 변경 실패: {e}")
        return

    else:
        return  # 취소

def on_category_changed(*args):
    update_asset_menu()
    save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))
    # print("[DEBUG] category 변경 및 상태 저장됨")

def on_asset_changed(*args):
    update_process_menu()
    save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))
    # print("[DEBUG] asset 변경 및 상태 저장됨")

def on_process_changed(*args):
    update_file_menu()
    save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))
    # print("[DEBUG] process 변경 및 상태 저장됨")

def on_file_changed(*args):
    save_maya_ldv_state(cmds.optionMenu(projectMenuName, q=True, v=True))
    # print("[DEBUG] file 변경 및 상태 저장됨")
    
def open_selected_asset_folder():
    selected_project = cmds.optionMenu(projectMenuName, query=True, value=True)
    selected_category = cmds.optionMenu(categoryMenuName, query=True, value=True)
    selected_asset = cmds.optionMenu(assetMenuName, query=True, value=True)
    selected_process = cmds.optionMenu(processMenuName, query=True, value=True)

    base_path = get_project_path(selected_project)
    
    if is_coc_project(selected_project):
        folder_path = get_asset_folder_path(selected_project, selected_category, selected_asset)
    elif selected_process == "Fin":
        folder_path = os.path.join(base_path, selected_category, selected_asset)
    else:
        folder_path = os.path.join(base_path, selected_category, selected_asset, selected_process)

    if os.path.exists(folder_path):
        os.startfile(folder_path)
    else:
        cmds.warning(f"[⚠️] 경로가 존재하지 않습니다: {folder_path}")

def deploy_rr_lookdev(*args):
    if not os.path.exists(RR_LOOKDEV_LOCAL_PATH):
        cmds.warning(f"Local rrLookdev.py does not exist: {RR_LOOKDEV_LOCAL_PATH}")
        return

    deploy_dir = os.path.dirname(RR_LOOKDEV_DEPLOY_PATH)
    if not os.path.exists(deploy_dir):
        cmds.warning(f"Deploy folder does not exist: {deploy_dir}")
        return

    try:
        shutil.copy2(RR_LOOKDEV_LOCAL_PATH, RR_LOOKDEV_DEPLOY_PATH)
        cmds.confirmDialog(
            title="Deploy Complete",
            message=f"Deployed rrLookdev.py\n\nFrom:\n{RR_LOOKDEV_LOCAL_PATH}\n\nTo:\n{RR_LOOKDEV_DEPLOY_PATH}",
            button=["OK"]
        )
    except Exception as e:
        cmds.warning(f"rrLookdev deploy failed: {e}")

def rrLookdevUI():
    global projectMenuName, categoryMenuName, assetMenuName, fileMenuName, processMenuName 
    
    window_name = "rrLookdev"

    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)

    cmds.window(window_name, title="rrLookdev", width=300, height=510)
    cmds.columnLayout(adjustableColumn=True)
    cmds.frameLayout(lv=0, w=302)
   
    #타이틀
    cmds.text(label="StoryFarm Asset Manager v1.1", align='center', height=40, enableBackground=True)
    cmds.frameLayout(lv=0, w=300, mh=5, mw=10)

    cmds.rowLayout(numberOfColumns=3, columnWidth3=[92, 92, 92], columnAlign=[(1, 'center'), (2, 'center'), (3, 'center')])
    cmds.button(label="Asset Browser", height=30, backgroundColor=[0.23, 0.23, 0.23], width=92, command=lambda *args: open_selected_asset_folder())
    cmds.button(label="Setup", height=30, backgroundColor=[0.33, 0.36, 0.42], width=92, command=open_shared_project_setup_for_lookdev)
    cmds.button(label="Deploy", height=30, backgroundColor=[0.35, 0.45, 0.35], width=92, command=deploy_rr_lookdev)
    cmds.setParent('..')
    
    cmds.columnLayout(adjustableColumn=True)  
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[50, 250], columnAlign=[(1, 'center'), (2, 'center')])
    projectMenuName = cmds.optionMenu(height=30, width=276, changeCommand=lambda x: [setProjectFromDropdown(), update_category_menu(), on_maya_dropdown_change()])
    refresh_projects_from_pipeline()
    for project_name in projects.keys():
        cmds.menuItem(label=project_name)
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[70, 135, 70], columnAlign=[(1, 'center'), (2, 'center'), (3, 'center')])
    cmds.text(label="Cat.", width=70)
    cmds.text(label="Asset", width=135)    
    cmds.text(label="Process", width=70)
    # cmds.text(label="Version", width=91)
    cmds.setParent('..')
    
    
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[70, 135, 70], columnAlign=[(1, 'center'), (2, 'center'), (3, 'center')])
    categoryMenuName = cmds.optionMenu(changeCommand=on_category_changed, height=29, width=70)
    assetMenuName = cmds.optionMenu(changeCommand=on_asset_changed, height=29, width=135)
    processMenuName = cmds.optionMenu(changeCommand=on_process_changed, height=29, width=70)
    cmds.menuItem(label="Fin")
    cmds.menuItem(label="mod")
    cmds.menuItem(label="rig")
    cmds.setParent('..')

    cmds.rowLayout(numberOfColumns=1, columnWidth1=278, columnAlign=[(1, 'center')])
    fileMenuName = cmds.optionMenu(changeCommand=on_file_changed, height=29, width=280)
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[50, 230], columnAlign=[(1, 'left'), (2, 'left')])
    cmds.text(label="변경사항 :", height=25, width=50)
    global changeDescriptionField  # 변경사항을 저장할 전역 변수
    changeDescriptionField = cmds.textField(placeholderText='여기에 변경사항을 영어로 입력하세요.', height=25, width=228)
    cmds.setParent('..')  # rowLayout 끝내기
    
    
    cmds.rowLayout(numberOfColumns=4, columnWidth4=[68, 68, 68, 68], columnAlign=[(1, 'center'), (2, 'center'), (3, 'center'), (4, 'center')])
    cmds.button(label="파일열기", command=lambda _: load_selected_asset("open"), height=20, width=68)
    cmds.button(label="레퍼런스", command=lambda _: load_selected_asset("reference"), height=20, width=68)
    cmds.button(label="+1 버전저장", command=lambda _: incremental_save(), height=20, width=68)
    cmds.button(label="퍼블리시", command=lambda _: pubAsset(), height=20, width=68)
    
    
    cmds.setParent('..')
    
    # cmds.button(label="Refresh", command=lambda x: refresh_dropdowns(), w=290, h=30)

    cmds.separator(height=20, style='in')
    # Object Checker
    cmds.text(label="Asset Checker", backgroundColor=[0.23,0.23,0.23], align='center', height=30, font='boldLabelFont', enableBackground=True)

    cmds.columnLayout(adjustableColumn=True)
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="히스토리", command=check_history_wrapper, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.button(label="다각형", command=check_and_cleanup_ngons, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..')
    

    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="넌매니폴드 매쉬", command=run_cleanup_command_for_all_meshes, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.button(label="_geo 체크", command=check_and_fix_mesh_suffix, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="프리즈 검사", command=find_non_frozen_transforms, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.button(label="네임스페이스", command=check_mesh_namespace, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="중복 이름 검사", command=check_and_fix_duplicate_names, height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.button(label="메터리얼 검사", command=lambda x: check_material_and_sg_names(), height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="중복 UV", command=lambda x: check_uv_sets(), height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.button(label="UV셋 이름을 map1 으로", command=lambda x: rename_uv_sets_to_map1(), height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..')
    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])

    if blendRename:
        cmds.button(label="페이셜 이름 검사", command=lambda x: blendRename.check_target_names_ui(), width=138, height=30, backgroundColor=[0.4, 0.4, 0.4])
        cmds.button(label="페이셜 리스트 열기", command=lambda x: blendRename.open_blend_targets(), width=138, height=30, backgroundColor=[0.4, 0.4, 0.4])
    else:
        cmds.button(label="페이셜 이름 검사 (비활성화)", enable=False, width=138, height=30)
        cmds.button(label="페이셜 리스트 열기 (비활성화)", enable=False, width=138, height=30)

    cmds.setParent('..')

    
    
    cmds.separator(height=20, style='in')
    
    # 메터리얼 리네이머
    cmds.text(label="Material Renamer", backgroundColor=[0.23,0.23,0.23], align='center', height=30, font='boldLabelFont', enableBackground=True)    
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="매쉬이름 > 메터리얼", command=lambda x: set_shading_group_name(get_materials_from_selected_objects), height=30, backgroundColor=[0.5, 0.5, 0.5], width=138)
    cmds.button(label="메터리얼이름 > SG이름", command=lambda x: set_shading_group_name(get_materials_from_selected_materials), height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..')
    cmds.separator(style='none', height=5)
    
    cmds.separator(height=20, style='in')
    cmds.text(label="Anti Virus", backgroundColor=[0.23,0.23,0.23], align='center', height=30, font='boldLabelFont', enableBackground=True)
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    cmds.button(label="언노운 플러그인", command=lambda x: remove_unknown_plugins(), height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.button(label="스크립트 에러/바이러스", command=lambda x: remove_virus_nodes(), height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    cmds.setParent('..') 
    


    cmds.separator(height=20, style='in')
    # 익스포트 USD
    cmds.text(label="Export USD", backgroundColor=[0.23,0.23,0.23], align='center', height=30, font='boldLabelFont', enableBackground=True)
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[68, 20, 68], columnAlign=[(1, 'center'), (2, 'center'), (2, 'center')])
    cmds.button(label="Auto Export USD", command=lambda x: export_usd(), height=30, backgroundColor=[0.5, 0.5, 0.5], width=110)
    cmds.button(label="Folder", command=lambda x: open_export_folder(), height=30, backgroundColor=[0.5, 0.5, 0.5], width=52)
    cmds.button(label="Manual Export USD", command=lambda x: export_usd_to_custom_folder(), height=30, backgroundColor=[0.5, 0.5, 0.5], width=110)    
    cmds.setParent('..')
    cmds.separator(style='none', height=5)
    
    cmds.separator(height=20, style='in')    
    # 텍스쳐 리로더
    # cmds.text(label="Texture Reloader", backgroundColor=[0.23,0.23,0.23], align='center', height=30, font='boldLabelFont', enableBackground=True)
    # cmds.rowLayout(numberOfColumns=3, columnWidth3=[140, 50, 50], columnAlign=[(1, 'left'), (2, 'center'), (3, 'center')])
    # cmds.text(label="Preview Texture size")
    # texture_option_menu = cmds.optionMenu(changeCommand=set_texture_max_resolution)
    # cmds.menuItem(label='256')
    # cmds.menuItem(label='512')
    # cmds.menuItem(label='1024')
    # cmds.menuItem(label='2048')
    # cmds.menuItem(label='4096')
    # cmds.optionMenu(texture_option_menu, edit=True, value=512)
    # cmds.setParent('..')
    # cmds.rowLayout(numberOfColumns=2, columnWidth2=[138, 138], columnAlign=[(1, 'center'), (2, 'center')])
    # cmds.button(label="리로드 UDIM 텍스쳐", command='import maya.mel as mel\nmel.eval("generateAllUvTilePreviews;")', height=30, backgroundColor=[0.4, 0.4, 0.4], width=138)
    # cmds.button(label="리로드 텍스쳐", command=reload_all_textures, height=30, backgroundColor=[0.5, 0.5, 0.5], width=138)
    cmds.setParent('..')
    cmds.separator(style='none', height=5)
    
    
    maya_state = load_maya_ldv_state()
    if maya_state:
        try:
            restored_project = normalize_project_selection(maya_state.get("project", ""))
            if restored_project:
                cmds.optionMenu(projectMenuName, e=True, v=restored_project)
            update_category_menu()
            cmds.optionMenu(categoryMenuName, e=True, v=maya_state.get("category", ""))
            update_asset_menu()
            cmds.optionMenu(assetMenuName, e=True, v=maya_state.get("asset", ""))
            update_process_menu()
            cmds.optionMenu(processMenuName, e=True, v=maya_state.get("process", ""))
            update_file_menu()
            cmds.optionMenu(fileMenuName, e=True, v=maya_state.get("file", ""))
        except Exception as e:
            print(f"[⚠️] Maya LookDev UI 복원 실패: {e}")


      
    cmds.showWindow()
    cmds.evalDeferred(lambda *args: update_dropdowns_from_scene_path())  # ✅ 현재 씬의 경로를 기반으로 자동 드롭다운 설정



# Maya 파일이 열릴 때 자동으로 업데이트되도록 설정
# cmds.scriptJob(event=["SceneOpened", update_dropdowns_based_on_current_file], protected=True)
rrLookdevUI()
