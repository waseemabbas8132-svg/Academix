# TrOCR 2-Beam Experiment Report

**Date:** 2026-11-17  
**Status:** Blocked before model load; no inference was run

## Result

The required RAM guard was not met at the final pre-run check: **1.904 GiB available** versus the existing **2.5 GiB minimum**. No competing Python/OCR processes were running at the final check. No processes were terminated. The pilot script did not start, TrOCR was not loaded, and neither greedy replay nor 2-beam inference occurred.

| Measure | Saved greedy baseline | New 2-beam pilot |
| --- | ---: | ---: |
| CER | 16.2436% overall validation | Not measured |
| WER | 40.3155% overall validation | Not measured |
| Exact matches | 79/1,197 overall validation | Not measured |
| Pilot sample predictions | Existing saved validation predictions | Not produced |
| Runtime / peak RAM | Historical full run only | Not measured |
| Improved / regressed / unchanged | — | Not measurable |

These are not zero gains or zero regressions; the candidate was not run. No full validation run was attempted, and **production OCR was not changed**.

## Decoder settings and paired pilot design

The production recognizer sets `max_new_tokens=192` and does not explicitly pass `num_beams` or `do_sample`; the locally inspected generation defaults resolve to greedy one-beam decoding. Production also requests token scores. The saved validation baseline uses greedy `num_beams=1`, `do_sample=false`, `max_new_tokens=192`, and `use_cache=true`, with the existing preprocessing variant. The planned pilot holds those validation settings and preprocessing constant, changing only `num_beams` from 1 to 2; it selects 50 deterministic validation crops across the 43 pages and checks crop/reference alignment against the saved predictions.

## RAM checks and saved files

Available RAM fluctuated during preparation: **2.520 GiB**, then **2.845 GiB**, then **1.904 GiB** at the final pre-run check. The last check was below the guard, so execution stopped safely. No model or held-out test data was accessed.

The result directory [`evaluation/results/trocr_2beam_20261117/`](./results/trocr_2beam_20261117/) contains the preflight record and the paired-pilot script for a future run when the safety threshold is met. No pilot prediction or metric artifacts were generated.

## Decision

**Do not adopt 2-beam decoding based on this blocked run.** There is no measured pilot evidence. Keep the existing production decoder unchanged. Rerun the paired pilot only after a fresh preflight has at least 2.5 GiB available; evaluate all 1,197 validation samples only if the pilot passes its predeclared improvement gate.
