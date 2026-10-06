"""Steady-state reactor operating settings and station-local energy allocation."""
import copy
import math
import numpy as np
from scipy.optimize import linprog

THERMAL = ['steam_super','steam_high','steam_low','steam_depleted','mechanical_mw']

def finite(value, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(label+'必须是有限数字')
    return value

def operating_recipe(instance, recipe, parameters=None):
    r=copy.deepcopy(recipe)
    if not r.get('reactorType'): return r
    p=parameters or {}
    for key,value in p.items():
        finite(value,'反应堆参数 '+key)
        if value<=0: raise ValueError('反应堆基础参数必须大于零')
    typ=r['reactorType']
    max_level=3 if typ=='nr1' else 4
    level=finite(instance.get('level',max_level),'档位')
    if level not in range(1,max_level+1): raise ValueError('反应堆档位不合法')
    control=instance.get('control','manual')
    if control not in ['manual','auto'] or typ=='nr1' and control=='auto': raise ValueError('该反应堆不支持此调节方式')
    effective=level
    if control=='auto':
        effective=finite(instance.get('averageLevel',level),'平均档位')
        if not 1<=effective<=level: raise ValueError('自动调节平均档位必须在第一档与所选最高档之间')
    r['inputs'],r['outputs'],r['duration']={}, {},60
    if typ=='fbr':
        mode=instance.get('breeding',1)
        if mode not in [0,1,3] or isinstance(mode,bool): raise ValueError('增殖模式必须为 0、1 或 3')
        fraction=finite(instance.get('blanketFraction',1),'毯式增殖供料比例')
        if not 0<=fraction<=1: raise ValueError('毯式供料比例必须在 0–1')
        core=p.get('fbrCorePerLevel',4)*effective*(.5 if mode==0 else 1)
        steam=p.get('fbrSteamPerLevel',96)*effective*(.25 if mode==3 else 1)
        r['inputs']={'water':steam,'core':core}
        r['outputs']={'steam_super':steam,'spent_core':core}
        if mode:
            blanket=p.get('fbrCorePerLevel',4)*effective*mode*fraction
            r['inputs']['blanket']=blanket; r['outputs']['enriched_blanket']=blanket
    else:
        fuel=instance.get('fuel','uranium_rod')
        if fuel not in (['uranium_rod'] if typ=='nr1' else ['uranium_rod','mox_rod']): raise ValueError('燃料与反应堆不兼容')
        steam=p.get('nrSteamPerLevel',96)*effective
        rods=p.get('nrRodsPerLevel',.5)*effective
        r['inputs']={'water':steam,fuel:rods}
        r['outputs']={'steam_high':steam,'spent_mox' if fuel=='mox_rod' else 'spent_fuel':rods}
    r['name']+=f" · 档位 {effective:g}"+(f" · {instance.get('breeding',1)}×增殖" if typ=='fbr' else '')
    return r

def scope_recipe(recipe, group):
    r=copy.deepcopy(recipe)
    r['station']=group
    for side in ['inputs','outputs']:
        r[side]={f'{p}@{group}' if p in THERMAL else p:q for p,q in r[side].items()}
    return r

def compiled(data, mode):
    """Fix chosen reactors; optimize auxiliary buildings independently per station."""
    out=copy.deepcopy(data); rs=out['recipes']
    by_id={r['id']:r for r in rs}
    instances=out.get('instances',[])
    special=[i for i in instances if by_id.get(i.get('recipeId'),{}).get('reactorType')]
    if not special and not any(r.get('reactorType') for r in rs): return out
    params=out.get('reactorParameters')
    if mode=='audit':
        generated=[]; converted=[]
        for i in instances:
            original=by_id.get(i.get('recipeId'))
            if original is None: raise ValueError('建筑引用不存在的配方')
            r=operating_recipe(i,original,params)
            if r.get('reactorType') or r.get('plantRole'):
                r=scope_recipe(r,i.get('station','主电站'))
            r['id']='instance:'+i['id']; r['count']=1
            r['load']=0 if i.get('enabled') is False else (1 if r.get('reactorType') else i.get('load',1))
            generated.append(r); converted.append({**i,'recipeId':r['id'],'load':r['load']})
        # Retain unused normal recipes for material goals and zero-rate audit rows.
        out['recipes']=[{**r,'count':0,'load':0} for r in rs if not r.get('reactorType')]+generated
        out['instances']=converted
        return out
    groups=sorted({i.get('station','主电站') for i in special}) or ['主电站']
    generated=[r for r in rs if not r.get('reactorType') and not r.get('plantRole')]
    for i in special:
        r=scope_recipe(operating_recipe(i,by_id[i['recipeId']],params),i.get('station','主电站'))
        r.update(id='reactor:'+i['id'],min=0 if i.get('enabled') is False else 1,max=0 if i.get('enabled') is False else 1,full=True)
        generated.append(r)
    for group in groups:
        for template in rs:
            if template.get('plantRole'):
                r=scope_recipe(template,group);r['id']=template['id']+'@'+group;r['name']+=' · '+group
                r['templateId']=template['id'];r['station']=group
                generated.append(r)
    out['recipes']=generated
    # Explicit original steam policies expand into their own station networks.
    policies=out.setdefault('policies',{})
    for p in THERMAL:
        pol=policies.pop(p,None)
        if pol:
            if pol.get('import'): raise ValueError('核电优化不允许外部导入蒸汽或机械功')
            if pol.get('target',0): raise ValueError('蒸汽目标请在具体电站组设置')
            for group in groups: policies[f'{p}@{group}']=copy.deepcopy(pol)
    return out

def analyze(data):
    by_id={r['id']:r for r in data['recipes']}
    groups={}; fixed=[]
    for i in data.get('instances',[]):
        r=by_id.get(i.get('recipeId'))
        if not r: raise ValueError('建筑引用不存在的配方')
        if r.get('buildingId') and r['buildingId']!=i.get('buildingId'): raise ValueError('配方与建筑类型不匹配')
        finite(i.get('load',1),'负荷')
        if not 0<=i.get('load',1)<=1: raise ValueError('负荷必须在 0–1')
        r=operating_recipe(i,r,data.get('reactorParameters'))
        group=i.get('station','主电站')
        if r.get('reactorType') or r.get('plantRole'):
            groups.setdefault(group,[]).append((i,r))
        else: fixed.append((i,r))
    reports=[]; loads={}; reactor_rows=[]
    for group,items in groups.items():
        supplies={p:0 for p in THERMAL}; water_demand=0; equipment=[]; warnings=[]
        for i,r in items:
            if r.get('reactorType'):
                on=i.get('enabled') is not False
                for p in THERMAL: supplies[p]+=r['outputs'].get(p,0) if on else 0
                water_demand+=r['inputs'].get('water',0) if on else 0
                reactor_rows.append({'id':i['id'],'recipe':r,'running':on})
                if i.get('control')=='auto': warnings.append('自动调节按用户填写的平均档位估算，最低运行档为第一档。')
                if r['reactorType']=='fbr' and i.get('breeding',1) and i.get('blanketFraction',1)<1: warnings.append('毯式增殖不足；核心燃烧及所选模式换热量保持独立。')
            else: equipment.append((i,r))
        gross=0; recovered=0; residual=supplies.copy()
        if equipment:
            a=np.array([[60/r['duration']*(r['outputs'].get(p,0)-r['inputs'].get(p,0)) for i,r in equipment] for p in THERMAL])
            objective=[-60/r['duration']*(r['outputs'].get('electricity',0)*1000+r['outputs'].get('water',0))+1e-5 for i,r in equipment]
            bounds=[(0,0 if i.get('enabled') is False else i.get('load',1)) for i,r in equipment]
            result=linprog(objective,A_ub=-a[:4],b_ub=[supplies[p] for p in THERMAL[:4]],A_eq=a[4:5],b_eq=[-supplies['mechanical_mw']],bounds=bounds,method='highs')
            if not result.success: raise ValueError('发电链容量分配失败：'+result.message)
            for (i,r),v in zip(equipment,result.x):
                loads[i['id']]=float(v)
                gross+=r['outputs'].get('electricity',0)*60/r['duration']*v
                recovered+=r['outputs'].get('water',0)*60/r['duration']*v
            remaining=a@result.x+np.array(list(supplies.values()))
            residual=dict(zip(THERMAL,map(float,remaining)))
        capacities={p:sum(r['inputs'].get(p,0)*60/r['duration']*(0 if i.get('enabled') is False else i.get('load',1)) for i,r in equipment) for p in THERMAL}
        leftovers=sum(max(0,residual[p]) for p in THERMAL[:4])
        if leftovers>1e-6: warnings.append(f'仍有 {leftovers:.3f}/60 蒸汽未被配套设备处理；当前配置不能持续承接设定档位。')
        generator_capacity=sum(r['outputs'].get('electricity',0)*60/r['duration']*(0 if i.get('enabled') is False else i.get('load',1)) for i,r in equipment)
        if supplies['steam_high']>0 and capacities['steam_high']<supplies['steam_high']: warnings.append('高压蒸汽入口处理容量不足。')
        if supplies['steam_super']>0 and capacities['steam_super']<supplies['steam_super']: warnings.append('超高压蒸汽入口处理容量不足。')
        # Explicit supply promises are checked against recovered water, not silently invented.
        external=data.get('stationWater',{}).get(group)
        if external is not None:
            finite(external,'外部供水上限')
            if external<0: raise ValueError('外部供水上限不能为负')
            if external+recovered+1e-6<water_demand: warnings.append('外部供水上限与回收水之和不足以满足所选运行档位。')
        else: warnings.append('外部供水能力未填写；这里只计算所需补水，未确认供水可行。')
        reports.append({'station':group,'grossMW':float(gross),'generatorCapacityMW':float(generator_capacity),'waterDemand':float(water_demand),'recoveredWater':float(recovered),'makeupWater':max(0,float(water_demand-recovered)),'residual':residual,'capacities':capacities,'warnings':warnings})
    auxiliary_mw=sum(max(0,r.get('power',0))*(0 if i.get('enabled') is False else i.get('load',1)) for i,r in fixed)
    gross=sum(s['grossMW'] for s in reports)
    return {'stations':reports,'grossMW':gross,'auxiliaryMW':auxiliary_mw,'netMW':gross-auxiliary_mw,'equipmentLoads':loads,'reactors':reactor_rows,'assumption':'稳态理想效率、同组蒸汽与机械轴视为已连通。发电量为燃料和补水得到满足时的容量结果，不模拟启停、轴充能或应急冷却。'}
