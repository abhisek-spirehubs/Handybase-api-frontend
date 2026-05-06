#!/usr/bin/env python3
"""
Scan Django templates under frontend/templates and insert '{% load i18n %}'
if missing. The tag will be placed after an {% extends %} line when present,
otherwise at the top of the file. Creates a .bak backup for each modified file
for safety and prints a summary.

Run: python3 frontend/scripts/add_i18n.py
"""
import io
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'templates'

def process_file(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    if '{% load i18n %}' in text:
        return False

    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('{% extends'):
            insert_at = i + 1
            break
        # if file already has other load tags, insert after them
        if stripped.startswith('{% load'):
            insert_at = i + 1
            break

    new_lines = lines[:insert_at] + ['{% load i18n %}'] + lines[insert_at:]
    # backup
    bak = path.with_suffix(path.suffix + '.bak')
    path.rename(bak)
    path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    return True

def main():
    modified = []
    if not ROOT.exists():
        print(f"Templates root not found: {ROOT}")
        return

    for dirpath, dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            if not fn.endswith('.html'):
                continue
            p = Path(dirpath) / fn
            try:
                changed = process_file(p)
            except Exception as e:
                print(f"Error processing {p}: {e}")
                continue
            if changed:
                modified.append(str(p.relative_to(ROOT.parent)))

    print('\nModified templates:')
    for m in modified:
        print(' -', m)
    print(f'Total modified: {len(modified)}')

if __name__ == '__main__':
    main()
