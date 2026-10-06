using System;
using System.IO;
using BalancerPlanner;

public static class SnapshotTests {
    static int checks;
    static void Check(bool value,string description){checks++;if(!value)throw new Exception(description);}
    public static void Main(string[] args) {
        var row=new BuildingSnapshot{Id="1",Name="装配机I",BuildingId="AssemblyManual",RecipeId="parts",Duration=40,Workers=4,PowerMw=.04,MaintenanceProduct="maintenance1",MaintenancePer60=2};
        row.Inputs["iron"]=3;row.Outputs["parts"]=4;
        var plan=new SnapshotPlan();plan.Add(row);plan.Add(row);
        Check(plan.Calculate().Buildings==1,"Duplicate selection must not duplicate buildings");
        Check(plan.Calculate().Inputs["iron"]==4.5,"40 second cycle input normalization");
        Check(plan.Calculate().Outputs["parts"]==6,"40 second cycle output normalization");
        row.Inputs["iron"]=100;
        Check(plan.Calculate().Inputs["iron"]==4.5,"Snapshot must not retain mutable source dictionaries");
        var boosted=plan.Rows[0].Copy();boosted.Id="2";boosted.Boosted=true;boosted.MaintenanceProduct="maintenance2";plan.Add(boosted);
        Check(plan.Calculate().Outputs["parts"]==18,"Exact x2 boosted throughput");
        Check(plan.Calculate().Maintenance.Count==2,"Different maintenance grades remain distinct");
        var paused=boosted.Copy();paused.Id="3";paused.Paused=true;plan.Add(paused);
        Check(plan.Calculate().Outputs["parts"]==18,"Paused building must have zero material throughput");
        Check(plan.Calculate().Workers==12,"Paused building retains configured workers");
        var unsupported=paused.Copy();unsupported.Id="4";unsupported.Paused=false;unsupported.UnsupportedReason="multi recipe";plan.Add(unsupported);
        Check(plan.Calculate().Incomplete && plan.Calculate().Unsupported==1,"Unsupported configuration must be explicit");
        Check(plan.Calculate().Outputs["parts"]==18,"Unsupported machine must not silently contribute throughput");
        plan.Remove("2");Check(plan.Calculate().Outputs["parts"]==6,"Removing one snapshot affects only local plan");
        Directory.CreateDirectory(args[0]);
        var path=Path.Combine(args[0],Guid.NewGuid().ToString("N")+".json");
        var saved=new SavedSnapshot{GameVersion="test",CapturedAt="test",Buildings=plan.Rows};saved.Save(path);
        var restored=SavedSnapshot.Load(path);
        var other=new SnapshotPlan();other.Replace(restored.Buildings);
        Check(other.Calculate().Buildings==3,"External snapshot roundtrip");
        Check(other.Calculate().Outputs["parts"]==6,"Roundtrip preserves quantities and pause state");
        Check(restored.Buildings[0].Name=="装配机I","Unicode name roundtrip");
        bool rejected=false;try{saved.Save(path);}catch(IOException){rejected=true;}
        Check(rejected,"Do not overwrite previous snapshots");
        var invalid=new BuildingSnapshot{Id="invalid",Duration=0};other.Clear();other.Add(invalid);
        rejected=false;try{other.Calculate();}catch(ArgumentException){rejected=true;}
        Check(rejected,"Invalid duration must not yield infinite rates");
        Console.WriteLine("Mod snapshot tests: "+checks+" checks passed.");
    }
}
