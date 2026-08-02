# 範例 6:LangGraph + LLM 大腦 指揮迷你 LSF 模擬器
#
# 執行方式:
#   ~/.venv/bin/python lsf_ai_scheduler.py
#
# 架構(誰演什麼角色):
#
#   ┌─────────── LangGraph(代理人流程圖)───────────┐
#   │                                                │
#   │   observe ──> decide ──> apply ──┐             │
#   │      ^        (大腦)             │             │
#   │      └────── 還有 job 沒跑完 ────┘             │
#   │                                                │
#   └────────────────────────────────────────────────┘
#            │查看狀態          │執行決策
#            v                  v
#   ┌──────────── 迷你 LSF 模擬器(遊戲場)──────────┐
#   │  hosts、slots、job 佇列、時鐘、搶佔(SUSP)     │
#   └────────────────────────────────────────────────┘
#
#   - 模擬器只負責「世界運轉」:時間前進、job 跑完、新 job 到達。
#     它自己不做任何排程決策。
#   - 每次有事件發生(job 到達 / 跑完),LangGraph 迴圈就把
#     「目前佇列狀態」做成快照,交給大腦決定:誰上機?放哪台?要不要搶佔?
#   - 大腦有兩種,程式會自動選:
#       * 設了 ANTHROPIC_API_KEY  → 真的 Claude(claude-opus-5)當排程大腦
#       * 沒設                    → 內建的規則大腦(示範用,行為固定)
#
# 劇情(和範例 5 同款):
#   B  大 job(6 slots、40 分),全場只有 H1 塞得下
#   A1~A4 小任務(各 2 slots、20 分)
#   U  急件,第 20 分才出現(6 slots、10 分),40 分前必須完成
#   → 想讓 U 趕上 deadline,大腦必須決定「搶佔 B」,U 跑完再讓 B 續跑。
#
# 這裡的模擬器是手刻的迷你版(幾十行,方便看懂);
# 要做更大的模擬,SimPy 是對味的工具,大腦這一側完全不用改。

import json
import os
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

# ---------- 任務與機器 ----------
JOBS = {
    #  名稱: 到達時間, 執行時間, slots, 優先權, (deadline)
    "B":  dict(arrival=0,  dur=40, slots=6, prio=5),
    "A1": dict(arrival=0,  dur=20, slots=2, prio=3),
    "A2": dict(arrival=0,  dur=20, slots=2, prio=3),
    "A3": dict(arrival=0,  dur=20, slots=2, prio=3),
    "A4": dict(arrival=0,  dur=20, slots=2, prio=3),
    "U":  dict(arrival=20, dur=10, slots=6, prio=9, deadline=40),
}
HOSTS = {"H1": 8, "H2": 4}

# ---------- 迷你 LSF 模擬器 ----------
class MiniLSF:
    def __init__(self):
        self.now = 0.0
        self.state = {}      # job -> future/pending/running/suspended/done
        self.remaining = {}  # job -> 還要跑幾分鐘
        self.place = {}      # job -> host(執行中或被暫停時)
        self.finish_at = {}  # job -> 完成時刻
        self.intervals = []  # [job, host, begin, end] 給最後的報表用
        for j, info in JOBS.items():
            self.state[j] = "pending" if info["arrival"] <= 0 else "future"
            self.remaining[j] = float(info["dur"])

    def free_slots(self, h):
        used = sum(JOBS[j]["slots"] for j in JOBS
                   if self.state[j] == "running" and self.place[j] == h)
        return HOSTS[h] - used

    def snapshot(self):
        def info(j, extra=()):
            d = {"name": j, "slots": JOBS[j]["slots"],
                 "priority": JOBS[j]["prio"],
                 "remaining_minutes": round(self.remaining[j], 1)}
            if "deadline" in JOBS[j]:
                d["deadline"] = JOBS[j]["deadline"]
            for k in extra:
                d[k] = self.place[j] if k == "host" else d.get(k)
            return d
        return {
            "time": self.now,
            "hosts": {h: {"capacity": HOSTS[h], "free": self.free_slots(h)}
                      for h in HOSTS},
            "pending":   [info(j) for j in JOBS if self.state[j] == "pending"],
            "running":   [info(j, ("host",)) for j in JOBS if self.state[j] == "running"],
            "suspended": [info(j, ("host",)) for j in JOBS if self.state[j] == "suspended"],
        }

    def apply(self, actions):
        for a in actions:
            j, kind = a.get("job"), a.get("action")
            if kind == "preempt" and self.state.get(j) == "running":
                self.state[j] = "suspended"
                for seg in self.intervals:
                    if seg[0] == j and seg[3] is None:
                        seg[3] = self.now
                print(f"    [t={self.now:>3.0f}] {j} 被搶佔(SUSP),釋放 "
                      f"{JOBS[j]['slots']} slots")
            elif kind == "start" and self.state.get(j) in ("pending", "suspended"):
                h = a.get("host")
                if self.state[j] == "suspended":
                    h = self.place[j]  # 真實 LSF:原地 RESUME,不搬家
                if h not in HOSTS or self.free_slots(h) < JOBS[j]["slots"]:
                    print(f"    [t={self.now:>3.0f}] 決策無效:{j} 放不進 {h},略過")
                    continue
                self.state[j] = "running"
                self.place[j] = h
                self.intervals.append([j, h, self.now, None])
                tag = "RESUME 續跑" if any(s[0] == j for s in self.intervals[:-1]) else "開始"
                print(f"    [t={self.now:>3.0f}] {j} 在 {h} {tag}"
                      f"(還需 {self.remaining[j]:.0f} 分)")

    def advance(self):
        """把時鐘撥到下一個事件(某 job 跑完、或新 job 到達)"""
        times = [self.now + self.remaining[j] for j in JOBS
                 if self.state[j] == "running"]
        times += [JOBS[j]["arrival"] for j in JOBS if self.state[j] == "future"]
        if not times:
            return False
        t = min(times)
        dt = t - self.now
        for j in JOBS:
            if self.state[j] == "running":
                self.remaining[j] -= dt
        self.now = t
        for j in JOBS:
            if self.state[j] == "running" and self.remaining[j] <= 1e-9:
                self.state[j] = "done"
                self.finish_at[j] = self.now
                for seg in self.intervals:
                    if seg[0] == j and seg[3] is None:
                        seg[3] = self.now
                print(f"    [t={self.now:>3.0f}] {j} 跑完")
            if self.state[j] == "future" and JOBS[j]["arrival"] <= self.now:
                self.state[j] = "pending"
                print(f"    [t={self.now:>3.0f}] {j} 到達,進入佇列")
        return True

    def done(self):
        return all(s == "done" for s in self.state.values())

# ---------- 大腦 1:內建規則(沒有 API key 時用) ----------
def rule_brain(snap):
    free = {h: v["free"] for h, v in snap["hosts"].items()}
    waiting = sorted(snap["pending"] + snap["suspended"],
                     key=lambda j: -j["priority"])
    running = list(snap["running"])
    actions, notes = [], []
    for job in waiting:
        hosts = [job["host"]] if "host" in job else list(HOSTS)
        placed = False
        for h in hosts:
            if free[h] >= job["slots"]:
                actions.append({"action": "start", "job": job["name"], "host": h})
                free[h] -= job["slots"]
                placed = True
                break
        if not placed and job["priority"] >= 8:
            # 急件塞不下 → 找一台機器,搶佔優先權較低的 job 來騰位子
            for h in hosts:
                if snap["hosts"][h]["capacity"] < job["slots"]:
                    continue
                victims = sorted(
                    [r for r in running
                     if r["host"] == h and r["priority"] < job["priority"]],
                    key=lambda r: r["priority"])
                gain, chosen = free[h], []
                for v in victims:
                    if gain >= job["slots"]:
                        break
                    chosen.append(v)
                    gain += v["slots"]
                if gain >= job["slots"]:
                    for v in chosen:
                        actions.append({"action": "preempt",
                                        "job": v["name"], "host": h})
                        running.remove(v)
                    actions.append({"action": "start",
                                    "job": job["name"], "host": h})
                    free[h] = gain - job["slots"]
                    notes.append(f"搶佔 {'+'.join(v['name'] for v in chosen)} "
                                 f"讓急件 {job['name']} 上機")
                    break
    reason = "; ".join(notes) if notes else "優先權高的先上,塞得下就放"
    return actions, reason

# ---------- 大腦 2:Claude(設了 ANTHROPIC_API_KEY 時用) ----------
SCHED_SYSTEM = """你是 LSF 排程器的大腦。輸入是叢集目前的 JSON 快照,請決定此刻要執行的動作。

規則:
- start:讓 pending 或 suspended 的 job 上指定 host(slots 必須塞得下;suspended 的 job 只能在原 host 續跑)。
- preempt:暫停一個 running 的 job,釋放它的 slots(用於讓高優先權急件插隊)。
- 有 deadline 的 job 絕對不能遲到;其次讓總完工時間越短越好。
- 不需要動作時回傳空陣列。一次回傳這個時間點的所有動作,先 preempt 後 start。"""

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reason": {"type": "string", "description": "一句話說明決策理由"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["start", "preempt"]},
                    "job": {"type": "string"},
                    "host": {"type": "string"},
                },
                "required": ["action", "job", "host"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reason", "actions"],
    "additionalProperties": False,
}

def make_llm_brain():
    import anthropic
    client = anthropic.Anthropic()

    def llm_brain(snap):
        # fallbacks="default":Claude 的安全分類器若拒答,自動改用建議的後備模型重跑
        resp = client.beta.messages.create(
            model="claude-opus-5",
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SCHED_SYSTEM,
            output_config={"format": {"type": "json_schema",
                                      "schema": ACTION_SCHEMA}},
            messages=[{"role": "user",
                       "content": json.dumps(snap, ensure_ascii=False)}],
        )
        if resp.stop_reason == "refusal":
            return [], "(模型拒答,本輪不動作)"
        data = json.loads(next(b.text for b in resp.content if b.type == "text"))
        return data["actions"], data["reason"]

    return llm_brain

# ---------- LangGraph:observe → decide → apply → (迴圈) ----------
sim = MiniLSF()
if os.environ.get("ANTHROPIC_API_KEY"):
    brain, brain_name = make_llm_brain(), "Claude(claude-opus-5)"
else:
    brain, brain_name = rule_brain, "內建規則大腦(設 ANTHROPIC_API_KEY 可換成 Claude)"

class SchedState(TypedDict, total=False):
    snapshot: dict
    actions: list
    reason: str

def observe(state: SchedState) -> SchedState:
    return {"snapshot": sim.snapshot()}

def decide(state: SchedState) -> SchedState:
    actions, reason = brain(state["snapshot"])
    txt = "、".join(f"{a['action']} {a['job']}" +
                    (f"@{a['host']}" if a["action"] == "start" else "")
                    for a in actions) or "(不動作)"
    print(f"  t={sim.now:>3.0f} 大腦決策: {txt}   理由: {reason}")
    return {"actions": actions, "reason": reason}

def apply_node(state: SchedState) -> SchedState:
    sim.apply(state["actions"])
    sim.advance()
    return {}

graph = StateGraph(SchedState)
graph.add_node("observe", observe)
graph.add_node("decide", decide)
graph.add_node("apply", apply_node)
graph.add_edge(START, "observe")
graph.add_edge("observe", "decide")
graph.add_edge("decide", "apply")
graph.add_conditional_edges("apply", lambda s: END if sim.done() else "observe",
                            {"observe": "observe", END: END})
app = graph.compile()

print(f"排程大腦:{brain_name}")
print("事件紀錄:")
app.invoke({}, config={"recursion_limit": 300})

# ---------- 報表 ----------
print()
print("最終班表:")
for j in JOBS:
    segs = [(s[2], s[3]) for s in sim.intervals if s[0] == j]
    host = next(s[1] for s in sim.intervals if s[0] == j)
    txt = "、".join(f"{b:.0f}~{e:.0f} 分" for b, e in segs)
    note = "  ← 被搶佔後續跑" if len(segs) > 1 else ""
    if "deadline" in JOBS[j]:
        ok = "趕上" if sim.finish_at[j] <= JOBS[j]["deadline"] else "遲到!"
        note = f"  (deadline {JOBS[j]['deadline']} 分 → {ok})"
    print(f"  {j:>2}: {host}  {txt}{note}")
print(f"全部完工:{max(sim.finish_at.values()):.0f} 分")
