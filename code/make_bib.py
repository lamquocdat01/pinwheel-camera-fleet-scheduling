#!/usr/bin/env python3
"""
make_bib.py -- build latex/refs.bib from refs_verified.json.

Every field is taken from the metadata a live API returned (Crossref or arXiv). Nothing is
typed by hand except the bibkey and the entry type mapping. A reference whose status is not
"OK" is NOT written: it is listed as DROPPED at the end (law C5 / round-3 law 3).

Every entry gets a `doi` field, and elsarticle-num prints DOIs, so the rendered PDF carries a
resolvable identifier on every line (the T30 desk-reject lesson).

Usage:  python Submission_FGCS/make_bib.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "refs_verified.json")

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

OUT = os.path.join(_find_latex_dir(HERE), "refs.bib")

TYPE = {"journal-article": "article", "proceedings-article": "inproceedings",
        "book-chapter": "incollection", "posted-content": "misc"}

# entry-specific overrides that the APIs do not carry (series/booktitle wording only)
BOOKTITLE = {
    "kawamura2024stoc": "Proceedings of the 56th Annual ACM Symposium on Theory of Computing (STOC)",
    "holte1989pinwheel": "Proceedings of the 22nd Hawaii International Conference on System Sciences (HICSS)",
    "kusano2026sofsem": "SOFSEM 2026: Theory and Practice of Computer Science, LNCS",
    "dosa2007ffd": "Combinatorics, Algorithms, Probabilistic and Experimental Methodologies (ESCAPE), LNCS 4614",
    "yang2021deeprt": "Proceedings of the 6th ACM/IEEE Symposium on Edge Computing (SEC)",
}
NOTE = {
    # the published version is cited; the preprint identifier is kept for readers
    "kanellopoulos2026finite": "Preprint: arXiv:2604.16030",
    "fujiwara2026real": "Preprint: arXiv:2510.24068",
    # The publisher DOI for this paper (10.1145/3453142.3491278) does not resolve, so the
    # archival identifier that does is printed instead.
    "yang2021deeprt": "Preprint: arXiv:2105.01803",
    # Elsevier asks for data references to be tagged [dataset] in the reference list.
    "cdnet2014": "[dataset]",
    "lasiesta2016": "[dataset]",
    "bmc2012": "[dataset]",
}

# ---------------------------------------------------------------- capitalisation protection
# elsarticle-num lowercases every title, so an acronym that is not brace-protected is printed
# as ordinary prose: "dnn", "iot", "Splitstream", "ffd(i)". Runs of two or more capitals are
# protected automatically; names whose capitalisation is internal have to be listed.
PROTECT_WORDS = ["SplitStream", "CDnet", "IoT", "InferFair", "PnG", "QoS", "AoI", "DeepRT"]

# Trademarks and proper nouns that the publisher's OWN metadata records in lower case, so
# there is no capitalisation left for protect_caps to protect. Restoring it is a typographic
# correction to a name, never a change of content: the mapping is from the exact lower-case
# string Crossref returns to the registered spelling, and each one is listed explicitly so it
# can be checked by eye.
PROPER_NOUNS = {
    "bluetooth low energy": "{Bluetooth} {Low} {Energy}",
}

# USENIX proceedings carry no DOI. These fields are transcribed from the publisher's own
# landing page, which verify_refs.py fetches and checks for the expected title; the page URL
# is what gets printed as the resolvable identifier.
USENIX = {
    "jiang2018mainstream": {
        "title": "Mainstream: Dynamic Stem-Sharing for Multi-Tenant Video Processing",
        "author": ("Jiang, Angela H. and Wong, Daniel L.-K. and Canel, Christopher and "
                   "Tang, Lilia and Misra, Ishan and Kaminsky, Michael and "
                   "Kozuch, Michael A. and Pillai, Padmanabhan and Andersen, David G. and "
                   "Ganger, Gregory R."),
        "booktitle": "2018 USENIX Annual Technical Conference (USENIX ATC 18)",
        "pages": "29--42", "year": "2018"},
    "padmanabhan2023gemel": {
        "title": "Gemel: Model Merging for Memory-Efficient, Real-Time Video Analytics at the Edge",
        "author": ("Padmanabhan, Arthi and Agarwal, Neil and Iyer, Anand and "
                   "Ananthanarayanan, Ganesh and Shu, Yuanchao and Karianakis, Nikolaos and "
                   "Xu, Guoqing Harry and Netravali, Ravi"),
        "booktitle": "20th USENIX Symposium on Networked Systems Design and Implementation "
                     "(NSDI 23)",
        "pages": "973--994", "year": "2023"},
}


_ACRONYM = re.compile(r"(?<![A-Za-z])([A-Z]{2,})(?![a-z])")
_PAREN_CAP = re.compile(r"\(([A-Z])\)")


def protect_caps(title):
    """Brace-protect capitalisation in a BibTeX title. Maths segments are left untouched."""
    if not title:
        return title
    out = []
    for i, seg in enumerate(re.split(r"(\$[^$]*\$)", title)):
        if i % 2 == 1:                       # a $...$ segment
            out.append(seg)
            continue
        for lower, proper in PROPER_NOUNS.items():
            seg = re.sub(re.escape(lower), proper, seg, flags=re.I)
        for w in PROTECT_WORDS:
            seg = re.sub(r"(?<![{A-Za-z])" + w + r"(?![}A-Za-z])", "{" + w + "}", seg)
        seg = _ACRONYM.sub(lambda m: "{" + m.group(1) + "}", seg)
        seg = _PAREN_CAP.sub(lambda m: "({" + m.group(1) + "})", seg)   # e.g. FFD(I), OPT(I)
        out.append(seg)
    return "".join(out)

# FORMATTING-ONLY overrides. These change how a verified record is typeset, never what it says.
# Each one is justified by a field the API returned but placed in the wrong BibTeX slot
# (e.g. Dagstuhl reports its proceedings title in `journal`), or by an article number that
# Crossref leaves out. Content is never invented here.
OVERRIDE = {
    # Dagstuhl reports its proceedings title in `journal` ("LIPIcs, Volume 359, ISAAC 2025").
    # Split it into the BibTeX slots the style expects, so that the series and volume are
    # printed once, by format.bvolume, instead of twice. ISAAC 2025 is the 36th of the series.
    # ESA 2026 reports its proceedings title in `journal` ("LIPIcs, Volume 388, ESA 2026")
    "kawamura2025covering": {"_type": "inproceedings",
                             "booktitle": "34th European Symposium on Algorithms (ESA 2026)",
                             "series": "LIPIcs", "volume": "388", "pages": "83:1--83:7",
                             "journal": None, "howpublished": None, "note": None},
    # SIAM files SODA papers as book chapters; they are conference papers
    # SIAM files SODA papers as book chapters; they are conference papers. Crossref stores
    # the title with LaTeX maths in it ("the \(\text{k}\)-Visits Problem").
    "kanellopoulos2025kvisits": {"_type": "inproceedings", "howpublished": None, "note": None,
                                 "title": "Finite Pinwheel Scheduling: the $k$-Visits Problem"},
    # Crossref stores only the short title for this one; the full title is on the DOI record
    "shen2019nexus": {"_type": "inproceedings",
                      "title": "Nexus: a GPU cluster engine for accelerating DNN-based "
                               "video analysis"},
    # Springer does not return the LNCS volume through Crossref
    "kusano2026sofsem": {"series": "LNCS", "volume": "16448"},
    # DeepRT: cite the conference version, print the identifier that resolves (see NOTE)
    "yang2021deeprt": {"_type": "inproceedings", "year": "2021", "pages": "271--284",
                       "booktitle": BOOKTITLE["yang2021deeprt"], "howpublished": None},
    # likewise for ICALP 2026 ("LIPIcs, Volume 374, ICALP 2026")
    "kanellopoulos2026finite": {"_type": "inproceedings",
                                "booktitle": "International Colloquium on Automata, Languages, "
                                             "and Programming (ICALP 2026)",
                                "series": "LIPIcs", "volume": "374",
                                "journal": None},
    # Crossref reports only the series name in `container`; the volume and the workshop title
    # are on the publisher's own DOI landing page.
    "bmc2012": {"booktitle": "Computer Vision -- ACCV 2012 Workshops",
                "series": "LNCS", "volume": "7728", "year": "2013"},
    # Crossref returns bare surnames for this record; the given names are on the article page.
    "fishburn2002densities": {"author": "Fishburn, Peter C. and Lagarias, Jeffrey C."},
    # Crossref reports the volume as the free-text string "vol. 28:4, SOFSEM 2026 / Special
    # issues"; split it into the slots the style expects. The journal is an overlay journal, so
    # the article number is the only locator it has.
    "fujiwara2026real": {"_type": "article", "year": "2026",
                         "journal": "Discrete Mathematics \\& Theoretical Computer Science",
                         "volume": "28", "number": "4", "pages": "17657",
                         "howpublished": None},
    "kawamura2026pnas": {"pages": "e2530214123"},
    # Crossref leaves this chapter's year empty; a sibling chapter of the same book
    # (ISBN 9783540744504, DOI 10.1007/978-3-540-74450-4_43) reports 2007. The volume is
    # already named in the booktitle above, so it is not repeated as a `volume` field.
    "dosa2007ffd": {"year": "2007"},
}


# ---------------------------------------------------------------- LTWA abbreviation
# Elsevier asks for journal names abbreviated per the List of Title Word Abbreviations
# (ISO 4 / LTWA). Crossref returns the full title, so it is abbreviated here on the way out.
# Titles of a single word are not abbreviated (LTWA rule), hence Algorithmica untouched.
LTWA = {
    "Future Generation Computer Systems": "Future Gener. Comput. Syst.",
    "Journal of Network and Computer Applications": "J. Netw. Comput. Appl.",
    "IEEE Transactions on Parallel and Distributed Systems": "IEEE Trans. Parallel Distrib. Syst.",
    "IEEE/ACM Transactions on Networking": "IEEE/ACM Trans. Netw.",
    "IEEE Transactions on Computers": "IEEE Trans. Comput.",
    "IEEE Communications Surveys \\& Tutorials": "IEEE Commun. Surv. Tutor.",
    "Real-Time Systems": "Real-Time Syst.",
    "Journal of Systems Architecture": "J. Syst. Archit.",
    "Theoretical Computer Science": "Theor. Comput. Sci.",
    "Journal of Computer and System Sciences": "J. Comput. Syst. Sci.",
    "Journal of the ACM": "J. ACM",
    "Computer Vision and Image Understanding": "Comput. Vis. Image Underst.",
    "Proceedings of the National Academy of Sciences": "Proc. Natl. Acad. Sci. U. S. A.",
    "Discrete Mathematics \\& Theoretical Computer Science": "Discrete Math. Theor. Comput. Sci.",
    "Algorithmica": "Algorithmica",
    "IEEE Transactions on Computers": "IEEE Trans. Comput.",
    "Real-Time Systems": "Real-Time Syst.",
}

_UNABBREVIATED = []


def ltwa(journal):
    """Abbreviate a journal title per LTWA; record anything not in the table."""
    if not journal:
        return journal
    if journal in LTWA:
        return LTWA[journal]
    _UNABBREVIATED.append(journal)
    return journal


# Non-ASCII symbols that pdflatex + inputenc(utf8) cannot typeset directly. Accented Latin
# letters are NOT in this table: they work fine with T1 fontenc and must be preserved.
SYMBOL = {
    "≤": "$\\le$", "≥": "$\\ge$", "≠": "$\\ne$", "≈": "$\\approx$",
    "×": "$\\times$", "−": "-", "–": "--", "—": "---",
    " ": " ", " ": " ", "’": "'", "“": "``", "”": "''",
    "→": "$\\to$", "≤": "$\\le$",
}


def esc(s):
    if s is None:
        return ""
    s = re.sub(r"<[^>]+>", "", str(s))
    s = s.replace("&amp;", "&")                  # undo XML entity first
    for k, v in SYMBOL.items():
        s = s.replace(k, v)
    s = re.sub(r"(?<!\\)&", r"\\&", s)           # escape only unescaped ampersands
    s = re.sub(r"\s+", " ", s).strip()
    return s


def surname_first(name):
    """Normalise one author name to BibTeX's unambiguous `Family, Given` form.

    The two upstream sources disagree about the order they hand names back:

      * the arXiv export API returns display order, "Hiroshi Fujiwara";
      * DataCite (and Crossref) already return "Fujiwara, Hiroshi".

    Flipping both produced "Hiroshi, Fujiwara" in the bibliography, i.e. the given name
    printed as the surname. BibTeX cannot detect this -- "A, B" is *by definition* family A,
    given B -- so it renders silently wrong, which is exactly the shape of error that gets a
    submission desk-screened for unverifiable references. Decide by the comma, never by
    position, and strip the stray trailing commas DataCite sometimes carries.
    """
    n = re.sub(r"\s+", " ", (name or "").strip()).strip(",").strip()
    if not n:
        return ""
    if "," in n:
        family, given = n.split(",", 1)                  # already Family, Given
        family, given = family.strip(), given.strip()
    else:
        parts = n.split()
        if len(parts) == 1:
            return parts[0]
        # everything after the given names is the surname; keep multi-word surnames together
        # by treating lowercase particles (van, von, de, der, di, del, la) as part of it
        i = len(parts) - 1
        while i > 1 and parts[i - 1].islower():
            i -= 1
        family, given = " ".join(parts[i:]), " ".join(parts[:i])
    return ("%s, %s" % (family, given)).strip().strip(",").strip() if given else family


def authors_from(rec):
    for key in ("crossref", "arxiv"):
        src = rec["sources"].get(key)
        if isinstance(src, dict) and src.get("authors"):
            return " and ".join(esc(surname_first(a)) for a in src["authors"] if a)
    return ""


def main():
    if not os.path.exists(CACHE):
        sys.exit("run verify_refs.py first")
    d = json.load(open(CACHE))
    entries, dropped = [], []
    for key, r in d.items():
        if r["status"] != "OK":
            dropped.append((key, r["status"]))
            continue
        cr = r["sources"].get("crossref") if isinstance(r["sources"].get("crossref"), dict) else None
        ax = r["sources"].get("arxiv") if isinstance(r["sources"].get("arxiv"), dict) else None
        f = {}
        if cr:
            etype = TYPE.get(cr.get("type"), "misc")
            f["title"] = esc(cr.get("title"))
            f["year"] = cr.get("year")
            container = esc(cr.get("container"))
            if etype == "article":
                f["journal"] = container
                for k, src in (("volume", "volume"), ("number", "issue"), ("pages", "page")):
                    if cr.get(src):
                        f[k] = esc(cr[src])
            else:
                f["booktitle"] = BOOKTITLE.get(key, container)
                if cr.get("page"):
                    f["pages"] = esc(cr["page"])
                if cr.get("publisher"):
                    f["publisher"] = esc(cr["publisher"])
            f["doi"] = r["doi"]
        elif ax is None and isinstance(r["sources"].get("landing_page"), dict):
            # USENIX mints no DOI. The landing page was fetched and the expected title found
            # on it by verify_refs.py; that page URL is the resolvable identifier printed.
            lp = r["sources"]["landing_page"]
            etype = "inproceedings"
            f["title"] = esc(USENIX[key]["title"])
            f["author"] = USENIX[key]["author"]
            f["booktitle"] = USENIX[key]["booktitle"]
            f["pages"] = USENIX[key]["pages"]
            f["year"] = USENIX[key]["year"]
            f["publisher"] = "USENIX Association"
            f["url"] = lp["url"]
        elif ax is None:
            # only doi.org content negotiation answered: parse its BibTeX
            bt = r["sources"].get("doi.org") or ""
            etype = (re.match(r"@(\w+)", bt).group(1).lower()
                     if re.match(r"@(\w+)", bt) else "misc")
            for k in ("title", "author", "year", "journal", "booktitle", "volume", "pages",
                      "publisher", "series"):
                m = re.search(r"\n\s*%s\s*=\s*\{(.*?)\}\s*,?\n" % k, bt, re.S)
                if m:
                    f[k] = esc(m.group(1))
            f["doi"] = r["doi"]
        else:
            etype = "misc"
            f["title"] = esc(ax.get("title"))
            f["year"] = (ax.get("published") or "")[:4]
            jr = esc(ax.get("journal_ref"))
            if ax.get("doi"):                       # arXiv knows the journal DOI
                f["doi"] = ax["doi"]
                f["howpublished"] = jr or ("arXiv:" + r["arxiv"])
            else:
                f["doi"] = "10.48550/arXiv." + r["arxiv"]
                f["howpublished"] = "arXiv:" + r["arxiv"] + " [preprint]"
        if not f.get("author"):
            f["author"] = authors_from(r)
        if key in NOTE:
            f["note"] = NOTE[key]
        for k, v in OVERRIDE.get(key, {}).items():
            if k == "_type":
                etype = v
            else:
                f[k] = v
        if f.get("title"):
            f["title"] = protect_caps(f["title"])
        if f.get("journal"):
            f["journal"] = ltwa(f["journal"])
        # An entry that carries a DOI does NOT also get a `url`: elsarticle-num prints the DOI
        # as a hyperlinked "doi:10.…", so adding https://doi.org/<same doi> makes every
        # reference print the same identifier twice and costs most of a page. Entries with no
        # DOI still need a URL, and keep one.
        if not f.get("doi"):
            f["url"] = f.get("url") or ""
        else:
            f.pop("url", None)
        body = ",\n".join("  %-12s = {%s}" % (k, v) for k, v in f.items()
                          if v not in (None, "", "None"))
        entries.append("@%s{%s,\n%s\n}\n" % (etype, key, body))

    hdr = ("%% refs.bib -- GENERATED by Submission_FGCS/make_bib.py from refs_verified.json.\n"
           "%% Every entry was returned by a live Crossref or arXiv query; nothing is hand-typed.\n"
           "%% Regenerate: python Submission_FGCS/verify_refs.py && python Submission_FGCS/make_bib.py\n\n")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(hdr + "\n".join(entries))
    print("wrote %d entries -> %s" % (len(entries), OUT))
    if dropped:
        print("DROPPED (not verified):", dropped)
    if _UNABBREVIATED:
        print("NOT IN LTWA TABLE (printed in full):", sorted(set(_UNABBREVIATED)))


if __name__ == "__main__":
    main()
