"""Complete cached-run review packages: selected slices, contact sheet and offline HTML."""
import copy
import hashlib
import html
import io
import json
import zipfile
from datetime import datetime, timezone

from PIL import Image, ImageDraw

from pulmo_attention import attention_summary, finite_number, summary_csv, validate_stack
from pulmo_cases import ApiError
from pulmo_explain import render_png
from pulmo_reports import bound_prediction


MAX_EXPORT_BYTES = 64 * 1024 * 1024
REPORT_FORMAT = 'pulmo-review'
REPORT_VERSION = 1
SCORE_LABELS = ['Aspergillus', 'Other fungal', 'Non-fungal']


def json_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError):
        raise ApiError(400, 'invalid_report', 'Prediction metadata cannot be serialized as finite JSON.') from None


def pixel_fingerprint(stack):
    """Hash the model input, including dimensions, without source patient identifiers."""
    digest = hashlib.sha256()
    digest.update(str(tuple(stack.shape)).encode('ascii'))
    digest.update(stack.dtype.str.encode('ascii'))
    digest.update(stack.tobytes(order='C'))
    return digest.hexdigest()


def public_prediction(result, include_clinical=False):
    # Explicit allowlist: do not leak names through unknown future metadata fields.
    fields = ['model', 'predicted_class', 'probabilities', 'labels', 'device',
              'explanation_status', 'explanation_diagnostics', 'severity', 'disclaimer']
    exported = {key: copy.deepcopy(result[key]) for key in fields if key in result}
    if include_clinical:
        for key in ('clinical', 'inputs'):
            if key in result:
                exported[key] = copy.deepcopy(result[key])
    return exported


def review_snapshot(case, run, threshold=.5, positions=None, include_clinical=False):
    prediction = bound_prediction(case, run)
    stack, cam = validate_stack(case['stack'], prediction.get('cam'))
    summary = attention_summary(stack, cam, threshold, positions)
    result = {
        'format': REPORT_FORMAT,
        'schema_version': REPORT_VERSION,
        'run_id': run,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'input_fingerprint': pixel_fingerprint(stack),
        'prediction': public_prediction(prediction['result'], include_clinical),
        'attention': summary,
        'privacy': {
            'case_name_included': False,
            'clinical_inputs_included': bool(include_clinical),
            'note': 'Images and input fingerprints remain sensitive research data.',
        },
        'method': {
            'name': 'Grad-CAM',
            'target': 'final predicted-class logit',
            'layer': 'bb.layer4',
            'normalization': 'case maximum',
            'sampling': 'three neighbouring CT slices per sampled position',
        },
        'limitations': summary['limitations'] + [
            'Research output only. No diagnostic accuracy or calibration is inferred from this report.',
            'A hash detects changed bytes; it does not authenticate an author or validate a model.',
        ],
    }
    json_bytes(result)
    bound_prediction(case, run)
    return result, stack, cam


def contact_sheet(images, columns=4, tile_width=224):
    """Input is [(one_based_position, png_bytes)]. Preserve image aspect ratios."""
    if not images or len(images) > 128:
        raise ApiError(400, 'invalid_positions', 'Choose 1 to 128 images for the contact sheet.')
    columns = min(columns, len(images))
    if not 1 <= columns <= 8 or not 64 <= tile_width <= 512:
        raise ApiError(400, 'invalid_layout', 'Unsupported contact sheet layout.')
    padding, label_height = 10, 24
    tile_height = tile_width + label_height
    row_count = (len(images) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * (tile_width + padding) + padding,
                              row_count * (tile_height + padding) + padding), '#071c2c')
    draw = ImageDraw.Draw(sheet)
    for index, (position, data) in enumerate(images):
        with Image.open(io.BytesIO(data)) as source:
            source = source.convert('RGB')
            source.thumbnail((tile_width, tile_width), Image.Resampling.LANCZOS)
            x = padding + (index % columns) * (tile_width + padding)
            y = padding + (index // columns) * (tile_height + padding)
            offset_x = (tile_width - source.width) // 2
            offset_y = (tile_width - source.height) // 2
            sheet.paste(source, (x + offset_x, y + offset_y))
            draw.text((x, y + tile_width + 4), f'Position {position}', fill='#b8efff')
    buffer = io.BytesIO()
    sheet.save(buffer, format='PNG')
    return buffer.getvalue()


def _text(value):
    return html.escape(str(value), quote=True)


def _value(value):
    if value is None:
        return 'Not available'
    if isinstance(value, float):
        return f'{value:.5f}'
    return _text(value)


def offline_html(report, image_files):
    """Script-free HTML. No fetched fonts, scripts or remote resources."""
    prediction = report['prediction']
    attention = report['attention']
    details = [
        ('Run', report['run_id']),
        ('Model', prediction.get('model', 'Not recorded')),
        ('Predicted class', prediction.get('predicted_class', 'Not recorded')),
        ('Created UTC', report['created_at']),
        ('Input fingerprint', report['input_fingerprint']),
        ('Attention status', attention['status']),
        ('Display threshold', attention['threshold']),
        ('Coordinate space', attention['coordinate_space']),
    ]
    detail_html = ''.join(f'<dt>{_text(key)}</dt><dd>{_text(value)}</dd>' for key, value in details)
    scores = prediction.get('probabilities', [])
    score_html = ''.join(f'<li>{_text(label)}: {_value(score)}</li>'
                         for label, score in zip(SCORE_LABELS, scores))
    rows = []
    figures = []
    for row in attention['rows']:
        position = row['position']
        rows.append('<tr>' + ''.join(f'<td>{_value(row[key])}</td>' for key in
                    ('position', 'status', 'mean', 'maximum', 'above_threshold_fraction', 'entropy')) + '</tr>')
        original = image_files[position]['original']
        overlay = image_files[position].get('overlay')
        pictures = f'<img src="{_text(original)}" alt="Original model input position {position}">'
        if overlay:
            pictures += f'<img src="{_text(overlay)}" alt="Grad-CAM position {position}">'
        figures.append(f'<figure>{pictures}<figcaption>Sampled position {position}</figcaption></figure>')
    warnings = ''.join(f'<li>{_text(item)}</li>' for item in report['limitations'])
    clinical = ''
    if report['privacy']['clinical_inputs_included']:
        clinical = '<h2>Clinical inputs</h2><pre>' + _text(json.dumps({
            key: prediction.get(key) for key in ('clinical', 'inputs')
        }, ensure_ascii=False, indent=2)) + '</pre>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>PULMO AI explanation review</title>
<style>
body {{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:1rem;color:#143047}}
h1,h2 {{color:#084d67}} dt {{font-weight:600}} dd {{margin:0 0 .8rem;overflow-wrap:anywhere}}
table {{border-collapse:collapse;width:100%}} td,th {{padding:.6rem;border:1px solid #abc;text-align:left}}
figure {{break-inside:avoid;margin:1rem 0;padding:1rem;background:#edf5f8}}
figure img {{width:45%;max-width:400px;margin:.3rem}} figcaption {{font-weight:600}}
.notice {{padding:1rem;background:#fff4d6}} pre {{white-space:pre-wrap;overflow-wrap:anywhere}}
@media print {{body {{margin:0;font-size:11pt}} h2 {{break-after:avoid}} .notice {{border:1px solid #777}}}}
</style></head><body>
<h1>PULMO AI · Explanation review</h1>
<p class="notice">Research use only. Attention does not define lesions or establish diagnosis.</p>
<dl>{detail_html}</dl><h2>Uncalibrated class scores</h2><ul>{score_html}</ul>
<h2>Position statistics</h2><p>Above-threshold fraction counts positive pixels at or above the display threshold.</p>
<table><thead><tr><th>Position</th><th>Status</th><th>Mean</th><th>Maximum</th><th>Fraction</th><th>Entropy</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>{clinical}
<h2>Original inputs and attention</h2>{''.join(figures)}
<h2>Interpretation limits</h2><ul>{warnings}</ul>
<p>Check manifest.json with the supplied offline verifier before sharing. Hashes are not digital signatures.</p>
</body></html>'''.encode('utf-8')


def build_review_archive(case, run, threshold=.5, positions=None, opacity=.55, include_clinical=False):
    opacity = finite_number(opacity, 'Opacity', 0, 1)
    report, stack, cam = review_snapshot(case, run, threshold, positions, include_clinical)
    report['display'] = {'opacity': opacity, 'image_channel': 'middle neighbouring slice'}
    files = {}
    images = {}
    sheet_images = []
    for position in report['attention']['selected_positions']:
        index = position - 1
        original = f'images/position-{position:03d}-original.png'
        files[original] = render_png(stack[index, 1])
        images[position] = {'original': original}
        shown = original
        if cam is not None:
            overlay = f'images/position-{position:03d}-overlay.png'
            files[overlay] = render_png(stack[index, 1], cam[index], opacity)
            images[position]['overlay'] = overlay
            shown = overlay
        sheet_images.append((position, files[shown]))
        if sum(map(len, files.values())) > MAX_EXPORT_BYTES:
            raise ApiError(413, 'report_too_large', 'Select fewer positions for this export.')
    files['contact-sheet.png'] = contact_sheet(sheet_images)
    files['statistics.csv'] = summary_csv(report['attention'])
    files['report.json'] = json_bytes(report)
    files['index.html'] = offline_html(report, images)
    manifest = {
        'format': REPORT_FORMAT,
        'schema_version': REPORT_VERSION,
        'run_id': run,
        'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(files.items())},
    }
    files['manifest.json'] = json_bytes(manifest)
    if sum(map(len, files.values())) > MAX_EXPORT_BYTES:
        raise ApiError(413, 'report_too_large', 'Select fewer positions for this export.')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    bound_prediction(case, run)
    return output.getvalue()
