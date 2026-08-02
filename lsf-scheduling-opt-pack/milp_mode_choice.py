# MILP 範例 7:session 還是 array?—— 資源越多不一定效率越高
#
# 執行方式:
#   ~/.venv/bin/python milp_mode_choice.py
#
# 現象(這個範例要捕捉的真實情況):
#   EDA 工具每「開一次」都有啟動開銷(license checkout、載入設計檔,這裡設 10 分鐘)。
#   同一批工作有兩種跑法:
#     array   模式:每個任務各開一份工具 → 各付 10 分鐘開銷,但可以平行跑
#     session 模式:只開一份工具(付一次開銷),任務在裡面「排隊依序跑」
#   於是出現非線性、非單調的效率關係:
#     - 短工作:開銷 10 分 > 工作本身 5 分,各開各的超浪費 → 適合 session
#     - 長工作:開銷相對可忽略,平行的好處大 → 適合 array
#   「給越多 license(array 全開)」反而讓總機器時間爆炸 —— 資源越多≠效率越高。
#
# 建模的招(和範例 5 的開關變數同門):
#   「模式選擇」是離散選項,每種選法的耗時可以「事先查表」:
#     短件×6 array   → 6 個單位,各 10+5  = 15 分
#     短件×6 session → 1 個單位,10+6×5  = 40 分
#     長件×2 array   → 2 個單位,各 10+30 = 40 分
#     長件×2 session → 1 個單位,10+2×30 = 70 分
#   用 0/1 變數 mode[g] 決定每組走哪條路,被選中的單位才需要排程。
#   查表之後一切都是線性的 → MILP 照吃,而且保證全域最優。
#   注意:「短配 session、長配 array」這條規則【沒有】寫進模型,
#   我們只告訴它開銷怎麼算 —— 讓求解器自己發現該怎麼配。
#
# 資源:license 同時最多 3 份(每個運行中的單位佔 1 份)。
# 為了聚焦在「模式選擇」,這個範例先拿掉 host/slot 維度(要加回來就照範例 3 的做法)。

import itertools
import pulp

STEP = 5          # 一格 5 分鐘
HORIZON = 24      # 排程視窗 120 分鐘
OVERHEAD = 10     # 工具啟動開銷(分鐘)
LICENSES = 3      # license 同時上限

groups = {
    #  組名: (件數, 每件的實際工作時間)
    "短件": (6, 5),
    "長件": (2, 30),
}

# ---------- 查表:每組×每模式 會產生哪些「執行單位」 ----------
def build_units():
    units = {}  # uid -> (組, 模式, 需要的時間格數)
    for g, (n, work) in groups.items():
        for k in range(1, n + 1):           # array:每件各自一個單位
            units[f"{g}_arr{k}"] = (g, "array", (OVERHEAD + work) // STEP)
        units[f"{g}_sess"] = (g, "session",   # session:整組一個單位
                              (OVERHEAD + n * work) // STEP)
    return units

UNITS = build_units()

# ---------- 建模 + 求解 ----------
def solve(fixed_mode=None):
    """fixed_mode: None=讓求解器自己選;或 {組: 'session'/'array'} 鎖定比較用"""
    prob = pulp.LpProblem("mode_choice", pulp.LpMinimize)

    # mode[g] = 1 → 這組走 session;0 → 走 array
    mode = pulp.LpVariable.dicts("mode", groups, cat=pulp.LpBinary)
    if fixed_mode:
        for g, m in fixed_mode.items():
            prob += mode[g] == (1 if m == "session" else 0)

    # s[(u,t)] = 1 → 單位 u 在時間格 t 開跑(跑到底,中途不斷)
    s = {}
    for u, (g, m, d) in UNITS.items():
        for t in range(HORIZON - d + 1):
            s[(u, t)] = pulp.LpVariable(f"s_{u}_{t}", cat=pulp.LpBinary)

    T = pulp.LpVariable("T", lowBound=0)
    prob += T

    # 被選中的模式,它的單位才要跑(array 單位跑 1-mode 次,session 單位跑 mode 次)
    for u, (g, m, d) in UNITS.items():
        total = pulp.lpSum(s[(u, t)] for t in range(HORIZON - d + 1))
        prob += total == (mode[g] if m == "session" else 1 - mode[g])

    # license:每個時間格,正在跑的單位數 ≤ 上限
    for tau in range(HORIZON):
        prob += (
            pulp.lpSum(
                s[(u, t)]
                for u, (g, m, d) in UNITS.items()
                for t in range(max(0, tau - d + 1), tau + 1)
                if (u, t) in s
            ) <= LICENSES
        )

    # makespan
    for (u, t), var in s.items():
        d = UNITS[u][2]
        prob += T >= (t + d) * STEP * var

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    chosen = {g: ("session" if mode[g].value() > 0.5 else "array")
              for g in groups}
    sched = []
    for (u, t), var in s.items():
        if var.value() > 0.5:
            d = UNITS[u][2]
            sched.append((u, t * STEP, (t + d) * STEP))
    return T.value(), chosen, sorted(sched, key=lambda x: x[1])

# ---------- 1) 讓求解器自由選模式 ----------
best_T, best_mode, best_sched = solve()
print("=== 讓求解器自己選模式 ===")
print(f"最短完工時間: {best_T:.0f} 分鐘")
for g in groups:
    print(f"  {g} → {best_mode[g]}")
print("班表:")
for u, b, e in best_sched:
    print(f"  {u:>8}: {b:>3.0f} ~ {e:>3.0f} 分")

# ---------- 2) 四種組合全部比一遍(驗證 + 看出效率差異) ----------
print()
print("=== 四種組合的比較(license 上限 3)===")
print(f"{'短件':>8} {'長件':>8} {'完工時間':>8} {'機器時間*':>9} {'備註'}")
useful = sum(n * w for n, w in groups.values())  # 真正有用的工作量
for m1, m2 in itertools.product(["session", "array"], repeat=2):
    combo = {"短件": m1, "長件": m2}
    t_combo, _, sched = solve(fixed_mode=combo)
    machine = sum(e - b for _, b, e in sched)  # license 被佔用的總分鐘數
    star = "  ← 求解器選的" if combo == best_mode else ""
    print(f"{m1:>8} {m2:>8} {t_combo:>7.0f}分 {machine:>8.0f}分{star}")
print(f"  * 機器時間 = license 被佔用的總分鐘;其中真正有用的工作只有 {useful} 分,")
print(f"    其餘都是重複付的啟動開銷 —— 開越多份工具,浪費越多。")
