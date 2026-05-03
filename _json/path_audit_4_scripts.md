# Path Audit For 4 Scripts

대상 파일:
- `rrRender.py`
- `rrAnimout.py`
- `rrLookdev.py`
- `sf_blendLdv_v2.py`

목표:
- 경로 관련 요소를 전부 추출
- 공용 설정 후보와 스크립트 전용 하드코딩을 분리
- Setup / Wizard가 실제로 만지는 경로 필드를 파악

## 결론 요약

- `rrRender.py`가 현재 가장 발전된 경로 모델을 가지고 있다.
- `rrAnimout.py`는 `rrRender_project_paths.json`만 읽는 경량 버전이다.
- `rrLookdev.py`는 아직 별도 하드코딩 프로젝트 맵을 유지한다.
- `sf_blendLdv_v2.py`도 별도 하드코딩 프로젝트 맵과 드라이브 탐색 로직을 유지한다.
- 즉, 현재 4개 스크립트는 같은 프로젝트를 다루지만 "경로의 진실"이 한 군데에 있지 않다.

## 1. rrRender.py

### 1-1. 설정 파일 경로

- 공용 설정 저장 폴더 하드코딩:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:32)
  `PROJECT_SETTINGS_DIR = r"M:\RND\SFtools\2023\render\_json"`
- 로컬 개발용 json 폴더:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:36)
  `HWANG_LOCAL_PROJECT_SETTINGS_SOURCE_DIR = r"C:\Users\hwang\Desktop\codex\rrRender\_json"`
- 런타임 dev json 폴더:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:37)
  `HWANG_RUNTIME_PROJECT_SETTINGS_DIR = r"C:\_json\rrRender_dev"`
- 실제 파일명:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:33)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:34)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:35)

### 1-2. 프로젝트 기본 경로 하드코딩

- 표준 프로젝트 기본값:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:39)
- 포함 프로젝트:
  `THE_TRAP`, `ARBOBION`, `DSC`, `BTS`, `FUZZ`, `COC`
- 하드코딩 필드:
  `drive`, `asset_base`, `scene_base`, `project_json_base`, `output_base`, `cache_base`, `asset_*_dir`, `scene_root_dir`, `ren_dir`, `cache_dir`, `publish_dir`
- COC 특수값:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:115)
  `drive = S:/PROJECT/COC/02_Production`
  `project_json_base = C:/_json`
  `output_base = S:/PROJECT/COC/02_Production/output`
  `cache_base = S:/PROJECT/COC/02_Production/Rendering`
  `scene_root_dir = Animation/Detail`
  `ren_dir = maya`
  `scene_identifier_mode = filename`

### 1-3. schema 생성 시 파생되는 경로

- scene root 생성:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:229)
- render preset / render setting json 경로 생성:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:244)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:245)
- asset category root 생성:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:285)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:294)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:303)
- output root template 생성:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:325)

주의:
- `output_base`가 이미 `T:/output` 같은 값인데 schema 기본 생성은 다시 `"output"`을 붙이는 코드라 drift 위험이 있다.

### 1-4. 경로 해석 함수

- 설정 파일 위치:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:347)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:351)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:355)
- 프로젝트 경로 해석:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:764)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:773)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:784)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:793)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:847)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:854)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:858)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:862)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:866)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1231)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1241)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1255)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1270)

### 1-5. 상태 저장 경로

- 최근 브라우저 상태 폴더 하드코딩:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1297)
  `RECENT_BROWSER_STATE_DIR = r"C:\_json"`
- 상태 파일명:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1298)
- 관련 함수:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1301)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1317)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1348)

### 1-6. 배포/개발 하드코딩 경로

- 배포 스크립트 경로:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1458)
- 배포 백업 경로:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1459)
- 로컬 개발 스크립트 경로:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1461)

### 1-7. Setup / Wizard가 만지는 경로

- Setup popup:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1948)
- Setup UI에서 직접 수정 가능한 필드:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1972)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1974)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1975)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1976)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1977)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1982)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1983)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1984)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1989)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1990)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1991)
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:1992)
- 경로 picker:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2040)
- New Project Wizard:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2047)
- Wizard 입력:
  `project_name`, `prefix`, `publish_file`, `scene_file`, `geometry_root_hint`
- UI 로딩:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2309)
- UI 저장:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2337)
- 저장 operator:
  [rrRender.py](C:/Users/hwang/Desktop/codex/rrRender/rrRender.py:2472)

정리:
- `rrRender`는 이미 “공용 Setup Editor”가 될 수 있는 가장 가까운 형태다.

## 2. rrAnimout.py

### 2-1. 설정/배포 하드코딩 경로

- pipeline import 경로:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:30)
  `ppPath = 'M:/RND/SFtools/2023/pipeline/'`
- 설정 json 폴더:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:32)
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:34)
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:35)
- 배포 스크립트 경로:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:36)
- 배포 백업 경로:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:37)
- 로컬 개발 경로:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:38)

### 2-2. 프로젝트 기본 경로 하드코딩

- 프로젝트 기본값 테이블:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:54)
- 포함 프로젝트:
  `THE_TRAP`, `ARBOBION`, `BTS`, `CKR`, `DSC`, `FUZZ`, `COC`
- `CKR`는 rrRender sample 쪽에는 없지만 Animout/Lookdev 계열에는 남아있다.

### 2-3. 상태 저장 경로

- 애님아웃 브라우저 상태:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:104)
  `~/_json/animOut_state_maya.json`
- 상태 save/load:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:106)
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:127)

### 2-4. 경로 해석 함수

- 설정 파일 경로:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:287)
- scene root:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:346)
- scene work path:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:359)
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:409)
- COC cut folder:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:426)
- cache dir:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:462)

### 2-5. Setup가 만지는 범위

- 실제 Setup 적용 함수:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:3134)
- Setup popup:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:3151)
- UI 버튼:
  [rrAnimout.py](C:/Users/hwang/Desktop/codex/rrRender/rrAnimout.py:3842)

정리:
- `rrAnimout`의 Setup은 현재 “경로 편집기”가 아니라 “json 재동기화 + 메뉴 리프레시”에 가깝다.
- 즉, 공용 setup 체계로 가려면 `rrRender` 스타일 editor를 불러오거나 같은 필드를 재사용해야 한다.

## 3. rrLookdev.py

### 3-1. 프로젝트 루트 하드코딩

- 프로젝트 맵:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:23)
- 포함 프로젝트:
  `BTS`, `THE_TRAP`, `ARBO_BION`, `CKR`, `DSC`, `FUZZ`, `COC`
- 문제점:
  `ARBO_BION` 표기만 있고 `ARBOBION` 표준 alias 체계가 따로 없다.

### 3-2. 배포/개발 경로

- 로컬 스크립트 경로:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:35)
- 배포 스크립트 경로:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:36)
- pipeline import 경로:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:177)

### 3-3. 상태 저장 경로

- Maya UI state:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:45)
  `~/_json/ldv_browser_state_maya.json`
- save/load:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:149)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:163)

### 3-4. 경로 생성 규칙

- asset root:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:55)
- asset folder:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:61)
- asset file:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:69)
- scene export info:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:83)
- parse current scene path:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:793)

### 3-5. 강한 하드코딩 포인트

- publish final 경로를 직접 박아둔 코드:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:903)
  `A:/assets/ch`
- COC/export/usd 관련 경로 조합:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:92)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:101)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:450)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:452)

### 3-6. Setup/UI 성격

- 별도 Setup 버튼은 없음
- project/category/asset/process/file를 직접 optionMenu로 관리:
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:1820)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:1843)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:1857)
  [rrLookdev.py](C:/Users/hwang/Desktop/codex/rrRender/rrLookdev.py:1866)

정리:
- `rrLookdev`는 공용 config를 아직 전혀 읽지 않는 독립형 구조다.

## 4. sf_blendLdv_v2.py

### 4-1. 드라이브/상태/프로젝트 하드코딩

- 우선 드라이브:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:37)
  `PREFERRED_DRIVES = ["M:/", "S:/"]`
- 상태 파일:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:39)
  `%USERPROFILE%/Documents/_json/ldv_browser_state.json`
- 프로젝트 맵:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:43)
- 포함 프로젝트:
  `BTS`, `Trap`, `DSC`, `FUZZ`, `COC`
- 문제점:
  `Trap` 표기가 `THE_TRAP`과 다르고, 표시 이름/접두사도 따로 관리된다.

### 4-2. 배포/개발 하드코딩 경로

- 배포 스크립트:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:60)
- 백업 폴더:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:61)
- 로컬 개발 경로:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:63)

### 4-3. 경로 해석 함수

- 활성 드라이브 탐색:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:232)
- 드라이브 기반 상대경로 해석:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:238)
- 프로젝트 path type 해석:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:245)
- script/preset/cache 해석:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:256)
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:259)
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:262)

주의:
- 이 파일은 `project path`와 별개로 `script asset path`를 `M:/RND/SFtools/2025/lookdev/...` 또는 `S:/assets/scripts/...`에서 찾는다.
- 즉, 프로젝트 config만 공용화해도 리소스 경로는 따로 남는다.

### 4-4. 하드코딩 리소스 경로

- lookdev blend/json resource:
  `ldvLight_v03.blend`, `ldvLight_cycle.blend`, `SF_Paint.blend`, `MI_Paint.json`
  여러 곳에서 `resolve_script_path("blend", ...)` 사용
- OSL 하드코딩:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:3325)
  `M:\RND\SFtools\2025\lookdev\blend\CNPRK_EasyToon.osl`
- backup export 경로:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:894)
  `U:/coc`
- prefix 기반 backup 경로:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:897)
  `U:/{prefix}/assets`

### 4-5. 상태 저장/캐시 경로

- 브라우저 상태 생성/읽기/쓰기:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:265)
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:277)
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:284)
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:289)
- cache root:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:274)
- asset list cache:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:395)

### 4-6. Setup/UI 성격

- 별도 Setup 버튼 없음
- Deploy 버튼만 있음:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:5628)
- 프로젝트/카테고리/어셋 상태를 자체 브라우저 state로 복원:
  [sf_blendLdv_v2.py](C:/Users/hwang/Desktop/codex/rrRender/sf_blendLdv_v2.py:2091)

정리:
- `sf_blendLdv_v2`는 프로젝트 경로와 리소스 경로가 혼합되어 있다.

## 5. 하드코딩 드라이브 / 루트 목록

발견된 하드코딩 루트:
- `M:\RND\SFtools\2023\render\_json`
- `M:\RND\SFtools\2023\render\rrRender.py`
- `M:\RND\SFtools\2023\render\rrAnimout.py`
- `M:\RND\SFtools\2023\render\_t`
- `M:\RND\SFtools\2023\lookDev\rrLookdev.py`
- `M:\RND\SFtools\2023\pipeline\`
- `M:\RND\SFtools\2025\lookdev\sf_blendLdv_v2.py`
- `M:\RND\SFtools\2025\lookdev\_t`
- `M:\RND\SFtools\2025\lookdev\blend\CNPRK_EasyToon.osl`
- `C:\Users\hwang\Desktop\codex\rrRender\_json`
- `C:\Users\hwang\Desktop\codex\rrRender\rrRender.py`
- `C:\Users\hwang\Desktop\codex\rrRender\rrAnimout.py`
- `C:\Users\hwang\Desktop\codex\rrRender\rrLookdev.py`
- `C:\Users\hwang\Desktop\codex\rrRender\sf_blendLdv_v2.py`
- `C:\_json`
- `C:\_json\rrRender_dev`
- `T:/`
- `A:/`
- `B:/`
- `S:/`
- `Z:/`
- `K:/`
- `U:/coc`
- `U:/{prefix}/assets`
- `S:/PROJECT/COC/02_Production`
- `S:/PROJECT/COC/02_Production/CHSetup/controller`
- `S:/PROJECT/COC/02_Production/Rendering`
- `S:/PROJECT/COC/02_Production/output`

## 6. 공용 설정 후보

공용 `pipeline_config`로 끌어올리기 좋은 항목:
- project id / prefix
- drive / asset_root / scene_root / json_root / output_root
- asset category roots
- scene browser level 구조
- work dir 목록
- cache root mode / file template
- scene identifier mode
- geometry root hint
- render preset / render setting json 위치
- DCC별 scene extension

## 7. 스크립트 전용으로 남겨야 할 가능성이 큰 항목

- 배포 스크립트 경로
- 배포 백업 폴더
- local dev path
- browser state save path
- tool-specific cache root
- lookdev 리소스 경로 (`ldvLight_v03.blend`, `SF_Paint.blend`, OSL 등)
- pipeline module import 경로 (`M:/RND/SFtools/.../pipeline/`)

## 8. Setup / Wizard 통합 관점

현재 상태:
- `rrRender`만 실질적인 경로 편집 UI가 있다.
- `rrAnimout` Setup은 편집이 아니라 json 동기화/새로고침이다.
- `rrLookdev`와 `sf_blendLdv_v2`는 Setup이 아니라 독립 project selector에 가깝다.

통합 목표:
- 모든 스크립트의 Setup 버튼은 같은 `pipeline_config`를 수정
- Wizard도 새 프로젝트를 같은 `pipeline_config`에 추가
- 각 스크립트는 경로 자체를 소유하지 않고 "공용 설정을 읽는 소비자"가 됨

## 9. 바로 다음 정리 후보

우선순위 추천:
1. 프로젝트 명칭 alias 통합
2. 표준 프로젝트 5개 경로 템플릿화
3. COC 전용 profile 분리
4. Lookdev 리소스 경로와 프로젝트 경로 분리
5. state 파일 저장 위치 공통 정책 수립
