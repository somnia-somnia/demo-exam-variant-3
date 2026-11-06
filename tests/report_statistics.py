"""Count normalized Unicode text; generated docs and binary media are separate."""
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = [p.relative_to(ROOT).as_posix() for p in sorted(ROOT.glob('*.py'))]
files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'rental').glob('*.py'))]
files += ['static/style.css', 'static/script.js', 'requirements.txt']
files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'templates').glob('*.html'))]
rows = []
for name in files:
    content = (ROOT/name).read_text(encoding='utf-8')
    rows.append(dict(file=name, lines=len(content.splitlines()), nonempty=sum(bool(s.strip()) for s in content.splitlines()),
                     characters=len(content), bytes=(ROOT/name).stat().st_size))
total = {key: sum(r[key] for r in rows) for key in ['lines', 'nonempty', 'characters', 'bytes']}
optional = (ROOT/'tools/import_legacy.py').read_text(encoding='utf-8')
result = dict(scope='all site runtime source; line endings normalized to LF; Unicode code points', files=rows, total=total,
              optional_legacy_import=dict(characters=len(optional), lines=len(optional.splitlines())))
(ROOT/'docs/line-statistics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
with (ROOT/'docs/file-statistics.csv').open('w', encoding='utf-8-sig', newline='') as out:
    writer = csv.DictWriter(out, fieldnames=['file', 'lines', 'nonempty', 'characters', 'bytes'])
    writer.writeheader()
    writer.writerows(rows)
table = '| Файл | Строк | Непустых | Символов |\n|---|---:|---:|---:|\n'
table += ''.join(f"| `{r['file']}` | {r['lines']} | {r['nonempty']} | {r['characters']} |\n" for r in rows)
table += f"| **Всего** | **{total['lines']}** | **{total['nonempty']}** | **{total['characters']}** |\n"
text = '# Статистика исходников\n\n06.11.2026. Серверные HTML-шаблоны, JS только для слайдера.\n\n' + table
text += '\nПодсчёт: splitlines(), непустые strip(), символы Unicode с LF. '
text += 'Все Python/HTML/CSS/JS исходники сайта и requirements.txt включены. Схему создаёт Django ORM. '
text += 'Фото, шрифты, готовые зависимости, тесты, документация и инструменты модуля 4 считаются отдельно.\n'
text += f"\nПри 100–120 символах/мин только набор займёт {total['characters']/120:.0f}–{total['characters']/100:.0f} минут. "
text += 'Это арифметическая оценка без настройки, проверки и сборки макета. Бюджет 10–12 тысяч символов достигнут; '
text += 'целевые 120 минут на весь экзамен с запасом не подтверждены. '
text += 'Уменьшение числа переносов строк не уменьшает объём набора.\n'
text += '\nПовторить подсчёт: `python tests/report_statistics.py`. Модуль 4 — редактируемый артефакт, '
text += 'его генератор не предназначен для ручного набора на экзамене. Старые руководства относятся к предыдущей версии.\n'
text += '\nDjango + MySQL: публичная главная со слайдером и тремя карточками машин. '
text += 'Фото находятся на главной; формы остаются короткими. Поля Django Forms отвечают за вывод и серверную проверку. '
text += 'Использованы отступы Python по 2 пробела и допустимые некавыченные статические HTML-атрибуты. '
text += 'Никаких закодированных исходников, генерации программы при запуске или выноса логики за пределы счётчика нет.\n'
text += f'\nОдноразовый инструмент импорта старой SQLite: {len(optional)} символов, {len(optional.splitlines())} строк, '
text += 'учтён отдельно. Для нового сайта и запуска он не нужен. SQL в docs/schema.mysql.sql — отчёт SHOW CREATE TABLE, не исходник приложения.\n'
(ROOT/'docs/STATISTICS.md').write_text(text, encoding='utf-8')
print(table)
