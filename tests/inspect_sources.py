"""Read every nested ZIP, extract original text and create local media contact sheets."""
import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tmp' / 'source-review'
OUT.mkdir(parents=True, exist_ok=True)
ARCHIVE = Path(r'C:\Users\somnia\Downloads\Telegram\Вариант 3.zip')
records, images, texts = [], [], []
font = ImageFont.truetype(str(ROOT / 'static/fonts/Montserrat-Regular.ttf'), 12)


def read_zip(data, prefix=''):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not info.flag_bits & 0x800:
                try:
                    name = name.encode('cp437').decode('cp866')
                except (UnicodeError, LookupError):
                    pass
            path, raw = prefix + name, z.read(info)
            record = dict(path=path, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            records.append(record)
            suffix = Path(name).suffix.lower()
            if suffix == '.zip':
                read_zip(raw, path + '!/')
            elif suffix == '.pdf':
                reader = PdfReader(io.BytesIO(raw))
                text = '\n'.join(f'PAGE {i+1}\n{p.extract_text()}' for i, p in enumerate(reader.pages))
                texts.append((path, text))
                record['pages'] = len(reader.pages)
            elif suffix == '.docx':
                with zipfile.ZipFile(io.BytesIO(raw)) as doc:
                    xml = ET.fromstring(doc.read('word/document.xml'))
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    text = '\n'.join(''.join(p.itertext()) for p in xml.findall('.//w:p', ns))
                    texts.append((path, text))
            elif suffix in ('.ttf', '.otf'):
                loaded = ImageFont.truetype(io.BytesIO(raw), 16)
                record['font'] = loaded.getname()
            elif suffix in ('.jpg', '.jpeg', '.png', '.webp'):
                with Image.open(io.BytesIO(raw)) as im:
                    record['size'] = im.size
                    images.append((path, im.convert('RGB').copy()))


read_zip(ARCHIVE.read_bytes())
for i, (path, text) in enumerate(texts):
    (OUT / f'text-{i+1}.txt').write_text(path + '\n\n' + text, encoding='utf-8')
for offset in range(0, len(images), 20):
    batch = images[offset:offset+20]
    sheet = Image.new('RGB', (1000, ((len(batch)+3)//4)*190), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, (path, im) in enumerate(batch):
        x, y = i % 4 * 250, i // 4 * 190
        sheet.paste(ImageOps.contain(im, (242, 150)), (x+4, y))
        draw.text((x+4, y+151), Path(path).name[:29], font=font, fill='black')
    sheet.save(OUT / f'media-{offset//20+1}.jpg')
report = dict(archive=str(ARCHIVE), archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
              files=len(records), images=len(images), extracted_documents=len(texts), entries=records)
report['source_copy_verification'] = {}
for name in ('Вариант 3.pdf', 'Руководство по стилю.pdf', 'Текст.docx'):
    digest = hashlib.sha256((ROOT/'docs/original'/name).read_bytes()).hexdigest()
    assert any(r['sha256'] == digest for r in records), name
    report['source_copy_verification'][name] = digest
(ROOT / 'docs/source-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(f'ZIP entries: {len(records)}, decoded images: {len(images)}, original documents: {len(texts)}')
print('\n'.join(path for path, _ in texts))
