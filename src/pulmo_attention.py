"""Descriptive attention statistics in model-input coordinates, without inference."""
import csv
import io
import math

import numpy as np

from pulmo_cases import ApiError


COORDINATES = 'cropped model input; x increases right, y increases down'
LIMITATIONS = [
    'Attention intensity is not probability, lesion area or disease severity.',
    'Coordinates refer to cropped model inputs, not original CT or patient anatomy.',
    'Thresholds are display choices, not validated diagnostic cutoffs.',
    'Case-normalized values cannot measure absolute evidence across patients.',
]


def finite_number(value, name, low, high):
    if isinstance(value, (bool, str)):
        raise ApiError(400, 'invalid_review_parameter', f'{name} must be numeric.')
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ApiError(400, 'invalid_review_parameter', f'{name} must be numeric.') from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ApiError(400, 'invalid_review_parameter', f'{name} must be between {low} and {high}.')
    return value


def selected_positions(value, count):
    """Parse one-based positions. Reject duplicates and excessive selections."""
    if not isinstance(count, int) or not 1 <= count <= 128:
        raise ApiError(400, 'invalid_stack', 'Expected 1 to 128 sampled positions.')
    if value is None or value == '':
        return list(range(count))
    if isinstance(value, str):
        if len(value) > 512:
            raise ApiError(400, 'invalid_positions', 'Position selection is too long.')
        value = value.split(',')
        try:
            value = [int(item.strip()) for item in value]
        except ValueError:
            raise ApiError(400, 'invalid_positions', 'Use comma-separated position numbers.') from None
    if not isinstance(value, (list, tuple)) or not value or len(value) > count:
        raise ApiError(400, 'invalid_positions', 'Select one or more available positions.')
    if any(type(item) is not int or not 1 <= item <= count for item in value):
        raise ApiError(400, 'invalid_positions', f'Positions must be integers from 1 to {count}.')
    if len(set(value)) != len(value):
        raise ApiError(400, 'invalid_positions', 'Each position may be selected only once.')
    return [item - 1 for item in sorted(value)]


def validate_stack(stack, cam):
    stack = np.asarray(stack)
    if stack.ndim != 4 or stack.shape[1] != 3:
        raise ApiError(400, 'invalid_stack', 'Expected sampled three-channel model inputs.')
    count, _, height, width = stack.shape
    if not 1 <= count <= 128 or not 1 <= height <= 1024 or not 1 <= width <= 1024:
        raise ApiError(400, 'invalid_stack', 'Model input dimensions exceed report limits.')
    if stack.dtype != np.uint8:
        raise ApiError(400, 'invalid_stack', 'Report input must be uint8 preprocessed pixels.')
    if cam is None:
        return stack, None
    cam = np.asarray(cam)
    if cam.shape != (count, height, width) or not np.issubdtype(cam.dtype, np.number):
        raise ApiError(400, 'invalid_explanation', 'Attention dimensions do not match model inputs.')
    if not np.isfinite(cam).all() or np.any(cam < 0) or np.any(cam > 1 + 1e-6):
        raise ApiError(400, 'invalid_explanation', 'Attention must contain finite normalized values.')
    return stack, np.clip(cam, 0, 1)


def _rounded(value):
    return round(float(value), 8)


def position_statistics(gray, attention, position, threshold):
    """No anatomy labels: left/right here are image halves, not patient sides."""
    height, width = gray.shape
    result = {
        'position': position,
        'width': width,
        'height': height,
        'input_min': int(gray.min()),
        'input_max': int(gray.max()),
        'input_mean': _rounded(gray.mean()),
        'input_constant': bool(gray.min() == gray.max()),
        'status': 'not_requested' if attention is None else 'zero_signal',
        'mean': None,
        'maximum': None,
        'sum': None,
        'positive_fraction': None,
        'above_threshold_fraction': None,
        'centroid': None,
        'peak': None,
        'threshold_box': None,
        'entropy': None,
        'image_half_mass': None,
    }
    if attention is None:
        return result
    values = attention.astype(np.float64)
    total = float(values.sum())
    positive = values > 0
    mask = positive & (values >= threshold)
    result.update(
        status='available' if total > 0 else 'zero_signal',
        mean=_rounded(values.mean()),
        maximum=_rounded(values.max()),
        sum=_rounded(total),
        positive_fraction=_rounded(positive.mean()),
        above_threshold_fraction=_rounded(mask.mean()),
    )
    if total == 0:
        return result
    yy, xx = np.indices(values.shape)
    peak_y, peak_x = np.unravel_index(values.argmax(), values.shape)
    result['centroid'] = {
        'x': _rounded((values * xx).sum() / total),
        'y': _rounded((values * yy).sum() / total),
    }
    result['peak'] = {'x': int(peak_x), 'y': int(peak_y)}
    probabilities = values[positive] / total
    normalizer = math.log(values.size) if values.size > 1 else 1
    result['entropy'] = _rounded(-(probabilities * np.log(probabilities)).sum() / normalizer)
    result['image_half_mass'] = {
        'left': _rounded(values[:, :width // 2].sum() / total),
        'right': _rounded(values[:, width // 2:].sum() / total),
        'upper': _rounded(values[:height // 2].sum() / total),
        'lower': _rounded(values[height // 2:].sum() / total),
    }
    if mask.any():
        ys, xs = np.nonzero(mask)
        result['threshold_box'] = {
            'x_min': int(xs.min()), 'x_max': int(xs.max()),
            'y_min': int(ys.min()), 'y_max': int(ys.max()),
        }
    return result


def attention_summary(stack, cam, threshold=.5, positions=None):
    threshold = finite_number(threshold, 'Threshold', 0, 1)
    stack, cam = validate_stack(stack, cam)
    indexes = selected_positions(positions, len(stack))
    rows = [position_statistics(stack[i, 1], None if cam is None else cam[i], i + 1, threshold)
            for i in indexes]
    masses = {i + 1: float(cam[i].astype(np.float64).sum()) if cam is not None else 0 for i in indexes}
    ranked = sorted(rows, key=lambda row: (-masses[row['position']], row['position']))
    total_mass = sum(masses.values())
    for row in rows:
        row['selected_mass_fraction'] = _rounded(masses[row['position']] / total_mass) if total_mass else None
    return {
        'schema_version': 1,
        'coordinate_space': COORDINATES,
        'threshold': threshold,
        'sampled_positions': len(stack),
        'selected_positions': [index + 1 for index in indexes],
        'status': 'not_requested' if cam is None else 'available' if total_mass else 'zero_signal',
        'ranked_positions': [row['position'] for row in ranked] if total_mass else [],
        'zero_signal_positions': [row['position'] for row in rows if row['status'] == 'zero_signal'],
        'constant_input_positions': [row['position'] for row in rows if row['input_constant']],
        'rows': rows,
        'limitations': list(LIMITATIONS),
    }


CSV_FIELDS = [
    'position', 'status', 'mean', 'maximum', 'sum',
    'positive_fraction', 'above_threshold_fraction', 'selected_mass_fraction',
    'entropy', 'input_min', 'input_max', 'input_mean', 'input_constant',
    'centroid_x', 'centroid_y', 'peak_x', 'peak_y',
    'box_x_min', 'box_y_min', 'box_x_max', 'box_y_max',
]


def summary_csv(summary):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader()
    for row in summary['rows']:
        flat = {key: row.get(key) for key in CSV_FIELDS}
        for source, prefix in [('centroid', 'centroid'), ('peak', 'peak'), ('threshold_box', 'box')]:
            for key, value in (row[source] or {}).items():
                flat[f'{prefix}_{key}'] = value
        writer.writerow(flat)
    return buffer.getvalue().encode('utf-8')
