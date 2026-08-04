我幫你整理成一個比較像研究筆記的形式。我會刻意**不談 MILP 和公式**，只整理思考脈絡，因為我覺得目前最重要的是先把研究方向釐清。

---

# License-aware Scheduling 的研究思考

## 一、問題的起點

一開始考慮的是一個非常簡單的模型：

> **一個 Job 對應一個 License。**

因此排程問題可以簡化成：

* 哪個 Job 先執行？
* 如何降低 License Peak？
* 如何降低 License Oscillation？

此時，每個 Job 的資源需求都是一個**數字 (scalar)**。

例如：

| Job | License Demand |
| --- | -------------- |
| A   | 1              |
| B   | 1              |
| C   | 1              |

---

## 二、問題的擴充

實際的 EDA 環境通常不是如此。

一個 Job 可能同時需要多種 License，例如：

| Job | VCS | PrimeTime | Calibre |
| --- | --- | --------- | ------- |
| A   | 2   | 0         | 1       |
| B   | 0   | 3         | 0       |
| C   | 1   | 1         | 2       |

這時，每個 Job 不再是一個數字，而是一個：

> **資源需求向量 (Resource Vector)**

例如

```
Job A = (2,0,1)

Job B = (0,3,0)

Job C = (1,1,2)
```

這代表排程問題開始從

> **Single Resource Scheduling**

轉變成

> **Multi-resource Scheduling**

---

# 三、研究思維的改變

以前的 Scheduler 想的是：

> 下一個要 dispatch 哪一個 Job？

現在開始變成：

> 下一批要 dispatch 哪一組 Job？

這是整個研究最大的轉折。

因為：

以前：

```
Queue

↓

選一個 Job

↓

Dispatch
```

現在：

```
Queue

↓

挑一組互補的 Jobs

↓

一起 Dispatch
```

Scheduler 不再只是排序（Ordering），而是在做：

> **Vector Composition（向量組合）**

---

# 四、可能的加速方法

## 方向一：Best Fit（資源填滿）

概念：

每次不是挑第一個 Job，而是挑：

> **最能利用目前剩餘資源的 Job。**

例如目前剩餘：

```
VCS = 5
PT = 8
Calibre = 2
```

Scheduler 找：

> 哪個 Job 最能填滿這些空間。

優點：

* 很快
* 容易實作
* Resource 增加時仍可使用

---

## 方向二：Dominant Resource

每個 Job 找出：

> 最主要消耗的 Resource。

例如：

```
CPU 20%

VCS 95%

PT 10%
```

Dominant Resource = VCS

Scheduler 可以：

* 分群
* 分類
* 根據主要資源安排 Dispatch

優點：

Resource 增加時不用修改核心演算法。

---

## 方向三：Resource Complement（互補）

不要找資源需求相似的 Job。

而是找：

> **互補的 Job。**

例如：

```
A=(4,0)

B=(0,3)
```

比

```
A=(4,0)

C=(5,1)
```

更適合同時執行。

因為：

```
(4,0)+(0,3)
```

通常比

```
(4,0)+(5,1)
```

更容易充分利用所有資源。

---

## 方向四：Job Clustering

先把 Queue 分群。

例如：

```
Simulation Jobs

Timing Jobs

DRC Jobs
```

或

```
High-VCS Jobs

High-PT Jobs

High-Calibre Jobs
```

再決定不同群之間如何交錯 Dispatch。

避免：

```
Simulation

Simulation

Simulation

Timing
```

造成單一 License 被瞬間耗盡。

---

## 方向五：Lookahead Scheduling

每次 Dispatch 前：

不要只看 Queue 第一個。

而是：

```
Queue 前 N 個
```

模擬：

```
如果 dispatch A？

如果 dispatch B？

如果 dispatch C？
```

選：

> 對整體 Resource 最好的方案。

這屬於：

> Greedy + Lookahead

速度通常比 MILP 快很多。

---

# 五、思考上的突破

我認為真正重要的不是：

> 一個 Job 有幾個 License。

而是：

> 一個 Job 是一個 Resource Vector。

因此 Scheduler 不應該一直思考：

> 下一個 Job 是誰？

而應該思考：

> 哪一組 Job 可以一起執行？

例如：

Capacity

```
(8,8)
```

Queue

```
A=(6,0)

B=(0,6)

C=(4,4)
```

傳統 Scheduler：

```
選 A
```

Vector Composition：

```
選 A+B
```

因為：

```
(6,0)+(0,6)
=(6,6)
```

比單獨挑一個 Job 更能利用系統資源。

---

# 六、Vector Composition 的核心概念

每個 Job 都是一個 Resource Vector。

例如：

```
CPU
Memory
VCS
PrimeTime
Calibre
...
```

Scheduler 的工作不是：

> 排序 Job。

而是：

> 從 Queue 中找出一組 Resource Vector，使它們的總和最符合目前系統可用資源。

因此，每一次 Dispatch，其實都是一個：

> **Subset Selection（子集合選擇）**

問題。

不是：

```
選一個 Job
```

而是：

```
選一組 Jobs
```

使得：

* Resource 利用率高
* License Peak 低
* License Oscillation 小
* Makespan 不惡化

---

# 七、我認為最值得研究的方向

如果把研究抽象化，我會把核心問題定義成：

> **License-aware Vector Composition Scheduling**

研究的重點不再是：

* 如何修改 MILP。
* 如何加入更多 Constraint。
* 如何從「一個 License」擴充到「兩個 License」。

而是：

> **如何在每一次 Dispatch 時，快速從 Queue 中挑選一組資源需求互補的 Jobs，使多種 License（甚至 CPU、Memory、GPU 等資源）都能保持高利用率，同時避免單一資源形成 Peak，且不顯著增加 Makespan。**

---

## 我最後補充一個我認為最重要的觀察

我覺得這份整理裡，真正有研究潛力的不是五個方法本身，而是**思考層級的改變**：

* **傳統排程**：Job 是排程單位，演算法負責決定「下一個執行誰」。
* **向量組合排程**：**Job Group** 才是排程單位，演算法負責決定「哪些工作應該一起被 dispatch」。

如果這個觀點成立，那五個方向（Best Fit、Dominant Resource、Resource Complement、Clustering、Lookahead）都可以被視為不同的**Job Group 建構策略**，而不是彼此競爭的演算法。這樣整個研究架構會更一致，也更容易隨著資源種類增加而擴充。

這就是這個方向最有趣、也是最困難的地方。

答案是：**License 限制不是例外，而是你在做 Vector Composition 時的邊界（Constraint）**。

也就是說，**License 不會推翻「挑一組 Job」這個想法，而是決定哪些組合是合法的。**

---

## 先看沒有 License 限制

假設 Capacity：

| Resource | Capacity |
| -------- | -------- |
| CPU      | 32       |
| Memory   | 64       |

Queue：

| Job | CPU | Memory |
| --- | --- | ------ |
| A   | 16  | 16     |
| B   | 16  | 32     |
| C   | 8   | 16     |

很容易就能找到一組最適合的。

---

## 加入 License 限制

現在變成

| Resource | Capacity |
| -------- | -------- |
| CPU      | 32       |
| Memory   | 64       |
| VCS      | 4        |
| PT       | 2        |

Queue：

| Job | CPU | Mem | VCS | PT |
| --- | --- | --- | --- | -- |
| A   | 16  | 16  | 3   | 0  |
| B   | 16  | 32  | 1   | 2  |
| C   | 8   | 16  | 2   | 0  |

你挑任何一組 Job，都必須滿足：

* CPU 不超過 32
* Memory 不超過 64
* VCS 不超過 4
* PT 不超過 2

所以 **License 已經變成 Resource Vector 的其中一維**。

---

## 真正改變的是「評分方式」

假設剩餘資源：

```text
CPU=32
Mem=64
VCS=4
PT=2
```

如果挑 A

剩：

```text
CPU=16
Mem=48
VCS=1
PT=2
```

這時再挑 C

VCS 會變成

```text
1-2=-1
```

不合法。

所以：

> **不是 A+C 不好，而是 A+C 根本不能形成合法組合。**

因此 Vector Composition 的第一步不是找最佳，而是**先過濾掉所有不合法的組合**。

---

# 我反而想到一件更重要的事

其實 Scheduler 不需要真的找「最佳組合」。

它可以分兩步：

## Step 1：建立 Candidate Set

從 Queue 中找出

> 可以放進目前剩餘 License 的 Job。

例如：

剩餘

```text
VCS=4
PT=2
```

Queue：

| Job | VCS | PT |
| --- | --- | -- |
| A   | 3   | 0  |
| B   | 5   | 0  |
| C   | 1   | 2  |
| D   | 2   | 1  |

先把 B 排除。

Candidate：

```text
A
C
D
```

---

## Step 2：再做 Composition

Candidate：

```text
A
C
D
```

不是選一個。

而是找：

```text
A+D
```

或

```text
C+D
```

哪個最好。

這樣搜尋空間瞬間小很多。

---

# 我甚至會更激進一點

如果 Queue 有

```text
5000 jobs
```

根本不用看全部。

只看：

例如

```text
Priority 前100名
```

或

```text
Waiting 最久100名
```

形成 Candidate。

然後只在這 100 個裡做 Vector Composition。

速度會快非常多。

---

# 我認為真正的研究問題可能變成這樣

不是：

> 如何找最佳的 Job 組合？

而是：

> **如何在 License 約束下，快速產生一組「足夠好」的 Job 組合？**

這和最佳化的思維不同。

它比較像搜尋（search）：

```text
Queue
    │
    ▼
License Feasible Filter
    │
    ▼
Candidate Jobs
    │
    ▼
Composition Strategy
(Best Fit / Complement / Lookahead...)
    │
    ▼
Dispatch Group
```

---

## 我最後想補充一個我剛剛想到的觀點

我覺得**License 本身不應該是你的研究核心**。

它比較像是**搜尋空間的剪枝（pruning）條件**。

真正有價值的是後面的 **Composition Strategy**：在所有符合 License 限制的候選工作中，如何快速找到一組彼此互補、能提高整體資源利用率的工作。

這樣的架構還有一個好處：如果未來新增 GPU、Memory、Storage 等限制，它們都只是多了幾個「可行性檢查」的條件，而你的 Composition 演算法本身不需要重寫，只需要接受更多資源維度即可。

我認為這種**「Feasibility Filter + Composition Strategy」的兩階段架構**，會比一開始就把所有限制揉進一個大型最佳化模型，更容易擴充，也更適合真實的 LSF 排程環境。

對，而且**你問到的是這個方向真正的核心問題**。

如果 Queue 有一萬個 Job：

```text
10000 Jobs
```

你如果想找

> 最佳組合

那基本上就是在解

> **Subset Selection / Knapsack**

複雜度很快就爆炸。

例如就算只是問：

> 「這 10000 個 Job 中，哪幾個一起 dispatch 最好？」

理論上組合數是

[
2^{10000}
]

完全不可能。

所以**真正的研究不是 Composition，而是 Fast Composition**。

---

## 我會把整個問題拆成三層

### 第一層：Filter（剪枝）

先不要看全部。

例如：

```
10000 Jobs

↓

只留下可能被 dispatch 的
```

可以怎麼剪？

例如：

* Priority 前 500
* Waiting Time 最久 500
* Runtime 最短 500
* 或者「目前 License 有機會跑的」

假設最後剩

```
300 Jobs
```

---

### 第二層：Grouping（分群）

300 個還是很多。

所以再分群。

例如依 License Pattern：

```
VCS-heavy

PT-heavy

Mixed

CPU-heavy
```

甚至可以用 clustering。

最後變成

```
20 群
```

---

### 第三層：Composition

最後只在：

```
20 Groups
```

裡找。

而不是：

```
10000 Jobs
```

---

## 我反而想到另一個更像 LSF 的做法

LSF 是 event-driven。

它不是每天晚上一次排完。

它通常是：

```
License 空出來一點

↓

Scheduler 被喚醒

↓

Dispatch 幾個 Job

↓

等待下一次事件
```

例如：

```
每次只 dispatch 5 個 Job
```

那問題就變了。

不是

> 從 10000 個挑 5000 個。

而是

> 從 10000 個裡挑 5 個。

搜尋空間瞬間小很多。

---

## 甚至可以用 Beam Search

例如：

先挑第一個。

剩下：

```
Top 10 候選
```

每一個再往下找。

一直保留：

```
Best 20 組
```

最後選最好。

這比暴力搜尋快很多。

---

## 我還想到一個很符合 HPC 的方法

很多 HPC Scheduler 根本不看全部 Queue。

它只看：

> **Window**

例如：

```
Queue

1~100
```

下一次：

```
50~150
```

或：

```
Priority Top 200
```

這叫做 **Candidate Window**。

原因很簡單：

**排程器不是在求全域最佳，而是在有限時間內做下一次 dispatch。**

所以 Window 是很合理的設計。

---

# 我覺得這裡反而出現了一個研究問題

我甚至不會問：

> 怎麼做 Composition？

我會問：

> **Candidate Window 應該多大？**

例如：

Window = 20

速度超快。

但品質不好。

Window = 500

品質很好。

但慢。

Window = 100

可能剛剛好。

這其實就是一個可以研究的 trade-off。

---

## 我現在突然想到一個可能比演算法本身更有趣的研究主題

整個架構其實可以變成：

```
Waiting Queue (10000 jobs)
          │
          ▼
Candidate Selection
(哪些值得考慮？)
          │
          ▼
Candidate Window (100~300 jobs)
          │
          ▼
Resource Composition
(怎麼組成一批？)
          │
          ▼
Dispatch
```

你會發現，**Composition 不一定是最難的**。

真正決定效率的，很可能是：

> **如何在極大的 Queue 中，用很低的成本挑出「值得思考」的 Candidate。**

這和資訊檢索（Information Retrieval）的概念有點像：不是先對所有資料做昂貴的排序，而是先快速召回一小批候選（retrieval），再做精細的排序（ranking）。

---

### 我反而想挑戰一個假設

我們剛才一直假設「要從 Queue 裡找最好的一組」。但真實的 LSF 未必需要這樣。

更符合實務的問題可能是：

> **能不能在 10–50 毫秒內，找到一組比 FIFO 明顯好、但不一定是最佳的 Job？**

如果你的演算法能做到這點，而且在模擬器上證明它比 FIFO 或現有策略有更好的 Makespan、較低的 License Peak、較平滑的 License 使用曲線，那它就已經很有研究價值了。因為對實際的 scheduler 來說，**決策速度本身就是一項重要的性能指標**，不是只有排程品質。

