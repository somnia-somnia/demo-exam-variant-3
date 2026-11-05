"""Verify DB constraints and generate ER from actual SQLite PRAGMA metadata."""
import json
import sqlite3
import tempfile
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from db import DB

with tempfile.TemporaryDirectory() as directory:
    db = DB(str(Path(directory)/'schema.db'))
    db.script((ROOT/'schema.sql').read_text(encoding='utf-8'))
    tables = {}
    for name in ('users', 'bookings', 'reviews'):
        tables[name] = dict(columns=[dict(r) for r in db.all(f'PRAGMA table_info({name})')],
            foreign_keys=[dict(r) for r in db.all(f'PRAGMA foreign_key_list({name})')],
            indexes=[dict(r) for r in db.all(f'PRAGMA index_list({name})')])
    assert db.one('PRAGMA foreign_keys')[0] == 1
    assert db.one('PRAGMA integrity_check')[0] == 'ok'
    assert not db.all('PRAGMA foreign_key_check')
    assert tables['bookings']['foreign_keys'][0]['table'] == 'users'
    assert tables['reviews']['foreign_keys'][0]['table'] == 'bookings'
    report = dict(result='PASS', sqlite_version=sqlite3.sqlite_version, foreign_keys_enabled=1,
                  integrity='ok', foreign_key_check=[], tables=tables,
                  er_source='Actual SQLite PRAGMA table_info / foreign_key_list / index_list; not a GUI export')
    (ROOT/'docs/db-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="460" viewBox="0 0 1120 460">',
           '<rect width="1120" height="460" fill="#f8f9fa"/><g font-family="Arial,sans-serif" fill="#212b36">',
           '<text x="30" y="40" font-size="24">Ключ.на.старт · ER из метаданных SQLite</text>',
           '<text x="30" y="72" font-size="14">PK — первичный ключ · FK — внешний ключ · UK — уникальное значение</text>']
    for index, (name, meta) in enumerate(tables.items()):
        x = 30+380*index
        svg += [f'<rect x="{x}" y="105" width="290" height="285" rx="8" fill="white" stroke="#212b36"/>',
                f'<text x="{x+16}" y="135" font-size="21" fill="#d9480f">{name}</text>']
        unique = set()
        for idx in db.all(f'PRAGMA index_list({name})'):
            if idx['unique']:
                unique.update(r['name'] for r in db.all(f"PRAGMA index_info({idx['name']})"))
        foreign = {r['from'] for r in meta['foreign_keys']}
        for i, column in enumerate(meta['columns']):
            flags = [flag for flag, yes in [('PK', column['pk']), ('FK', column['name'] in foreign), ('UK', column['name'] in unique)] if yes]
            text = escape(column['name']+' '+column['type']+(' · '+', '.join(flags) if flags else ''))
            svg.append(f'<text x="{x+16}" y="{170+29*i}" font-size="16">{text}</text>')
    svg += ['<path d="M320 205H410 M700 205H790" fill="none" stroke="#212b36" stroke-width="2"/>',
            '<text x="330" y="192" font-size="13">1 → 0..N</text><text x="710" y="192" font-size="13">1 → 0..1</text>',
            '<text x="30" y="430" font-size="14">Один отзыв на заявку; владельца отзыва определяет связь с заявкой.</text></g></svg>']
    (ROOT/'docs/er.svg').write_text('\n'.join(svg)+'\n', encoding='utf-8')
    db.close()
print('PASS: SQLite metadata, integrity, FK, generated ER')
