#!/usr/bin/env python3
"""
build_event_corpus.py -- build this paper's event corpus from per-frame detection records.

The simulator needs one artefact only: for every video, how long the video is and when each
event starts and ends.  This script derives that artefact directly from the per-frame object
detections, so the corpus is defined by a rule stated in the paper rather than inherited from
any other pipeline.

    event  =  a maximal run of consecutive frames in which the detector reports
              at least one bounding box

Input
-----
A directory tree of per-frame detection records, one JSON file per video:

    <root>/<dataset>/<category>__<video>.json
    {"frames": [{"frame": <int>, "boxes": [[x1, y1, x2, y2, score, class], ...]}, ...]}

Frame indices are 0-based positions in the video's sorted frame list, restricted to the
dataset's temporal region of interest where the dataset defines one.  Only the presence or
absence of a box is used; coordinates, scores and class ids are ignored, so the corpus is
insensitive to the detector's localisation quality and depends only on its firing pattern.

Set the root with --detections or PINWHEEL_DETECTIONS_DIR.

Output
------
    data/event_corpus.csv     dataset, video, n_frames, event_id, onset, duration
    data/CORPUS_README.md     detector, parameters, extraction rule, dataset licences

Only CDnet2014, LASIESTA and BMC are kept.  Any other dataset directory is skipped and
reported, as are videos with no detection records and videos in which the detector never
fires (they carry no event and so contribute nothing to a replay).

Usage
-----
    python code/build_event_corpus.py
    python code/build_event_corpus.py --detections <root> --check-against <legacy.csv>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")

# The three public corpora the paper replays. VIRAT is present in the detection tree but is
# excluded: its clips were capped at 500 frames when the detector was run, so they are
# truncation stubs rather than complete sequences.
CORPUS_DATASETS = ("CDnet2014", "LASIESTA", "BMC")

DEFAULT_DETECTIONS = os.environ.get(
    "PINWHEEL_DETECTIONS_DIR",
    r"D:\THS Programing\zz\09.02 Scene Comlexity Metric"
    r"\scm-scene-complexity\data\detections_cpu",
)

# Detector provenance, read off the detection run's configuration. Recorded here so that the
# corpus is reproducible and so the paper can describe the detector without guessing.
DETECTOR = OrderedDict((
    ("family", "YOLO (Ultralytics)"),
    ("weights", "yolo26s-seg.pt"),
    ("task", "detection boxes only; segmentation masks not decoded"),
    ("confidence_threshold", 0.25),
    ("image_size", 640),
    ("precision", "FP32, CPU"),
    ("classes", "all 80 COCO classes; no class filter"),
))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def events_from_frames(frames):
    """Maximal runs of consecutive frames carrying at least one detection box.

    `frames` is the video's frame list in file order; frame indices are taken from the records
    themselves, so an event's onset is a frame index of the video, not a position in the list.
    """
    events, in_event, onset = [], False, 0
    for rec in frames:
        active = len(rec.get("boxes", ())) > 0
        if active and not in_event:
            onset, in_event = rec["frame"], True
        elif not active and in_event:
            events.append((onset, rec["frame"] - onset))
            in_event = False
    if in_event:
        events.append((onset, frames[-1]["frame"] - onset + 1))
    return events


def build(detections_root):
    """Walk the detection tree and return (rows, per_video, skipped)."""
    if not os.path.isdir(detections_root):
        sys.exit("detection root not found: %s\n"
                 "Set --detections or PINWHEEL_DETECTIONS_DIR." % detections_root)

    present = sorted(d for d in os.listdir(detections_root)
                     if os.path.isdir(os.path.join(detections_root, d)))
    skipped = [d for d in present if d not in CORPUS_DATASETS]

    rows, per_video = [], OrderedDict()
    for dataset in CORPUS_DATASETS:
        ds_dir = os.path.join(detections_root, dataset)
        if not os.path.isdir(ds_dir):
            sys.exit("missing dataset directory: %s" % ds_dir)
        for name in sorted(os.listdir(ds_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(ds_dir, name)
            with open(path, encoding="utf-8") as f:
                frames = json.load(f).get("frames", [])
            if not frames:
                continue
            events = events_from_frames(frames)
            if not events:
                continue
            stem = name[:-len(".json")]
            # The file name is "<category>__<video>"; the video identifier alone is unique
            # within a dataset and is what the simulator keys on.
            video = stem.split("__", 1)[1] if "__" in stem else stem
            n_frames = len(frames)
            per_video[(dataset, video)] = n_frames
            for event_id, (onset, duration) in enumerate(events):
                rows.append((dataset, video, n_frames, event_id, onset, duration))
    return rows, per_video, skipped


def write_corpus(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dataset", "video", "n_frames", "event_id", "onset", "duration"])
        w.writerows(rows)


README = """\
# Event corpus

`event_corpus.csv` is the only input the simulator reads. It is produced by
`code/build_event_corpus.py` from per-frame object detections and holds, for every video, the
video length and the onset and duration of every event.

## Extraction rule

> An **event** is a maximal run of consecutive frames in which the detector reports at least
> one bounding box.

Only the presence or absence of a box is used. Box coordinates, confidence scores and class
ids are discarded, so the corpus reflects when the detector fires, not how well it localises.
A video in which the detector never fires carries no event and is left out.

`onset` is the index of the event's first frame and `duration` its length in frames, so the
event occupies frames `onset .. onset + duration - 1`. Frame indices are 0-based positions in
the video's sorted frame list, restricted to the dataset's temporal region of interest where
the dataset defines one (CDnet2014 ships one per video in `temporalROI.txt`). `n_frames` is
the number of frames the detector scored for that video and is repeated on each of its rows.

## Detector

%(detector)s

## Columns

| Column | Meaning |
|---|---|
| `dataset` | `CDnet2014`, `LASIESTA` or `BMC` |
| `video` | video identifier, unique within its dataset |
| `n_frames` | frames scored for this video |
| `event_id` | 0-based index of the event within its video, in onset order |
| `onset` | frame index of the event's first frame |
| `duration` | event length in frames |

## Corpus size

%(sizes)s

## Datasets and licensing

The three corpora are third-party public datasets, cited in the paper:

- **CDnet2014** — ChangeDetection.net 2014 video database.
- **LASIESTA** — Labeled and Annotated Sequences for Integral Evaluation of SegmenTation
  Algorithms.
- **BMC** — Background Models Challenge (synthetic sequences).

Only the derived event annotations above are distributed here. **No video, frame, or image
from any of the three datasets is redistributed in this repository**, and neither are the
per-frame detection records. Obtain the videos from their original providers under their own
terms and re-run `code/build_event_corpus.py` to regenerate this file.

## Reproducing

    set PINWHEEL_DETECTIONS_DIR=<root of the per-frame detection records>
    python code/build_event_corpus.py

The script prints the corpus size and the SHA-256 of the file it writes.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detections", default=DEFAULT_DETECTIONS,
                    help="root of the per-frame detection records")
    ap.add_argument("--out", default=os.path.join(DATA, "event_corpus.csv"))
    ap.add_argument("--check-against", default=None,
                    help="optional CSV with dataset,video,onset,duration columns to compare "
                         "the extracted events against, row for row")
    a = ap.parse_args()

    rows, per_video, skipped = build(a.detections)
    n_videos, n_events = len(per_video), len(rows)
    n_frames = sum(per_video.values())
    by_dataset = OrderedDict(
        (d, sum(1 for (ds, _) in per_video if ds == d)) for d in CORPUS_DATASETS)

    if skipped:
        print("skipped datasets outside the corpus: %s" % ", ".join(skipped))
    print("videos=%d  events=%d  frames=%d  %s"
          % (n_videos, n_events, n_frames, json.dumps(by_dataset)))

    write_corpus(rows, a.out)
    digest = sha256(a.out)
    print("wrote %s  sha256=%s" % (a.out, digest))

    detector_lines = "\n".join("- **%s**: %s" % (k.replace("_", " "), v)
                               for k, v in DETECTOR.items())
    size_lines = "\n".join(
        ["- %d videos, %d events, %d frames" % (n_videos, n_events, n_frames)]
        + ["  - %s: %d videos" % (d, n) for d, n in by_dataset.items()])
    readme = os.path.join(os.path.dirname(a.out), "CORPUS_README.md")
    with open(readme, "w", encoding="utf-8", newline="\n") as f:
        f.write(README % {"detector": detector_lines, "sizes": size_lines})
    print("wrote %s" % readme)

    if a.check_against:
        compare(rows, per_video, a.check_against)


def compare(rows, per_video, reference):
    """Assert that the extracted events agree with a reference listing, row for row."""
    ref_events, ref_frames = {}, {}
    with open(reference, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["dataset"] not in CORPUS_DATASETS:
                continue
            key = (r["dataset"], r["video"])
            ref_events.setdefault(key, []).append((int(r["onset"]), int(r["duration"])))
            if "n_frames" in r:
                ref_frames[key] = int(r["n_frames"])

    mine = {}
    for ds, video, _, _, onset, duration in rows:
        mine.setdefault((ds, video), []).append((onset, duration))

    only_mine = sorted(set(mine) - set(ref_events))
    only_ref = sorted(set(ref_events) - set(mine))
    diff = sorted(k for k in set(mine) & set(ref_events) if mine[k] != ref_events[k])
    bad_n = sorted(k for k in ref_frames if per_video.get(k) != ref_frames[k])

    print("compare against %s" % reference)
    print("  videos only here: %d   only in reference: %d" % (len(only_mine), len(only_ref)))
    print("  videos whose event list differs: %d" % len(diff))
    print("  videos whose n_frames differs:   %d" % len(bad_n))
    if only_mine or only_ref or diff or bad_n:
        for k in (only_mine + only_ref + diff + bad_n)[:10]:
            print("    %s" % (k,))
        sys.exit("MISMATCH")
    print("  IDENTICAL")


if __name__ == "__main__":
    main()
