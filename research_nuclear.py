"""Save source pages and extract the Wiki's explicitly labelled recipe blocks."""
from html.parser import HTMLParser
from pathlib import Path
import json, urllib.request
from concurrent.futures import ThreadPoolExecutor

class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
    def find(self, predicate):
        out = [self] if predicate(self) else []
        for c in self.children:
            if isinstance(c, Node): out.extend(c.find(predicate))
        return out
    def text(self): return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)
    def has(self, cls): return cls in self.attrs.get('class','').split()

class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.root=Node(); self.current=self.root
    def handle_starttag(self, tag, attrs):
        node=Node(tag,attrs,self.current); self.current.children.append(node)
        if tag not in ['img','br','hr','meta','link','input','source','wbr']: self.current=node
    def handle_endtag(self, tag):
        node=self.current
        while node.parent and node.tag!=tag: node=node.parent
        if node.parent: self.current=node.parent
    def handle_data(self, data): self.current.children.append(data)

PAGES=['Nuclear_Reactor','Nuclear_Reactor_II','Fast_Breeder_Reactor','Enrichment_Plant','Nuclear_Reprocessing_Plant','Chemical_Plant_II','Assembly_II','Uranium_Rod','Assembly_III','Super-Pressure_Turbine','High-Pressure_Turbine_II','Low-Pressure_Turbine_II','Power_Generator_(Large)','Cooling_Tower_(Large)']
def read(page):
    path=Path('research')/(page+'.html.txt')
    if path.exists(): source=path.read_text(encoding='utf-8')
    else:
        source=urllib.request.urlopen(urllib.request.Request('https://wiki.coigame.com/'+page,headers={'User-Agent':'CoI-Balancer nuclear data research'}),timeout=35).read().decode()
        path.write_text(source,encoding='utf-8')
    parser=Parser(); parser.feed(source); recipes=[]
    for node in parser.root.find(lambda n:n.has('recipe-wrapper')):
        side='inputs'; recipe={'inputs':{},'outputs':{},'duration':None}
        for block in [c for c in node.children if isinstance(c,Node) and c.has('block')]:
            if block.has('time'):
                upper=block.find(lambda n:n.has('upper'))
                recipe['duration']=upper[0].text().strip() if upper else None
                side='outputs'; continue
            upper=block.find(lambda n:n.has('upper'))
            anchors=block.find(lambda n:n.tag=='a' and n.attrs.get('title') and not n.attrs.get('href','').startswith('/File:'))
            if upper and anchors:
                recipe[side][anchors[0].attrs['title']]=upper[0].text().strip()
        if recipe['inputs'] or recipe['outputs']: recipes.append(recipe)
    return page,recipes

if __name__=='__main__':
    Path('research').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool: data=dict(pool.map(read,PAGES))
    Path('research/wiki-recipes.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    for page,recipes in data.items():
        if page=='Assembly_II': recipes=[r for r in recipes if 'Uranium Rods' in r['outputs']]
        if page=='Chemical_Plant_II': recipes=[r for r in recipes if any(x in r['outputs'] for x in ['Core Fuel','Blanket Fuel','MOX Rods'])]
        print(page,json.dumps(recipes,ensure_ascii=False))
