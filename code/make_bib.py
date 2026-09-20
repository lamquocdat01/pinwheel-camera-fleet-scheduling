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
}
NOTE = {
    # the proceedings version is cited; the preprint identifier is kept for readers
    "kanellopoulos2026finite": "Preprint: arXiv:2604.16030",
    # Elsevier asks for data references to be tagged [dataset] in the reference list.
    "cdnet2014": "[dataset]",
    "lasiesta2016": "[dataset]",
    "bmc2012": "[dataset]",
}

# ---------------------------------------------------------------- capitalisation protection
# elsarticle-num lowercases every title, so an acronym that is not brace-protected is printed
# as ordinary prose: "dnn", "iot", "Splitstream", "ffd(i)". Runs of two or more capitals are
# protected automatically; names whose capitalisation is internal have to be listed.
PROTECT_WORDS = ["SplitStream", "CDnet", "IoT"]

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
    "kobayashi2025isaac": {"_type": "inproceedings",
                           "booktitle": "36th International Symposium on Algorithms and "
                                        "Computation (ISAAC 2025)",
                           "series": "LIPIcs", "volume": "359",
                           "journal": None, "note": None},
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
    "fujiwara2026real": {"_type": "article", "year": "2026",
                         "journal": "Discrete Mathematics \\& Theoretical Computer Science",
                         "volume": "28", "number": "4", "howpublished": None},
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


def authors_from(rec):
    cr = rec["sources"].get("crossref")
    if isinstance(cr, dict) and cr.get("authors"):
        return " and ".join(esc(a) for a in cr["authors"])
    ax = rec["sources"].get("arxiv")
    if isinstance(ax, dict) and ax.get("authors"):
        out = []
        for a in ax["authors"]:
            parts = esc(a).split()
            out.append(parts[-1] + ", " + " ".join(parts[:-1]) if len(parts) > 1 else esc(a))
        return " and ".join(out)
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
        f["url"] = "https://doi.org/" + f["doi"]
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
