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
