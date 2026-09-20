#!/usr/bin/env python3
"""
make_numbers.py -- generate Submission_FGCS/latex/numbers.tex from results/*.json.

LAW C6: every measured number printed in the manuscript comes from here. Nothing is typed
by hand into main.tex. If a JSON is missing, the macro is emitted as \TODO{...} so that the
render check (C5/C2) catches it on the rendered PDF.

Usage:  python code/make_numbers.py
"""
import json, math, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TOPIC = os.path.abspath(os.path.join(HERE, ".."))
RESULTS = os.path.join(TOPIC, "results")

def _find_latex_dir(start):
    """Locate the directory holding main.tex. Works both in the author's working tree
    (<topic>/Submission_FGCS/latex) and in the published repository (<repo>/latex)."""
    d = os.path.abspath(start)
    for _ in range(4):
        for cand in (os.path.join(d, "latex"),
                     os.path.join(d, "Submission_FGCS", "latex")):
            if os.path.exists(os.path.join(cand, "main.tex")):
                return cand
        d = os.path.dirname(d)
    return os.path.join(start, "latex")


def _find_file(name, *roots):
    for r in roots:
        p = os.path.join(r, name)
        if os.path.exists(p):
            return p
    return os.path.join(roots[0], name)

OUT = os.path.join(_find_latex_dir(TOPIC), "numbers.tex")

L = []
MISSING = []


def load(name):
    p = os.path.join(RESULTS, name)
    if not os.path.exists(p):
        MISSING.append(name)
        return None
    return json.load(open(p))


def emit(macro, value, comment=""):
    L.append("\\newcommand{\\%s}{%s}%s" % (macro, value, ("   %% %s" % comment) if comment else ""))


def num(x, nd=0):
    if x is None:
        return "\\TODO{missing}"
    if nd == 0:
        return "{:,}".format(int(round(x)))   # English thousands separator, as Elsevier expects
    return ("%." + str(nd) + "f") % x


def pct(x, nd=1):
    return ("%." + str(nd) + "f") % (100.0 * x)


# ---------------------------------------------------------------- corpus
c = load("corpus_meta.json")
if c:
    emit("numVideos", num(c["n_videos"]))
    emit("numEvents", num(c["n_events"]))
    emit("numFrames", num(c["n_frames"]))
    for k, v in c["datasets"].items():
        emit("numVid" + k.replace("2014", ""), num(v))
    emit("numShaCorpus", c["source"]["event_corpus.csv"][:12])

# ---------------------------------------------------------------- A3 proof checks
a3 = load("A3_proof_checks.json")
if a3:
    C0 = a3.get("C0_certificate_transfer")
    if C0:
        emit("numCzeroKmax", num(C0["Kmax"]))
        emit("numCzeroPatterns", num(sum(r["patterns"] for r in C0["rows"])))
    C1 = a3["C1_two_three_M"]
    emit("numConeN", num(len(C1["rows"])))
    emit("numConeMmax", num(C1["M_max"]))
    emit("numConeRhoMin", num(C1["rho_min"], 5))
    C2 = a3["C2_switch_capacity"]
    emit("numCtwoClean", num(C2["n_clean"]))
    emit("numCtwoExact", num(C2["n_clean_exact"]))
    emit("numCtwoCells", num(C2["n_cells"]))
    C3 = a3["C3_model_groups"]
    q2 = [r for r in C3["rows"] if r["q"] >= 2]
    band = [r for r in q2 if (r["N"] + (r["q"] - 1) * r["s"]) <= r["K"] < (r["N"] + r["q"] * r["s"])]
    emit("numCthreeCells", num(C3["n_cells"]))
    emit("numCthreeQtwo", num(len(q2)))
    emit("numCthreeBand", num(len(band)))
    emit("numCthreeBandFeasible", num(sum(1 for r in band if r["feasible"])))
    C4 = a3["C4_harmonic_dimensioning"]
    emit("numCfourTrials", num(C4["trials"]))
    emit("numCfourRatioMean", num(C4["ratio_m_over_lb_mean"], 3))
    emit("numCfourRatioMax", num(C4["ratio_m_over_lb_max"], 3))
    C5 = a3["C5_blackout_budget"]
    emit("numCfiveCells", num(C5["n_cells"]))
    emit("numCfiveFail", num(C5["provable_budget_failures"]))
    emit("numCfiveDraftFail", num(C5["draft_budget_failures"]))
    C6 = a3["C6_greedy_vs_optimum"]
    emit("numCsixTrials", num(C6["trials"]))
    emit("numCsixOptFrac", pct(C6["frac_optimal"]))
    emit("numCsixGapMean", pct(C6["gap_mean"], 2))
    emit("numCsixGapMax", pct(C6["gap_max"], 2))
    emit("numCsixGapPninefive", pct(C6["gap_p95"], 2))

# ---------------------------------------------------------------- E1 / E1b
e1 = load("E1_density_sweep.json")
if e1:
    emit("numEoneInstances", num(e1["meta"]["n_instances"]))
    below = [b for b in e1["bins"] if float(b.split(",")[1][:-1]) <= 5 / 6 + 1e-9]
    emit("numEoneBelowN", num(sum(e1["bins"][b]["n_decided"] for b in below)))
    emit("numEoneBelowUnsched",
         num(sum(e1["bins"][b]["unschedulable_below_5_6"] for b in e1["bins"])))
    emit("numEoneEdfSeventy", num(1 - e1["bins"]["(0.700,0.750]"]["edf_ok_frac"], 2))
    emit("numEoneEdfSeventyPct", pct(1 - e1["bins"]["(0.700,0.750]"]["edf_ok_frac"], 0))
    emit("numEoneEdfEightPct", pct(1 - e1["bins"]["(0.750,0.833]"]["edf_ok_frac"], 0))
    emit("numEoneHarmEightPct", pct(e1["bins"]["(0.750,0.833]"]["harmonic_ok_frac"], 0))
    emit("numEoneWheelEightPct", pct(e1["bins"]["(0.750,0.833]"]["wheel_ok_frac"], 0))
    emit("numEoneHarmNinePct", pct(e1["bins"]["(0.833,0.900]"]["harmonic_ok_frac"], 0))
    emit("numEoneWheelNinePct", pct(e1["bins"]["(0.833,0.900]"]["wheel_ok_frac"], 0))
    emit("numEoneUndecided", num(sum(1 for r in e1["instances"] if r["exact"] is None)))
    emit("numEoneWheelCands", num(len(__import__("importlib")
                                      .import_module("pinwheel_sim").WHEEL_CANDIDATES)))
e1b = load("E1b_admission_conservatism.json")
if e1b:
    emit("numConservPct", pct(e1b["overall"]["conservatism"], 1))
    emit("numConservRefused", num(e1b["overall"]["n_refused"]))
    emit("numConservSched", num(e1b["overall"]["n_schedulable"]))

# ---------------------------------------------------------------- E2
e2 = load("E2_trace_frontier.json")
if e2:
    S = [s for s in e2["summary"] if s["scheduler"] == "harmonic"]
    emit("numEtwoCertTotal", num(sum(s["n_cert_total"] for s in S)))
    emit("numEtwoCertMissed", num(sum(s["miss_cert_total"] for s in S)))
    ED0 = [s for s in e2["summary"] if s["scheduler"] == "edf_lazy"]
    emit("numEtwoEdfCertTotal", num(sum(s["n_cert_total"] for s in ED0)))
    emit("numEtwoEdfCertMissed", num(sum(s["miss_cert_total"] for s in ED0)))
    # violating runs are reported over the heterogeneous profiles only: with a homogeneous
    # profile lazy EDF degenerates to round robin and never violates, so including those runs
    # in the denominator would understate the failure rate of the heuristic.
    EDH = [s for s in ED0 if s["profile"] != "uniform"]
    emit("numEtwoEdfHetViolRuns", num(sum(s["violating_runs"] for s in EDH)))
    emit("numEtwoEdfHetRuns", num(sum(s["n"] for s in EDH)))
    emit("numEtwoEdfUnifViolRuns", num(sum(s["violating_runs"] for s in ED0
                                           if s["profile"] == "uniform")))
    gains = []
    for N in sorted({s["N"] for s in S}):
        for r in sorted({s["rho_star"] for s in S}):
            u = next((s for s in S if s["N"] == N and s["rho_star"] == r
                      and s["profile"] == "uniform"), None)
            h = next((s for s in S if s["N"] == N and s["rho_star"] == r
                      and s["profile"] == "shaped_harm"), None)
            if u and h and u["miss_all_rate_mean"] > 0:
                gains.append((h["miss_all_rate_mean"] - u["miss_all_rate_mean"])
                             / u["miss_all_rate_mean"])
    emit("numEtwoGainMinPct", pct(-max(gains), 0))
    emit("numEtwoGainMaxPct", pct(-min(gains), 0))
    emit("numEtwoBoundErr", num(max(abs(s["lemma2_bound_rate_mean"] - s["miss_all_rate_mean"])
                                    for s in S if s["profile"] != "shaped_int"), 3))
    ED = [s for s in e2["summary"] if s["scheduler"] == "edf_lazy"]
    emit("numEtwoEdfViolRuns", num(sum(s["violating_runs"] for s in ED)))
    emit("numEtwoEdfRuns", num(sum(s["n"] for s in ED)))
    emit("numEtwoLatUnifMax", num(max(s["lat_max_cert_max"] for s in S
                                      if s["profile"] == "uniform")))
    emit("numEtwoLatShapedMax", num(max(s["lat_max_cert_max"] for s in S
                                        if s["profile"] == "shaped_harm")))
    # divisor wheel (round 3): same certificate, more profiles it can actually build
    W = [s for s in e2["summary"] if s["scheduler"] == "wheel"]
    if W:
        emit("numEtwoWheelCertTotal", num(sum(s["n_cert_total"] for s in W)))
        emit("numEtwoWheelCertMissed", num(sum(s["miss_cert_total"] for s in W)))
        for tag, prof in (("Int", "shaped_int"),):
            fh = [r for r in e2["runs"] if r["profile"] == prof and r["scheduler"] == "harmonic"]
            fw = [r for r in e2["runs"] if r["profile"] == prof and r["scheduler"] == "wheel"]
            emit("numEtwoHarmFeas" + tag, num(sum(1 for r in fh if r["feasible"])))
            emit("numEtwoWheelFeas" + tag, num(sum(1 for r in fw if r["feasible"])))
            emit("numEtwoFeasRuns" + tag, num(len(fh)))

# ---------------------------------------------------------------- E3
e3 = load("E3_switch_cost.json")
if e3:
    ok = sum(1 for s in e3["summary"]
             if (s["prop2_feasible"] and s["violating_runs"] == 0)
             or ((not s["prop2_feasible"]) and s["violating_runs"] == s["n"]))
    emit("numEthreeCells", num(len(e3["summary"])))
    emit("numEthreeCorrect", num(ok))

# ---------------------------------------------------------------- E4
e4 = load("E4_fleet_dimensioning.json")
if e4:
    R = e4["rows"]
    emit("numEfourCameras", num(e4["meta"]["M_cameras"]))
    cor3 = [r for r in R if r["method"] == "cor3_harmonic_ffd"]
    ffd = [r for r in R if r["method"] == "ffd_5_6_heuristic"]
    edf = [r for r in R if r["method"] == "edf_fit_heuristic"]
    emit("numEfourCorThreeRatioMin", num(min(r["boxes_over_lb"] for r in cor3), 2))
    emit("numEfourCorThreeRatioMax", num(max(r["boxes_over_lb"] for r in cor3), 2))
    emit("numEfourCorThreeAtLB", num(sum(1 for r in cor3 if r["boxes"] == r["lower_bound_boxes"])))
    emit("numEfourConfigs", num(len(cor3)))
    worse = sum(1 for a, b in zip(sorted(cor3, key=lambda r: (r["profile"], r["K_target"])),
                                  sorted(ffd, key=lambda r: (r["profile"], r["K_target"])))
                if b["boxes"] > a["boxes"])
    emit("numEfourFfdWorse", num(worse))
    emit("numEfourFfdViolCam", num(sum(r["violating_cameras"] for r in ffd)))
    emit("numEfourFfdMissCert", num(sum(r["miss_cert"] for r in ffd)))
    emit("numEfourCorThreeViol", num(sum(r["violating_cameras"] for r in cor3)))
    u8 = next(r for r in cor3 if r["profile"] == "uniform" and r["K_target"] == 8)
    emit("numEfourUEightBoxes", num(u8["boxes"]))
    emit("numEfourUEightLB", num(u8["lower_bound_boxes"]))
    emit("numEfourUEightFfd", num(next(r["boxes"] for r in ffd
                                       if r["profile"] == "uniform" and r["K_target"] == 8)))
    h12 = next(r for r in cor3 if r["profile"] == "trace_heterogeneous" and r["K_target"] == 12)
    emit("numEfourHTwelveBoxes", num(h12["boxes"]))
    emit("numEfourHTwelveLB", num(h12["lower_bound_boxes"]))

# ---------------------------------------------------------------- E5
e5 = load("E5_churn_admission.json")
if e5:
    hi = max(s["lambda_in"] for s in e5["summary"])
    emit("numEfiveLamHigh", num(hi, 3))
    emit("numEfiveLamLevels", num(len({s["lambda_in"] for s in e5["summary"]})))
    def g(pol, field, lam=None):
        return next(s[field] for s in e5["summary"]
                    if s["policy"] == pol and s["lambda_in"] == (lam if lam else hi))
    emit("numEfiveEdfViol", num(g("admit_then_edf", "violations_per_1k_slots"), 3))
    emit("numEfiveDensViol", num(g("density_5_6", "violations_per_1k_slots"), 3))
    emit("numEfiveHarmViol", num(g("density_1_harmonic", "violations_per_1k_slots"), 3))
    emit("numEfiveResViol", num(g("harmonic_residue_constructive", "violations_per_1k_slots"), 3))
    for pol, tag in (("admit_then_edf", "Edf"), ("density_5_6", "Dens"),
                     ("density_1_harmonic", "Harm"), ("harmonic_residue_constructive", "Res")):
        emit("numEfive" + tag + "Busy", num(g(pol, "busy_fraction"), 3))
    emit("numEfiveEdfRej", pct(g("admit_then_edf", "rejection_rate")))
    emit("numEfiveDensRej", pct(g("density_5_6", "rejection_rate")))
    emit("numEfiveResRej", pct(g("harmonic_residue_constructive", "rejection_rate")))
    r = g("admit_then_edf", "violations_per_1k_slots") / max(1e-9, g("density_5_6", "violations_per_1k_slots"))
    emit("numEfiveDensFactor", num(r, 0))
    # What the guarantee costs *relative to admit-then-EDF*: the extra share of requests the
    # constructive scheduler turns away, in percentage points, and one over that share as a
    # "one camera in N" reading. Both are derived here so that neither is typed into main.tex,
    # and so that the text cannot quote the absolute refusal rate as if it were the price.
    extra = (g("harmonic_residue_constructive", "rejection_rate")
             - g("admit_then_edf", "rejection_rate"))
    emit("numEfiveResExtraRejPP", num(100.0 * extra, 1))
    emit("numEfiveResExtraRejOneIn", num(round(1.0 / max(1e-9, extra))))
    emit("numEfiveResZeroCells",
         num(sum(1 for s in e5["summary"]
                 if s["policy"] == "harmonic_residue_constructive"
                 and s["violations_per_1k_slots"] == 0)))
    emit("numEfivePolicyCells", num(len({s["lambda_in"] for s in e5["summary"]})))

# ---------------------------------------------------------------- E6
e6 = load("E6_blackout.json")
if e6:
    emit("numEsixCells", num(e6["prediction_cells"]))
    emit("numEsixCorrect", num(e6["prediction_cells_correct"]))
    emit("numEsixSeeds", num(e6["meta"]["H"] and len({r["seed"] for r in e6["runs"]})))

# ---------------------------------------------------------------- E7
e7 = load("E7_energy.json")
if e7:
    r_main = e7["meta"]["r_main"]
    emit("numRmain", num(r_main, 0))
    emit("numRgrid", ", ".join("%g" % x for x in e7["meta"]["r_grid"]))
    # headline range is quoted at the principal ratio
    emit("numGainMin", num(e7["gain_min"], 2))
    emit("numGainMax", num(e7["gain_max"], 2))
    for r_val, tag in zip(e7["meta"]["r_grid"], ("Rlo", "Rmid", "Rhi")):
        g = e7["by_r"]["%g" % r_val]
        emit("numR" + tag, num(r_val, 0))
        emit("numGainMin" + tag, num(g["gain_min"], 2))
        emit("numGainMax" + tag, num(g["gain_max"], 2))
    b = next(r for r in e7["rows"] if r["N"] == 12 and abs(r["rho_star"] - 0.5) < 1e-6
             and r["profile"] == "shaped_harm" and r["r"] == r_main)
    emit("numTwelveHalfShared", num(b["e_per_camera_frame_shared"], 2))
    emit("numTwelveHalfPrivate", num(b["e_per_camera_frame_private"], 2))
    emit("numTwelveHalfGain", num(b["consolidation_gain"], 2))

# ---------------------------------------------------------------- E8
e8 = load("E8_sensitivity.json")
if e8:
    H = e8["holdout"]
    emit("numHoldoutVideos", num(e8["meta"]["holdout_eligible_videos"]))
    emit("numHoldoutTotal", num(e8["meta"]["holdout_total_videos"]))
    emit("numHoldoutCells", num(H["cells"]))
    emit("numHoldoutWins", num(H["holdout_wins_cells"]))
    emit("numHoldoutGain", num(-H["mean_gain_holdout_pct"], 1))
    emit("numOracleGain", num(-H["mean_gain_oracle_pct"], 1))
    emit("numOracleShare", num(100.0 * (1 - H["mean_gain_holdout_pct"] / H["mean_gain_oracle_pct"]), 0))
    P = e8["per_dataset"]["rows"]
    emit("numPerDsCells", num(len(P)))
    emit("numPerDsWins", num(sum(1 for r in P if r["gain_pct"] < 0)))
    for ds, tag in (("CDnet2014", "Cdnet"), ("LASIESTA", "Lasiesta"), ("BMC", "Bmc")):
        rr = [r for r in P if r["dataset"] == ds]
        emit("numGain" + tag, num(-sum(r["gain_pct"] for r in rr) / len(rr), 1))
        st = e8["per_dataset"]["duration_stats"][ds]
        emit("numMed" + tag, num(st["median_duration"], 0))
        emit("numPninety" + tag, num(st["p90_duration"], 0))
        emit("numMean" + tag, num(st["mean_duration"], 1))
        emit("numEv" + tag, num(st["n_events"]))
    C = e8["latency_cap"]["rows"]
    c16 = next(r for r in C if r["N"] == 6 and abs(r["rho_star"] - 5 / 6) < 1e-6 and r["K_max"] == 16)
    c64 = next(r for r in C if r["N"] == 6 and abs(r["rho_star"] - 5 / 6) < 1e-6 and r["K_max"] == 64)
    emit("numCapMissSixteen", num(c16["miss_all_rate"], 3))
    emit("numCapMissSixtyfour", num(c64["miss_all_rate"], 3))
    emit("numCapLatSixteen", num(c16["lat_max_cert"]))
    emit("numCapLatSixtyfour", num(c64["lat_max_cert"]))
    emit("numCapCostPct", num(100.0 * (c16["miss_all_rate"] - c64["miss_all_rate"])
                              / c64["miss_all_rate"], 0))
    RR = e8["round_robin_baseline"]["rows"]
    r6 = next(r for r in RR if r["N"] == 6 and abs(r["rho_star"] - 0.5) < 1e-6)
    emit("numRRMissSix", num(r6["rr_miss"], 3))
    emit("numRROursSix", num(r6["harm_miss"], 3))

# ---------------------------------------------------------------- refs
rp = _find_file("refs_verified.json", HERE, os.path.join(TOPIC, "Submission_FGCS"))
if os.path.exists(rp):
    rv = json.load(open(rp))
    emit("numRefsTotal", num(len(rv)))
    emit("numRefsOK", num(sum(1 for r in rv.values() if r["status"] == "OK")))
    def preprint_only(r):
        if r["doi"]:
            return False
        a = r["sources"].get("arxiv") or {}
        return not (isinstance(a, dict) and a.get("doi"))     # a journal DOI found on arXiv counts as archival
    emit("numRefsPreprint", num(sum(1 for r in rv.values() if preprint_only(r))))
else:
    MISSING.append("refs_verified.json")

# ---------------------------------------------------------------- code repository
# The repository macros go into their own file, latex/repo.tex, which is NOT tracked by the
# public repository. Reason: the Data availability section quotes the commit hash of the
# published tag, and if that macro lived in a tracked file, writing it would change the tree and
# therefore the hash. main.tex falls back to placeholders when repo.tex is absent, so a reader
# who clones the repository can still build the manuscript.
REPO_OUT = os.path.join(_find_latex_dir(TOPIC), "repo.tex")
rp2 = os.path.join(RESULTS, "repo_meta.json")
if os.path.exists(rp2):
    rm = json.load(open(rp2))
    repo_lines = [
        "% repo.tex -- GENERATED by code/make_numbers.py from results/repo_meta.json.",
        "% Not tracked by the code repository (see the comment in make_numbers.py).",
        "\\renewcommand{\\numRepoUrl}{%s}" % rm["url"],
        "\\renewcommand{\\numRepoCommit}{%s}" % rm["commit"][:12],
        "\\renewcommand{\\numRepoTag}{%s}" % rm["tag"],
    ]
    with open(REPO_OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(repo_lines) + "\n")
    print("wrote repo macros -> %s" % REPO_OUT)
else:
    MISSING.append("repo_meta.json (repository not published yet)")

emit("numBuildDate", date.today().isoformat())

hdr = ["%% numbers.tex -- GENERATED by code/make_numbers.py on %s. DO NOT EDIT BY HAND." % date.today(),
       "%% Every measured value in main.tex comes from results/*.json (law C6).",
       "%% Regenerate:  python code/make_numbers.py", ""]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(hdr + sorted(L)) + "\n")
print("wrote %d macros -> %s" % (len(L), OUT))
if MISSING:
    print("MISSING inputs:", MISSING)
    sys.exit(1)
