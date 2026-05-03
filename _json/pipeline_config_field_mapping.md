# Pipeline Config Field Mapping

기존 파일은 유지하고, 나중에 공용 설정 파일 `pipeline_config.json`을 추가할 때 참고하는 매핑표다.

대상 기존 파일:
- `rrRender_project_paths.json`
- `rrRender_project_schema.json`
- `rrRender_project_overrides.json`

기본 원칙:
- 삭제/대체가 아니라 "공용 읽기 모델"을 먼저 정의한다.
- 값이 겹치면 우선순위는 `schema > paths > overrides`.
- `overrides`는 기본값 소스가 아니라 예외/수동 보정 저장소로 본다.

## Proposed Target Shape

```json
{
  "version": 1,
  "projects": {
    "BTS": {
      "identity": {},
      "paths": {},
      "scene_browser": {},
      "scene_structure": {},
      "scene_filename_rules": {},
      "assets": {},
      "cache": {},
      "output": {},
      "dcc": {},
      "overrides": {}
    }
  }
}
```

## Top-Level Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `version` | new file value | none | 새 공용 파일 버전 |
| `projects.<project_key>` | all 3 files merged by project key | none | 프로젝트 키는 기존과 동일 유지 |
| `projects.<project_key>.identity.project_id` | `schema.project_id` | project key | 보통 project key와 동일 |
| `projects.<project_key>.identity.project_prefix` | `schema.project_prefix` | `paths.prefix` | prefix는 공통 키값으로 유지 |

## Paths Mapping

| Target field | Primary source | Fallback source | Example |
| --- | --- | --- | --- |
| `paths.project_root` | `schema.paths.project_root` | `paths.drive` | `B:/` |
| `paths.asset_root` | derive from asset categories if same root | `paths.asset_base` | `B:/assets` |
| `paths.scene_root` | first browser root or derived scene root | `paths.scene_base + paths.scene_root_dir` | `B:/scenes` |
| `paths.json_root` | `schema.paths.project_json_root` | `paths.project_json_base` | `B:/` or `C:/_json` |
| `paths.output_root` | `schema.paths.output_root` | `paths.output_base` | `B:/output` |
| `paths.render_preset_json` | `schema.paths.render_preset_json` | derive from `json_root` | `B:/_json/renderPreset.json` |
| `paths.render_setting_json` | `schema.paths.render_setting_json` | derive from `json_root` | `B:/_json/renderSetting.json` |

## Scene Browser Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `scene_browser.levels` | `schema.scene_browser.levels` | build from `paths.scene_root_dir`, `paths.ren_dir` | schema 값을 그대로 우선 사용 |
| `scene_browser.file_level_id` | `schema.scene_browser.file_level_id` | `"work"` | |
| `scene_browser.file_extensions` | `schema.scene_browser.file_extensions` | infer by DCC | Blender는 `.blend`, Maya는 `.ma`, `.mb` |

## Scene Structure Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `scene_structure.identifier_source` | `schema.scene_structure.identifier_source` | `paths.scene_identifier_mode` mapped | `folder_depth` or `filename` |
| `scene_structure.scene_level_id` | `schema.scene_structure.scene_level_id` | `"scene"` | COC는 `episode` 가능 |
| `scene_structure.cut_level_id` | `schema.scene_structure.cut_level_id` | `"cut"` or `null` | |
| `scene_structure.work_level_id` | `schema.scene_structure.work_level_id` | `"work"` | |
| `scene_structure.cache_path_mode` | `schema.scene_structure.cache_path_mode` | `"relative_to_work"` | |
| `scene_structure.cache_relative_path` | `schema.scene_structure.cache_relative_path` | `paths.cache_dir` | |

## Scene Filename Rules Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `scene_filename_rules.scene_token_pattern` | `schema.scene_filename_rules.scene_token_pattern` | none | COC 같은 filename 프로젝트용 |
| `scene_filename_rules.cut_token_pattern` | `schema.scene_filename_rules.cut_token_pattern` | none | |
| `scene_filename_rules.version_pattern` | `schema.scene_filename_rules.version_pattern` | none | |
| `scene_filename_rules.example` | `schema.scene_filename_rules.example` | none | |

## Assets Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `assets.categories` | `schema.assets.categories` | build from `paths.asset_*_dir` | 공통 파일에서도 category list 유지 |
| `assets.asset_id_rules` | `schema.assets.asset_id_rules` | default template | 현재는 schema 쪽이 더 완전함 |
| `assets.categories[].id` | `schema.assets.categories[].id` | derived category key | `ch`, `bg`, `prop`, `character` |
| `assets.categories[].label` | `schema.assets.categories[].label` | category id | |
| `assets.categories[].root_path` | `schema.assets.categories[].root_path` | `paths.asset_base + category_dir` | |
| `assets.categories[].publish_file_mode` | `schema.assets.categories[].publish_file_mode` | default by DCC | |
| `assets.categories[].publish_file_template` | `schema.assets.categories[].publish_file_template` | default template | |
| `assets.categories[].asset_id_source` | `schema.assets.categories[].asset_id_source` | `"folder_name"` | |
| `assets.categories[].geometry_root_hint` | `schema.assets.categories[].geometry_root_hint` | `paths.geometry_root_hint` | |

## Cache Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `cache.root_mode` | `schema.cache.root_mode` | derive from project type | |
| `cache.root_template` | `schema.cache.root_template` | `"{work_path}/" + paths.cache_dir` | |
| `cache.file_template` | `schema.cache.file_template` | default template | |
| `cache.match_mode` | `schema.cache.match_mode` | `"by_asset_id_and_category"` | |
| `cache.extensions` | `schema.cache.extensions` | DCC-specific default | |

## Output Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `output.root_template` | `schema.output.root_template` | build from `paths.output_base` and work dir | |
| `output.version_folder_mode` | `schema.output.version_folder_mode` | `"v###"` | |
| `output.default_version_digits` | `schema.output.default_version_digits` | infer from project | 표준 3자리, COC 2자리 |
| `output.file_slot_prefix_template` | `schema.output.file_slot_prefix_template` | default template | |

## DCC Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `dcc.default` | infer from browser file extensions | infer from project profile | `blender` / `maya` |
| `dcc.blender.scene_extensions` | derived | none | `.blend` |
| `dcc.maya.scene_extensions` | derived | none | `.ma`, `.mb` |
| `dcc.<name>.work_dirs` | derive from `scene_browser.levels[].fixed_options` | `paths.ren_dir` | |

## Overrides Mapping

| Target field | Primary source | Fallback source | Notes |
| --- | --- | --- | --- |
| `overrides.asset_registry` | `overrides.asset_registry` | `[]` | 현재 override 파일 값을 그대로 유지 |
| `overrides.cache_overrides` | `overrides.cache_overrides` | `[]` | |
| `overrides.rrRender` | future script-specific section | none | 새 공용 파일에서 추가 가능 |
| `overrides.rrAnimout` | future script-specific section | none | |
| `overrides.rrLookdev` | future script-specific section | none | |
| `overrides.sf_blendLdv_v2` | future script-specific section | none | |

## Existing `paths` File Fields

`rrRender_project_paths.json` 기준 직접 매핑:

| Existing field | Proposed target field | Notes |
| --- | --- | --- |
| `drive` | `paths.project_root` | |
| `prefix` | `identity.project_prefix` | |
| `asset_base` | `paths.asset_root` | |
| `scene_base` | base for `paths.scene_root` | `scene_root_dir`와 합성 필요 |
| `project_json_base` | `paths.json_root` | |
| `output_base` | `paths.output_root` | |
| `asset_ch_dir` | `assets.categories[ch].root_path` input | |
| `asset_bg_dir` | `assets.categories[bg].root_path` input | |
| `asset_prop_dir` | `assets.categories[prop].root_path` input | |
| `scene_root_dir` | `paths.scene_root` input | |
| `ren_dir` | `dcc.<name>.work_dirs[0]` or browser work default | |
| `cache_dir` | `scene_structure.cache_relative_path` and cache fallback | |
| `publish_dir` | asset publish/path convention hint | 아직 공용 필드 분리 후보 |
| `scene_identifier_mode` | `scene_structure.identifier_source` mapped | `filename` / folder-based |
| `geometry_root_hint` | `assets.categories[].geometry_root_hint` fallback | |

## Existing `schema` File Fields

`rrRender_project_schema.json` 기준 직접 매핑:

| Existing field | Proposed target field | Notes |
| --- | --- | --- |
| `project_id` | `identity.project_id` | |
| `project_prefix` | `identity.project_prefix` | |
| `paths.*` | `paths.*` | 거의 1:1 |
| `scene_browser.*` | `scene_browser.*` | 거의 1:1 |
| `scene_structure.*` | `scene_structure.*` | 거의 1:1 |
| `scene_filename_rules.*` | `scene_filename_rules.*` | filename 프로젝트용 |
| `assets.*` | `assets.*` | 거의 1:1 |
| `cache.*` | `cache.*` | 거의 1:1 |
| `output.*` | `output.*` | 거의 1:1 |
| `browser_sync.*` | `dcc.blender.browser_sync` or common sync section | 별도 섹션 후보 |

## Existing `overrides` File Fields

`rrRender_project_overrides.json` 기준 직접 매핑:

| Existing field | Proposed target field | Notes |
| --- | --- | --- |
| `asset_registry` | `overrides.asset_registry` | |
| `cache_overrides` | `overrides.cache_overrides` | |

## Merge Priority

프로젝트별 병합 순서 제안:

1. 기본 베이스는 `rrRender_project_paths.json`
2. 구조/규칙은 `rrRender_project_schema.json`으로 덮어씀
3. 예외값은 `rrRender_project_overrides.json`을 `overrides` 하위에 병합
4. 스크립트별 임시 설정은 앞으로 `overrides.<script_name>`로 확장

## Notes

- 표준 프로젝트(`THE_TRAP`, `ARBOBION`, `DSC`, `BTS`, `FUZZ`)는 거의 템플릿화 가능하다.
- `COC`는 filename 기반 프로젝트라 별도 profile처럼 다루는 것이 안전하다.
- `browser_sync`는 아직 `rrRender` 성격이 강해서, 공용 파일로 갈 때는 `common` 섹션 또는 `dcc.blender` 하위로 내리는 것이 좋아 보인다.
- `publish_dir`는 현재 schema 쪽에 명확한 대응 필드가 약하므로, 추후 `publish` 섹션 신설 후보다.
