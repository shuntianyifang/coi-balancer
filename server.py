import json
import math
import copy
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import numpy as np
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from nuclear import compiled, analyze

ROOT = Path(__file__).parent

def number(v, label):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f'{label} 必须是有限数字')
    return float(v)

def validate(data):
    recipes = data['recipes']
    if not recipes or len(recipes) > 500:
        raise ValueError('配方数量必须在 1–500 之间')
    ids = set()
    for r in recipes:
        if not r['id'] or r['id'] in ids:
            raise ValueError('配方 ID 必须唯一且非空')
        ids.add(r['id'])
        if number(r['duration'], '周期') <= 0:
            raise ValueError('周期必须大于零')
        for side in ['inputs', 'outputs']:
            for p, q in r[side].items():
                if not p or number(q, '物料数量') < 0:
                    raise ValueError('物料数量不能为负')
        for k in ['power', 'workers', 'maintenance']:
            number(r.get(k, 0), k)
        if number(r.get('cost', 1), '目标成本') <= 0:
            raise ValueError('目标成本必须大于零')
    return recipes

def calculate(data, mode):
    data = copy.deepcopy(data)
    validate(data)
    plant_report = analyze(data) if mode == 'audit' and any(r.get('reactorType') for r in data['recipes']) else None
    if plant_report:
        for i in data.get('instances',[]):
            if i['id'] in plant_report['equipmentLoads']: i['load'] = plant_report['equipmentLoads'][i['id']]
    data = compiled(data, mode)
    rs = validate(data)
    if mode == 'audit' and 'instances' in data:
        by_id = {r['id']:r for r in rs}
        for r in rs: r['count'], r['load'] = 0, 0
        running = {r['id']:0 for r in rs}
        instance_ids = set()
        for instance in data['instances']:
            if instance['id'] in instance_ids: raise ValueError('建筑实例 ID 重复')
            instance_ids.add(instance['id'])
            recipe_id = instance['recipeId']
            if recipe_id not in by_id: raise ValueError('建筑引用不存在的配方')
            r = by_id[recipe_id]
            if r.get('buildingId') and instance.get('buildingId') != r['buildingId']:
                raise ValueError('配方与建筑类型不匹配')
            load = number(instance.get('load',1), '建筑负荷')
            if not 0 <= load <= 1: raise ValueError('建筑负荷必须在 0–1')
            r['count'] += 1
            running[recipe_id] += load if instance.get('enabled',True) else 0
        for r in rs: r['load'] = running[r['id']]/r['count'] if r['count'] else 0
    products = sorted({p for r in rs for s in ['inputs', 'outputs'] for p in r[s]})
    rates = np.array([[60 / r['duration'] * (r['outputs'].get(p, 0) - r['inputs'].get(p, 0)) for r in rs] for p in products])
    buildings = None
    if mode == 'audit':
        x = np.array([number(r.get('count', 0), '建筑数量') * number(r.get('load', 1), '负荷') for r in rs])
        if any(r.get('count', 0) < 0 or not 0 <= r.get('load', 1) <= 1 for r in rs):
            raise ValueError('数量不能为负，负荷必须在 0–1')
        imports = np.zeros(len(products))
        buildings = [r.get('count', 0) for r in rs]
    else:
        policies = data.get('policies', {})
        if set(policies) - set(products):
            raise ValueError('约束包含配方中不存在的物料')
        imported = [p for p in products if policies.get(p, {}).get('import', False)]
        m, n = len(products), len(rs)
        cols = np.zeros((m, len(imported)))
        for j, p in enumerate(imported):
            cols[products.index(p), j] = 1
        a = np.concatenate([rates, cols], axis=1)
        eq, beq, ub, bub = [], [], [], []
        for i, p in enumerate(products):
            pol = policies.get(p, {})
            target = number(pol.get('target', 0), '目标')
            if target < 0:
                raise ValueError('目标不能为负')
            if pol.get('surplus', False):
                ub.append(-a[i]); bub.append(-target)
            else:
                eq.append(a[i]); beq.append(target)
        for station,cap in data.get('stationWater',{}).items():
            cap=number(cap,'电站外部供水上限')
            if cap<0: raise ValueError('供水上限不能为负')
            water_row=[60/r['duration']*(r['inputs'].get('water',0)-r['outputs'].get('water',0)) if r.get('station')==station else 0 for r in rs]+[0]*len(imported)
            ub.append(water_row);bub.append(cap)
        bounds = []
        for r in rs:
            low = number(r.get('min', 0), '最小运行量')
            high = r.get('max')
            high = None if high is None else number(high, '最大运行量')
            if low < 0 or high is not None and high < low:
                raise ValueError('运行量上下限不合法')
            bounds.append((low, high))
        for p in imported:
            cap = policies[p].get('cap')
            cap = None if cap is None else number(cap, '进口上限')
            if cap is not None and cap < 0:
                raise ValueError('进口上限不能为负')
            bounds.append((0, cap))
        objective = [r.get('cost', 1) for r in rs] + [number(policies[p].get('cost', 100), '进口成本') for p in imported]
        if any(v < 0 for v in objective):
            raise ValueError('成本不能为负')
        if mode == 'integer':
            # x = productive running capacity, z = installed integer buildings.
            size = len(objective)
            constraints = []
            if eq:
                constraints.append(LinearConstraint(np.pad(np.array(eq), ((0,0),(0,n))), beq, beq))
            if ub:
                constraints.append(LinearConstraint(np.pad(np.array(ub), ((0,0),(0,n))), -np.inf, bub))
            capacity = np.zeros((n, size+n))
            for j in range(n):
                capacity[j,j] = 1
                capacity[j,size+j] = -1
            constraints.append(LinearConstraint(capacity, [-0.0 if r.get('full',False) else -np.inf for r in rs], 0))
            cap = data.get('buildingLimit')
            if cap is not None:
                cap = number(cap, '建筑总数上限')
                if cap < 0: raise ValueError('建筑上限不能为负')
                constraints.append(LinearConstraint([([0]*size)+([1]*n)], -np.inf, cap))
            lower = [b[0] for b in bounds] + [0]*n
            upper = [np.inf if b[1] is None else b[1] for b in bounds] + [np.inf]*n
            c = [r.get('cost',1)*1e-6 for r in rs] + objective[n:] + [r.get('cost',1) for r in rs]
            result = milp(c, integrality=[0]*size+[1]*n, bounds=Bounds(lower,upper), constraints=constraints, options={'time_limit':20})
            if result.success:
                buildings = [int(round(v)) for v in result.x[size:]]
        else:
            result = linprog(objective, A_eq=np.array(eq) if eq else None, b_eq=beq or None, A_ub=np.array(ub) if ub else None, b_ub=bub or None, bounds=bounds, method='highs')
        if not result.success:
            return {'ok': False, 'message': '这些约束无可行解。检查禁用的进口、配方容量、固定满载和副产物去向。', 'solver': result.message}
        x = result.x[:n]
        imports = cols @ result.x[n:n+len(imported)]
    net = rates @ x
    flows = []
    for i, p in enumerate(products):
        target = data.get('policies', {}).get(p, {}).get('target', 0)
        flows.append({'product': p, 'net': float(net[i]), 'import': float(imports[i]), 'target': target, 'remainder': float(net[i] + imports[i] - target)})
    if buildings is None: buildings = [math.ceil(max(0,v-1e-7)) for v in x]
    warnings = [f"{r['name']}：{r.get('status','未标记')}；{r.get('source','缺少来源')}" for r,v in zip(rs,x) if v>1e-7 and (r.get('status') != '已交叉验证' or not r.get('source'))]
    if plant_report:
        for f in flows:
            if f['remainder'] < -1e-6 and f['product'] not in ['electricity'] and '@' not in f['product']:
                warnings.append(f"{f['product']} 存在 {abs(f['remainder']):.3f}/60 缺口；核电结果需要外部供给或补齐辅助链。")
    return {'ok': True, 'mode': mode, 'plant':plant_report, 'warnings': warnings, 'flows': flows, 'recipes': [{'id': r['id'], 'name': r['name'], 'rate': float(v), 'buildings': b, 'load': float(v/b) if b else 0, 'templateId':r.get('templateId',r['id'].split('@')[0]),'station':r.get('station')} for r,v,b in zip(rs,x,buildings)], 'totals': {**{k: float(sum(r.get(k,0)*v for r,v in zip(rs,x))) for k in ['power','maintenance']}, 'workers':float(sum(r.get('workers',0)*b for r,b in zip(rs,buildings))), 'buildings':float(sum(buildings))}}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)
    def do_POST(self):
        try:
            if self.path not in ['/api/audit', '/api/solve', '/api/integer','/api/plant']:
                self.send_error(404); return
            length = int(self.headers.get('Content-Length', 0))
            if length > 2_000_000:
                raise ValueError('数据超过 2MB')
            payload=json.loads(self.rfile.read(length))
            if self.path=='/api/plant':
                validate(payload); output={'ok':True,**analyze(payload)}
            else: output = calculate(payload, self.path.rsplit('/', 1)[1])
            self.send_response(200)
        except Exception as e:
            output = {'ok': False, 'message': str(e)}
            self.send_response(400)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(output, ensure_ascii=False).encode())

if __name__ == '__main__':
    print('CoI 配平器：http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
