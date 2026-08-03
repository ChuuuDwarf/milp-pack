# LSF 排程最佳化學習筆記：從數學模型到 MILP、DCA 與 AI Agent

## 研究主軸

本專案不是研究 MILP、DCA 或 LLM 本身，而是研究：

> **License-Constrained LSF Scheduling**

也就是在 CPU、Host、License、Session 等多重資源限制下，尋找 **Makespan 最短**的排程。

整體研究流程：

```text
真實 LSF 問題
        │
        ▼
建立數學模型
        │
        ▼
理論分析
 (Complexity / Lower Bound / Properties)
        │
        ▼
MILP（Exact Solver）
        │
        ▼
DCA（Large-scale Solver）
        │
        ▼
Simulator（驗證）
        │
        ▼
LLM Scheduler（線上決策）
```

## Step 1 建立數學模型（Mathematical Model）

先將 LSF 抽象成排程模型。

每個 Job 定義：

- Processing Time
- License Requirement
- Slot Requirement
- Session Mode
- Priority
- Host Constraint

系統資源包含：

- CPU Slots
- License Pool
- Hosts
- Session Rules
- Preemption Rules

目標：

> **Minimize Makespan**

---

## Step 2 理論分析（Theoretical Analysis）

先分析問題，而不是先求解。

### Problem Complexity

分析問題與 Parallel Machine Scheduling 的關係，說明大型問題具有 NP-hard 性質，因此需要 Heuristic 或 Approximation。

### Lower Bound

建立 Makespan 的理論下界，例如：

- CPU Lower Bound
- License Lower Bound
- Host Lower Bound

最後：

```text
LB = max(LB_cpu, LB_license, LB_host)
```

實驗時主要比較：

```text
Makespan / Lower Bound
```

而不是只比較 Makespan。

### Scheduling Properties

分析演算法的重要性質，例如：

- Work-Conserving
- 無不必要 License Idle
- Session License 不重複 Checkout
- Packing 不增加 Checkout 次數

Simulator 用來驗證上述性質。

---

## Step 3 MILP（Exact Solver）

MILP 的定位：

- 小規模最佳解
- Optimal Certificate
- Ground Truth
- 驗證其他演算法

---

## Step 4 DCA（Large-scale Solver）

DCA 的定位：

- 大規模近似求解
- 保持良好解品質
- 作為 MILP 的可擴展版本

小規模問題仍以 MILP 驗證。

---

## Step 5 Simulator（Validation Platform）

Simulator 不負責找最佳解，而是：

- 驗證 MILP
- 驗證 DCA
- 驗證 Lower Bound 是否緊密
- 驗證 Scheduling Properties
- 建立大型測試案例

因此 Simulator 是 Validation Platform，而不是 Solver。

---

## Step 6 LLM Scheduler（Online Scheduling）

LLM 用於未知未來工作的線上排程。

流程：

```text
LLM
  │
Decision
  ▼
MILP（必要時局部最佳化）
  │
  ▼
Simulator 驗證
```

---

## 方法定位

| 方法 | 角色 |
|------|------|
| 數學模型 | 定義問題 |
| 理論分析 | Complexity、Lower Bound、Properties |
| MILP | Exact Solver（Ground Truth） |
| DCA | Large-scale Solver |
| Simulator | Validation Platform |
| LLM | Online Decision Maker |

---

## 方法論總結

本專案的方法論不是「先做模擬，再找好的演算法」，而是：

> **先建立數學模型，再分析理論性質，接著利用 MILP 求得小規模最佳解，使用 DCA 求解大型問題，最後以 Simulator 驗證理論分析與演算法效能，並探索 LLM 作為線上排程決策者的可行性。**
