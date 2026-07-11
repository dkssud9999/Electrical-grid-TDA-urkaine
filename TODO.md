# TODO List

## 프로젝트 목표
우크라이나 전력망 데이터로 TDA 분석을 수행하여 취약점 탐지.
Vietoris-Rips complex를 전기적 특성(PTDF, LODF, KCL 기반)을 반영한 거리 함수로 구성.

## 진행 상황

### ✅ 완료
- [x] 기본 그래프 에디터 (Node, Edge, GraphEditor)
- [x] PTDF/LODF/Effective Resistance 계산 모듈 (`ptdf_calculator.py`)
- [x] OOP 거리 메트릭 클래스 (`metrics.py` - ABC 패턴, KCLCurrentDistance 포함) ->테스트해본결과 전기거리 모델이 완성되지않았다고 나옴
- [x] Vietoris-Rips Complex (`vr_core.py`)
- [x] 전력망 데이터 임포터 (JSON, CSV, Matpower, PyPSA)  ->테스트 해본 결과 로드되지않았다고 나옴
- [x] Grid → Graph 변환기 (`grid_to_graph.py`)
- [x] TDA 탐색기 GUI (`power_grid_tda.py`)
- [x] AI 분석 (OpenRouter + DeepSeek)
- [x] TODO.md / history.md 생성
- [x] `power_grid_tda.py` matplotlib 버그 수정 (`set_faceplot` → `set_facecolor`, 중복 라인 정리)
- [x] 기본 unit tests 51개 구현 (PTDF, VR, Metrics 모두 통과)
- [x] README.md 업데이트
- [x] KCLCurrentDistance 구현 (확장성 준비)
- [x] `requirements.txt` 생성 (의존성 목록)
- [x] 우크라이나 전력망 데이터 로더 (`power_grid/ukraine_loader.py`)  ->나는 3bus와 5bus 만 로딩할 수 있을 뿐임, 다시 확인해보길바람
- [x] 취약점 탐지 엔진 (`tda/vulnerability.py`)

### 📋 향후 계획
- [ ] 우크라이나 실제 전력망 데이터 수집 및 로더 테스트
- [ ] 거리 공간 최적화 (연구팀 회의 결과 반영)
- [ ] 지속성 호몰로지 기반 취약점 탐지 알고리즘 고도화
- [ ] 취약점 탐지 결과 시각화 GUI 통합
- [ ] 연구팀 회의 결과 반영 (거리 함수 정의 확정)
- [ ] 대규모 데이터 처리 성능 최적화
- [ ] KCL 기반 거리 함수 AC 확장 (R, X, tap ratio 포함)


중요계획:
주기적으로 담당자가 테스트를 하는데, 이 때 에러창이 뜨거나 하는 등의 로그를 수집하기 위해 로그 파일과 폴더를 만들 것

