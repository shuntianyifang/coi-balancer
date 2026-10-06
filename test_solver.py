import unittest
import json
from pathlib import Path
from server import calculate

def r(id, ins, outs, **kw):
    return dict(id=id,name=id,inputs=ins,outputs=outs,duration=60,**kw)

class SolverTests(unittest.TestCase):
    def test_building_instances(self):
        d={'recipes':[r('a',{'ore':2},{'iron':1},workers=4,buildingId='furnace',count=99)],'instances':[{'id':'one','recipeId':'a','buildingId':'furnace','load':.5},{'id':'two','recipeId':'a','buildingId':'furnace','load':1,'enabled':False}]}
        out=calculate(d,'audit')
        self.assertEqual(out['totals']['buildings'],2)
        self.assertEqual(out['totals']['workers'],8)
        self.assertEqual(out['recipes'][0]['rate'],.5)
        self.assertEqual(d['recipes'][0]['count'],99)
        d['instances'][0]['buildingId']='wrong'
        with self.assertRaises(ValueError): calculate(d,'audit')
    def test_integer_partial_capacity(self):
        d={'recipes':[r('a',{'ore':1},{'iron':1},workers=4)],'policies':{'ore':{'import':True},'iron':{'target':1.5}}}
        out=calculate(d,'integer')
        self.assertTrue(out['ok'])
        self.assertEqual(out['recipes'][0]['buildings'],2)
        self.assertAlmostEqual(out['recipes'][0]['load'],.75)
        self.assertEqual(out['totals']['workers'],8)
        d['buildingLimit']=1
        self.assertFalse(calculate(d,'integer')['ok'])
    def test_integer_full_load(self):
        d={'recipes':[r('a',{'ore':1},{'iron':1},full=True)],'policies':{'ore':{'import':True},'iron':{'target':1.5}}}
        self.assertFalse(calculate(d,'integer')['ok'])
        d['policies']['iron']['surplus']=True
        out=calculate(d,'integer')
        self.assertTrue(out['ok'])
        self.assertEqual(out['recipes'][0]['rate'],2)
    def test_audit_installed_workers(self):
        out=calculate({'recipes':[r('a',{}, {'iron':1},count=3,load=.2,workers=4)]},'audit')
        self.assertEqual(out['totals']['workers'],12)
        self.assertAlmostEqual(out['recipes'][0]['load'],.2)
    def test_bundled_examples(self):
        examples = json.loads((Path(__file__).parent / 'samples-test.json').read_text(encoding='utf-8'))
        for name, data in examples.items():
            with self.subTest(name=name):
                self.assertTrue(calculate(data, 'solve')['ok'])
    def test_chain(self):
        d={'recipes':[r('a',{'ore':2},{'iron':1}),r('b',{'iron':2},{'parts':1})], 'policies':{'ore':{'import':True},'parts':{'target':3}}}
        result=calculate(d,'solve')
        self.assertTrue(result['ok'])
        self.assertAlmostEqual(next(x['import'] for x in result['flows'] if x['product']=='ore'),12)
        self.assertTrue(all(abs(x['remainder'])<1e-7 for x in result['flows']))
    def test_cycle(self):
        d={'recipes':[r('fresh',{'ore':1},{'fuel':1}),r('reactor',{'fuel':4},{'spent':4,'power':10},min=1,max=1),r('recycle',{'spent':4},{'fuel':3})], 'policies':{'ore':{'import':True},'power':{'target':10}}}
        out=calculate(d,'solve')
        self.assertTrue(out['ok'])
        self.assertAlmostEqual(next(x['import'] for x in out['flows'] if x['product']=='ore'),1)
    def test_no_silent_import(self):
        self.assertFalse(calculate({'recipes':[r('a',{'ore':1},{'iron':1})],'policies':{'iron':{'target':1}}},'solve')['ok'])
    def test_surplus_and_cap(self):
        d={'recipes':[r('a',{'ore':1},{'iron':1,'waste':1})], 'policies':{'ore':{'import':True,'cap':2},'iron':{'target':1},'waste':{'surplus':True}}}
        self.assertTrue(calculate(d,'solve')['ok'])
        d['policies']['iron']['target']=3
        self.assertFalse(calculate(d,'solve')['ok'])
    def test_audit_period(self):
        d={'recipes':[r('a',{'ore':2},{'iron':1},count=2,load=.5)]}
        d['recipes'][0]['duration']=30
        self.assertAlmostEqual(next(x['net'] for x in calculate(d,'audit')['flows'] if x['product']=='iron'),2)
    def test_invalid(self):
        with self.assertRaises(ValueError):
            calculate({'recipes':[r('a',{}, {'x':1},min=3,max=2)]},'solve')

if __name__=='__main__': unittest.main()
