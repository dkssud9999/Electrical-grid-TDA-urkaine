# TODO List

## 프로젝트 목표
우크라이나 전력망 데이터로 TDA 분석을 수행하여 취약점 탐지.
Vietoris-Rips complex를 전기적 특성(PTDF, LODF, KCL 기반)을 반영한 거리 함수로 구성.

## 진행 상황

### ✅ 완료
- [x] 기본 그래프 에디터 (Node, Edge, GraphEditor)
- [x] PTDF/LODF/Effective Resistance 계산 모듈 (`ptdf_calculator.py`)
- [x] OOP 거리 메트릭 클래스 (`metrics.py` - ABC 패턴, KCLCurrentDistance 포함)
- [x] Vietoris-Rips Complex (`vr_core.py`)
- [x] 전력망 데이터 임포터 (JSON, CSV, Matpower, PyPSA)
- [x] Grid → Graph 변환기 (`grid_to_graph.py`)
- [x] TDA 탐색기 GUI (`power_grid_tda.py`)
- [x] AI 분석 (OpenRouter + DeepSeek)
- [x] TODO.md / history.md 생성
- [x] `power_grid_tda.py` matplotlib 버그 수정
- [x] 기본 unit tests 53개 구현 (PTDF, VR, Metrics 모두 통과)
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

---

## ⚠️ 실험 방법론 vs 현재 코드 간 괴리 분석 (Gap Analysis)

### 1. LODF 역수 기반 거리 (Primary approach) ❌ 미구현
**방법론**: "PTDF행렬을 구해서, LODF를 구하고 그 역수를 기반으로 하는게 가장 가능성있는 계획"
- **현재**: `BusLODFDistance`는 LODF sensitivity 벡터 사용 (LODF 역수 아님)
- **현재**: `PTDFInverseDistance`는 PTDF 벡터 거리의 역수 사용
- **필요**: `LODFInverseDistance` — LODF 행렬의 pseudo-inverse를 직접 거리로 사용하는 메트릭

### 2. KCL 기반 거리 함수 GUI 미통합 ⚠️
- `KCLCurrentDistance` 클래스는 구현되어 있으나:
  - `power_grid_tda.py`의 `METRICS` 딕셔너리에 등록되지 않음
  - `compare_metrics_vulnerability()`의 `metric_fns`에 포함되지 않음
  - 단위 테스트 없음

### 3. 실험 자동화 파이프라인 ❌ 미구현
- 우크라이나 그리드 로드 → 모든 거리 메트릭 계산 → TDA → 취약점 비교 → 리포트
- `compare_metrics_vulnerability()` 함수는 추가되었으나 GUI와 통합되지 않음
- CLI 기반 배치 실험 도구 없음

### 4. 취약점 엔진 검증 ❌ 미테스트
- `tda/vulnerability.py`에 대한 단위 테스트 없음
- `compare_metrics_vulnerability()`에 대한 테스트 없음
- 실제 우크라이나 그리드 데이터로 end-to-end 테스트 없음

### 5. 지속성 호몰로지 → 취약점 매핑 연구 중 ⏳
- 방법론: "거리공간은 지속성 호몰로지가 나타나는 부분이 취약점이 되는 방식"
- 현재 3가지 휴리스틱 (isolation, component merge, cycle membership) 사용 중
- 연구팀 회의 결과에 따라 매핑 방식 변경 필요

### 6. README.md 구버전 정보 ⚠️
- "47 unit tests"라고 표기되어 있으나 실제로는 53개
- `compare_metrics_vulnerability` 함수 문서화 안 됨
- `vulnerability.py` API 문서화 안 됨

---

## 📋 향후 계획 (우선순위 순)

###P0: 최우선순위계획
 - [ ] 취약점 분석은 휴리스틱 방식을 전혀 사용하지 않고 AC 조류분석을 통해 직접 간선 하나하나씩을 제거하며 취약한 간선을 찾는다
 취약점과 메트릭을 통해 발견한 취약점의 일치도는 간선은 발견한 간선이고 취약한 간선인 간선의 수를 전체 간선으로 나눈 값으로 한다.
호몰로지를 통해 찾은 취약한 간선 후보는 취약한 호몰로지가 나타나는 사이클의 간선들로 정한다, 또한 취약점을 실제로 분석해서 호몰로지와 비교할 때에는 TDA의 방법을 전혀 사용하지 않고 오직 AC 조류분석계산을 한다
취약점을 구하는 법은 간선 하나를 지우고, 다른 간선에 선로 임계 전류 이상이 흐르게 되거나, 노드에 전력이 크게 모자라게 되거나, 네트워크 망이 고립되는 경우 등으로 과학적, 현실적으로 실효성 있는 방식(+컴퓨팅 가능)으로 정한 후, readme에 이를 명확하게 나타낸다

### P1: 핵심 메트릭 구현 및 통합
- [x] **LODFInverseDistance 메트릭 구현**
  - LODF 행렬의 pseudo-inverse를 거리로 사용
  - `electrical_distance/metrics.py`에 새 클래스 추가
  - `power_grid_tda.py` METRICS에 등록
  - `compare_metrics_vulnerability()`에 포함
  - 단위 테스트 추가
- [x] **KCLCurrentDistance GUI 통합**
  - `power_grid_tda.py` METRICS에 KCL Current Distance 등록
  - `compare_metrics_vulnerability()` metric_fns에 추가
  - 단위 테스트 추가

### P2: 테스트 및 검증
- [ ] **취약점 엔진 단위 테스트**
  - `compute_vulnerability_scores` (known topology 검증)
  - `rank_vulnerable_buses`
  - `compare_metrics_vulnerability` (3-bus, 5-bus)
  - `_detect_cycle_members`
- [ ] **실험 자동화 CLI 도구**
  - `scripts/compare_metrics.py` 등
  - 우크라이나 18-Bus / 28-Bus → 모든 메트릭 → 취약점 리포트
  - alignment score 기준 메트릭 랭킹 출력 + JSON/CSV export

### P2: GUI 개선
- [ ] **취약점 분석 결과 GUI 통합**
  - `compare_metrics_vulnerability()` 결과를 GUI 테이블로 표시
  - 메트릭별 alignment score 시각화 (막대 그래프)
  - 우클릭으로 특정 메트릭 상세 분석

### P3: 연구 결과 반영 및 문서화
- [ ] **지속성 호몰로지-취약점 매핑 연구 결과 반영**
  - 연구팀 회의 결과 대기
  - 새로운 매핑 방식 구현
- [ ] **README.md 최신화**
  - 테스트 개수 53으로 업데이트
  - `vulnerability.py` API 문서 추가
  - `compare_metrics_vulnerability` 문서 추가
  - KCLCurrentDistance 문서 추가
- [ ] **KCL 기반 거리 함수 AC 확장 (R, X, tap ratio 포함)**

---

## 참고사항
- `unsolved issues.txt`에 모든 이슈가 정리되어 있음
- `history.md`에 프로젝트 변경 이력 저장됨
- `ukraine_loader.py`에는 `get_ukraine_330kv_grid()`, `get_large_ukraine_grid()`, `get_sample_ukraine_grid()` 함수가 구현되어 있음
- `tda/vulnerability.py`에 `compare_metrics_vulnerability()`와 `_detect_cycle_members()` 함수가 추가되어 있음

