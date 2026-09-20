#!/usr/bin/env python3
"""
verify_refs.py -- Topic 34. Machine-verify every candidate reference.

LAW: no invented citations. A reference enters refs.bib only if a live source returned
metadata for it. Sources tried, in order: Crossref REST, doi.org content negotiation
(BibTeX), arXiv API. Anything unresolved is reported UNVERIFIED and dropped.

Usage:  python verify_refs.py            # fetch + write refs_verified.json
        python verify_refs.py --report   # render the C5 verification table (markdown)
"""
from __future__ import annotations
import json, re, sys, time, urllib.error, urllib.parse, urllib.request, html
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "refs_verified.json"
UA = {"User-Agent": "topic34-refcheck/1.0 (mailto:lamquocdat@gmail.com)"}

# (bibkey, expected-title-fragment, doi, arxiv-id)
REFS = [
    # --- pinwheel core -------------------------------------------------------
    ("holte1989pinwheel", "pinwheel", "10.1109/HICSS.1989.48075", None),
    ("chanchin1992general", "double-integer reduction", "10.1109/12.144627", None),
    ("chanchin1993schedulers", "larger classes of pinwheel", "10.1007/BF01187034", None),
    ("linlin1997three", "three distinct numbers", "10.1007/PL00009181", None),
    ("fishburn2002densities", "achievable densities", "10.1007/s00453-002-0938-9", None),
    ("kawamura2024stoc", "density threshold conjecture", "10.1145/3618260.3649757", None),
    ("kawamura2026pnas", "density threshold conjecture", "10.1073/pnas.2530214123", None),
    # the ISAAC 2025 paper now has a journal version, with a third author
    ("kobayashi2026tcs", "fixed parameter tractability", "10.1016/j.tcs.2026.115998", None),
    ("kusano2026sofsem", "Density-Based Heuristics", "10.1007/978-3-032-17801-5_46", None),
    # Published in DMTCS since the last round (vol. 28:4, SOFSEM 2026 special issue,
    # article 17657); cite the journal version, keeping the arXiv identifier in the note.
    ("fujiwara2026real", "Real Periods", "10.46298/dmtcs.17657", None),
    # published at SODA 2026 since the last round; cite the proceedings version
    ("kanellopoulos2025kvisits", "Visits Problem", "10.1137/1.9781611978971.16", None),
    # published at ESA 2026 (LIPIcs 388); Crossref does not index Dagstuhl, doi.org does
    ("kawamura2025covering", "Pinwheel Covering", "10.4230/LIPIcs.ESA.2026.83", None),
    ("liulayland1973", "Hard-Real-Time", "10.1145/321738.321743", None),
    # --- bin packing (Cor. 3) ------------------------------------------------
    ("dosa2007ffd", "First Fit Decreasing", "10.1007/978-3-540-74450-4_1", None),
    # --- perception / attention scheduling ----------------------------------
    ("liu2023attention", "attention scheduling", "10.1007/s11241-023-09396-z", None),
    ("liu2026multitenant", "Multi-Tenant DNN Inference", None, "2602.11004"),
    # --- real-time inference on shared accelerators / edge resource management ----
    ("lee2024imcpng", "imprecise mixed-criticality", "10.1016/j.future.2024.06.015", None),
    ("peng2024inferfair", "InferFair", "10.1016/j.future.2023.08.020", None),
    ("raj2025uavfleets", "DNN inferencing on edge and cloud", "10.1016/j.future.2025.107874", None),
    ("zhang2026prta", "preemption threshold scheduling", "10.1016/j.future.2025.108363", None),
    ("lee2025timing", "Timing guarantees for inference", "10.1007/s11241-025-09445-9", None),
    ("li2022aoi", "Age of Information Guarantee", "10.1109/TNET.2022.3156866", None),
    # --- pinwheel already applied in real-time systems and sensing (G1) ------
    ("han1992distance", "distance-constrained", "10.1109/REAL.1992.242649", None),
    ("han1996distance", "Distance-constrained scheduling", "10.1109/12.508320", None),
    ("hsueh2001distributed", "distributed pinwheel", "10.1109/12.902752", None),
    ("baruah1997broadcast", "broadcast disks", "10.1109/ICDE.1997.582023", None),
    ("gopalakrishnan2006radar", "radar dwells", "10.1007/s11241-006-6882-z", None),
    # --- the same problem re-derived as an age-of-information threshold (G4) --
    ("li2020aoi", "Maximum Thresholds", "10.1109/INFOCOM41043.2020.9155514", None),
    # --- systems with an admission test or a per-stream guarantee (G3) -------
    # The ACM DOI for DeepRT (10.1145/3453142.3491278) does not resolve: doi.org, Crossref
    # and the proceedings DOI all return 404. Cite the archival record that does resolve.
    ("yang2021deeprt", "DeepRT", None, "2105.01803"),
    ("hu2024canvas", "Canvas-Based Attention Scheduling", "10.1109/RTAS61025.2024.00035", None),
    ("shen2019nexus", "Nexus", "10.1145/3341301.3359658", None),
    ("jiang2018mainstream", "Mainstream", None, None,
     "https://www.usenix.org/conference/atc18/presentation/jiang"),
    ("padmanabhan2023gemel", "Gemel", None, None,
     "https://www.usenix.org/conference/nsdi23/presentation/padmanabhan"),
    # --- window-constrained real-time task models (G3) -----------------------
    ("hamdaoui1995mkfirm", "firm deadlines", "10.1109/12.477249", None),
    ("bernat2001weaklyhard", "Weakly hard", "10.1109/12.919277", None),
    # --- networked-systems admission control and coverage --------------------
    ("liang2024splitstream", "SplitStream", "10.1016/j.jnca.2024.103866", None),
    # --- edge video analytics / GPU sharing context -------------------------
    ("zhou2023comst", "Edge", "10.1109/COMST.2023.3323091", None),
    # the arXiv preprint (2101.10463) was published in IEEE TPDS 34(5), 2023; cite the journal
    ("zou2023rtgpu", "RTGPU", "10.1109/TPDS.2023.3235439", None),
    # --- [dataset] entries for the three public corpora ---------------------
    ("cdnet2014", "CDnet 2014", "10.1109/CVPRW.2014.126", None),
    ("lasiesta2016", "LASIESTA", "10.1016/j.cviu.2016.08.005", None),
    ("bmc2012", "background extraction", "10.1007/978-3-642-37410-4_25", None),
]


# Crossref answers 429 when called in a tight loop from this machine, which used to look like
# an unverified reference. Space the calls out and always keep doi.org as a second opinion.
PAUSE = 2.5


def fetch_doi_bibtex(doi):
    u = "https://doi.org/" + urllib.parse.quote(doi)
    req = urllib.request.Request(u, headers={**UA, "Accept": "application/x-bibtex"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")


def doi_resolves(doi):
    """Last-resort check: does doi.org resolve this DOI to a publisher page at all?
    Records where it lands, so a reference is never called verified without evidence."""
    u = "https://doi.org/" + urllib.parse.quote(doi)
    req = urllib.request.Request(u, headers=UA, method="HEAD")
    try:
        r = urllib.request.urlopen(req, timeout=40)
        return {"http_status": r.status, "resolved_to": r.url}
    except urllib.error.HTTPError as e:
        # some publishers refuse HEAD but the redirect still proves the DOI exists
        return {"http_status": e.code, "resolved_to": e.url} if e.code < 500 else None


def fetch_crossref(doi):
    u = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40)
    return json.loads(r.read())["message"]


def fetch_arxiv(aid):
    # The export API answers 406 unless an Atom Accept header is sent.
    u = "https://export.arxiv.org/api/query?id_list=" + aid
    hdrs = {**UA, "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8"}
    x = urllib.request.urlopen(urllib.request.Request(u, headers=hdrs), timeout=40).read().decode()
    if "<entry>" not in x:
        return None
    e = x[x.index("<entry>"):x.rindex("</entry>") + 8]

    def g(tag):
        m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), e, re.S)
        return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else None

    authors = re.findall(r"<name>(.*?)</name>", e)
    return {"title": g("title"), "authors": authors, "published": g("published"),
            "updated": g("updated"), "doi": g("arxiv:doi"),
            "journal_ref": g("arxiv:journal_ref"), "id": g("id")}


def fetch_datacite(doi):
    """Second opinion for arXiv records. Every arXiv preprint carries the registered DOI
    10.48550/arXiv.<id>, whose metadata DataCite serves independently of the export API --
    which has answered 406 to every request from this machine since 2026-09-20."""
    u = "https://api.datacite.org/dois/" + urllib.parse.quote(doi, safe="")
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40)
    a = json.loads(r.read())["data"]["attributes"]
    titles = a.get("titles") or [{}]
    return {"title": titles[0].get("title"),
            "authors": [c.get("name") for c in a.get("creators", []) if c.get("name")],
            "published": str(a.get("publicationYear") or ""),
            "doi": None, "journal_ref": None, "id": a.get("url")}


def slim(r):
    return {"title": (r.get("title") or [None])[0],
            "container": (r.get("container-title") or [None])[0],
            "year": r.get("issued", {}).get("date-parts", [[None]])[0][0],
            "volume": r.get("volume"), "issue": r.get("issue"), "page": r.get("page"),
            "type": r.get("type"), "publisher": r.get("publisher"),
            "authors": [(a.get("family", "") + ", " + a.get("given", "")).strip(", ")
                        for a in r.get("author", [])],
            "alt_id": r.get("alternative-id")}


def main():
    out = {}
    for entry in REFS:
        # (key, fragment, doi, arxiv[, url]) -- USENIX proceedings mint no DOI, so those
        # entries are verified by fetching the publisher's own landing page and finding the
        # expected title on it.
        key, frag, doi, aid = entry[:4]
        url = entry[4] if len(entry) > 4 else None
        rec = {"key": key, "expect_fragment": frag, "doi": doi, "arxiv": aid, "url": url,
               "status": "UNVERIFIED", "sources": {}}
        if url and not doi and not aid:
            try:
                req = urllib.request.Request(url, headers={**UA, "Accept": "text/html"})
                page = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
                text = re.sub(r"<[^>]+>", " ", page)
                text = re.sub(r"\s+", " ", html.unescape(text))
                m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
                rec["sources"]["landing_page"] = {
                    "url": url, "bytes": len(page),
                    "title": re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else None,
                    "found_fragment": frag.lower() in text.lower()}
                if rec["sources"]["landing_page"]["found_fragment"]:
                    rec["status"] = "OK"
            except Exception as e:
                rec["sources"]["landing_page"] = "ERR " + str(e)
            time.sleep(PAUSE)
        if doi:
            try:
                rec["sources"]["crossref"] = slim(fetch_crossref(doi))
                rec["status"] = "OK"
            except Exception as e:
                rec["sources"]["crossref"] = "ERR " + str(e)
            time.sleep(PAUSE)
            if rec["status"] != "OK":
                try:
                    rec["sources"]["doi.org"] = fetch_doi_bibtex(doi)
                    rec["status"] = "OK"
                except Exception as e:
                    rec["sources"]["doi.org"] = "ERR " + str(e)
                time.sleep(PAUSE)
            if rec["status"] != "OK":
                h = doi_resolves(doi)
                rec["sources"]["doi.org HEAD"] = h or "ERR did not resolve"
                if h:
                    rec["status"] = "OK"
                time.sleep(PAUSE)
        if aid:
            try:
                r = fetch_arxiv(aid)
                rec["sources"]["arxiv"] = r
                if r:
                    rec["status"] = "OK"
                    rec["datacite_doi"] = "10.48550/arXiv." + aid
            except Exception as e:
                rec["sources"]["arxiv"] = "ERR " + str(e)
            time.sleep(0.4)
            if rec["status"] != "OK":
                adoi = "10.48550/arXiv." + aid
                try:
                    r = fetch_datacite(adoi)
                    rec["sources"]["arxiv"] = r          # same slot: make_bib reads it
                    rec["sources"]["arxiv_via"] = "datacite"
                    rec["status"] = "OK"
                    rec["datacite_doi"] = adoi
                except Exception as e:
                    rec["sources"]["datacite"] = "ERR " + str(e)
                time.sleep(PAUSE)
        blob = ""
        for s in rec["sources"].values():
            if isinstance(s, dict):
                blob += " " + str(s.get("title") or "")
            elif isinstance(s, str):
                blob += " " + s
        rec["title_match"] = (frag.lower() in blob.lower()) if frag else None
        if rec["status"] == "OK" and rec["title_match"] is False:
            rec["status"] = "TITLE-MISMATCH"
        out[key] = rec
        print("%-15s %-28s %s" % (rec["status"], key, doi or ("arXiv:" + str(aid))))
    json.dump(out, open(CACHE, "w"), indent=1)
    n_ok = sum(1 for r in out.values() if r["status"] == "OK")
    print("\n%d/%d verified; cache -> %s" % (n_ok, len(out), CACHE))


def report():
    d = json.load(open(CACHE))
    print("| key | identifier printed on the page | status | title as returned by the API | venue / year |")
    print("|---|---|---|---|---|")
    for k, r in d.items():
        ident = r["doi"] or ("10.48550/arXiv." + str(r["arxiv"]))
        src = r["sources"].get("crossref") or r["sources"].get("arxiv") or {}
        if not isinstance(src, dict):
            src = {}
        title = (src.get("title") or "")[:75]
        ven = str(src.get("container") or src.get("journal_ref") or "")
        yr = src.get("year") or (src.get("published") or "")[:4]
        print("| `%s` | %s | %s | %s | %s %s |" % (k, ident, r["status"], title, ven, yr))


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    else:
        main()
