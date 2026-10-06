using System;
using System.Collections.Generic;
using Mafi;
using Mafi.Core.Entities;
using Mafi.Core.Entities.Static.Layout;
using Mafi.Core.Factory.Machines;
using Mafi.Core.Factory.Recipes;
using Mafi.Core.Terrain;

namespace BalancerPlanner {
    public sealed class GameSnapshotReader {
        readonly EntitiesManager entities;
        public GameSnapshotReader(EntitiesManager manager){entities=manager;}
        static string Name(Mafi.Core.Prototypes.Proto proto) {
            var value=proto.Strings.Name.ToString();
            var identifiers=new[]{"AssemblyManual","AssemblyElectrified","AssemblyElectrifiedT2","AssemblyRoboticT1","AssemblyRoboticT2"};
            var index=Array.IndexOf(identifiers,proto.Id.ToString());
            if(index>=0)return "装配机"+new[]{"I","II","III","IV","V"}[index];
            return string.IsNullOrWhiteSpace(value)?proto.Id.ToString():value;
        }
        public BuildingSnapshot[] ReadArea(RectangleTerrainArea2i area) {
            var rows=new List<BuildingSnapshot>();
            foreach(var entity in entities.GetAllEntitiesOfType<LayoutEntity>()) {
                if(!entity.IsDestroyed && entity.IsConstructed && entity.IsSelected(area)) {
                    if(rows.Count>=1000)throw new InvalidOperationException("一次最多选择1000座建筑，请缩小范围");
                    rows.Add(Read(entity));
                }
            }
            return rows.ToArray();
        }
        public BuildingSnapshot[] Refresh(BuildingSnapshot[] previous) {
            var wanted=new HashSet<string>();foreach(var row in previous)wanted.Add(row.Id);
            var rows=new List<BuildingSnapshot>();
            foreach(var entity in entities.GetAllEntitiesOfType<LayoutEntity>())
                if(!entity.IsDestroyed && entity.IsConstructed && wanted.Contains(entity.Id.ToString()))rows.Add(Read(entity));
            return rows.ToArray();
        }
        public BuildingSnapshot Read(LayoutEntity entity) {
            var row=new BuildingSnapshot {Id=entity.Id.ToString(),BuildingId=entity.Prototype.Id.ToString(),Name=Name(entity.Prototype),Paused=entity.IsPaused};
            row.Workers=entity.Prototype.Costs.Workers;
            var maintenance=entity.Prototype.Costs.Maintenance;
            if(maintenance.Product!=null){
                row.MaintenanceProduct=maintenance.Product.Id.ToString();
                row.ProductNames[row.MaintenanceProduct]=Name(maintenance.Product);
                row.MaintenancePer60=maintenance.MaintenancePerMonth.Value.ToDouble()*60/Duration.OneMonth.Seconds.ToDouble();
            }
            var machine=entity as Machine;
            if(machine==null){row.UnsupportedReason="首版暂不计算该特殊建筑";return row;}
            if(machine.Prototype.GetType()!=typeof(MachineProto)){row.UnsupportedReason="特殊机器原型待适配";return row;}
            row.State=machine.CurrentState.ToString();row.Boosted=machine.IsBoosted;
            row.SpeedFactor=machine.SpeedFactor.ToDouble();row.DurationMultiplier=machine.DurationMultiplier.ToDouble();
            if(machine.RecipesAssigned.Count!=1){row.UnsupportedReason="未指定配方，或配置了多个配方（暂不支持排程）";return row;}
            var recipe=machine.RecipesAssigned[0];row.RecipeId=recipe.Id.ToString();
            var binding=machine.Prototype.GetRecipeBindingFor(recipe);
            row.Duration=binding.Duration.Seconds.ToDouble();
            if(row.Duration<=0){row.UnsupportedReason="配方周期无效";return row;}
            // Keep unsupported modifiers explicit until their UI semantics are verified.
            if(Math.Abs(row.SpeedFactor-1)>1e-7 || Math.Abs(row.DurationMultiplier-1)>1e-7 || Math.Abs(machine.VirtualOutputMultiplier.ToDouble()-1)>1e-7){row.UnsupportedReason="存在速度/周期/虚拟产出修正，尚未核验";return row;}
            row.PowerMw=(double)machine.PowerRequired.Value/Electricity.OneKw.Value/1000;
            foreach(var input in recipe.AllInputs){
                var id=input.Product.Id.ToString();double previous;row.Inputs.TryGetValue(id,out previous);row.Inputs[id]=previous+input.Quantity.Value*binding.Multiplier;row.ProductNames[id]=Name(input.Product);
            }
            foreach(var output in recipe.AllOutputs){
                var id=output.Product.Id.ToString();double previous;row.Outputs.TryGetValue(id,out previous);row.Outputs[id]=previous+output.Quantity.Value*binding.Multiplier;row.ProductNames[id]=Name(output.Product);
            }
            return row;
        }
    }
}
