# DCA 範例 4:目標函數出現「非線性項」時,MILP 解不了 —— 用 DCA 處理
#
# 執行方式:
#   ~/.venv/bin/python dca_example.py
#
# 情境:
#   沿用範例 1 的 job 指派問題,但加一個真實的非線性需求 ——「整併加分」:
#   job 集中到少數 host 可以省電、減少資源碎片,所以 host 負載越集中越好。
#   目標改成
#       maximize  Σ priority[j]·x[j][h]  +  w · Σ_h load[h]^2
#   其中 load[h] = Σ_j slots[j]·x[j][h]。
#   load^2 是「凸函數」,放在 maximize 裡整個問題就變成非凸、非線性,
#   線性求解器(CBC)直接拒收 —— 這就是「模型不再線性」的情形。
#
# DCA(Difference-of-Convex Algorithm)的想法:
#   把目標寫成「凸 − 凸」兩塊(min −F = (−Σp·x) − (w·Σload^2),兩塊都凸),
#   每一輪把後面那塊在目前解 x_k 附近「線性化」(切平面):
#       load[h]^2  ≈  2·L_k[h]·load[h] − L_k[h]^2      (L_k = 上一輪的負載)
#   線性化之後子問題就是普通 MILP,交給 CBC 解,解完更新 L_k 再來一輪。
#   因為切平面永遠低估凸函數,每一輪目標值保證不變差,幾輪內就收斂。
#   代價:DCA 只保證「局部最優」,所以最後用暴力枚舉驗證這次有沒有拿到全域最優。
#
# 同一套配方也能直接套到範例 3(milp_schedule.py)的時間軸模型:
#   任何「凸項放錯邊」的非線性目標(整併、能耗、拖延懲罰平方…)都照樣
#   線性化 → 解 MILP → 迭代。
#
# 模型(每一輪的 MILP 子問題):
#   變數    x[j][h] ∈ {0,1}
#   目標    maximize Σ p[j]·x[j][h] + w · Σ_h 2·L_k[h]·(Σ_j slots[j]·x[j][h])
#   限制    與範例 1 相同(每 job ≤ 1 台、host slot 容量、license 總量)

import itertools
import pulp

# ---------- 資料(host / license 與範例 1 相同,job 需求略調,
#             讓 DCA 的逐輪改善過程看得見) ----------
jobs = {
    #  名稱: (優先權, 需要 slots, 需要 license)
    "J1": (10, 4, 1),
    "J2": (8, 2, 2),
    "J3": (6, 3, 0),
    "J4": (5, 2, 1),
    "J5": (3, 1, 1),
}

hosts = {
    #  名稱: slot 容量
    "H1": 8,
    "H2": 4,
    "H3": 4,
}

TOTAL_LICENSES = 3

W = 0.2  # 整併加分的權重:0.2 × load^2,load 最大 8 → 一台最多加 12.8 分

# ---------- 工具 ----------
def loads_of(assign):
    """assign: {job: host or None} → 各 host 的 slot 負載"""
    load = {h: 0 for h in hosts}
    for j, h in assign.items():
        if h is not None:
            load[h] += jobs[j][1]
    return load

def true_objective(assign):
    """真正的非線性目標值:優先權總分 + w·Σ load^2"""
    load = loads_of(assign)
    prio = sum(jobs[j][0] for j, h in assign.items() if h is not None)
    return prio + W * sum(v * v for v in load.values())

def feasible(assign):
    load = loads_of(assign)
    if any(load[h] > hosts[h] for h in hosts):
        return False
    lic = sum(jobs[j][2] for j, h in assign.items() if h is not None)
    return lic <= TOTAL_LICENSES

# ---------- DCA 主迴圈 ----------
def solve_subproblem(L_k):
    """把 load^2 在 L_k 線性化後的 MILP 子問題"""
    prob = pulp.LpProblem("dca_subproblem", pulp.LpMaximize)
    x = pulp.LpVariable.dicts(
        "x", [(j, h) for j in jobs for h in hosts], cat=pulp.LpBinary
    )
    load_expr = {
        h: pulp.lpSum(jobs[j][1] * x[(j, h)] for j in jobs) for h in hosts
    }
    # 線性化:load^2 → 2·L_k·load(常數項 −L_k^2 不影響 argmax,省略)
    prob += (
        pulp.lpSum(jobs[j][0] * x[(j, h)] for j in jobs for h in hosts)
        + W * pulp.lpSum(2 * L_k[h] * load_expr[h] for h in hosts)
    )
    for j in jobs:
        prob += pulp.lpSum(x[(j, h)] for h in hosts) <= 1, f"one_host_{j}"
    for h in hosts:
        prob += load_expr[h] <= hosts[h], f"capacity_{h}"
    prob += (
        pulp.lpSum(jobs[j][2] * x[(j, h)] for j in jobs for h in hosts)
        <= TOTAL_LICENSES,
        "licenses",
    )
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    assign = {}
    for j in jobs:
        placed = [h for h in hosts if x[(j, h)].value() > 0.5]
        assign[j] = placed[0] if placed else None
    return assign

# 第 0 輪:L_k 全 0,子問題就是範例 1 的原始 MILP(只看優先權)
L_k = {h: 0 for h in hosts}
prev_obj = None
print("DCA 迭代過程:")
for it in range(1, 21):
    assign = solve_subproblem(L_k)
    obj = true_objective(assign)
    L_k = loads_of(assign)
    detail = "  ".join(f"{h}:{L_k[h]}" for h in hosts)
    print(f"  第 {it} 輪: 真目標值 = {obj:.1f}   負載 {detail}")
    if prev_obj is not None and obj <= prev_obj + 1e-9:
        print("  目標值不再進步,收斂")
        break
    prev_obj = obj

# ---------- 結果 ----------
print()
print("DCA 最終解:")
for j in jobs:
    h = assign[j]
    where = h if h is not None else "放棄(資源不足)"
    print(f"  {j} (優先權 {jobs[j][0]:>2}) -> {where}")
load = loads_of(assign)
for h in hosts:
    print(f"  {h}: 使用 {load[h]}/{hosts[h]} slots")
print(f"  真目標值(優先權 + {W}·Σload²): {true_objective(assign):.1f}")

# ---------- 驗證:暴力枚舉全域最優 ----------
# 5 個 job、每個有 4 種去處(3 台 host 或放棄)→ 4^5 = 1024 種組合,直接列舉
best_obj, best_assign = -1.0, None
for combo in itertools.product([None, *hosts], repeat=len(jobs)):
    cand = dict(zip(jobs, combo))
    if feasible(cand) and true_objective(cand) > best_obj:
        best_obj, best_assign = true_objective(cand), cand

print()
print(f"暴力枚舉的全域最優值: {best_obj:.1f}")
if abs(best_obj - true_objective(assign)) < 1e-9:
    print("→ DCA 這次找到的就是全域最優")
else:
    print("→ DCA 落在局部最優(DCA 只保證不變差,不保證全域;"
          "實務上會多試幾個起點)")
    for j in jobs:
        h = best_assign[j]
        print(f"  全域最優:{j} -> {h if h else '放棄'}")
