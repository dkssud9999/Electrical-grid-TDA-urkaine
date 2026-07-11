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

