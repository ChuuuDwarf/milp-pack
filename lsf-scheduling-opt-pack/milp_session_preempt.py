# MILP 範例 5:貼近真實 LSF 的排程 —— 彈性 session、license、搶佔(preempt)
#
# 執行方式:
#   ~/.venv/bin/python milp_session_preempt.py
#
# 語意完全比照 lsf-sim 模擬器(lsfsim/cluster.py):
#
# (1) license(rusage_shared)是獨立的全域資源:
#     每個 job「派發時扣一次、整個生命週期抓著、結束才歸還」。
#     session 父 job 算一個 job → 整個 session 不管跑幾個 task 都只吃一份。
#     ★ 被搶佔(SSUSP)時只釋放 host 資源(slot),license 照樣抓著
#       (cluster.py _preempt_for:「SSUSP frees HOST resources only;
#         shared (license) stay held」)—— 搶佔救得了 slot,救不了 license!
#
# (2) session 是「分配 slot」的模式(不是一種 license):
#     一個父 job 帶 n 個 slot 上限、n_min 起跑(彈性),裡面排一串 task;
#     有空位就一直吸(_elastic_grow)、task 還沒排完抓到就不放,
#     尾聲 task 排空才逐格釋放(「會一直拿、拿到不放、做完才放」)。
#     slot 可以跨 host 拼湊(alloc = [(host, k), ...])。
#     ※ 這裡的 MILP 讓 session 寬度 K[t] 自由變化 —— 這是彈性 session「能力
#       的上界」;模擬器的貪婪吸收是其中一種實際行為。
#
# (3) 搶佔(preempt):SSUSP 凍結剩餘時間、釋放 slot;RESUME 續跑。
#     彈性 session 不可被搶佔(cluster.py:elastic not preemptable)。
#
# 劇情安排(license 只有 2 份,好戲在這):
#     S  彈性 session(EDA):8 個 task 各 10 分,slot 上限 4、n_min=2,吃 1 份 lic
#     B  大 job:6 slots、40 分,吃 1 份 lic —— 全場只有 H1 塞得下
#     U  急件:6 slots、10 分,吃 1 份 lic,第 20 分到、40 分前必須完成,也只有 H1 塞得下
#     U 要上機得同時有「slot」和「lic」:slot 可以靠搶佔 B 騰出來,
#     但 B 被 SUSP 時 lic 不會放 —— 所以 lic 只能等 S 整個做完歸還。
#     排程器被迫讓 S「全速衝刺」(吸滿 4 slots 兩步跑完)早早還 lic。
#
# 模型(時間離散化,STEP=10 分鐘一格):
#   B/U:a[i][h] 指派、r[i][h][t] 執行中、life[i][t] 生命週期(連續一段,
#        涵蓋 SUSP 的空檔 → lic 在 SUSP 期間照樣被抓著)
#   S : active[t] session 活著(連續一段)、k[h][t] 在 host h 抓的 slot 數
#        Σ_t Σ_h k = task 總數(一格一個 slot 做完一個 10 分 task)
#   資源:每 (h,t) slot 容量;每 t 的 lic:Σ life·lic + active·lic ≤ 總數
#   目標:minimize makespan(+ 小懲罰:斷開次數、生命週期不要無謂拖長)

import pulp

STEP = 10          # 一格 10 分鐘
HORIZON = 12       # 排程視窗 120 分鐘

hosts = {"H1": 8, "H2": 4, "H3": 4}

TOTAL_LIC = 2      # license 總數(全域池,job 拿了直到結束才還,SUSP 不還)

# ---------- basic job(B、U) ----------
jobs = {
    #  名稱: 執行時間, slots, lic, 到達, deadline
    "B": dict(dur=40, slots=6, lic=1, release=0,  deadline=None),
    "U": dict(dur=10, slots=6, lic=1, release=20, deadline=40),
}
# ---------- 彈性 session(S) ----------
SESS = dict(tasks=8, task_dur=10, n=4, n_min=2, lic=1)
assert SESS["task_dur"] == STEP  # 一格剛好做完一個 task,寬度 K = 每格完成數

dur_steps = {i: jobs[i]["dur"] // STEP for i in jobs}

def valid_steps(i):
    lo = jobs[i]["release"] // STEP
    hi = HORIZON if jobs[i]["deadline"] is None else jobs[i]["deadline"] // STEP
    return range(lo, hi)

def valid_hosts(i):
    return [h for h in hosts if jobs[i]["slots"] <= hosts[h]]

# ---------- 建模 + 求解(preempt 開/關 各跑一次) ----------
def solve(preempt):
    prob = pulp.LpProblem("lsf_schedule", pulp.LpMinimize)

    # --- B/U:指派、執行、開始、生命週期 ---
    a, r, s, life, ls = {}, {}, {}, {}, {}
    for i in jobs:
        for h in valid_hosts(i):
            a[(i, h)] = pulp.LpVariable(f"a_{i}_{h}", cat=pulp.LpBinary)
            for t in valid_steps(i):
                r[(i, h, t)] = pulp.LpVariable(f"r_{i}_{h}_{t}", cat=pulp.LpBinary)
        for t in valid_steps(i):
            s[(i, t)] = pulp.LpVariable(f"s_{i}_{t}", cat=pulp.LpBinary)
            life[(i, t)] = pulp.LpVariable(f"life_{i}_{t}", cat=pulp.LpBinary)
            ls[(i, t)] = pulp.LpVariable(f"ls_{i}_{t}", cat=pulp.LpBinary)

    # --- S:session 活著 + 各 host 抓的 slot 數 ---
    active = pulp.LpVariable.dicts("act", range(HORIZON), cat=pulp.LpBinary)
    sst = pulp.LpVariable.dicts("sst", range(HORIZON), cat=pulp.LpBinary)
    k = pulp.LpVariable.dicts(
        "k", [(h, t) for h in hosts for t in range(HORIZON)],
        lowBound=0, cat=pulp.LpInteger)

    T = pulp.LpVariable("T", lowBound=0)
    prob += (T + 0.01 * pulp.lpSum(s.values())
             + 0.005 * pulp.lpSum(life.values())
             + 0.005 * pulp.lpSum(active.values()))

    def z(i, t):  # 任務 i 在 t 是否在跑(跨 host)
        return pulp.lpSum(r[(i, h, t)] for h in valid_hosts(i) if (i, h, t) in r)

    for i in jobs:
        prob += pulp.lpSum(a[(i, h)] for h in valid_hosts(i)) == 1
        for h in valid_hosts(i):
            for t in valid_steps(i):
                prob += r[(i, h, t)] <= a[(i, h)]
        prob += pulp.lpSum(r[(i, h, t)] for h in valid_hosts(i)
                           for t in valid_steps(i)) == dur_steps[i]
        steps = list(valid_steps(i))
        for idx, t in enumerate(steps):
            z_prev = z(i, steps[idx - 1]) if idx > 0 else 0
            prob += s[(i, t)] >= z(i, t) - z_prev
            # 生命週期:蓋住所有執行格,而且是「連續一段」
            # → SUSP 的空檔也算活著 → lic 在空檔照樣被抓(比照模擬器)
            prob += life[(i, t)] >= z(i, t)
            l_prev = life[(i, steps[idx - 1])] if idx > 0 else 0
            prob += ls[(i, t)] >= life[(i, t)] - l_prev
        prob += pulp.lpSum(ls[(i, t)] for t in steps) <= 1   # 生命只有一段
        if not preempt:
            prob += pulp.lpSum(s[(i, t)] for t in steps) <= 1  # 不准斷開

    # --- session 限制 ---
    for t in range(HORIZON):
        K = pulp.lpSum(k[(h, t)] for h in hosts)
        prob += K <= SESS["n"] * active[t]          # 活著才抓,最多 n
        prob += K >= active[t]                       # 活著至少 1 slot
        a_prev = active[t - 1] if t > 0 else 0
        prob += sst[t] >= active[t] - a_prev
        prob += K >= SESS["n_min"] * sst[t]          # 起跑至少 n_min(彈性)
    prob += pulp.lpSum(sst[t] for t in range(HORIZON)) <= 1  # session 開一次
    prob += (pulp.lpSum(k[(h, t)] for h in hosts for t in range(HORIZON))
             == SESS["tasks"])                       # 一格×一slot=一個task

    # --- 資源 ---
    for t in range(HORIZON):
        for h in hosts:  # slot:B/U 佔的 + session 抓的 ≤ 容量
            prob += (pulp.lpSum(jobs[i]["slots"] * r[(i, h, t)]
                                for i in jobs if (i, h, t) in r)
                     + k[(h, t)] <= hosts[h])
        # lic:生命週期內都抓著(含 SUSP 空檔);session 整段吃一份
        prob += (pulp.lpSum(jobs[i]["lic"] * life[(i, t)]
                            for i in jobs if (i, t) in life)
                 + SESS["lic"] * active[t] <= TOTAL_LIC)

    # --- makespan ---
    for (i, h, t), var in r.items():
        prob += T >= (t + 1) * STEP * var
    for t in range(HORIZON):
        prob += T >= (t + 1) * STEP * active[t]

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal", pulp.LpStatus[status]

    sched = {}
    for i in jobs:
        h = next(hh for hh in valid_hosts(i) if a[(i, hh)].value() > 0.5)
        ts = sorted(t for t in valid_steps(i) if r[(i, h, t)].value() > 0.5)
        lf = sorted(t for t in valid_steps(i) if life[(i, t)].value() > 0.5)
        sched[i] = (h, ts, lf)
    kv = {(h, t): int(round(k[(h, t)].value())) for h in hosts
          for t in range(HORIZON)}
    act = [t for t in range(HORIZON) if active[t].value() > 0.5]
    return T.value(), sched, kv, act

def segments(ts):
    segs = []
    for t in ts:
        if segs and t == segs[-1][1]:
            segs[-1][1] = t + 1
        else:
            segs.append([t, t + 1])
    return [(b * STEP, e * STEP) for b, e in segs]

def report(title, makespan, sched, kv, act):
    print(f"=== {title} ===")
    print(f"makespan: {makespan:.0f} 分鐘")
    n = int(makespan) // STEP
    # 甘特圖:B/U 照舊;session 顯示成 S×寬度
    grid = {}
    for h in hosts:
        for t in range(n):
            names = [i for i in jobs if sched[i][0] == h and t in sched[i][1]]
            if kv[(h, t)] > 0:
                names.append(f"S×{kv[(h, t)]}")
            grid[(h, t)] = ",".join(names) or "·"
    width = max(len(c) for c in grid.values()) + 2
    print("  時間(分) " +
          "".join(f"{t*STEP:<{width}}" for t in range(n)) + str(int(makespan)))
    for h in hosts:
        row = "".join(f"{'|' + grid[(h, t)]:<{width}}" for t in range(n))
        print(f"  {h}({hosts[h]}格) {row}|")
    # 各 job 說明
    for i in jobs:
        h, ts, lf = sched[i]
        segs = segments(ts)
        txt = "、".join(f"{b}~{e} 分" for b, e in segs)
        note = "  ← 被搶佔:SUSP 後 RESUME(SUSP 期間 lic 沒有放!)" \
            if len(segs) > 1 else ""
        if i == "U":
            note = "  (20 分才到,deadline 40 分 → 有趕上)"
        print(f"  {i:>2}: {h}  {txt}{note}")
    ss = segments(act)
    widths = "、".join(f"t={t*STEP}~{(t+1)*STEP} 抓 "
                       f"{sum(kv[(h, t)] for h in hosts)} slots" for t in act)
    print(f"   S: 彈性 session {ss[0][0]}~{ss[0][1]} 分,共 {SESS['tasks']} 個 task"
          f"({widths})")
    # lic 表:誰在哪個時間抓著 license(SUSP 也算)
    print(f"  license 持有狀況(總數 {TOTAL_LIC};SUSP 不放、session 整段一份):")
    for t in range(n):
        holders = []
        for i in jobs:
            h, ts, lf = sched[i]
            if t in lf:
                holders.append(i + ("(SUSP)" if t not in ts else ""))
        if t in act:
            holders.append("S")
        used = sum(jobs[i]["lic"] for i in jobs if t in sched[i][2]) \
            + (SESS["lic"] if t in act else 0)
        assert used <= TOTAL_LIC
        # slot 驗證
        for h in hosts:
            occ = sum(jobs[i]["slots"] for i in jobs
                      if sched[i][0] == h and t in sched[i][1]) + kv[(h, t)]
            assert occ <= hosts[h]
        print(f"    t={t*STEP:>3}~{(t+1)*STEP} 分: {used}/{TOTAL_LIC}"
              f"({'、'.join(holders) or '無'})")
    print()

# ---------- 執行 ----------
mk_pre, sched_pre, kv_pre, act_pre = solve(preempt=True)
report("允許搶佔(PREEMPTIVE queue)", mk_pre, sched_pre, kv_pre, act_pre)

mk_no, sched_no, kv_no, act_no = solve(preempt=False)
report("禁止搶佔", mk_no, sched_no, kv_no, act_no)

print(f"結論:允許搶佔讓 makespan 從 {mk_no:.0f} → {mk_pre:.0f} 分。"
      f"另注意 license 的行為:U 的 slot 靠搶佔 B 就能騰出,但 B 被 SUSP 時"
      f" lic 不會放,U 的 lic 只能等 S 整個做完歸還 —— 所以最佳解讓 S 全速衝刺"
      f"(吸滿 {SESS['n']} slots)早早結束還 lic。")
