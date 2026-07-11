# Project History

## 2026-07-11 — Initial Architecture Review & TODO Setup

### Changes
- **Repository analysis**: 전체 코드베이스 아키텍처 파악 완료
- **TODO.md 생성**: 프로젝트 목표와 진행 상황을 추적할 todolist 작성
- **history.md 생성**: 본 파일 — 프로젝트 변경 이력 추적 시작

### Known Issues
1. `power_grid_tda.py` line ~440: `set_faceplot` → `set_facecolor` 오타 (matplotlib)
2. 테스트 코드 없음
3. KCL 기반 거리 함수 미구현

---

## 2026-07-11 — Bug Fixes, Tests, and KCL Extensibility

### Changes
1. **matplotlib 버그 수정**: `power_grid_tda.py`의 `set_faceplot` → `set_facecolor` 오타 수정
2. **Unit tests 구현 (51개 모두 통과)**: PTDF, VR, Metrics 테스트
3. **KCLCurrentDistance 구현**: `metrics.py`에 KCL 기반 전류 거리 메트릭 추가
4. **pyproject.toml 생성**: pip install -e . 지원
5. **README.md 업데이트**: 테스트 실행 방법, 프로젝트 관리 섹션 추가
6. **불필요 import 제거**: `metrics.py`에서 사용되지 않는 `Optional` import 제거

### Test Results
```
51 passed in 0.19s
```

---

## 2026-07-11 — Ukraine Loader, Vulnerability Engine, Bug Fixes

### Changes
1. **`power_grid_tda.py` 추가 버그 수정**: set_faceplot 제거, 중복 라인 정리
2. **우크라이나 전력망 데이터 로더 생성** (`power_grid/ukraine_loader.py`)
3. **취약점 탐지 엔진 생성** (`tda/vulnerability.py`)
4. **`requirements.txt` 생성**

### Test Results
```
51 passed in 0.23s
```

---

## 2026-07-11 14:30 — Critical Bug Fix: _vulnerability_analysis 메서드 승격

### Changes
1. **`graph_editor.py` 클래스 메서드 승격**: 로컬 함수 → 클래스 메서드 (7개 메서드)
2. **`unsolved issues.txt` 업데이트**

### Test Results
```
51 passed in 0.23s
```

---

## 2026-07-11 — VR Complex H1 Cycle Death Bug Fix

### Changes
1. **`tda/vr_core.py` persistence_pairs() 버그 수정**: break 제거, youngest edge rule 개선

### Test Results
```
51 passed in 0.09s
```

---

## 2026-07-11 21:30 — Vulnerability Analysis 완전 재통합 & 들여쓰기 오류 최종 수정

### Changes
1. **`integration/power_grid_tda.py` 완전 재작성**:
   - `_vulnerability_analysis()`, `_show_vulnerability_window()`, `_color_vr_nodes_by_vulnerability()` 3개 메서드 클래스에 정식 추가
   - `⚠ 취약점 분석` 버튼 안정적으로 추가 (Animate, Compare 버튼 옆)
   - 모든 들여쓰기 8-space로 통일, SyntaxError 완전 해결
   - `tda.vulnerability` import 정상화

2. **테스트 확인**: 51개 테스트 전부 통과 ✅

3. **`unsolved issues.txt` 업데이트**: IndentationError 해결 표기

### Test Results
```
51 passed in 0.08s
```

---

## 2026-07-11 16:30 — Bus LODF Sensitivity 근본적 재설계: PTDF-weighted Signed LODF

### Changes
1. **`compute_bus_lodf_sensitivity()` 완전 재작성** (`electrical_distance/ptdf_calculator.py`)

### Test Results
```
51 passed in 0.11s
```

---

## 2026-07-11 17:30 — git 복원 및 문서 정리

### 상황
- 이전 작업에서 `graph_editor.py`의 `_import_power_grid` 메서드에 우크라이나 섹션(18-Bus, 28-Bus)을 추가하는 과정에서 들여쓰기 오류 발생
- `insert` 도구가 앞 공백을 유지하지 않아 첫 줄이 0-space로 삽입되어 SyntaxError 발생
- 중복 삽입 문제로 파일이 깨져 `git checkout`으로 복원
- 현재 `graph_editor.py`는 git 버전(우크라이나 버튼 없음)으로 정상 작동 중

### 현재 상태
- **51개 테스트 모두 통과** ✅
- `graph_editor.py` 파싱 정상 ✅
- `_import_power_grid` 메서드에 우크라이나 섹션 미추가 상태 (git 버전)
- `TODO.md`와 `unsolved issues.txt` 업데이트 완료

### Known Issues
~~1. **graph_editor.py 들여쓰기 오류 (미해결)**: `_import_power_grid` 메서드에 우크라이나 섹션 추가 필요~~
   ~~- 5-Bus 버튼 다음에 18-Bus, 28-Bus 버튼 추가~~
   ~~- `load_from_file()` 함수 정의 필요~~
   ~~- `get_ukraine_330kv_grid`, `get_large_ukraine_grid` import 필요~~

## 2026-07-11 18:00 — Ukraine 섹션 들여쓰기 오류 수정

### 발견된 문제
1. **`graph_editor.py` `_import_power_grid` SyntaxError**: Ukraine 섹션(18-Bus, 28-Bus)이 16-space 들여쓰기로 되어있어 Python 문법 오류 발생.
   - 원인: `load_test_grid` 함수 내부 레벨(16-space)로 잘못 삽입됨
   - 수정: 메서드 본문 레벨(8-space)로 변경
2. **import 확인**: `get_test_grid_3bus`, `get_test_grid_5bus`, `get_ukraine_330kv_grid`, `get_large_ukraine_grid` 모두 정상 임포트 가능
   - `get_test_grid_3bus`/`get_test_grid_5bus`는 `power_grid.importer`에 정의됨 (electrical_distance 아님)
   - `get_ukraine_330kv_grid`/`get_large_ukraine_grid`는 `power_grid.ukraine_loader`에 정의됨

### Test Results
```
51 passed in 0.08s
```

---

## 2026-07-11 18:57 — Birth=Death 필터링: Persistence Diagram 시각적 노이즈 제거

### Changes
1. **`graph_editor.py` `_draw_pd()` 함수 수정**: H0/H1 points 루프에서 `if b >= d - 1e-12: continue` 추가 — birth=death (대각선) 점 필터링

2. **`integration/power_grid_tda.py` `_draw_persistence_diagram()` 메서드 수정**: 동일한 필터 적용

3. **`integration/power_grid_tda.py` `_compare_metrics()` matplotlib scatter 섹션 수정**: `b < d - 1e-12` 조건으로 필터링

### Test Results
```
51 passed in 0.08s
```

### Resolved Issues
- ✅ birth=death 점 필터링 — persistence diagram에서 무의미한 대각선 점 제거

---

## 2026-07-11 21:30 — TDA 탐색기 VR 알고리즘 통일: inline VR → VRComplex 클래스

### Changes
1. **`graph_editor.py` `_tda_explorer()` 리팩토링**:
   - inline VR 구현 (union-find H₀/H₁ persistence, Betti curves) **완전 제거** (~80줄)
   - 대신 `VRComplex(D)` 클래스 사용으로 변경 (동일한 `tda/vr_core.py` 알고리즘)
   - 슬라이더 update 함수의 Betti number 계산도 `vr.betti_numbers(alpha)`로 통일
   - 별도 `b0_vals` / `b1_vals` pre-compute 제거 (더 이상 필요 없음)

2. **버그 수정**: 기존 inline VR 구현의 H1 triangle killing 로직에 `break` 문이 있어 첫 번째 발견된 삼각형만 처리하는 버그 존재.
   - `VRComplex`의 올바른 youngest edge rule 구현으로 대체되어 이 버그 해결됨.

### 영향
- 이제 **동일한 Euclidean 거리 행렬**에 대해 `_tda_explorer()`(📊 TDA 탐색기)와 `PowerGridTDAExplorer`(🔬 TDA Distance → Geographic)가 **완전히 동일한 persistence 결과**를 반환함
- 코드 중복 제거, 유지보수성 향상
- `_tda_explorer()`의 코드가 약 80줄 감소하여 더 깔끔해짐

### Test Results
```
51 passed in 0.08s
```

### Resolved Issues
- ✅ TDA 탐색기 vs TDA Euclidean 결과 불일치 문제 해결 (근본 원인: inline VR 구현 차이 + triangle killing break 버그)

