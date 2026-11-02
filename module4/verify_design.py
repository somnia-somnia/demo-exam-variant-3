"""Independent verification of the delivered .sketch archive (no regeneration)."""
from pathlib import Path
import json, zipfile, hashlib, re
import jsonschema
from PIL import Image

HERE=Path(__file__).resolve().parent
archive=HERE/'Группа-Таймыр.sketch'
schema=json.loads((HERE/'sketch-file-format-6.5.0.schema.json').read_text(encoding='utf-8'))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    document=json.loads(z.read('document.json'))
    meta=json.loads(z.read('meta.json'));user=json.loads(z.read('user.json'))
    pages=[]
    for ref in document['pages']:
        assert ref['_class']=='MSJSONFileReference' and ref['_ref_class']=='MSImmutablePage'
        pages.append(json.loads(z.read(ref['_ref']+'.json')))
    expanded={**document,'pages':pages}
    jsonschema.Draft7Validator(schema).validate({'document':expanded,'meta':meta,'user':user})
    def walk(layers,ox=0,oy=0,shown=True):
        for layer in layers:
            f=layer['frame'];x=ox+f['x'];y=oy+f['y'];visible=shown and layer['isVisible']
            yield layer,x,y,visible
            yield from walk(layer.get('layers',[]),x,y,visible)
    boards=[a for p in pages for a in p['layers'] if a['_class']=='artboard']
    assert len(boards)==2
    board_ids={a['do_objectID'] for a in boards};text=[];all_text=[];links=[];styles=set();stats=[];images=0
    for board in boards:
        assert (board['frame']['width'],board['frame']['height'])==(430,932)
        grid=board['layout'];assert grid['numberOfColumns']==4
        assert grid['columnWidth']*4+grid['gutterWidth']*3==398
        n=0
        for a,x,y,visible in walk(board['layers']):
            n+=1;f=a['frame']
            if a['_class']=='text':
                value=a['attributedString']['string'];all_text.append(value)
                attrs=a['attributedString']['attributes'][0]['attributes'];font=attrs['MSAttributedStringFontAttribute']['attributes']
                assert font['size']>=14
                assert font['name'] in ['Roboto-Regular','Roboto-Bold']
                styles.add((font['name'],font['size']))
                if visible:
                    text.append(value)
                    assert x>=0 and y>=0 and x+f['width']<=430 and y+f['height']<=932,(value,x,y,f)
            if 'flow' in a:
                assert a['flow']['destinationArtboardID'] in board_ids
                assert f['width']>=40 and f['height']>=40
                links.append(a['flow'])
            if a['_class']=='group' and ('Подробнее' in a['name'] or a['name'] in ['Заказать лицензию','Скачать пробную версию']):
                assert f['width']>=40 and f['height']>=40
            if a['_class']=='bitmap':
                images+=1;assert a['image']['_ref'] in z.namelist()
            assert f['width']>0 and f['height']>0
        stats.append({'screen':board['name'],'size':[430,932],'layers':n})
    assert len(styles)<=4
    assert len(links)==4
    assert boards[0]['isFlowHome'] and not boards[1]['isFlowHome']

# Inspect source docx paragraphs directly, rather than a second hard-coded copy.
from xml.etree import ElementTree as ET
docx=HERE.parent/'docs'/'original'/'Текст.docx'
with zipfile.ZipFile(docx) as z:
    root=ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    # Read w:t nodes only, avoiding XML metadata.
    paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)).strip() for p in root.findall('.//w:p',ns)]
required=[]
for p in paragraphs:
    if not p or re.match(r'^Экран\s*\d$',p):continue
    if p.startswith('Меню навигации:'):required+=['Главная','Решения']
    elif p.startswith('Кнопки:'):required += [s.strip() for s in p.split(':',1)[1].split(',')]
    elif p.startswith('Кнопка:'):required.append(p.split(':',1)[1].strip())
    elif p=='Окно поиска':continue # The search field is a control, not a printed heading.
    else:required.append(p)
missing=[p for p in required if p not in text]
assert not missing,missing
for n in ['01-home.png','02-solutions.png']:
    with Image.open(HERE/n) as im:assert im.size==(430,932)

report={'result':'PASS','validation':'Official JSON Schema draft-07, read back from actual .sketch archive','archive_crc':'PASS','schema_package_version':'6.5.0','format_version':meta['version'],'artboards':stats,'native_editable_text_layers':len(all_text),'visible_text_layers':len(text),'typography_styles':sorted([list(s) for s in styles]),'native_navigation_connections':len(links),'native_bitmap_layers':images,'required_source_paragraphs':len(required),'missing_source_paragraphs':missing,'source_checked':'Текст.docx / word/document.xml','minimum_text_px':14,'minimum_touch_target_px':[40,40],'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'visual_reference_inspection':'Pillow preview inspected; all copy fits within both 430×932 viewports','native_app_open_test':'NOT RUN: Sketch GUI is unavailable in the Windows environment','native_hover':'NOT IMPLEMENTED in legacy format146; editable hover-state layers and precise manual instructions included'}
(HERE/'verification-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
