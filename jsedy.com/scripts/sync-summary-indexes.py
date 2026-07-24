#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'summary_research.json'
SUMMARY_DIR = ROOT / 'content' / 'en' / 'summary'


def main() -> None:
    payload = json.loads(DATA.read_text(encoding='utf-8'))
    competitors = payload.get('competitors', {})
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    top = SUMMARY_DIR / '_index.md'
    top.write_text(
        '---\n'
        'title: "HowlOps Summary"\n'
        'description: "Private synthesis of competitor research, pricing posture, and HowlOps saleability."\n'
        'robotsNoIndex: true\n'
        '---\n',
        encoding='utf-8',
    )
    for slug, meta in competitors.items():
        title = meta.get('title') or slug.replace('-', ' ').title()
        description = meta.get('description') or f'Private HowlOps synthesis for {title}.'
        target = SUMMARY_DIR / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / '_index.md').write_text(
            '---\n'
            f'title: "{title}"\n'
            f'description: "{description}"\n'
            'robotsNoIndex: true\n'
            '---\n',
            encoding='utf-8',
        )
    print(f'Refreshed {len(competitors)} summary section indexes')


if __name__ == '__main__':
    main()
