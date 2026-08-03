---
name: lsf-scheduling-opt
description: Use when solving LSF/cluster job scheduling or resource allocation problems in this project — makespan, license/session limits, slots, preemption, mode choice (session vs array), nonlinear objectives, or verifying a schedule is optimal. Triggers: 排程, 最佳化, makespan, license, 搶佔, preempt, MILP, DCA, pulp.
---

# LSF 排程最佳化工作流程

## 核心原則

先判斷**問題的形狀**再選工具;答案一定要**驗證**,不能只看跑得出來。

## 方法選擇(決策樹)

| 問題形狀 | 用什麼 | 範本檔案 |
|---|---|---|
| 目標與限制全是線性 | MILP(pulp + CBC),保證全域最優 | `milp_example.py`、`milp_makespan.py` |
| 資源是「同一時刻的併發上限」(license/slots 會釋放) | 時間離散化 MILP:變數=「job 在時間 t 於 host h 開始」 | `milp_schedule.py` |
| 非線性,但來自**離散選項**(session vs array、模式選擇、「有無」開關) | 開關變數 + 查表 → 仍是 MILP,保證最優,**不需要 DCA** | `milp_session_preempt.py`、`milp_mode_choice.py` |
| 非線性(凸−凸結構;純凸/凹項是其特例)+ **小題目** | 查表直線化 exact MILP,直接拿 Optimal 證書 | `dca_milp_workflow.py` 第 1 部(檔名有 dca,但第 1 部走的是「免 DCA」的 MILP 路線) |
| 非線性 + **大題目**(exact MILP 在時限內解不完) | DCA 多起點換速度 + 隨機小題目用 MILP 抽驗品質 | `dca_example.py`、`dca_milp_workflow.py` |
| **線性但大題目**(組合爆炸,時限內解不完) | `timeLimit` 拿「目前最好 + gap」自行判斷夠不夠好;或貪婪/啟發式 + 抽驗 | `dca_milp_workflow.py` 第 3 部(同概念) |
| 政策模糊、口語化、事件驅動臨場決策 | LLM 大腦(LangGraph 迴圈 + 模擬器)+ 程式防呆把關 | `lsf_ai_scheduler.py` |

**兩個獨立的軸,依序問**:

1. **形狀(決定怎麼建模)**:關係線性嗎?注意很多「看起來非線性」的關係可以**精確改寫成線性**:max/makespan → 引入 T 逐條 `≤ T`;階梯/有無 → 0/1 開關;離散選項或小整數值域的函數 → 查表。0/1 變數本身**不是**非線性——MILP 的難來自整數組合爆炸,不是非線性。真改寫不了(連續非凸、查表開關會爆炸)才走 DCA。
2. **規模(決定怎麼求解)**:不管線不線性,整數組合爆炸都可能讓 exact MILP 解不完。判別不用猜——設 `timeLimit`(例如 20 秒)試解:`Optimal` 且沒用滿時間 → 用它拿證書;用滿時間 → 換快的方法(有凸−凸結構 → DCA 多起點;否則貪婪/啟發式),並用小題目抽驗品質。經驗值:約 50 jobs × 10 hosts(500+ 個 0/1 變數 + 查表開關)CBC 就可能撞牆。

所有範本檔案都在**專案根目錄**(與本 skill 的 `.claude/` 同層)。

## 建模招式速查

- **時間軸**:切成 STEP 分鐘一格;確認 job 時間都是 STEP 倍數、HORIZON 蓋得住最壞情況。
- **搶佔**:用「每格是否在跑」變數,可斷開=允許搶佔;加「只准開始一次」=禁止。LSF 是原地 SUSP/RESUME,不搬家。
- **階梯/查表非線性**:整數值域小 → 開關變數 z[k]=「值剛好是 k」,函數值查表 Σf(k)·z。
- **license vs session 語意(比照 lsf-sim 模擬器,cluster.py)**:
  - license(`rusage_shared`)= 全域池,每個 job 扣一次、整個生命週期抓著(**SUSP 也不放**)、結束才還;session 父 job 只算一個 job → 整段吃一份。建模:life[i][t] 連續區間 0/1 變數(蓋住 SUSP 空檔),Σ lic·life ≤ 總數。
  - session = **分配 slot 的模式**(不是一種 license):彈性 n_min 起跑、有空位就吸到上限 n、task 沒排完不放、尾聲逐格釋放、slot 可跨 host。建模:active[t] 連續一段 + 寬度 k[h][t](Σk = task 數,task 時長=STEP 時一格一 slot 做一個 task)。彈性 session 不可被搶佔。
  - **搶佔只釋放 slot,不釋放 license**——別假設 SUSP 會讓出 lic。
- **可行性預檢**:單一 job 需求超過全站上限 → 先擋下並指名,別讓整個模型無解。

## 驗證清單(每次都做)

1. 求解狀態必須是 `Optimal`(這是全域最優的數學證書);設了 `timeLimit` 且用滿時間 → 證書不可信,只是「目前最好」。
2. 手算下界對照(總工作量÷容量、瓶頸資源串列時間);答案貼著下界 = 鐵定最優。
3. 小題目暴力枚舉當第二意見;DCA 的答案必抽驗(它只保證局部最優)。
4. 用 assert 逐時間點檢查限制式——這驗「可行」,和「最優」是兩件事,都要做。
5. 模型 vs 現實的落差(STEP 粒度、HORIZON、簡化假設)要明講。

「拿到解之後怎麼驗」的可執行範本:`dca_milp_workflow.py` 的 `solve_exact()`(證書)與第 2 部(抽驗迴圈)、`dca_example.py` 結尾的暴力枚舉、`milp_schedule.py` / `milp_session_preempt.py` 結尾的逐時間點 assert。

## 常見錯誤

- 把 license 當一次性總量、搶不到就「放棄」→ 真實是併發上限,job 要排隊等。
- DCA 只跑單一起點 → 至少 3 起點(全零 + 隨機)。
- LLM 大腦的輸出直接執行 → 必須有防呆層驗證動作合法性。

## 環境

執行一律用 `~/.venv/bin/python`(pulp、langgraph、anthropic 都在此 venv;系統 python3 看不到)。完整脈絡見 `README_排程學習筆記.md`。
