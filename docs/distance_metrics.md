# 전기적 거리공간 함수 상세 설명 (Electrical Distance Metrics)

> 이 문서는 프로젝트에서 사용된 모든 거리공간(distance metric) 함수들에 대해
> 수학적 정의, 거리공간 성질, 물리적 해석, 그리고 지속성 호몰로지(persistent homology) 기반
> 취약점 분석과의 연관성을 설명합니다.

---

## 목차

1. [개요](#1-개요)
2. [PTDFVectorDistance](#2-ptdfvectordistance)
3. [EffectiveResistanceDistance](#3-effectiveresistancedistance)
4. [BusLODFDistance (Bus LODF Sensitivity)](#4-buslodfdistance-bus-lodf-sensitivity)
5. [PTDFInverseDistance](#5-ptdfinversedistance)
6. [LODFInverseDistance](#6-lodfinversedistance)
7. [KCLCurrentDistance](#7-kclcurrentdistance)
8. [HybridDistance](#8-hybriddistance)
9. [GeodesicElectricalHybrid](#9-geodesicelectricalhybrid)
10. [Geographic (Euclidean) Distance](#10-geographic-euclidean-distance)
11. [거리공간 성질 비교 요약](#11-거리공간-성질-비교-요약)
12. [취약점 분석과의 연결](#12-취약점-분석과의-연결)

---

## 1. 개요

### 배경

이 프로젝트는 전력망의 **취약점(vulnerability)** 을 찾기 위해 **지속성 호몰로지(persistent homology)** 를
사용합니다. 구체적으로, 전력망의 버스(bus)들 사이의 **전기적 거리(electrical distance)** 를 정의하고,
이 거리공간 위에 **비에토리스-립스 컴플렉스(Vietoris-Rips complex)** 를 구성하여
H₁ 지속성 사이클(persistent cycle)을 추출합니다.

이때 중요한 가정은:

> **"지속성 호몰로지에서 오래 지속되는 H₁ 사이클을 구성하는 선로들이
>   전력망의 N-1 취약 선로일 가능성이 높다"**

는 것입니다. 이 가정이 성립하려면 거리공간이 전기적 특성을 **물리적으로 의미 있게**
반영해야 합니다.

### DC 조류계산(Decoupled Power Flow) 가정

모든 전기적 거리함수는 기본적으로 **DC 조류계산 근사**를 사용합니다:

$$P = B' \cdot \theta$$

$$PTDF = \text{diag}(b) \cdot C \cdot (B')^{-1}$$

여기서:
- $B'$: 서셉턴스 행렬 (n_bus × n_bus)
- $C$: 입사 행렬 (n_line × n_bus)
- $b$: 각 선로의 서셉턴스 벡터
- $PTDF$: 전력 전송 분배 계수 행렬 (n_line × n_bus)

### 거리공간의 필요 조건

함수 $d: X \times X \to \mathbb{R}_{\ge 0}$가 **거리공간(metric space)** 이 되려면
다음 조건들을 만족해야 합니다:

| 조건 | 정의 | 설명 |
|------|------|------|
| **Non-negativity** (비음수성) | $d(i,j) \ge 0$ | 거리는 항상 0 이상 |
| **Identity of Indiscernibles** (동일자 식별) | $d(i,j) = 0 \iff i = j$ | 다른 점 사이 거리는 0보다 큼 |
| **Symmetry** (대칭성) | $d(i,j) = d(j,i)$ | 방향 무관 |
| **Triangle Inequality** (삼각부등식) | $d(i,j) \le d(i,k) + d(k,j)$ | 직진 경로가 최단 |

---

## 2. PTDFVectorDistance

### 수학적 정의

$$d(i,j) = \lVert PTDF[:,i] - PTDF[:,j] \rVert_p$$

여기서 $PTDF[:,i] \in \mathbb{R}^{n_{\text{line}}}$은 버스 $i$에서 1 p.u. 주입 시
각 선로의 전력 흐름 변화율을 나타내는 벡터입니다.

### 거리공간 성질

| 성질 | 만족 여부 | 증명 |
|------|----------|------|
| **Non-negativity** | ✅ | 노름(norm)의 성질: $\lVert x \rVert_p \ge 0$ |
| **Identity of Indiscernibles** | ✅ | $PTDF[:,i] = PTDF[:,j}$ 이면 $i=j$ (DC 조류계산에서 slack bus가 동일하면 PTDF 벡터는 버스별로 고유함) |
| **Symmetry** | ✅ | $\lVert PTDF[:,i] - PTDF[:,j] \rVert_p = \lVert PTDF[:,j] - PTDF[:,i] \rVert_p$ |
| **Triangle Inequality** | ✅ | 노름의 삼각부등식: $\lVert x - z \rVert_p \le \lVert x - y \rVert_p + \lVert y - z \rVert_p$ |

> **결론**: PTDFVectorDistance는 **완전한 거리공간(metric space)** 입니다.

### 물리적 의미

- $PTDF[l,i]$는 버스 $i$에서 1 p.u. 전력을 주입하고 slack bus에서 회수할 때
  선로 $l$에 흐르는 전력 변화율입니다.
- 두 버스 $i,j$의 PTDF 벡터가 유사하다는 것은 **"어느 버스에 전력을 주입해도
  전체 선로 흐름 패턴이 비슷하다"** 는 의미입니다.
- 즉, PTDFVectorDistance가 작은 버스들은 **전기적으로 밀접하게 연결**되어 있습니다.

### 취약점 분석과의 관련성

- PTDF 벡터가 유사한 버스들은 전력 흐름 패턴이 비슷하므로, 이들 사이의 선로가
  고장 나면 유사한 재분배 패턴이 발생합니다.
- H₁ 사이클은 PTDFVectorDistance 기반 VR 복합체에서 **전력 흐름 패턴이 유사한
  버스들이 형성하는 고리 구조**를 포착합니다.
- 이러한 고리가 N-1 사고 시 **재분배 경로**(대체 경로) 역할을 하므로,
  고리를 구성하는 선로들의 고장이 연쇄적 과부하를 유발할 가능성이 높습니다.
- `compare_metrics.py`의 Ukraine 18-bus 실험에서 **PTDF Vector (L2)가 최고
  alignment score (0.9600)** 를 기록하여 가장 우수한 성능을 보였습니다.

---

## 3. EffectiveResistanceDistance

### 수학적 정의

$$R_{\text{eff}}(i,j) = (e_i - e_j)^T \cdot L^+ \cdot (e_i - e_j)$$

여기서:
- $L = C^T \cdot \text{diag}(b) \cdot C$는 **가중 라플라시안 행렬**(weighted Laplacian)
- $L^+$는 라플라시안의 무어-펜로즈 유사역행렬(Moore-Penrose pseudoinverse)
- $e_i$는 $i$번째 표준 기저 벡터 (단위 벡터)
- $b$는 선로 서셉턴스 가중치

### 거리공간 성질

| 성질 | 만족 여부 | 증명 |
|------|----------|------|
| **Non-negativity** | ✅ | $L^+$가 양의 반정치(PSD)이므로 이차형식은 항상 $\ge 0$ |
| **Identity of Indiscernibles** | ✅ | $R_{\text{eff}}(i,i) = 0$, $i \neq j$이면 $L^+$의 kernel이 1차원(상수벡터)이므로 양수 |
| **Symmetry** | ✅ | $(e_i - e_j)^T L^+ (e_i - e_j) = (e_j - e_i)^T L^+ (e_j - e_i)$ |
| **Triangle Inequality** | ✅ | 유효 저항은 **제곱 유클리드 거리의 내적 공간 표현**으로 삼각부등식 만족 |
| **추가 성질** | ✅ | **pythagorean property**: 그래프가 트리 구조일 때 $R_{\text{eff}}(i,j)$는 물리적 저항과 일치 |

> **결론**: EffectiveResistanceDistance는 **완전한 거리공간**이며, 그래프 이론에서
> **저항 거리(resistance distance)** 라고도 불리는 이론적으로 가장 잘 정립된 지표입니다.

### 물리적 의미

- 각 선로의 서셉턴스 $b = 1/x$를 전도도(conductance)로 해석하면,
  전력망은 **순수 저항 네트워크(pure resistive network)** 가 됩니다.
- $R_{\text{eff}}(i,j)$는 버스 $i$와 $j$ 사이에 1A의 전류를 흘릴 때의
  **등가 저항(equivalent resistance)** 과 같습니다. (이것이 "유효 저항"이라는 이름의 유래)
- 이는 그래프 상의 **랜덤 워크 커뮤트 시간(random walk commute time)** 과도
  비례 관계에 있습니다 ($C(i,j) = 2m \cdot R_{\text{eff}}(i,j)$, 여기서 $m$은 전체 선로 수).

### 취약점 분석과의 관련성

- 유효 저항이 큰 버스 쌍은 **전기적으로 멀리 떨어져 있어** 효율적인 전력 전송이 어렵습니다.
- 유효 저항이 작은 버스들은 **강하게 결합**되어 있어 이들 사이의 선로 고장이
  큰 영향을 미칩니다.
- DC 조류계산 근사에서 **PTDF와 유효 저항은 밀접한 관계**가 있습니다:
  $$R_{\text{eff}}(i,j) = \sum_{l} \frac{(PTDF[l,i] - PTDF[l,j])^2}{b_l}$$
  즉, PTDF Vector Distance (L2)의 **가중 제곱 버전**이라고 볼 수 있습니다.
- 따라서 H₁ 사이클은 **전기적으로 강하게 결합된 버스들의 고리**를 포착하며,
  이 고리의 선로들은 상호 의존성이 높아 N-1 사고 시 연쇄 고장 위험이 있습니다.

---

## 4. BusLODFDistance (Bus LODF Sensitivity)

### 수학적 정의

먼저 각 버스 $i$에 대해 **LODF 민감도 벡터** $v_i \in \mathbb{R}^{n_{\text{line}}}$를 정의합니다:

$$v_i[k] = \sum_{l \in \text{incident}(i)} PTDF[l,i] \times LODF[l,k]$$

여기서 $\text{incident}(i)$는 버스 $i$에 연결된 모든 선로의 집합입니다.

그리고 거리는:

$$d(i,j) = \lVert v_i - v_j \rVert_2$$

LODF는 다음과 같이 정의됩니다:

$$LODF_{l,k} = \frac{PTDF[l,f_k] - PTDF[l,t_k]}{1 - (PTDF[k,f_k] - PTDF[k,t_k])}$$

이는 **선로 $k$가 고장 났을 때 선로 $l$의 흐름 변화율**을 나타냅니다.

### 거리공간 성질

| 성질 | 만족 여부 | 증명 |
|------|----------|------|
| **Non-negativity** | ✅ | L2 노름이므로 항상 $\ge 0$ |
| **Identity of Indiscernibles** | ❌ (약함) | PTDF 가중치로 인해 일반적으로 $v_i \neq v_j$ ($i \neq j$)이나, 특수한 대칭 구조에서 동일 벡터 가능성이 완전히 배제되지는 않음 |
| **Symmetry** | ✅ | $\lVert v_i - v_j \rVert_2 = \lVert v_j - v_i \rVert_2$ |
| **Triangle Inequality** | ✅ | L2 노름의 삼각부등식 성립 |

> **참고**: Bus LODF Sensitivity는 원래 PTDF 없는 순수 LODF 합계 방식($v_i[k] = \sum_{l \in \text{incident}(i)} |LODF[l,k]|$)에서
> **PTDF 가중치를 도입**하여 개선되었습니다. 순수 LODF 방식은 대칭적 그리드에서 버스들이 동일한 민감도 벡터를 가져
> Identity of Indiscernibles가 심각하게 위반되었습니다 (history.md 2026-07-11 16:30 참조).

### 물리적 의미

- $v_i[k]$는 다음과 같이 해석됩니다:
  > **"선로 $k$가 고장 났을 때, 버스 $i$에 연결된 선로들의 흐름이 얼마나 변하는지,
  >   각 선로에 대한 버스 $i$의 주입 영향력(PTDF)으로 가중평균한 값"**

- 즉, 이 거리는 **"각 선로 고장에 대한 버스들의 반응 패턴 차이"** 를 측정합니다.
- PTDF 가중치가 없으면 대칭적 그리드의 모든 버스가 동일한 민감도를 가지므로
  변별력이 없었습니다. PTDF 가중치를 도입함으로써 각 버스의 **방향성 있는 영향력**을
  반영할 수 있게 되었습니다.

### 취약점 분석과의 관련성

- 이 거리는 **직접적으로 선로 고장(outage) 시나리오**를 기반으로 합니다.
- $d(i,j)$가 작은 버스들은 **동일한 고장에 대해 비슷하게 반응**합니다.
- 즉, 이 거리공간에서 가까운 버스들은 **함께 취약해지는 경향**이 있습니다.
- H₁ 사이클은 **고장 반응 패턴이 유사한 버스들의 고리**를 포착하며,
  이는 "어느 한 선로가 고장 나면 고리 전체가 영향을 받는다"는 것을 의미합니다.
- 이는 N-1 분석의 **연쇄 고장 메커니즘**과 직접적으로 연결됩니다.

---

## 5. PTDFInverseDistance

### 수학적 정의

PTDF Vector Distance $d_{PTDF}(i,j)$를 다양한 함수로 변환:

**Inverse 모드:**
$$d(i,j) = \frac{1}{1 + d_{PTDF}(i,j)}$$

**Gaussian 모드:**
$$d(i,j) = \exp\left(-\frac{d_{PTDF}(i,j)}{\sigma}\right)$$

**Logistic 모드:**
$$d(i,j) = \frac{1}{1 + \exp(d_{PTDF}(i,j) - \sigma)}$$

### 거리공간 성질

| 성질 | Inverse | Gaussian | Logistic |
|------|---------|----------|----------|
| **Non-negativity** | ✅ | ✅ | ✅ |
| **Identity of Indiscernibles** | ❌ | ❌ | ❌ |
| **Symmetry** | ✅ | ✅ | ✅ |
| **Triangle Inequality** | ❌ | ❌ | ❌ |

> **결론**: PTDFInverseDistance는 **거리공간이 아닙니다(pseudometric 이하)**.
> 특히 삼각부등식을 만족하지 않으며 $d(i,i) \neq 0$일 수 있습니다 (Inverse 모드에서 $d(i,i) = 1/2$).
> 엄밀히 말하면 **유사도 척도(similarity measure)** 에 가깝습니다.

### 물리적 의미

- 원래 PTDF 노름이 무한대가 될 수 있는 문제를 해결하기 위해 **유계(bounded) 구간 [0,1]로 사상**합니다.
- 거리가 아닌 **유사도(similarity)** 로 해석하는 것이 적절합니다:
  - $d(i,j) \to 1$: 두 버스가 전기적으로 매우 유사
  - $d(i,j) \to 0$: 두 버스가 전기적으로 매우 다름

### 취약점 분석과의 관련성

- VR 복합체는 일반적으로 원래 거리(노름)가 필요하므로,
  이 변환된 유사도를 거리로 사용하면 지속성 호몰로지의 해석이 어려워집니다.
- 그러나 **1에 가까운 값들이 많은 영역**에서 VR 복합체가 빨리 성장하므로
  (작은 threshold에서도 많은 에지 생성), 취약점 탐지의 분해능이 달라질 수 있습니다.
- `compare_metrics.py`에서는 Inverse 모드가 사용되며 이론적 한계에도 불구하고
  실제 alignment score는 괜찮은 성능을 보일 수 있습니다.

---

## 6. LODFInverseDistance

### 수학적 정의

이는 프로젝트의 **가장 핵심적이고 독창적인 거리함수**입니다.

먼저 LODF 행렬 $LODF \in \mathbb{R}^{n_{\text{line}} \times n_{\text{line}}}$의
유사역행렬(pseudoinverse)을 구합니다:

$$LODF^+ = \text{pinv}(LODF)$$

각 버스 $i$에 대해 **LODF 역공간 프로파일** $v_i \in \mathbb{R}^{n_{\text{line}}}$을 정의:

$$v_i = C[:,i]^T \cdot LODF^+$$

여기서 $C[:,i]$는 입사 행렬의 $i$번째 열로, 버스 $i$에 연결된 선로들을 나타냅니다.

최종 거리:

$$d(i,j) = \lVert v_i - v_j \rVert_2$$

### 거리공간 성질

| 성질 | 만족 여부 | 증명 |
|------|----------|------|
| **Non-negativity** | ✅ | L2 노름 |
| **Identity of Indiscernibles** | ✅ (일반적) | $C[:,i] \neq C[:,j]$ ($i \neq j$) 이고 $LODF^+$가 full rank에 가까우면 상이한 프로파일 |
| **Symmetry** | ✅ | $\lVert v_i - v_j \rVert_2 = \lVert v_j - v_i \rVert_2$ |
| **Triangle Inequality** | ✅ | L2 노름의 삼각부등식 |

> **결론**: LODFInverseDistance는 **완전한 거리공간**입니다.
> 이는 프로젝트의 핵심 가설인 **"PTDF를 구하고, LODF를 구하고 그 역수를 기반으로 하는 것이
> 가장 가능성 있는 계획"** 을 직접 구현한 것입니다.

### 수학적 직관

LODF 행렬은 **선로 고장이 다른 선로로 전파되는 방식을 나타내는 선형 연산자**입니다.
그 유사역행렬 $LODF^+$는 이 **고장 전파 공간의 "역방향" 사상**을 정의합니다:

$$LODF^+ : \text{(선로 고장 영향)} \mapsto \text{(고장 원인 공간)}$$

버스 $i$의 입사 벡터 $C[:,i]$는 "버스 $i$에 어떤 선로들이 연결되어 있는가"를 나타내며,
여기에 $LODF^+$를 곱하면:

> **"버스 $i$에 연결된 선로 패턴을 LODF 고장 전파 공간의 관점에서 재해석한 표현"**

을 얻습니다.

### 물리적 의미 (핵심 통찰)

LODFInverseDistance의 핵심 통찰은 다음과 같습니다:

> **LODF는 "선로 $k$가 고장 났을 때 다른 선로들의 흐름이 어떻게 변하는가"를 나타냅니다.**
> **그 유사역행렬은 반대로 "어떤 선로 흐름 변화 패턴이 어떤 고장에 의해 발생했는가"를**
> **추론할 수 있게 해줍니다.**
>
> **버스 $i$의 입사 벡터를 이 유사역공간에 사영하면, 해당 버스가 경험하는**
> **"고장 전파 공간에서의 위치"를 얻을 수 있습니다.**

두 버스의 프로파일 $v_i, v_j$가 유사하다는 것은:
> **"두 버스가 선로 고장으로 인한 흐름 재분배를 유사한 방식으로 경험한다"**

는 것을 의미합니다.

### 취약점 분석과의 관련성

1. **LODF는 N-1 사고의 직접적인 수학적 모델**입니다.
   - $LODF[l,k]$는 "선로 $k$가 고장 났을 때 선로 $l$의 부하가 $LODF[l,k]$만큼 증가한다"
   - 이는 N-1 취약점 분석의 핵심 요소입니다.

2. **LODFInverseDistance 기반 H₁ 사이클**은:
   - **고장 전파 공간에서 유사한 위치에 있는 버스들의 고리**
   - 이 고리의 선로들은 하나가 고장 나면 고리 전체의 흐름이 크게 재분배됨

3. **이 거리가 N-1 취약점과 높은 alignment를 보일 것으로 기대되는 이유**:
   - LODF 자체가 N-1 사고의 영향력을 직접 계산하므로,
   - LODF의 유사역을 통해 정의된 거리는 **N-1 사고와 가장 직접적으로 연결**됨
   - 따라서 이 거리공간의 H₁ 사이클은 N-1 취약 선로와 높은 일치를 보일 가능성이 큼

---

## 7. KCLCurrentDistance

### 수학적 정의

각 버스 $i$에 대해 1 p.u. 전력을 주입했을 때의 **선로 전류 벡터** $I_i \in \mathbb{R}^{n_{\text{line}}}$를 계산:

1. DC 조류계산: $B'\theta = P$를 풀어 전압 위상각 $\theta$를 구함
2. 선로 전류: $I_i[l] = b_l \cdot (C[l,:] \cdot \theta)$ (DC 근사에서 전류 ≈ 전력)

최종 거리:

$$d(i,j) = \lVert I_i - I_j \rVert_p$$

### 거리공간 성질

| 성질 | 만족 여부 | 증명 |
|------|----------|------|
| **Non-negativity** | ✅ | 노름 성질 |
| **Identity of Indiscernibles** | ✅ | DC 조류계산에서 서로 다른 버스 주입은 다른 전류 분포 생성 |
| **Symmetry** | ✅ | $\lVert I_i - I_j \rVert_p = \lVert I_j - I_i \rVert_p$ |
| **Triangle Inequality** | ✅ | 노름의 삼각부등식 |

> **결론**: KCLCurrentDistance는 **완전한 거리공간**입니다.

### PTDF Vector Distance와의 관계

KCL Current Distance와 PTDF Vector Distance는 밀접한 관계가 있습니다:

$$I_i[l] = b_l \cdot (C[l,:] \cdot \theta)$$

여기서 $\theta = (B')^{-1} \cdot P_i$이고, $P_i$는 버스 $i$에 1 p.u.를 주입하는 벡터입니다.

반면 PTDF는:

$$PTDF[l,i] = b_l \cdot (C[l,:] \cdot (B')^{-1} \cdot e_i) = \text{선로 $l$의 전력 변화율}$$

즉, KCL 전류 $I_i$와 PTDF 열벡터 $PTDF[:,i]$는 **선형적으로 관련되어 있지만**
다음과 같은 차이가 있습니다:

| 특성 | PTDF Vector | KCL Current |
|------|-------------|-------------|
| 물리량 | 전력 변화율 (dimensionless) | 전류 (A or p.u.) |
| 해석 | "버스 주입이 선로에 미치는 영향" | "버스 주입 시 실제 선로 전류" |
| 확장성 | DC 한정 | 전역행렬(Y)로 AC 확장 가능 |

### 물리적 의미

- KCL Current Distance는 **실제 전류의 분포 패턴**을 비교합니다.
- 두 버스의 전류 벡터가 유사하다는 것은 **"두 버스에서 전력을 주입하면
  실제 전류가 비슷한 경로로 흐른다"** 는 의미입니다.
- 가장 큰 장점은 **확장성(extensibility)**: 현재는 DC 근사(서셉턴스만 사용)이지만,
  전역행렬 $Y = G + jB$를 사용하면 **선로 저항(R)과 리액턴스(X)를 모두 고려한
  AC 전류 거리**로 확장할 수 있습니다.

### 취약점 분석과의 관련성

- KCL Current Distance는 **실제 전류 분포**를 기반으로 하므로,
  과부하(overload) 현상을 직접적으로 반영합니다.
- 전류 분포가 유사한 버스들이 형성하는 H₁ 사이클은:
  - **동일한 전류 경로를 공유하는 고리**
  - 하나의 선로가 고장 나면 고리 내 다른 선로들의 전류가 급증할 가능성
- 단, 현재 구현은 DC 근사이므로 AC 효과(무효전력, 전압 위반)는 반영되지 않습니다.
  향후 AC 확장 시 더 정확한 취약점 예측이 가능할 것입니다.

---

## 8. HybridDistance

### 수학적 정의

$$D_{\text{hybrid}} = \sum_{k} w_k \cdot \text{normalize}(D_k)$$

여기서 각 구성 요소 $D_k$는 개별적으로 $[0,1]$ 범위로 정규화됩니다:

$$\text{normalize}(D) = \frac{D - \min(D)}{\max(D) - \min(D)}$$

### 거리공간 성질

| 성질 | 만족 여부 | 설명 |
|------|----------|------|
| **Non-negativity** | ✅ | 가중합이므로 |
| **Identity of Indiscernibles** | ❌ | 정규화 과정에서 동일성 보장이 깨질 수 있음 |
| **Symmetry** | ✅ | 각 구성 요소가 대칭이면 가중합도 대칭 |
| **Triangle Inequality** | ❌ | 정규화가 비선형 변환이므로 일반적으로 불성립 |

> **결론**: HybridDistance는 일반적으로 **거리공간이 아닙니다**.
> 실험적 탐색을 위한 도구입니다.

### 물리적 의미

- 여러 거리의 장점을 결합하려는 시도입니다.
- 예를 들어 PTDFVectorDistance(민감도 중심) + EffectiveResistance(연결성 중심)를
  결합하면 두 가지 측면을 모두 반영할 수 있습니다.
- 단, 가중치 설정이 까다롭고 각 구성 요소의 스케일 차이로 인해
  정규화가 필수적입니다.

### 취약점 분석과의 관련성

- 다양한 측면의 전기적 특성을 종합적으로 반영할 수 있습니다.
- 이상적인 가중치를 찾는 것이 중요한 연구 과제입니다.
- 현재는 실험적 도구 수준이며, 실제 취약점 분석에서는 단일 메트릭이
  더 나은 성능을 보일 수 있습니다 (compare_metrics.py 결과 참조).

---

## 9. GeodesicElectricalHybrid

### 수학적 정의

$$D = w_{\text{geo}} \cdot D_{\text{geo}} + w_{\text{elec}} \cdot D_{\text{elec}}$$

여기서:
- $D_{\text{geo}}$: 버스 위치의 유클리드 거리 (정규화 후 $[0,1]$)
- $D_{\text{elec}}$: 선택된 전기적 거리 (정규화 후 $[0,1]$)
- $w_{\text{geo}} + w_{\text{elec}} = 1$

### 거리공간 성질

| 성질 | 만족 여부 | 설명 |
|------|----------|------|
| **Non-negativity** | ✅ | 가중합 |
| **Identity of Indiscernibles** | ❌ | 정규화로 인해 $d(i,i) \neq 0$일 수 있음 |
| **Symmetry** | ✅ | 두 구성 요소 모두 대칭이므로 |
| **Triangle Inequality** | ❌ | 정규화로 인해 일반적으로 불성립 |

> **결론**: GeodesicElectricalHybrid는 정규화로 인해 **거리공간이 아닙니다**.

### 물리적 의미

- 전력망에서 지리적 위치와 전기적 특성은 **완전히 독립적이지 않습니다**.
  - 가까운 버스들은 일반적으로 짧은 선로로 연결되어 낮은 리액턴스(높은 서셉턴스)를 가짐
  - 긴 선로는 높은 리액턴스를 가지며 전기적으로도 먼 거리에 해당
- $w_{\text{geo}}$가 크면 **지리적 클러스터링**이 강조되고,
  $w_{\text{elec}}$가 크면 **전기적 특성**이 강조됩니다.
- 기본값: $w_{\text{geo}} = 0.3, w_{\text{elec}} = 0.7$ (전기적 특성 우선)

### 취약점 분석과의 관련성

- 지리적으로 가까운 선로들은 **동시에 고장 날 물리적 위험**(태풍, 지진 등)이 있습니다.
- 전기적으로 취약한 선로들이 항상 지리적으로 가까운 것은 아니므로,
  $w_{\text{geo}}$를 너무 높게 설정하면 **전기적 취약점 탐지 성능이 저하**될 수 있습니다.
- 극단적으로 긴 선로(예: Ukraine 18-bus의 Dnipro-Kharkiv 연결)는 지리적 거리는
  크지만 전기적 중요성이 큰 특수 사례로, 이 혼합 거리에서 잘 포착될 수 있습니다.

---

## 10. Geographic (Euclidean) Distance

### 수학적 정의

$$d(i,j) = \sqrt{(x_i - x_j)^2 + (y_i - y_j)^2}$$

### 거리공간 성질

| 성질 | 만족 여부 |
|------|----------|
| **Non-negativity** | ✅ |
| **Identity of Indiscernibles** | ✅ |
| **Symmetry** | ✅ |
| **Triangle Inequality** | ✅ |

> **결론**: Geographic Distance는 **완전한 거리공간**입니다. (표준 유클리드 거리)

### 물리적 의미

- 전력망의 **물리적 배치**만을 반영하며 전기적 특성은 전혀 고려하지 않습니다.
- 일반적으로 짧은 선로는 리액턴스가 작아 전력 전송 효율이 높습니다.
- 그러나 선로 한계치(rate)는 길이와 직접적인 상관관계가 없을 수 있습니다.

### 취약점 분석과의 관련성

- **비교 기준(baseline)** 으로만 사용됩니다.
- 전기적 특성을 전혀 반영하지 않으므로 취약점 탐지 성능이 가장 낮을 것으로 예상됩니다.
- `compare_metrics.py`에서 Geographic distance는 alignment score가
  가장 낮을 것으로 기대되며, 이는 **"전기적 거리함수를 사용하는 의미"** 를
  입증하는 근거가 됩니다.

---

## 11. 거리공간 성질 비교 요약

| 거리함수 | Non-negativity | Identity | Symmetry | Triangle Inequality | **완전한 거리공간?** |
|----------|:--------------:|:--------:|:--------:|:-------------------:|:-------------------:|
| **PTDFVector (L1/L2)** | ✅ | ✅ | ✅ | ✅ | **✅** |
| **EffectiveResistance** | ✅ | ✅ | ✅ | ✅ | **✅** |
| **Bus LODF Sensitivity** | ✅ | ⚠️ (약함) | ✅ | ✅ | **⚠️ (실질적) ✅** |
| **PTDF Inverse** | ✅ | ❌ | ✅ | ❌ | **❌** |
| **LODF Inverse** | ✅ | ✅ | ✅ | ✅ | **✅** |
| **KCL Current** | ✅ | ✅ | ✅ | ✅ | **✅** |
| **Hybrid** | ✅ | ❌ | ✅ | ❌ | **❌** |
| **Geo-Elec Hybrid** | ✅ | ❌ | ✅ | ❌ | **❌** |
| **Geographic (Euclidean)** | ✅ | ✅ | ✅ | ✅ | **✅** |

> **범례**: ✅ 만족 / ❌ 불만족 / ⚠️ 조건부 만족

### 완전한 거리공간의 중요성

비에토리스-립스 복합체는 거리공간의 **삼각부등식**에 의존하지 않습니다.
VR 복합체는 단순히 $d(i,j) \le \alpha$인 모든 에지를 추가하므로,
pseudometric만 있어도 구성이 가능합니다.

그러나 **지속성 호몰로지의 해석** 측면에서는 완전한 거리공간이 유리합니다:
- 삼각부등식이 성립하면 H₁ 사이클의 birth/death threshold가 물리적으로 의미 있음
- 거리공간이 아닌 경우 birth/death의 해석이 모호해짐

---

## 12. 취약점 분석과의 연결

### 핵심 가설: "왜 지속성 호몰로지로 취약점을 찾을 수 있는가?"

```
전력망의 버스들 사이에 전기적 거리를 정의한다
   ↓
VR 복합체를 구성한다
   ↓
지속성 호몰로지로 H₁ 사이클을 추출한다
   ↓
H₁ 사이클을 구성하는 선로들이 N-1 취약 선로일 가능성이 높다
```

### 이 가설이 성립하는 물리적 이유

1. **H₁ 사이클 = 대체 경로의 존재**
   - 전력망에서 H₁ 사이클은 **폐로(loop) 구조**를 나타냅니다.
   - 폐로 구조는 한 선로가 고장 나도 전력을 우회하여 공급할 수 있는
     **대체 경로(alternate path)** 를 제공합니다.
   - 그러나 이 대체 경로를 통해 흐르는 전력이 기존 선로의 한계치를 초과하면
     **연쇄 과부하(cascading overload)** 가 발생합니다.

2. **거리함수와 취약점의 관계**

   | 거리함수 | 포착하는 현상 | 취약점과의 연결 |
   |----------|-------------|----------------|
   | PTDFVector | 유사한 전력 흐름 민감도 | 같은 전력 변화를 경험하는 버스들의 고리 → 동시 과부하 위험 |
   | EffectiveResistance | 강한 전기적 결합 | 결합이 강할수록 고장 영향이 큼 |
   | Bus LODF Sensitivity | 유사한 고장 반응 패턴 | 동일 고장에 함께 취약해짐 |
   | **LODF Inverse** | **유사한 고장 전파 경험** | **가장 직접적인 N-1 취약점 포착** |
   | KCL Current | 유사한 전류 분포 | 동일 전류 경로 공유 → 과부하 전파 |

3. **LODF Inverse Distance가 가장 유망한 이유**
   - LODF는 **직접적으로 N-1 사고의 영향**을 정량화합니다.
   - LODF의 유사역행렬을 통해 정의된 거리는 **N-1 고장 공간에서의
     버스 위치**를 나타냅니다.
   - 따라서 이 거리공간의 H₁ 사이클은 **N-1 사고와 가장 직접적인 연관성**을 가집니다.
   - 이는 `project objective.txt`에서 언급된 "가장 가능성 있는 계획"과 일치합니다.

### 실험적 검증 (Ukraine 18-bus 예비 결과)

`scripts/compare_metrics.py`를 통해 Ukraine 18-bus 그리드에서
8개 메트릭을 비교한 결과:

```
PTDF Vector (L2) → alignment 0.9600 (★ 최고)
```

N-1 취약 분석 결과 모든 25개 선로가 취약한 것으로 나타나(100%),
alignment score의 변별력이 제한적이었습니다. 더 현실적인 rate 조건이나
다양한 그리드에서의 추가 실험이 필요합니다.

---

## 부록: 수학적 상세

### A. PTDF의 수학적 유도

DC 조류계산에서:

$$P = B'\theta$$

버스 $i$에 1 p.u. 주입 시:

$$\theta = (B')^{-1} e_i$$

선로 $l$의 전력 흐름:

$$P_l = b_l \cdot (C[l,:] \cdot \theta) = b_l \cdot C[l,:] \cdot (B')^{-1} \cdot e_i$$

따라서:

$$PTDF[l,i] = b_l \cdot C[l,:] \cdot (B')^{-1} \cdot e_i$$

행렬 형태:

$$PTDF = \text{diag}(b) \cdot C \cdot (B')^{-1}$$

### B. LODF의 수학적 유도

선로 $k$ 고장 시, 이는 버스 $f_k$와 $t_k$ 사이에
$\Delta P = -P_k$ (원래 흐름만큼 반대 방향)의 주입과 동일:

$$\Delta P = -P_k \cdot (e_{f_k} - e_{t_k})$$

이 주입의 영향:

$$\Delta P_l = PTDF[l,:] \cdot \Delta P = PTDF[l,:] \cdot (-P_k \cdot (e_{f_k} - e_{t_k}))$$

$$= -P_k \cdot (PTDF[l,f_k] - PTDF[l,t_k])$$

선로 $k$ 자신의 영향:

$$\Delta P_k = -P_k \cdot (PTDF[k,f_k] - PTDF[k,t_k])$$

고장 후 선로 $k$의 새로운 흐름은 0이 되어야 하므로:

$$P_k + \Delta P_k = P_k - P_k \cdot (PTDF[k,f_k] - PTDF[k,t_k]) = 0$$

이로부터 LODF 정의:

$$LODF[l,k] = \frac{PTDF[l,f_k] - PTDF[l,t_k]}{1 - (PTDF[k,f_k] - PTDF[k,t_k])}$$

### C. Effective Resistance와 PTDF의 관계

유효 저항:

$$R_{\text{eff}}(i,j) = (e_i - e_j)^T \cdot L^+ \cdot (e_i - e_j)$$

여기서 $L = C^T \cdot \text{diag}(b) \cdot C$이므로:

$$R_{\text{eff}}(i,j) = \sum_{l} \frac{(C[l,:] \cdot (e_i - e_j))^2}{b_l}$$

DC 조류계산에서 $PTDF = \text{diag}(b) \cdot C \cdot (B')^{-1}$이고,
$B'$와 $L$의 관계를 이용하면:

$$R_{\text{eff}}(i,j) = \sum_{l} \frac{(PTDF[l,i] - PTDF[l,j])^2}{b_l}$$

즉, **Effective Resistance는 PTDF Vector Distance (L2)의
서셉턴스 가중 제곱 버전**입니다.

