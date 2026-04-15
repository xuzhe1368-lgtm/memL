# AGENTS.md - memL Repository Rules

## Memory Migration Guardrail (Mandatory)

When any agent migrates memory files in this repo, it MUST follow this exact method:

1. Read files with `encoding="utf-8-sig"` and `errors="replace"`.
2. Normalize text with Unicode NFC.
3. Remove illegal control chars: `[\x00-\x08\x0B\x0C\x0E-\x1F]` (keep `\n\r\t`).
4. Only parse JSON for `.json` / `.jsonl` after cleaning.
5. Never run `json.loads()` on `.md` files.
6. Markdown must be treated as plain text and chunked by heading/paragraph.
7. Per-file failure must be logged and skipped; do not abort whole migration.

Default migration entrypoint:
- `python scripts/migrate_memory_safe.py --input <path> --output migration_output.jsonl`
