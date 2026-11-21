"""Reproducible, validation-only TrOCR error analysis; no model or image access.

Run: ..\\.venv\\Scripts\\python.exe -m evaluation.analyze_trocr_errors
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from evaluation.evaluate_trocr_baseline import (
    NORMALIZATION, RESULTS, calculate_metrics, edit_distance, normalize_text,
)

INPUT = RESULTS / 'bentham_trocr_validation_predictions.jsonl'
CHAR_BINS = [('0', 0, 0), ('1-10', 1, 10), ('11-25', 11, 25),
             ('26-50', 26, 50), ('51-75', 51, 75), ('76-100', 76, 100),
             ('101+', 101, None)]
WORD_BINS = [('0', 0, 0), ('1-3', 1, 3), ('4-7', 4, 7),
             ('8-12', 8, 12), ('13+', 13, None)]
OPERATIONS = ('substitution', 'deletion', 'insertion')


def align_errors(reference, prediction) -> list[dict]:
    """Minimum unit-cost edits; ties: match, substitution, deletion, insertion.

    Positions are zero-based normalized character/word indices. Insertion
    reference_index and deletion prediction_index denote boundaries. None means
    no unit on that side. Alignment is deterministic, not linguistically unique.
    """
    n, m = len(reference), len(prediction)
    costs = [list(range(m + 1))] + [[i] + [0] * m for i in range(1, n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            costs[i][j] = min(costs[i-1][j-1] + (reference[i-1] != prediction[j-1]),
                              costs[i-1][j] + 1, costs[i][j-1] + 1)
    edits = []
    i, j = n, m
    while i or j:
        if i and j and reference[i-1] == prediction[j-1] and costs[i][j] == costs[i-1][j-1]:
            i, j = i-1, j-1
            continue
        if i and j and costs[i][j] == costs[i-1][j-1] + 1:
            i, j = i-1, j-1
            operation, expected, actual = 'substitution', reference[i], prediction[j]
        elif i and costs[i][j] == costs[i-1][j] + 1:
            i -= 1
            operation, expected, actual = 'deletion', reference[i], None
        else:
            j -= 1
            operation, expected, actual = 'insertion', None, prediction[j]
        edits.append({'operation': operation, 'reference': expected, 'prediction': actual,
                      'reference_index': i, 'prediction_index': j})
    return list(reversed(edits))


def spelling_candidate(edit: dict) -> bool:
    """Near alphabetic substitution, not a dictionary-verified spelling diagnosis."""
    reference, prediction = edit['reference'], edit['prediction']
    if edit['operation'] != 'substitution' or not reference.isalpha() or not prediction.isalpha():
        return False
    if reference.casefold() == prediction.casefold() or min(len(reference), len(prediction)) < 3:
        return False
    distance = edit_distance(reference.casefold(), prediction.casefold())
    return distance <= 2 and distance / max(len(reference), len(prediction)) <= .4


def load_predictions(path: Path) -> list[dict]:
    rows, seen = [], set()
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f'Invalid prediction JSON on line {number}') from exc
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in
                                          ('page_id', 'crop_relative_path', 'reference_raw')):
            raise ValueError(f'Invalid identifiers/reference on line {number}')
        if not row['page_id'] or not row['crop_relative_path']:
            raise ValueError(f'Empty identifier on line {number}')
        if row.get('status') not in ('ok', 'failed'):
            raise ValueError(f'Invalid prediction status on line {number}')
        if row['status'] == 'ok' and not isinstance(row.get('prediction_raw'), str):
            raise ValueError(f'Missing successful prediction on line {number}')
        if row['status'] == 'failed' and (row.get('prediction_raw') is not None or
                                        not isinstance(row.get('error'), str) or
                                        not row.get('failure_stage')):
            raise ValueError(f'Invalid failed prediction on line {number}')
        for field, raw in [('reference_normalized', row['reference_raw']),
                           ('prediction_normalized', row.get('prediction_raw') or '')]:
            if field in row and row[field] != normalize_text(raw):
                raise ValueError(f'Inconsistent {field} on line {number}')
        key = row['crop_relative_path'].replace('\\', '/')
        if key in seen:
            raise ValueError(f'Duplicate crop on line {number}: {key}')
        seen.add(key)
        rows.append(row)
    if not rows:
        raise ValueError('Prediction input is empty')
    return rows


def _histogram(counter: Counter) -> list[dict]:
    return [{'reference': reference, 'prediction': prediction, 'count': count}
            for (reference, prediction), count in sorted(
                counter.items(), key=lambda item: (-item[1], item[0][0] or '', item[0][1] or ''))]


def _length_breakdown(rows: list[dict], bins: list[tuple], *, words: bool) -> list[dict]:
    output = []
    for label, minimum, maximum in bins:
        selected = []
        for row in rows:
            text = normalize_text(row['reference_raw'])
            length = len(text.split()) if words else len(text)
            if length >= minimum and (maximum is None or length <= maximum):
                selected.append(row)
        metrics = calculate_metrics(selected)
        output.append({'bin': label, 'minimum': minimum, 'maximum': maximum, **metrics})
    return output


def analyze(rows: list[dict], *, top_n: int = 20) -> tuple[dict, list[dict]]:
    if not rows or top_n < 1:
        raise ValueError('Analysis requires samples and positive top_n')
    histograms = {unit: {operation: Counter() for operation in OPERATIONS}
                  for unit in ('character', 'word')}
    examples = []
    for index, row in enumerate(rows):
        reference = normalize_text(row['reference_raw'])
        prediction = normalize_text(row['prediction_raw']) if row['status'] == 'ok' else ''
        character_edits = align_errors(reference, prediction)
        word_edits = align_errors(reference.split(), prediction.split())
        for unit, edits in [('character', character_edits), ('word', word_edits)]:
            for edit in edits:
                histograms[unit][edit['operation']][(edit['reference'], edit['prediction'])] += 1
        candidates = [edit for edit in word_edits if spelling_candidate(edit)]
        exact = row['status'] == 'ok' and reference == prediction
        categories = []
        if exact:
            categories.append('exact_match')
        if any(edit['operation'] == 'deletion' for edit in word_edits):
            categories.append('missing_words')
        if any(edit['operation'] == 'insertion' for edit in word_edits):
            categories.append('extra_words')
        if candidates:
            categories.append('spelling_candidates')
        if row['status'] != 'ok':
            categories.append('failed')
        examples.append({
            'sample_index': index, 'source_record': row, 'categories': categories,
            'reference_normalized': reference, 'prediction_normalized': prediction,
            'reference_characters': len(reference), 'reference_words': len(reference.split()),
            'character_errors': len(character_edits), 'word_errors': len(word_edits),
            'cer': len(character_edits) / max(1, len(reference)),
            'wer': len(word_edits) / max(1, len(reference.split())),
            'exact_match': exact, 'character_edits': character_edits,
            'word_edits': word_edits, 'spelling_candidates': candidates,
        })
    metrics = calculate_metrics(rows)
    assert sum(sample['character_errors'] for sample in examples) == metrics['character_errors']
    assert sum(sample['word_errors'] for sample in examples) == metrics['word_errors']
    rankings = {}
    for metric in ('cer', 'wer'):
        ranked = sorted(examples, key=lambda sample: (-sample[metric], sample['sample_index']))[:top_n]
        rankings[f'highest_{metric}'] = [sample['sample_index'] for sample in ranked]
        for sample in ranked:
            sample['categories'].append(f'high_{metric}')
    category_indices = {category: [sample['sample_index'] for sample in examples
                                   if category in sample['categories']]
                        for category in ('exact_match', 'missing_words', 'extra_words',
                                         'spelling_candidates', 'failed')}
    punctuation_insertions = sum(
        count for (_, prediction), count in histograms['word']['insertion'].items()
        if all(not character.isalnum() for character in prediction)
    )
    summary = {
        'metrics': metrics, 'normalization': NORMALIZATION,
        'methodology': {
            'alignment': 'Per-sample unit-cost Levenshtein; backtrace ties: match, substitution, deletion, insertion. Minimum alignments may be ambiguous; counts describe this deterministic alignment.',
            'indices': 'Zero-based input sample order and normalized character/word indices; absent edit units are null.',
            'rates': 'Corpus CER/WER use total errors / max(1, total reference units), never averages of line rates. Per-line and length-bin zero-reference denominators are also max(1, reference units). Rates may exceed 1.',
            'failures': 'Retained, scored as empty predictions and never exact matches, matching the baseline evaluator.',
            'word_errors': 'Whitespace tokenization; case and punctuation retained. Missing/extra words are alignment deletions/insertions, not semantic diagnoses.',
            'spelling_candidates': 'Alphabetic word substitutions only; both lengths >=3, casefolded strings differ, Levenshtein <=2 and <=40% of longer length. Heuristic near-spelling errors, not dictionary-verified; excludes case-only changes.',
            'ranking': f'Top {top_n} per-line CER/WER, descending; ties by input order. Short references can yield extreme rates.',
            'examples': 'One example row per input, with the complete unchanged source_record and all edit operations; multiple category tags may apply.',
            'scope': 'Saved validation predictions only. No test predictions, datasets, image crops or model weights read. No tuning or causal claims about handwriting quality.',
        },
        'diagnostics': {
            'inserted_space_characters': histograms['character']['insertion'][(None, ' ')],
            'punctuation_only_word_insertions': punctuation_insertions,
            'case_only_word_substitutions': sum(
                count for (reference, prediction), count in histograms['word']['substitution'].items()
                if reference.casefold() == prediction.casefold()),
        },
        'sample_count': len(rows),
        'unique_pages': len({row['page_id'] for row in rows}),
        'empty_normalized_references': sum(not sample['reference_normalized'] for sample in examples),
        'empty_normalized_predictions': sum(not sample['prediction_normalized'] for sample in examples),
        'category_counts': {category: len(indices) for category, indices in category_indices.items()},
        'category_sample_indices': category_indices,
        'operation_totals': {unit: {operation: sum(counter.values())
                                   for operation, counter in operations.items()}
                             for unit, operations in histograms.items()},
        'common_errors': {unit: {operation: _histogram(counter)
                                for operation, counter in operations.items()}
                          for unit, operations in histograms.items()},
        'by_reference_character_length': _length_breakdown(rows, CHAR_BINS, words=False),
        'by_reference_word_length': _length_breakdown(rows, WORD_BINS, words=True),
        **rankings,
    }
    return summary, examples


def _cell(value) -> str:
    # JSON quotes expose literal spaces, punctuation and absent edit units.
    return json.dumps(value, ensure_ascii=False).replace('|', '&#124;').replace('<', '&lt;').replace('>', '&gt;')


def render_markdown(summary: dict, examples: list[dict]) -> str:
    metrics = summary['metrics']
    lines = ['# Bentham TrOCR validation error analysis', '',
             f"Source: `{INPUT.name}`; SHA-256: `{summary['input_sha256']}`.", '',
             f"Analyzed **{summary['sample_count']:,} samples** across **{summary['unique_pages']} pages**. "
             f"CER **{metrics['cer']:.4%}**, WER **{metrics['wer']:.4%}**, "
             f"exact match **{metrics['exact_match_accuracy']:.4%}** "
             f"({metrics['exact_matches']}/{summary['sample_count']}); failures **{metrics['failed_samples']}**.", '',
             '## Reproducible method', '',
             'Run from `ai-engine`: `..\\.venv\\Scripts\\python.exe -m evaluation.analyze_trocr_errors`.', '',
             'Normalization: Unicode NFC, collapse/trim Unicode whitespace; preserve case, punctuation and accents. Raw text is retained unchanged in each example’s `source_record`.', '']
    lines.extend(f"- **{name}:** {description}" for name, description in summary['methodology'].items())
    character_totals = summary['operation_totals']['character']
    word_totals = summary['operation_totals']['word']
    diagnostics = summary['diagnostics']
    lines.extend(['', '## Observed findings', '',
                  f"- Character substitutions account for {character_totals['substitution']:,}/{metrics['character_errors']:,} character edits.",
                  f"- There are {diagnostics['inserted_space_characters']} inserted space characters. "
                  f"Of {word_totals['insertion']} inserted word tokens, {diagnostics['punctuation_only_word_insertions']} are punctuation-only tokens. "
                  'Tokenization and punctuation contribute to WER; inserted tokens are not all extra lexical words.',
                  f"- {diagnostics['case_only_word_substitutions']} word substitutions differ only in case; case is intentionally preserved in scoring.",
                  f"- {summary['category_counts']['missing_words']} samples contain aligned word deletions, "
                  f"{summary['category_counts']['extra_words']} contain aligned insertions, and "
                  f"{summary['category_counts']['spelling_candidates']} contain near-spelling candidates. Categories overlap."])
    short = summary['by_reference_character_length'][1]
    typical = summary['by_reference_character_length'][4]
    if short['total_evaluated_samples'] and typical['total_evaluated_samples']:
        lines.extend([f"- References of 1?10 characters ({short['total_evaluated_samples']} samples) have "
                      f"CER {short['cer']:.2%} and WER {short['wer']:.2%}; 51?75 characters "
                      f"({typical['total_evaluated_samples']} samples) have CER {typical['cer']:.2%} and "
                      f"WER {typical['wer']:.2%}. Small reference denominators amplify short-line rates; "
                      'this comparison does not establish a causal length effect.'])
    lines.extend(['', f"Empty normalized references: {summary['empty_normalized_references']}; "
                  f"empty normalized predictions: {summary['empty_normalized_predictions']}.", '',
                  '## Edit operation counts', '', '| Unit | Substitutions | Deletions | Insertions |',
                  '|---|---:|---:|---:|'])
    for unit, totals in summary['operation_totals'].items():
        lines.append(f"| {unit} | {totals['substitution']} | {totals['deletion']} | {totals['insertion']} |")
    for unit, operations in summary['common_errors'].items():
        lines.extend(['', f'## Common {unit} errors', ''])
        for operation, histogram in operations.items():
            lines.extend([f'### {operation.title()}s', '', '| Reference unit | Prediction unit | Count |',
                          '|---|---|---:|'])
            for entry in histogram[:12]:
                lines.append(f"| {_cell(entry['reference'])} | {_cell(entry['prediction'])} | {entry['count']} |")
            lines.append('')
    for field, label in [('by_reference_character_length', 'characters'),
                         ('by_reference_word_length', 'words')]:
        lines.extend(['', f'## Error rates by reference length ({label})', '',
                      '| Length | Samples | Reference chars | Char edits | CER | Reference words | Word edits | WER | Exact matches |',
                      '|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
        for group in summary[field]:
            cer_display = f"{group['cer']:.2%}" if group['total_evaluated_samples'] else 'n/a'
            wer_display = f"{group['wer']:.2%}" if group['total_evaluated_samples'] else 'n/a'
            lines.append(f"| {group['bin']} | {group['total_evaluated_samples']} | {group['reference_characters']} | "
                         f"{group['character_errors']} | {cer_display} | {group['reference_words']} | "
                         f"{group['word_errors']} | {wer_display} | {group['exact_matches']} |")
    for category, title in [('missing_words', 'Missing-word examples'),
                            ('extra_words', 'Extra-word examples'),
                            ('spelling_candidates', 'Near-spelling substitution candidates'),
                            ('exact_match', 'Exact-match examples')]:
        indices = summary['category_sample_indices'][category]
        lines.extend(['', f'## {title} ({len(indices)} samples)', ''])
        for index in indices[:5]:
            sample = examples[index]
            source = sample['source_record']
            lines.extend([f"- Sample {index}: `{source['crop_relative_path']}`", 
                          f"  - Raw reference: {_cell(source['reference_raw'])}",
                          f"  - Raw prediction: {_cell(source['prediction_raw'])}"])
            edits = sample['spelling_candidates'] if category == 'spelling_candidates' else [
                edit for edit in sample['word_edits'] if edit['operation'] == (
                    'deletion' if category == 'missing_words' else 'insertion')]
            if category != 'exact_match':
                lines.append('  - Aligned edits: ' + '; '.join(
                    f"{_cell(edit['reference'])} → {_cell(edit['prediction'])}" for edit in edits))
    for metric in ('cer', 'wer'):
        lines.extend(['', f'## Highest per-line {metric.upper()}', '',
                      '| Sample | Crop | Ref chars | Ref words | CER | WER |', '|---:|---|---:|---:|---:|---:|'])
        for index in summary[f'highest_{metric}']:
            sample = examples[index]
            lines.append(f"| {index} | {sample['source_record']['crop_relative_path']} | "
                         f"{sample['reference_characters']} | {sample['reference_words']} | "
                         f"{sample['cer']:.2%} | {sample['wer']:.2%} |")
        lines.append('')
        for index in summary[f'highest_{metric}'][:3]:
            source = examples[index]['source_record']
            lines.extend([f"- Sample {index} raw reference: {_cell(source['reference_raw'])}; "
                          f"raw prediction: {_cell(source['prediction_raw'])}"])
    lines.extend(['', 'All exact matches, ranked samples and category memberships are enumerated in the JSON report; '
                  'the examples JSONL contains every input sample, raw text, per-line rates and alignments. '
                  'Histograms in JSON are complete; Markdown shows the 12 most frequent edits per operation. '
                  'These are descriptive validation findings, not evidence of causes or model changes.', ''])
    return '\n'.join(lines)


def run_analysis() -> dict:
    source = INPUT.read_bytes()
    rows = load_predictions(INPUT)
    if len(rows) != 1197:
        raise ValueError(f'Expected 1197 validation samples, found {len(rows)}')
    summary, examples = analyze(rows)
    summary['input_file'] = str(INPUT)
    summary['input_sha256'] = hashlib.sha256(source).hexdigest()
    if INPUT.read_bytes() != source:
        raise RuntimeError('Validation predictions changed during analysis')
    RESULTS.mkdir(parents=True, exist_ok=True)
    outputs = {
        'bentham_trocr_error_analysis.json': json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
        'bentham_trocr_error_examples.jsonl': ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in examples),
        'bentham_trocr_error_analysis.md': render_markdown(summary, examples),
    }
    for name, content in outputs.items():
        target = RESULTS / name
        temporary = target.with_suffix(target.suffix + '.tmp')
        temporary.write_text(content, encoding='utf-8', newline='\n')
        temporary.replace(target)
    print(json.dumps({key: summary[key] for key in
                      ('sample_count', 'unique_pages', 'metrics', 'operation_totals', 'category_counts')}, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        run_analysis()
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f'Error analysis failed: {exc}\n')


if __name__ == '__main__':
    main()
