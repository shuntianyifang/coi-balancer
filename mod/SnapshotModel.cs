using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.IO;

namespace BalancerPlanner {
    [DataContract]
    public sealed class BuildingSnapshot {
        [DataMember] public string Id;
        [DataMember] public string BuildingId;
        [DataMember] public string Name;
        [DataMember] public string RecipeId;
        [DataMember] public string State;
        [DataMember] public bool Paused;
        [DataMember] public bool Boosted;
        [DataMember] public double SpeedFactor;
        [DataMember] public double DurationMultiplier;
        [DataMember] public double Duration;
        [DataMember] public double PowerMw;
        [DataMember] public int Workers;
        [DataMember] public string MaintenanceProduct;
        [DataMember] public double MaintenancePer60;
        [DataMember] public string UnsupportedReason;
        [DataMember] public Dictionary<string,double> Inputs = new Dictionary<string,double>();
        [DataMember] public Dictionary<string,double> Outputs = new Dictionary<string,double>();
        [DataMember] public Dictionary<string,string> ProductNames = new Dictionary<string,string>();
        public BuildingSnapshot Copy() {
            var copy=(BuildingSnapshot)MemberwiseClone();
            copy.Inputs=new Dictionary<string,double>(Inputs);
            copy.Outputs=new Dictionary<string,double>(Outputs);
            copy.ProductNames=new Dictionary<string,string>(ProductNames);
            return copy;
        }
    }
    public sealed class BalanceSummary {
        public int Buildings, Workers, Unsupported, Paused;
        public double PowerMw;
        public Dictionary<string,double> Inputs=new Dictionary<string,double>();
        public Dictionary<string,double> Outputs=new Dictionary<string,double>();
        public Dictionary<string,double> Maintenance=new Dictionary<string,double>();
        public Dictionary<string,string> ProductNames=new Dictionary<string,string>();
        public bool Incomplete {get{return Unsupported>0;}}
    }
    public sealed class SnapshotPlan {
        readonly Dictionary<string,BuildingSnapshot> entries=new Dictionary<string,BuildingSnapshot>();
        public BuildingSnapshot[] Rows {get{return entries.Values.OrderBy(r=>r.Name).ThenBy(r=>r.Id).ToArray();}}
        public void Add(BuildingSnapshot row) {
            if(string.IsNullOrEmpty(row.Id))throw new ArgumentException("Missing building instance ID");
            entries[row.Id]=row.Copy();
        }
        public void Remove(string id){entries.Remove(id);}
        public void Clear(){entries.Clear();}
        public void Replace(IEnumerable<BuildingSnapshot> rows){Clear();foreach(var row in rows)Add(row);}
        static void Sum(Dictionary<string,double> target,string key,double value) {
            if(string.IsNullOrEmpty(key))return;
            double previous;target.TryGetValue(key,out previous);target[key]=previous+value;
        }
        public BalanceSummary Calculate() {
            var result=new BalanceSummary();
            foreach(var row in entries.Values){
                result.Buildings++;result.Workers+=row.Workers;
                foreach(var name in row.ProductNames)result.ProductNames[name.Key]=name.Value;
                Sum(result.Maintenance,row.MaintenanceProduct,row.MaintenancePer60);
                if(row.Paused)result.Paused++;
                if(!string.IsNullOrEmpty(row.UnsupportedReason)){result.Unsupported++;continue;}
                if(row.Paused)continue;
                if(row.Duration<=0 || double.IsNaN(row.Duration) || double.IsInfinity(row.Duration))throw new ArgumentException("Invalid cycle duration");
                var factor=60/row.Duration*(row.Boosted?2:1);
                foreach(var item in row.Inputs)Sum(result.Inputs,item.Key,item.Value*factor);
                foreach(var item in row.Outputs)Sum(result.Outputs,item.Key,item.Value*factor);
                result.PowerMw+=row.PowerMw;
            }
            return result;
        }
    }
    [DataContract]
    public sealed class SavedSnapshot {
        [DataMember] public int SchemaVersion=1;
        [DataMember] public string GameVersion;
        [DataMember] public string CapturedAt;
        [DataMember] public string Mode="ConfiguredCapacity";
        [DataMember] public BuildingSnapshot[] Buildings;
        public void Save(string path) {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var temporary=path+".tmp";
            using(var file=File.Create(temporary))new DataContractJsonSerializer(typeof(SavedSnapshot)).WriteObject(file,this);
            if(File.Exists(path))throw new IOException("Refusing to overwrite existing snapshot");
            File.Move(temporary,path);
        }
        public static SavedSnapshot Load(string path) {
            using(var file=File.OpenRead(path)) {
                var value=(SavedSnapshot)new DataContractJsonSerializer(typeof(SavedSnapshot)).ReadObject(file);
                if(value.SchemaVersion!=1 || value.Buildings==null)throw new IOException("Invalid snapshot file");
                return value;
            }
        }
    }
}
