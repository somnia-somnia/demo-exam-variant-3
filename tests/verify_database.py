"""Verify real MySQL metadata; generate SQL and ER artifacts from a fresh DB."""
import os
import sys
import json
from html import escape
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.mysql_support import Database

database = Database()
os.environ['MYSQL_DATABASE'] = database.name
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config')
import django
django.setup()
from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from rental.models import User, Booking, Review

try:
    call_command('migrate', run_syncdb=True, interactive=False, verbosity=0)
    tables, ddl = {}, []
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        version = cursor.fetchone()[0]
        for name in ('users', 'bookings', 'reviews'):
            cursor.execute(f'SHOW FULL COLUMNS FROM `{name}`')
            columns = [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]
            constraints = connection.introspection.get_constraints(cursor, name)
            assert any(c['primary_key'] for c in constraints.values()), name
            cursor.execute(f'SHOW CREATE TABLE `{name}`')
            ddl.append(cursor.fetchone()[1]+';')
            tables[name] = dict(columns=columns, constraints=constraints)
        cursor.execute('CHECK TABLE users,bookings,reviews')
        integrity = cursor.fetchall()
        assert all(row[-1] == 'OK' for row in integrity)
    assert any(c['foreign_key'] == ('users','id') for c in tables['bookings']['constraints'].values())
    assert any(c['foreign_key'] == ('bookings','id') for c in tables['reviews']['constraints'].values())
    assert any(c['unique'] and c['columns'] == ['login_key'] for c in tables['users']['constraints'].values())
    try:
        with transaction.atomic():
            Booking.objects.create(user_id=999, car='LADA Vesta', payment='Наличными',start_date='2026-12-02')
    except IntegrityError:
        pass
    else:
        raise AssertionError('FK accepted missing user')
    report = dict(result='PASS', engine='MySQL', version=version, tables=tables,
                  integrity=integrity, orphan_insert='rejected', er_source='SHOW FULL COLUMNS and Django MySQL introspection')
    (ROOT/'docs/db-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/schema.mysql.sql').write_text('-- Generated reference, not executed at startup; Django ORM creates tables.\n\n'+'\n\n'.join(ddl)+'\n',encoding='utf-8')
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="520" viewBox="0 0 1120 520">',
        '<rect width="1120" height="520" fill="#f8f9fa"/><g font-family="Arial,sans-serif" fill="#212b36">',
        '<text x="30" y="40" font-size="24">Ключ.на.старт · ER из метаданных MySQL</text>',
        '<text x="30" y="72" font-size="14">PK — первичный ключ · FK — внешний ключ · UK — уникальный ключ</text>']
    mermaid = ['erDiagram','    users ||--o{ bookings : creates','    bookings ||--o{ reviews : receives']
    for index,(name,meta) in enumerate(tables.items()):
        x=30+380*index
        svg += [f'<rect x="{x}" y="105" width="290" height="330" rx="8" fill="white" stroke="#212b36"/>',
                f'<text x="{x+16}" y="135" font-size="21" fill="#d9480f">{name}</text>']
        mermaid.append('    '+name+' {')
        for i,col in enumerate(meta['columns']):
            flags=[]
            for c in meta['constraints'].values():
                if col['Field'] in c['columns']:
                    for flag,condition in [('PK',c['primary_key']),('FK',bool(c['foreign_key'])),('UK',c['unique'] and not c['primary_key'])]:
                        if condition and flag not in flags: flags.append(flag)
            label=col['Field']+' '+col['Type']+(' · '+','.join(flags) if flags else '')
            svg.append(f'<text x="{x+16}" y="{170+30*i}" font-size="16">{escape(label)}</text>')
            mermaid.append('        '+col['Type'].replace('(','_').replace(')','')+' '+col['Field']+(' '+','.join(flags) if flags else ''))
        mermaid.append('    }')
    svg += ['<path d="M320 260H410 M700 260H790" fill="none" stroke="#212b36" stroke-width="2"/>',
        '<text x="330" y="245" font-size="13">1 → 0..N</text><text x="710" y="245" font-size="13">1 → 0..N</text>',
        '<text x="30" y="480" font-size="14">login_key = SHA-256(lower(login)); отзыв принадлежит владельцу через заявку.</text></g></svg>']
    (ROOT/'docs/er.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
    (ROOT/'docs/er.mmd').write_text('\n'.join(mermaid)+'\n',encoding='utf-8')
    print('PASS: MySQL '+version+', PK/FK/UNIQUE, CHECK TABLE, orphan rejected, SQL/ER generated')
finally:
    connection.close()
    database.close()
