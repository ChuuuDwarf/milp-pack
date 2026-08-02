# MILP 範例 3:符合真實情況的排程 —— 資源是「同一時刻的併發上限」
#
# 執行方式:
#   ~/.venv/bin/python milp_schedule.py
#
# 前兩個範例的簡化與真實情況的差距:
#   範例 1(milp_example.py)  license 當成一次性總量,搶不到的 job 直接「放棄」
#                              → 真實 LSF 裡 job 是排隊等,license 用完會釋放
#   範例 2(milp_makespan.py)  完全沒有 slot / license 限制,等於資源無限
#
# 這個範例加入「時間軸」修正:
#   - 每個 job 有開始時間,佔用資源到跑完為止,跑完就釋放
#   - 每台 host 在「每個時間點」的 slot 併發用量 ≤ 容量
#   - 全站在「每個時間點」的 license 併發用量 ≤ 總量
#   - 所有 job 都要跑完(資源不夠就等,不是放棄),讓 makespan 最短
#
# 模型:
#   時間離散化成 STEP 分鐘一格,t = 0, 1, 2, ...
#   變數    s[j][h][t] ∈ {0,1}   job j 是否在時間格 t 於 host h 開始執行
#           T ≥ 0                makespan(分鐘)
#   目標    minimize T
#   限制    (1) 每個 job 恰好開始一次(選一台 host、一個開始時間)
#           (2) 每台 host、每個時間點:正在跑的 job 的 slot 加總 ≤ 容量
#           (3) 每個時間點:正在跑的 job 的 license 加總 ≤ 總量
#           (4) 每個 job 的完工時間 ≤ T

import sys
import pulp

# ---------- 資料 ----------
jobs = {
    #  名稱: (執行時間(分鐘), 需要 slots, 需要 license)
    "J1": (50, 4, 1),
    "J2": (30, 2, 2),
    "J3": (40, 6, 0),
    "J4": (20, 3, 1),
    "J5": (10, 1, 1),
    "J6": (25, 2, 1),
}

hosts = {
    #  名稱: slot 容量
    "H1": 8,
    "H2": 4,
    "H3": 4,
}

TOTAL_LICENSES = 3

STEP = 5  # 時間格大小(分鐘),job 時間都是 5 的倍數

# ---------- 可行性檢查 ----------
# 單一 job 的需求就超過全站上限的話,它永遠排不進去
# (真實 LSF 裡這種 job 會永遠 PEND),先擋下來而不是讓整個模型無解
for j, (dur, need_slot, need_lic) in jobs.items():
    if need_slot > max(hosts.values()):
        sys.exit(f"{j} 需要 {need_slot} slots,超過最大 host 容量 "
                 f"{max(hosts.values())},永遠排不進去")
    if need_lic > TOTAL_LICENSES:
        sys.exit(f"{j} 需要 {need_lic} 個 license,超過總量 "
                 f"{TOTAL_LICENSES},永遠排不進去")

# 時間軸長度上限:全部 job 依序跑完(最保守),一定排得下
horizon = sum(dur for dur, _, _ in jobs.values()) // STEP
dur_steps = {j: jobs[j][0] // STEP for j in jobs}

# ---------- 建模 ----------
prob = pulp.LpProblem("schedule_makespan", pulp.LpMinimize)

# s[(j, h, t)] = 1:job j 在時間格 t 於 host h 開始
# 只建「跑得完」的開始時間(t + 執行時間 ≤ horizon)
starts = [
    (j, h, t)
    for j in jobs
    for h in hosts
    for t in range(horizon - dur_steps[j] + 1)
]
s = pulp.LpVariable.dicts("s", starts, cat=pulp.LpBinary)

T = pulp.LpVariable("T", lowBound=0)
prob += T

# 限制 1:每個 job 恰好開始一次
for j in jobs:
    prob += (
        pulp.lpSum(s[(jj, h, t)] for (jj, h, t) in starts if jj == j) == 1,
        f"must_run_{j}",
    )

# job j 在 t 開始的話,佔用資源的時間格是 [t, t + dur_steps[j])
def running_at(j, h, tau):
    """回傳讓 job j 在時間格 tau「正在 host h 上跑」的所有開始時間變數"""
    return [
        s[(j, h, t)]
        for t in range(max(0, tau - dur_steps[j] + 1), tau + 1)
        if (j, h, t) in s
    ]

for tau in range(horizon):
    # 限制 2:每台 host 每個時間點的 slot 併發用量
    for h in hosts:
        prob += (
            pulp.lpSum(
                jobs[j][1] * v for j in jobs for v in running_at(j, h, tau)
            ) <= hosts[h],
            f"slots_{h}_t{tau}",
        )
    # 限制 3:每個時間點的 license 併發用量
    prob += (
        pulp.lpSum(
            jobs[j][2] * v
            for j in jobs
            for h in hosts
            for v in running_at(j, h, tau)
        ) <= TOTAL_LICENSES,
        f"licenses_t{tau}",
    )

# 限制 4:完工時間 ≤ T(每個 job 只有一個 s=1,所以線性加總就是它的完工時間)
for j in jobs:
    prob += (
        STEP * pulp.lpSum(
            (t + dur_steps[j]) * s[(jj, h, t)]
            for (jj, h, t) in starts if jj == j
        ) <= T,
        f"finish_{j}",
    )

# ---------- 求解 ----------
status = prob.solve(pulp.PULP_CBC_CMD(msg=False))

# ---------- 結果 ----------
print(f"求解狀態: {pulp.LpStatus[status]}")
print(f"makespan: {T.value():.0f} 分鐘")
print(f"(全部依序跑 = {sum(d for d, _, _ in jobs.values())} 分鐘)")
print()

schedule = {}  # j -> (host, 開始分鐘, 結束分鐘)
for (j, h, t) in starts:
    if s[(j, h, t)].value() > 0.5:
        schedule[j] = (h, t * STEP, t * STEP + jobs[j][0])

for j in jobs:
    h, beg, end = schedule[j]
    dur, need_slot, need_lic = jobs[j]
    print(f"  {j}: {h}  {beg:>3} ~ {end:>3} 分  "
          f"(slots {need_slot}, license {need_lic})")

# 驗證:掃過每個時間點,確認併發用量沒有超過上限
print()
print(f"每個時間點的併發用量(license 總量 {TOTAL_LICENSES}):")
makespan = int(T.value())
for tau_min in range(0, makespan, STEP):
    lic = sum(jobs[j][2] for j, (h, b, e) in schedule.items()
              if b <= tau_min < e)
    slot_use = {h: 0 for h in hosts}
    for j, (h, b, e) in schedule.items():
        if b <= tau_min < e:
            slot_use[h] += jobs[j][1]
    assert lic <= TOTAL_LICENSES
    assert all(slot_use[h] <= hosts[h] for h in hosts)
    bars = "  ".join(f"{h} {slot_use[h]}/{hosts[h]}" for h in hosts)
    print(f"  t={tau_min:>3}: license {lic}/{TOTAL_LICENSES}  {bars}")
