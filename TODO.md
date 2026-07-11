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
- [x] 기본 unit tests 51개 구현 (PTDF, VR, Metrics 모두 통과)
- [x] README.md 업데이트
- [x] KCLCurrentDistance 구현 (확장성 준비)
- [x] `requirements.txt` 생성
- [x] 우크라이나 전력망 데이터 로더 (`power_grid/ukraine_loader.py`)
- [x] 취약점 탐지 엔진 (`tda/vulnerability.py`)
- [x] `_vulnerability_analysis` 메서드 승격 (로컬 함수 → 클래스 메서드)
- [x] VR Complex H1 Cycle Death 버그 수정
- [x] Bus LODF Sensitivity 재설계: PTDF-weighted Signed LODF
- [x] `_import_power_grid` 들여쓰기 오류 수정 (16 → 8 spaces)
- [x] 우크라이나 전력망 18-Bus / 28-Bus 버튼 GUI 통합 완료
- [x] 로그 시스템 구축 (`utils/logger.py`, `logs/` 디렉토리)
- [x] 취약점 분석 PowerGridTDAExplorer 통합 (⚠ 버튼 + 결과 창 + VR 색상 표시)
- [x] `power_grid_tda.py` IndentationError 최종 수정 (write_to_file로 완전 재작성)

### 📋 향후 계획
- [ ] 거리 공간 최적화 (연구팀 회의 결과 반영)
- [ ] 지속성 호몰로지 기반 취약점 탐지 알고리즘 고도화
- [ ] 취약점 탐지 결과 시각화 GUI 통합 완료
- [ ] 연구팀 회의 결과 반영 (거리 함수 정의 확정)
- [ ] 대규모 데이터 처리 성능 최적화
- [ ] KCL 기반 거리 함수 AC 확장 (R, X, tap ratio 포함)
- [ ] 로그 파일 및 폴더 생성 (에러/경고 수집)

## 참고사항
- `unsolved issues.txt`에 모든 이슈가 정리되어 있음
- `history.md`에 프로젝트 변경 이력 저장됨
- `ukraine_loader.py`에는 `get_ukraine_330kv_grid()`, `get_large_ukraine_grid()`, `get_sample_ukraine_grid()` 함수가 구현되어 있음
- GUI에서 우크라이나 그리드를 로드하려면 import 문과 버튼 코드 추가 필요

