import copy
import itertools
import json
from pathlib import Path

import pytest

from evaluation import analyze_trocr_errors as analysis
from evaluation.evaluate_trocr_baseline import calculate_metrics, edit_distance


def row(reference, prediction, *, index=0, failed=False):
    return {'page_id': 'page-1', 'crop_relative_path': f'line-{index}.png',
            'reference_raw': reference, 'prediction_raw': prediction,
            'status': 'failed' if failed else 'ok',
            'error': 'broken image' if failed else None,
            'failure_stage': 'image' if failed else None}


def test_known_character_and_word_edits():
    assert analysis.align_errors('cat', 'cut') == [
        {'operation': 'substitution', 'reference': 'a', 'prediction': 'u',
         'reference_index': 1, 'prediction_index': 1}]
    deleted = analysis.align_errors('one two three'.split(), 'one three'.split())
    assert [(edit['operation'], edit['reference'], edit['prediction']) for edit in deleted] == [
        ('deletion', 'two', None)]
    inserted = analysis.align_errors('one three'.split(), 'one two three'.split())
    assert [(edit['operation'], edit['reference'], edit['prediction']) for edit in inserted] == [
        ('insertion', None, 'two')]
    assert analysis.align_errors('abc', 'abc') == []
    assert analysis.align_errors('aa', 'a')[0]['reference_index'] == 0
    assert analysis.align_errors('ab', 'ba') == analysis.align_errors('ab', 'ba')
    assert [edit['operation'] for edit in analysis.align_errors('ab', 'ba')] == [
        'substitution', 'substitution']


def test_exhaustive_short_alignments_have_minimum_distance_and_reconstruct_prediction():
    strings = [''.join(parts) for length in range(4)
               for parts in itertools.product('ab', repeat=length)]
    for reference in strings:
        for prediction in strings:
            edits = analysis.align_errors(reference, prediction)
            assert len(edits) == edit_distance(reference, prediction)
            reconstructed = list(reference)
            # Forward indices refer to original units; reverse application avoids shifts.
            for edit in reversed(edits):
                index = edit['reference_index']
                if edit['operation'] == 'substitution':
                    reconstructed[index] = edit['prediction']
                elif edit['operation'] == 'deletion':
                    del reconstructed[index]
                else:
                    reconstructed.insert(index, edit['prediction'])
            assert ''.join(reconstructed) == prediction


def test_analysis_counts_categories_and_length_coverage_without_mutation():
    rows = [row(' Exact\ttext ', 'Exact text', index=0), row('cat', 'cut', index=1),
            row('one two three', 'one three', index=2),
            row('one three', 'one two three', index=3), row('', 'x', index=4),
            row('lost word', None, index=5, failed=True)]
    before = copy.deepcopy(rows)
    summary, examples = analysis.analyze(rows, top_n=2)
    assert rows == before
    assert [sample['source_record'] for sample in examples] == rows
    assert summary['metrics'] == calculate_metrics(rows)
    assert summary['sample_count'] == 6
    assert summary['metrics']['failed_samples'] == 1
    assert summary['category_counts']['exact_match'] == 1
    assert summary['category_counts']['missing_words'] == 2
    assert summary['category_counts']['extra_words'] == 2
    assert summary['category_counts']['spelling_candidates'] == 1
    assert summary['empty_normalized_references'] == 1
    assert summary['empty_normalized_predictions'] == 1
    assert summary['operation_totals']['word'] == {'substitution': 1, 'deletion': 3, 'insertion': 2}
    assert sum(summary['operation_totals']['character'].values()) == summary['metrics']['character_errors']
    for key in ('by_reference_character_length', 'by_reference_word_length'):
        assert sum(group['total_evaluated_samples'] for group in summary[key]) == 6
        assert sum(group['character_errors'] for group in summary[key]) == summary['metrics']['character_errors']
        assert sum(group['word_errors'] for group in summary[key]) == summary['metrics']['word_errors']
    assert summary['highest_cer'] == sorted(range(6), key=lambda i: (-examples[i]['cer'], i))[:2]
    assert summary['highest_wer'] == sorted(range(6), key=lambda i: (-examples[i]['wer'], i))[:2]
    assert analysis.analyze(rows, top_n=2) == (summary, examples)


def test_empty_references_failures_and_rates_over_one():
    rows = [row('', 'one two', index=0), row('', '', index=1),
            row('', None, failed=True, index=2)]
    summary, examples = analysis.analyze(rows)
    assert examples[0]['cer'] == 7
    assert examples[0]['wer'] == 2
    assert examples[1]['exact_match'] is True
    assert examples[2]['exact_match'] is False
    assert summary['metrics']['cer'] == 7
    assert summary['metrics']['wer'] == 2
    assert summary['metrics']['exact_match_accuracy'] == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        analysis.analyze([])


def test_spelling_candidate_is_explicitly_restricted():
    candidate = lambda reference, prediction: analysis.spelling_candidate(
        {'operation': 'substitution', 'reference': reference, 'prediction': prediction})
    assert candidate('cat', 'cut')
    assert candidate('proceed', 'process')
    assert not candidate('CAT', 'cat')
    assert not candidate('cat,', 'cat.')
    assert not candidate('to', 'do')
    assert not candidate('apple', 'orange')
    assert not analysis.spelling_candidate({'operation': 'deletion', 'reference': 'cat', 'prediction': None})


@pytest.mark.parametrize('length', [0, 1, 10, 11, 25, 26, 50, 51, 75, 76, 100, 101])
def test_length_bin_boundaries_cover_exactly_once(length):
    summary, _ = analysis.analyze([row('x' * length, 'x' * length)])
    populated = [group for group in summary['by_reference_character_length'] if group['total_evaluated_samples']]
    assert len(populated) == 1
    assert populated[0]['minimum'] <= length
    assert populated[0]['maximum'] is None or length <= populated[0]['maximum']


@pytest.mark.parametrize('payload, message', [
    ('', 'empty'), ('broken', 'Invalid prediction JSON'),
    ('[]', 'Invalid identifiers'),
    (json.dumps({**row('a', None), 'status': 'ok'}), 'Missing successful prediction'),
    (json.dumps({**row('a', 'a'), 'reference_normalized': 'changed'}), 'Inconsistent'),
    (json.dumps(row('a', 'a')) + '\n' + json.dumps(row('a', 'a')), 'Duplicate'),
])
def test_invalid_prediction_input(tmp_path, payload, message):
    path = tmp_path / 'validation.jsonl'
    path.write_text(payload, encoding='utf-8')
    with pytest.raises(ValueError, match=message):
        analysis.load_predictions(path)


def test_generate_all_outputs_reproducibly_preserves_source_and_other_files(tmp_path, monkeypatch):
    source = tmp_path / 'bentham_trocr_validation_predictions.jsonl'
    rows = [row('cat', 'cut', index=i) for i in range(1197)]
    source.write_text(''.join(json.dumps(item) + '\n' for item in rows), encoding='utf-8')
    before = source.read_bytes()
    sentinel = tmp_path / 'bentham_trocr_baseline_predictions.jsonl'
    sentinel.write_bytes(b'not used by validation analysis')
    monkeypatch.setattr(analysis, 'INPUT', source)
    monkeypatch.setattr(analysis, 'RESULTS', tmp_path)
    summary = analysis.run_analysis()
    outputs = {name: (tmp_path / name).read_bytes() for name in (
        'bentham_trocr_error_analysis.json', 'bentham_trocr_error_examples.jsonl',
        'bentham_trocr_error_analysis.md')}
    assert summary['sample_count'] == 1197
    saved = [json.loads(line) for line in outputs['bentham_trocr_error_examples.jsonl'].splitlines()]
    assert [item['source_record'] for item in saved] == rows
    assert json.loads(outputs['bentham_trocr_error_analysis.json']) == summary
    markdown = outputs['bentham_trocr_error_analysis.md'].decode('utf-8')
    assert 'Highest per-line CER' in markdown
    assert 'Near-spelling substitution candidates' in markdown
    assert analysis.run_analysis() == summary
    assert all((tmp_path / name).read_bytes() == data for name, data in outputs.items())
    assert source.read_bytes() == before
    assert sentinel.read_bytes() == b'not used by validation analysis'


def test_wrong_validation_sample_count_fails_without_outputs(tmp_path, monkeypatch):
    source = tmp_path / 'validation.jsonl'
    source.write_text(json.dumps(row('a', 'a')), encoding='utf-8')
    monkeypatch.setattr(analysis, 'INPUT', source)
    monkeypatch.setattr(analysis, 'RESULTS', tmp_path)
    with pytest.raises(ValueError, match='Expected 1197 validation samples'):
        analysis.run_analysis()
    assert list(tmp_path.iterdir()) == [source]


def test_diagnostics_separate_punctuation_insertions_and_case_substitutions():
    summary, _ = analysis.analyze([
        row('Hello', 'hello', index=0), row('cat', 'cat ,', index=1),
        row('cat', 'cat dog', index=2),
    ])
    assert summary['diagnostics'] == {
        'inserted_space_characters': 2,
        'punctuation_only_word_insertions': 1,
        'case_only_word_substitutions': 1,
    }
    assert summary['operation_totals']['word']['insertion'] == 2
