#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path('/Users/jsedy/jsedy.com website/jsedy.com')
KB = ROOT / 'knowledgebase' / 'projects' / 'howlops' / 'competitors-research'
OUT = ROOT / 'data' / 'read_research.json'

HEADING_RE = re.compile(r'^##\s+(.+?)\s*$')
BULLET_RE = re.compile(r'^-\s+(.*\S)\s*$')
NUM_LINK_RE = re.compile(r'^\d+\.\s+\[(.+?)\]\((.+?)\)')
INLINE_CODE_RE = re.compile(r'`([^`]+)`')


def run_git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(ROOT / 'knowledgebase'), *args], text=True).strip()


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def clean(text: str) -> str:
    text = INLINE_CODE_RE.sub(r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def slug_to_title(slug: str) -> str:
    return ' '.join(part.capitalize() for part in slug.split('-'))


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = '_preamble'
    sections[current] = []
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)
    return sections


def bullets(section_lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in section_lines:
        m = BULLET_RE.match(line)
        if m:
            items.append(clean(m.group(1)))
    return items


def first_paragraph(section_lines: list[str]) -> str:
    buf: list[str] = []
    started = False
    for line in section_lines:
        raw = line.strip()
        if not raw:
            if started and buf:
                break
            continue
        if raw.startswith('- ') or re.match(r'^\d+\.\s', raw):
            if started and buf:
                break
            continue
        buf.append(raw)
        started = True
    return clean(' '.join(buf))


def readme_meta(path: Path) -> dict:
    text = read_text(path)
    lines = text.splitlines()
    sections = split_sections(lines)
    meta = {
        'title': slug_to_title(path.parent.name),
        'slug': path.parent.name,
        'rotation_status': None,
        'last_checked': None,
        'covered_topics': [],
        'key_findings': [],
        'howlops_messaging': [],
        'claim_checks': [],
        'revenue_status': 'Veřejně ověřený roční revenue údaj zatím v current research není.',
    }
    for line in lines[:10]:
        line = line.strip()
        if line.startswith('# '):
            meta['title'] = clean(line[2:])
        elif 'status v rotaci:' in line:
            meta['rotation_status'] = clean(line.split(':', 1)[1])
        elif 'naposledy zkontrolováno:' in line:
            meta['last_checked'] = clean(line.split(':', 1)[1])

    for line in sections.get('Co už bylo pokryto', []):
        m = NUM_LINK_RE.match(line.strip())
        if m:
            meta['covered_topics'].append({'title': clean(m.group(1)), 'path': m.group(2)})

    meta['key_findings'] = bullets(sections.get('Dosud nejvýraznější zjištění', []))[:6]
    meta['claim_checks'] = [clean(x) for x in sections.get('Claim-checks vůči lokálnímu repo HowlOps', []) if x.strip().startswith('### ')][:6]

    messaging_lines = sections.get('Doporučená změna messagingu pro HowlOps', [])
    msg = bullets(messaging_lines)
    if not msg:
        para = first_paragraph(messaging_lines)
        if para:
            msg = [para]
    meta['howlops_messaging'] = msg[:5]

    lowered = text.lower()
    revenue_hits = []
    for pattern in ['arr', 'mrr', 'revenue', 'annual revenue', 'funding', 'valuation']:
        if pattern in lowered:
            revenue_hits.append(pattern)
    if revenue_hits:
        meta['revenue_status'] = 'Nalezeny komerční/revenue zmínky v research souborech; vyžadují ruční ověření v detailních položkách.'
    return meta


def feature_meta(path: Path, competitor_slug: str) -> dict:
    text = read_text(path)
    lines = text.splitlines()
    sections = split_sections(lines)
    title = clean(lines[0][2:]) if lines and lines[0].startswith('# ') else slug_to_title(path.stem)
    researched_at = None
    primary_urls: list[str] = []
    for line in lines[:12]:
        stripped = line.strip()
        if 'prozkoumáno:' in stripped:
            researched_at = clean(stripped.split(':', 1)[1])
    # primary URLs block
    for i, line in enumerate(lines[:20]):
        if line.strip().startswith('- primární_url:'):
            for sub in lines[i+1:i+8]:
                s = sub.strip()
                if s.startswith('- '):
                    primary_urls.append(clean(s[2:]))
                else:
                    break
            break

    summary = first_paragraph(sections.get('1. Co to je', [])) or first_paragraph(sections.get('Co to je', []))
    pricing_points = bullets(sections.get('5. Ceny / dostupnost v plánech', []))[:4]
    howlops_points = bullets(sections.get('7. Proč na tom záleží pro HowlOps', []))[:4]
    if not howlops_points:
        howlops_points = bullets(sections.get('7. Proč je to důležité pro HowlOps', []))[:4]
    git_rel = str(path.relative_to(ROOT / 'knowledgebase'))
    last_commit_date = run_git('log', '-1', '--date=short', '--format=%ad', '--', git_rel)
    last_commit_subject = run_git('log', '-1', '--format=%s', '--', git_rel)
    return {
        'slug': path.stem,
        'title': title,
        'path': f'features/{path.name}',
        'researched_at': researched_at,
        'summary': summary,
        'pricing_points': pricing_points,
        'howlops_points': howlops_points,
        'primary_urls': primary_urls,
        'last_commit_date': last_commit_date,
        'last_commit_subject': last_commit_subject,
        'competitor_slug': competitor_slug,
    }


def competitor_meta(dir_path: Path) -> dict:
    readme = dir_path / 'README.md'
    meta = readme_meta(readme)
    rel_dir = str(dir_path.relative_to(ROOT / 'knowledgebase'))
    meta['last_commit_date'] = run_git('log', '-1', '--date=short', '--format=%ad', '--', rel_dir)
    meta['last_commit_subject'] = run_git('log', '-1', '--format=%s', '--', rel_dir)
    features_dir = dir_path / 'features'
    features = []
    if features_dir.exists():
        for path in sorted(features_dir.glob('*.md')):
            features.append(feature_meta(path, dir_path.name))
    meta['features'] = features
    pricing_feature = next((f for f in features if f['slug'] == 'pricing-and-plan-gates'), None)
    if pricing_feature and pricing_feature['pricing_points']:
        meta['commercial_snapshot'] = pricing_feature['pricing_points']
    else:
        meta['commercial_snapshot'] = []
    if not any('revenue' in json.dumps(f, ensure_ascii=False).lower() for f in features):
        meta['revenue_status'] = 'Veřejně ověřený roční revenue údaj zatím v current research není.'
    return meta


def main() -> None:
    competitors: dict[str, dict] = {}
    for dir_path in sorted(p for p in KB.iterdir() if p.is_dir() and (p / 'README.md').exists()):
        competitors[dir_path.name] = competitor_meta(dir_path)
    payload = {
        'generated_from': str(KB),
        'competitors': competitors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
