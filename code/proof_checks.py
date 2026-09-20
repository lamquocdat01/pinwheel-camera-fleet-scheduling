#!/usr/bin/env python3
"""
proof_checks.py -- Topic 34 (B1), round 2.  Machine checks for every claim the manuscript
asserts as a theorem.  Nothing is written into the manuscript unless the corresponding
check here passes.

Checks
  C0  Lemma 1 (certificate transfer): over every binary service pattern of length H and every
      window K <= 8, the K-refresh property holds iff every event of duration D >= K is
      detected; the worst detection latency over refreshing patterns is exactly K-1; and for
      every D < K some refreshing pattern misses an event of that duration.  Brute force.
  C1  Thm 1(iii): the family {2,3,M} is unschedulable for every M -- exhaustive state search.
  C2  Prop 2b: homogeneous capacity under switch cost is exactly floor(K/(1+s)) -- exhaustive
      search over schedules with an explicit switch penalty.
  C3  Prop 2c: q model groups, s between groups and 0 inside.  Sufficiency N+q*s <= K and
      necessity N+(q-1)*s <= K, checked exhaustively for small (N,q,s,K).
  C4  Cor 3: harmonic (power-of-two) rounding + FFD packs into m = ceil(sum 1/Khat) unit-density
      boxes, m <= ceil(2*rho), every box schedulable by the constructive harmonic scheduler.
  C5  Prop 3 (corrected): blackout budget B_i = l*(floor((K_i+l-2)/P_e)+1); the *old* budget
      l*(floor(K_i/P_e)+1) is shown to undercount by an explicit adversarial escalation phase.
  C6  Thm 3: greedy marginal allocation vs. exhaustive optimum on the discrete grid.

Usage:  python proof_checks.py            (~1 min)
Output: results/A3_proof_checks.json      (consumed by make_numbers.py)
Seed 42.
"""
import itertools, json, math, os, random, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC = os.path.abspath(os.path.join(HERE, ".."))
RESULTS = os.path.join(TOPIC, "results")
sys.path.insert(0, HERE)
from pinwheel_sim import exact_schedulable, harmonic_round, density  # noqa: E402

SEED = 42
OUT = {}


# --------------------------------------------------------------------------- C0
def check_C0(Kmax=8):
    """Lemma 1 by brute force, on one camera in isolation.

    A service pattern is a subset O of {0,...,H-1}: the slots at which the accelerator serves
    this camera. An event of onset o and duration D occupies slots o..o+D-1 and is *detected*
    iff O meets that interval; its latency is (first served slot in the interval) - o.

    For every K <= Kmax we enumerate every pattern of length H = 2K (enough to contain two
    disjoint windows of K slots, which is what the counterexample needs) and check:

      (a) equivalence   -- O has the K-refresh property  <=>  every event with D >= K that
                           fits inside the horizon is detected;
      (b) latency bound -- over refreshing patterns the worst latency of an event with
                           D >= K is at most K-1, and some refreshing pattern attains K-1;
      (c) not certifiable below K -- for every D < K there is a refreshing pattern and an
                           onset such that the event is missed.
    """
    rows = []
    for K in range(1, Kmax + 1):
        H = 2 * K
        refresh_equiv_ok = True
        worst_latency = -1
        missable = {D: False for D in range(1, K)}
        n_patterns = 0
        for mask in range(1 << H):
            n_patterns += 1
            served = [(mask >> t) & 1 for t in range(H)]
            # K-refresh property: every window of K consecutive slots holds a served slot
            refreshing = all(any(served[w:w + K]) for w in range(H - K + 1))
            # every long event inside the horizon is detected
            long_ok, lat = True, -1
            for D in range(K, H + 1):
                for o in range(H - D + 1):
                    hit = [t for t in range(o, o + D) if served[t]]
                    if not hit:
                        long_ok = False
                    else:
                        lat = max(lat, hit[0] - o)
            if refreshing != long_ok:
                refresh_equiv_ok = False
            if refreshing:
                worst_latency = max(worst_latency, lat)
                for D in range(1, K):
                    if missable[D]:
                        continue
                    for o in range(H - D + 1):
                        if not any(served[o:o + D]):
                            missable[D] = True
                            break
        rows.append({"K": K, "patterns": n_patterns,
                     "equivalence_holds": refresh_equiv_ok,
                     "worst_latency": worst_latency,
                     "latency_bound_tight": worst_latency == K - 1,
                     "short_durations_missable": all(missable.values())})
    return {"rows": rows, "Kmax": Kmax,
            "equivalence_all_K": all(r["equivalence_holds"] for r in rows),
            "tight_all_K": all(r["latency_bound_tight"] for r in rows),
            "short_missable_all_K": all(r["short_durations_missable"] for r in rows)}


# --------------------------------------------------------------------------- C1
def check_C1(Ms=range(3, 40)):
    """{2,3,M} must be unschedulable for every M (density 5/6 + 1/M)."""
    rows = []
    for M in Ms:
        r = exact_schedulable([2, 3, M], max_states=2_000_000)
        rows.append({"M": M, "rho": 5 / 6 + 1 / M, "schedulable": r})
    bad = [r for r in rows if r["schedulable"] is not False]
    return {"rows": rows, "all_unschedulable": not bad, "undecided_or_schedulable": bad,
            "M_max": max(Ms), "rho_min": min(r["rho"] for r in rows)}


# --------------------------------------------------------------------------- C2/C3
def feasible_with_switch(K, group, s, horizon_states=300_000):
    """Exact decision for the pinwheel instance K with a switch cost s paid whenever the served
    camera's *group* changes (group[i] == group[j] => no cost).  State = (u_1..u_N, last group).
    u_i = slots since camera i was last served.  Serving camera i at the current slot costs
    1 slot, preceded by s idle slots if group[i] != last group (and last group is defined).
    Returns True iff an infinite schedule exists (cycle in the reachable state graph)."""
    N = len(K)
    seen = {}

    def step(u, g, i):
        cost = 1 + (s if (g is not None and group[i] != g) else 0)
        # the served camera also ages across the s switch slots: its realised gap is u[i]+cost
        if u[i] + cost > K[i]:
            return None
        nu = []
        for j in range(N):
            v = (0 if j == i else u[j] + cost)
            if v >= K[j]:
                return None
            nu.append(v)
        # camera i is served in the last of the `cost` slots, so its own counter is 0
        return (tuple(nu), group[i])

    start = (tuple([0] * N), None)
    stack = [[start, 0]]
    seen[start] = 1
    while stack:
        if len(seen) > horizon_states:
            return None
        st, idx = stack[-1]
        u, g = st
        moved = False
        while idx < N:
            i = idx
            stack[-1][1] = idx + 1
            idx += 1
            ch = step(u, g, i)
            if ch is None:
                continue
            c = seen.get(ch, 0)
            if c == 1:
                return True
            if c == 0:
                seen[ch] = 1
                stack.append([ch, 0])
                moved = True
                break
        if not moved:
            seen[st] = 2
            stack.pop()
    return False


def check_C2(Ks=(4, 6, 8, 10, 12, 14, 16, 20, 24), ss=(1, 2, 3, 4), Nmax=10):
    """Homogeneous K, all cameras in distinct groups (every switch costs s).
    Claim: max feasible N = floor(K/(1+s)).  s = 0 is Corollary 1 and is covered by E1."""
    rows = []
    for K in Ks:
        for s in ss:
            pred = max(1, K // (1 + s))   # N = 1 never switches
            found, censored, undecided = 0, False, False
            for N in range(1, Nmax + 1):
                ok = feasible_with_switch([K] * N, list(range(N)), s)
                if ok is True:
                    found = N
                    if N == Nmax:
                        censored = True
                elif ok is False:
                    break
                else:
                    undecided = True
                    break
            match = (found == pred) if not (censored or undecided) else (pred >= found)
            rows.append({"K": K, "s": s, "predicted_Nmax": pred, "measured_Nmax": found,
                         "censored": censored, "undecided": undecided, "match": match})
    clean = [r for r in rows if not (r["censored"] or r["undecided"])]
    return {"rows": rows, "all_match": all(r["match"] for r in rows),
            "n_cells": len(rows), "n_clean": len(clean),
            "n_clean_exact": sum(1 for r in clean if r["measured_Nmax"] == r["predicted_Nmax"]),
            "n_match": sum(1 for r in rows if r["match"])}


def check_C3(Ks=(6, 8, 10, 12), ss=(1, 2, 3), qs=(1, 2, 3)):
    """q model groups of equal size; s only between groups.
    Sufficient claim: N + q*s <= K  =>  feasible.
    Necessary  claim: feasible      =>  N + (q-1)*s <= K."""
    rows = []
    for K in Ks:
        for s in ss:
            for q in qs:
                for per in range(1, 5):
                    N = q * per
                    if N > 9:
                        continue
                    group = [g for g in range(q) for _ in range(per)]
                    ok = feasible_with_switch([K] * N, group, s)
                    if ok is None:
                        continue
                    suff = (N + q * s <= K)
                    nec = (N + (q - 1) * s <= K)
                    rows.append({"K": K, "s": s, "q": q, "N": N, "feasible": ok,
                                 "suff_pred": suff, "nec_pred": nec,
                                 "suff_ok": (not suff) or ok,        # suff => feasible
                                 "nec_ok": (not ok) or nec})         # feasible => nec
    return {"rows": rows,
            "sufficiency_holds": all(r["suff_ok"] for r in rows),
            "necessity_holds": all(r["nec_ok"] for r in rows),
            "n_cells": len(rows),
            "n_tight": sum(1 for r in rows if r["feasible"] and not r["suff_pred"])}


# --------------------------------------------------------------------------- C4
def pow2_floor(k):
    return 1 << int(math.floor(math.log2(k)))


def ffd_unit_bins(items, cap=1.0, eps=1e-12):
    """First-Fit-Decreasing into bins of capacity cap.  Returns list of bins (lists of indices)."""
    order = sorted(range(len(items)), key=lambda i: -items[i])
    bins, load = [], []
    for i in order:
        placed = False
        for b in range(len(bins)):
            if load[b] + items[i] <= cap + eps:
                bins[b].append(i)
                load[b] += items[i]
                placed = True
                break
        if not placed:
            bins.append([i])
            load.append(items[i])
    return bins, load


def harmonic_box_ok(Ksub):
    """Is this box schedulable by the single-base harmonic constructive scheduler?
    (Powers of two share base 1; density <= 1 then suffices -- Prop. 1(a).)"""
    if not Ksub:
        return True
    for a in range(1, max(Ksub) + 1):
        Kp = harmonic_round(Ksub, a)
        if Kp is None:
            continue
        if sum(1.0 / k for k in Kp) <= 1.0 + 1e-12:
            return True
    return False


def check_C4(trials=4000, Nrange=(5, 60), Krange=(2, 64)):
    rng = random.Random(SEED)
    viol_bound, viol_sched, viol_lb = 0, 0, 0
    ratios = []
    rows = []
    for _ in range(trials):
        N = rng.randint(*Nrange)
        K = [rng.randint(*Krange) for _ in range(N)]
        rho = density(K)
        Khat = [pow2_floor(k) for k in K]
        x = [1.0 / k for k in Khat]
        bins, load = ffd_unit_bins(x, 1.0)
        m = len(bins)
        m_perfect = math.ceil(sum(x) - 1e-12)
        lb = math.ceil(rho - 1e-12)
        ok_sched = all(harmonic_box_ok([Khat[i] for i in b]) for b in bins)
        if m != m_perfect:
            viol_bound += 1
        if not ok_sched:
            viol_sched += 1
        if m > math.ceil(2 * rho - 1e-12):
            viol_lb += 1
        ratios.append(m / lb)
        rows.append({"N": N, "rho": rho, "m": m, "m_perfect": m_perfect, "lb": lb})
    return {"trials": trials,
            "ffd_equals_ceil_sum": viol_bound == 0,
            "every_box_harmonic_schedulable": viol_sched == 0,
            "m_le_ceil_2rho": viol_lb == 0,
            "ratio_m_over_lb_max": max(ratios), "ratio_m_over_lb_mean": sum(ratios) / len(ratios),
            "n_violations": {"perfect_packing": viol_bound, "schedulable": viol_sched,
                             "factor2": viol_lb}}


# --------------------------------------------------------------------------- C5
def blackout_worst_case(K, l, Pe):
    """Max number of blackout slots inside SOME window of K consecutive slots, over all
    escalation phases with starts >= Pe apart and length l.  Brute force over phase,
    prefix sums over windows."""
    best = 0
    span = 3 * (K + Pe + l) + 8
    for phase in range(Pe):
        busy = [0] * span
        t = phase
        while t < span:
            for u in range(t, min(t + l, span)):
                busy[u] = 1
            t += Pe
        pre = [0] * (span + 1)
        for u in range(span):
            pre[u + 1] = pre[u] + busy[u]
        for a in range(0, span - K):
            v = pre[a + K] - pre[a]
            if v > best:
                best = v
    return best


def check_C5():
    rows = []
    old_fail, new_fail = 0, 0
    for l in (2, 4, 8):
        for Pe in (8, 10, 12, 16, 20, 30, 50, 100, 200):
            for K in (8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256):
                if Pe < l:
                    continue
                w = blackout_worst_case(K, l, Pe)
                old = l * (K // Pe + 1)                      # T02 draft (start-counting)
                new = min(K, l * -(-(K + l - 1) // Pe))      # provable (intersection-counting)
                if old < w:
                    old_fail += 1
                if new < w:
                    new_fail += 1
                rows.append({"l": l, "Pe": Pe, "K": K, "worst": w, "draft_budget": old,
                             "provable_budget": new, "draft_ok": old >= w, "provable_ok": new >= w,
                             "provable_slack": new - w, "draft_slack": old - w})
    tight = min(rows, key=lambda r: r["draft_slack"])
    return {"rows": rows, "draft_budget_failures": old_fail, "provable_budget_failures": new_fail,
            "n_cells": len(rows),
            "draft_budget_tightest_cell": tight,
            "provable_ge_draft_frac": sum(1 for r in rows
                                          if r["provable_budget"] >= r["draft_budget"]) / len(rows)}


# --------------------------------------------------------------------------- C6
def greedy_shape(costs, grid, budget):
    """Marginal-allocation greedy used by the simulator: start at the coarsest window, then
    repeatedly buy the step with the best (objective drop)/(density cost)."""
    N = len(costs)
    idx = [len(grid) - 1] * N
    K = [grid[j] for j in idx]
    rho = sum(1.0 / k for k in K)
    while True:
        best, bi = 0.0, None
        for i in range(N):
            if idx[i] == 0:
                continue
            kn = grid[idx[i] - 1]
            dK = 1.0 / kn - 1.0 / K[i]
            if rho + dK > budget + 1e-12:
                continue
            gain = (costs[i](K[i]) - costs[i](kn)) / dK
            if gain > best:
                best, bi = gain, i
        if bi is None:
            break
        idx[bi] -= 1
        K[bi] = grid[idx[bi]]
        rho = sum(1.0 / k for k in K)
    return K, sum(costs[i](K[i]) for i in range(N))


def check_C6(trials=200, N=4, grid=(2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64)):
    """Compare greedy marginal allocation against the exhaustive grid optimum on small
    instances with heavy-tailed empirical duration laws (Pareto, alpha = 1.2)."""
    rng = random.Random(SEED)
    gaps = []
    worst = None
    grid = list(grid)
    for _ in range(trials):
        laws = [[max(1, int(rng.paretovariate(1.2))) for _ in range(rng.randint(10, 80))]
                for _ in range(N)]
        tab = [{k: sum(max(0.0, 1.0 - x / k) for x in d) for k in grid} for d in laws]

        def mk(i):
            return lambda k, i=i: tab[i][k]
        costs = [mk(i) for i in range(N)]
        budget = rng.choice([0.5, 2 / 3, 5 / 6, 1.0])
        Kg, og = greedy_shape(costs, grid, budget)
        best = None
        for combo in itertools.product(grid, repeat=N):
            if sum(1.0 / k for k in combo) > budget + 1e-12:
                continue
            o = sum(tab[i][combo[i]] for i in range(N))
            if best is None or o < best[0]:
                best = (o, combo)
        if best is None:
            continue
        gap = (og - best[0]) / max(1e-9, best[0])
        gaps.append(gap)
        if worst is None or gap > worst["gap"]:
            worst = {"gap": gap, "budget": budget, "greedy_K": Kg, "opt_K": list(best[1]),
                     "greedy_obj": og, "opt_obj": best[0]}
    gaps.sort()
    return {"trials": len(gaps), "N": N, "grid": grid,
            "gap_mean": sum(gaps) / len(gaps), "gap_max": gaps[-1],
            "gap_p95": gaps[int(0.95 * (len(gaps) - 1))],
            "frac_optimal": sum(1 for g in gaps if g < 1e-9) / len(gaps), "worst": worst}


# --------------------------------------------------------------------------- main
if __name__ == "__main__":
    os.makedirs(RESULTS, exist_ok=True)
    for name, fn in (("C0_certificate_transfer", check_C0),
                     ("C1_two_three_M", check_C1), ("C2_switch_capacity", check_C2),
                     ("C3_model_groups", check_C3), ("C4_harmonic_dimensioning", check_C4),
                     ("C5_blackout_budget", check_C5), ("C6_greedy_vs_optimum", check_C6)):
        OUT[name] = fn()
        head = {k: v for k, v in OUT[name].items() if not isinstance(v, (list, dict))}
        print(name, "->", json.dumps(head)[:400])
    OUT["meta"] = {"seed": SEED, "script": "code/proof_checks.py"}
    json.dump(OUT, open(os.path.join(RESULTS, "A3_proof_checks.json"), "w"), indent=1)
    print("\nwritten:", os.path.join(RESULTS, "A3_proof_checks.json"))
