# Functional Path Requirements

목적:
- 경로를 통합할 때 반드시 살아 있어야 하는 기능을 정리한다.
- 단순히 `path value`를 옮기는 것이 아니라, 각 툴이 그 경로를 어떻게 사용하고 있는지까지 본다.

원칙:
- 공용 설정은 `pipeline_config.json`으로 모은다.
- 하지만 기능을 살리는 책임은 `config + tool refresh behavior` 둘 다에 있다.

## 1. rrRender.py 에서 반드시 살아야 하는 기능

### 1-1. 프로젝트 설정 로드/병합

관련 함수:
- [ensure_project_config_loaded](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:714)
- [ensure_project_schema_loaded](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:378)

살아야 하는 동작:
- 프로젝트 기본값을 읽는다.
- 저장된 json이 있으면 기본값 위에 덮어쓴다.
- schema가 없는 프로젝트는 기본 schema를 자동 생성한다.

의미:
- 공용 config로 가더라도 “프로젝트가 하나 빠졌을 때 최소 기본값으로 열리는 동작”이 필요하다.

### 1-2. Setup Editor 로드/저장

관련 함수:
- [load_project_path_settings_to_ui](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2426)
- [save_project_path_settings_from_ui](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2454)

살아야 하는 동작:
- 현재 프로젝트 선택 시 UI 필드에 값이 채워짐
- 수정 후 저장하면 프로젝트 경로 규칙이 다시 계산됨
- `scene_root_dir`처럼 전체 경로로 넣어도 `scene_base + scene_root_dir`로 재분해됨

의미:
- 공용 Setup App에서도 단순 key-value 편집기가 아니라 “경로 재분해/정규화” 로직이 필요하다.

### 1-3. scene browser 자동 동기화

관련 함수:
- [sync_browser_to_filepath](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1842)

살아야 하는 동작:
- 현재 파일 경로를 보고 프로젝트를 추론한다.
- scene/cut/work 혹은 확장 browser level 값을 역으로 복원한다.
- 프로젝트 전환까지 같이 수행될 수 있다.

의미:
- 공용 config가 바뀌면 rrRender는 단순 reload가 아니라 browser state 재동기화가 필요하다.

### 1-4. cache 경로 해석

관련 함수:
- [resolve_cache_context](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:889)
- [get_usd_path](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:6953)

살아야 하는 동작:
- 현재 scene 파일의 실제 위치를 우선으로 sibling cache를 찾는다.
- filename 기반 프로젝트는 `cache_base` fallback도 사용한다.
- USD 파일명은 `prefix + scene_token + cut_token + category + asset_name` 규칙으로 생성된다.

의미:
- `cache_root` 하나만 넣어서는 부족하고, `cache resolution strategy`까지 공용 모델에 들어가야 한다.

### 1-5. render settings / preset 경로 찾기

관련 함수:
- [get_project_json_path](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1318)
- [get_project_output_path](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1333)
- [load_project_render_settings](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:3254)
- [get_render_preset_json_path](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:11390)

살아야 하는 동작:
- 프로젝트별 render setting/preset json 위치를 정확히 찾는다.
- output path는 schema template를 우선 사용하고, 없으면 fallback 조합을 사용한다.

의미:
- 공용 config에는 `render_setting_json`, `render_preset_json`, `output template`가 반드시 있어야 한다.

## 2. rrAnimout.py 에서 반드시 살아야 하는 기능

### 2-1. Maya scene browser 경로 해석

관련 함수:
- [get_scene_root_path](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:346)
- [get_current_file_work_path_for_scene](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:359)
- [find_filename_scene_work_path](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:385)
- [get_scene_work_path](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:409)

살아야 하는 동작:
- 폴더 기반 프로젝트는 `scene/ cut / work` 경로로 브라우징한다.
- filename 기반 프로젝트는 실제 파일명에서 scene/cut를 파싱해서 work path를 찾는다.
- 현재 열려 있는 파일이 있으면 그 파일의 폴더를 우선 사용한다.

의미:
- 공용 config에 `identifier_source = folder_depth or filename`만 넣는 것으로 끝나지 않고, Maya 쪽 work path 우선순위도 반영해야 한다.

### 2-2. COC 특수 cache / cut folder 로직

관련 함수:
- [get_coc_cut_folder_path](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:426)
- [get_cache_dir_path](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:462)

살아야 하는 동작:
- COC는 일반 프로젝트처럼 `scene/cut/work/cache`로만 가지 않는다.
- 현재 파일과 episode 정보를 기반으로 cut folder를 역산한다.
- 거기서 cache 경로를 만든다.

의미:
- COC는 profile 분리 없이 일반 프로젝트 규칙으로 합치면 바로 깨진다.

### 2-3. Setup 버튼이 실제로 하는 일

관련 함수:
- [animout_setup_project_settings](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:3134)
- [show_animout_setup_popup](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:3151)

살아야 하는 동작:
- json sync
- config reload
- project menu refill
- scene browser refresh

의미:
- 공용 Setup App 이후에도 Animout는 “설정 편집”이 아니라 “설정 반영” 후처리 버튼이 필요하다.

### 2-4. publish 경로 재지정

관련 함수:
- [set_selected_as_published](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:3734)

살아야 하는 동작:
- 선택한 참조 어셋을 프로젝트 publish root 기반 `.mb` 파일로 갈아끼운다.

의미:
- asset category root가 공용 config에서 정확해야 한다.

## 3. rrLookdev.py 에서 반드시 살아야 하는 기능

### 3-1. 프로젝트/카테고리/프로세스 기반 asset path 구성

관련 함수:
- [get_assets_root](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:55)
- [get_asset_folder_path](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:61)
- [get_asset_file_path](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:69)

살아야 하는 동작:
- 일반 프로젝트는 `assets/category/asset/[process]`
- COC는 `controller/asset/...`
- `Fin`이면 process 없이 final file을 찾음

의미:
- Lookdev는 project root만 알면 되는 게 아니라 `Fin/mod/rig` 같은 process semantics도 유지해야 한다.

### 3-2. 현재 scene 경로를 역으로 파싱해서 UI 복원

관련 함수:
- [parse_scene_path](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:793)
- [update_dropdowns_from_scene_path](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:830)

살아야 하는 동작:
- 현재 파일 경로를 보고 project/category/asset/process/version을 추론한다.
- UI optionMenu를 자동으로 복원한다.

의미:
- 공용 config 전환 후에도 Lookdev는 scene path reverse parsing 로직이 반드시 살아야 한다.

### 3-3. UI 메뉴 갱신

관련 함수:
- [update_category_menu](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:927)
- [update_asset_menu](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:946)
- [update_process_menu](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:977)
- [update_file_menu](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:1005)

살아야 하는 동작:
- project가 바뀌면 category/asset/process/file 드롭다운이 실제 경로 기준으로 즉시 갱신된다.
- Fin 파일 존재 여부에 따라 기본 process가 달라진다.

의미:
- 공용 Setup App 이후에도 Lookdev는 reload 이후 menu repopulate가 필요하다.

### 3-4. export / publish 경로

관련 함수:
- [get_scene_export_info](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:83)
- [export_usd](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:257)
- [export_usd_to_custom_folder](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:668)
- [publish](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:897)

살아야 하는 동작:
- 현재 씬 기준 export final dir를 계산한다.
- custom folder export도 가능하다.
- publish는 현재 심각한 하드코딩 `A:/assets/ch`가 남아 있다.

의미:
- publish 경로 규칙도 공용 config로 올릴 대상이다.

## 4. sf_blendLdv_v2.py 에서 반드시 살아야 하는 기능

### 4-1. 프로젝트 경로와 리소스 경로 분리

관련 함수:
- [resolve_project_path](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:245)
- [resolve_script_path](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:256)
- [resolve_cache_path](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:262)

살아야 하는 동작:
- 프로젝트 자산 경로와
- lookdev 도구 리소스 경로가
- 서로 다른 규칙으로 해석된다.

의미:
- 공용 config 하나로 모든 걸 커버하려면 `project paths`와 `tool resource paths`를 분리 저장해야 한다.

### 4-2. Blender 파일 경로 기반 project root / prefix 추론

관련 함수:
- [get_project_path](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:1283)
- [get_project_prefix](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:1309)

살아야 하는 동작:
- 현재 저장된 블렌더 파일 경로에서 project root와 prefix를 추론한다.
- COC는 별도 root/prefix를 사용한다.

의미:
- prefix와 project alias의 표준화가 중요하다.

### 4-3. scene asset mod path / json texture path

관련 함수:
- [get_scene_asset_mod_dir](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:333)
- [apply_textures_from_json_ch](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:3802)
- [apply_textures_from_json](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:3916)

살아야 하는 동작:
- asset mod dir 아래 `usd/{asset}.json`을 찾는다.
- 그 json 기반으로 재질/텍스처를 재적용한다.

의미:
- asset publish/layout 경로 규칙이 바뀌면 LookDev Blender 툴도 같이 깨진다.

### 4-4. COC render output 경로

관련 함수:
- [get_coc_render_output_dir](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:340)

살아야 하는 동작:
- `sheet/render/v###` 경로를 만들고 다음 버전을 올린다.

의미:
- output template는 프로젝트 공통이지만, 일부 툴 전용 output subpath가 추가로 필요하다.

### 4-5. asset cache 생성

관련 함수:
- [update_asset_list_cache](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:5300)

살아야 하는 동작:
- 프로젝트별 asset root를 스캔한다.
- COC는 `mod/usd`가 있는 asset만 유효하다고 본다.

의미:
- asset discovery rule도 프로젝트 profile에 따라 달라진다.

## 5. 공용 Setup App만으로는 부족한 것

Setup App이 해줄 수 있는 것:
- 프로젝트 추가/수정
- 공용 config 저장
- 경로 검증

Setup App만으로 부족한 것:
- rrRender browser sync
- rrAnimout 메뉴/씬 리프레시
- rrLookdev optionMenu repopulate
- sf_blendLdv_v2 asset cache 재생성
- 각 툴의 state reload

결론:
- `Setup App = 설정 편집기`
- `각 툴 Setup 버튼 = 편집기 호출 + 저장 후 refresh`

## 6. 앞으로 공용 config에 들어가야 하는 것

필수:
- project aliases
- canonical project list
- paths: project_root / asset_root / scene_root / json_root / output_root / cache_root
- asset categories
- scene browser levels
- scene identifier mode
- cache resolution mode
- output template
- render preset / render setting json path
- dcc scene extensions

강력 추천:
- project profiles: `standard`, `character_only`, `maya_filename`
- tool resource paths
- tool refresh requirements
- asset discovery rules
- publish path rules

## 7. 바로 다음에 검증할 것

우선순위:
1. `pipeline_config.json`에 `tool_paths` 섹션 추가
2. `pipeline_config.json`에 `profiles` 섹션 추가
3. `COC`, `CKR`, standard 프로젝트를 profile로 분리
4. 각 툴별 refresh checklist를 json 또는 spec으로 연결
