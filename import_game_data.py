"""Validate a runtime export and create a scene; never overwrite bundled data."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from server import validate

ASSEMBLY_NAMES = {
    'AssemblyManual': '装配机I',
    'AssemblyElectrified': '装配机II',
    'AssemblyElectrifiedT2': '装配机III',
    'AssemblyRoboticT1': '装配机IV',
    'AssemblyRoboticT2': '装配机V',
}

def numeric(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f'{label} 无效')
    return value


def convert(package, source_hash, evidence=None):
    if package.get('schemaVersion') != 1 or not package.get('gameVersion'):
        raise ValueError('缺少已识别的导出格式或运行时游戏版本')
    if package.get('errors'):
        raise ValueError('导出存在错误，请先检查原始包 errors；不生成不完整目录')
    if evidence and evidence.get('gameVersion') != package['gameVersion']:
        raise ValueError('核验证据与导出版本不一致')
    products = {p['id']: p for p in package['products']}
    machines = {b['id']: b for b in package['buildings']}
    if len(products) != len(package['products']) or len(machines) != len(package['buildings']):
        raise ValueError('产品或建筑 ID 重复')
    recipes, excluded, ids = [], [], set()
    for binding in package['bindings']:
        machine = machines[binding['buildingId']]
        key = binding['buildingId'] + '::' + binding['recipeId']
        if key in ids:
            raise ValueError('重复建筑配方绑定：' + key)
        ids.add(key)
        # Export only ordinary MachineProto; derived machinery needs review.
        if machine['type'] != 'Mafi.Core.Factory.Machines.MachineProto':
            excluded.append({'id': key, 'reason': '特殊建筑原型：' + machine['type']})
            continue
        duration = numeric(binding['durationSeconds'], '周期', True)
        multiplier = numeric(binding['multiplier'], '数量倍率', True)
        power_multiplier = numeric(binding['powerMultiplier'], '耗电倍率')
        io = {}
        for side in ['inputs', 'outputs']:
            io[side] = {}
            for item in binding[side]:
                product = item['productId']
                if product not in products:
                    raise ValueError('未知物料：' + product)
                quantity = numeric(item['quantity'], '单次数量') * multiplier
                io[side][product] = io[side].get(product, 0) + quantity
        display_name = (binding['name'] if binding['name'] != binding['recipeId'] else '') or (' + '.join(products[p]['name'] for p in io['inputs']) + ' → ' + ' + '.join(products[p]['name'] for p in io['outputs']))
        maintenance = machine.get('maintenance')
        maintenance_rate = 0
        maintenance_product = None
        if maintenance:
            maintenance_rate = numeric(maintenance['quantityPerMonth'], '维护月消耗') * 60 / numeric(maintenance['monthSeconds'], '游戏月秒数', True)
            maintenance_product = maintenance['productId']
            if maintenance_rate and maintenance_product not in products:
                raise ValueError('未知维护物料：' + str(maintenance_product))
        recipes.append({'id': key, 'gameRecipeId': binding['recipeId'], 'buildingId': binding['buildingId'],
                        'name': display_name, **io, 'duration': duration,
                        'power': numeric(machine['electricityRaw'], '耗电') / numeric(machine['electricityOneKwRaw'], 'kW 基数', True) / 1000 * power_multiplier,
                        'workers': numeric(machine['workers'], '工人'),
                        'maintenance': maintenance_rate, 'maintenanceUnknown': maintenance is None,
                        'maintenanceProduct': maintenance_product, 'maintenanceSource': maintenance,
                        'count': 0, 'load': 1,
                        'status': '游戏运行时导出 · 原版身份及界面速率待核验',
                        'source': f"BalancerDataExporter {package['exporterVersion']} / {package['gameVersion']} / SHA256 {source_hash}"})
    if not recipes:
        raise ValueError('没有可导入的普通建筑配方')
    if len(recipes) > 500:
        raise ValueError('导出普通配方超过当前求解器 500 条限制；需先分目录，不可静默截断')
    scene = {'version': f"游戏导出 {package['gameVersion']} · 待原版身份与游戏抽查",
             'productNames': {k: v['name'] for k, v in products.items()},
             'buildings': [{'id': b['id'], 'name': ASSEMBLY_NAMES.get(b['id'], b['name']), 'icon': '/icons/factory.svg'} for b in machines.values()],
             'recipes': recipes, 'instances': [], 'policies': {},
             'dataSource': {'sha256': source_hash, 'exporterVersion': package['exporterVersion'],
                            'gameVersion': package['gameVersion'], 'exportedAt': package['exportedAt'],
                            'modListComplete': package.get('modListComplete', False),
                            'prototypeOwners': package.get('prototypeOwners', []), 'assemblyHashes': package.get('assemblyHashes', {}), 'verified': False,
                            'maintenanceSupported': all(not r['maintenanceUnknown'] for r in recipes)}}
    validate(scene)
    if evidence:
        checked = []
        for sample in evidence.get('samples', []):
            if not sample.get('gameUiChecked'):
                continue
            recipe = next((r for r in recipes if r['buildingId'] == sample['buildingId'] and r['gameRecipeId'] == sample['recipeId']), None)
            if recipe is None:
                raise ValueError('核验条目不在本次目录中')
            for side in ['inputs', 'outputs']:
                actual = {p: q * 60 / recipe['duration'] for p, q in recipe[side].items()}
                expected = sample[side + 'Per60']
                if actual.keys() != expected.keys() or any(abs(q - expected[p]) > 1e-7 for p, q in actual.items()):
                    raise ValueError('核验速率与本次导出不一致：' + recipe['id'])
            recipe['status'] = '已交叉验证'
            recipe['source'] += ' / 游戏界面样本核验'
            checked.append(recipe['id'])
        scene['dataSource']['checkedBindings'] = checked
        scene['dataSource']['runtimeEvidence'] = {k: evidence.get(k) for k in ['build', 'update', 'loadedExternalMods', 'loadedOfficialDlc']}
        scene['version'] = f"游戏导出 {package['gameVersion']} · {len(recipes)}配方 / {len(checked)}条界面抽查通过"
    report = {'importedBindings': len(recipes), 'exportedBindings': len(package['bindings']),
              'excluded': excluded, 'specialPrototypes': [{k: p.get(k) for k in ['id', 'name', 'type']} for p in package.get('specialPrototypes', [])],
              'warnings': [('维护采用基础月消耗折算的运行量加权估算；不同维护等级分别统计，未模拟动态维护和过载。' if scene['dataSource']['maintenanceSupported'] else '维护值未知，不可用作维护预算。'),
                           '尚未确认完整加载 MOD 列表；原版身份需在游戏中确认。',
                           '运行时导出不等于游戏界面抽查完成。']}
    return scene, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    raw = args.export.read_bytes()
    evidence = json.loads(args.evidence.read_text(encoding='utf-8')) if args.evidence else None
    scene, report = convert(json.loads(raw.decode('utf-8-sig')), hashlib.sha256(raw).hexdigest(), evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit('输出文件已存在，请选择新路径，避免覆盖用户方案。')
    args.output.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding='utf-8')
    args.output.with_suffix('.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Imported {len(scene["recipes"])} bindings; review the accompanying report before use.')
