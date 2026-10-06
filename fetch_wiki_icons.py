import urllib.request, urllib.parse, re, html, json, hashlib
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).parent
OUT=ROOT/'web'/'icons'
NOTICES=OUT/'wiki-notices'
NOTICES.mkdir(exist_ok=True)
FILES=['Blast Furnace.png','Assembly (Electric).png','Enrichment Plant.png','Nuclear Reactor II.png','Fast Breeder Reactor.png','Nuclear Reprocessing Plant.png','Chemical Plant.png','Greenhouse II.png','Nuclear Reactor.png','Super-pressure Turbine.png','High-Pressure Turbine II.png','Low-Pressure Turbine II.png','Power Generator (Large).png','Cooling Tower (Large).png']
def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'CoI-Balancer/0.3 (local icon importer)'}),timeout=30).read()
def plain(text):
    return ' '.join(html.unescape(re.sub('<[^>]+>',' ',re.sub('<!--.*?-->','',text,flags=re.S))).split())
manifest=json.loads((OUT/'wiki-manifest.json').read_text(encoding='utf-8')) if (OUT/'wiki-manifest.json').exists() else {}
for name in FILES:
    if name in manifest and (ROOT/'web'/manifest[name]['path'].lstrip('/')).exists(): continue
    page='https://wiki.coigame.com/File:'+urllib.parse.quote(name.replace(' ','_'),safe='()')
    source=fetch(page).decode('utf-8')
    match=re.search(r'class="fullImageLink"[^>]*><a href="([^"]+)"',source)
    if not match: raise ValueError('Missing original image: '+name)
    url=urllib.parse.urljoin(page,html.unescape(match.group(1)))
    license_part=source.split('id="License"',1)[1].split('<!--',1)[0] if 'id="License"' in source else ''
    license_text=plain(license_part.split('</h2>',1)[-1])
    if not license_text: raise ValueError('Missing license: '+name)
    summary=source.split('id="Summary"',1)[1].split('<h2',1)[0] if 'id="Summary"' in source else ''
    filename='wiki_'+re.sub('[^a-z0-9]+','_',name.lower()).strip('_')+'.png'
    image=fetch(url)
    if not image.startswith(bytes.fromhex('89504e470d0a1a0a')): raise ValueError('Not PNG')
    (OUT/filename).write_bytes(image)
    (NOTICES/(filename+'.html.txt')).write_text(source,encoding='utf-8')
    manifest[name]={'path':'/icons/'+filename,'sourcePage':page,'originalUrl':url,'licenseText':license_text,'summary':plain(summary.split('</h2>',1)[-1]),'retrievedAt':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(image).hexdigest(),'noticePath':'/icons/wiki-notices/'+filename+'.html.txt'}
    print(name, len(image), flush=True)
(OUT/'wiki-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'web'/'wiki-icons.js').write_text('window.WikiIcons='+json.dumps(manifest,ensure_ascii=False)+';',encoding='utf-8')
(OUT/'WIKI-LICENSES.md').write_text('# Wiki image source and license notices\n\nImages remain subject to their original copyright. These notices reproduce the Wiki file-page statements, not a new license.\n\n'+'\n\n'.join('## '+name+'\n\nSource: '+v['sourcePage']+'\n\n'+v['summary']+'\n\nLicense notice (verbatim): '+v['licenseText'] for name,v in manifest.items()),encoding='utf-8')
