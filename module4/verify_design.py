"""Check the delivered Sketch ZIP. Structural PASS does not mean native playback PASS."""
from pathlib import Path
from collections import Counter
from xml.etree import ElementTree as ET
import hashlib, io, json, math, struct, zipfile
import jsonschema
from PIL import Image, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MEDIA = ROOT / 'source' / 'Медиа' / 'Медиа'


def postscript_names(path):
    """Read TrueType nameID 6 without installing fontTools."""
    data = path.read_bytes()
    for i in range(struct.unpack_from('>H', data, 4)[0]):
        tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12 + 16*i)
        if tag == b'name':
            break
    else:
        raise AssertionError('Missing TTF name table')
    _, count, strings = struct.unpack_from('>HHH', data, offset)
    names = set()
    for i in range(count):
        platform, _, _, name_id, length, pos = struct.unpack_from('>HHHHHH', data, offset + 6 + i*12)
        if name_id == 6:
            raw = data[offset + strings + pos:offset + strings + pos + length]
            names.add(raw.decode('utf-16-be' if platform in (0, 3) else 'mac_roman'))
    return names


def walk(layers, ox=0, oy=0, shown=True, ancestors=()):
    for layer in layers:
        f = layer['frame']; x, y = ox + f['x'], oy + f['y']
        visible = shown and layer['isVisible']
        yield layer, x, y, visible, ancestors
        yield from walk(layer.get('layers', []), x, y, visible, ancestors + (layer,))


def source_texts():
    with zipfile.ZipFile(ROOT / 'docs' / 'original' / 'Текст.docx') as z:
        root = ET.fromstring(z.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    screens = [[], []]; index = None
    for p in root.findall('.//w:p', ns):
        value = ''.join(t.text or '' for t in p.findall('.//w:t', ns)).strip()
        if not value:
            continue
        if value in ('Экран 1', 'Экран 2'):
            index = int(value[-1]) - 1; continue
        assert index is not None
        if value.startswith(('Меню навигации:', 'Кнопки:')):
            screens[index].extend(t.strip() for t in value.split(':', 1)[1].split(','))
        elif value.startswith('Кнопка:'):
            screens[index].append(value.split(':', 1)[1].strip())
        elif value != 'Окно поиска':
            screens[index].append(value)
    return screens


def rgb(c):
    return tuple(round(c[k]*255) for k in ('red', 'green', 'blue'))


def luminance(c):
    v = [n/255 for n in c]
    v = [n/12.92 if n <= .04045 else ((n+.055)/1.055)**2.4 for n in v]
    return .2126*v[0] + .7152*v[1] + .0722*v[2]


def contrast(a, b):
    l1, l2 = sorted((luminance(a), luminance(b)))
    return (l2+.05)/(l1+.05)


archive = HERE / 'Группа-Таймыр.sketch'
schema_path = HERE / 'sketch-file-format-6.5.0.schema.json'
# Compared byte-for-byte with the published 6.5.0 package during this audit.
schema_sha256 = hashlib.sha256(schema_path.read_bytes()).hexdigest()
assert schema_sha256 == '563e7d563cdb4eae44a60f06f7bea7ae42cba415d094b918798753e43bcdd988'
schema = json.loads(schema_path.read_text(encoding='utf-8'))
assert schema['$id'].endswith('@6.5.0/dist/file-format.schema.json')
font_names = {}
for weight in ('Regular', 'Bold'):
    name = 'Roboto-' + weight; path = HERE / 'assets' / (name + '.ttf')
    assert path.read_bytes() == (MEDIA / 'Roboto' / 'Roboto' / path.name).read_bytes()
    font_names[name] = sorted(postscript_names(path)); assert name in font_names[name]

source = source_texts()
styles, ids, board_stats, contrast_rows = set(), set(), [], []
visible_count = hidden_count = flow_count = button_count = bitmap_count = layer_count = 0
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == len(set(z.namelist())) and z.testzip() is None
    document, meta, user = (json.loads(z.read(n + '.json')) for n in ('document', 'meta', 'user'))
    pages = []
    for ref in document['pages']:
        assert ref['_class'] == 'MSJSONFileReference' and ref['_ref_class'] == 'MSImmutablePage'
        pages.append(json.loads(z.read(ref['_ref'] + '.json')))
    jsonschema.Draft7Validator(schema).validate({'document': {**document, 'pages': pages}, 'meta': meta, 'user': user})
    assert meta['version'] == 146 and len(pages) == 1
    boards = pages[0]['layers']
    assert len(boards) == 2 and all(a['_class'] == 'artboard' for a in boards)
    assert boards[0]['isFlowHome'] and not boards[1]['isFlowHome']
    assert z.read('images/logo.png') == (MEDIA / 'Логотип_полный.png').read_bytes()
    assert z.read('images/photo.jpg') == (HERE / 'assets' / 'photo.jpg').read_bytes()
    assert (HERE / 'assets' / 'photo-original.jpg').read_bytes() == (MEDIA / 'large.jpg').read_bytes()
    expected_photo = io.BytesIO()
    ImageOps.fit(Image.open(MEDIA / 'large.jpg').convert('RGB'), (796, 220)).save(expected_photo, format='JPEG', quality=94)
    assert z.read('images/photo.jpg') == expected_photo.getvalue()
    for index, board in enumerate(boards):
        assert (board['frame']['width'], board['frame']['height']) == (430, 932)
        assert board['prototypeViewport']['size'] == '{430, 932}'
        assert board['name'] == ('01 · Главная', '02 · Решения')[index]
        grid = board['layout']
        assert grid['isEnabled'] and grid['numberOfColumns'] == 4 and grid['columnWidth'] == 89
        assert grid['gutterWidth'] == 14 and grid['horizontalOffset'] == 16 and grid['totalWidth'] == 398
        assert 16 + 4*89 + 3*14 + 16 == 430
        records = list(walk(board['layers'])); expected = source[index].copy()
        if index == 0:
            expected.insert(2, 'Поиск по продуктам')
        actual, hidden, bottoms, rects = [], [], [], []
        board_buttons, search_fields = [], []
        for record_index, (a, x, y, visible, ancestors) in enumerate(records):
            layer_count += 1; assert a['do_objectID'] not in ids; ids.add(a['do_objectID'])
            f = a['frame']
            assert all(math.isfinite(f[k]) for k in ('x', 'y', 'width', 'height'))
            assert f['width'] > 0 and f['height'] > 0
            assert x >= 0 and y >= 0 and x + f['width'] <= 430 + 1e-8 and y + f['height'] <= 932 + 1e-8, (a['name'], f)
            if ancestors:
                parent = ancestors[-1]['frame']
                assert f['x'] >= 0 and f['y'] >= 0 and f['x']+f['width'] <= parent['width']+1e-8 and f['y']+f['height'] <= parent['height']+1e-8, (a['name'], 'outside parent')
            if a['name'] == 'Поиск / поле':
                search_fields.append([x, y, f['width'], f['height']])
            st = a.get('style', {})
            if st:
                assert st['contextSettings']['opacity'] == 1 and st['contextSettings']['blendMode'] == 0
                assert not any(e.get('isEnabled') for k in ('shadows', 'innerShadows') for e in st.get(k, []))
                for k in ('fills', 'borders'):
                    for e in st.get(k, []):
                        if e['isEnabled']:
                            assert e['contextSettings']['opacity'] == 1 and e['color']['alpha'] == 1
            if visible:
                bottoms.append(y + f['height'])
            if a['_class'] in ('rectangle', 'oval'):
                assert a['isClosed'] and len(a['points']) == 4
            if a['_class'] == 'text':
                value = a['attributedString']['string']; runs = a['attributedString']['attributes']
                assert len(runs) == 1 and runs[0]['location'] == 0
                assert runs[0]['length'] == len(value.encode('utf-16-le'))//2
                attrs = runs[0]['attributes']; assert attrs == st['textStyle']['encodedAttributes']
                ft = attrs['MSAttributedStringFontAttribute']['attributes']
                assert ft['name'] in font_names and ft['size'] >= 14
                lines = a['userInfo']['org.exam.module4']['referenceLines']
                line_height = attrs['paragraphStyle']['minimumLineHeight']
                styles.add((ft['name'], ft['size'], line_height))
                assert attrs['paragraphStyle']['maximumLineHeight'] == line_height
                assert ' '.join(' '.join(lines).split()) == ' '.join(value.split())
                assert f['height'] == len(lines)*line_height
                font = ImageFont.truetype(str(HERE / 'assets' / (ft['name']+'.ttf')), ft['size'])
                assert max(font.getlength(t) for t in lines) <= f['width']
                assert sum(font.getmetrics()) <= line_height, (value, font.getmetrics(), line_height)
                if visible:
                    actual.append(value); visible_count += 1
                    rects.append((value, x, y, f['width'], f['height']))
                    background = rgb(board['backgroundColor'])
                    for prior, px, py, pv, _ in records[:record_index]:
                        pf = prior['frame']; fills = prior.get('style', {}).get('fills', [])
                        if pv and prior['_class'] == 'rectangle' and px <= x and py <= y and px+pf['width'] >= x+f['width'] and py+pf['height'] >= y+f['height'] and fills:
                            background = rgb(fills[0]['color'])
                    fg = rgb(attrs['MSAttributedStringColorAttribute']); ratio = contrast(fg, background)
                    assert ratio >= 4.5, (value, ratio)
                    contrast_rows.append(('#%02X%02X%02X' % fg, '#%02X%02X%02X' % background, round(ratio, 3)))
                else:
                    hidden.append(value); hidden_count += 1
                    assert any(p['name'] == 'Состояния / hover меню · спецификация' and not p['isVisible'] for p in ancestors)
            if 'flow' in a:
                assert visible and a['_class'] == 'group' and a['name'] in ('Меню / Главная', 'Меню / Решения')
                expected_id = boards[0 if a['name'].endswith('Главная') else 1]['do_objectID']
                assert a['flow']['destinationArtboardID'] == expected_id; flow_count += 1
            if a['_class'] == 'group' and a.get('userInfo', {}).get('org.exam.module4', {}).get('role') in ('navigation', 'button'):
                button_count += 1; assert f['width'] >= 40 and f['height'] >= 40
                board_buttons.append([a['name'], x, y, f['width'], f['height'], 'flow' in a])
                if a['userInfo']['org.exam.module4']['role'] == 'button':
                    assert not any('flow' in t for t, *_ in walk([a]))
            if a['_class'] == 'bitmap':
                bitmap_count += 1; assert a['image']['_ref'] in z.namelist()
                assert st['contextSettings']['opacity'] == 1
                with Image.open(io.BytesIO(z.read(a['image']['_ref']))) as image:
                    assert abs(f['width']/f['height'] - image.width/image.height) < 1e-8
        assert actual == expected, {'screen': index+1, 'missing': list((Counter(expected)-Counter(actual)).elements()), 'extra': list((Counter(actual)-Counter(expected)).elements()), 'order_matches': actual == expected}
        assert hidden == ['Главная', 'Решения']
        assert search_fields == ([[16, 108, 398, 44]] if index == 0 else [])
        expected_buttons = ['Меню / Главная', 'Меню / Решения'] + (['Заказать лицензию', 'Скачать пробную версию'] if index == 0 else [a['name']+' / Подробнее' for a in board['layers'] if a['_class'] == 'group' and a['name'] != 'Состояния / hover меню · спецификация' and not a['name'].startswith('Меню /')])
        assert [b[0] for b in board_buttons] == expected_buttons
        assert [b[5] for b in board_buttons] == [True, True]+[False]*(len(expected_buttons)-2)
        for i, first in enumerate(rects):
            for second in rects[i+1:]:
                _, x1, y1, w1, h1 = first; _, x2, y2, w2, h2 = second
                assert min(x1+w1, x2+w2) <= max(x1, x2) or min(y1+h1, y2+h2) <= max(y1, y2), (first, second)
        board_stats.append({'screen': board['name'], 'size': [430, 932], 'visible_texts': len(actual), 'source_texts': len(source[index]), 'layers': len(records), 'visible_content_bottom_px': max(bottoms), 'bottom_margin_px': 932-max(bottoms), 'buttons_name_x_y_width_height_has_flow': board_buttons})

assert styles == {('Roboto-Regular', 14, 18), ('Roboto-Bold', 14, 18), ('Roboto-Bold', 16, 20), ('Roboto-Bold', 28, 34)}
assert flow_count == 4 and button_count == 12 and bitmap_count == 3
for name in ('01-home.png', '02-solutions.png'):
    with Image.open(HERE / name) as im:
        assert im.size == (430, 932)

report = {
    'result': 'PARTIAL: native hover is not implemented; editor rendering and playback are not tested',
    'automated_checks': 'PASS', 'archive_crc': 'PASS', 'official_schema': '6.5.0 / draft-07',
    'schema_sha256': schema_sha256,
    'format_version': meta['version'], 'artboards': board_stats, 'layers_excluding_artboards': layer_count,
    'visible_text_layers': visible_count, 'hidden_hover_text_layers': hidden_count,
    'exact_source_text_occurrences': sum(map(len, source)), 'extra_visible_text': ['Поиск по продуктам'],
    'text_order_and_multiplicity': 'PASS per screen', 'hidden_text_allowlist': 'PASS: exactly two menu labels per screen',
    'typography_styles': sorted(styles), 'ttf_postscript_names': font_names,
    'utf16_ranges': 'PASS', 'pillow_metrics_and_text_box_overlap': 'PASS; this is not CoreText verification',
    'native_navigation_connections': flow_count, 'buttons_without_transition': button_count-flow_count,
    'button_minimum_height_px': 40, 'search_target_px': [398, 44],
    'bitmap_layers': bitmap_count, 'source_media_and_crop': 'PASS byte-for-byte/recomputed crop',
    'geometry_opacity_shapes': 'PASS; all frames inside artboards, opacity 1, closed four-point shapes',
    'text_contrasts_fg_bg_ratio': sorted(set(contrast_rows)),
    'reference_pngs': 'Pillow references, not native editor exports',
    'native_app_open_test': 'NOT TESTED: coordinated Cua/Windows inventory found no Sketch, Figma or Adobe XD editor', 'native_coretext_rendering': 'NOT TESTED',
    'native_prototype_playback': 'NOT TESTED', 'native_hover': 'NOT IMPLEMENTED',
    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'source_docx_sha256': hashlib.sha256((ROOT/'docs'/'original'/'Текст.docx').read_bytes()).hexdigest(),
    'source_pdf_sha256': hashlib.sha256((ROOT/'docs'/'original'/'Вариант 3.pdf').read_bytes()).hexdigest()
}
(HERE/'verification-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=True, indent=2))
