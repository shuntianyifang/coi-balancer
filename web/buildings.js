// Pure building calculations, shared with Node tests.
(function(root){
function validateInstance(instance, recipes){
 const r=recipes.find(r=>r.id===instance.recipeId);
 if(!r)throw Error('建筑引用不存在的配方');
 if(r.buildingId && r.buildingId!==instance.buildingId)throw Error('配方与建筑类型不匹配');
 if(!Number.isFinite(instance.load)||instance.load<0||instance.load>1)throw Error('建筑负荷必须在 0–1');
 return r;
}
function operatingRecipe(instance,recipe,parameters={}){
 const r=JSON.parse(JSON.stringify(recipe));if(!r.reactorType)return r;
 const type=r.reactorType,max=type==='nr1'?3:4,level=instance.level??max,control=instance.control??'manual';
 if(!Number.isInteger(level)||level<1||level>max)throw Error('反应堆档位不合法');
 if(!['manual','auto'].includes(control)||(type==='nr1'&&control==='auto'))throw Error('反应堆调节方式不合法');
 const actual=control==='auto'?(instance.averageLevel??level):level;
 if(!Number.isFinite(actual)||actual<1||actual>level)throw Error('自动平均档位必须在第一档与最高档之间');
 r.duration=60;
 if(type==='fbr'){
  const mode=instance.breeding??1,fraction=instance.blanketFraction??1;
  if(![0,1,3].includes(mode)||!Number.isFinite(fraction)||fraction<0||fraction>1)throw Error('增殖设置不合法');
  const core=(parameters.fbrCorePerLevel??4)*actual*(mode===0?.5:1),steam=(parameters.fbrSteamPerLevel??96)*actual*(mode===3?.25:1);
  r.inputs={water:steam,core};r.outputs={steam_super:steam,spent_core:core};
  if(mode){r.inputs.blanket=(parameters.fbrCorePerLevel??4)*actual*mode*fraction;r.outputs.enriched_blanket=r.inputs.blanket}
 }else{
  const fuel=instance.fuel??'uranium_rod';if(!(type==='nr1'?['uranium_rod']:['uranium_rod','mox_rod']).includes(fuel))throw Error('燃料与反应堆不兼容');
  const steam=(parameters.nrSteamPerLevel??96)*actual,rods=(parameters.nrRodsPerLevel??.5)*actual;
  r.inputs={water:steam,[fuel]:rods};r.outputs={steam_high:steam,[fuel==='mox_rod'?'spent_mox':'spent_fuel']:rods};
 }
 return r;
}
function flows(instance, recipes,parameters){const r=operatingRecipe(instance,validateInstance(instance,recipes),parameters),load=instance.enabled===false?0:r.reactorType?1:instance.load,factor=60/r.duration*load;return {inputs:Object.fromEntries(Object.entries(r.inputs).map(([p,q])=>[p,q*factor])),outputs:Object.fromEntries(Object.entries(r.outputs).map(([p,q])=>[p,q*factor])),power:(r.power||0)*load,workers:r.workers||0}}
const api={flows,validateInstance,operatingRecipe};if(typeof module!=='undefined')module.exports=api;else root.BuildingMath=api;
})(typeof window!=='undefined'?window:this);
