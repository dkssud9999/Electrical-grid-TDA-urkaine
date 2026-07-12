# TODO List

## 프로젝트 목표
우크라이나 전력망 데이터로 TDA 분석을 수행하여 취약점 탐지.
Vietoris-Rips complex를 전기적 특성(PTDF, LODF, KCL 기반)을 반영한 거리 함수로 구성.

## 진행 상황

### ✅ 완료
- [x] 기본 그래프 에디터 (Node, Edge, GraphEditor)
- [x] PTDF/LODF/Effective Resistance 계산 모듈 (`ptdf_calculator.py`)
- [x] OOP 거리 메트릭 클래스 (`metrics.py` - ABC 패턴, 8개 메트릭)
- [x] Vietoris-Rips Complex (`vr_core.py`)
- [x] 전력망 데이터 임포터 (JSON, CSV, Matpower, PyPSA)
- [x] Grid → Graph 변환기 (`grid_to_graph.py`)
- [x] TDA 탐색기 GUI (`power_grid_tda.py`)
- [x] AI 분석 (OpenRouter + DeepSeek)
- [x] TODO.md / history.md 생성
- [x] `power_grid_tda.py` matplotlib 버그 수정
- [x] README.md 업데이트
- [x] KCLCurrentDistance 구현 (확장성 준비)
- [x] `requirements.txt` 생성
- [x] 우크라이나 전력망 데이터 로더 (`power_grid/ukraine_loader.py`)
- [x] 취약점 탐지 엔진 (`tda/vulnerability.py`)
- [x] `_vulnerability_analysis` 메서드 승격 (로컬 함수 → 클래스 메서드)
- [x] VR Complex H1 Cycle Death 버그 수정
- [x] Bus LODF Sensitivity 재설계: PTDF-weighted Signed LODF
- [x] 우크라이나 전력망 18-Bus / 28-Bus 버튼 GUI 통합 완료
- [x] 로그 시스템 구축 (`utils/logger.py`, `logs/` 디렉토리)
- [x] 취약점 분석 PowerGridTDAExplorer 통합 (⚠ 버튼 + 결과 창 + VR 색상 표시)
- [x] `power_grid_tda.py` IndentationError 수정
- [x] `compare_metrics_vulnerability()` 함수 추가 — 거리 메트릭별 취약점 정렬 비교 가능
- [x] `_detect_cycle_members()` 함수 추가 — 2-core 기반 H1 사이클 멤버 검출
- [x] **P1: LODFInverseDistance 메트릭 구현** (`electrical_distance/metrics.py`)
- [x] **P1: KCLCurrentDistance GUI 통합** (`integration/power_grid_tda.py`)
- [x] **P0: AC 조류분석 기반 N-1 취약점 분석** (`power_grid/ac_power_flow.py`, `power_grid/contingency.py`)
  - Newton-Raphson AC 조류분석 솔버 (순수 numpy)
  - N1ContingencyAnalyzer: 각 라인 제거 후 AC 조류분석 재실행
  - 취약점 기준: 선로 과부하, 전압 위반, 섬격리(islanding)
- [x] **P0: 호몰로지 비교 함수** (`tda/vulnerability.py`)
  - `compare_with_homology()`: N-1 취약 간선과 H1 사이클 간선 간 정렬 점수
  - `compare_metrics_vulnerability()`: 여러 거리 메트릭 간 정렬 점수 비교
- [x] **P0: 단위 테스트 23개 추가** (`tests/test_contingency.py`)
  - AC 조류분석 (3-bus, 5-bus 수렴, 전력 균형)
  - N-1 컨틴전시 (3-bus, 5-bus, 위반 상세 구조)
  - 사이클 추출 (triangle, tree, square)
  - 정렬 점수 (perfect, partial, no overlap, empty)
  - 통합 테스트 (compare_with_homology, compare_metrics_vulnerability)

---

## ⚠️ 실험 방법론 vs 현재 코드 간 괴리 분석 (Gap Analysis)

### 1. LODF 역수 기반 거리 ✅ 구현 완료
**방법론**: "PTDF행렬을 구해서, LODF를 구하고 그 역수를 기반으로 하는게 가장 가능성있는 계획"
- **구현**: `LODFInverseDistance` — LODF 행렬의 pseudo-inverse 기반 거리
- `electrical_distance/metrics.py`에 클래스 구현
- `power_grid_tda.py` METRICS에 등록됨
- `compare_metrics_vulnerability()` metric_fns에 포함됨
- 단위 테스트 4개 추가

### 2. KCL 기반 거리 함수 GUI 통합 ✅ 완료
- `KCLCurrentDistance` 클래스 구현 완료
- `power_grid_tda.py` METRICS에 등록 완료
- `compare_metrics_vulnerability()` metric_fns에 포함 완료
- 단위 테스트 2개 추가

### 3. AC 조류분석 기반 N-1 취약점 분석 ✅ 구현 완료
- **방법론**: "취약점 분석은 휴리스틱 방식을 전혀 사용하지 않고 AC 조류분석을 통해 직접 간선 하나하나씩을 제거하며 취약한 간선을 찾는다"
- **구현**: `N1ContingencyAnalyzer` (`power_grid/contingency.py`)
  - 취약점 기준: 선로 과부하(flow > rate), 전압 위반(V < 0.9 or V > 1.1), 섬격리(islanding)
  - alignment score = |intersection| / total_edges
- **구현**: `compare_with_homology()` (`tda/vulnerability.py`)
  - N-1 취약 간선과 H1 사이클 간선 비교
  - precision, recall, specificity 포함

### 4. 실험 자동화 파이프라인 ❌ 미구현
- 우크라이나 그리드 로드 → 모든 거리 메트릭 계산 → TDA → 취약점 비교 → 리포트
- `compare_metrics_vulnerability()` 함수는 추가되었으나 GUI와 통합되지 않음
- CLI 기반 배치 실험 도구 없음

### 5. 취약점 엔진 검증 ⚠️ 부분 완료
- `tests/test_contingency.py`에 N-1 + 호몰로지 통합 테스트 23개 추가됨
- `tda/vulnerability.py`의 legacy 함수들(compute_vulnerability_scores 등)은 아직 테스트 없음
- 실제 우크라이나 그리드 데이터로 end-to-end 테스트 없음

### 6. README.md 구버전 정보 ⚠️
- "47 unit tests"라고 표기되어 있으나 실제로는 82개
- `vulnerability.py` API 문서화 안 됨
- `compare_metrics_vulnerability` 함수 문서화 안 됨
- N-1 contingency analysis 기준 문서화 안 됨
- AC power flow solver 문서화 안 됨

---

## 📋 향후 계획 (우선순위 순)

### P2: 테스트 및 검증 ✅ 완료
- [x] **실험 자동화 CLI 도구** (`scripts/compare_metrics.py`)
  - 우크라이나 18-Bus / 28-Bus → 모든 메트릭 → 취약점 리포트
  - alignment score 기준 메트릭 랭킹 출력 + JSON/CSV export

### P2: GUI 개선 ✅ 완료
- [x] **취약점 분석 결과 GUI 통합**
  - `compare_metrics_vulnerability()` 결과를 GUI 테이블로 표시
  - 메트릭별 alignment score 순위표 + Best Metric 하이라이트
  - PowerGridTDAExplorer에 "📊 Metrics vs N-1" 버튼 추가

### P3: 연구 결과 반영 및 문서화 ✅ 완료
- [x] **README.md 최신화**
  - 테스트 개수 82로 업데이트
  - `vulnerability.py` API 문서 추가
  - `compare_metrics_vulnerability` 문서 추가
  - N-1 contingency analysis 기준 문서화
  - AC power flow solver 문서화
  - CLI 도구 문서화
- [ ] **지속성 호몰로지-취약점 매핑 연구 결과 반영** (연구팀 회의 결과 대기)
- [ ] **KCL 기반 거리 함수 AC 확장 (R, X, tap ratio 포함)**

---

## 참고사항
- `unsolved issues.txt`에 모든 이슈가 정리되어 있음
- `history.md`에 프로젝트 변경 이력 저장됨
- `ukraine_loader.py`에는 `get_ukraine_330kv_grid()`, `get_large_ukraine_grid()`, `get_sample_ukraine_grid()` 함수가 구현되어 있음
- `tda/vulnerability.py`에 `compare_metrics_vulnerability()`와 `_detect_cycle_members()` 함수가 추가되어 있음
- 현재 테스트 82개 모두 통과

