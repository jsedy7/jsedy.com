#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = ROOT / 'knowledgebase' / 'projects' / 'howlops'
COMP_ROOT = KB_ROOT / 'competitors-research'
RESEARCH_ROOT = KB_ROOT / 'research'
READ_DATA = ROOT / 'data' / 'read_research.json'
OUT = ROOT / 'data' / 'summary_research.json'

SECTION_RE = re.compile(r'^##\s+(.+?)\s*$')
BULLET_RE = re.compile(r'^-\s+(.*\S)\s*$')
INLINE_CODE_RE = re.compile(r'`([^`]+)`')
LINK_RE = re.compile(r'\[(.*?)\]\((.*?)\)')
CURRENCY_RE = re.compile(r'(\$\d+[\d,.]*(?:/month|/mo)?|€\d+[\d,.]*(?:/month|/mo)?|£\d+[\d,.]*(?:/month|/mo)?)')
REVENUE_HINT_RE = re.compile(r'\b(arr|mrr|revenue|annual revenue|funding|valuation|employees?|run rate)\b', re.I)


def clean(text: str) -> str:
    text = INLINE_CODE_RE.sub(r'\1', text)
    text = LINK_RE.sub(r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def title_from_slug(slug: str) -> str:
    return ' '.join(part.capitalize() for part in slug.split('-'))


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = text.replace('&', ' and ')
    text = text.replace('/', ' ')
    text = text.replace('.', ' ')
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {'_preamble': []}
    current = '_preamble'
    for line in lines:
        m = SECTION_RE.match(line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)
    return sections


def bullets(section_lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in section_lines:
        m = BULLET_RE.match(line.strip())
        if m:
            out.append(clean(m.group(1)))
    return out


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


def section_text(text: str, heading: str) -> str:
    m = re.search(rf'## {re.escape(heading)}\n(.*?)(?=\n## |\Z)', text, re.S)
    return m.group(1).strip() if m else ''


def run_git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(ROOT / 'knowledgebase'), *args], text=True).strip()


def load_read_data() -> dict[str, dict]:
    if not READ_DATA.exists():
        return {}
    payload = json.loads(READ_DATA.read_text(encoding='utf-8'))
    return payload.get('competitors', {})


def latest_revalidation_files(slugs: set[str]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(RESEARCH_ROOT.glob('*.md')):
        text = path.read_text(encoding='utf-8', errors='ignore')
        m = re.search(r'-\s*konkurenti:\s*(.+)', text)
        if not m:
            continue
        raw = clean(m.group(1))
        if ',' in raw:
            continue
        candidate = slugify(raw)
        if candidate not in slugs:
            continue
        found[candidate] = path
    return found


def verdict_category(verdict: str) -> str:
    v = verdict.lower()
    if 'horší pro howlops' in v or 'za ' in v or 'slabší' in v:
        return 'weaker'
    if 'lepší pro howlops' in v and 'částečně' not in v and 'stejný' not in v:
        return 'stronger'
    if 'částečně lepší' in v or 'stejný' in v:
        return 'mixed'
    return 'mixed'


def split_labelled_items(line: str, label: str) -> list[str]:
    line = clean(line)
    line = re.sub(rf'^(?:\*\*)?{re.escape(label)}:(?:\*\*)?\s*', '', line, flags=re.I).strip()
    if not line:
        return []
    parts = [clean(part.strip(' .')) for part in line.split(';') if part.strip()]
    return [p for p in parts if p]


def extract_financial_signals(comp_dir: Path) -> tuple[list[str], list[str]]:
    price_signals: list[str] = []
    revenue_signals: list[str] = []
    for path in sorted(comp_dir.glob('features/*.md')):
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        for line in lines:
            s = clean(line)
            if not s:
                continue
            if s.startswith('-'):
                s = s.lstrip('-').strip()
            lower = s.lower()
            if CURRENCY_RE.search(s) and ('plan' in lower or 'free' in lower or 'team' in lower or 'enterprise' in lower or 'solo' in lower):
                if s not in price_signals:
                    price_signals.append(s)
            has_finance = bool(REVENUE_HINT_RE.search(s))
            if has_finance:
                if 'evidence url' in lower:
                    continue
                if s not in revenue_signals:
                    revenue_signals.append(s)
    return price_signals[:5], revenue_signals[:5]


def top_actions(readme_text: str, latest_text: str) -> list[str]:
    actions: list[str] = []
    backlog = section_text(readme_text, 'Kandidátní zbývající oblasti funkcí / backlog')
    actions.extend(bullets(backlog.splitlines()))
    msg = section_text(readme_text, 'Doporučená změna messagingu pro HowlOps')
    msg_bullets = bullets(msg.splitlines())
    if msg_bullets:
        actions.extend(msg_bullets)
    else:
        para = first_paragraph(msg.splitlines())
        if para:
            actions.append(para)
    if not actions and latest_text:
        missing_block = section_text(latest_text, 'Shipped / in-progress / missing / neověřené') or section_text(latest_text, 'Shipped / in-progress / missing')
        for item in bullets(missing_block.splitlines()):
            if clean(item).lower().startswith('missing:'):
                actions.extend(split_labelled_items(item, 'missing'))
    return actions[:5]


def stronger_note(category: str, verdict: str) -> str:
    if category == 'stronger':
        return 'Aktuální corpus naznačuje, že HowlOps je proti tomuto produktu přesvědčivější v užším prodávaném use case.'
    if category == 'weaker':
        return 'Aktuální corpus říká, že HowlOps proti tomuto produktu zatím spíš dohání šíři, hloubku nebo trust vrstvu.'
    return 'Aktuální corpus je smíšený: HowlOps má dílčí výhody, ale ne čistý celkový náskok.'


def price_potential_note(category: str, price_signals: list[str], revenue_signals: list[str]) -> str:
    if price_signals:
        anchor = price_signals[0]
        if category == 'weaker':
            return f'Veřejný pricing anchor existuje ({anchor}). Dokud HowlOps proti této třídě produktu neuzavře hlavní gapy, je bezpečnější prodávat úzký pilot / team use case než se tvářit jako plná náhrada.'
        if category == 'stronger':
            return f'Veřejný pricing anchor existuje ({anchor}). Pokud HowlOps prodává hlubší incident/on-call hodnotu, může se kotvit podle týmového výsledku a ne podle nejnižší solo ceny.'
        return f'Veřejný pricing anchor existuje ({anchor}). Současný corpus spíš podporuje founder-led team pricing než čistý low-end uptime checker positioning.'
    if revenue_signals:
        return 'V corpus jsou komerční nebo revenue signály, ale bez dost přesných veřejných cenových anchorů pro poctivý exact pricing návrh. Vhodnější je zatím pilot/team positioning.'
    return 'V current corpus chybí dost přesné veřejné pricing anchor body pro poctivý exact price recommendation. Bezpečnější je řídit se narrow-use-case pilot prodejem a ověřit willingness-to-pay na prvních klientech.'


def extract_summary(latest_text: str) -> tuple[str, list[str], list[str], str]:
    verdict = ''
    m = re.search(r'## Verdikt\n\*\*(.+?)\*\*', latest_text, re.S)
    if m:
        verdict = clean(m.group(1).splitlines()[0])
    lagging: list[str] = []
    shipped: list[str] = []
    block = section_text(latest_text, 'Shipped / in-progress / missing / neověřené') or section_text(latest_text, 'Shipped / in-progress / missing')
    for item in bullets(block.splitlines()):
        cleaned = clean(item).lower()
        if cleaned.startswith('missing:'):
            lagging.extend(split_labelled_items(item, 'missing'))
        elif cleaned.startswith('shipped:'):
            shipped.extend(split_labelled_items(item, 'shipped'))
    changed_block = section_text(latest_text, 'Co se oproti starším závěrům zpřesnilo')
    changes = []
    for line in changed_block.splitlines():
        line = line.strip()
        if re.match(r'^\d+\.\s+\*\*', line):
            changes.append(clean(re.sub(r'^\d+\.\s*', '', line)))
    return verdict, lagging[:6], changes[:5], ', '.join(shipped[:6])


def overall_sellability() -> dict:
    readiness = (KB_ROOT / 'howlops-readiness-for-first-clients-checklist.md').read_text(encoding='utf-8', errors='ignore')
    pricing = (RESEARCH_ROOT / '2026-06-10_21_pricing-clarity.md').read_text(encoding='utf-8', errors='ignore')
    priorities = []
    m = re.search(r'order priorit:\n1\.\s*(.+?)\n2\.\s*(.+?)\n3\.\s*(.+?)\n4\.\s*(.+?)\n5\.\s*(.+?)\n', readiness, re.S)
    if m:
        priorities = [clean(m.group(i)) for i in range(1, 6)]
    else:
        priorities = ['alert reliability', 'debugability / audit trail', 'noise control / anti-flood', 'onboarding clarity']
    posture = 'Current evidence supports founder-led pilots and narrow first paying clients sooner than broad self-serve scale.'
    risk_match = re.search(r'4\) produktový problém vs prezentace / docs / pricing / trust\n(.*?)(?=\n5\)|\Z)', pricing, re.S)
    step_match = re.search(r'5\) 1 doporučený další krok\n(.*?)(?=\Z)', pricing, re.S)
    price_truth = clean(risk_match.group(1)) if risk_match else ''
    next_step = clean(step_match.group(1)) if step_match else ''
    return {
        'sellability_posture': posture,
        'priorities': priorities,
        'pricing_truth_risk': price_truth,
        'pricing_next_step': next_step,
        'not_indexable_note': 'This summary surface is intentionally marked noindex / nofollow.',
    }


def main() -> None:
    read_data = load_read_data()
    slugs = set(read_data.keys()) or {p.name for p in COMP_ROOT.iterdir() if p.is_dir()}
    latest_files = latest_revalidation_files(slugs)

    competitors: dict[str, dict] = {}
    buckets = {'stronger': [], 'mixed': [], 'weaker': []}

    for slug in sorted(slugs):
        comp_dir = COMP_ROOT / slug
        if not comp_dir.exists():
            continue
        readme = comp_dir / 'README.md'
        readme_text = readme.read_text(encoding='utf-8', errors='ignore') if readme.exists() else ''
        latest_path = latest_files.get(slug)
        latest_text = latest_path.read_text(encoding='utf-8', errors='ignore') if latest_path else ''
        verdict, lagging, changes, shipped_text = extract_summary(latest_text)
        category = verdict_category(verdict) if verdict else 'mixed'
        price_signals, revenue_signals = extract_financial_signals(comp_dir)
        read_meta = read_data.get(slug, {})
        last_commit_date = run_git('log', '-1', '--date=short', '--format=%ad', '--', str(comp_dir.relative_to(ROOT / 'knowledgebase')))
        last_commit_subject = run_git('log', '-1', '--format=%s', '--', str(comp_dir.relative_to(ROOT / 'knowledgebase')))
        item = {
            'slug': slug,
            'title': read_meta.get('title') or title_from_slug(slug),
            'description': read_meta.get('description') or '',
            'last_checked': read_meta.get('last_checked'),
            'last_commit_date': last_commit_date,
            'last_commit_subject': last_commit_subject,
            'verdict': verdict or 'No compact verdict extracted yet.',
            'verdict_category': category,
            'where_howlops_lags': lagging or ['Current corpus did not extract a compact missing list yet.'],
            'what_changed': changes,
            'priority_for_howlops': top_actions(readme_text, latest_text) or ['Turn the latest research into a narrower, more truthful buyer-facing story.'],
            'relative_strength_note': stronger_note(category, verdict),
            'stronger_signals': [read_meta.get('revenue_status')] if read_meta.get('revenue_status') else [],
            'public_price_signals': price_signals,
            'public_revenue_signals': revenue_signals,
            'howlops_price_potential': price_potential_note(category, price_signals, revenue_signals),
            'shipped_surface_excerpt': shipped_text,
            'latest_research_file': latest_path.name if latest_path else None,
        }
        competitors[slug] = item
        buckets[category].append({'slug': slug, 'title': item['title'], 'verdict': item['verdict']})

    payload = {
        'generated_from': str(COMP_ROOT),
        'overall': overall_sellability(),
        'buckets': buckets,
        'competitors': competitors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
