# Project History

## 2026-07-11 — Initial Architecture Review & TODO Setup

### Changes
- **Repository analysis**: 전체 코드베이스 아키텍처 파악 완료
- **TODO.md 생성**: 프로젝트 목표와 진행 상황을 추적할 todolist 작성
- **history.md 생성**: 본 파일 — 프로젝트 변경 이력 추적 시작

### Current Architecture
```
graph_editor/
├── graph_editor.py              # Main GUI (Tkinter)
├── electrical_distance/
│   ├── ptdf_calculator.py       # PTDF, LODF, Effective Resistance (pure numpy)
│   └── metrics.py               # OOP metric classes (ABC pattern)
├── tda/
│   └── vr_core.py               # Vietoris-Rips complex (union-find)
├── power_grid/
│   └── importer.py              # Multi-format grid parser
├── integration/
│   ├── grid_to_graph.py         # Grid → GraphEditor converter
│   └── power_grid_tda.py        # TDA explorer GUI with electrical metrics
└── tests/
    └── __init__.py              # Empty test package
```

### Known Issues
1. `power_grid_tda.py` line ~440: `set_faceplot` → `set_facecolor` 오타 (matplotlib)
2. 테스트 코드 없음
3. KCL 기반 거리 함수 미구현

### Next Steps
1. matplotlib 버그 수정
2. 기본 unit tests 구현
3. KCL 기반 거리 함수 확장성 준비

---

## 2026-07-11 — Bug Fixes, Tests, and KCL Extensibility

### Changes
1. **matplotlib 버그 수정**: `power_grid_tda.py`의 `set_faceplot` → `set_facecolor` 오타 수정
2. **Unit tests 구현 (51개 모두 통과)**: PTDF, VR, Metrics 테스트
3. **KCLCurrentDistance 구현**: `metrics.py`에 KCL 기반 전류 거리 메트릭 추가
4. **pyproject.toml 생성**: pip install -e . 지원
5. **README.md 업데이트**: 테스트 실행 방법, 프로젝트 관리 섹션 추가
6. **불필요 import 제거**: `metrics.py`에서 사용되지 않는 `Optional` import 제거

### Files Modified
- `integration/power_grid_tda.py` — set_faceplot → set_facecolor
- `electrical_distance/metrics.py` — KCLCurrentDistance 추가, 불필요 import 제거
- `tests/test_ptdf_calculator.py` — 신규 생성
- `tests/test_vr_core.py` — 신규 생성
- `tests/test_metrics.py` — 신규 생성 (KCLCurrentDistance 테스트 포함)
- `pyproject.toml` — 신규 생성
- `README.md` — 테스트/프로젝트 관리 섹션 추가
- `TODO.md` — 진행 상황 업데이트
- `graph_editor/__init__.py` — 신규 생성 (패키지 초기화)

### Test Results
```
51 passed in 0.19s
```

---

## 2026-07-11 — Ukraine Loader, Vulnerability Engine, Bug Fixes

### Changes
1. **`power_grid_tda.py` 추가 버그 수정**:
   - `_compare_metrics()` 메서드 내 `set_faceplot = "..."` 불필요한 속성 할당 제거
   - `ax.set_facecolor(\"#2A2A3E\")` 이스케이프된 따옴표 버그 수정
   - 중복된 `ax.set_facecolor` 호출 정리

2. **우크라이나 전력망 데이터 로더 생성** (`power_grid/ukraine_loader.py`):
   - `load_ukraine_grid()` — 자동 포맷 감지 로더
   - `load_ukraine_json()` — JSON 로더
   - `load_ukraine_csv()` — CSV 로더
   - `load_ukraine_entsoe_csv()` — ENTSO-E 포맷 로더
   - `load_ukraine_detailed()` — 다중 전압 레벨 지원 상세 로더
   - `get_sample_ukraine_grid()` — Dnipro 지역 6-bus 샘플 테스트 그리드

3. **취약점 탐지 엔진 생성** (`tda/vulnerability.py`):
   - `compute_vulnerability_scores()` — 지속성 호몰로지 기반 3가지 점수:
     - Isolation Score: 거리 공간에서 고립된 버스 탐지
     - Component Merge Score: 늦게 병합되는 컴포넌트의 버스 강조
     - Cycle Membership Score: 지속적인 사이클 구조의 버스 식별 (취약도 감소)
   - `rank_vulnerable_buses()` — 취약도 순위 정렬
   - `compute_vulnerability_summary()` — 종합 분석 리포트

4. **`requirements.txt` 생성**: 의존성 목록 정리

### Files Modified/Added
- `integration/power_grid_tda.py` — 버그 수정 (set_faceplot 제거, 중복 라인 정리)
- `power_grid/ukraine_loader.py` — **신규 생성**
- `tda/vulnerability.py` — **신규 생성**
- `requirements.txt` — **신규 생성**
- `TODO.md` — 진행 상황 업데이트
- `history.md` — 본 항목

### Known Issues
- `pytest` 미설치 (Arch Linux, pip 없음) — `requirements.txt`에 기록, 사용자 설치 필요
- 우크라이나 실제 전력망 데이터 수집 필요
- 취약점 탐지 결과 GUI 통합 미완료

### Next Steps
- 우크라이나 실제 전력망 데이터 수집 및 로더 테스트
- 거리 공간 최적화 (연구팀 회의 결과 반영)
- 취약점 탐지 결과 시각화 GUI 통합
- 연구팀 회의 결과 반영 (거리 함수 정의 확정)
- `pytest` 설치 후 테스트 실행 확인

---

## 2026-07-11 14:30 — Critical Bug Fix: _vulnerability_analysis 메서드 승격

### Changes
1. **`graph_editor.py` 클래스 메서드 승격**:
   - `_on_undo` 메서드 내부에 로컬 함수(`def`)로 잘못 정의되어 있던 7개 메서드들을 `GraphEditor` 클래스의 실제 메서드로 승격 (8-space → 4-space indent)
   - 영향받은 메서드: `_vulnerability_analysis`, `_build_euclidean_distance_matrix`, `_build_electrical_distance_matrix`, `_color_nodes_by_score`, `_reset_node_colors`, `_show_vulnerability_window`, `_show_vulnerability_pd`
   - 이로 인해 `"⚠ 취약점 분석"` 버튼 클릭 시 발생하던 `AttributeError: 'GraphEditor' object has no attribute '_vulnerability_analysis'` 버그 수정

2. **`unsolved issues.txt` 업데이트**: 해결된 이슈를 기록으로 변경

3. **`TODO.md` 업데이트**: 로그 파일 수집 항목을 향후 계획에 추가

### Root Cause
`_on_undo` 메서드(Ctrl+Z) 내부에서 `# ── Vulnerability Analysis ─────────────────────────────────────` 주석 아래의 모든 취약점 분석 관련 메서드들이 로컬 함수로 정의됨. `self`를 인자로 받는 로컬 함수는 Python에서 유효하지만 클래스 메서드가 아니므로 `self._vulnerability_analysis`로 접근 불가능.

### Test Results
```
51 passed in 0.23s
```

### Files Modified
- `graph_editor.py` — 메서드 들여쓰기 수정 (로컬 함수 → 클래스 메서드)
- `unsolved issues.txt` — 해결된 이슈 마킹
- `TODO.md` — 로그 수집 항목 추가
---

## 2026-07-11 — VR Complex H₁ Cycle Death Bug Fix

### Changes
1. **`tda/vr_core.py` persistence_pairs() 버그 수정**:
   - **문제**: 삼각형(2-simplex) 완성 시 `break` 문으로 인해 새 엣지가 동시에 완성시키는 여러 삼각형 중 첫 번째만 처리됨. 나머지 삼각형들은 H₁ 사이클을 죽일 기회를 잃어, 사이클들이 무한대(infinity)까지 생존하는 현상 발생
   - **수정**: `break` 제거 → 새 엣지가 완성시키는 **모든** 삼각형을 처리
   - **추가 수정**: "youngest edge rule" 구현 개선 — 삼각형의 세 엣지를 거리 내림차순으로 정렬하여, 아직 살아있는 H₁ 사이클이 있는 가장 어린 엣지를 찾아 cycle을 kill
   - **결과**: 모든 메트릭(PTDF, Effective R, PTDF Inverse)에서 H₁ death가 infinity로 잘못 표시되던 현상 수정

2. **수정 전/후 비교 (5-bus grid 기준)**:

   | 메트릭 | 수정 전 (infinity death) | 수정 후 (finite death) |
   |---|---|---|
   | PTDF Vector (L2) | 1개 at infinity | 0개 at infinity, max pers=0.098 |
   | Effective Resistance | 1개 at infinity | 0개 at infinity, max pers=0.008 |
   | PTDF Inverse | 2개 at infinity | 0개 at infinity, max pers=0.002 |
   | Bus LODF Sensitivity | 0개 (death=birth) | 0개 (동일, 별도 이슈 있음) |

### Root Cause
- `persistence_pairs()`의 삼각형 검사 루프에서 `break` 문으로 인해 한 edge addition 당 하나의 triangle만 처리됨
- 예: 5-bus grid에서 edge (0,4) 추가 시 (0,4,1), (0,4,3), (0,4,2) 세 개의 삼각형이 동시에 완성되지만, (0,4,1)만 처리되고 (0,4,3)이 죽여야 할 cycle (3,4)가 infinity로 생존

### Test Results
```
51 passed in 0.09s
```

### Files Modified
- `tda/vr_core.py` — triangle killing 로직 수정 (break 제거, youngest edge rule 개선)

---

## 2026-07-11 16:30 — Bus LODF Sensitivity 근본적 재설계: PTDF-weighted Signed LODF

### Changes
1. **`compute_bus_lodf_sensitivity()` 완전 재작성** (`electrical_distance/ptdf_calculator.py`):
   - **문제**: 기존 abs-sum 방식 (v_i[k] = Σ|LODF[incident, k]|)이 대칭적 그리드에서 서로 다른 버스의 민감도 벡터가 동일해지는 문제 발생
     - 3-bus: 모든 버스 쌍 D[i,j] ≈ 0 (완전 붕괴)
     - 5-bus: D[1,3] ≈ 0, D[2,4] ≈ 0 (대칭 버스 쌍에서 거리 0)
     - 원인: LODF 절댓값이 대칭적 위치에서 동일하며, incident line 기반 합계가 정보를 잃어버림
   - **수정**: `v_i[k] = Σ_{l incident to bus i} PTDF[l,i] × LODF[l,k]`로 변경
     - PTDF[l,i]를 가중치로 사용하여 버스별 고유한 민감도 부여
     - PTDF 벡터는 대칭적 그리드에서도 버스별로 고유하므로 문제 해결
     - 부호 보존으로 방향성 정보 활용

2. **수정 전/후 비교**:

   | 그리드 | 수정 전 (abs-sum) | 수정 후 (PTDF-weighted) |
   |---|---|---|
   | 3-bus | 모든 D[i,j] ≈ 0 (3개 쌍) | 모두 고유 (0.96, 0.19, 1.15) |
   | 5-bus D[1,3] | 4.1e-15 (≈0) | 1.570 |
   | 5-bus D[2,4] | 2.6e-15 (≈0) | 0.964 |

### Root Cause
abs-sum 방식은 각 incident line의 |LODF|를 단순 합산하는데, 대칭적 그리드에서 |LODF|는 대칭 위치에서 동일한 값을 가지므로 버스 구분 불가. PTDF 벡터는 PTDF 계산 과정에서 버스 위치의 비대칭성을 반영하므로, PTDF를 가중치로 사용하면 대칭성이 깨짐.

### Files Modified
- `electrical_distance/ptdf_calculator.py` — `compute_bus_lodf_sensitivity()` 재작성
- `unsolved issues.txt` — 해결된 이슈 업데이트
- `TODO.md` — 진행 상황 업데이트
- `history.md` — 본 항목

### Test Results
```
51 passed in 0.11s
```

