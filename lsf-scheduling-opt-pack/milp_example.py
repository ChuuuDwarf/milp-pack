# MILP 範例:把一批 job 指派到 host,最大化完成的優先權總分
#
# 注意:這是入門用的簡化模型 —— license 被當成一次性總量,搶不到就「放棄」。
# 真實 LSF 裡 license 是同一時刻的併發上限,job 跑完會釋放、搶不到的 job 會等,
# 符合真實情況的版本見 milp_schedule.py(範例 3)。
#
# 執行方式:
#   ~/.venv/bin/python milp_example.py
#
# 模型:
#   變數    x[j][h] ∈ {0,1}   job j 是否指派到 host h
#   目標    maximize Σ priority[j] * x[j][h]
#   限制    (1) 每個 job 最多指派到一台 host
#           (2) 每台 host 的 slot 用量不得超過容量
#           (3) 全站 license 用量不得超過總量

import pulp

# ---------- 資料 ----------
jobs = {
    #  名稱: (優先權, 需要 slots, 需要 license)
    "J1": (10, 4, 1),
    "J2": (8, 2, 2),
    "J3": (6, 6, 0),
    "J4": (5, 3, 1),
    "J5": (3, 1, 1),
}

hosts = {
    #  名稱: slot 容量
    "H1": 8,
    "H2": 4,
    "H3": 4,
}

TOTAL_LICENSES = 3

# ---------- 建模 ----------
prob = pulp.LpProblem("job_placement", pulp.LpMaximize)

# 二元變數:x[(j, h)] = 1 表示 job j 放在 host h
x = pulp.LpVariable.dicts(
    "x", [(j, h) for j in jobs for h in hosts], cat=pulp.LpBinary
)

# 目標函數:被指派的 job 優先權總和最大
prob += pulp.lpSum(jobs[j][0] * x[(j, h)] for j in jobs for h in hosts)

# 限制 1:每個 job 最多放在一台 host
for j in jobs:
    prob += pulp.lpSum(x[(j, h)] for h in hosts) <= 1, f"one_host_{j}"

# 限制 2:host slot 容量
for h in hosts:
    prob += (
        pulp.lpSum(jobs[j][1] * x[(j, h)] for j in jobs) <= hosts[h],
        f"capacity_{h}",
    )

# 限制 3:license 總量
prob += (
    pulp.lpSum(jobs[j][2] * x[(j, h)] for j in jobs for h in hosts)
    <= TOTAL_LICENSES,
    "licenses",
)

# ---------- 求解 ----------
status = prob.solve(pulp.PULP_CBC_CMD(msg=False))  # msg=True 可看求解器過程

# ---------- 結果 ----------
print(f"求解狀態: {pulp.LpStatus[status]}")
print(f"目標值(完成的優先權總分): {pulp.value(prob.objective):.0f}")
print()

used_slots = {h: 0 for h in hosts}
used_lic = 0
for j in jobs:
    placed = [h for h in hosts if x[(j, h)].value() > 0.5]
    if placed:
        h = placed[0]
        used_slots[h] += jobs[j][1]
        used_lic += jobs[j][2]
        print(f"  {j} (優先權 {jobs[j][0]:>2}) -> {h}")
    else:
        print(f"  {j} (優先權 {jobs[j][0]:>2}) -> 放棄(資源不足)")

print()
for h in hosts:
    print(f"  {h}: 使用 {used_slots[h]}/{hosts[h]} slots")
print(f"  license: 使用 {used_lic}/{TOTAL_LICENSES}")
