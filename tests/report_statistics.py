"""Count normalized Unicode text; generated docs and binary media are separate."""
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = ['app.py', 'db.py', 'schema.sql', 'static/style.css', 'static/script.js']
files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'templates').glob('*.html'))]
rows = []
for name in files:
    content = (ROOT/name).read_text(encoding='utf-8')
    rows.append(dict(file=name, lines=len(content.splitlines()), nonempty=sum(bool(s.strip()) for s in content.splitlines()),
                     characters=len(content), bytes=(ROOT/name).stat().st_size))
total = {key: sum(r[key] for r in rows) for key in ['lines', 'nonempty', 'characters', 'bytes']}
result = dict(scope='site source only; line endings normalized to LF; Unicode code points', files=rows, total=total)
(ROOT/'docs/line-statistics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
with (ROOT/'docs/file-statistics.csv').open('w', encoding='utf-8-sig', newline='') as out:
    writer = csv.DictWriter(out, fieldnames=['file', 'lines', 'nonempty', 'characters', 'bytes'])
    writer.writeheader()
    writer.writerows(rows)
table = '| Файл | Строк | Непустых | Символов |\n|---|---:|---:|---:|\n'
table += ''.join(f"| `{r['file']}` | {r['lines']} | {r['nonempty']} | {r['characters']} |\n" for r in rows)
table += f"| **Всего** | **{total['lines']}** | **{total['nonempty']}** | **{total['characters']}** |\n"
text = '# Статистика исходников\n\n05.11.2026. Серверные HTML-шаблоны, JS только для слайдера.\n\n' + table
text += '\nПодсчёт: splitlines(), непустые strip(), символы Unicode с LF. '
text += 'Фото, шрифты, зависимости, тесты, документация и инструменты модуля 4 в объём сайта не входят.\n'
text += f"\nПри 100–120 символах/мин только набор займёт {total['characters']/120:.0f}–{total['characters']/100:.0f} минут. "
text += 'Это арифметическая оценка без настройки, проверки и сборки макета. Целевые 120 минут с запасом не подтверждены. '
text += 'Уменьшение числа переносов строк не уменьшает объём набора.\n'
text += '\nПовторить подсчёт: `python tests/report_statistics.py`. Модуль 4 — редактируемый артефакт, '
text += 'его генератор не предназначен для ручного набора на экзамене. Старые руководства относятся к предыдущей версии.\n'
(ROOT/'docs/STATISTICS.md').write_text(text, encoding='utf-8')
print(table)
