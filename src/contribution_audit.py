"""Reproducible Git statistics; additions are activity, not unique authored code."""
import argparse
import collections
import json
import subprocess
from pathlib import Path


CODE_SUFFIXES = {'.py', '.js', '.cjs', '.mjs', '.css', '.html', '.sh', '.ps1', '.ts', '.tsx'}
MEMBERS = {
    'zhouqian2123@gmail.com': ('A', 'ZhouJiasheng-Jason'),
    '235226655+serenetang02@users.noreply.github.com': ('B', 'SereneTang02'),
    '114154623+lwd0110@users.noreply.github.com': ('C', 'lwd0110'),
    '265002037+hanjingmu2004-coder@users.noreply.github.com': ('D', 'hanjingmu2004-coder'),
}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], encoding='utf-8', errors='replace')


def category(path):
    path = Path(path)
    if path.suffix.lower() in CODE_SUFFIXES:
        return 'tests' if 'tests' in path.parts else 'production'
    if path.suffix.lower() in {'.md', '.rst', '.txt'}:
        return 'documentation'
    return 'other'


def identity(email):
    return MEMBERS.get(email.lower(), ('unmapped', email))


def collect(root, revision='HEAD', blame=True):
    resolved = git(root, 'rev-parse', '--verify', revision + '^{commit}').strip()
    rows = {}

    def row_for(email):
        member, account = identity(email)
        key = account
        if key not in rows:
            rows[key] = {'member': member, 'account': account, 'emails': set(), 'names': set(),
                         'commits': 0, 'merge_commits': 0, 'added': 0, 'deleted': 0,
                         'categories': {key: {'added': 0, 'deleted': 0, 'current_lines': 0}
                                        for key in ('production', 'tests', 'documentation', 'other')}}
        rows[key]['emails'].add(email)
        return rows[key]

    history = git(root, 'log', resolved, '--no-renames', '--numstat',
                  '--format=COMMIT%x09%ae%x09%an%x09%P')
    current = None
    for line in history.splitlines():
        if line.startswith('COMMIT\t'):
            _, email, name, parents = line.split('\t', 3)
            current = row_for(email)
            current['names'].add(name)
            current['commits'] += 1
            if len(parents.split()) > 1:
                current['merge_commits'] += 1
        elif '\t' in line and current is not None:
            added, deleted, path = line.split('\t', 2)
            if not added.isdigit() or not deleted.isdigit():
                continue
            kind = category(path)
            for key, value in [('added', int(added)), ('deleted', int(deleted))]:
                current[key] += value
                current['categories'][kind][key] += value
    if blame:
        names = git(root, 'ls-tree', '-rz', '--name-only', resolved).split('\0')
        for path in filter(None, names):
            kind = category(path)
            # Current ownership is limited to textual source/test files.
            if kind not in ('production', 'tests'):
                continue
            output = git(root, 'blame', '--line-porcelain', resolved, '--', path)
            email = None
            for line in output.splitlines():
                if line.startswith('author-mail '):
                    email = line[len('author-mail '):].strip('<>')
                elif line.startswith('\t') and email:
                    row_for(email)['categories'][kind]['current_lines'] += 1
    total_added = sum(row['added'] for row in rows.values())
    total_code_added = sum(row['categories'][kind]['added'] for row in rows.values()
                           for kind in ('production', 'tests'))
    total_current = sum(row['categories'][kind]['current_lines'] for row in rows.values()
                        for kind in ('production', 'tests'))
    for row in rows.values():
        row['names'] = sorted(row['names'])
        row['emails'] = sorted(row['emails'])
        row['net'] = row['added'] - row['deleted']
        row['code_added'] = sum(row['categories'][kind]['added'] for kind in ('production', 'tests'))
        row['current_code_lines'] = sum(row['categories'][kind]['current_lines'] for kind in ('production', 'tests'))
        row['addition_share'] = row['added'] / total_added if total_added else 0
        row['code_addition_share'] = row['code_added'] / total_code_added if total_code_added else 0
        row['current_code_share'] = row['current_code_lines'] / total_current if total_current else None
    return {'revision': resolved, 'blame_included': blame,
            'totals': {'added': total_added, 'code_added': total_code_added, 'current_code_lines': total_current},
            'members': sorted(rows.values(), key=lambda row: (row['member'], row['account']))}


def markdown(audit):
    lines = [
        '# Repository contribution audit', '',
        f"Snapshot: `{audit['revision']}`. Statistics include commits reachable from this revision only.", '',
        '| Member | GitHub identity | Commits | Added | Deleted | Net | All additions share | Code additions | Code additions share |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for row in audit['members']:
        lines.append(f"| {row['member']} | {row['account']} | {row['commits']} | {row['added']:,} | "
                     f"{row['deleted']:,} | {row['net']:,} | {row['addition_share']:.2%} | "
                     f"{row['code_added']:,} | {row['code_addition_share']:.2%} |")
    lines += ['', '## Source, tests and current line attribution', '',
              '| Member | Production additions | Test additions | Documentation additions | Other additions | Current source/test lines |',
              '|---|---:|---:|---:|---:|---:|']
    for row in audit['members']:
        categories = row['categories']
        values = [categories[kind]['added'] for kind in ('production', 'tests', 'documentation', 'other')]
        current = str(row['current_code_lines']) if audit['blame_included'] else 'Not computed'
        lines.append(f"| {row['member']} | " + ' | '.join(map(str, values)) + f' | {current} |')
    lines += ['', '## Interpretation', '',
              '- Git additions include blank lines and comments, repeated edits and moved code; they are not effective or unique code lines.',
              '- Code additions include source and tests. Data tables, notebooks, generated reports and document files are excluded from that column.',
              '- Current attribution uses ordinary git blame on source/test files. It counts the last editor, not original authorship or intellectual contribution.',
              '- Merge commits are counted but Git default numstat does not attribute a merged diff again.',
              '- Binary files have no line count. Renames are counted as deletion/addition with --no-renames; this can inflate activity.',
              '- Identities are grouped by email. Zhou Jason and Zhou Jiasheng share the same email and are grouped as A.',
              '- Initial imports and refactoring remain in history totals; totals should not be used alone to assess workload.',
              '- The report does not change Git authors, dates or existing history.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--revision', default='HEAD')
    parser.add_argument('--skip-blame', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    audit = collect(args.repo, args.revision, not args.skip_blame)
    result = json.dumps(audit, ensure_ascii=False, indent=2) if args.json else markdown(audit)
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result)


if __name__ == '__main__':
    main()
