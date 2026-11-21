# TrOCR Fine-Tuning Readiness — Academix AI Engine

Audit date: **2026-11-16**, Asia/Karachi. Project: `C:\Users\SUNNY.COMPUTERS\academix\ai-engine`.

## 1. Executive verdict: NOT READY

Dataset integrity and page separation pass. Training must not begin yet:

1. **Dataset license and local download provenance are UNVERIFIED.** The local release contains no explicit license grant. Matching research-availability wording online does not establish commercial, adaptation, model-training or weight-redistribution rights for this copy.
2. **Training plumbing is absent.** Top-level decoder start/padding IDs are unset. The installed Transformers loss dispatch also presents an extra label-shift risk, confirmed by a lightweight synthetic loss check. Generation-only baselines do not exercise either training issue.
3. **Insufficient current free RAM.** Approximately **3.25 GiB** was available. Full FP32 AdamW state alone needs approximately **4.97 GiB**, excluding activations and runtime overhead. A frozen-encoder stage still needs about **4.01 GiB** before overhead.
4. `accelerate`, required for the proposed Trainer approach, is absent. No installation was attempted.

This audit created only this report. No model weights were loaded, no model inference/backward/optimizer steps ran, no models/datasets were downloaded, and no existing code, datasets, manifests, predictions, metrics or checkpoints were changed. The proposed configuration below is conditional guidance, not permission to train.

## 2. Dataset audit

### Live verification

Crop paths in all manifests resolve against **`datasets/processed/bentham`**, not the split-manifest directory.

| Manifest | Crops | Pages | Empty transcriptions | Duplicate records / crop paths |
|---|---:|---:|---:|---:|
| `datasets/processed/bentham/manifest.jsonl` | 11,413 | 433 | 0 | 0 / 0 |
| `datasets/manifests/bentham/train.jsonl` | 9,100 | 347 | 0 | 0 / 0 |
| `datasets/manifests/bentham/validation.jsonl` | 1,197 | 43 | 0 | 0 / 0 |
| `datasets/manifests/bentham/test.jsonl` | 1,116 | 43 | 0 | 0 / 0 |

- **11,413/11,413 crops exist**, stay within the processed root, pass Pillow `verify()` and fully decode with `load()`. No missing/unreadable images or recorded-dimension mismatches.
- All crops are RGB. Width range **30–2,486**, height range **29–416** pixels; these are independent extrema.
- Each crop was SHA-256 hashed before decoding and rehashed afterward: **all unchanged**. There are **0 duplicate image-byte hash groups**, including **0 across splits**. This does not detect perceptual near-duplicates.
- Page intersections: train/validation **0**, train/test **0**, validation/test **0**.
- A canonical-record multiset comparison proves the three split manifests exactly cover the processed manifest, including every original transcription, with no addition, omission or duplicate assignment.
- Page percentages: **80.1386 / 9.9307 / 9.9307%**. Crop percentages: **79.7336 / 10.4880 / 9.7783%**. Counts match the previous reports and seed-42 split report.
- All **433 PAGE XML files** were parsed. All Creator fields are blank. No writer/author-named elements or attributes were found. Metadata dates span `2013-03-07T15:03:58` through `2013-10-29T17:01:56`. No license/rights/copyright/attribution elements were found in PAGE Metadata.
- **Page separation only** is established. Writers may cross splits. No writer-disjoint claim is justified.

The combined live crop/metadata checks took **139.06 seconds**, not a training benchmark. Pixel-to-transcription quality, polygon correctness and perceptual duplicates were not manually adjudicated.

### Historical diagnostics and source partitions

`datasets/processed/bentham/dataset_report.json` records 11,473 annotated lines, 60 invalid-polygon rejections and 11,413 extracted crops. It retains an old unreadable-crop diagnostic for `line_images/035_320_001__r1__r210__r001_l016_g000142.png`. That crop passes the live audit. Treat this as a stale historical diagnostic; the stored report was not rewritten and the historical repair sequence was not reconstructed.

The source release has different benchmark partitions:

| Original file in `datasets/raw/BenthamDatasetR0-GT/Partitions` | Entries |
|---|---:|
| `Train.lst` | 350 |
| `Validation.lst` | 50 |
| `Test.lst` | 33 |
| `TrainLines.lst` | 9,198 |
| `ValidationLines.lst` | 1,415 |
| `TestLines.lst` | 860 |

Academix uses its existing custom seed-42 page split, not these published partitions. Do not resplit or describe Academix results as results on the original benchmark test partition.

### Manifest preservation

Before/after SHA-256 values matched:

| Manifest | SHA-256 |
|---|---|
| Processed | `1c3cc39cb98a731d4e985c82a22a1c973d005d5fcbc730582f36fba1cdb78442` |
| Train | `85178420a4703b62ff9b11157fa4aebcd411ee2e3e5402fcd4796488ddf184b3` |
| Validation | `56aaaee040a6ea2548bc6d738568729ce5f25d82a46c2d30b52488755e3103f1` |
| Test | `51ee7e555e709880b8c47ccc4a1fe5e35fc4190464e4782bc6447cc8e6aff8fb` |

## 3. Source and license findings

### Local documentary evidence

Source directories are `datasets/raw/BenthamDatasetR0-GT` (**23,386 files**) and `datasets/raw/BenthamDatasetR0-Images` (**433 files**).

`BenthamDatasetR0-GT/README.txt` identifies **Bentham Dataset R0**, ends **June 2014**, credits page naming to **UCL BENTHAM PROJECT**, and gives contact `jandreu@prhlt.upv.es`, subject **Bentham Dataset R0**. No contact was sent. It describes PAGE 2010 annotations and warns that supplied line-image filenames do not necessarily correspond to PAGE line IDs; custom extraction should take the transcript from the corresponding PAGE element. The preparation code follows that pairing approach.

The phrase **“Use this information as you prefer.”** occurs under **Partitions**. It is not an explicit general grant for images, annotations, commercial exploitation, ML training or derived weights.

There is **no named license, complete license text, copyright grant or binding attribution clause** in the local README. No separate LICENSE/COPYING/NOTICE/terms/attribution document was found in either Bentham tree. No original dataset archive was found under `datasets` for upstream checksum comparison. `datasets/raw/README.md` and the AI-engine `README.md` describe an earlier IAM-like inventory; neither grants Bentham rights.

**Exact locally established version:** a release labeled **Bentham Dataset R0**, with a June 2014 internal README. **Exact download origin and equivalence to an upstream archive remain unverified.** XML modification dates are not a dataset license or an authoritative release identifier.

### External primary-source corroboration

The [Zenodo record](https://zenodo.org/records/44519) identifies **Bentham Dataset R0 v1**, published **8 January 2016**, DOI **10.5281/zenodo.44519**, creator **Sánchez, Joan Andreu**, Universitat Politècnica de València. Its archive names match the local folders. Its description says **“This dataset is free available for research purposes”**. The fetched Rights section exposed no license name. API/export retrieval failed. No specific Creative Commons license or checksum match was verified. The online standalone README is 739 bytes; the local internal README is 3,316 bytes, so they are not interchangeable evidence.

A search-index excerpt for [UCL Transcription Desk Terms](https://transcribe-bentham.ucl.ac.uk/td/Terms_of_Use) refers to **CC BY-NC-ND 4.0** for material on that service. Direct retrieval returned HTTP 403. This raises a scope question; it does not establish that those terms govern R0, or permit importing a different permissive license.

### Permission verdict: UNVERIFIED

| Question | Documentary conclusion |
|---|---|
| License name for the local images and GT | **UNVERIFIED**; no grant included locally |
| Commercial use | **Not established**; research availability is not a commercial grant |
| Modification/cropping/adaptation | **Not explicitly established** by local rights documents |
| Model training/fine-tuning | **Not explicitly licensed locally**; HTR research context does not settle downstream scope |
| Commercial deployment / distribution of derived weights | **Not established** |
| Attribution requirements | **No formal local clause found**; authoritative requirements need confirmation |

Before training, retain documentary confirmation connecting this exact release to an authorized source and covering **both images and transcription/geometry annotations**. Confirm research/commercial scope, preprocessing/adaptation, ML training, internal deployment and derived-weight/data distribution. Clarify UCL/volunteer/other rights and whether separate permissions supersede restrictive service terms. Historic subject matter alone does not establish rights in all digital assets or annotations.

Recommended scholarly credit, pending actual license requirements: UCL Bentham Project/Transcribe Bentham, PRHLT–Universitat Politècnica de València, the creator/DOI above and the provider's specified dataset publication. This is a recommendation, not an assertion of an attribution-only license.

The [official TrOCR model page](https://huggingface.co/microsoft/trocr-base-handwritten) labels the model **MIT** and describes an IAM-fine-tuned single-line recognizer. No model card/license file is cached locally. Retain the applicable model notice and verify redistribution scope. Model licensing does not grant Bentham rights.

## 4. Model compatibility

Cache root: `C:\Users\SUNNY.COMPUTERS\.cache\huggingface\hub\models--microsoft--trocr-base-handwritten`.

Pinned revision: **`eaacaf452b06415df8f10bb6fad3a4c11e609406`**. The snapshot contains configuration, processor/tokenizer files and `model.safetensors`. Only the safetensors header/file size was inspected; weights were not deserialized. Processor/config loading used the absolute local snapshot, `local_files_only=True`, `HF_HUB_OFFLINE=1`, and `TRANSFORMERS_OFFLINE=1`.

### Images, tokenizer and interfaces

- `TrOCRProcessor`, slow **`ViTImageProcessor`**, **`RobertaTokenizer`**, byte-level BPE, `add_prefix_space=false`.
- RGB image → bilinear resize **384×384** → rescale **1/255** → channel mean/std **0.5/0.5**. Output float32 **`[B,3,384,384]`**. A synthetic white-image processor check produced `[1,3,384,384]`, all values `1.0`. No model forward ran.
- Square resize distorts line aspect ratios. Keep the existing transform for comparability; letterboxing or enhancement would be a separate validated preprocessing change.
- Encoder: ViT, 12 layers, hidden size **768**, patch size **16**. Decoder: TrOCR, 12 layers, hidden size **1024**, cross-attention input size **768**, vocabulary **50,265**. The hidden-size difference is supported by configured cross-attention.
- IDs: BOS/CLS **0**, EOS **2**, PAD **1**, UNK **3**. Tokenizer maximum length and decoder position capacity: **512**.
- Future inputs: pixels `[B,3,384,384]`; integer labels `[B,T]`. Generated outputs are token IDs `[B,T]` decoded with the same tokenizer.

### Target-length audit: train and validation only

Tokenization used existing **NFC + whitespace collapse/trim**, preserving case/punctuation/accents, with standard special tokens, no padding and **no truncation**. Test labels were checked for non-emptiness, but were not tokenized to select limits.

| Split | Count | Min tokens | Median | P95 | Max tokens | >64 / >128 / >192 | UNK |
|---|---:|---:|---:|---:|---:|---|---:|
| Train | 9,100 | 3 | 13 | 18 | **34** | 0 / 0 / 0 | 0 |
| Validation | 1,197 | 3 | 14 | 18 | **26** | 0 / 0 / 0 | 0 |

A **64-token training target ceiling**, including special tokens, covers observed labels. Use dynamic padding and a length assertion; do not silently truncate. The existing inference ceiling **192 new tokens** is separate and should remain fixed for initial validation comparisons. Neither is the architectural limit of 512.

Raw versus normalized references differ in **4,334 train / 537 validation** records. Annotation-marker row counts are: `<gap` **40 / 7**, `_` **373 / 47**, `=` **377 / 60**. Agree a target policy before training. Keeping current normalization/markers initially preserves comparability; removing or interpreting markers changes the target definition. Originals remain untouched.

### Training configuration gaps

The cached **top-level** model config has null `decoder_start_token_id`, `pad_token_id` and `eos_token_id`. Generation config has **2,1,2**. Training's `shift_tokens_right` reads the top-level model config and will reject unset start/pad IDs; successful generation does not establish training readiness.

Future code must set in-memory top-level IDs to **start=2, pad=1, eos=2**, keep generation consistent and verify decoder vocab size **50,265**. Preserve the pretrained start convention instead of blindly replacing it with BOS=0. Supply labels once; let the wrapper create shifted decoder inputs. Do not double-shift labels.

Right-pad labels using their attention mask; padding becomes **-100**, EOS remains intact. Ensure targets are not entirely ignored. For metric decoding, replace -100 with PAD **on a copy**. Add collator tests for mixed lengths, masks, BOS/EOS, token ranges and decoder inputs. No training dataset adapter/collator/optimizer/trainer exists in the inspected project modules.

### Blocking loss-alignment verification

Installed Transformers **4.57.6** source shows:

1. `VisionEncoderDecoderModel.forward` shifts decoder inputs right, then calls `self.loss_function(logits=..., labels=..., vocab_size=...)`.
2. Its class name has no matching installed `LOSS_MAPPING` entry; the base property falls back to **`ForCausalLMLoss`**.
3. That fallback shifts labels left internally when `shift_labels` is absent, creating a potential extra shift for already position-aligned encoder-decoder outputs.

A tiny **loss-function-only** probe used synthetic `[1,4,5]` logits and labels `[0,3,2,-100]`: independent aligned cross-entropy **0.0**, dispatched fallback loss **20.0**. No model instance, backward pass, optimizer or parameter update was involved.

This confirms dispatch/shift behavior, not an end-to-end training test. Require a verified library build or explicitly tested aligned token cross-entropy with -100 ignored. Verify wrapper loss against independent aligned cross-entropy, including masks and accumulation, before any optimizer update. No library/code patch was made. [Official encoder-decoder documentation](https://huggingface.co/docs/transformers/model_doc/vision-encoder-decoder) describes pixel-values/labels training and automatic decoder-input creation; installed source governs environment-specific findings.

### Training/inference sharing and mismatches

The baseline directly processes RGB line crops with the cached processor, seed 42, CPU float32, greedy decoding, one beam, no sampling, `max_new_tokens=192`, `use_cache=True`. Future crop-level training can share that processor/tokenizer.

The application page path differs: `recognize_page` calls EXIF transpose, grayscale conversion, median filter size 3, autocontrast cutoff 1, contrast factor 1.15, maximum dimension 2400, then threshold-based line segmentation and RGB/TrOCR processing. Prepared polygon crops do not reproduce that pipeline. Later evaluate page enhancement/segmentation on validation pages separately; line CER is not an end-to-end page guarantee.

The recognizer defaults `local_files_only=False`; future fine-tuned inference must explicitly select its new local checkpoint/processor offline. Save complete processor/tokenizer and generation config with checkpoints. Pin `use_fast=False` and versions initially. Cached generation has `use_cache=False` and decoder config has legacy `max_length=20`; explicit baseline generation overrides matter. Disable cache during training, especially with gradient checkpointing, and enable it deliberately for evaluation.

The earlier warning about initialized encoder pooler weights should be recorded in a future run. Serialized header counts below are not an exact live-model parameter count: aliases and newly initialized unused pooling parameters can differ. The warning is not a reason to run training during this audit.

## 5. Hardware and performance feasibility

### Measured environment

- Windows **11**, build **26200**; Python **3.12.9**, 64-bit.
- **Intel Core i5-1145G7 @ 2.60 GHz**, **8 logical CPUs**.
- Physical RAM **16,844,550,144 bytes ≈15.69 GiB**. Available at inspection: **3,488,288,768 bytes ≈3.25 GiB**, a point-in-time measurement.
- PyTorch **2.15.0+cpu**, Transformers **4.57.6**, Pillow **12.3.0**, NumPy **2.5.4**, tokenizers **0.22.2**, safetensors **0.8.0**.
- Intel Iris Xe is user-reported, not separately enumerated. It is not a CUDA device for this CPU-only build. No alternate GPU backend was configured/tested.
- `accelerate` is **not installed**; a Trainer implementation requires a compatible version. A manual loop still needs its own verified device/resume/evaluation handling.
- Disk free: **324,885,946,368 bytes ≈302.6 GiB**.

### Memory estimates and safety

The safetensors header contains **478 F32 tensors**, **333,331,200 serialized elements**: encoder **86,062,848**, decoder **247,268,352**. File size: **1,333,384,464 bytes ≈1.24 GiB**. These are persisted header counts, not measured model allocations.

Full FP32 AdamW persistent state is approximately:

`P × (4 bytes weights + 4 gradients + 4 first moment + 4 second moment)`

That is **5.33 GB decimal / 4.97 GiB**. Frozen-encoder training retains encoder weights and decoder gradients/moments: `4×encoder_elements + 16×decoder_elements ≈4.01 GiB`. This excludes activations, libraries, allocator fragmentation, data buffers, checkpoint copies, Windows, the IDE and shared graphics memory. The [AdamW documentation](https://docs.pytorch.org/docs/stable/generated/torch.optim.AdamW.html) describes the two moment states used in this calculation.

**Planning envelopes, not measured peaks:** approximately **6–10 GiB process RAM** for frozen-encoder decoder adaptation, or **8–14 GiB or more** for full-model batch-one training, depending on padding, kernels and temporary allocations. Full training can exceed usable physical RAM even after applications close. Batch size one does not eliminate optimizer state.

Current available RAM is below even the frozen-encoder persistent estimate: **do not start a pilot now**. Before a separately authorized pilot, close memory-heavy applications, target **8–10 GiB free**, reserve several GiB for Windows, then require measured peak use plus at least 20% headroom. That free-memory threshold is not a guarantee of fit. Provision another suitable machine if headroom cannot be achieved. Paging can cause prolonged stalls or termination; it is not a RAM substitute.

Use lazy image loading/closing, batch 1, dynamic label padding, `num_workers=0` initially on Windows, no pinned-memory queue, and conservative CPU AdamW `foreach=False`, `fused=False`. Do not cache all processed tensors in RAM: one `[3,384,384]` float32 tensor is about 1.69 MiB; 9,100 alone require about **15 GiB**.

Accumulation increases effective batch size but does not remove base state or per-sample work. Gradient checkpointing trades time for activation memory and requires a later measured decision. CPU FP16 is not recommended initially; BF16 support/performance was not established.

### Time estimate — assumptions, not fabricated measurements

**No training or gradient benchmark ran.** Teacher-forced forward/backward time cannot be inferred directly from autoregressive inference.

The existing **validation metrics only** record 1,197 sequential CPU samples in **3,069.99 seconds = 51m 10s ≈0.85 h**. This supports a validation-generation overhead estimate, not a training-step estimate. Future generated lengths, load and speed can change.

Let `s` be measured amortized seconds per batch-one training microstep, including forward/backward and its share of optimizer work:

`train hours/epoch = 9,100 × s / 3,600 = 2.528 × s`.

Add validation, checkpoint I/O and interruptions. Illustrative sensitivity examples, **not predictions or measured bounds**:

| Assumed s | Training/epoch | With ~0.85 h validation | Three epochs excluding checkpoint I/O |
|---:|---:|---:|---:|
| 1 second | 2.53 h | 3.38 h | 10.1 h |
| 5 seconds | 12.64 h | 13.49 h | 40.5 h |
| 15 seconds | 37.92 h | 38.77 h | 116.3 h |

Real time can fall outside this table. A later authorized **20–50-microstep** memory/timing pilot is necessary. CPU fine-tuning is technically possible under controlled conditions but **not a practical routine multi-experiment workflow on the currently loaded machine**. Slow measured steps can mean multi-day runs; no exact training duration is promised.

### Checkpoint storage

Approximate model export: **1.24 GiB** plus processor/config. Full FP32 AdamW resume state: **3.73 GiB/checkpoint** (weights plus two moments), excluding scheduler/RNG/metadata and temporary files. Frozen-encoder resume state: about **3.08 GiB/checkpoint**. Gradients normally are not part of saved optimizer state.

Two full checkpoints, a best-model export and one temporary checkpoint can approach **12.5 GiB**. Reserve **15–20 GiB**. Current disk space is adequate. Keep experiments in a new directory; preserve the cached pretrained model and baseline artifacts.

## 6. Conditional initial training proposal

This configuration is proposed for later authorized work after all prerequisites are satisfied; nothing here was executed.

| Item | Conservative proposal |
|---|---|
| Initial weights | Pinned cached revision `eaacaf452b06415df8f10bb6fad3a4c11e609406`, local-only loading |
| Updates | **Train only**, 9,100 crops |
| Trainable modules | Freeze image encoder for the first pilot/epoch; train decoder including cross-attention. This reduces resource needs but does not guarantee fit. |
| Optimizer | AdamW on trainable parameters; betas `(0.9,0.999)`, epsilon `1e-8`, weight decay `0.01`, exclude biases/norm parameters; `foreach=False`, `fused=False` |
| Learning rate | Initial **5e-5** for decoder-only adaptation; linear schedule, **5% warmup**, max gradient norm **1.0**; proposed, not tuned |
| Batch / dtype | Train **1**, validation **1**, CPU float32 |
| Accumulation | **8** microbatches, effective batch 8; **1,138 optimizer updates/epoch** if final partial group is flushed. Test scaling/partial groups. |
| Targets | Existing normalization/markers in memory; dynamic right-padding, **64-token length assertion**, padding=-100; tested IDs, one decoder-input shift and aligned loss |
| Epochs | **1 initially**, after pilot; consider **2–3 total** only if validation and measured resource budget justify it |
| Selection data | **Validation only**, all 1,197 samples; corpus CER primary, WER and exact match secondary |
| Validation decoding | Same baseline normalization and greedy generation: one beam, no sampling, max 192 new tokens, float32, batch 1; cache off for training/on for evaluation |
| Checkpoints | Evaluate/save each epoch; retain 2, best validation CER, `greater_is_better=False`, reload best at end |
| Early stopping | Proposed patience **2 evaluations**, minimum improvement **0.001 absolute CER** (0.1 percentage point); epoch-level stopping has limited resolution within a three-epoch cap |
| Resuming | Full model/processor/tokenizer/generation config, optimizer/scheduler, RNG, epoch/step and accumulation boundary/state; explicit experiment checkpoint |
| Reproducibility | Seed **42** for Python/NumPy/PyTorch/train shuffle; pin versions/revision, record manifest hashes, trainable modules, normalization, threads, device and timestamps; deterministic algorithms where supported |
| Test use | **Final evaluation only after selecting/fixing the model and decoding policy**; all 1,116 test crops; no test predictions used for schedules, targets, thresholds or early stopping |

A later, separately budgeted full-model experiment might start around **1e-5–2e-5** if resources allow, using validation to assess its value. These rates are proposals, not claims of improved accuracy. Do not unfreeze during the feasibility pilot or change the established partitions.

Epoch-only saving can lose hours after a restart. Future code may add resume-only snapshots at safe optimizer boundaries, separately from epoch-based model selection; test atomic writes and restoration. Keep Trainer evaluation/save strategies compatible with best-model loading. A manual loop must explicitly handle device/mode switches, failure accounting, accumulated loss and resuming.

The test split already has a pretrained baseline. Treat historical test results as fixed context, not an iterative tuning signal. Lock selection before final testing. This audit did not open test predictions or test metrics.

## 7. Risks and mitigation

| Risk | Mitigation |
|---|---|
| Unverified rights/provenance | Retain authoritative evidence for this release, both assets/annotations, permitted training/use/distribution and attribution |
| Unset IDs / wrong loss alignment | Correct in-memory configuration and independently test aligned -100-masked loss before any optimizer update |
| RAM exhaustion, paging and thermal slowdown | Free/provision RAM, freeze encoder, batch 1, no loader workers, measured authorized pilot and safety headroom |
| Multi-hour/day runs, interruptions | Pilot-based budget, full-state checkpoints, safe resume boundaries and stable power/storage |
| Unsupported writer-isolation claims | Report page-level separation only |
| Crop/page domain mismatch | Share crop processor initially; separately assess page preprocessing/segmentation on validation |
| Markers / normalization drift | Explicit versioned label policy; preserve raw labels and case/punctuation |
| Stale extraction diagnostic | Preserve historical report; cite fresh verification, reconcile documentation only in later authorized work |
| Test leakage into decisions | Validation-only selection; test predictions excluded from all tuning |
| Incomplete checkpoint artifacts | Save processor/config/optimizer/RNG together and verify recovery in a new experiment directory |

## 8. Exact prerequisites before training

1. **Resolve provenance and dataset rights** for the exact R0 release and intended Academix use. Confirm images, annotations, preprocessing, training, commercial scope and derived-weight redistribution; record mandatory attribution. Keep UNVERIFIED until documented.
2. **Retain applicable model licensing/notices** and clarify redistribution scope separately from dataset rights.
3. **Authorize and implement the training pipeline**: immutable manifest loading, offline loaders, train-only sampler, correct labels/masks/IDs/loss, validation generation and complete checkpoint/resume behavior. There is no training implementation ready to approve now.
4. **Resolve installed loss dispatch** through a verified build or tested aligned-loss implementation; validate padding, one-time input shifting and accumulation before updates. No environment/code fix was made here.
5. **Provision compatible training dependencies**, including `accelerate` for Trainer, in separately authorized work; pin versions. No package install/download was performed.
6. **Approve the annotation/normalization policy** and assert target lengths without truncating; leave source files and splits untouched.
7. **Free/provision sufficient RAM**. At measured 3.25 GiB free, do not attempt training. Plan 8–10 GiB free for a conservative pilot, then verify measured peak plus safety margin; not a guaranteed fit.
8. **Separately authorize a tiny training feasibility pilot**, after rights/correctness are resolved, measuring peak resident/committed RAM, amortized microstep time, finite loss/gradients and resume integrity. No such pilot was run here.
9. **Set wall-time/storage/resume budgets** from pilot results and protect baseline artifacts/cached weights in new experiment paths.
10. **Fix the validation-only selection and final-test protocol**, including page-level limitations, before a full epoch.

## 9. Exact inspection scope and test evidence

### Local files

Paths are relative to the AI-engine root except where another root is stated. Individual members of large sets are exactly enumerated by the pinned processed manifest; reproducing that enumeration avoids a redundant 11,413-line appendix.

- `datasets/raw/BenthamDatasetR0-GT/README.txt`: complete release description.
- `datasets/raw/README.md`, `README.md`, `evaluation/BENTHAM_BASELINE.md`, `pyproject.toml`: relevant provenance/setup/conventions.
- All **433** `datasets/raw/BenthamDatasetR0-GT/PAGE/*.xml` files: parsed metadata. Exact source names are the distinct `source_xml_path` values in the processed manifest, rooted at that PAGE directory. Example: `002_080_001.xml`.
- `datasets/raw/BenthamDatasetR0-GT/Partitions/Train.lst`, `Validation.lst`, `Test.lst`, `TrainLines.lst`, `ValidationLines.lst`, `TestLines.lst`: all entries counted; leading IDs in page lists inspected.
- `datasets/processed/bentham/manifest.jsonl`, `datasets/manifests/bentham/train.jsonl`, `validation.jsonl`, `test.jsonl`: every record, with hashes in section 2.
- **All 11,413 crop files** enumerated by `crop_relative_path` in the pinned processed manifest, resolved under `datasets/processed/bentham`: byte hashes, Pillow integrity/full decoding and dimensions.
- `datasets/processed/bentham/dataset_report.json`, `datasets/manifests/bentham/split_report.json`: historical diagnostics/provenance.
- `evaluation/results/bentham_trocr_validation_metrics.json`: stored timing/configuration only. Prediction JSONL files and test metrics were **not read**.
- `preprocessing/prepare_bentham_dataset.py`, `preprocessing/split_bentham_dataset.py`, `preprocessing/handwritten_ocr.py`, `preprocessing/image_preprocessor.py`, `preprocessing/text_extractor.py`, `inference/evaluation_pipeline.py`, `evaluation/evaluate_trocr_baseline.py`: relevant preparation/inference/metric/loading paths inspected or searched.
- `tests/test_trocr_baseline.py`, `tests/test_trocr_error_analysis.py`: selected pure tests below.
- Under the cache root in section 4: `refs/main`; revision snapshot `config.json`, `generation_config.json`, `preprocessor_config.json`, `tokenizer_config.json`, `special_tokens_map.json`, `vocab.json`, `merges.txt`; **header/file size only** of `model.safetensors`.
- Under `C:\Users\SUNNY.COMPUTERS\academix\.venv\Lib\site-packages\transformers`: `models/vision_encoder_decoder/modeling_vision_encoder_decoder.py`, `models/vision_encoder_decoder/configuration_vision_encoder_decoder.py`, `models/trocr/modeling_trocr.py`, `models/vit/image_processing_vit.py`, `modeling_utils.py`, `loss/loss_utils.py`, `training_args.py`: relevant configuration, shift/loss, normalization and dependency behavior.

Raw-tree filenames were searched for README/license/terms/notice/attribution files and original archives. The audit did not read every raw transcription file or decode the original raw images; it inspected all PAGE metadata and processed crops as stated. OS checks used the Windows memory API, CPU registry description, Python/package metadata and disk free-space query. No checkpoint tensor data was deserialized.

### Existing tests executed without workspace cache writes

Command prefix: `..\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q`, followed by:

```text
tests/test_trocr_baseline.py::test_normalization_preserves_case_punctuation_accents
tests/test_trocr_baseline.py::test_known_corpus_metrics
tests/test_trocr_baseline.py::test_metrics_normalize_and_count_failures_in_full_denominator
tests/test_trocr_baseline.py::test_edits_empty_references_and_rates_above_one
tests/test_trocr_error_analysis.py::test_known_character_and_word_edits
tests/test_trocr_error_analysis.py::test_exhaustive_short_alignments_have_minimum_distance_and_reconstruct_prediction
tests/test_trocr_error_analysis.py::test_analysis_counts_categories_and_length_coverage_without_mutation
tests/test_trocr_error_analysis.py::test_empty_references_failures_and_rates_over_one
```

**8 passed in 0.08 seconds.** These pure tests use no filesystem fixtures and do not run evaluators or regenerate reports. Bytecode and pytest cache writing were disabled. The full suite/preparation tests were unnecessary and were not rerun.

Other passed checks: JSON counts/non-empty labels, exact multiset coverage, pairwise page separation, path containment, all crop integrity/decoding/dimensions, byte duplicates, before/after hashes, PAGE metadata, local processor shape and train/validation target lengths. Configuration and synthetic-loss probes exposed unresolved training items; they are **not passing end-to-end training tests**.

### External primary references

Accessed 2026-11-16, documentation only; no model/data archives fetched:

- [Zenodo R0 record](https://zenodo.org/records/44519): candidate source and research availability; API/export failed, no license inferred.
- [UCL Terms](https://transcribe-bentham.ucl.ac.uk/td/Terms_of_Use): search excerpt only, direct HTTP 403; applicability unresolved.
- [Official TrOCR model card](https://huggingface.co/microsoft/trocr-base-handwritten): advertised model license and single-line scope.
- [Hugging Face encoder-decoder documentation](https://huggingface.co/docs/transformers/model_doc/vision-encoder-decoder): conceptual interface; local source used for environment-specific conclusions.
- [PyTorch AdamW documentation](https://docs.pytorch.org/docs/stable/generated/torch.optim.AdamW.html): moment-state algorithm supporting arithmetic.

**Only created/modified project file: `evaluation/TROCR_FINE_TUNING_READINESS.md`.** Existing datasets, manifests, predictions, metrics, model weights, backend and Flutter files remain unchanged.
