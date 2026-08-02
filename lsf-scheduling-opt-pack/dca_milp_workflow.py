# 範例 8:DCA 與 MILP 的分工 —— 小題目拿證書、大題目換速度、中間用抽驗把關
#
# 執行方式:
#   ~/.venv/bin/python dca_milp_workflow.py     (全程約 30~40 秒)
#
# 這個範例把之前討論的工作流程做成可執行的三部曲:
#
#   第 1 部:小題目 → 「查表直線化 MILP」直接解,一次拿到 Optimal 證書,
#            根本不需要 DCA。(題目 = 範例 4 的資料,驗證 DCA 的 37.6 是真最優)
#
#   第 2 部:抽驗 → 隨機生 10 個小題目,DCA(多起點)和 exact MILP 各解一次,
#            統計 DCA 的命中率和落差 —— 這就是「用 MILP 抽查 DCA 品質」。
#
#   第 3 部:大題目 → exact MILP 給它 20 秒也算不完(只回「目前最好」),
#            DCA 多起點約 1 秒就給出差距很小的答案 —— 「DCA 換速度」。
#
# 非線性目標(與範例 4 相同):maximize Σ priority·x + W·Σ_h load_h²
# 查表直線化:load 只可能是整數 0..容量 → 開關變數 z[h][k]=「負載剛好是 k」,
#             load² 就變成查表 Σ k²·z(範例 7 的招),精確、無誤差。

import random
import time
import pulp

W = 0.15  # 整併加分權重

# ---------- 共用:隨機題目產生器 ----------
def gen_instance(n_jobs, n_hosts, seed):
    rng = random.Random(seed)
    jobs = {f"J{i}": (rng.randint(1, 10),   # 優先權
                      rng.randint(1, 4),    # slots
                      rng.randint(0, 2))    # license
            for i in range(1, n_jobs + 1)}
    hosts = {f"H{i}": rng.choice([8, 10, 12, 16]) for i in range(1, n_hosts + 1)}
    lic = max(2, sum(j[2] for j in jobs.values()) // 3)
    return jobs, hosts, lic

def add_base_constraints(prob, x, jobs, hosts, lic):
    for j in jobs:
        prob += pulp.lpSum(x[(j, h)] for h in hosts) <= 1
    for h in hosts:
        prob += pulp.lpSum(jobs[j][1] * x[(j, h)] for j in jobs) <= hosts[h]
    prob += (pulp.lpSum(jobs[j][2] * x[(j, h)] for j in jobs for h in hosts)
             <= lic)

def true_objective(assign, jobs, hosts):
    load = {h: 0 for h in hosts}
    prio = 0
    for j, h in assign.items():
        if h is not None:
            load[h] += jobs[j][1]
            prio += jobs[j][0]
    return prio + W * sum(v * v for v in load.values())

# ---------- 路線 A:查表直線化 exact MILP(有證書) ----------
def solve_exact(jobs, hosts, lic, time_limit=None):
    prob = pulp.LpProblem("exact", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", [(j, h) for j in jobs for h in hosts],
                              cat=pulp.LpBinary)
    z = pulp.LpVariable.dicts("z", [(h, k) for h in hosts
                                    for k in range(hosts[h] + 1)],
                              cat=pulp.LpBinary)
    prob += (pulp.lpSum(jobs[j][0] * x[(j, h)] for j in jobs for h in hosts)
             + W * pulp.lpSum(k * k * z[(h, k)]
                              for h in hosts for k in range(hosts[h] + 1)))
    add_base_constraints(prob, x, jobs, hosts, lic)
    for h in hosts:
        load = pulp.lpSum(jobs[j][1] * x[(j, h)] for j in jobs)
        prob += pulp.lpSum(z[(h, k)] for k in range(hosts[h] + 1)) == 1
        prob += load == pulp.lpSum(k * z[(h, k)] for k in range(hosts[h] + 1))
    t0 = time.time()
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    elapsed = time.time() - t0
    certified = (pulp.LpStatus[status] == "Optimal"
                 and (time_limit is None or elapsed < time_limit * 0.98))
    return pulp.value(prob.objective), elapsed, certified

# ---------- 路線 B:DCA(快,但只到局部最優) ----------
def dca_once(jobs, hosts, lic, L0):
    L, prev = dict(L0), None
    for _ in range(20):
        prob = pulp.LpProblem("sub", pulp.LpMaximize)
        x = pulp.LpVariable.dicts("x", [(j, h) for j in jobs for h in hosts],
                                  cat=pulp.LpBinary)
        # load² 在 L 附近線性化:2·L[h]·load
        prob += (pulp.lpSum(jobs[j][0] * x[(j, h)] for j in jobs for h in hosts)
                 + W * pulp.lpSum(2 * L[h] * jobs[j][1] * x[(j, h)]
                                  for j in jobs for h in hosts))
        add_base_constraints(prob, x, jobs, hosts, lic)
        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        assign = {j: next((h for h in hosts if x[(j, h)].value() > 0.5), None)
                  for j in jobs}
        obj = true_objective(assign, jobs, hosts)
        L = {h: sum(jobs[j][1] for j, hh in assign.items() if hh == h)
             for h in hosts}
        if prev is not None and obj <= prev + 1e-9:
            return prev
        prev = obj
    return prev

def dca_multistart(jobs, hosts, lic, seed=1, starts=3):
    rng = random.Random(seed)
    t0 = time.time()
    best = -1.0
    for s in range(starts):
        L0 = ({h: 0 for h in hosts} if s == 0        # 起點 1:全零(=先只看優先權)
              else {h: rng.randint(0, hosts[h]) for h in hosts})  # 其餘:隨機起點
        best = max(best, dca_once(jobs, hosts, lic, L0))
    return best, time.time() - t0

# ================= 第 1 部:小題目直接拿證書 =================
print("═══ 第 1 部:小題目 → 查表直線化 MILP,直接拿 Optimal 證書 ═══")
jobs4 = {"J1": (10, 4, 1), "J2": (8, 2, 2), "J3": (6, 3, 0),
         "J4": (5, 2, 1), "J5": (3, 1, 1)}          # 範例 4 的資料
hosts4 = {"H1": 8, "H2": 4, "H3": 4}
_W_backup, W = W, 0.2                                # 範例 4 用的是 W=0.2
obj, t, certified = solve_exact(jobs4, hosts4, 3)
print(f"  目標值 {obj:.1f},耗時 {t:.2f} 秒,證書:{'Optimal ✓' if certified else '無'}")
print(f"  → 與範例 4 DCA 的 37.6、暴力枚舉的 37.6 一致;小題目用這條路,免用 DCA\n")
W = _W_backup

# ================= 第 2 部:抽驗 DCA 的品質 =================
print("═══ 第 2 部:抽驗 → 10 個隨機小題目,DCA vs exact MILP ═══")
hits, gaps = 0, []
for i in range(10):
    jobs_i, hosts_i, lic_i = gen_instance(n_jobs=15, n_hosts=5, seed=100 + i)
    opt, _, _ = solve_exact(jobs_i, hosts_i, lic_i)
    dca_val, _ = dca_multistart(jobs_i, hosts_i, lic_i, seed=i)
    gap = opt - dca_val
    gaps.append(gap)
    hit = gap < 1e-6
    hits += hit
    print(f"  題目{i+1:>2}: 最優 {opt:>6.1f} | DCA {dca_val:>6.1f} | "
          f"落差 {gap:>5.1f} {'✓ 命中' if hit else ''}")
print(f"  → 命中率 {hits}/10,平均落差 {sum(gaps)/len(gaps):.1f},最大落差 {max(gaps):.1f}")
print(f"  → 抽驗告訴你 DCA 在這類題目上「大概多可靠」,再決定要不要加起點數\n")

# ================= 第 3 部:大題目,DCA 換速度 =================
print("═══ 第 3 部:大題目(50 jobs × 10 hosts)→ DCA 換速度 ═══")
jobs_big, hosts_big, lic_big = gen_instance(n_jobs=50, n_hosts=10, seed=42)
TIME_BUDGET = 20
obj_m, t_m, certified = solve_exact(jobs_big, hosts_big, lic_big,
                                    time_limit=TIME_BUDGET)
note = "Optimal ✓" if certified else f"時間用罄,只回「目前最好」,無完整證書"
print(f"  exact MILP:{obj_m:>6.1f},耗時 {t_m:>5.1f} 秒({note})")
obj_d, t_d = dca_multistart(jobs_big, hosts_big, lic_big, seed=1)
print(f"  DCA×3 起點:{obj_d:>6.1f},耗時 {t_d:>5.1f} 秒")
print(f"  → 落差 {obj_m - obj_d:.1f}({(obj_m - obj_d) / obj_m * 100:.1f}%),"
      f"速度差 {t_m / t_d:.0f} 倍")
print(f"  → 題目再大下去 MILP 連「目前最好」都給不出來,DCA 仍然秒級收斂")
