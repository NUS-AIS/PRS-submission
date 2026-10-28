"""Bounded, extraction-free verification of locally saved review archives."""
import hashlib
import io
import json
import math
import re
import stat
import zipfile
from pathlib import PurePosixPath


MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 270
MAX_JSON_BYTES = 2 * 1024 * 1024
HASH_PATTERN = re.compile(r'^[0-9a-f]{64}$')


class VerificationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fail(code, message):
    raise VerificationError(code, message)


def safe_name(name):
    if not isinstance(name, str) or not name or len(name) > 160:
        return False
    path = PurePosixPath(name)
    return (not path.is_absolute() and '\\' not in name and ':' not in name
            and all(part not in ('', '.', '..') for part in name.split('/'))
            and all(32 <= ord(character) < 127 for character in name))


def strict_json(data, label):
    if len(data) > MAX_JSON_BYTES:
        fail('metadata_too_large', f'{label} exceeds the metadata size limit.')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('duplicate_json_key', f'{label} contains a duplicate key.')
            result[key] = value
        return result

    def constant(value):
        fail('nonfinite_json', f'{label} contains a non-finite numeric value.')

    try:
        result = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        fail('invalid_json', f'{label} is not valid UTF-8 JSON.')
    if not isinstance(result, dict):
        fail('invalid_json_object', f'{label} must contain a JSON object.')
    # JSON exponents such as 1e999 bypass parse_constant and become infinity.
    pending = [result]
    while pending:
        value = pending.pop()
        if isinstance(value, float) and not math.isfinite(value):
            fail('nonfinite_json', f'{label} contains a non-finite numeric value.')
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return result


def validate_manifest(manifest, names):
    if manifest.get('format') != 'pulmo-review' or manifest.get('schema_version') != 1:
        fail('unsupported_format', 'Unsupported review archive format or version.')
    if not isinstance(manifest.get('run_id'), str) or not manifest['run_id']:
        fail('invalid_run', 'Manifest has no valid run identifier.')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        fail('invalid_manifest', 'Manifest must list archive files.')
    if set(files) != names - {'manifest.json'}:
        fail('manifest_members', 'Archive members do not match the manifest.')
    required = {'report.json', 'statistics.csv', 'index.html', 'contact-sheet.png'}
    if not required.issubset(files):
        fail('missing_required_file', 'Review is missing a required report file.')
    for name, entry in files.items():
        if not safe_name(name) or not isinstance(entry, dict):
            fail('invalid_manifest', 'Invalid manifest entry.')
        size = entry.get('bytes')
        digest = entry.get('sha256')
        if type(size) is not int or size < 0 or size > MAX_EXPANDED_BYTES:
            fail('invalid_manifest_size', 'Manifest contains an invalid byte count.')
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            fail('invalid_manifest_hash', 'Manifest contains an invalid SHA256 digest.')
    return files


def validate_report(report, manifest):
    if report.get('format') != 'pulmo-review' or report.get('schema_version') != 1:
        fail('unsupported_report', 'Unsupported report schema.')
    if report.get('run_id') != manifest['run_id']:
        fail('run_mismatch', 'Report and manifest refer to different runs.')
    fingerprint = report.get('input_fingerprint')
    if not isinstance(fingerprint, str) or not HASH_PATTERN.fullmatch(fingerprint):
        fail('invalid_fingerprint', 'Report input fingerprint is invalid.')
    prediction = report.get('prediction')
    if not isinstance(prediction, dict):
        fail('invalid_prediction', 'Report prediction must be an object.')
    scores = prediction.get('probabilities')
    if not isinstance(scores, list) or len(scores) != 3:
        fail('invalid_scores', 'Expected three finite class scores.')
    if any(type(score) not in (int, float) or not 0 <= score <= 1 for score in scores):
        fail('invalid_scores', 'Class scores must be finite numbers between zero and one.')
    if abs(sum(scores) - 1) > .001:
        fail('invalid_scores', 'Class scores do not sum to one within tolerance.')
    attention = report.get('attention')
    if not isinstance(attention, dict):
        fail('invalid_attention', 'Report attention must be an object.')
    positions = attention.get('selected_positions')
    count = attention.get('sampled_positions')
    if type(count) is not int or not 1 <= count <= 128:
        fail('invalid_positions', 'Invalid sampled-position count.')
    if not isinstance(positions, list) or not positions or len(positions) > count:
        fail('invalid_positions', 'Invalid selected positions.')
    if any(type(value) is not int or not 1 <= value <= count for value in positions):
        fail('invalid_positions', 'Position numbers are outside the model input.')
    if positions != sorted(set(positions)):
        fail('invalid_positions', 'Selected positions must be unique and sorted.')
    rows = attention.get('rows')
    if not isinstance(rows, list) or len(rows) != len(positions):
        fail('invalid_statistics', 'Statistics do not cover the selected positions.')
    if any(not isinstance(row, dict) for row in rows):
        fail('invalid_statistics', 'Each statistics row must be an object.')
    if [row.get('position') for row in rows] != positions:
        fail('invalid_statistics', 'Statistics and selected positions do not agree.')
    status = attention.get('status')
    if status not in ('available', 'zero_signal', 'not_requested'):
        fail('invalid_attention', 'Unrecognized attention status.')
    threshold = attention.get('threshold')
    if type(threshold) not in (int, float) or not 0 <= threshold <= 1:
        fail('invalid_threshold', 'Report display threshold must be between zero and one.')
    for row in rows:
        if row.get('status') not in ('available', 'zero_signal', 'not_requested'):
            fail('invalid_statistics', 'Unrecognized per-position attention status.')
        for field in ('mean', 'maximum', 'positive_fraction', 'above_threshold_fraction',
                      'selected_mass_fraction', 'entropy'):
            value = row.get(field)
            if value is not None and (type(value) not in (int, float) or not 0 <= value <= 1):
                fail('invalid_statistics', f'Invalid normalized metric: {field}')
        if row['status'] == 'not_requested' and any(row.get(field) is not None
                                                    for field in ('mean', 'maximum', 'sum')):
            fail('invalid_statistics', 'An absent heatmap cannot have measured attention.')
        if row['status'] == 'zero_signal' and row.get('maximum') != 0:
            fail('invalid_statistics', 'Zero-signal row has nonzero or missing maximum.')
    expected_images = set()
    for position in positions:
        expected_images.add(f'images/position-{position:03d}-original.png')
        if status != 'not_requested':
            expected_images.add(f'images/position-{position:03d}-overlay.png')
    actual_images = {name for name in manifest['files'] if name.startswith('images/')}
    if expected_images != actual_images:
        fail('image_members', 'Images do not match selected positions and explanation status.')


def inspect_archive(data):
    """Verify all bytes before returning a report; never extract or execute HTML."""
    if not isinstance(data, bytes) or len(data) > MAX_ARCHIVE_BYTES:
        fail('archive_size', 'Archive exceeds the size limit or is not bytes.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ENTRIES:
                fail('entry_limit', 'Archive has an unsupported number of files.')
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)):
                fail('duplicate_member', 'Archive contains duplicate filenames.')
            if any(not safe_name(name) for name in names):
                fail('unsafe_path', 'Archive contains an unsafe path.')
            if sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
                fail('expanded_size', 'Expanded archive exceeds the size limit.')
            for entry in entries:
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode) or entry.is_dir():
                    fail('unsupported_member', 'Only ordinary files are supported.')
                if entry.flag_bits & 1:
                    fail('encrypted_member', 'Encrypted reports are not supported.')
                if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    fail('compression', 'Unsupported compression method.')
            if 'manifest.json' not in names:
                fail('missing_manifest', 'Archive has no manifest.json.')
            if archive.getinfo('manifest.json').file_size > MAX_JSON_BYTES:
                fail('metadata_too_large', 'Manifest exceeds metadata size limit.')
            manifest = strict_json(archive.read('manifest.json'), 'Manifest')
            files = validate_manifest(manifest, set(names))
            for name, expected in files.items():
                if archive.getinfo(name).file_size != expected['bytes']:
                    fail('size_mismatch', f'File size mismatch: {name}')
                payload = archive.read(name)
                if hashlib.sha256(payload).hexdigest() != expected['sha256']:
                    fail('hash_mismatch', f'File content changed: {name}')
            report = strict_json(archive.read('report.json'), 'Report')
            validate_report(report, manifest)
            return {
                'valid': True,
                'run_id': manifest['run_id'],
                'file_count': len(entries),
                'expanded_bytes': sum(entry.file_size for entry in entries),
                'report': report,
                'note': 'Integrity verified; authorship and medical validity are not verified.',
            }
    except VerificationError:
        raise
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, OSError, ValueError):
        fail('invalid_zip', 'Archive is corrupt or cannot be read.')
