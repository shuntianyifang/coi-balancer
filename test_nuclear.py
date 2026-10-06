import copy
import json
import subprocess
import unittest
from pathlib import Path
from nuclear import operating_recipe, analyze, compiled
from server import calculate

CAT=json.loads((Path(__file__).parent/'web/nuclear-catalog.json').read_text(encoding='utf-8'))

def instance(typ='nr2', **kw):
    return dict(id=typ,buildingId=typ,recipeId=typ+'_operation',load=1,enabled=True,level=4 if typ!='nr1' else 3,station='A',**kw)

def equipped(typ='nr2', breeding=1):
    d=copy.deepcopy(CAT); i=instance(typ,breeding=breeding);d['instances']=[i]
    if typ=='fbr' and breeding!=3:counts={'super_turbine':8,'high_turbine':8,'low_turbine':8,'generator':16,'cooling':4}
    elif typ=='fbr':counts={'super_turbine':2,'high_turbine':2,'low_turbine':2,'generator':4,'cooling':1}
    else:counts={'high_turbine':8,'low_turbine':8,'generator':8,'cooling':4}
    for b,count in counts.items():
        r=next(r for r in d['recipes'] if r['buildingId']==b)
        for n in range(count):d['instances'].append(dict(id=f'{b}{n}',buildingId=b,recipeId=r['id'],load=1,enabled=True,station='A'))
    return d

class NuclearTests(unittest.TestCase):
    def test_all_levels_and_fuels(self):
        for typ in ['nr1','nr2']:
            r=next(r for r in CAT['recipes'] if r.get('reactorType')==typ)
            for level in range(1,4 if typ=='nr1' else 5):
                for fuel in ['uranium_rod'] if typ=='nr1' else ['uranium_rod','mox_rod']:
                    i=instance(typ,fuel=fuel);i['level']=level
                    out=operating_recipe(i,r)
                    self.assertEqual(out['inputs'][fuel],level*.5)
                    self.assertEqual(out['outputs']['steam_high'],level*96)
    def test_fbr_modes_and_independent_blanket(self):
        r=next(r for r in CAT['recipes'] if r.get('reactorType')=='fbr')
        for mode,core,steam,blanket in [(0,8,384,0),(1,16,384,16),(3,16,96,48)]:
            out=operating_recipe(instance('fbr',breeding=mode),r)
            self.assertEqual(out['inputs']['core'],core)
            self.assertEqual(out['outputs']['steam_super'],steam)
            self.assertEqual(out['inputs'].get('blanket',0),blanket)
        out=operating_recipe(instance('fbr',breeding=3,blanketFraction=0),r)
        self.assertEqual(out['inputs']['core'],16)
        self.assertEqual(out['outputs']['steam_super'],96)
        self.assertEqual(out['outputs']['enriched_blanket'],0)
    def test_invalid_auto_and_fuel(self):
        r=next(r for r in CAT['recipes'] if r.get('reactorType')=='nr2')
        with self.assertRaises(ValueError):operating_recipe(instance('nr2',control='auto',averageLevel=.5),r)
        with self.assertRaises(ValueError):operating_recipe(instance('nr2',fuel='core'),r)
    def test_nr2_complete_plant(self):
        report=analyze(equipped())['stations'][0]
        self.assertAlmostEqual(report['grossMW'],120)
        self.assertAlmostEqual(report['recoveredWater'],288)
        self.assertAlmostEqual(report['makeupWater'],96)
        self.assertTrue(all(abs(q)<1e-7 for q in report['residual'].values()))
    def test_nr1_and_stopped_reactor(self):
        d=equipped('nr1');self.assertAlmostEqual(analyze(d)['grossMW'],90)
        d['instances'][0]['enabled']=False
        report=analyze(d)
        self.assertEqual(report['grossMW'],0)
        self.assertEqual(report['stations'][0]['waterDemand'],0)
    def test_requested_net_power(self):
        d=copy.deepcopy(CAT);d['policies']['electricity']['target']=100
        out=calculate(d,'integer')
        self.assertTrue(out['ok'])
        self.assertGreaterEqual(-out['totals']['power'],100-1e-6)
    def test_fbr_power(self):
        for mode,mw in [(0,240),(1,240),(3,60)]:
            self.assertAlmostEqual(analyze(equipped('fbr',mode))['stations'][0]['grossMW'],mw)
    def test_missing_generator_and_cross_station(self):
        d=equipped();d['instances']=[i for i in d['instances'] if i['buildingId']!='generator']
        self.assertEqual(analyze(d)['stations'][0]['grossMW'],0)
        d=equipped()
        for i in d['instances']:
            if i['buildingId']=='generator':i['station']='B'
        self.assertTrue(all(s['grossMW']==0 for s in analyze(d)['stations']))
    def test_generator_bottleneck(self):
        d=equipped();d['instances']=[i for i in d['instances'] if i['buildingId']!='generator' or i['id']=='generator0']
        self.assertAlmostEqual(analyze(d)['stations'][0]['grossMW'],15)
    def test_water_warning(self):
        d=equipped();d['stationWater']={'A':90}
        self.assertTrue(any('供水上限' in w for w in analyze(d)['stations'][0]['warnings']))
        d=copy.deepcopy(CAT);d['stationWater']={'主电站':90}
        self.assertFalse(calculate(d,'solve')['ok'])
    def test_solver_full_fuel_chain_and_actual_audit(self):
        d=copy.deepcopy(CAT)
        out=calculate(d,'solve')
        self.assertTrue(out['ok'])
        self.assertTrue(all(abs(f['remainder'])<1e-7 or d['policies'].get(f['product'],{}).get('surplus') for f in out['flows']))
        self.assertGreater(next(f['import'] for f in out['flows'] if f['product']=='steel'),0)
        self.assertLess(out['totals']['power'],0)
        audited=calculate(equipped(),'audit')
        self.assertAlmostEqual(audited['totals']['power'],-120)
        self.assertEqual(audited['totals']['buildings'],29)
    def test_compiled_settings_not_extra_reactors(self):
        d=copy.deepcopy(CAT);out=compiled(d,'integer')
        reactors=[r for r in out['recipes'] if r.get('reactorType')]
        self.assertEqual(len(reactors),1)
        self.assertEqual(reactors[0]['min'],1)
        self.assertEqual(reactors[0]['max'],1)
    def test_js_python_parity(self):
        cases=[]
        for typ in ['nr1','nr2','fbr']:
            r=next(r for r in CAT['recipes'] if r.get('reactorType')==typ)
            for mode in [0,1,3]:
                i=instance(typ,breeding=mode,blanketFraction=.4)
                cases.append({'i':i,'r':r})
        js="const m=require('./web/buildings.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c=>m.operatingRecipe(c.i,c.r)))))"
        result=subprocess.run(['node','-e',js],input=json.dumps(cases),capture_output=True,text=True,encoding='utf-8',cwd=Path(__file__).parent,check=True)
        for case,actual in zip(cases,json.loads(result.stdout)):
            expected=operating_recipe(case['i'],case['r'])
            self.assertEqual(actual['inputs'],expected['inputs']);self.assertEqual(actual['outputs'],expected['outputs'])

if __name__=='__main__': unittest.main()
