"""CLI: verify an exported ZIP or compare two verified reports; no model assets needed."""
import argparse
import json
import sys
from pathlib import Path

from pulmo_review_compare import compare_reports
from pulmo_review_verify import MAX_ARCHIVE_BYTES, VerificationError, inspect_archive


def load_verified(path):
    path = Path(path)
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise VerificationError('archive_size', 'Review archive exceeds 64 MB.')
    with path.open('rb') as source:
        data = source.read(MAX_ARCHIVE_BYTES + 1)
    return inspect_archive(data)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    subcommands = cli.add_subparsers(dest='command', required=True)
    verify = subcommands.add_parser('verify', help='Check archive membership, sizes, hashes and schema')
    verify.add_argument('archive', type=Path)
    verify.add_argument('--include-report', action='store_true', help='Print embedded report including any clinical inputs')
    compare = subcommands.add_parser('compare', help='Compare two independently verified archives')
    compare.add_argument('left', type=Path)
    compare.add_argument('right', type=Path)
    for command in (verify, compare):
        command.add_argument('--output', type=Path, help='Write JSON to a new file; existing files are not overwritten')
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'verify':
            result = load_verified(args.archive)
            if not args.include_report:
                result.pop('report', None)
        else:
            left = load_verified(args.left)['report']
            right = load_verified(args.right)['report']
            result = compare_reports(left, right)
        serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            with args.output.open('x', encoding='utf-8') as destination:
                destination.write(serialized + '\n')
        else:
            print(serialized)
        return 0
    except VerificationError as exc:
        print(json.dumps({'valid': False, 'code': exc.code, 'detail': str(exc)}), file=sys.stderr)
        return 2
    except OSError as exc:
        print(json.dumps({'valid': False, 'code': 'file_error', 'detail': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
