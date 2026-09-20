#!/usr/bin/env python3
"""
pinwheel_sim.py — Topic 34 (B1): Pinwheel scheduling for certified multi-camera perception
on ONE shared accelerator. 100% desk: replays the 121-video / 3,713-event corpus
(CDnet2014 + LASIESTA + BMC, per-event onset/duration built by code/build_event_corpus.py)
as N synchronous camera streams and measures certificate violations vs. density.

Experiments
  E1  synthetic profiles: schedulability (exact state-space search) vs. EDF heuristic vs.
      harmonic rounding, binned by density  -> results/E1_density_sweep.json
  E2  trace replay: uniform vs. shaped windows at equal density, EDF + harmonic schedulers
      -> results/E2_trace_frontier.json
  E3  switch cost s (model reload): violations vs. (1+s)*density  -> results/E3_switch_cost.json
  figs -> results/fig_E1_violation_vs_density.png, fig_E2_frontier.png, fig_E3_switch.png

Usage:  python pinwheel_sim.py --exp E1|E2|E3|figs|all [--quick]
Data:   data/event_corpus.csv, written by code/build_event_corpus.py from per-frame object
        detections (see data/CORPUS_README.md). Override its location with PINWHEEL_DATA_DIR.
Seed 42 throughout. Author: Dat Lam Quoc (FSB, FPT University). 2026-09-04.
"""
import argparse, csv, hashlib, json, math, os, random, sys, time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC_DIR = os.path.abspath(os.path.join(HERE, ".."))
RESULTS = os.path.join(TOPIC_DIR, "results")
DATA_DIR = os.environ.get("PINWHEEL_DATA_DIR", os.path.join(TOPIC_DIR, "data"))
CORPUS_DATASETS = ("CDnet2014", "LASIESTA", "BMC")   # the 121-video / 3,713-event corpus (VIRAT excluded)
SEED = 42


# ----------------------------------------------------------------------------- corpus
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_corpus():
    """Read data/event_corpus.csv: one row per event, carrying its video's length."""
    ev_path = os.path.join(DATA_DIR, "event_corpus.csv")
    nframes = {}
    events = defaultdict(list)
    with open(ev_path, newline="") as f:
        for r in csv.DictReader(f):
            if r["dataset"] not in CORPUS_DATASETS:
                continue
            key = (r["dataset"], r["video"])
            nframes[key] = int(r["n_frames"])
            events[key].append((int(r["onset"]), int(r["duration"])))
    videos = sorted(nframes)
    n_events = sum(len(events[v]) for v in videos)
    assert len(videos) == 121, f"expected 121 videos, got {len(videos)}"
    assert n_events == 3713, f"expected 3713 events, got {n_events}"
    meta = {"n_videos": len(videos), "n_events": n_events,
            "n_frames": int(sum(nframes.values())),
            "datasets": {d: sum(1 for v in videos if v[0] == d) for d in CORPUS_DATASETS},
            "source": {"event_corpus.csv": sha256(ev_path)}}
    return videos, nframes, events, meta


# ----------------------------------------------------------------------------- schedulers
def density(K):
    return float(sum(1.0 / k for k in K))


def edf_schedule(K, H, s=0, lazy=False):
    """Earliest-deadline-first pinwheel heuristic. Switch cost s: switching camera costs s idle slots.
    lazy=True: non-work-conserving -- serve only when some j cameras have deadlines within the next
    j slots (i.e. idling now would force a violation); busy fraction then tracks the density.
    Returns sched array of length H (-1 = idle/switching)."""
    N = len(K)
    sched = np.full(H, -1, dtype=np.int32)
    last = [0] * N            # pretend all served at slot 0 (grace)
    t, prev = 0, -1
    while t < H:
        if lazy:
            dl = sorted(last[j] + K[j] for j in range(N))
            must = any(dl[j] <= t + j + (s if (s and prev != -1) else 0) for j in range(N))
            if not must:
                t += 1
                continue
        # camera with smallest deadline last+K; ties -> larger K first (avoids starving long windows),
        # then least-recently served
        i = min(range(N), key=lambda j: (last[j] + K[j], -K[j], last[j]))
        if s and prev != -1 and i != prev:
            t += s                # model reload / context switch: accelerator busy, no frame served
            if t >= H:
                break
        sched[t] = i
        last[i] = t
        prev = i
        t += 1
    return sched


def harmonic_round(K, base):
    """Round each K down to base*2^j (j>=0); returns None if some K < base."""
    out = []
    for k in K:
        if k < base:
            return None
        j = int(math.floor(math.log2(k / base)))
        out.append(base << j)
    return out


def harmonic_schedule(K, H):
    """Single-base harmonic rounding (Holte et al. 1989 style): try every base a in [2, max K],
    round each K_i down to a*2^j, keep the base with the smallest rounded density <= 1, then assign
    residues greedily (always succeeds for a harmonic multiset of density <= 1).
    Returns (sched, rounded K) or (None, best rounded K)."""
    best = None
    for a in range(2, max(K) + 1):
        Kp = harmonic_round(K, a)
        if Kp is None:
            continue
        d = sum(1.0 / k for k in Kp)
        if best is None or d < best[0]:
            best = (d, Kp)
    if best is None:
        return None, K
    Kp = best[1]
    if best[0] > 1.0 + 1e-12:
        return None, Kp
    order = sorted(range(len(K)), key=lambda i: Kp[i])
    M = max(Kp)
    occupied = np.zeros(M, dtype=bool)
    offset = [None] * len(K)
    for i in order:
        k = Kp[i]
        found = False
        for r in range(k):
            if not occupied[r::k].any():
                occupied[r::k] = True
                offset[i] = r
                found = True
                break
        if not found:
            return None, Kp
    sched = np.full(H, -1, dtype=np.int32)
    t = np.arange(H)
    for i in range(len(K)):
        sched[(t % Kp[i]) == offset[i]] = i
    return sched, Kp


# ----------------------------------------------------------------------------- divisor wheel
# Round-3 addition (2026-09-06). A strictly stronger constructive scheduler than the single-base
# harmonic one: instead of rounding every window down to a*2^j for one base a, round it down to
# the largest DIVISOR of a common wheel length M, then assign each camera a residue class mod its
# rounded window. Camera i is then served at exactly the slots t = r_i (mod d_i), so its gap is
# exactly d_i <= K_i and the certificate holds by construction.
#
# NOTE ON ATTRIBUTION: this is NOT the Chan-Chin 7/10 scheduler. Chan and Chin's construction is
# behind a paywall and no accessible secondary source states it precisely enough to reimplement
# faithfully, so we did not implement it (see the Limitations section of the manuscript). The
# divisor wheel needs no external theorem at all: a successful packing IS the certificate, which
# is checked per instance. Its failures are instances that admit no perfectly periodic schedule.
def _divisors(M):
    d = []
    i = 1
    while i * i <= M:
        if M % i == 0:
            d.append(i)
            if i != M // i:
                d.append(M // i)
        i += 1
    return sorted(d)


def _wheel_candidates(limit=2520):
    """Wheel lengths to try: every a*2^j (this subsumes the single-base harmonic scheduler) plus
    every 13-smooth number, so that windows such as 11 or 13 are not rounded down to 8."""
    c = {a << j for a in range(2, 17) for j in range(0, 12) if (a << j) <= limit}
    s = {1}
    for p in (2, 3, 5, 7, 11, 13):
        s |= {x * p ** k for x in list(s) for k in range(1, 12) if x * p ** k <= limit}
    return sorted(c | {x for x in s if x >= 2})


WHEEL_CANDIDATES = _wheel_candidates()
_WHEEL_DIVISORS = {M: _divisors(M) for M in WHEEL_CANDIDATES}


def wheel_round(K, M):
    """Round each window DOWN to the largest divisor of M not exceeding it (certificate-safe)."""
    ds = _WHEEL_DIVISORS[M]
    out = []
    for k in K:
        best = 1
        for d in ds:
            if d <= k:
                best = d
            else:
                break
        out.append(best)
    return out


def wheel_pack(Kr, M, budget=20_000):
    """Assign each camera a residue class mod its rounded window on a wheel of M slots.
    Depth-first with backtracking, smallest window first. Returns the residues or None."""
    order = sorted(range(len(Kr)), key=lambda i: Kr[i])
    occ = np.zeros(M, dtype=bool)
    res = [None] * len(Kr)
    nodes = [0]

    def rec(j):
        if nodes[0] > budget:
            return False
        if j == len(order):
            return True
        i = order[j]
        d = Kr[i]
        for r in range(d):
            nodes[0] += 1
            if nodes[0] > budget:
                return False
            if not occ[r::d].any():
                occ[r::d] = True
                res[i] = r
                if rec(j + 1):
                    return True
                occ[r::d] = False
                res[i] = None
        return False

    return res if rec(0) else None


def divisor_wheel_schedule(K, H):
    """Constructive divisor-wheel scheduler. Returns (sched, rounded K, M) or (None, None, None).
    Wheels are tried in increasing rounded density, i.e. least wasted capacity first."""
    cands = []
    for M in WHEEL_CANDIDATES:
        Kr = wheel_round(K, M)
        if min(Kr) < 1:
            continue
        rho = sum(1.0 / d for d in Kr)
        if rho <= 1.0 + 1e-12:
            cands.append((rho, M, Kr))
    cands.sort(key=lambda c: (c[0], c[1]))
    for rho, M, Kr in cands:
        res = wheel_pack(Kr, M)
        if res is None:
            continue
        sched = np.full(H, -1, dtype=np.int32)
        t = np.arange(H)
        for i in range(len(K)):
            sched[(t % Kr[i]) == (res[i] % Kr[i])] = i
        return sched, Kr, M
    return None, None, None


def exact_schedulable(K, max_states=400_000, time_limit=None):
    """Exact decision by cycle search in the state graph (u_i = slots since last service).
    Returns True / False / None (budget exceeded).

    The budget is a STATE COUNT, not a wall-clock limit (round-3 fix, 2026-09-06): a wall-clock
    budget made the verdict depend on machine load, so re-running the same seed on a busier
    machine flipped a handful of instances between False and None. `time_limit` is kept only so
    that callers can opt back into the old behaviour; leave it None for reproducible results."""
    N = len(K)
    start = tuple([0] * N)
    color = {}
    t0 = time.time()
    stack = [(start, 0)]
    color[start] = 1  # grey
    path = [start]
    # iterative DFS with explicit child index
    frames = [[start, 0]]
    while frames:
        if len(color) > max_states or (time_limit is not None and time.time() - t0 > time_limit):
            return None
        u, idx = frames[-1]
        # generate children lazily: serve camera i
        moved = False
        while idx < N:
            i = idx
            frames[-1][1] = idx + 1
            idx += 1
            ok = True
            child = []
            for j in range(N):
                if j == i:
                    child.append(0)
                else:
                    v = u[j] + 1
                    if v >= K[j]:
                        ok = False
                        break
                    child.append(v)
            if not ok:
                continue
            child = tuple(child)
            c = color.get(child, 0)
            if c == 1:
                return True      # cycle reachable -> infinite schedule exists
            if c == 0:
                color[child] = 1
                frames.append([child, 0])
                moved = True
                break
        if not moved:
            color[u] = 2
            frames.pop()
    return False


def max_gaps(sched, N, H, warm):
    """Max service gap per camera over [warm, H) (gap measured between consecutive services)."""
    gaps = [0] * N
    for i in range(N):
        S = np.flatnonzero(sched == i)
        S = S[S >= warm]
        if len(S) < 2:
            gaps[i] = H
        else:
            gaps[i] = int(np.max(np.diff(S)))
    return gaps


# ----------------------------------------------------------------------------- replay
def build_streams(rng, videos, nframes, events, N, H):
    """Assign N cameras to N distinct videos (sampled without replacement), wrap cyclically to H."""
    chosen = rng.sample(videos, N)
    streams = []
    for v in chosen:
        n = nframes[v]
        ev = []
        m = 0
        while m * n < H:
            for (s, d) in events[v]:
                s2 = s + m * n
                if s2 + d - 1 < H:
                    ev.append((s2, d))
            m += 1
        streams.append({"video": f"{v[0]}/{v[1]}", "n_frames": n, "events": ev})
    return streams


def replay(sched, streams, K, warm):
    """Per-camera event outcomes. certified = events with D >= K_i (onset >= warm)."""
    out = {"n_events": 0, "n_cert": 0, "miss_cert": 0, "miss_all": 0, "lat_sum": 0.0, "lat_n": 0,
           "lat_max_cert": 0}
    for i, st in enumerate(streams):
        S = np.flatnonzero(sched == i)
        for (s, d) in st["events"]:
            if s < warm:
                continue
            out["n_events"] += 1
            k = np.searchsorted(S, s)
            caught = k < len(S) and S[k] <= s + d - 1
            lat = int(S[k] - s) if caught else None
            cert = d >= K[i]
            if cert:
                out["n_cert"] += 1
                if not caught:
                    out["miss_cert"] += 1
                else:
                    out["lat_max_cert"] = max(out["lat_max_cert"], lat)
            if not caught:
                out["miss_all"] += 1
            else:
                out["lat_sum"] += lat
                out["lat_n"] += 1
    return out


def shaping_objective(streams, K):
    """Expected number of missed events (periodic worst case, Lemma 2): sum_i n_i * E[(1-D/K_i)_+]."""
    tot = 0.0
    for st, k in zip(streams, K):
        d = np.array([dd for (_, dd) in st["events"]], dtype=float)
        if len(d):
            tot += float(np.sum(np.clip(1.0 - d / k, 0.0, None)))
    return tot


def shaped_windows(streams, budget, grid=None, Kmin=2, Kmax=64):
    """Greedy discrete budget shaping (Theorem 3 relaxed): weights = event rate per camera,
    objective = expected number of missed (uncertified) events under the periodic worst case
    eps_i(K) = E[(1 - D/K)_+]. Start at the largest grid value, repeatedly buy the step with the
    best (miss reduction / density cost) until the budget is exhausted.
    grid: sorted list of admissible K values (default all integers in [Kmin, Kmax])."""
    N = len(streams)
    grid = sorted(set(grid)) if grid is not None else list(range(Kmin, Kmax + 1))
    durs = [np.array([d for (_, d) in st["events"]], dtype=float) for st in streams]

    def cost(i, K):
        if len(durs[i]) == 0:
            return 0.0
        return float(np.sum(np.clip(1.0 - durs[i] / K, 0.0, None)))

    idx = [len(grid) - 1] * N
    K = [grid[j] for j in idx]
    rho = density(K)
    while True:
        best, bi = 0.0, None
        for i in range(N):
            if idx[i] == 0:
                continue
            k_new = grid[idx[i] - 1]
            dK = 1.0 / k_new - 1.0 / K[i]
            if rho + dK > budget + 1e-12:
                continue
            gain = (cost(i, K[i]) - cost(i, k_new)) / dK
            if gain > best:
                best, bi = gain, i
        if bi is None:
            break
        idx[bi] -= 1
        K[bi] = grid[idx[bi]]
        rho = density(K)
    return K


def shaped_harmonic_windows(streams, budget, Kmax=64):
    """Budget shaping restricted to one harmonic chain {a*2^j}: schedulable by construction whenever
    the density is <= 1 (Prop. 1(a)). Tries every base a and keeps the best objective."""
    best = None
    for a in range(2, 17):
        grid = [a << j for j in range(0, 8) if (a << j) <= Kmax]
        if len(grid) < 2:
            continue
        K = shaped_windows(streams, budget, grid=grid)
        obj = shaping_objective(streams, K)
        if best is None or obj < best[0]:
            best = (obj, K, a)
    return best[1], best[2]


# ----------------------------------------------------------------------------- experiments
def run_E1(quick):
    rng = random.Random(SEED)
    n_inst = 240 if quick else 600
    rows = []
    bins = [(0.40, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 0.75), (0.75, 5 / 6), (5 / 6, 0.90),
            (0.90, 0.95), (0.95, 1.0), (1.0, 1.10)]
    per_bin = n_inst // len(bins)
    H = 4000
    for lo, hi in bins:
        got = 0
        tries = 0
        while got < per_bin and tries < 20000:
            tries += 1
            N = rng.randint(3, 8)
            K = sorted(rng.randint(2, 14) for _ in range(N))
            rho = density(K)
            if not (lo < rho <= hi):
                continue
            ex = exact_schedulable(K)
            sched = edf_schedule(K, H)
            gaps = max_gaps(sched, N, H, warm=max(K))
            edf_ok = all(g <= K[i] for i, g in enumerate(gaps))
            hs, Kp = harmonic_schedule(K, H)
            ws, Kw, Mw = divisor_wheel_schedule(K, H)
            rows.append({"N": N, "K": K, "rho": rho, "bin": f"({lo:.3f},{hi:.3f}]", "exact": ex,
                         "edf_ok": edf_ok, "harmonic_ok": hs is not None,
                         "wheel_ok": ws is not None, "wheel_M": Mw, "distinct": len(set(K))})
            got += 1
    # aggregate
    agg = {}
    for lo, hi in bins:
        b = f"({lo:.3f},{hi:.3f}]"
        R = [r for r in rows if r["bin"] == b]
        dec = [r for r in R if r["exact"] is not None]
        agg[b] = {"n": len(R), "n_decided": len(dec),
                  "exact_schedulable_frac": (sum(1 for r in dec if r["exact"]) / len(dec)) if dec else None,
                  "edf_ok_frac": sum(1 for r in R if r["edf_ok"]) / len(R) if R else None,
                  "harmonic_ok_frac": sum(1 for r in R if r["harmonic_ok"]) / len(R) if R else None,
                  "wheel_ok_frac": sum(1 for r in R if r["wheel_ok"]) / len(R) if R else None,
                  "wheel_gain_over_harmonic": (sum(1 for r in R if r["wheel_ok"])
                                               - sum(1 for r in R if r["harmonic_ok"])) / len(R) if R else None,
                  "edf_fails_on_schedulable": sum(1 for r in dec if r["exact"] and not r["edf_ok"]),
                  "unschedulable_below_5_6": sum(1 for r in dec if (not r["exact"]) and r["rho"] <= 5 / 6)}
    out = {"meta": {"seed": SEED, "H": H, "n_instances": len(rows), "K_range": [2, 14], "N_range": [3, 8],
                    "exact": "cycle search in state graph, start all-zero, cap 4e5 states / 3 s"},
           "bins": agg, "instances": rows}
    json.dump(out, open(os.path.join(RESULTS, "E1_density_sweep.json"), "w"), indent=1)
    return out


def run_E2(quick, videos, nframes, events):
    H = 6000
    seeds = 6 if quick else 12
    Ns = [4, 6, 8, 12]
    budgets = [0.5, 2 / 3, 5 / 6, 1.0]
    rows = []
    for N in Ns:
        for rho_star in budgets:
            for sd in range(seeds):
                rng = random.Random(SEED * 1000 + sd)
                streams = build_streams(rng, videos, nframes, events, N, H)
                Ku = max(2, math.ceil(N / rho_star))
                profiles = {"uniform": [Ku] * N,
                            "shaped_int": shaped_windows(streams, rho_star),
                            "shaped_harm": shaped_harmonic_windows(streams, rho_star)[0]}
                for pname, K in profiles.items():
                    for sname in ("edf_lazy", "edf_wc", "harmonic", "wheel"):
                        if sname == "edf_lazy":
                            sched = edf_schedule(K, H, lazy=True)
                        elif sname == "edf_wc":
                            sched = edf_schedule(K, H, lazy=False)
                        elif sname == "wheel":
                            sched, Kw, Mw = divisor_wheel_schedule(K, H)
                            if sched is None:
                                rows.append({"N": N, "rho_star": rho_star, "seed": sd, "profile": pname,
                                             "scheduler": sname, "K": K, "rho": density(K), "feasible": False})
                                continue
                        else:
                            sched, Kp = harmonic_schedule(K, H)
                            if sched is None:
                                rows.append({"N": N, "rho_star": rho_star, "seed": sd, "profile": pname,
                                             "scheduler": sname, "K": K, "rho": density(K), "feasible": False})
                                continue
                        warm = max(K)
                        gaps = max_gaps(sched, N, H, warm)
                        viol = sum(1 for i, g in enumerate(gaps) if g > K[i])
                        rp = replay(sched, streams, K, warm)
                        busy = float(np.mean(sched[warm:] >= 0))
                        rows.append({"N": N, "rho_star": rho_star, "seed": sd, "profile": pname,
                                     "scheduler": sname, "K": K, "rho": density(K), "feasible": True,
                                     "busy": busy, "violating_cameras": viol,
                                     "n_events": rp["n_events"], "n_cert": rp["n_cert"],
                                     "miss_cert": rp["miss_cert"], "miss_all": rp["miss_all"],
                                     "miss_all_rate": rp["miss_all"] / max(1, rp["n_events"]),
                                     "miss_cert_rate": rp["miss_cert"] / max(1, rp["n_cert"]),
                                     "lemma2_bound_rate": shaping_objective(streams, K) / max(1, sum(len(st["events"]) for st in streams)),
                                     "lat_mean": rp["lat_sum"] / max(1, rp["lat_n"]),
                                     "lat_max_cert": rp["lat_max_cert"],
                                     "bound_lat_cert": max(K) - 1})
    agg = defaultdict(list)
    for r in rows:
        if r["feasible"]:
            agg[(r["N"], round(r["rho_star"], 4), r["profile"], r["scheduler"])].append(r)
    summary = []
    for key, R in sorted(agg.items()):
        summary.append({"N": key[0], "rho_star": key[1], "profile": key[2], "scheduler": key[3], "n": len(R),
                        "rho_mean": float(np.mean([r["rho"] for r in R])),
                        "busy_mean": float(np.mean([r["busy"] for r in R])),
                        "miss_all_rate_mean": float(np.mean([r["miss_all_rate"] for r in R])),
                        "lemma2_bound_rate_mean": float(np.mean([r["lemma2_bound_rate"] for r in R])),
                        "miss_cert_total": int(sum(r["miss_cert"] for r in R)),
                        "n_cert_total": int(sum(r["n_cert"] for r in R)),
                        "violating_runs": int(sum(1 for r in R if r["violating_cameras"] > 0)),
                        "lat_mean": float(np.mean([r["lat_mean"] for r in R])),
                        "lat_max_cert_max": int(max(r["lat_max_cert"] for r in R)),
                        "bound_lat_cert_max": int(max(r["bound_lat_cert"] for r in R))})
    out = {"meta": {"seed": SEED, "H": H, "seeds": seeds, "Ns": Ns, "budgets": budgets,
                    "profiles": {"uniform": "K = ceil(N/rho*) for all cameras",
                                 "shaped_int": "greedy budget shaping on integers 2..64 (Thm 3 relaxed)",
                                 "shaped_harm": "greedy budget shaping on one harmonic chain a*2^j (Prop 1a): schedulable by construction"},
                    "schedulers": {"edf_lazy": "EDF, non-work-conserving (idle unless forced)",
                                   "edf_wc": "EDF, work-conserving (busy=1)",
                                   "harmonic": "single-base harmonic rounding + residue assignment (guaranteed when rounded density <= 1)",
                                   "wheel": "divisor-wheel: round each window down to a divisor of a common wheel length M, then assign residue classes with backtracking; a successful packing is itself the certificate. NOT the Chan-Chin 7/10 scheduler -- see Limitations."}},
           "summary": summary, "runs": rows}
    json.dump(out, open(os.path.join(RESULTS, "E2_trace_frontier.json"), "w"), indent=1)
    return out


def run_E3(quick, videos, nframes, events):
    H = 6000
    seeds = 4 if quick else 8
    N = 6
    Ks = [8, 10, 12, 14, 16, 20, 24]
    ss = [0, 1, 2, 3]
    rows = []
    for K0 in Ks:
        K = [K0] * N
        for s in ss:
            for sd in range(seeds):
                rng = random.Random(SEED * 1000 + sd)
                streams = build_streams(rng, videos, nframes, events, N, H)
                sched = edf_schedule(K, H, s=s, lazy=True)
                warm = max(K) * 2
                gaps = max_gaps(sched, N, H, warm)
                viol = sum(1 for i, g in enumerate(gaps) if g > K[i])
                rp = replay(sched, streams, K, warm)
                rows.append({"N": N, "K": K0, "s": s, "seed": sd, "rho": density(K),
                             "rho_eff": (1 + s) * density(K), "bound_Nmax": K0 // (1 + s),
                             "violating_cameras": viol, "max_gap": max(gaps),
                             "miss_cert": rp["miss_cert"], "n_cert": rp["n_cert"],
                             "miss_all_rate": rp["miss_all"] / max(1, rp["n_events"]),
                             "busy": float(np.mean(sched[warm:] >= 0))})
    agg = defaultdict(list)
    for r in rows:
        agg[(r["K"], r["s"])].append(r)
    summary = [{"K": k, "s": s, "rho": 6 / k, "rho_eff": (1 + s) * 6 / k, "N": N,
                "prop2_feasible": N <= k // (1 + s),
                "violating_runs": int(sum(1 for r in R if r["violating_cameras"] > 0)), "n": len(R),
                "miss_cert_total": int(sum(r["miss_cert"] for r in R)),
                "miss_all_rate_mean": float(np.mean([r["miss_all_rate"] for r in R]))}
               for (k, s), R in sorted(agg.items())]
    out = {"meta": {"seed": SEED, "H": H, "N": N, "Ks": Ks, "switch_costs": ss,
                    "model": "switching camera costs s idle slots (lazy EDF in real time; homogeneous K so EDF = round-robin)"},
           "summary": summary, "runs": rows}
    json.dump(out, open(os.path.join(RESULTS, "E3_switch_cost.json"), "w"), indent=1)
    return out


def make_figs():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # vector (TrueType) text rather than matplotlib's default Type 3 bitmapped glyphs
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["ps.fonttype"] = 42
    # Figures print at roughly their natural width across both columns, so the sizes below are
    # very nearly the sizes on the page. The base is 10pt because matplotlib draws mathtext
    # sub- and superscripts at 0.7 of it, and the smallest glyph on the page has to stay >= 7pt.
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 10, "axes.labelsize": 10,
                         "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9})
    # E1
    p = os.path.join(RESULTS, "E1_density_sweep.json")
    if os.path.exists(p):
        d = json.load(open(p))
        labels = list(d["bins"].keys())
        x = np.arange(len(labels))
        ex = [d["bins"][b]["exact_schedulable_frac"] or 0 for b in labels]
        ed = [d["bins"][b]["edf_ok_frac"] or 0 for b in labels]
        hm = [d["bins"][b]["harmonic_ok_frac"] or 0 for b in labels]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(x - 0.27, ex, 0.27, label="exact schedulable (state search)")
        ax.bar(x, ed, 0.27, label="EDF heuristic: no violation")
        ax.bar(x + 0.27, hm, 0.27, label="single-base harmonic rounding feasible")
        ax.axvline(4.5, color="k", ls="--", lw=1)
        ax.text(4.55, 1.02, "5/6", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, fontsize=9)
        ax.set_ylim(0, 1.08)
        ax.set_xlabel("density bin  Σ 1/K_i")
        ax.set_ylabel("fraction of random profiles")
        ax.set_title("E1 — schedulability vs density (N∈[3,8], K∈[2,14])")
        ax.legend(fontsize=9, loc="lower left")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS, "fig_E1_violation_vs_density.png"), dpi=160)
    # E2
    p = os.path.join(RESULTS, "E2_trace_frontier.json")
    if os.path.exists(p):
        d = json.load(open(p))
        fig, axs = plt.subplots(1, 2, figsize=(10, 4))
        for prof, mk, ls in (("uniform", "o", "-"), ("shaped_harm", "s", "--")):
            for N, col in ((4, "C0"), (6, "C1"), (8, "C2"), (12, "C3")):
                S = [s for s in d["summary"] if s["profile"] == prof and s["scheduler"] == "harmonic" and s["N"] == N]
                if not S:
                    continue
                axs[0].plot([s["busy_mean"] for s in S], [s["miss_all_rate_mean"] for s in S], marker=mk,
                            color=col, ls=ls, label=f"{prof} N={N}")
        axs[0].axvline(5 / 6, color="k", ls=":", lw=1)
        axs[0].set_xlabel("busy fraction of the accelerator (∝ energy)")
        axs[0].set_ylabel("uncertified miss rate (all events)")
        axs[0].set_title("E2 — uncertified miss vs energy (guaranteed harmonic scheduler)")
        axs[0].legend(fontsize=8, ncol=2)
        S = [s for s in d["summary"] if s["scheduler"] == "edf_lazy"]
        cmap = {"uniform": "C0", "shaped_harm": "C2", "shaped_int": "C3"}
        for prof, col in cmap.items():
            P = [s for s in S if s["profile"] == prof]
            axs[1].scatter([s["rho_mean"] for s in P], [s["violating_runs"] / s["n"] for s in P], c=col, label=prof)
        axs[1].legend(fontsize=9)
        axs[1].axvline(5 / 6, color="k", ls=":", lw=1)
        axs[1].set_xlabel("realised density ρ")
        axs[1].set_ylabel("fraction of runs with a certificate violation")
        axs[1].set_title("E2 — certificate violations of the lazy-EDF heuristic")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS, "fig_E2_frontier.png"), dpi=160)
    # E3
    p = os.path.join(RESULTS, "E3_switch_cost.json")
    if os.path.exists(p):
        d = json.load(open(p))
        fig, ax = plt.subplots(figsize=(6, 4))
        for s, col in ((0, "C0"), (1, "C1"), (2, "C2"), (3, "C3")):
            S = [r for r in d["summary"] if r["s"] == s]
            ax.plot([r["rho_eff"] for r in S], [r["violating_runs"] / r["n"] for r in S], marker="o", color=col,
                    label=f"switch cost s={s}")
        ax.axvline(1.0, color="k", ls=":", lw=1)
        ax.axvline(5 / 6, color="k", ls="--", lw=1)
        ax.set_xlabel("effective density (1+s)·Σ1/K_i")
        ax.set_ylabel("fraction of runs with certificate violation")
        ax.set_title("E3 — switch cost divides capacity (N=6, homogeneous K)")
        ax.legend(fontsize=9)
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS, "fig_E3_switch.png"), dpi=160)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="all", choices=["E1", "E2", "E3", "figs", "all", "check"])
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    random.seed(SEED)
    np.random.seed(SEED)
    videos, nframes, events, meta = load_corpus()
    json.dump(meta, open(os.path.join(RESULTS, "corpus_meta.json"), "w"), indent=1)
    print("corpus:", json.dumps({k: v for k, v in meta.items() if k != "source"}))
    if a.exp == "check":
        return
    t0 = time.time()
    if a.exp in ("E1", "all"):
        o = run_E1(a.quick)
        print("E1 bins:", json.dumps(o["bins"], indent=0)[:1500], f"[{time.time()-t0:.1f}s]")
    if a.exp in ("E2", "all"):
        o = run_E2(a.quick, videos, nframes, events)
        print("E2 summary rows:", len(o["summary"]), f"[{time.time()-t0:.1f}s]")
    if a.exp in ("E3", "all"):
        o = run_E3(a.quick, videos, nframes, events)
        print("E3 summary:", json.dumps(o["summary"])[:1200], f"[{time.time()-t0:.1f}s]")
    if a.exp in ("figs", "all"):
        make_figs()
        print("figs written")


if __name__ == "__main__":
    main()
