using System;
using System.IO;
using System.Linq;
using Mafi;
using Mafi.Core.Simulation;
using Mafi.Core.Entities;
using Mafi.Core.GameLoop;
using Mafi.Core.Terrain;
using Mafi.Unity.Camera;
using Mafi.Unity.InputControl;
using Mafi.Unity.InputControl.AreaTool;
using Mafi.Unity.Terrain;
using UnityEngine;

namespace BalancerPlanner {
    public sealed class PlannerOverlay : MonoBehaviour {
        readonly object gate=new object();
        readonly SnapshotPlan plan=new SnapshotPlan();
        ISimLoopEvents events;
        GameSnapshotReader reader;
        AreaSelectionTool selection;
        string directory, message="点击框选，将建成建筑追加到配置产能核算。";
        Rect window=new Rect(120,100,780,650);
        Vector2 scroll;
        bool visible, selecting, pending, refresh, replacing, subscribed;
        RectangleTerrainArea2i area;
        Font font;
        public void Initialize(DependencyResolver resolver,string modDirectory) {
            directory=Path.Combine(modDirectory,"plans");
            events=resolver.Resolve<ISimLoopEvents>();
            reader=new GameSnapshotReader(resolver.Resolve<EntitiesManager>());
            selection=new AreaSelectionTool(resolver.Resolve<CameraController>(),resolver.Resolve<IGameLoopEvents>(),resolver.Resolve<ShortcutsManager>(),
                resolver.Instantiate<TerrainCursor>(),resolver.Resolve<TerrainAreaOutlineRenderer>(),
                (selected,add)=>{},SelectionDone,CancelSelection,default(Option<Action>));
            events.ReadGameStateFrequent.AddNonSaveable(this,ReadPending);
            subscribed=true;
            font=Font.CreateDynamicFontFromOSFont("Microsoft YaHei",16);
        }
        void SelectionDone(RectangleTerrainArea2i selected,bool addition) {
            lock(gate){area=selected;pending=true;refresh=false;}
            selecting=false;selection.Deactivate();visible=true;
        }
        void CancelSelection(){selecting=false;if(selection!=null)selection.Deactivate();visible=true;}
        void ReadPending() {
            lock(gate){
                if(!pending)return;
                pending=false;
                try {
                    var rows=refresh?reader.Refresh(plan.Rows):reader.ReadArea(area);
                    if(refresh||replacing)plan.Replace(rows);else foreach(var row in rows)plan.Add(row);
                    replacing=false;
                    message="已读取 "+rows.Length+" 座建筑。结果为配置产能，含停机状态；不代表实际持续产量。";
                    Log.Info("BalancerPlanner: snapshot read "+rows.Length+" buildings; configured-capacity only.");
                }catch(Exception error){message="读取失败："+error.Message;Log.Error("BalancerPlanner: "+error);}
            }
        }
        void Update(){if(Input.GetKeyDown(KeyCode.F8))visible=!visible;}
        void OnGUI() {
            var original=GUI.skin.font;
            try {
                if(font!=null)GUI.skin.font=font;
                if(GUI.Button(new Rect(Screen.width-190,70,180,36),selecting?"取消框选":"配平计算器 [F8]")){if(selecting)CancelSelection();else visible=!visible;}
                if(visible){lock(gate)window=GUILayout.Window(846281,window,DrawWindow,"配平计算器 · 只读配置快照");}
            }finally{GUI.skin.font=original;}
        }
        void StartSelection(bool replace) {
            replacing=replace;visible=false;selecting=true;selection.Activate(true,null,null);
            message="拖动框选已建成建筑，右键或取消按钮退出。";
        }
        void DrawWindow(int id) {
            GUILayout.BeginHorizontal();
            if(GUILayout.Button("框选追加"))StartSelection(false);
            if(GUILayout.Button("框选替换"))StartSelection(true);
            if(GUILayout.Button("重新读取")){pending=true;refresh=true;}
            if(GUILayout.Button("清空")){plan.Clear();message="已清空计算器，游戏建筑未改变。";}
            if(GUILayout.Button("保存快照"))SaveSnapshot();
            if(GUILayout.Button("关闭"))visible=false;
            GUILayout.EndHorizontal();
            GUILayout.Label(message);
            var totals=plan.Calculate();
            GUILayout.Label("建筑 "+totals.Buildings+" · 配置工人 "+totals.Workers+" · 停机 "+totals.Paused+" · 已支持项净耗电 "+totals.PowerMw.ToString("0.###")+" MW");
            if(totals.Incomplete)GUILayout.Label("包含 "+totals.Unsupported+" 座待适配建筑；资源和耗电仅统计已支持项，请勿当作完整工厂总量。");
            GUILayout.Label("维护是全部选中建筑的基础配置估算，不模拟停机减免或动态维护。正净值为余量，负净值为缺口；物料 /60。");
            scroll=GUILayout.BeginScrollView(scroll,GUILayout.Height(470));
            foreach(var product in totals.Inputs.Keys.Union(totals.Outputs.Keys).OrderBy(p=>p)) {
                double input,output;totals.Inputs.TryGetValue(product,out input);totals.Outputs.TryGetValue(product,out output);
                string name;totals.ProductNames.TryGetValue(product,out name);
                GUILayout.Label((name??product)+"    消耗 "+input.ToString("0.###")+"    产出 "+output.ToString("0.###")+"    净值 "+(output-input).ToString("0.###"));
            }
            foreach(var item in totals.Maintenance){string name;totals.ProductNames.TryGetValue(item.Key,out name);GUILayout.Label((name??item.Key)+" · 基础维护配置 /60："+item.Value.ToString("0.###"));}
            GUILayout.Space(12);GUILayout.Label("建筑快照（相同设置合并显示，实际实例仍独立）");
            foreach(var group in plan.Rows.GroupBy(r=>r.BuildingId+"|"+r.RecipeId+"|"+r.Paused+"|"+r.Boosted+"|"+r.SpeedFactor+"|"+r.DurationMultiplier+"|"+r.UnsupportedReason)) {
                var first=group.First();GUILayout.BeginHorizontal();
                GUILayout.Label(first.Name+" ×"+group.Count()+" · "+(first.Paused?"停机":"启用")+(first.Boosted?" · 加速":"")+" · "+(first.UnsupportedReason??first.RecipeId)+" · 状态 "+first.State);
                if(GUILayout.Button("移除本组",GUILayout.Width(90)))foreach(var row in group.ToArray())plan.Remove(row.Id);
                GUILayout.EndHorizontal();
            }
            GUILayout.EndScrollView();GUI.DragWindow(new Rect(0,0,10000,22));
        }
        void SaveSnapshot() {
            try {
                var path=Path.Combine(directory,"snapshot-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff")+".json");
                new SavedSnapshot{GameVersion=GameVersion.FULL_VERSION,CapturedAt=DateTime.UtcNow.ToString("o"),Buildings=plan.Rows}.Save(path);
                message="快照已保存到 Mod 的 plans 文件夹，游戏存档未修改。";
            }catch(Exception error){message="保存失败："+error.Message;}
        }
        void OnDestroy() {
            if(events!=null && subscribed)events.ReadGameStateFrequent.RemoveNonSaveable(this,ReadPending);
            if(selection!=null)selection.Deactivate();
            if(font!=null)UnityEngine.Object.Destroy(font);
        }
    }
}
