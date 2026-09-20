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

- **family**: YOLO (Ultralytics)
- **weights**: yolo26s-seg.pt
- **task**: detection boxes only; segmentation masks not decoded
- **confidence threshold**: 0.25
- **image size**: 640
- **precision**: FP32, CPU
- **classes**: all 80 COCO classes; no class filter

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

- 121 videos, 3713 events, 166589 frames
  - CDnet2014: 53 videos
  - LASIESTA: 48 videos
  - BMC: 20 videos

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
