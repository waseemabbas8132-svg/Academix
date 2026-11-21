# Handwriting Dataset Comparison — Academix AI Engine

Research/access date: **2026-11-16**, Asia/Karachi. Scope: publicly accessible publisher documentation and license text, not downloaded dataset contents or a legal determination about every downstream use.

## 1. Executive recommendation

**Best open candidate for an English Academix prototype: Goodnotes Handwriting Kollection (GNHK).** Its official publisher repository applies **CC BY 4.0 to the dataset**, and its modern photographed English handwriting is a closer domain match than historical manuscripts. This is affirmative copyright-license evidence for commercial reuse/adaptation, not an assumption from free access. However, original data access currently needs clarification, writer-disjoint evaluation is not established, and the documents do not give a separate model-weight distribution statement. Do not describe it as unconditional commercial-product clearance.

**Best classroom-specific supplement: ClozeFormHandwriting.** Its author repository explicitly licenses **images and annotations under CC BY 4.0**. It is relevant to difficult student writing but is only a small single-word corpus, not a replacement for line-level assignment data. Confirm consent/privacy scope before commercial use of student samples.

**Paid route worth a contract inquiry:** Nexdata's English handwriting OCR offering. The publisher advertises commercial licensing, but exact preprocessing, trained-weight, redistribution and attribution rights require the actual agreement. No purchase, sample request or contact was made.

**Do not commercially fine-tune from IAM, CVL or Washington under their current published noncommercial terms. Keep Bentham R0 rights UNVERIFIED.** The cached TrOCR checkpoint does not grant access rights to IAM or other datasets merely because it was pretrained/fine-tuned using them.

The final recommendation is to qualify GNHK's official release and rights documentation first, use the classroom corpus only as a reviewed supplement, and plan separately consented student-assignment data or a negotiated vendor collection for product-domain coverage. No dataset in this report is declared unconditionally cleared for weight distribution.

## 2. How permissions are classified

- **Confirmed:** an official source expressly states the relevant license or purpose.
- **License-based:** the named license grants reproduction/adaptation/sharing for the proposed copyright acts; this is distinguished from an explicit ML- or model-weight-specific clause.
- **NC only:** permitted published purpose is noncommercial; commercial use needs a separate grant.
- **UNVERIFIED:** necessary scope, applicability or agreement could not be established. This does not mean the use is definitively unlawful, nor that it is permitted.

A dataset's images, underlying copied text, transcriptions, geometry annotations, code and existing model weights may have different rights. A permissive code license or repository badge alone is not a dataset grant. A commercial image-use grant alone is not a verified model-weight distribution grant.

[CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en), sections 2–3, permits reproduction and adaptation/sharing without a noncommercial restriction, subject to credit/notices, license link and change indications. Privacy/publicity and other third-party rights are not comprehensively licensed. The text does not specifically classify trained weights. Where broad licensed rights apply to a use they can be sufficient; absence of the words “machine learning” is not automatically a prohibition. This report nevertheless marks **explicit weight-specific permission** UNVERIFIED unless established, and requires a documented release decision for Academix. Do not assume weights either automatically inherit or automatically escape dataset conditions.

## 3. License and access comparison

Each row's evidence links and asset distinctions are explained in section 5. “Commercial” describes the published grant, not an already-executed agreement with Academix.

| Dataset | Official license / terms | Commercial use | ML training | Preprocess / crop | Explicit derived-weight distribution | Processed-data redistribution | Access / fees |
|---|---|---|---|---|---|---|---|
| **IAM v3.0** | Custom **noncommercial research only** terms | **Not granted** | Confirmed for research; not commercial | Research use implied; exact transformation/redistribution scope UNVERIFIED | **UNVERIFIED** | **UNVERIFIED**, particularly commercial | Registration; free noncommercial research access |
| **Bentham R0** | Exact package license **UNVERIFIED**; publisher states research availability | **UNVERIFIED** | Research context, no verified explicit grant for intended scope | **UNVERIFIED** | **UNVERIFIED** | **UNVERIFIED** | Public publisher archives; research availability; no commercial fee/grant established |
| **CVL v1.1** | **CC BY-NC 3.0 Unported**, plus noncommercial research-purpose statement | **Not granted** | NC research; recognition/identification context | Adaptation allowed within NC license and publisher scope | **UNVERIFIED** | NC license-based sharing only, with attribution and underlying-text review; not commercial | Publication says no registration; public access; current archive availability not tested |
| **Washington / IAM-HistDB** | Custom **noncommercial research and teaching only** terms | **Not granted** | Confirmed research/training context, NC only | Research processing context; exact standalone grant UNVERIFIED | **UNVERIFIED** | **UNVERIFIED** | Publisher family requires registration; no commercial fee/grant established |
| **GNHK** | **CC BY 4.0**, official dataset README and LICENSE | **License-based confirmed commercial reuse** | Publisher recognition benchmarks/model-building purpose plus broad license; no separate commercial-ML clause | License-based adaptation, including crops, with notices | **UNVERIFIED as a named model-weight grant**; broader license must be assessed for the actual artifact | License-based sharing of covered dataset derivatives, with attribution/change notices | Publisher says free; original landing URL now redirects; current official archive route UNVERIFIED |
| **ClozeFormHandwriting** | **CC BY 4.0 explicitly covering images and annotations** | **License-based confirmed commercial reuse** | Explicit OCR training purpose plus broad license; consent scope still requires review | License-based adaptation | **UNVERIFIED as a named model-weight grant** | License-based sharing of covered derivatives, subject to attribution/privacy review | Public author repository, no fee/login gate observed for documentation; data not fetched |
| **Nexdata 30K English handwriting** | Paid proprietary agreement; exact name/full contract **UNVERIFIED** | Publisher explicitly advertises commercial licensing; Academix grant not acquired | Intended OCR/AI use; binding scope requires agreement | **UNVERIFIED until contract review** | **UNVERIFIED until contract review** | **UNVERIFIED until contract review**; do not assume raw/crop resale rights | Paid, quote/contact route; price not published on inspected product page |

For GNHK/ClozeFormHandwriting, an existing permissive copyright grant is stronger evidence than the other candidates' research-only access. It is not proof of all privacy, consent, third-party-text or weight-distribution questions. No additional dataset-specific prohibition is invented, and no missing permission is silently filled in.

## 4. Technical comparison

Counts are publisher/documentation counts, not new local image audits. No dataset was acquired or decoded for this comparison.

| Dataset | Size / language / handwriting | Line images and transcriptions | Writers and split evidence | Fit for student assignments / TrOCR |
|---|---|---|---|---|
| IAM | 1,539 pages; 13,353 lines; 115,320 words; modern English, 300-dpi grayscale | Ready line PNGs and transcription/metadata | 657 writers overall; official writer-independent task available | Strong technical match, but commercial dataset rights blocked |
| Bentham R0 | Historical English; local prepared set already audited: 433 pages, 11,413 crops; source had 11,473 annotated lines | PAGE geometry/transcripts; Academix crops already exist | Writer IDs unavailable locally; custom page split only | Easy reuse technically, weaker modern-domain fit; rights unresolved |
| CVL | 310 writers, seven repeated source texts: six English and one German; RGB scans | Word/XML and line geometry available; ready line-crop package not verified | Current v1.1 corrects writer ID; writer grouping possible; recognition writer-disjoint split not verified | Repeated vocabulary and punctuation omissions limit general assignment recognition |
| Washington | Provisional secondary description: 20 pages, 656 lines, 4,894 words; 18th-century English longhand | Binarized/normalized line and word images with transcripts reported | Two writers reported; writer-independent split not established | Tiny historical benchmark; poor main source for broad student handwriting |
| GNHK | 687 photographed documents; 9,363 lines; 39,026 text instances, including symbols; modern English | Word polygons/text and line IDs enable construction of line crops/labels | Diverse regions; maximum five images per writer reported; random page train/test split, writer isolation unverified | **Best main open candidate** for realistic English camera inputs; preparation needed |
| ClozeFormHandwriting | Public release: 3,000 English single-word classroom responses; difficult handwriting | Cropped word PNGs and filename/log labels; no sentence-line corpus | Style/group IDs are not established unique writer IDs; writer isolation unverified | Strong targeted robustness supplement; cannot train long-line context or general grading by itself |
| Nexdata | Publisher lists 30,276 images and 500,579 polygon boxes; English on A4/lined paper, multiple pen colors | JSON region transcripts/polygons; whether boxes are words or full lines is unverified | Writer count, demographic coverage and disjoint partitions unverified | Potentially strong product fit if contract, label granularity and writer metadata qualify |

GNHK is not a ready-made TrOCR line manifest. Future preparation would need correct geometric ordering, full-source grouping and validation; this research neither creates nor proposes reusing an unverified third-party repackaging. No line counts after filtering are claimed.

## 5. Candidate-specific evidence and qualifications

### 5.1 IAM Handwriting Database

**Publisher:** original IAM, University of Bern; current host HEIA-FR. [Official v3.0 source/terms](https://fki.tic.heia-fr.ch/databases/iam-handwriting-database) were available through indexed official-domain content; direct fetch failed.

Training/testing recognizers is an explicit purpose, limited to **noncommercial research**. No separate commercial grant or weight/redistribution clause was established. Registration is required; cite **Marti and Bunke (2002)**. Underlying LOB corpus text rights need consideration too.

The official writer-independent task uses **6,161 train / 900 validation-1 / 940 validation-2 / 1,861 test lines**, totaling **9,862**, not the complete corpus. Writers are separated by set. **Disposition: technically strong; obtain a separate commercial agreement before product training.**

### 5.2 Bentham Dataset R0

**Publisher/source:** Joan Andreu Sánchez, Universitat Politècnica de València; [Zenodo R0 v1, DOI 10.5281/zenodo.44519](https://zenodo.org/records/44519). The fetched record names the two archives and research availability but exposes no usable named license. The existing local investigation records the June 2014 internal README and unavailable archive-provenance checksum comparison.

**Separate asset terms:** [UCL Transcription Desk terms](https://transcribe-bentham.ucl.ac.uk/td/Terms_of_Use) and [official project credits](https://blogs.ucl.ac.uk/transcribe-bentham/credits/) name **CC BY-NC-ND 4.0 for service transcripts**; UCL's indexed terms direct image-reuse inquiries to administrators. Direct Terms access returned 403; official-domain indexed text was available. This is not proof that the R0 image/GT package has that same or another license.

Named-license applicability, crop redistribution, weight distribution and commercial training remain **UNVERIFIED**. No formal R0 attribution clause was confirmed; proposed scholarly credit is UCL/Transcribe Bentham, PRHLT-UPV and the dataset creator/DOI, pending mandatory wording. Source reading-order and historical-language differences also matter. **Disposition: retain current rights block.**

### 5.3 CVL Handwriting Database

**Publisher:** Computer Vision Lab, TU Wien. **Official terms:** [CVL database page](https://cvl.tuwien.ac.at/research/cvl-databases/an-off-line-database-for-writer-retrieval-writer-identification-and-word-spotting/), explicitly **Creative Commons Attribution-NonCommercial 3.0 Unported**, with noncommercial-research purpose wording. [License legal code](https://creativecommons.org/licenses/by-nc/3.0/legalcode).

Current page identifies **v1.1**, dated 12 September 2013, with **310 writers** after a writer-ID correction. It describes 27 writers providing seven texts and 283 providing five: **1,604 pages calculated from those counts**, not a downloaded file count. Cite **Kleber, Fiel, Diem and Sablatnig, ICDAR 2013**. The original [publisher-hosted paper](https://cvl.tuwien.ac.at/wp-content/uploads/2014/12/kleber-icdar132.pdf) reports 311 writers before correction and says access needs no registration; do not mix those versions.

The paper describes XML text-line/word hierarchy but no punctuation ground truth, and a Wikipedia source text with a separate **CC Attribution-ShareAlike** notice. That source's exact version/scope needs review; the database license does not erase underlying-text conditions. No model-specific weight distribution grant was found. **Disposition: obtain separate commercial rights, including relevant source text, before use.**

### 5.4 Washington Database

**Publisher:** IAM-HistDB research group, originally Bern, currently presented at HEIA-FR; manuscripts originate in the George Washington Papers at the Library of Congress.

**Authoritative umbrella terms:** [IAM Historical Document Database](https://fki.tic.heia-fr.ch/databases/iam-historical-document-database). Its official-domain indexed page specifically includes Washington and restricts these datasets to **noncommercial research and teaching**, requires registration and describes training/testing use. This is a custom purpose restriction, not an identified permissive SPDX license.

The detailed [Washington publisher URL](https://fki.tic.heia-fr.ch/databases/washington-database) timed out; its historical/nested variants were unavailable. The technical figures in section 4 are **provisional corroboration** from the [research redistributor's reproduced description](https://github.com/aimagelab/HWD/releases), not newly verified publisher statistics and not the basis of the licensing conclusion. Washington-specific citation wording and current standalone redistribution terms remain UNVERIFIED. Original manuscript availability does not license a packaged annotation set. **Disposition: commercial rights not granted by the confirmed family terms; weak domain/diversity fit anyway.**

### 5.5 GNHK — preferred open English candidate

**Publisher:** Goodnotes; authors Alex W. C. Lee, Jonathan Chung and Marco Lee (ICDAR 2021, with Goodnotes/AWS affiliations). **Dataset declaration:** [official README](https://github.com/GoodNotes/GNHK-dataset/blob/main/README.md). **Exact license:** [official CC BY 4.0 LICENSE](https://github.com/GoodNotes/GNHK-dataset/blob/main/LICENSE).

The README applies the grant to the **dataset**, not just software; no differing image/annotation license was disclosed. Confirm archive-level exceptions when acquisition is authorized. It requests the Lee–Chung–Lee paper citation, disclaims warranties and provides a personal-information removal contact. Retain license/creator notices and record preprocessing changes.

The [authors' paper, hosted by Amazon Science](https://cdn.amazon.science/38/fe/4c3105fb43129bf59cc0aadb5d78/gnhk-a-dataset-for-english-handwriting-in-the-wild.pdf) describes word quadrilaterals, `line_idx`, transcripts, and handwritten/printed flags. It reports four geographic regions, at most five images per writer, and a random **75/25 train/test** allocation; validation comes from training. **Actual writer count and writer-disjoint partitions are UNVERIFIED.** Existing line IDs support reconstruction, but pre-extracted line files are not established. Printed labels and `%math%`, `%SC%`, `%NA%` placeholders need an explicit policy; they are not full mathematical transcriptions.

**Access caveat:** the README's `https://goodnotes.com/gnhk/` route now resolves to the general homepage. The repository provides documentation, license and paper, not a verified working archive path. Publisher says free; current data access/registration details are UNVERIFIED. Contact authors for an official release/checksum before using mirrors. **Disposition: strongest documented open main candidate, conditional on access, provenance, privacy and weight-release review.**

### 5.6 ClozeFormHandwriting — targeted student-writing supplement

**Publisher:** author repository by Shrey Chandola and collaborators Manikandan Ravikiran/Rohit Saluja. [Official README](https://github.com/Shrey0900/ClozeFormHandwriting/blob/main/README.md) explicitly applies **CC BY 4.0 to images and annotations**; [LICENSE](https://github.com/Shrey0900/ClozeFormHandwriting/blob/main/LICENSE) confirms commercial adaptation/sharing terms. Cite **Chandola, Ravikiran and Saluja, AIED 2025**, and preserve required license notices.

The public corpus contains **3,000 correct single-word classroom responses**, excluding the other **2,000 incorrect responses** in the full benchmark. PNGs have filename/log transcripts; six style/group IDs do **not** establish six unique writers or writer-independent splits. No writer count or comprehensive minor/guardian/commercial-consent documentation was established. The repository explicitly describes OCR training use. It is public, with no observed documentation login/fee gate; data was not fetched.

An additionally identified Zenodo record, `10.5281/zenodo.18851954`, was not directly retrievable here; the author README/LICENSE are the primary evidence used. The reviewed README did not independently establish the consent scope described by third-party catalog summaries. **Disposition: useful word-level supplement after consent/privacy review; no sentence-level or general grading coverage, and no explicit weight-specific statement found.**

### 5.7 Nexdata 30K English Handwriting OCR — contract route

**Publisher/source:** [Nexdata official product page](https://www.nexdata.ai/datasets/ocr/1417). It explicitly markets a **paid dataset licensed for commercial use** and supplies the size/format figures in section 4. Its document-style English handwriting is potentially relevant, but box granularity, writer metadata and split isolation need confirmation.

No exact public data-license contract, weight-release clause, attribution rule, redistribution right or price was established. A quote and signed agreement must cover both images and JSON annotations, preprocessing, training, commercial deployment, continued rights in trained weights and any intended external weight/crop release. **Disposition: legitimate commercial-license lead, not rights already obtained by Academix.**

## 6. Technical suitability and preparation implications

These are recommendations/inferences from the documented formats, not results of training or new dataset inspection:

1. **Granularity:** TrOCR's current baseline expects one text line per image. IAM supplies that directly; Bentham is already prepared locally but rights-blocked. Washington supplies line data in the described package but is small/restricted. CVL needs careful XML-to-line preparation. GNHK needs line reconstruction from annotated geometry. ClozeFormHandwriting is only word-level. Nexdata's actual region granularity must be confirmed rather than assuming every box is a line.
2. **Leakage:** split by writer whenever supported, otherwise by source page/document and disclose the limitation. Never random-split crops from one page. Repeated passages in CVL and narrow target vocabularies in classroom word corpora also limit evidence of open-vocabulary generalization. Keep a clean held-out student-domain evaluation collection when rights permit one.
3. **Language:** the recommendation assumes English recognition. These sources do not establish coverage of Urdu, other scripts or all multilingual classroom content. Mixed-script requirements need another rights/suitability investigation, not an English-data accuracy claim.
4. **Image domain:** photographed modern writing is a closer qualitative match to mobile submissions than clean historical line benchmarks. That is a domain-fit inference, not measured superiority. Test independently on representative, consented assignment images before product claims.
5. **Text versus grading:** math placeholders, single-word correct-answer samples and recognition transcripts are not grading rubrics. Incorrect answers, cross-outs, formulas, diagrams and layout require explicit handling; none of these corpora alone establishes safe assignment grading.
6. **Preprocessing:** future RGB conversion, orientation/line extraction, target normalization and label masking should match the chosen TrOCR pipeline and be versioned in new artifacts. Do not silently rewrite reference spelling or derive labels from expected correct answers rather than the ink actually present.
7. **CPU feasibility:** changing data does not resolve the existing ~16-GB CPU machine's memory/time limits, missing training dependency or decoder/loss blockers. Preserve the prior readiness/investigation reports and settle those issues separately. No new model-load or training benchmark was appropriate for this documentation task.

## 7. Best candidate for Academix and the next decision

**Choose GNHK as the first open-dataset qualification target**, rather than clearing IAM/CVL/Washington by assumption or proceeding with Bentham's unverified rights. Obtain an official accessible copy's provenance and retained license documentation first, under later authorization. Confirm annotation exceptions, personal-data handling, writer grouping and a documented decision about trained-model distribution. This recommendation rests on affirmative publisher licensing plus task/domain fit, not a guarantee that every product right has been resolved.

**Add ClozeFormHandwriting only as a focused, separately reviewed supplement**, not the primary line corpus or proof of grading quality. Its explicit image/annotation grant is valuable; student-consent scope, narrow vocabulary and missing writer identity remain relevant.

If a supported commercial agreement and broader assignment-style coverage are priorities, investigate **Nexdata's contract** or commission an appropriately consented collection. Require written coverage of weights and derivatives; a sales claim that data is commercial does not supply the omitted terms. No registration, contact, purchase or collection was performed here.

No dataset is recommended as **unconditionally commercially safe**. GNHK and ClozeFormHandwriting have verified permissive dataset copyright declarations; several additional questions remain. A separate weight-specific clarification can reduce uncertainty without pretending that the broad CC adaptation grant is meaningless or that every use of weights is automatically an adaptation.

## 8. Permissions and prerequisites before any training

For the selected release, retain a compact rights register with publisher, release/version/hash, acquisition path/date, asset-specific terms, notices and commercial-purpose decision. Resolve:

| Item | Required evidence / decision |
|---|---|
| Images | Authorized source and a grant covering intended commercial copying/preprocessing/training |
| Text/transcriptions | License and provenance for the underlying text and the transcriptions; separate from image rights where needed |
| Geometry/annotations | Explicit scope of the dataset grant or separate annotation terms |
| Trained weights | Document whether the applicable rights cover the intended model artifact and release; seek express publisher/contract clarification where unverified. Distinguish private training, SaaS deployment, customer delivery and public weight publication. |
| Processed crops | Permission and obligations for internal preparation versus public redistribution; preserve attribution and change notices where required |
| Personal/student data | Consent/release, permitted commercial scope, minors/guardian requirements if relevant, de-identification and retention/removal responsibilities |
| Vendor contract | Affiliates/contractors, training/evaluation, ownership or usage rights in weights, deployment/distribution, post-termination retention, crop redistribution and any limits/fees |
| Attribution | Creator/source/license link, supplied notices, modification log and requested academic citation; include a dataset provenance section in any eventual model card |
| Base model | Retain and review the existing checkpoint's own license/notices; its use does not transfer rights to the source datasets |
| Engineering | Resolve the previous token-ID/loss/API blockers and RAM feasibility before a separately authorized implementation/smoke test |

For **IAM, CVL or Washington**, obtain an explicit commercial exception/license from the relevant rights holders, including text/annotations and intended weight distribution. For **Bentham**, establish the exact release's rights and reconcile source-image/transcript scope before training. For **GNHK/ClozeFormHandwriting**, preserve the affirmative CC BY grant and complete the remaining artifact/privacy/provenance review. No permission email was sent on the user's behalf.

A future experiment must use training data only for updates, validation only for selection, and a final held-out test after choices are locked. This report does not authorize dataset acquisition, preparation or training.

## 9. Source quality, access limits and work performed

**Primary sources used:** official IAM/IAM-HistDB pages (indexed official content when direct fetch failed), TU Wien's current CVL page and original paper, the Bentham publisher deposit/UCL service terms, Goodnotes' repository/LICENSE and original authors' paper, the ClozeFormHandwriting authors' README/LICENSE, the Nexdata product page, and Creative Commons legal texts.

- Direct IAM/IAM-HistDB page fetches returned 502/timeouts; official-domain indexed content supplied the published terms and IAM counts/task table. This is distinguished from a live successful origin fetch.
- The Washington detail page/legacy variants were unavailable. Its provisional technical counts are the sole secondary-source exception, explicitly labeled; the **license conclusion uses official IAM-HistDB family terms**, not the mirror.
- Bentham deposit Rights rendering did not identify a package license. UCL direct Terms fetch returned 403, but its official-domain indexed terms/credits were available. The standalone R0 README could not be retrieved in this research pass; prior local investigation remains supporting context, not newly downloaded license evidence.
- GNHK's original landing URL redirects to the general Goodnotes site. A working official data archive and file-level exceptions were not verified.
- GitHub README/LICENSE documents are official author/publisher statements, not proof of every contributor's underlying authority. No image samples, archives, mirrors or dataset subsets were downloaded to inspect/validate claims.
- HTR-United, survey tables, third-party repackagings and catalog listings were discovery leads only, except the explicitly marked Washington size corroboration. Unretrievable additional leads were not promoted into verified recommendations.
- Access/price details are limited to the documents inspected; no account was registered, no paid terms accepted and no numerical price invented.

### Official source and license register

All links checked/attempted **2026-11-16**:

1. IAM: https://fki.tic.heia-fr.ch/databases/iam-handwriting-database — dataset, task, registration and terms.
2. IAM-HistDB/Washington family: https://fki.tic.heia-fr.ch/databases/iam-historical-document-database — registration and NC research/teaching terms.
3. Washington detail (unavailable): https://fki.tic.heia-fr.ch/databases/washington-database — current advertised detail route; older nested/Bern variants also unavailable.
4. Bentham publisher: https://zenodo.org/records/44519 — R0 v1 / DOI 10.5281/zenodo.44519.
5. UCL service terms: https://transcribe-bentham.ucl.ac.uk/td/Terms_of_Use ; credits: https://blogs.ucl.ac.uk/transcribe-bentham/credits/ — transcript policy/image distinction, indexed content.
6. CVL: https://cvl.tuwien.ac.at/research/cvl-databases/an-off-line-database-for-writer-retrieval-writer-identification-and-word-spotting/ — current v1.1 and license.
7. CVL original paper: https://cvl.tuwien.ac.at/wp-content/uploads/2014/12/kleber-icdar132.pdf — original version, geometry, punctuation and access.
8. CVL license: https://creativecommons.org/licenses/by-nc/3.0/legalcode — Attribution-NonCommercial 3.0 Unported.
9. GNHK: https://github.com/GoodNotes/GNHK-dataset/blob/main/README.md ; https://github.com/GoodNotes/GNHK-dataset/blob/main/LICENSE — dataset CC BY 4.0 and author notice.
10. GNHK author paper: https://cdn.amazon.science/38/fe/4c3105fb43129bf59cc0aadb5d78/gnhk-a-dataset-for-english-handwriting-in-the-wild.pdf — technical format/counts/split.
11. ClozeFormHandwriting: https://github.com/Shrey0900/ClozeFormHandwriting/blob/main/README.md ; https://github.com/Shrey0900/ClozeFormHandwriting/blob/main/LICENSE — explicit image/annotation grant and format.
12. Nexdata: https://www.nexdata.ai/datasets/ocr/1417 — commercial offering/specifications, not a signed license.
13. General CC BY 4.0 legal code: https://creativecommons.org/licenses/by/4.0/legalcode.en — grants and conditions.

### Local scope and verification

Read existing `evaluation/TROCR_BLOCKERS_INVESTIGATION.md` for project context. Before/after hashes verified unchanged for that report, `evaluation/TROCR_FINE_TUNING_READINESS.md`, and the three Bentham split manifests. No prediction/model/image analysis or tests requiring those assets were run. Dataset/model tests were unnecessary for a research-document change; only document completeness/link and preservation checks were performed.

**Only created project file: `evaluation/HANDWRITING_DATASET_COMPARISON.md`.** Existing datasets, manifests, predictions, checkpoints, backend and Flutter code were left unchanged. No training, fine-tuning, package installation or dataset download occurred.
