"""Export editable layer geometry from the delivered Sketch, not its generator."""
import csv
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def layers(items, parent='', x=0, y=0):
    for layer in items:
        if not layer.get('isVisible', True):
            continue
        frame = layer['frame']
        xx, yy = x+frame['x'], y+frame['y']
        text = layer.get('attributedString', {}).get('string', '')
        style = layer.get('style', {}).get('textStyle', {}).get('encodedAttributes', {})
        font = style.get('MSAttributedStringFontAttribute', {}).get('attributes', {})
        yield [parent+'/'+layer['name'], layer['_class'], xx, yy, frame['width'], frame['height'],
               text, font.get('name', ''), font.get('size', ''), style.get('paragraphStyle', {}).get('minimumLineHeight', '')]
        yield from layers(layer.get('layers', []), parent+'/'+layer['name'], xx, yy)


with zipfile.ZipFile(HERE/'Группа-Таймыр.sketch') as z, (HERE/'layer-specification.csv').open('w', encoding='utf-8-sig', newline='') as out:
    writer = csv.writer(out)
    writer.writerow(['screen', 'layer', 'type', 'x', 'y', 'width', 'height', 'text', 'font', 'size', 'line_height'])
    doc = json.loads(z.read('document.json'))
    for ref in doc['pages']:
        page = json.loads(z.read(ref['_ref']+'.json'))
        for board in page['layers']:
            for row in layers(board['layers']):
                writer.writerow([board['name'], *row])
print('Exported visible native layers to module4/layer-specification.csv')
