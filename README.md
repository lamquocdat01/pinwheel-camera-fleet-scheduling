# Real-Time Scheduling of Camera Fleets on Shared Edge Accelerators

Code, results and manuscript sources for the paper

> **Real-Time Scheduling of Camera Fleets on Shared Edge Accelerators: A Pinwheel
> Schedulability Test, Admission Control and Multi-Node Dimensioning**
> Dat Lam Quoc, FPT School of Business and Technology, FPT University, Ho Chi Minh City.

Multi-camera inference at the edge is a hard real-time scheduling problem: one node carries one
accelerator and many streams. If each camera's service-level agreement is written as a *refresh
window* $K_i$ --- inspect this camera at least once every $K_i$ frame slots, which bounds its
worst-case detection latency by $K_i-1$ --- then the fleet is a pinwheel task system and
admission is decided by a single addition: a schedule meeting every agreement exists whenever
$\sum_i 1/K_i \le 5/6$. This repository contains the corpus builder, the simulator that replays a
121-video surveillance corpus against that rule, the machine checks for every theorem in the
paper, and the scripts that turn the result files into the numbers, tables and figures printed in
the manuscript. **No number in the paper is typed by hand**: `code/make_numbers.py` regenerates
`latex/numbers.tex` from `results/*.json`.

## Reproducing

```bash
pip install -r requirements.txt

# per-frame detection records, only needed to rebuild the corpus (see "Data" below)
export PINWHEEL_DETECTIONS_DIR=/path/to/detections

python code/build_event_corpus.py          # detections -> data/event_corpus.csv
python code/pinwheel_sim.py    --exp all   # E1-E3   round-1 experiments      (~6 min)
python code/proof_checks.py                # C0-C6   machine checks per theorem (~2 min)
python code/pinwheel_round2.py --exp all   # E1b, E4-E8 + all figures        (~5 min)
python code/make_numbers.py                # results/*.json -> latex/numbers.tex

cd latex && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Everything is seeded (`SEED = 42`) and deterministic: the exhaustive schedulability search uses a
state-count budget rather than a wall-clock budget, and no experiment seeds itself from Python's
per-process string hash, so the same verdicts come back on any machine and in any process.

To regenerate the bibliography from live metadata (needs network access to Crossref, doi.org and
DataCite), run `python code/verify_refs.py` followed by `python code/make_bib.py`. Nothing enters
`latex/refs.bib` unless an API returned it; the cached verification is in `code/refs_verified.json`.

`code/build_and_check.py` rebuilds the manuscript and runs the pre-submission checks on the
*rendered PDF*: no leftover placeholders, a resolvable DOI printed for every reference, the corpus
size stated correctly, the abstract within the 250-word limit, highlights within 85 characters,
the mandatory declaration sections present with the AI declaration before the references, no
Type 3 fonts, no figure text below 7pt at print size, and the page limit.

## Data

The corpus is 121 public surveillance videos --- 53 from CDnet2014, 48 from LASIESTA, 20 from
BMC --- carrying 3,713 annotated events over 166,589 frames.

`data/event_corpus.csv` is the only input the simulator reads, and it **is** included here. It is
built by `code/build_event_corpus.py` from per-frame object detections under the rule

> an **event** is a maximal run of consecutive frames in which the detector reports at least one
> bounding box,

using a YOLO detector at 640 px input and a confidence threshold of 0.25, over all COCO classes.
Only the presence or absence of a box is used. `data/CORPUS_README.md` documents the detector,
its parameters, the column meanings and the dataset licences.

**Neither the source video nor the per-frame detection records are redistributed here.** The
source datasets are third-party and must be obtained from their authors:
CDnet2014 (Wang et al., CVPRW 2014, `10.1109/CVPRW.2014.126`),
LASIESTA (Cuevas et al., CVIU 2016, `10.1016/j.cviu.2016.08.005`),
BMC (Vacavant et al., ACCV 2012 Workshops, `10.1007/978-3-642-37410-4_25`).

The published corpus file is pinned by SHA-256 in `results/corpus_meta.json`.

## Energy

Energy is reported in units of the accelerator's idle slot energy, under the linear slot model
`e(a) = 1 + a (r - 1)` with the single parameter `r = E_active / E_idle`. Results are computed
over the grid `r in {3, 10, 30}` and quoted at `r = 10`. No absolute power figure is claimed
anywhere: turning the consolidation gain into joules requires a measurement on the target
accelerator, which this work does not make.

## Layout

```
code/      corpus builder, simulator, round-2 experiments, per-theorem machine checks,
           number/bibliography generators, build + render checker
data/      event_corpus.csv and the corpus documentation
results/   every JSON the manuscript quotes, plus the results write-up
figures/   the seven figures, vector PDF
latex/     manuscript sources (main.tex, generated numbers.tex, generated refs.bib)
           and the elsarticle class and bibliography style (LPPL, redistributed with the paper)
```

`latex/main.tex` also reads an optional `latex/repo.tex` holding this repository's URL, commit and
tag for the Data availability statement. It is generated locally and deliberately not tracked
here, so that publishing the code cannot change the commit hash the paper quotes; the manuscript
builds without it.

## Licence

MIT --- see `LICENSE`. The bundled `elsarticle.cls` and `elsarticle-num.bst` are copyright
Elsevier Ltd and distributed under the LaTeX Project Public License 1.3 or later; they are not
covered by the MIT licence above.
