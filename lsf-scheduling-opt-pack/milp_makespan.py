# MILP 範例 2:所有 job 都要跑完,讓總完工時間(makespan)最短
#
# 注意:這是入門用的簡化模型 —— 沒有 slot / license 限制,等於資源無限。
# 加上「每個時間點的併發資源上限」的真實版本見 milp_schedule.py(範例 3)。
#
# 執行方式:
#   ~/.venv/bin/python milp_makespan.py
#
# 模型:
#   變數    x[j][h] ∈ {0,1}   job j 是否指派到 host h(二元變數)
#           T ≥ 0             總完工時間(連續變數)← 這就是 "Mixed" 的部分
#   目標    minimize T
#   限制    (1) 每個 job 必須指派到「恰好一台」host(不能放棄)
#           (2) 每台 host 的收工時間 = 分到的 job 執行時間加總,必須 ≤ T

import pulp

# ---------- 資料 ----------
jobs = {
    #  名稱: 執行時間(分鐘)
    "J1": 50,
    "J2": 30,
    "J3": 40,
    "J4": 20,
    "J5": 10,
    "J6": 25,
}

hosts = ["H1", "H2", "H3"]

# ---------- 建模 ----------
prob = pulp.LpProblem("makespan", pulp.LpMinimize)  # 注意:改成最小化

# 二元變數:job 放哪台
x = pulp.LpVariable.dicts(
    "x", [(j, h) for j in jobs for h in hosts], cat=pulp.LpBinary
)

# 連續變數:總完工時間
T = pulp.LpVariable("T", lowBound=0)

# 目標:讓總完工時間最短
prob += T

# 限制 1:每個 job 必須放在恰好一台 host(== 1,不是 <= 1)
for j in jobs:
    prob += pulp.lpSum(x[(j, h)] for h in hosts) == 1, f"must_run_{j}"

# 限制 2:每台 host 的工作時間加總不能超過 T
for h in hosts:
    prob += (
        pulp.lpSum(jobs[j] * x[(j, h)] for j in jobs) <= T,
        f"finish_time_{h}",
    )

# ---------- 求解 ----------
status = prob.solve(pulp.PULP_CBC_CMD(msg=False))

# ---------- 結果 ----------
print(f"求解狀態: {pulp.LpStatus[status]}")
print(f"總完工時間: {T.value():.0f} 分鐘")
print(f"(所有工作時間加總 = {sum(jobs.values())} 分鐘,"
      f"平均分給 {len(hosts)} 台的理論下限 = {sum(jobs.values())/len(hosts):.1f} 分鐘)")
print()

for h in hosts:
    assigned = [j for j in jobs if x[(j, h)].value() > 0.5]
    total = sum(jobs[j] for j in assigned)
    detail = " + ".join(f"{j}({jobs[j]})" for j in assigned)
    print(f"  {h}: {detail}  = {total} 分鐘")
