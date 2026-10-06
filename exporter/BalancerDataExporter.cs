using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using Mafi;
using Mafi.Core.Mods;
using Mafi.Core.Prototypes;
using Mafi.Core.Products;
using Mafi.Core.Factory.Machines;
using Mafi.Core.Entities;

// Original exporter code. References game APIs; does not redistribute game files.
public sealed class BalancerDataExporter : DataOnlyMod, IMod {
    private ProtosDb database;
    public BalancerDataExporter(ModManifest manifest) : base(manifest) {}
    public override void RegisterPrototypes(ProtoRegistrator registrator) {}
    void IMod.RegisterDependencies(DependencyResolverBuilder builder, ProtosDb db, bool gameWasLoaded) { database = db; }
    void IMod.Initialize(DependencyResolver resolver, bool gameWasLoaded) {
        if (database == null) return;
        try { Export(); } catch (Exception error) { Log.Error("BalancerDataExporter: " + error); }
    }
    static Dictionary<string, object> Obj(params object[] values) {
        var result = new Dictionary<string, object>();
        for (int i=0; i<values.Length; i+=2) result.Add((string)values[i], values[i+1]);
        return result;
    }
    static object Member(object value, string name) {
        if(value==null) return null;
        var type=value.GetType();
        var field=type.GetField(name); if(field!=null) return field.GetValue(value);
        var prop=type.GetProperties().FirstOrDefault(p=>p.Name==name && p.GetIndexParameters().Length==0);
        return prop==null?null:prop.GetValue(value,null);
    }
    static string Name(Proto proto) {
        var name=Member(proto.Strings,"Name"); return name==null || string.IsNullOrWhiteSpace(name.ToString())?proto.Id.ToString():name.ToString();
    }
    static double Numeric(object value) {
        if(value==null) throw new Exception("Missing numeric value");
        if(value is IConvertible) return Convert.ToDouble(value,CultureInfo.InvariantCulture);
        var method=value.GetType().GetMethod("ToDouble",Type.EmptyTypes);
        if(method!=null) return Convert.ToDouble(method.Invoke(value,null));
        return double.Parse(value.ToString(),CultureInfo.InvariantCulture);
    }
    static List<object> Io<T>(Mafi.Collections.ImmutableCollections.ImmutableArray<T> items) {
        var result=new List<object>();
        foreach(var item in items) {
            var product=(ProductProto)Member(item,"Product");
            result.Add(Obj("productId",product.Id.ToString(),"quantity",Member(Member(item,"Quantity"),"Value"),
                "hidden",Member(item,"HideInUi"),"pollution",Member(item,"IsPollution")));
        }
        return result;
    }
    static object Describe(object value, int depth) {
        if(value==null)return null;
        if(depth>6)return Obj("truncated",true,"type",value.GetType().FullName);
        if(value is string || value is bool || value is int || value is float || value is double || value is long)return value;
        if(value is char)return value.ToString();
        if(value is Proto)return Obj("id",((Proto)value).Id.ToString(),"type",value.GetType().FullName);
        if(value is Duration)return Obj("seconds",Numeric(((Duration)value).Seconds));
        if(value is Quantity)return ((Quantity)value).Value;
        if(value is PartialQuantity)return Numeric(((PartialQuantity)value).Value);
        if(value is Percent)return ((Percent)value).ToDouble();
        if(value is Electricity)return Obj("raw",((Electricity)value).Value,"oneKwRaw",Electricity.OneKw.Value);
        if(value is Type)return ((Type)value).FullName;
        if(value.GetType().IsEnum)return value.ToString();
        if(value.GetType().Name.StartsWith("ImmutableArray")) {
            var result=new List<object>();
            var enumerator=value.GetType().GetMethod("GetEnumerator",Type.EmptyTypes).Invoke(value,null);
            var move=enumerator.GetType().GetMethod("MoveNext");
            while((bool)move.Invoke(enumerator,null))result.Add(Describe(Member(enumerator,"Current"),depth+1));
            return result;
        }
        return Fields(value,depth+1);
    }
    static object Fields(object value, int depth) {
        var result=Obj("type",value.GetType().FullName);
        foreach(var field in value.GetType().GetFields(BindingFlags.Public|BindingFlags.Instance|BindingFlags.DeclaredOnly)) {
            if(field.Name=="Graphics" || field.FieldType.Name=="Gfx")continue;
            try { result[field.Name]=Describe(field.GetValue(value),depth); }
            catch(Exception error) {result[field.Name]=Obj("error",error.Message);}
        }
        return result;
    }
    void Export() {
        var products=new List<object>(); var buildings=new List<object>(); var bindings=new List<object>();
        var special=new List<object>(); var errors=new List<object>();
        var owners=new Dictionary<string,object>();
        foreach(var proto in database.All<Proto>()) {
            if(proto.Mod!=null) owners[proto.Mod.Manifest.Id]=Obj("id",proto.Mod.Manifest.Id,"version",proto.Mod.Manifest.Version.ToString(),"thirdParty",proto.Mod.Manifest.IsThirdParty);
            if(!(proto is MachineProto) && proto is EntityProto && (proto.GetType().FullName.Contains(".NuclearReactors.") || proto.GetType().FullName.Contains(".PowerGenerators.") || proto.GetType().FullName.Contains(".Farms.")))
                special.Add(Obj("id",proto.Id.ToString(),"name",Name(proto),"type",proto.GetType().FullName,"fields",Fields(proto,0)));
        }
        foreach(var p in database.All<ProductProto>()) products.Add(Obj("id",p.Id.ToString(),"name",Name(p),"type",p.Type.ToString()));
        foreach(var machine in database.All<MachineProto>()) {
            buildings.Add(Obj("id",machine.Id.ToString(),"name",Name(machine),"type",machine.GetType().FullName,
                "workers",machine.Costs.Workers,"electricityRaw",machine.ElectricityConsumed.Value,
                "electricityOneKwRaw",Electricity.OneKw.Value,"maintenanceRaw",machine.Costs.Maintenance.ToString(),
                "maintenance",Obj("productId",machine.Costs.Maintenance.Product==null?null:machine.Costs.Maintenance.Product.Id.ToString(),
                    "quantityPerMonth",Numeric(machine.Costs.Maintenance.MaintenancePerMonth.Value),
                    "maxQuantityPerMonth",Numeric(machine.Costs.Maintenance.MaxMaintenancePerMonth.Value),
                    "monthSeconds",Numeric(Duration.OneMonth.Seconds))));
            foreach(var binding in machine.RecipeBindings) {
                try {
                    var recipe=binding.Recipe;
                    bindings.Add(Obj("buildingId",machine.Id.ToString(),"recipeId",recipe.Id.ToString(),"name",Name(recipe),
                        "durationSeconds",Numeric(binding.Duration.Seconds),"multiplier",binding.Multiplier,
                        "inputs",Io(recipe.AllInputs),"outputs",Io(recipe.AllOutputs),
                        "powerMultiplier",recipe.PowerMultiplier.ToDouble(),
                        "powerMultiplierRaw",recipe.PowerMultiplier.ToString()));
                } catch(Exception error) {errors.Add(Obj("buildingId",machine.Id.ToString(),"recipeId",binding.Recipe.Id.ToString(),"error",error.Message));}
            }
        }
        string version=null;
        foreach(var assembly in AppDomain.CurrentDomain.GetAssemblies()) {
            Type[] types; try{types=assembly.GetTypes();}catch{continue;}
            foreach(var type in types.Where(t=>t.Name=="GameVersion")) {
                var field=type.GetField("FULL_VERSION",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static);
                if(field!=null) version=Convert.ToString(field.GetValue(null));
            }
        }
        var hashes=new Dictionary<string,object>();
        foreach(var assembly in AppDomain.CurrentDomain.GetAssemblies().Where(a=>new[]{"Mafi","Mafi.Core","Mafi.Base"}.Contains(a.GetName().Name))) {
            using(var stream=File.OpenRead(assembly.Location)) using(var hash=SHA256.Create())
                hashes[assembly.GetName().Name]=BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
        }
        var package=Obj("schemaVersion",1,"exporterVersion","0.2.1","gameVersion",version,"exportedAt",DateTime.UtcNow.ToString("o"),"assemblyHashes",hashes,
            "modListComplete",false,"prototypeOwners",owners.Values.ToList(),"products",products,"buildings",buildings,
            "bindings",bindings,"specialPrototypes",special,"errors",errors);
        var folder=Path.Combine(Manifest.RootDirectoryPath,"exports"); Directory.CreateDirectory(folder);
        var path=Path.Combine(folder,"game-data-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff")+".json");
        File.WriteAllText(path,Json(package),new UTF8Encoding(false));
        Log.Info("BalancerDataExporter: exported "+bindings.Count+" bindings to "+path);
    }
    static string Json(object value) {
        if(value==null)return "null";
        if(value is string) return "\""+Escape((string)value)+"\"";
        if(value is bool)return (bool)value?"true":"false";
        var dictionary=value as IDictionary;
        if(dictionary!=null){var parts=new List<string>();foreach(DictionaryEntry entry in dictionary)parts.Add(Json(entry.Key.ToString())+":"+Json(entry.Value));return "{"+string.Join(",",parts)+"}";}
        var items=value as IEnumerable;
        if(items!=null){var parts=new List<string>();foreach(var item in items)parts.Add(Json(item));return "["+string.Join(",",parts)+"]";}
        return Convert.ToString(value,CultureInfo.InvariantCulture);
    }
    static string Escape(string text) {
        var output=new StringBuilder();foreach(char c in text){if(c=='"'||c=='\\')output.Append('\\').Append(c);else if(c<32)output.Append("\\u"+((int)c).ToString("x4"));else output.Append(c);}return output.ToString();
    }
}
