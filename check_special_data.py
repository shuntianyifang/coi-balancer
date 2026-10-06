"""Compare exported reactor prototype parameters with the calculator model."""
import argparse
import json
from pathlib import Path
from nuclear import operating_recipe


def check(package):
    prototypes = {p['id']: p for p in package['specialPrototypes']}
    rows = []
    for identifier, kind in [('NuclearReactor', 'nr1'), ('NuclearReactor2', 'nr2'), ('FastBreederReactor', 'fbr')]:
        # Use type and level to resolve NR II if the ID changes between versions.
        if identifier not in prototypes and kind == 'nr2':
            identifier = next(p['id'] for p in package['specialPrototypes'] if 'NuclearReactorProto' in p['type'] and p['fields']['MaxPowerLevel'] == 4 and p['id'] != 'FastBreederReactor')
        fields = prototypes[identifier]['fields']
        duration = fields['ProcessDuration']['seconds']
        steam_base = fields['SteamOutPerPowerLevel']['Quantity'] * 60 / duration
        water_base = fields['WaterInPerPowerLevel']['Quantity'] * 60 / duration
        for pair in fields['FuelPairs']:
            fuel_base = 60 / pair['Duration']['seconds']
            fuel = 'mox_rod' if pair['FuelInProto']['id'] == 'Product_MoxRod' else 'uranium_rod'
            modes = fields['Enrichment']['Value']['EnrichmentSteps'] if kind == 'fbr' else [{'BreedingRatio': 0, 'FuelMultiplier': 1, 'SteamReductionDiv': 1}]
            for step in modes:
                for level in range(1, fields['MaxPowerLevel'] + 1):
                    recipe = operating_recipe({'level': level, 'fuel': fuel, 'breeding': step['BreedingRatio']}, {'id':kind, 'name':kind, 'reactorType':kind})
                    expected_water = water_base * level / step['SteamReductionDiv']
                    expected_steam = steam_base * level / step['SteamReductionDiv']
                    expected_fuel = fuel_base * level * step['FuelMultiplier']
                    matches = abs(recipe['inputs']['water'] - expected_water) < 1e-8
                    matches &= abs(recipe['outputs']['steam_super' if kind == 'fbr' else 'steam_high'] - expected_steam) < 1e-8
                    matches &= abs(recipe['inputs']['core' if kind == 'fbr' else fuel] - expected_fuel) < 1e-8
                    if kind == 'fbr' and step['BreedingRatio']:
                        expected_blanket = fields['Enrichment']['Value']['ProcessedPerLevel'] * fuel_base * level * step['BreedingRatio']
                        matches &= abs(recipe['inputs']['blanket'] - expected_blanket) < 1e-8
                    rows.append({'prototype':identifier, 'level':level, 'fuel':pair['FuelInProto']['id'], 'breeding':step['BreedingRatio'], 'matches':bool(matches)})
    return {'gameVersion':package['gameVersion'], 'ok':all(row['matches'] for row in rows),
            'checks':rows, 'scope':'仅比较原型参数与模型公式；未验证启停、自动控制、效率变化或事故机制。'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(json.loads(args.export.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Reactor prototype checks: {len(result['checks'])}, passed: {result['ok']}")
    raise SystemExit(0 if result['ok'] else 1)
