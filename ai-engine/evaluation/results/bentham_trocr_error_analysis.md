# Bentham TrOCR validation error analysis

Source: `bentham_trocr_validation_predictions.jsonl`; SHA-256: `7dd1b4f6520fb4f14e2b4c7465b9f01c7358e453a1d4a25e2b3aae170ee5a98a`.

Analyzed **1,197 samples** across **43 pages**. CER **17.3568%**, WER **41.3574%**, exact match **5.9315%** (71/1197); failures **0**.

## Reproducible method

Run from `ai-engine`: `..\.venv\Scripts\python.exe -m evaluation.analyze_trocr_errors`.

Normalization: Unicode NFC, collapse/trim Unicode whitespace; preserve case, punctuation and accents. Raw text is retained unchanged in each example’s `source_record`.

- **alignment:** Per-sample unit-cost Levenshtein; backtrace ties: match, substitution, deletion, insertion. Minimum alignments may be ambiguous; counts describe this deterministic alignment.
- **indices:** Zero-based input sample order and normalized character/word indices; absent edit units are null.
- **rates:** Corpus CER/WER use total errors / max(1, total reference units), never averages of line rates. Per-line and length-bin zero-reference denominators are also max(1, reference units). Rates may exceed 1.
- **failures:** Retained, scored as empty predictions and never exact matches, matching the baseline evaluator.
- **word_errors:** Whitespace tokenization; case and punctuation retained. Missing/extra words are alignment deletions/insertions, not semantic diagnoses.
- **spelling_candidates:** Alphabetic word substitutions only; both lengths >=3, casefolded strings differ, Levenshtein <=2 and <=40% of longer length. Heuristic near-spelling errors, not dictionary-verified; excludes case-only changes.
- **ranking:** Top 20 per-line CER/WER, descending; ties by input order. Short references can yield extreme rates.
- **examples:** One example row per input, with the complete unchanged source_record and all edit operations; multiple category tags may apply.
- **scope:** Saved validation predictions only. No test predictions, datasets, image crops or model weights read. No tuning or causal claims about handwriting quality.

## Observed findings

- Character substitutions account for 6,004/9,402 character edits.
- There are 754 inserted space characters. Of 930 inserted word tokens, 168 are punctuation-only tokens. Tokenization and punctuation contribute to WER; inserted tokens are not all extra lexical words.
- 91 word substitutions differ only in case; case is intentionally preserved in scoring.
- 121 samples contain aligned word deletions, 629 contain aligned insertions, and 287 contain near-spelling candidates. Categories overlap.
- References of 1?10 characters (161 samples) have CER 73.28% and WER 108.05%; 51?75 characters (653 samples) have CER 16.43% and WER 39.17%. Small reference denominators amplify short-line rates; this comparison does not establish a causal length effect.

Empty normalized references: 0; empty normalized predictions: 0.

## Edit operation counts

| Unit | Substitutions | Deletions | Insertions |
|---|---:|---:|---:|
| character | 6004 | 963 | 2435 |
| word | 3078 | 160 | 930 |

## Common character errors

### Substitutions

| Reference unit | Prediction unit | Count |
|---|---|---:|
| "t" | "l" | 89 |
| "e" | "o" | 87 |
| "e" | "a" | 83 |
| "r" | "n" | 74 |
| "o" | "e" | 72 |
| "b" | "h" | 70 |
| "n" | "m" | 68 |
| "s" | "e" | 60 |
| "e" | "s" | 58 |
| "n" | "s" | 58 |
| "o" | "a" | 56 |
| "a" | "e" | 54 |

### Deletions

| Reference unit | Prediction unit | Count |
|---|---|---:|
| " " | null | 81 |
| "s" | null | 80 |
| "e" | null | 68 |
| "-" | null | 63 |
| "o" | null | 58 |
| "t" | null | 48 |
| "c" | null | 44 |
| "i" | null | 41 |
| "n" | null | 35 |
| ":" | null | 30 |
| "a" | null | 27 |
| "r" | null | 27 |

### Insertions

| Reference unit | Prediction unit | Count |
|---|---|---:|
| null | " " | 754 |
| null | "s" | 180 |
| null | "e" | 177 |
| null | "r" | 167 |
| null | "i" | 113 |
| null | "t" | 109 |
| null | "a" | 97 |
| null | "c" | 79 |
| null | "n" | 78 |
| null | "o" | 68 |
| null | "." | 65 |
| null | "l" | 59 |


## Common word errors

### Substitutions

| Reference unit | Prediction unit | Count |
|---|---|---:|
| "_" | "-" | 24 |
| "be" | "he" | 23 |
| "be" | "her" | 16 |
| "C" | "c." | 14 |
| "The" | "the" | 9 |
| "at" | "as" | 9 |
| "said" | "mid" | 8 |
| "he" | "her" | 7 |
| "in" | "is" | 7 |
| "3." | "." | 6 |
| "_" | "." | 6 |
| "bad" | "had" | 6 |

### Deletions

| Reference unit | Prediction unit | Count |
|---|---|---:|
| "be" | null | 8 |
| "If" | null | 4 |
| "_" | null | 4 |
| "-" | null | 3 |
| "&" | null | 2 |
| "." | null | 2 |
| "Mildmay" | null | 2 |
| "No" | null | 2 |
| "Of" | null | 2 |
| "a" | null | 2 |
| "an" | null | 2 |
| "for" | null | 2 |

### Insertions

| Reference unit | Prediction unit | Count |
|---|---|---:|
| null | "\"" | 78 |
| null | "," | 33 |
| null | "." | 29 |
| null | "of" | 12 |
| null | "a" | 10 |
| null | "it" | 10 |
| null | "2" | 8 |
| null | "3" | 7 |
| null | "man" | 7 |
| null | "I" | 6 |
| null | "that" | 6 |
| null | "him" | 5 |


## Error rates by reference length (characters)

| Length | Samples | Reference chars | Char edits | CER | Reference words | Word edits | WER | Exact matches |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | n/a | 0 | 0 | n/a | 0 |
| 1-10 | 161 | 595 | 436 | 73.28% | 174 | 188 | 108.05% | 26 |
| 11-25 | 73 | 1214 | 374 | 30.81% | 205 | 189 | 92.20% | 3 |
| 26-50 | 304 | 13169 | 2131 | 16.18% | 2444 | 944 | 38.63% | 20 |
| 51-75 | 653 | 38720 | 6363 | 16.43% | 7174 | 2810 | 39.17% | 22 |
| 76-100 | 6 | 471 | 98 | 20.81% | 81 | 37 | 45.68% | 0 |
| 101+ | 0 | 0 | 0 | n/a | 0 | 0 | n/a | 0 |

## Error rates by reference length (words)

| Length | Samples | Reference chars | Char edits | CER | Reference words | Word edits | WER | Exact matches |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | n/a | 0 | 0 | n/a | 0 |
| 1-3 | 213 | 1395 | 689 | 49.39% | 287 | 309 | 107.67% | 28 |
| 4-7 | 132 | 4760 | 1040 | 21.85% | 764 | 443 | 57.98% | 4 |
| 8-12 | 733 | 40344 | 6427 | 15.93% | 7413 | 2823 | 38.08% | 38 |
| 13+ | 119 | 7670 | 1246 | 16.25% | 1614 | 593 | 36.74% | 1 |

## Missing-word examples (121 samples)

- Sample 8: `line_images/071_018_003__r4__r119__r001_l009_g000567.png`
  - Raw reference: "2. The obligation you are under to assist a fellow creature"
  - Raw prediction: "2 . The obligation you are render to affect a fellow-mealware"
  - Aligned edits: "fellow" → null
- Sample 21: `line_images/071_018_003__r4__r106__r001_l022_g000580.png`
  - Raw reference: "injury, an act of unlawful &lt;gap/&gt; an act of kid="
  - Raw prediction: "injury , an undergraduate conferences-maned effitted :"
  - Aligned edits: "injury," → null; "an" → null; "act" → null
- Sample 55: `line_images/071_044_003__r4__r37__r001_l002_g000884.png`
  - Raw reference: "course to inform the owners. &lt;gap/&gt; to &lt;gap/&gt; if &lt;gap/&gt;&lt;gap/&gt;"
  - Raw prediction: "corrects to inform the airners ( #"
  - Aligned edits: "owners." → null; "&lt;gap/&gt;" → null; "to" → null
- Sample 76: `line_images/071_044_003__r4__r106__r001_l026_g000908.png`
  - Raw reference: "fact of its being taken. As if a man going in to a "
  - Raw prediction: "fact of its being taken . It's if a man going into a"
  - Aligned edits: "in" → null
- Sample 77: `line_images/071_044_003__r4__r105__r001_l027_g000909.png`
  - Raw reference: "whose possession or custody the thing is to know the"
  - Raw prediction: "whoseoglobin or custody the thing is to know the"
  - Aligned edits: "whose" → null

## Extra-word examples (629 samples)

- Sample 2: `line_images/071_018_003__r4__r125__r001_l003_g000561.png`
  - Raw reference: "special ground of justification (See Fit: [Justifications]),"
  - Raw prediction: "special ground of disabilities like the Washington lawyers"
  - Aligned edits: null → "disabilities"
- Sample 3: `line_images/071_018_003__r4__r49__r001_l004_g000562.png`
  - Raw reference: "assistance on such an occasion, unless when he had a"
  - Raw prediction: "guillance on week an occasion , and the whigs he had a"
  - Aligned edits: null → "occasion"; null → ","
- Sample 5: `line_images/071_018_003__r4__r122__r001_l006_g000564.png`
  - Raw reference: "him."
  - Raw prediction: "hein ."
  - Aligned edits: null → "hein"
- Sample 6: `line_images/071_018_003__r4__r121__r001_l007_g000565.png`
  - Raw reference: "threatens him and the less trouble it would cost to save"
  - Raw prediction: "threaters him and then left traveller , it would cost to face"
  - Aligned edits: null → "then"
- Sample 8: `line_images/071_018_003__r4__r119__r001_l009_g000567.png`
  - Raw reference: "2. The obligation you are under to assist a fellow creature"
  - Raw prediction: "2 . The obligation you are render to affect a fellow-mealware"
  - Aligned edits: null → "2"

## Near-spelling substitution candidates (287 samples)

- Sample 1: `line_images/071_018_003__r4__r126__r001_l002_g000560.png`
  - Raw reference: "if his forbearance proceed from any other motive than"
  - Raw prediction: "if his fotucarance process from any other motive than"
  - Aligned edits: "proceed" → "process"
- Sample 4: `line_images/071_018_003__r4__r47__r001_l005_g000563.png`
  - Raw reference: "3. A man is always punishable for withholding his "
  - Raw prediction: "is not more in always punishable for earth-holding has"
  - Aligned edits: "his" → "has"
- Sample 6: `line_images/071_018_003__r4__r121__r001_l007_g000565.png`
  - Raw reference: "threatens him and the less trouble it would cost to save"
  - Raw prediction: "threaters him and then left traveller , it would cost to face"
  - Aligned edits: "threatens" → "threaters"
- Sample 8: `line_images/071_018_003__r4__r119__r001_l009_g000567.png`
  - Raw reference: "2. The obligation you are under to assist a fellow creature"
  - Raw prediction: "2 . The obligation you are render to affect a fellow-mealware"
  - Aligned edits: "under" → "render"
- Sample 17: `line_images/071_018_003__r4__r110__r001_l018_g000576.png`
  - Raw reference: "If any farther mischief that is not personal be occasioned"
  - Raw prediction: "If any further mischief that is not personal he remained"
  - Aligned edits: "farther" → "further"

## Exact-match examples (71 samples)

- Sample 0: `line_images/071_018_003__r4__r127__r001_l001_g000559.png`
  - Raw reference: "that"
  - Raw prediction: "that"
- Sample 7: `line_images/071_018_003__r4__r120__r001_l008_g000566.png`
  - Raw reference: "is the stronger the greater the danger appears to be which"
  - Raw prediction: "is the stronger the greater the danger appears to be which"
- Sample 48: `line_images/071_021_002__r2__r307__r001_l022_g000608.png`
  - Raw reference: "the"
  - Raw prediction: "the"
- Sample 53: `line_images/071_021_002__r1__r305__r004_l001_g000613.png`
  - Raw reference: "18."
  - Raw prediction: "18."
- Sample 58: `line_images/071_044_003__r4__r125__r001_l006_g000888.png`
  - Raw reference: "one who has no reason to think himself already"
  - Raw prediction: "one who has no reason to think himself already"

## Highest per-line CER

| Sample | Crop | Ref chars | Ref words | CER | WER |
|---:|---|---:|---:|---:|---:|
| 52 | line_images/071_021_002__r4__r6__r003_l001_g000612.png | 1 | 1 | 500.00% | 200.00% |
| 106 | line_images/071_059_003__r1__r100__r004_l001_g001023.png | 1 | 1 | 400.00% | 100.00% |
| 677 | line_images/115_012_001__r1__r355__r001_l003_g006805.png | 1 | 1 | 300.00% | 100.00% |
| 1036 | line_images/116_287_001__r1__r34__r001_l007_g009918.png | 1 | 1 | 300.00% | 100.00% |
| 1062 | line_images/116_287_001__r4__r129__r003_l001_g009944.png | 1 | 1 | 300.00% | 100.00% |
| 54 | line_images/071_044_003__r4__r38__r001_l001_g000883.png | 6 | 1 | 250.00% | 100.00% |
| 26 | line_images/071_018_003__r2__r101__r003_l001_g000585.png | 1 | 1 | 200.00% | 100.00% |
| 83 | line_images/071_044_003__r2__r101__r004_l001_g000915.png | 1 | 1 | 200.00% | 100.00% |
| 128 | line_images/071_105_003__r5__r11__r003_l001_g001241.png | 1 | 1 | 200.00% | 100.00% |
| 151 | line_images/071_106_002__r4__r8__r003_l001_g001289.png | 1 | 1 | 200.00% | 100.00% |
| 204 | line_images/071_151_003__r4__r124__r003_l001_g002108.png | 1 | 1 | 200.00% | 100.00% |
| 227 | line_images/071_164_002__r4__r13__r003_l001_g002445.png | 1 | 1 | 200.00% | 100.00% |
| 229 | line_images/071_169_002__r5__r41__r001_l001_g002634.png | 3 | 1 | 200.00% | 200.00% |
| 254 | line_images/071_169_002__r2__r101__r004_l001_g002659.png | 1 | 1 | 200.00% | 100.00% |
| 278 | line_images/071_180_004__r2__r101__r003_l001_g002740.png | 1 | 1 | 200.00% | 100.00% |
| 302 | line_images/071_182_002__r1__r100__r004_l001_g002882.png | 1 | 1 | 200.00% | 100.00% |
| 329 | line_images/071_201_001__r2__r101__r003_l001_g003330.png | 1 | 1 | 200.00% | 100.00% |
| 330 | line_images/071_201_001__r1__r100__r004_l001_g003331.png | 1 | 1 | 200.00% | 100.00% |
| 356 | line_images/072_050_003__r4__r7__r004_l001_g003664.png | 1 | 1 | 200.00% | 100.00% |
| 387 | line_images/072_051_003__r3__r7__r003_l001_g003724.png | 1 | 1 | 200.00% | 100.00% |

- Sample 52 raw reference: "G"; raw prediction: "cis ."
- Sample 106 raw reference: "C"; raw prediction: "inc."
- Sample 677 raw reference: "£ "; raw prediction: "out"

## Highest per-line WER

| Sample | Crop | Ref chars | Ref words | CER | WER |
|---:|---|---:|---:|---:|---:|
| 15 | line_images/071_018_003__r4__r40__r001_l016_g000574.png | 7 | 1 | 100.00% | 300.00% |
| 697 | line_images/115_012_001__r1__r302__r001_l023_g006825.png | 18 | 1 | 33.33% | 300.00% |
| 328 | line_images/071_201_001__r3__r102__r002_l001_g003329.png | 17 | 2 | 52.94% | 250.00% |
| 5 | line_images/071_018_003__r4__r122__r001_l006_g000564.png | 4 | 1 | 75.00% | 200.00% |
| 9 | line_images/071_018_003__r4__r118__r001_l010_g000568.png | 10 | 1 | 30.00% | 200.00% |
| 13 | line_images/071_018_003__r4__r42__r001_l014_g000572.png | 10 | 1 | 60.00% | 200.00% |
| 27 | line_images/071_018_003__r1__r100__r004_l001_g000586.png | 2 | 1 | 50.00% | 200.00% |
| 28 | line_images/071_021_002__r2__r266__r001_l001_g000587.png | 6 | 1 | 116.67% | 200.00% |
| 52 | line_images/071_021_002__r4__r6__r003_l001_g000612.png | 1 | 1 | 500.00% | 200.00% |
| 67 | line_images/071_044_003__r4__l34__r001_l016_g000898.png | 9 | 1 | 177.78% | 200.00% |
| 96 | line_images/071_059_003__r4__r39__r001_l013_g001013.png | 4 | 1 | 100.00% | 200.00% |
| 134 | line_images/071_106_002__r3__r192__r001_l005_g001272.png | 8 | 1 | 37.50% | 200.00% |
| 145 | line_images/071_106_002__r3__r64__r001_l016_g001283.png | 11 | 1 | 9.09% | 200.00% |
| 152 | line_images/071_106_002__r1__r6__r004_l001_g001290.png | 2 | 1 | 50.00% | 200.00% |
| 160 | line_images/071_120_002__r6__r120__r001_l008_g001556.png | 11 | 1 | 36.36% | 200.00% |
| 168 | line_images/071_120_002__r5__r46__r002_l008_g001564.png | 11 | 1 | 45.45% | 200.00% |
| 172 | line_images/071_120_002__r5__r34__r002_l012_g001568.png | 7 | 1 | 42.86% | 200.00% |
| 174 | line_images/071_120_002__r5__r106__r002_l014_g001570.png | 11 | 1 | 54.55% | 200.00% |
| 180 | line_images/071_151_003__r3__r123__r001_l001_g002084.png | 4 | 1 | 125.00% | 200.00% |
| 229 | line_images/071_169_002__r5__r41__r001_l001_g002634.png | 3 | 1 | 200.00% | 200.00% |

- Sample 15 raw reference: ":fence."; raw prediction: "\" jersey ."
- Sample 697 raw reference: "Annuity-Societies. "; raw prediction: "Annuity policies ."
- Sample 328 raw reference: "Of State-Tumults."; raw prediction: "of Male . Tumulus ."

All exact matches, ranked samples and category memberships are enumerated in the JSON report; the examples JSONL contains every input sample, raw text, per-line rates and alignments. Histograms in JSON are complete; Markdown shows the 12 most frequent edits per operation. These are descriptive validation findings, not evidence of causes or model changes.
