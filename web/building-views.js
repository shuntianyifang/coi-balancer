// Group only settings that affect operation; retain the original instances.
(function(root){
function groups(instances,recipes,merge){
 if(!merge)return instances.map(i=>[i]);
 const grouped=new Map();
 for(const i of instances){
  const r=recipes.find(r=>r.id===i.recipeId);
  const state=[i.buildingId,i.recipeId,i.enabled!==false];
  if(r?.reactorType){
   const level=i.level??(r.reactorType==='nr1'?3:4),control=i.control??'manual';
   state.push(level,control,control==='auto'?(i.averageLevel??level):null);
   if(r.reactorType==='nr2')state.push(i.fuel??'uranium_rod');
   if(r.reactorType==='fbr')state.push(i.breeding??1,(i.breeding??1)===0?null:(i.blanketFraction??1));
  }else state.push(i.load);
  if(r?.reactorType||r?.plantRole)state.push(i.station||'主电站');
  // Unknown settings must not silently disappear through grouping.
  const known=new Set(['id','buildingId','recipeId','enabled','load','level','control','averageLevel','fuel','breeding','blanketFraction','station']);
  state.push(Object.keys(i).filter(k=>!known.has(k)).sort().map(k=>[k,i[k]]));
  const key=JSON.stringify(state);
  if(!grouped.has(key))grouped.set(key,[]);
  grouped.get(key).push(i);
 }
 return [...grouped.values()];
}
const api={groups};if(typeof module!=='undefined')module.exports=api;else root.BuildingViews=api;
})(typeof window!=='undefined'?window:globalThis);
