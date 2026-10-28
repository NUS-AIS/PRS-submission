# Repository contribution audit

Snapshot: `8a2afd7b4dbc8a327944662380100a3382fa0de7`. Statistics include commits reachable from this revision only.

| Member | GitHub identity | Commits | Added | Deleted | Net | All additions share | Code additions | Code additions share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | ZhouJiasheng-Jason | 7 | 2,452 | 99 | 2,353 | 20.87% | 1,193 | 22.27% |
| B | SereneTang02 | 6 | 2,664 | 73 | 2,591 | 22.67% | 1,033 | 19.28% |
| C | lwd0110 | 16 | 3,667 | 45 | 3,622 | 31.21% | 471 | 8.79% |
| D | hanjingmu2004-coder | 13 | 2,968 | 95 | 2,873 | 25.26% | 2,661 | 49.66% |

## Source, tests and current line attribution

| Member | Production additions | Test additions | Documentation additions | Other additions | Current source/test lines |
|---|---:|---:|---:|---:|---:|
| A | 925 | 268 | 119 | 1140 | 1060 |
| B | 797 | 236 | 186 | 1445 | 953 |
| C | 471 | 0 | 220 | 2976 | 440 |
| D | 1806 | 855 | 307 | 0 | 2638 |

## Interpretation

- Git additions include blank lines and comments, repeated edits and moved code; they are not effective or unique code lines.
- Code additions include source and tests. Data tables, notebooks, generated reports and document files are excluded from that column.
- Current attribution uses ordinary git blame on source/test files. It counts the last editor, not original authorship or intellectual contribution.
- Merge commits are counted but Git default numstat does not attribute a merged diff again.
- Binary files have no line count. Renames are counted as deletion/addition with --no-renames; this can inflate activity.
- Identities are grouped by email. Zhou Jason and Zhou Jiasheng share the same email and are grouped as A.
- Initial imports and refactoring remain in history totals; totals should not be used alone to assess workload.
- The report does not change Git authors, dates or existing history.

本表统计截至上述快照，不包含保存本统计文档的最后一次提交；最终实时数据请运行 python src/contribution_audit.py。
