import copy
import unittest
from import_game_data import convert


def package():
    return {'schemaVersion':1, 'gameVersion':'test-version', 'exporterVersion':'0.1.0', 'exportedAt':'test', 'errors':[],
            'products':[{'id':'ore','name':'Ore'},{'id':'iron','name':'Iron'}],
            'buildings':[{'id':'furnace','name':'Furnace','type':'Mafi.Core.Factory.Machines.MachineProto','workers':4,'electricityRaw':2000,'electricityOneKwRaw':1}],
            'bindings':[{'buildingId':'furnace','recipeId':'smelt','name':'Smelt','durationSeconds':30,'multiplier':2,'powerMultiplier':.5,
                         'inputs':[{'productId':'ore','quantity':3,'hidden':True}], 'outputs':[{'productId':'iron','quantity':1}]}]}


class ImportTests(unittest.TestCase):
    def test_monthly_maintenance_conversion_and_grade(self):
        p = package()
        p['products'].append({'id':'maintenance1','name':'维护I'})
        p['buildings'][0]['maintenance'] = {'productId':'maintenance1','quantityPerMonth':2,'maxQuantityPerMonth':2,'monthSeconds':120}
        scene, _ = convert(p, 'hash')
        recipe = scene['recipes'][0]
        self.assertEqual(recipe['maintenance'], 1)
        self.assertEqual(recipe['maintenanceProduct'], 'maintenance1')
        self.assertTrue(scene['dataSource']['maintenanceSupported'])
        p['buildings'][0]['maintenance']['monthSeconds'] = 0
        with self.assertRaises(ValueError): convert(p, 'hash')

    def test_maintenance_grades_not_summed(self):
        from server import calculate
        scene, _ = convert(package(), 'hash')
        first = scene['recipes'][0]
        first.update(count=1, maintenance=2, maintenanceProduct='maintenance1', maintenanceUnknown=False)
        second = copy.deepcopy(first)
        second.update(id='second', count=1, maintenance=3, maintenanceProduct='maintenance2')
        scene['recipes'].append(second)
        scene.pop('instances')
        result = calculate(scene, 'audit')
        self.assertEqual(result['maintenanceByProduct'], {'maintenance1':2,'maintenance2':3})
        self.assertIsNone(result['totals']['maintenance'])

    def test_evidence_only_marks_matching_sample(self):
        evidence = {'gameVersion':'test-version','samples':[{'buildingId':'furnace','recipeId':'smelt','gameUiChecked':True,'inputsPer60':{'ore':12},'outputsPer60':{'iron':4}}]}
        scene, _ = convert(package(), 'hash', evidence)
        self.assertEqual(scene['recipes'][0]['status'], '已交叉验证')
        self.assertFalse(scene['dataSource']['verified'])
        evidence['samples'][0]['outputsPer60']['iron'] = 5
        with self.assertRaises(ValueError): convert(package(), 'hash', evidence)
        evidence['gameVersion'] = 'another-version'
        with self.assertRaises(ValueError): convert(package(), 'hash', evidence)

    def test_binding_multiplier_hidden_inputs_and_power(self):
        scene, report = convert(package(), 'hash')
        recipe = scene['recipes'][0]
        self.assertEqual(recipe['inputs']['ore'] * 60 / recipe['duration'], 12)
        self.assertEqual(recipe['outputs']['iron'] * 60 / recipe['duration'], 4)
        self.assertEqual(recipe['power'], 1)
        self.assertFalse(scene['dataSource']['verified'])
        self.assertEqual(report['importedBindings'], 1)

    def test_invalid_data_rejected(self):
        for change in ['duration','product','version','errors','duplicate']:
            p=package()
            if change=='duration': p['bindings'][0]['durationSeconds']=0
            if change=='product': p['bindings'][0]['inputs'][0]['productId']='missing'
            if change=='version': p['gameVersion']=None
            if change=='errors': p['errors']=['failed']
            if change=='duplicate': p['bindings'].append(copy.deepcopy(p['bindings'][0]))
            with self.subTest(change=change), self.assertRaises(ValueError): convert(p,'hash')

    def test_shared_recipe_has_distinct_building_binding(self):
        p=package()
        machine=copy.deepcopy(p['buildings'][0]);machine['id']='furnace2';p['buildings'].append(machine)
        binding=copy.deepcopy(p['bindings'][0]);binding['buildingId']='furnace2';binding['durationSeconds']=15;p['bindings'].append(binding)
        scene,_=convert(p,'hash')
        self.assertEqual(len({r['id'] for r in scene['recipes']}),2)
        self.assertEqual(scene['recipes'][1]['duration'],15)


if __name__=='__main__': unittest.main()
