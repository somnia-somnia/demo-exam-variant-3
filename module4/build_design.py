"""Build genuine, editable Sketch design and deterministic reference previews.
Python + Pillow + jsonschema; all visual inputs are local exam media.
"""
from pathlib import Path
import json, uuid, zipfile, copy, shutil, io
from PIL import Image, ImageDraw, ImageFont, ImageOps
import jsonschema

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
MEDIA=ROOT/'source'/'Медиа'/'Медиа'
SCHEMA=OUT/'sketch-file-format-6.5.0.schema.json'
S=json.loads(SCHEMA.read_text(encoding='utf-8')); D=S['definitions']
ASSETS=OUT/'assets'; ASSETS.mkdir(exist_ok=True)
for n in ['Roboto-Regular.ttf','Roboto-Bold.ttf','OFL.txt']:
    shutil.copy2(MEDIA/'Roboto'/'Roboto'/n,ASSETS/n)
shutil.copy2(MEDIA/'Логотип_полный.png',ASSETS/'logo.png')
# Embedded, locally cropped photo. Original is retained alongside for manual editing.
shutil.copy2(MEDIA/'large.jpg',ASSETS/'photo-original.jpg')
ImageOps.fit(Image.open(MEDIA/'large.jpg').convert('RGB'),(796,220)).save(ASSETS/'photo.jpg',quality=94)

def uid(): return str(uuid.uuid4()).upper()
def default(s):
    if '$ref' in s: return default(D[s['$ref'].split('/')[-1]])
    if 'const' in s:return s['const']
    if 'enum' in s:return s['enum'][0]
    if 'oneOf' in s:return default(s['oneOf'][0])
    if s.get('title')=='UUID':return uid()
    t=s.get('type')
    if t=='object':return {k:default(s['properties'][k]) for k in s.get('required',[]) if k in s.get('properties',{})}
    if t=='array':return [default(s['items']) for _ in range(s.get('minItems',0))]
    if t=='boolean':return False
    if t in ['integer','number']:return s.get('minimum',0)
    if t=='string':
        p=s.get('pattern','')
        if p.startswith('^[0-9A-F]'):return uid()
        if p.startswith('^{(('):return '{{0, 0}, {1, 0}, {1, 1}, {0, 1}}'
        if p.startswith('^{-?'):return '{0, 0}'
        return ''
    return None

def obj(n):return default(D[n])
def color(h,a=1):
    c=obj('Color');c.update(red=int(h[1:3],16)/255,green=int(h[3:5],16)/255,blue=int(h[5:7],16)/255,alpha=a);return c
TEAL='#0E7583'; INK='#17363B'; MUTED='#536A6E'; LINE='#D5E3E5'; PALE='#EAF3F4'; WHITE='#FFFFFF'; BG='#F5F8F8'
def style(fill=None,border=None):
    v=obj('Style');v.update(miterLimit=10,startMarkerType=0,endMarkerType=0,windingRule=1)
    v['contextSettings']={'_class':'graphicsContextSettings','opacity':1,'blendMode':0}
    v['colorControls'].update(brightness=0,contrast=1,hue=0,saturation=1)
    v['fills']=[];v['borders']=[];v['shadows']=[]
    if fill:
        f=obj('Fill');f.update(isEnabled=True,color=color(fill),fillType=0,patternTileScale=1);f['contextSettings'].update(opacity=1,blendMode=0);v['fills']=[f]
    if border:
        b=obj('Border');b.update(isEnabled=True,color=color(border),fillType=0,position=1,thickness=1);b['contextSettings'].update(opacity=1,blendMode=0);v['borders']=[b]
    return v
def frame(x,y,w,h):return dict(_class='rect',constrainProportions=False,x=x,y=y,width=w,height=h)
def layer(n,name,x,y,w,h):
    a=obj(n);a.update(name=name,frame=frame(x,y,w,h),isVisible=True,resizingConstraint=63,booleanOperation=-1,layerListExpandedType=0)
    return a

FONTS={}
def font(size,bold=False,scale=1):
    key=(size,bold,scale)
    if key not in FONTS:FONTS[key]=ImageFont.truetype(str(ASSETS/('Roboto-Bold.ttf' if bold else 'Roboto-Regular.ttf')),round(size*scale))
    return FONTS[key]
def wrap(s,w,size=14,bold=False):
    f=font(size,bold);ls=[]
    for p in s.split('\n'):
        row=''
        for word in p.split():
            trial=(row+' '+word).strip()
            if row and f.getlength(trial)>w:ls.append(row);row=word
            else:row=trial
        ls.append(row)
    return ls

# Every scene instruction has an equivalent native Sketch layer.
class Scene:
    def __init__(self,name,artid):self.name=name;self.id=artid;self.layers=[];self.draw=[];self.buttons=[]
    def rect(self,name,x,y,w,h,fill=WHITE,border=None,r=0):
        a=layer('Rectangle',name,x,y,w,h);a.update(style=style(fill,border),isClosed=True,fixedRadius=r,hasConvertedToNewRoundCorners=True)
        pts=[]
        for p in ['{0, 0}','{1, 0}','{1, 1}','{0, 1}']:
            q=obj('CurvePoint');q.update(point=p,curveFrom=p,curveTo=p,curveMode=1,cornerRadius=r);pts.append(q)
        a['points']=pts;self.layers.append(a);self.draw.append(('rect',x,y,w,h,fill,border,r));return a
    def text(self,s,x,y,w,size=14,bold=False,c=INK,line=18,align=0,name=None):
        lines=wrap(s,w,size,bold);h=len(lines)*line
        a=layer('Text',name or s[:55],x,y,w,h)
        att={'MSAttributedStringFontAttribute':{'_class':'fontDescriptor','attributes':{'name':'Roboto-Bold' if bold else 'Roboto-Regular','size':size}},'MSAttributedStringColorAttribute':color(c),'paragraphStyle':{'_class':'paragraphStyle','alignment':align,'maximumLineHeight':line,'minimumLineHeight':line,'paragraphSpacing':0}}
        a.update(attributedString={'_class':'attributedString','string':s,'attributes':[{'_class':'stringAttribute','location':0,'length':len(s.encode('utf-16-le'))//2,'attributes':copy.deepcopy(att)}]},textBehaviour=1,lineSpacingBehaviour=2,glyphBounds='{{0, 0}, {'+str(w)+', '+str(h)+'}}',style=style())
        a['style']['textStyle']={'_class':'textStyle','verticalAlignment':0,'encodedAttributes':att}
        a['userInfo']={'org.exam.module4':{'referenceLines':lines,'lineHeight':line}}
        self.layers.append(a);self.draw.append(('text',x,y,w,h,lines,size,bold,c,line,align));return h
    def image(self,path,x,y,w,h,name):
        a=layer('Bitmap',name,x,y,w,h);a.update(image={'_class':'MSJSONFileReference','_ref_class':'MSImageData','_ref':'images/'+path.name},intendedDPI=72,clippingMask='{{0, 0}, {1, 0}, {1, 1}, {0, 1}}',style=style());self.layers.append(a);self.draw.append(('image',x,y,w,h,path));return a
    def button(self,label,x,y,w,h=40,primary=False,dest=None,name=None):
        start=len(self.layers)
        self.rect((name or label)+' / фон',x,y,w,h,TEAL if primary else WHITE,TEAL,6)
        self.text(label,x+8,y+(h-18)/2,w-16,bold=True,c=WHITE if primary else TEAL,align=2,name=(name or label)+' / подпись')
        pieces=self.layers[start:];self.layers=self.layers[:start]
        g=layer('Group',name or label,x,y,w,h);g['layers']=pieces;g['hasClickThrough']=False
        for p in pieces:p['frame']['x']-=x;p['frame']['y']-=y
        if dest:g['flow']={'_class':'MSImmutableFlowConnection','destinationArtboardID':dest,'animationType':0,'maintainScrollPosition':False}
        g['userInfo']={'org.exam.module4':{'role':'navigation' if dest else 'button','default':'normal','hoverTextColor':'#085966' if dest else 'unchanged','destination':dest}}
        self.layers.append(g);self.buttons.append({'label':label,'x':x,'y':y,'width':w,'height':h,'destination':dest})
        return g

HOME=uid(); SOLUTIONS=uid(); scenes=[Scene('01 · Главная',HOME),Scene('02 · Решения',SOLUTIONS)]
def header(s,active):
    s.rect('Область меню',0,0,430,96,WHITE)
    im=Image.open(ASSETS/'logo.png');ratio=im.width/im.height
    s.image(ASSETS/'logo.png',16,12,132,132/ratio,'Таймыр / исходный полный логотип')
    s.button('Главная',16,48,192,40,active=='Главная',HOME,'Меню / Главная')
    s.button('Решения',222,48,192,40,active=='Решения',SOLUTIONS,'Меню / Решения')

s=scenes[0];header(s,'Главная')
s.rect('Поиск / поле',16,108,398,44,WHITE,LINE,6)
# Search icon consists of editable native oval and rectangle.
a=layer('Oval','Поиск / линза',30,122,13,13);a.update(style=style(None,MUTED),isClosed=True)
a['points']=[]
for point,fr,to in [('{0.5, 0}','{0.223858, 0}','{0.776142, 0}'),('{1, 0.5}','{1, 0.223858}','{1, 0.776142}'),('{0.5, 1}','{0.776142, 1}','{0.223858, 1}'),('{0, 0.5}','{0, 0.776142}','{0, 0.223858}')]:
    p=obj('CurvePoint');p.update(point=point,curveFrom=fr,curveTo=to,hasCurveFrom=True,hasCurveTo=True,curveMode=2);a['points'].append(p)
s.layers.append(a)
b=layer('Rectangle','Поиск / ручка',43,133,2,8);b.update(style=style(MUTED),rotation=-45,isClosed=True,points=[])
for point in ['{0, 0}','{1, 0}','{1, 1}','{0, 1}']:
    p=obj('CurvePoint');p.update(point=point,curveFrom=point,curveTo=point,curveMode=1);b['points'].append(p)
s.layers.append(b)
s.draw.append(('search',30,122,13,13,MUTED))
s.text('Поиск по продуктам',54,121,340,c=MUTED)
s.text('ПЛАТФОРМА ДАННЫХ',16,174,398,bold=True,c=TEAL)
s.text('Таймыр Data Platform Enterprise',16,202,398,size=28,bold=True,line=34)
s.image(ASSETS/'photo.jpg',16,282,398,110,'Дата-центр / фото из Медиа')
description='Отечественная платформа со встроенными средствами защиты для надежного хранения, обработки и резервного копирования корпоративных данных в ИТ-инфраструктурах любого масштаба. Доступны версии для серверного, десктопного, мобильного и встраиваемого сценариев применения'
h=s.text(description,16,408,398)
y=408+h+14
facts=['Более 800 организаций используют Таймыр Data Platform','Непрерывная защита данных от сбоев и утечек на всех этапах хранения','Полная совместимость с отечественными ОС и стандартами']
for fact in facts:
    s.rect('Преимущество / маркер',16,y+5,5,5,TEAL,r=2)
    hh=s.text(fact,30,y,384,bold=False);y+=hh+8
s.button('Заказать лицензию',16,y+4,398,44,True)
s.button('Скачать пробную версию',16,y+56,398,44)
foot=y+114
s.rect('Подвал / линия',16,foot,398,1,LINE)
s.text('Продолжая, вы соглашаетесь с условиями использования и политикой конфиденциальности',16,foot+14,398,c=MUTED)
s.text('© 2025',16,foot+62,90,c=MUTED)
s.text('Все права защищены',120,foot+62,294,c=MUTED,align=1)
HOME_END=foot+80

products=[
 ('Таймыр Studio',['Удобство для администратора','Универсальность','Современность','Наглядность']),
 ('Таймыр Server',['Отказоустойчивый кластер баз данных','Централизованное управление конфигурациями','Инструменты для разработки и использования прикладного ПО','Безопасная среда исполнения контейнерных нагрузок']),
 ('Таймыр Mobile',['Адаптивность','Централизованность','Удобство']),
 ('Таймыр Embedded',['Поддержка основных процессорных архитектур','Гибкая система лицензирования','Сертификаты ключевых регуляторов','Техническая поддержка вендора ОС']),
 ('Программный стек «Группы Таймыр»',['Экосистема продуктов «Группы Таймыр»']),
 ('Техническая поддержка',['Консультация 24/7'])]

def card_h(title,bullets):
    return 12+len(wrap(title,168,16,True))*20+10+sum(len(wrap(b,158))*18 for b in bullets)+(len(bullets)-1)*4+8+40+12

s=scenes[1];header(s,'Решения');y=100
rows=[]
for row in range(3):
    pair=products[row*2:row*2+2];height=max(card_h(*p) for p in pair);rows.append(height)
    for col,(title,bullets) in enumerate(pair):
        x=16+206*col;start=len(s.layers)
        s.rect(title+' / карточка',x,y,192,height,WHITE,LINE,8)
        yy=y+12;s.text(title,x+12,yy,168,16,True,TEAL,20);yy+=len(wrap(title,168,16,True))*20+10
        for b in bullets:
            s.rect('Пункт / маркер',x+12,yy+6,3,3,TEAL,r=1)
            hh=s.text(b,x+22,yy,158);yy+=hh+4
        s.button('Подробнее',x+12,y+height-52,168,40,name=title+' / Подробнее')
        # Group cards while retaining every text, shape and button as editable children.
        pieces=s.layers[start:];s.layers=s.layers[:start]
        g=layer('Group',title,x,y,192,height);g['layers']=pieces;g['hasClickThrough']=True
        for p in pieces:p['frame']['x']-=x;p['frame']['y']-=y
        s.layers.append(g)
    y+=height+10
s.text('© 2025',16,y+2,80,c=MUTED)
s.text('Все права защищены',108,y+2,306,c=MUTED,align=1)
SOL_END=y+20

# Hidden native shape/text groups preserve the visual hover state for GUI setup.
for s in scenes:
    states=layer('Group','Состояния / hover меню · спецификация',0,0,430,96)
    states['isVisible']=False;states['layers']=[];states['userInfo']={'org.exam.module4':{'interaction':'NOT IMPLEMENTED: these editable hover samples are not connected to native triggers. Desired menu hover: text #085966, fill #EAF3F4.'}}
    for xx,label in [(16,'Главная'),(222,'Решения')]:
        state=Scene('hover',uid());state.rect('Hover / фон',xx,48,192,40,PALE,TEAL,6);state.text(label,xx+8,59,176,bold=True,c='#085966',align=2)
        group=layer('Group',label+' / Hover',xx,48,192,40);group['layers']=state.layers
        for a in group['layers']:a['frame']['x']-=xx;a['frame']['y']-=48
        states['layers'].append(group)
    s.layers.append(states)

print('Measured bottom extents',HOME_END,SOL_END,'card rows',rows)
assert HOME_END<=932,(HOME_END,'Home content exceeds viewport')
assert SOL_END<=932,(SOL_END,'Solutions content exceeds viewport')

def render(s,scale=3):
    im=Image.new('RGB',(430*scale,932*scale),BG);d=ImageDraw.Draw(im)
    for op in s.draw:
        kind=op[0]
        if kind=='rect':
            _,x,y,w,h,fill,border,r=op;d.rounded_rectangle((round(x*scale),round(y*scale),round((x+w)*scale),round((y+h)*scale)),r*scale,fill=fill,outline=border,width=scale)
        elif kind=='text':
            _,x,y,w,h,lines,size,bold,c,line,align=op;f=font(size,bold,scale)
            for i,t in enumerate(lines):
                tx=x*scale
                if align==1:tx+=(w*scale-f.getlength(t))
                if align==2:tx+=(w*scale-f.getlength(t))/2
                # Pillow top anchor provides predictable, non-clipping text previews.
                d.text((round(tx),round((y+i*line)*scale)),t,font=f,fill=c,anchor='lt')
        elif kind=='image':
            _,x,y,w,h,path=op;p=Image.open(path).convert('RGBA').resize((round(w*scale),round(h*scale)),Image.Resampling.LANCZOS);im.paste(p,(round(x*scale),round(y*scale)),p)
        elif kind=='search':
            _,x,y,w,h,c=op;d.ellipse((x*scale,y*scale,(x+w)*scale,(y+h)*scale),outline=c,width=2*scale);d.line(((x+w-1)*scale,(y+h-1)*scale,(x+w+5)*scale,(y+h+5)*scale),fill=c,width=2*scale)
    return im.resize((430,932),Image.Resampling.LANCZOS)

ims=[]
for i,s in enumerate(scenes):
    im=render(s);im.save(OUT/f'{i+1:02d}-{["home","solutions"][i]}.png');ims.append(im)
preview=Image.new('RGB',(908,980),'#DFE8E9')
for i,im in enumerate(ims):preview.paste(im,(16+i*446,24))
preview_bytes=io.BytesIO();preview.save(preview_bytes,format='PNG')

page=layer('Page','Модуль 4 · Группа Таймыр · 430×932',0,0,908,932);page['layers']=[]
for i,s in enumerate(scenes):
    a=layer('Artboard',s.name,i*478,0,430,932)
    a.update(do_objectID=s.id,layers=s.layers,hasBackgroundColor=True,backgroundColor=color(BG),includeBackgroundColorInExport=True,isFlowHome=i==0,resizesContent=False)
    a['prototypeViewport']={'_class':'MSImmutablePrototypeViewport','name':'Mobile 430 × 932','size':'{430, 932}'}
    a['layout']={'_class':'layoutGrid','isEnabled':True,'columnWidth':89,'gutterHeight':8,'gutterWidth':14,'horizontalOffset':16,'numberOfColumns':4,'rowHeightMultiplication':1,'totalWidth':398,'guttersOutside':False,'drawHorizontal':False,'drawHorizontalLines':False,'drawVertical':True}
    a['userInfo']={'org.exam.module4':{'screenSize':[430,932],'grid':'4 columns × 89, gap 14, margins 16','content':s.name,'scrollRequired':False}}
    page['layers'].append(a)

doc=default(S['properties']['document']);doc.update(colorSpace=1,pages=[page]);doc['assets']['colors']=[color(c) for c in [TEAL,INK,MUTED,LINE,PALE,WHITE,BG]]
meta=obj('Meta');meta.update(commit='generated-from-published-specification',version=146,compatibilityVersion=99,app='com.bohemiancoding.sketch3',autosaved=0,variant='NONAPPSTORE',appVersion='96',build=0)
meta['created']=dict(commit='generated-from-published-specification',appVersion='96',build=0,app='com.bohemiancoding.sketch3',compatibilityVersion=99,version=146,variant='NONAPPSTORE')
meta['pagesAndArtboards']={page['do_objectID']:{'name':page['name'],'artboards':{s.id:{'name':s.name} for s in scenes}}}
user={'document':{'pageListHeight':120,'pageListCollapsed':0},page['do_objectID']:{'scrollOrigin':'{0, 0}','zoomValue':0.7}}
expanded={'document':doc,'meta':meta,'user':user}
jsonschema.Draft7Validator(S).validate(expanded)
archive_doc=copy.deepcopy(doc);archive_doc['pages']=[{'_class':'MSJSONFileReference','_ref_class':'MSImmutablePage','_ref':'pages/'+page['do_objectID']}]
sketch=OUT/'Группа-Таймыр.sketch'
with zipfile.ZipFile(sketch,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in [('document.json',archive_doc),('meta.json',meta),('user.json',user),('pages/'+page['do_objectID']+'.json',page)]:z.writestr(name,json.dumps(data,ensure_ascii=False,separators=(',',':')))
    for n in ['logo.png','photo.jpg']:z.write(ASSETS/n,'images/'+n)
    z.writestr('previews/preview.png',preview_bytes.getvalue())

with zipfile.ZipFile(sketch) as z:assert z.testzip() is None
print('Built',sketch.name,'with official schema validation; native GUI/playback NOT TESTED, hover NOT IMPLEMENTED')
