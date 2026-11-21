# TrOCR Blockers Investigation — Academix AI Engine

Access/investigation date: **2026-11-16**, Asia/Karachi. Project: `C:\Users\SUNNY.COMPUTERS\academix\ai-engine`.

## Summary

**Training remains blocked.** The exact local Bentham R0 package's usage license is **UNVERIFIED**. Authoritative UCL documentation establishes restrictive terms for its online transcripts and a separate image-permission process; those facts do not prove the terms of the independently packaged R0 release. No documented grant was found covering commercial training, derived-weight distribution or processed-crop redistribution.

Local configuration and six no-gradient helper checks substantiate the decoder blockers. The cached generation/nested decoder IDs agree with the tokenizer, but the top-level training IDs are unset. Installed Transformers dispatches an already-aligned encoder-decoder loss through a causal-LM label-shifting helper. An unshifted helper passes padding and normalization checks and is available through a supported in-memory loss setter. This is a specific, version-bound future fix, not a completed end-to-end training validation.

**Full checkpoint forward-loss smoke test: SKIPPED for RAM safety.** No checkpoint weights were loaded, no model instance constructed, no backward propagation/optimizer/checkpoint saving performed. Only this investigation report was created; the existing readiness report is preserved.

## 1. Official license evidence and unresolved permissions

### Evidence register

All URLs below were accessed or attempted on **2026-11-16**. Only documentation/metadata was requested; no dataset archive or model was downloaded.

| Source | URL / location | Actual evidence and limits |
|---|---|---|
| Original R0 publisher deposit | https://zenodo.org/records/44519 | Identifies Bentham Dataset R0, v1, published 8 January 2016, DOI `10.5281/zenodo.44519`, creator Sánchez, Joan Andreu / Universitat Politècnica de València. Research availability is stated; the fetched Rights section exposed no named license. |
| Publisher's standalone README | https://zenodo.org/records/44519/files/README.txt?download=1 | Successfully read as documentation. Lists archive sizes/checksums and two dataset references; contains no license grant. |
| Local internal README | `datasets/raw/BenthamDatasetR0-GT/README.txt` | June 2014 R0 description, UCL page naming, PAGE/transcription correspondence and contact `jandreu@prhlt.upv.es`. No general license. The permissive-looking partition instruction concerns partition information, not a comprehensive rights grant. |
| UCL Terms of Use | https://transcribe-bentham.ucl.ac.uk/td/Terms_of_Use | Official-domain search result supplied the Terms and citation-guidelines text, associated with revision `oldid=224115`. Direct URL returned HTTP 403; alternate revision URL was unavailable. Search-index evidence is identified as such, not represented as a fresh direct fetch. |
| UCL project credits | https://blogs.ucl.ac.uk/transcribe-bentham/credits/ | Official-domain indexed page independently names the transcript license below. Direct fetch returned HTTP 502. |
| License publisher's legal code | https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en | Successfully read; sections 2 and 3 distinguish noncommercial use, adaptation, technical modifications and sharing/attribution. This defines that license, not its applicability to R0. |
| Zenodo reuse guidance | https://support.zenodo.org/help/en-gb/2-content/21-can-i-get-permission-to-use-a-specific-record | Repository explains that rights depend on the particular deposit's license; generic repository defaults are not evidence of a grant for this record. |

The R0 description says **“This dataset is free available for research purposes”**. This is a confirmed publisher statement, not commercial permission. Neither “open” access nor the repository's default CC BY license can substitute for the particular record's documented grant.

The publisher lists original archive MD5s `35a00f5e94728191cbc188963d533495` (Images) and `df4e1cf620c68ea8af7301fd51ed42fd` (GT). The previous audit found no retained original archive for verification. Matching folder names/local README identify an R0-like release, but do not establish the local download chain or an exact archive checksum match.

### Exact named license found — scoped to UCL transcripts

**Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)** is explicitly named for Transcribe Bentham transcripts by UCL's indexed Terms and Credits pages. UCL's terms separately direct image-reuse requests to its administrators and identify UCL Special Collections / the British Library as holders for the listed box ranges. Attribution instructions identify transcript folio/box, repository, site, access date and URL. Contact listed there: `transcribe.bentham@ucl.ac.uk`. No message was sent.

This confirms a named policy for that service's material. It does **not** establish that the R0 depositor supplied all images and annotations under the same license or under a separate permissive agreement.

The CC legal code permits noncommercial reproduction/sharing of licensed material and production/reproduction, **but not sharing**, of adapted material. Necessary technical modifications are separately permitted. Sharing requires specified credit/notices, a license link and indications of changes. It does not name ML training or derived weights. Whether a crop is a technical modification/adaptation, or weights constitute adapted material, is not resolved by those documents. No blanket assertion that ND prohibits every internal preprocessing step, or that weights automatically inherit or escape the license, is justified.

### Permission matrix for this local R0 dataset

| Requested use | Confirmed documentary status | Decision for Academix |
|---|---|---|
| Commercial use | No R0 commercial grant found. The related UCL transcript license is noncommercial. | **UNVERIFIED for R0; not granted by the cited UCL transcript license.** Do not treat research access as commercial permission. |
| Modification / preprocessing | No explicit R0-wide grant found. The CC license distinguishes technical changes and noncommercial adaptation; applicability and crop classification are unresolved. | **UNVERIFIED** for the intended R0 image/annotation processing scope. |
| ML model training | Research availability and HTR context are documented, but no examined text expressly licenses ML training and intended downstream use. | **UNVERIFIED**; research context is not an explicit commercial-training grant. |
| Distribution of derived weights | No examined R0 statement explicitly covers it; weight classification and underlying rights remain unresolved. | **UNVERIFIED**; obtain explicit scope confirmation. |
| Redistribution of processed crops | No explicit R0 image/crop redistribution grant found. UCL separately requires an image-reuse inquiry; transcript licensing does not grant image rights. | **UNVERIFIED**, including commercial redistribution. |

No applicable statutory exception or separate agreement was established; this is a documentary permission audit, not a determination that every possible use is unlawful.

### What must be confirmed

Request documentary confirmation from the R0 publisher/depositor and relevant image/annotation rightsholders connecting the exact release to its authoritative source. Ask separately about images, PAGE geometry and transcripts; internal research preprocessing/training; commercial Academix training/deployment; derived-weight distribution; and processed-crop redistribution. Obtain attribution wording, territory/purpose restrictions and any permission that supersedes the service terms. Proposed scholarly citations alone cannot repair a missing grant.

### Unavailable metadata and investigation limits

These metadata endpoints were attempted without downloading archives and were not accessible through the browsing tool:

- `https://zenodo.org/api/records/44519`
- `https://zenodo.org/records/44519/export/json`
- `https://zenodo.org/oai2d?verb=GetRecord&metadataPrefix=oai_dc&identifier=oai:zenodo.org:44519`
- `https://api.datacite.org/dois/10.5281/zenodo.44519`
- The DataCite query endpoint for the same DOI.

This inability is **not** evidence that no license exists upstream; it prevents confirmation here. No third-party assertion of CC BY was adopted, no repository default was substituted, and no archived revision of UCL service terms was assumed to govern the June 2014 local files.

## 2. Actual local tokenizer and model configuration

Environment: root Python **3.12.9**, PyTorch **2.15.0+cpu**, Transformers **4.57.6**. `accelerate` is absent. No package was installed or replaced.

Cache root: `C:\Users\SUNNY.COMPUTERS\.cache\huggingface\hub\models--microsoft--trocr-base-handwritten`.

Actual `refs/main` revision: **`eaacaf452b06415df8f10bb6fad3a4c11e609406`**. Processor, `VisionEncoderDecoderConfig` and `GenerationConfig` were loaded from this absolute local snapshot with `local_files_only=True`; processor used `use_fast=False`. Offline environment flags were set before imports. **No `VisionEncoderDecoderModel.from_pretrained` or model constructor was called.**

| Token/config field | Processor tokenizer | Top-level model config | Nested decoder config | Generation config |
|---|---:|---:|---:|---:|
| BOS / CLS | 0 | null (BOS) | 0 | 0 |
| Decoder start | Not a tokenizer field | **null** | **2** | **2** |
| PAD | **1** | **null** | **1** | **1** |
| EOS | **2** | **null** | **2** | **2** |

Other tokenizer IDs: SEP **2**, UNK **3**, MASK **50,264**. Both tokenizer length and decoder vocabulary size are **50,265**. Processor is `TrOCRProcessor`, tokenizer `RobertaTokenizer`; image size is **384×384**. These values were obtained from actual local objects and JSON, not inferred from examples.

**Compatibility conclusion:** nested decoder/generation agree with the tokenizer. The missing top-level training IDs are the gap. In particular, start **2** is the pretrained decoder convention even though BOS is **0**; blindly using a generic BOS/CLS recipe would alter that convention.

### Padding and decoder-input helper test

One existing **training-manifest reference**, not a test/validation sample, was selected:

- Crop identifier: `line_images/071_030_001__r4__r57__r001_l023_g000660.png`
- Raw reference: `the`
- Tokenization with standard special tokens, right-padding to length 8, no truncation: `[0,627,2,1,1,1,1,1]`.
- After masking attention-mask-zero positions: labels **`[0,627,2,-100,-100,-100,-100,-100]`**.
- `shift_tokens_right(labels, pad=1, start=2)` returned **`[2,0,627,2,1,1,1,1]`**.
- EOS remained present; no -100 entered decoder input IDs; decoding nonignored labels round-tripped to `the`.
- Calling the same helper with the unmodified top-level config IDs raised the expected missing `decoder_start_token_id` error.

Only its manifest text was tokenized. The crop was not changed or passed through a model. `-100` is a **loss ignore value**, not a valid decoder embedding/tokenizer input ID. Use the attention mask to identify label padding, keep EOS, shift decoder inputs once, and replace -100 with PAD on a copy before metric decoding.

## 3. Installed loss dispatch and training-API compatibility

### Source-level trace

Files under `C:\Users\SUNNY.COMPUTERS\academix\.venv\Lib\site-packages\transformers`:

- `models/vision_encoder_decoder/modeling_vision_encoder_decoder.py`: helper at line **37**, wrapper's label-input shift and loss call around lines **547–578**.
- `modeling_utils.py`: class-name-based loss selection during initialization; `loss_function` property around line **5755**, setter **5770**.
- `loss/loss_utils.py`: `ForCausalLMLoss` at line **45**, `ForMaskedLMLoss` at **71**, `LOSS_MAPPING` at **147**.
- `trainer.py`: `compute_loss` around **4076**, accumulated item-count handling around **5593**.

The wrapper creates decoder inputs by shifting labels right, obtains decoder logits, then invokes `self.loss_function` with the original labels. `VisionEncoderDecoderModel` matches no installed loss-map key, so the base property defaults to **`ForCausalLMLoss`**. Unless explicit shifted labels are supplied, that function pads/left-shifts labels internally. That next-token shift is inappropriate for already position-aligned wrapper logits.

### Executed no-gradient loss probes

Synthetic tensors were tiny, on CPU, and created without `requires_grad`. Calculations used `torch.no_grad()`. No checkpoint parameters or model outputs were involved.

| Probe | Actual result |
|---|---|
| Correctly aligned synthetic logits `[1,4,5]`, labels `[0,3,2,-100]`; direct cross-entropy | **0.0** |
| Actual installed default dispatch on the same logits/labels | **20.0**, via `ForCausalLMLoss` |
| Installed unshifted helper `ForMaskedLMLoss` on the same tensors | **0.0**, matches direct CE |
| Supported loss-property setter on a lightweight stand-in object | Passed; assigned helper retrieved unchanged |
| Unequal-length synthetic targets with -100 padding | Loss **1.6297565698623657**; changing ignored-position logits left it unchanged |
| Two microbatches using total nonignored-token count **5** | Summed normalized loss **1.6297565698623657**, equal to combined-batch mean |

The extra-shift behavior is reproduced at the actual dispatcher/helper level. This is stronger evidence than merely noticing a warning, but it is **not a full checkpoint forward-loss smoke test**. It does not establish full-model numerical loss, gradient correctness, optimizer behavior, or an installed Trainer run.

### Intended API

`VisionEncoderDecoderModel(pixel_values=..., labels=..., use_cache=False)` is the intended teacher-forced wrapper interface. After correct IDs and an aligned loss are installed in memory, the default `Seq2SeqTrainer` loss path can retain labels and let the wrapper create decoder inputs. A compatible `accelerate` dependency remains necessary.

Do not propose only an arbitrary `compute_loss_func` callback as a drop-in fix: this installed Trainer removes `labels` from inputs before the forward call when such a callback or label smoother is active. This wrapper then needs decoder inputs supplied separately. The smaller proposed override below retains the default label path; use `label_smoothing_factor=0.0` and no custom `compute_loss_func` initially. Check the Trainer's item-count handling rather than dividing the loss a second time blindly during gradient accumulation.

## 4. Full checkpoint forward-loss smoke test

**Status: SKIPPED — conservative RAM headroom was insufficient.**

A fresh Windows memory query, before Torch/Transformers imports, returned:

- Physical RAM: **16,844,550,144 bytes**, approximately **15.69 GiB**.
- Available RAM: **4,079,460,352 bytes**, approximately **3.80 GiB**.
- Cached safetensors size: **1,333,384,464 bytes**, approximately **1.24 GiB**.

No-gradient inference needs no optimizer/gradient state, so the readiness audit's 4.97-GiB AdamW-state estimate is **not** the correct minimum for this smoke test. The decision instead accounts for model residency, library imports, possible loading/conversion copies, attention/forward allocations and competing Windows/IDE demand. A rough **3–4+ GiB incremental peak allowance** is a conservative planning estimate, not a measured model peak or hard minimum. Against 3.80 GiB available before imports, safe spare capacity could not be established. Loading might succeed, but it would risk memory pressure/paging or exhaustion; the task explicitly permits static-only checkpoint inspection in that situation.

The six helper checks above do not substitute for a full smoke result. No crop tensor/model forward was run, no full-model loss value is reported, and no real-model accuracy or trainability conclusion is fabricated. A later no-gradient checkpoint forward should be run only with adequate measured headroom and the corrected in-memory configuration/loss.

## 5. Smallest safe future fix

**Scope: recommendations only.** No inference source, application code, cached JSON, model state, dataset or manifest was modified. The readiness report remains unchanged.

### Where to apply it

In a future training script, immediately **after local processor/model loading** and **before collator/Trainer construction, forward-loss validation or optimizer construction**. Repeat the setup after every model reload/resume; an in-memory callable override is not serialized by `save_pretrained` as a permanent library fix.

### Proposed configuration-only and loss-dispatch changes

The following is documentation, **not code executed against a checkpoint model in this investigation**:

```python
# Future training setup, pinned to the inspected Transformers build.
# processor/model must already have been loaded from the local snapshot,
# with local_files_only=True; processor uses use_fast=False.
from transformers.loss.loss_utils import ForMaskedLMLoss

start = model.generation_config.decoder_start_token_id  # actual cache: 2
pad = processor.tokenizer.pad_token_id                  # actual cache: 1
eos = processor.tokenizer.eos_token_id                  # actual cache: 2
assert start is not None and pad is not None and eos is not None
assert start == model.config.decoder.decoder_start_token_id
assert pad == model.config.decoder.pad_token_id
assert eos == model.config.decoder.eos_token_id
assert len(processor.tokenizer) == model.config.decoder.vocab_size

model.config.decoder_start_token_id = start
model.config.pad_token_id = pad
model.config.eos_token_id = eos
model.generation_config.pad_token_id = pad
model.generation_config.eos_token_id = eos

# Unshifted token cross-entropy; no alteration of the model architecture.
model.loss_function = ForMaskedLMLoss
# Future teacher-forced calls explicitly use use_cache=False.
```

`ForMaskedLMLoss` is the installed helper's name; using its **unshifted cross-entropy implementation** does not turn TrOCR into a masked-language model, introduce random masking, resize vocabulary or change pretrained weights. It ignores -100 and supports `num_items_in_batch`, as verified by the lightweight probes. It is an internal, version-sensitive API: pin the environment and test it again after any Transformers change. The supported setter is the reason no installed-library or inference-code patch is necessary for this proposed fix.

An alternative future implementation may compute the same aligned CE explicitly from logits, with decoder inputs prepared once and correct valid-token normalization. That requires more custom training plumbing. Replacing labels with another manual next-token shift, merely setting IDs, or blindly swapping BOS=0 for the observed start=2 does **not** resolve the demonstrated loss mismatch.

### Required label/collator behavior

- Tokenize the agreed reference text policy with the local processor tokenizer, preserving standard special tokens; retain raw source references unchanged.
- Right-pad per batch; mask only tokenizer attention-mask-zero label positions to **-100**. Retain EOS **2** and genuine nonpadding token IDs.
- Let the wrapper shift decoder inputs **once** when labels are supplied. No -100 may enter decoder embedding inputs.
- Validate target lengths without silent truncation. The prior audit measured train maximum **34** tokens and validation maximum **26**, including special tokens; the proposed 64-token assertion remains a documented candidate, not a reason to alter source labels.
- With the default Trainer path, initially use `label_smoothing_factor=0.0`, no custom `compute_loss_func`, and verify forwarding of the valid-token count. The unshifted helper uses sum/total-token normalization when that count is provided, otherwise mean CE.
- Do not add an extra accumulation divisor when the Trainer already handles normalization. Test unequal-length microbatches and partial accumulation groups under the actual selected Trainer version.
- Before decoding labels for CER/WER, replace -100 with PAD on a **copy**. Keep the baseline normalization policy explicit.

### Acceptance checks required before training

After memory and rights blockers are addressed, a future minimal **CPU eval-mode + `torch.no_grad()`** check should load the same cached checkpoint, apply the setup above, process one existing training crop and its reference, and compare the returned wrapper loss against independently computed **unshifted** cross-entropy of `outputs.logits` and the original masked labels. Require finite values and agreement within float32 tolerance; verify input/label shapes, IDs, no gradients, and unchanged source/checkpoint files. Also test two unequal-length label sequences for ignored-padding behavior. Do not call backward, construct an optimizer or save weights as part of that acceptance smoke check.

That real-checkpoint acceptance test was **not** completed here. A later training implementation also needs a separately authorized gradient/resume test; none is implied by the successful helper checks.

## 6. Remaining blockers

1. **R0 license/provenance:** explicit grants for images/annotations, training, intended commercial deployment, derived weights and crops remain UNVERIFIED. UCL's confirmed transcript restrictions and image process need reconciliation with the R0 release, not assumptions.
2. **Full-model compatibility acceptance:** no real checkpoint forward-loss test due RAM risk. The specific in-memory IDs and loss remedy are recommended and helper-tested, not installed or validated end to end.
3. **Resource headroom:** approximately 3.80 GiB available before imports is insufficient for a conservative full-model smoke decision; training has substantially greater requirements. Free/provision memory and measure peaks before any larger operation.
4. **Training dependencies/API:** `accelerate` is absent. No Trainer object was instantiated; no dependency upgrade/install or library change was attempted. The future environment must be pinned and its API reverified.
5. **Future training implementation:** collator, loss setup, validation-only selection and full-state resuming still need authorized implementation/testing. Existing inference remains untouched. Train/validation/test partitions remain fixed, with test excluded from updates and selection.

## 7. Checks performed and preservation evidence

### Executed checks: six passed

1. Unmodified top-level training IDs correctly trigger the installed helper's missing-start error.
2. Actual local tokenizer padding, -100 masking, decoder-input shifting and round-trip decoding pass for the training reference `the`.
3. Actual installed default dispatch reproduces shifted loss **20.0**, versus aligned/helper **0.0**.
4. The supported property setter stores/retrieves the unshifted helper on a lightweight stand-in; no model object/parameters were modified.
5. Unshifted CE matches independent CE and ignores changes to padded-position logits.
6. Token-count-normalized losses across two unequal-length microbatches equal combined-batch mean CE (**1.6297565698623657**).

The code ran through the root virtual environment as a PowerShell here-string piped to `..\.venv\Scripts\python.exe -B -u -`. No test/script files were created. Python bytecode writing was disabled. These are assertion-based helper checks, **not a new pytest suite or full model smoke test**. All synthetic floating tensors had `requires_grad=False`; calculations used `torch.no_grad()`. No optimizer or backward call occurred.

### Files inspected

- Existing `evaluation/TROCR_FINE_TUNING_READINESS.md` and `datasets/raw/BenthamDatasetR0-GT/README.txt`.
- `datasets/manifests/bentham/train.jsonl` for one existing short reference; no test predictions or datasets were used for tuning/analysis.
- Cached `refs/main`, `config.json`, `generation_config.json`, `preprocessor_config.json`, `tokenizer_config.json`, `special_tokens_map.json`, `vocab.json`, `merges.txt` under the pinned snapshot. `model.safetensors` was checked by file size/mtime only in this investigation; its tensor data was not loaded.
- Installed Transformers `modeling_utils.py`, `loss/loss_utils.py`, `models/vision_encoder_decoder/modeling_vision_encoder_decoder.py`, and `trainer.py` for actual shift, loss dispatch, setter and Trainer/item-count behavior.
- Official web documents and inaccessible endpoints enumerated in section 1. Unrelated search hits and third-party license claims were not used as evidence.

Before/after hashes were checked for the readiness report, local README, training manifest and the seven cached config/tokenizer files. The checkpoint file's size and modification timestamp were checked unchanged; a full 1.33-GB binary hash was not necessary or performed. Other protected files were not written or processed.

| Protected artifact | SHA-256 before/after |
|---|---|
| Existing readiness report | `2541d73f95ca42e66b18cdfff61bc33102fbe9aa96765a7b0e24895f2e39e9b6` |
| Local Bentham README | `a6375ad5b6f97e147455878947fe453e609e558fbe95b859c10aaccf15659300` |
| Train manifest | `85178420a4703b62ff9b11157fa4aebcd411ee2e3e5402fcd4796488ddf184b3` |
| Cached model config | `4c779f24e063c437c3dafd5b2e6c9f59f2fa2bd1dbb4ae6a30153bbbbf19e647` |
| Cached generation config | `41149cdcffec4d657f32dfcddd9b208037f01286c9e07945c724908c58ed0193` |

**Only new project file: `evaluation/TROCR_BLOCKERS_INVESTIGATION.md`.** The previous readiness report, model files, datasets, manifests, predictions/splits, backend and Flutter code were preserved.
