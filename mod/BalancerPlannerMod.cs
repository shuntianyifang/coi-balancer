using System;
using Mafi;
using Mafi.Core.Mods;
using Mafi.Core.Simulation;
using Mafi.Core.Entities;
using UnityEngine;

namespace BalancerPlanner {
    public sealed class BalancerPlannerMod : DataOnlyMod, IMod {
        GameObject overlay;
        public BalancerPlannerMod(ModManifest manifest):base(manifest){}
        bool IMod.IsUiOnly {get{return true;}}
        public override void RegisterPrototypes(ProtoRegistrator registrator){}
        void IMod.RegisterDependencies(DependencyResolverBuilder builder,Mafi.Core.Prototypes.ProtosDb db,bool gameWasLoaded){}
        void IMod.Initialize(DependencyResolver resolver,bool gameWasLoaded) {
            Log.Info("BalancerPlanner: Initialize called; gameWasLoaded="+gameWasLoaded);
            try {
                overlay=new GameObject("BalancerPlanner.ReadOnlyOverlay");
                var controller=overlay.AddComponent<PlannerOverlay>();
                controller.Initialize(resolver,Manifest.RootDirectoryPath);
                Log.Info("BalancerPlanner: UI-only initialized; F8 opens the calculator. No simulation state registered.");
            }catch(Exception error){Log.Error("BalancerPlanner: "+error);if(overlay!=null)UnityEngine.Object.Destroy(overlay);}
        }
        void IDisposable.Dispose(){if(overlay!=null)UnityEngine.Object.Destroy(overlay);overlay=null;}
    }
}
