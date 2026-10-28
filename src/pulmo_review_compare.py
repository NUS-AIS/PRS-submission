"""Compare already exported reports without rerunning or evaluating the model."""
import math

from pulmo_review_verify import VerificationError


def _scores(report):
    result = report.get('prediction', {}).get('probabilities')
    if not isinstance(result, list) or len(result) != 3:
        raise VerificationError('invalid_scores', 'A comparison requires three class scores.')
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
           for value in result):
        raise VerificationError('invalid_scores', 'Invalid class score in comparison.')
    return result


def compare_reports(left, right):
    left_scores, right_scores = _scores(left), _scores(right)
    same_input = bool(left.get('input_fingerprint')) and left.get('input_fingerprint') == right.get('input_fingerprint')
    a, b = left['prediction'], right['prediction']
    warnings = []
    if not same_input:
        warnings.append('Different model inputs: this is not a controlled model comparison.')
    if a.get('model') != b.get('model'):
        warnings.append('Different model identifiers; checkpoint equivalence is not established.')
    left_privacy = left.get('privacy', {})
    right_privacy = right.get('privacy', {})
    clinical_known = (left_privacy.get('clinical_inputs_included') is True
                      and right_privacy.get('clinical_inputs_included') is True)
    clinical_equal = a.get('clinical') == b.get('clinical') if clinical_known else None
    if clinical_equal is None:
        warnings.append('Clinical inputs were omitted from at least one report; equality cannot be checked.')
    elif not clinical_equal:
        warnings.append('Clinical inputs differ between the reports.')
    att_a, att_b = left.get('attention', {}), right.get('attention', {})
    threshold_equal = att_a.get('threshold') == att_b.get('threshold')
    method_equal = left.get('method') == right.get('method') and bool(left.get('method'))
    if not threshold_equal:
        warnings.append('Display thresholds differ; above-threshold fractions are not directly comparable.')
    if not method_equal:
        warnings.append('Explanation method metadata differs or is missing.')
    if a.get('predicted_class') != b.get('predicted_class'):
        warnings.append('Predicted classes differ, so Grad-CAM targets different class logits.')
    comparable_attention = same_input and method_equal
    rows_a = {row['position']: row for row in att_a.get('rows', [])}
    rows_b = {row['position']: row for row in att_b.get('rows', [])}
    common = sorted(rows_a.keys() & rows_b.keys())
    positions = []
    for position in common:
        row_a, row_b = rows_a[position], rows_b[position]
        has_signal_data = all(row.get('status') != 'not_requested' for row in (row_a, row_b))
        delta = {}
        for metric in ('mean', 'maximum', 'entropy', 'above_threshold_fraction'):
            av, bv = row_a.get(metric), row_b.get(metric)
            allowed = comparable_attention and has_signal_data and (metric != 'above_threshold_fraction' or threshold_equal)
            delta[metric] = round(bv - av, 8) if allowed and av is not None and bv is not None else None
        positions.append({'position': position, 'left_status': row_a.get('status'),
                          'right_status': row_b.get('status'), 'right_minus_left': delta})
    warnings.append('Differences are descriptive, not improvements in accuracy or clinical evidence.')
    warnings.append('Grad-CAM is normalized per case; intensity changes are not absolute evidence changes.')
    return {
        'schema_version': 1,
        'left_run': left.get('run_id'),
        'right_run': right.get('run_id'),
        'same_input': same_input,
        'same_model_identifier': a.get('model') == b.get('model'),
        'clinical_equal': clinical_equal,
        'same_method': method_equal,
        'same_threshold': threshold_equal,
        'prediction_changed': a.get('predicted_class') != b.get('predicted_class'),
        'class_score_deltas': [round(y - x, 8) for x, y in zip(left_scores, right_scores)],
        'common_positions': common,
        'left_only_positions': sorted(rows_a.keys() - rows_b.keys()),
        'right_only_positions': sorted(rows_b.keys() - rows_a.keys()),
        'position_deltas': positions,
        'warnings': warnings,
    }
