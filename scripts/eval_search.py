#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
import requests


def load_jsonl(path: Path):
    out = []
    if not path.exists():
        return out
    for ln in path.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        out.append(json.loads(ln))
    return out


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
    token = sys.argv[2] if len(sys.argv) > 2 else ''
    if not token:
        print('Usage: eval_search.py <base_url> <token>')
        sys.exit(1)

    qset = load_jsonl(Path('bench/queries.jsonl'))
    gold = {x['id']: x for x in load_jsonl(Path('bench/golden.jsonl'))}

    headers = {'Authorization': f'Bearer {token}'}
    total = len(qset)
    hit = 0
    mrr_sum = 0.0

    for q in qset:
        params = {
            'q': q['query'],
            'limit': q.get('k', 5),
            'explain': 'true',
        }
        for t in q.get('tags', []):
            # backend supports repeated tags; requests params list style
            pass
        r = requests.get(base + '/memory', headers=headers, params=params, timeout=15)
        r.raise_for_status()
        items = r.json().get('data', {}).get('results', [])

        g = gold.get(q['id'], {})
        exp_tags = g.get('expected_tags', [])
        exp_kw = g.get('expected_keywords', [])

        rank = None
        for i, it in enumerate(items, start=1):
            ok = False
            if exp_tags and any(t in (it.get('tags') or []) for t in exp_tags):
                ok = True
            if exp_kw:
                txt = (it.get('text') or '').lower()
                if any(k.lower() in txt for k in exp_kw):
                    ok = True
            if ok:
                rank = i
                break

        if rank is not None:
            hit += 1
            mrr_sum += 1.0 / rank

    recall = hit / total if total else 0.0
    mrr = mrr_sum / total if total else 0.0
    print(json.dumps({
        'total_queries': total,
        'hit_queries': hit,
        'recall_at_k': round(recall, 4),
        'mrr': round(mrr, 4),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
