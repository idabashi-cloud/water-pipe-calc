import streamlit as st
import graphviz
import math
import pandas as pd
import json
import io
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# --- 0. 初期設定データ ---
plt.rcParams['font.family'] = 'Meiryo'

# 負荷単位データ (LU)
FIXTURE_DATA = {
    "大便器 (洗浄弁) (公)": 10, "大便器 (タンク) (公)": 5, "小便器 (洗浄弁) (公)": 5, "小便器 (タンク) (公)": 3,
    "洗面器 (公)": 2, "手洗器 (公)": 0.5, "掃除用流し (公)": 4, "厨房流し (公)": 4, "シャワー (公)": 4,
    "大便器 (洗浄弁) (私)": 6, "大便器 (タンク) (私)": 3, "小便器 (洗浄弁) (私)": 5, "小便器 (タンク) (私)": 3,
    "洗面器 (私)": 1, "手洗器 (私)": 1, "台所流し (私)": 3, "浴槽 (私)": 2, "シャワー (私)": 2, "洗濯機 (私)": 2
}
DEFAULT_PUBLIC_LIST = [k.replace(" (公)", "") for k in FIXTURE_DATA.keys() if "(公)" in k]
DEFAULT_PRIVATE_LIST = [k.replace(" (私)", "") for k in FIXTURE_DATA.keys() if "(私)" in k]

# プリセット定義
PRESETS = {
    "単身住戸 (1R)": {
        "fixtures": {"大便器 (タンク) (私)": 1, "洗面器 (私)": 1, "シャワー (私)": 1, "台所流し (私)": 1, "洗濯機 (私)": 1},
        "person": 1, "dw": 1
    },
    "ファミリー (3LDK)": {
        "fixtures": {"大便器 (タンク) (私)": 1, "洗面器 (私)": 1, "浴槽 (私)": 1, "台所流し (私)": 1, "洗濯機 (私)": 1, "手洗器 (私)": 1},
        "person": 3, "dw": 1
    },
    "公共トイレ (小)": {
        "fixtures": {"大便器 (洗浄弁) (公)": 1, "小便器 (洗浄弁) (公)": 1, "洗面器 (公)": 1},
        "person": 0, "dw": 1
    },
    "公共トイレ (大)": {
        "fixtures": {"大便器 (洗浄弁) (公)": 3, "小便器 (洗浄弁) (公)": 3, "洗面器 (公)": 3, "掃除用流し (公)": 1},
        "person": 0, "dw": 1
    }
}

# 配管データベース
PIPE_DATABASES = {
    "SGP (配管用炭素鋼鋼管)": [
        {"サイズ": "15A", "内径(mm)": 16.1}, {"サイズ": "20A", "内径(mm)": 21.6},
        {"サイズ": "25A", "内径(mm)": 27.6}, {"サイズ": "32A", "内径(mm)": 35.7},
        {"サイズ": "40A", "内径(mm)": 41.6}, {"サイズ": "50A", "内径(mm)": 52.9},
        {"サイズ": "65A", "内径(mm)": 67.9}, {"サイズ": "80A", "内径(mm)": 80.7},
        {"サイズ": "100A", "内径(mm)": 106.3}, {"サイズ": "125A", "内径(mm)": 130.8},
        {"サイズ": "150A", "内径(mm)": 155.2},
    ],
    "VP (硬質ポリ塩化ビニル管)": [
        {"サイズ": "13", "内径(mm)": 13.0}, {"サイズ": "16", "内径(mm)": 16.0},
        {"サイズ": "20", "内径(mm)": 20.0}, {"サイズ": "25", "内径(mm)": 25.0},
        {"サイズ": "30", "内径(mm)": 31.0}, {"サイズ": "40", "内径(mm)": 40.0},
        {"サイズ": "50", "内径(mm)": 51.0}, {"サイズ": "65", "内径(mm)": 67.0},
        {"サイズ": "75", "内径(mm)": 77.0}, {"サイズ": "100", "内径(mm)": 100.0},
        {"サイズ": "125", "内径(mm)": 125.0}, {"サイズ": "150", "内径(mm)": 146.0},
    ],
    "SU (一般配管用ステンレス鋼管)": [
        {"サイズ": "13Su", "内径(mm)": 14.28}, {"サイズ": "20Su", "内径(mm)": 20.22},
        {"サイズ": "25Su", "内径(mm)": 26.58}, {"サイズ": "30Su", "内径(mm)": 31.6},
        {"サイズ": "40Su", "内径(mm)": 40.3}, {"サイズ": "50Su", "内径(mm)": 46.2},
        {"サイズ": "60Su", "内径(mm)": 57.5}, {"サイズ": "75Su", "内径(mm)": 73.3},
        {"サイズ": "80Su", "内径(mm)": 85.1}, {"サイズ": "100Su", "内径(mm)": 110.3},
        {"サイズ": "125Su", "内径(mm)": 134.8}, {"サイズ": "150Su", "内径(mm)": 159.2},
    ]
}
PIPE_DATABASES["HIVP (耐衝撃性硬質塩化ビニル管)"] = PIPE_DATABASES["VP (硬質ポリ塩化ビニル管)"]

SU_FLOW_CAPACITY = {
    "13Su": 18.0, "20Su": 45.0, "25Su": 85.0, "30Su": 120.0,
    "40Su": 200.0, "50Su": 320.0, "60Su": 500.0, "75Su": 900.0,
    "80Su": 1100.0, "100Su": 1900.0, "125Su": 3000.0, "150Su": 4500.0
}

FLOW_TABLE_FV = { 1: 93.9, 2: 96.2, 5: 102.9, 10: 113.8, 15: 124.4, 20: 134.5, 30: 153.9, 40: 172.0, 50: 188.9, 60: 204.7, 80: 233.3, 100: 258.3, 120: 280.4, 150: 309.0, 200: 348.0, 250: 380.7, 300: 410.7, 342: 435.7 }
FLOW_TABLE_FT = { 1: 16.8, 2: 18.8, 5: 24.9, 10: 34.8, 15: 44.3, 20: 53.5, 30: 71.0, 40: 87.3, 50: 102.5, 60: 116.8, 80: 142.8, 100: 165.8, 120: 186.3, 150: 213.6, 200: 252.9, 250: 288.6, 300: 324.0, 342: 354.7 }

def interpolate_flow(lu, is_fv=False):
    table = FLOW_TABLE_FV if is_fv else FLOW_TABLE_FT
    points = sorted(table.keys())
    if lu <= 0: return 0
    if lu in table: return table[lu]
    if lu > points[-1]:
        x1, x2 = points[-2], points[-1]
        y1, y2 = table[x1], table[x2]
        return y2 + (y2 - y1) / (x2 - x1) * (lu - x2)
    for i in range(len(points) - 1):
        x1, x2 = points[i], points[i+1]
        if x1 < lu < x2:
            return y1 + (y2 - y1) * (lu - x1) / (x2 - x1)
    return 0

# --- 1. 計算クラス ---
class PipeSection:
    def __init__(self, id, name, type, fixtures=None, manual_size=None, dwelling_count=1, person_count=0, specific_pipe_type=None, length=2.0, is_fixed_flow=False, fixed_flow_val=0.0, is_manual_critical=False, **kwargs):
        self.id = id
        self.name = name
        self.type = type 
        self.fixtures = fixtures if fixtures else {}
        self.manual_size = manual_size
        self.dwelling_count = dwelling_count
        self.person_count = person_count
        self.specific_pipe_type = specific_pipe_type
        self.length = length
        self.is_fixed_flow = is_fixed_flow
        self.fixed_flow_val = fixed_flow_val
        self.is_manual_critical = is_manual_critical
        
        # エラー回避用: 親IDの復元
        self.parent_id = kwargs.get("parent", None)
        
        self.children = []
        self.parent_name = ""
        
        self.load_units = 0.0
        self.total_load = 0.0
        self.system_count = 0
        self.total_person_count = 0
        self.fixture_count = 0
        self.flow_lpm = 0.0
        self.size = "-"
        self.velocity = 0.0
        self.head_loss = 0.0
        self.cum_head_loss = 0.0
        self.cum_length = 0.0
        self.equiv_len = 0.0
        self.is_manual = False
        self.calc_description = ""
        self.used_pipe_type = ""
        self.loss_params_used = {}

    def add_child(self, child_node):
        self.children.append(child_node)
        child_node.parent_name = self.name
        child_node.parent_id = self.id

    def calculate_self_stats(self, building_type):
        load = 0.0
        count = 0
        for fname_key, qty in self.fixtures.items():
            if qty > 0:
                count += qty
                if fname_key in FIXTURE_DATA:
                    load += qty * FIXTURE_DATA[fname_key]
        self.load_units = load
        self.fixture_count = count
        if "集合住宅 (BL基準)" in building_type:
            self.system_count = self.dwelling_count if self.type == "system" else 0
            self.person_count_val = 0
        elif "集合住宅 (人数基準)" in building_type:
            self.system_count = 0
            self.person_count_val = self.person_count if self.type == "system" else 0
        else:
            self.system_count = 0
            self.person_count_val = 0

    def calculate(self, all_pipe_db, default_pipe_type, max_velocity, building_type, is_fv, person_calc_params=None, loss_params=None):
        self.calculate_self_stats(building_type)
        child_load_sum = 0.0; child_system_sum = 0; child_person_sum = 0; child_fixture_sum = 0
        
        for child in self.children:
            c_load, c_sys, c_person, c_fix = child.calculate(all_pipe_db, default_pipe_type, max_velocity, building_type, is_fv, person_calc_params, loss_params)
            child_load_sum += c_load; child_system_sum += c_sys; child_person_sum += c_person; child_fixture_sum += c_fix
            
        self.total_load = self.load_units + child_load_sum
        self.system_total = self.system_count + child_system_sum
        self.person_total = self.person_count_val + child_person_sum
        self.fixture_total = self.fixture_count + child_fixture_sum
        
        # 流量計算
        auto_flow = 0.0; auto_desc = ""
        if "集合住宅 (BL基準)" in building_type:
            if self.system_total > 0:
                if self.system_total < 10: auto_flow = 42 * (self.system_total ** 0.33); auto_desc = f"BL基準(N<10) {self.system_total}戸"
                else: auto_flow = 19 * (self.system_total ** 0.67); auto_desc = f"BL基準(N≧10) {self.system_total}戸"
            elif self.total_load > 0: auto_flow = interpolate_flow(self.total_load, is_fv); auto_desc = f"負荷単位法 {self.total_load}LU"
        elif "集合住宅 (人数基準)" in building_type:
            if self.person_total > 0 and person_calc_params:
                if self.person_total <= 30: C=person_calc_params["C1"]; k=person_calc_params["k1"]
                else: C=person_calc_params["C2"]; k=person_calc_params["k2"]
                auto_flow = C * (self.person_total ** k); auto_desc = f"人数算定 {self.person_total}人"
        elif "一戸建て" in building_type:
            if self.fixture_total > 0: auto_flow = 17 * (self.fixture_total ** 0.475); auto_desc = f"総水栓数法 {self.fixture_total}個"
        else:
            if self.total_load > 0: auto_flow = interpolate_flow(self.total_load, is_fv); auto_desc = f"負荷単位法 {self.total_load}LU"
            else: auto_desc = "0 LU"

        if self.is_fixed_flow: self.flow_lpm = self.fixed_flow_val; self.calc_description = f"固定 {self.flow_lpm}L/min"
        else: self.flow_lpm = auto_flow; self.calc_description = auto_desc

        # 口径選定
        q_m3s = self.flow_lpm / 60000
        target_pipe_type = self.specific_pipe_type if self.specific_pipe_type else default_pipe_type
        self.used_pipe_type = target_pipe_type
        current_specs_df = pd.DataFrame(all_pipe_db.get(target_pipe_type, []))
        d_mm_actual = 0.0
        
        if self.manual_size and self.manual_size != "自動計算":
            self.size = self.manual_size; self.is_manual = True
            if not current_specs_df.empty:
                row = current_specs_df[current_specs_df["サイズ"] == self.manual_size]
                if not row.empty and q_m3s > 0:
                    d_mm_actual = row.iloc[0]["内径(mm)"]
                    self.velocity = round(q_m3s / (math.pi * ((d_mm_actual/1000)/2)**2), 2)
                else: self.velocity = 0.0
            self.calc_description += f" [固定: {self.size}]"
        else:
            self.is_manual = False; best_size = "規格外"; best_vel = 0.0
            if "SU" in target_pipe_type:
                sorted_cap = sorted(SU_FLOW_CAPACITY.items(), key=lambda x: x[1])
                found = False
                for sz, cap in sorted_cap:
                    if self.flow_lpm <= cap:
                        best_size = sz; found = True
                        row = current_specs_df[current_specs_df["サイズ"] == sz]
                        if not row.empty:
                            d_mm_actual = row.iloc[0]["内径(mm)"]
                            best_vel = round(q_m3s / (math.pi * ((d_mm_actual/1000)/2)**2), 2) if d_mm_actual>0 else 0.0
                        break
                if not found and self.flow_lpm > 0: best_size = "規格外(過大)"
            else:
                if not current_specs_df.empty:
                    sorted_s = current_specs_df.sort_values("内径(mm)")
                    for _, row in sorted_s.iterrows():
                        d = row["内径(mm)"]; a = math.pi * ((d/1000)/2)**2
                        if a <= 0: continue
                        v = q_m3s / a
                        if v <= max_velocity:
                            best_size = row["サイズ"]; best_vel = round(v, 2); d_mm_actual = d
                            break
            self.size = best_size; self.velocity = best_vel
            
        # 損失水頭計算 (Hazen-Williams)
        self.head_loss = 0.0
        self.loss_params_used = loss_params.copy() if loss_params else {}
        if loss_params and d_mm_actual > 0 and q_m3s > 0:
            C_val = loss_params.get("C", 130.0)
            fit_rate = loss_params.get("fitting", 1.2)
            D_m = d_mm_actual / 1000.0
            L_eq = self.length * fit_rate
            h = 10.666 * (C_val ** -1.852) * (D_m ** -4.87) * (q_m3s ** 1.852) * L_eq
            self.head_loss = round(h, 3)
            
        return self.total_load, self.system_total, self.person_total, self.fixture_total

    def calculate_cumulative_loss(self, parent_cum_loss=0.0, parent_cum_len=0.0):
        self.cum_head_loss = parent_cum_loss + self.head_loss
        self.cum_length = parent_cum_len + self.length
        for child in self.children:
            child.calculate_cumulative_loss(self.cum_head_loss, self.cum_length)

    def get_all_terminals(self):
        terminals = []
        if not self.children: terminals.append(self)
        for child in self.children: terminals.extend(child.get_all_terminals())
        return terminals

    def find_critical_node(self):
        all_terminals = self.get_all_terminals()
        if not all_terminals: return self
        manual_targets = [t for t in all_terminals if t.is_manual_critical]
        if manual_targets: return max(manual_targets, key=lambda t: t.cum_head_loss)
        return max(all_terminals, key=lambda t: t.cum_head_loss)

    def get_excel_data(self):
        data = []
        if self.id != "root":
            c_val = self.loss_params_used.get("C", "")
            fit_val = self.loss_params_used.get("fitting", "")
            row = {
                "区間名称": f"{self.parent_name} → {self.name}",
                "始点": self.parent_name, "終点": self.name,
                "種別": "分岐" if self.type == "branch" else "末端",
                "累計負荷 (LU)": round(self.total_load, 1),
                "累計戸数": self.system_total, "累計人数": self.person_total,
                "同時使用水量 (L/min)": round(self.flow_lpm, 1),
                "使用管種": self.used_pipe_type, "選定口径": self.size, "流速 (m/s)": self.velocity,
                "流速係数": c_val, "継手割増": fit_val, "管長 (m)": self.length,
                "単独損失 (m)": self.head_loss, "累計損失 (m)": round(self.cum_head_loss, 3),
                "判定": "固定" if self.is_manual else "自動", "計算式": self.calc_description
            }
            data.append(row)
        for child in self.children: data.extend(child.get_excel_data())
        return data

# --- 2. コールバック ---
def add_node(node_type, preset_data=None):
    if node_type == "branch":
        st.session_state["branch_counter"] += 1; count = st.session_state["branch_counter"]; name = f"分岐-{count}"
        init_fix = {}; dw=1; per=1
    else:
        st.session_state["system_counter"] += 1; count = st.session_state["system_counter"]; name = f"系統-{count}"
        if preset_data:
            init_fix = preset_data["fixtures"].copy(); dw=preset_data.get("dw",1); per=preset_data.get("person",1); name += f" ({preset_data.get('name')})"
        else: init_fix = {}; dw=1; per=1
    
    new_id = f"node_{node_type}_{count}"
    st.session_state["pipes"].append({
        "id": new_id, "name": name, "type": node_type, "parent": st.session_state["selected_id"],
        "fixtures": init_fix, "manual_size": None, "dwelling_count": dw, "person_count": per,
        "specific_pipe_type": None, "length": 2.0, "is_fixed_flow": False, "fixed_flow_val": 0.0,
        "is_manual_critical": False
    })
    st.session_state["selected_id"] = new_id

def insert_node_before():
    target_id = st.session_state["selected_id"]
    if target_id == "root": return
    target_node = next((p for p in st.session_state["pipes"] if p["id"] == target_id), None)
    if not target_node: return
    st.session_state["branch_counter"] += 1; count = st.session_state["branch_counter"]
    new_id = f"node_branch_{count}"; name = f"分岐-{count}"
    st.session_state["pipes"].append({
        "id": new_id, "name": name, "type": "branch", "parent": target_node["parent"],
        "fixtures": {}, "manual_size": None, "dwelling_count": 1, "person_count": 1,
        "specific_pipe_type": None, "length": 2.0, "is_fixed_flow": False, "fixed_flow_val": 0.0,
        "is_manual_critical": False
    })
    target_node["parent"] = new_id
    st.session_state["selected_id"] = new_id

def renumber_nodes():
    pipes = st.session_state["pipes"]; children_map = {p["id"]: [] for p in pipes}
    node_map = {p["id"]: p for p in pipes}; root_id = None
    for p in pipes:
        if p["parent"] is None: root_id = p["id"]
        elif p["parent"] in children_map: children_map[p["parent"]].append(p["id"])
    if not root_id: return
    b_cnt = 1
    def traverse(nid):
        nonlocal b_cnt
        node = node_map[nid]
        if node["id"] != "root" and node["type"] == "branch":
            node["name"] = f"分岐-{b_cnt}"; b_cnt += 1
        for child_id in children_map.get(nid, []): traverse(child_id)
    traverse(root_id)
    st.session_state["branch_counter"] = b_cnt
    st.success("番号修正完了")

def delete_current_node():
    tid = st.session_state["selected_id"]
    if tid == "root": return
    st.session_state["pipes"] = [p for p in st.session_state["pipes"] if p["id"] != tid]
    for p in st.session_state["pipes"]:
        if p["parent"] == tid: p["parent"] = "root"
    st.session_state["selected_id"] = "root"

def reset_all():
    st.session_state["pipes"] = [{"id": "root", "name": "ポンプ(始点)", "type": "branch", "parent": None, "fixtures": {}, "manual_size": None, "dwelling_count": 0, "person_count": 0, "specific_pipe_type": None, "length": 0.0, "is_fixed_flow": False, "fixed_flow_val": 0.0, "is_manual_critical": False}]
    st.session_state["branch_counter"] = 0; st.session_state["system_counter"] = 0; st.session_state["selected_id"] = "root"
    if "chart_image" in st.session_state: del st.session_state["chart_image"]
    if "excel_bytes" in st.session_state: del st.session_state["excel_bytes"]
    if "pdf_bytes" in st.session_state: del st.session_state["pdf_bytes"]

def set_parent(node_id):
    st.session_state["selected_id"] = node_id

# --- 4. グラフ描画関数 ---
def get_flow_curve_image(current_lu, current_flow, is_fv):
    x_vals = []
    v = 10
    while v <= 4000:
        x_vals.append(v)
        v *= 1.1
    y_fv = [interpolate_flow(x, True) for x in x_vals]
    y_ft = [interpolate_flow(x, False) for x in x_vals]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x_vals, y_fv, label='曲線① (洗浄弁)', color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax.plot(x_vals, y_ft, label='曲線② (タンク)', color='gray', linestyle=':', alpha=0.5, linewidth=1)
    active_y = y_fv if is_fv else y_ft
    label_txt = "選択中の基準"
    ax.plot(x_vals, active_y, color='blue', linewidth=1.5, label=label_txt)
    if current_lu > 0:
        ax.scatter([current_lu], [current_flow], color='red', s=80, zorder=5, label='現在値')
        ax.axvline(x=current_lu, color='red', linestyle='-', linewidth=0.5, alpha=0.7)
        ax.axhline(y=current_flow, color='red', linestyle='-', linewidth=0.5, alpha=0.7)
        ax.text(current_lu * 1.1, current_flow, f"{int(current_flow)} L/min", color='red', fontsize=9, va='bottom', fontweight='bold')
        ax.text(current_lu, current_flow * 0.75, f"{int(current_lu)} LU", color='red', fontsize=9, ha='left', fontweight='bold')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(10, 4000)
    ax.set_ylim(20, 3000)
    ax.grid(True, which="major", ls="-", alpha=0.5)
    ax.grid(True, which="minor", ls=":", alpha=0.2)
    ax.set_xlabel('給水負荷単位 (LU)')
    ax.set_ylabel('同時使用水量 (L/min)')
    ax.set_title('給水負荷単位同時使用流量線図 (図3.3.1)')
    ax.legend(loc='upper left', fontsize='small')
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf

# --- 5. UI ---
st.set_page_config(layout="wide", page_title="給水管計算ツール Final v44 (Unlimited)")

if "pipes" not in st.session_state: reset_all()
if "input_mode" not in st.session_state: st.session_state["input_mode"] = "public"
if "custom_presets" not in st.session_state: st.session_state["custom_presets"] = PRESETS.copy()

with st.sidebar:
    st.header("📂 ファイル操作")
    current_json = json.dumps(st.session_state["pipes"], ensure_ascii=False, indent=2)
    st.download_button("💾 構成保存 (JSON)", current_json, "pipe_config.json", "application/json")
    uploaded_file = st.file_uploader("📂 構成読込", type=["json"])
    if uploaded_file:
        try:
            loaded_data = json.load(uploaded_file)
            st.session_state["pipes"] = loaded_data
            st.success("読込完了"); st.rerun()
        except: st.error("読込エラー")

    st.divider()
    st.header("⚙️ 設計条件")
    building_type = st.selectbox("建物の用途", ["一般・事務所 (負荷単位法)", "集合住宅 (BL基準)", "集合住宅 (人数基準)", "一戸建て (総水栓数法)"])
    person_calc_params = {}
    is_fv = False
    if "一般" in building_type:
        is_fv = (st.radio("大便器方式", ["洗浄弁式", "ロータンク式"]) == "洗浄弁式")
    elif "人数基準" in building_type:
        st.caption("人数計算係数"); c1 = st.number_input("C1", 26.0); k1 = st.number_input("k1", 0.36)
        c2 = st.number_input("C2", 13.0); k2 = st.number_input("k2", 0.56)
        person_calc_params = {"C1": c1, "k1": k1, "C2": c2, "k2": k2}
    else:
        is_fv = (st.radio("大便器方式(参考)", ["洗浄弁式", "ロータンク式"]) == "洗浄弁式")

    st.divider()
    selected_pipe_type = st.selectbox("基本の管種", list(PIPE_DATABASES.keys()))
    graph_direction = st.radio("図面方向", ["横書き (左→右)", "縦書き (上→下)", "縦書き (下→上)"], horizontal=True)
    rankdir = "LR" if "左→右" in graph_direction else ("TB" if "上→下" in graph_direction else "BT")

    st.divider()
    show_velocity = st.checkbox("流速表示", False); show_head_loss = st.checkbox("損失表示", False)
    show_length = st.checkbox("管長表示", True); show_calc_formula = st.checkbox("計算式表示", False)
    max_vel_setting = st.number_input("許容流速 (m/s)", 2.0, step=0.1)
    
    with st.expander("🌊 摩擦損失計算の設定"):
        c_val_setting = st.number_input("流速係数 C", 130.0, step=1.0)
        fitting_ratio = st.number_input("継手類による割増率", 1.2, step=0.1)
        loss_params = {"C": c_val_setting, "fitting": fitting_ratio}

    st.divider()
    with st.expander("🛠️ プリセット管理"):
        new_preset_name = st.text_input("プリセット名", placeholder="例: 2LDKタイプA")
        col_p1, col_p2 = st.columns(2)
        new_dw = col_p1.number_input("戸数", min_value=1, value=1, step=1, key="new_dw")
        new_person = col_p2.number_input("人数", min_value=0, value=1, step=1, key="new_person")
        fixture_mode = st.radio("器具リスト選択", ["公共用", "個人用"], horizontal=True)
        src_list = DEFAULT_PUBLIC_LIST if fixture_mode == "公共用" else DEFAULT_PRIVATE_LIST
        suffix = "(公)" if fixture_mode == "公共用" else "(私)"
        temp_fixtures = {}
        for fname in src_list:
            qty = st.number_input(f"{fname}", min_value=0, step=1, key=f"new_fix_{fname}")
            if qty > 0: temp_fixtures[f"{fname} {suffix}"] = qty
        if st.button("プリセット登録"):
            if new_preset_name:
                st.session_state["custom_presets"][new_preset_name] = {"fixtures": temp_fixtures, "dw": new_dw, "person": new_person}
                st.success(f"「{new_preset_name}」を登録しました"); st.rerun()
        
        del_target = st.selectbox("削除するプリセット", ["(選択してください)"] + list(st.session_state["custom_presets"].keys()))
        if st.button("削除実行"):
            if del_target != "(選択してください)": del st.session_state["custom_presets"][del_target]; st.rerun()

col_ctrl, col_edit, col_view = st.columns([0.8, 1.2, 2.5])

with col_ctrl:
    st.subheader("1. 構成作成")
    current_parent = next((p for p in st.session_state["pipes"] if p["id"] == st.session_state["selected_id"]), None)
    if current_parent: st.info(f"接続先: **{current_parent['name']}**")
    else: st.warning("選択してください")

    if st.button("＋分岐点", width=True): add_node("branch")
    if st.session_state["selected_id"]!="root":
        if st.button("＋親の間に挿入", width=True): insert_node_before()
    if st.button("＋系統(末端)", width=True): add_node("system")
    st.markdown("---")
    
    with st.expander("⚡ プリセットから追加"):
        for pname, pdata in st.session_state["custom_presets"].items():
            if st.button(f"＋ {pname}", width=True):
                p_copy = pdata.copy(); p_copy["name"] = pname
                add_node("system", p_copy); st.rerun()
    
    if st.button("全リセット"): reset_all()

with col_edit:
    st.subheader("2. 詳細設定")
    current_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == st.session_state["selected_id"]), None)
    
    if current_idx is not None:
        current_data = st.session_state["pipes"][current_idx]
        def update_name():
            st.session_state["pipes"][current_idx]["name"] = st.session_state[f"name_{current_data['id']}"]
        st.text_input("名称", value=current_data["name"], key=f"name_{current_data['id']}", on_change=update_name)

        if current_data["id"] == "root": st.info("起点")
        else:
            is_fix = st.checkbox("流量固定", current_data.get("is_fixed_flow", False), key=f"fix_{current_data['id']}")
            if is_fix != current_data.get("is_fixed_flow", False): st.session_state["pipes"][current_idx]["is_fixed_flow"] = is_fix; st.rerun()
            if is_fix:
                fv = st.number_input("流量(L/min)", 0.0, step=1.0, value=current_data.get("fixed_flow_val", 0.0), key=f"fv_{current_data['id']}")
                st.session_state["pipes"][current_idx]["fixed_flow_val"] = fv
            
            leng = st.number_input("管長 (m)", 0.0, step=0.1, value=current_data.get("length", 2.0), key=f"ln_{current_data['id']}")
            st.session_state["pipes"][current_idx]["length"] = leng

            pipe_opts = ["(基本設定に従う)"] + list(PIPE_DATABASES.keys())
            curr_spec = current_data.get("specific_pipe_type")
            idx_spec = 0; 
            if curr_spec in PIPE_DATABASES: idx_spec = pipe_opts.index(curr_spec)
            def update_specific_pipe():
                val = st.session_state[f"spec_pipe_{current_data['id']}"]
                st.session_state["pipes"][current_idx]["specific_pipe_type"] = None if val == "(基本設定に従う)" else val
            st.selectbox("管種の個別指定:", options=pipe_opts, index=idx_spec, key=f"spec_pipe_{current_data['id']}", on_change=update_specific_pipe)

            current_pipe_db = PIPE_DATABASES[selected_pipe_type]
            if curr_spec and curr_spec in PIPE_DATABASES: current_pipe_db = PIPE_DATABASES[curr_spec]
            size_options = ["自動計算"] + [d["サイズ"] for d in current_pipe_db]
            current_manual = current_data.get("manual_size")
            if current_manual not in size_options: current_manual = "自動計算"
            def update_manual_size():
                val = st.session_state[f"manual_{current_data['id']}"]
                st.session_state["pipes"][current_idx]["manual_size"] = None if val == "自動計算" else val
            st.selectbox("口径固定:", options=size_options, index=size_options.index(current_manual), key=f"manual_{current_data['id']}", on_change=update_manual_size)

            if current_data["type"] == "system":
                st.markdown("---")
                if "BL" in building_type:
                    dw = st.number_input("戸数", 1, value=current_data.get("dwelling_count",1), key=f"dw_{current_data['id']}")
                    st.session_state["pipes"][current_idx]["dwelling_count"] = dw
                elif "人数" in building_type:
                    pc = st.number_input("人数", 1, value=current_data.get("person_count",1), key=f"pc_{current_data['id']}")
                    st.session_state["pipes"][current_idx]["person_count"] = pc
                else:
                    if "input_mode" not in st.session_state: st.session_state["input_mode"] = "public"
                    mode_col1, mode_col2 = st.columns(2)
                    if mode_col1.button("公共用リスト", type="primary" if st.session_state["input_mode"]=="public" else "secondary", width="stretch"):
                        st.session_state["input_mode"] = "public"; st.rerun()
                    if mode_col2.button("個人用リスト", type="primary" if st.session_state["input_mode"]=="private" else "secondary", width="stretch"):
                        st.session_state["input_mode"] = "private"; st.rerun()
                    
                    src_list = DEFAULT_PUBLIC_LIST if st.session_state["input_mode"] == "public" else DEFAULT_PRIVATE_LIST
                    suffix = "(公)" if st.session_state["input_mode"] == "public" else "(私)"
                    
                    fix_cols = st.columns(2)
                    for i, fname in enumerate(src_list):
                        save_key = f"{fname} {suffix}"
                        lu_val = FIXTURE_DATA.get(save_key, 0)
                        with fix_cols[i % 2]:
                            def update_fix(f_key=save_key, ui_key=f"f_{current_data['id']}_{save_key}"):
                                st.session_state["pipes"][current_idx]["fixtures"][f_key] = st.session_state[ui_key]
                            st.number_input(f"{fname} ({lu_val}LU)", min_value=0, step=1, value=current_data["fixtures"].get(save_key, 0), key=f"f_{current_data['id']}_{save_key}", on_change=update_fix)
                
                is_crit = st.checkbox("★最遠ルート末端に指定", current_data.get("is_manual_critical", False), key=f"cr_{current_data['id']}")
                if is_crit != current_data.get("is_manual_critical", False):
                    if is_crit:
                        for p in st.session_state["pipes"]: p["is_manual_critical"] = False
                    st.session_state["pipes"][current_idx]["is_manual_critical"] = is_crit
                    st.rerun()
        if current_data["id"] != "root":
            if st.button("削除", type="primary"): delete_current_node()

with col_view:
    st.subheader(f"3. 系統図")
    # **kwargsを追加したPipeSectionでインスタンス化
    node_map = {p["id"]: PipeSection(**p) for p in st.session_state["pipes"]}
    root_node = None
    for p in st.session_state["pipes"]:
        node = node_map[p["id"]]
        if p["parent"] and p["parent"] in node_map: node_map[p["parent"]].add_child(node)
        else: root_node = node
    
    critical_node = None
    if root_node:
        root_node.calculate(PIPE_DATABASES, selected_pipe_type, max_vel_setting, building_type, is_fv, person_calc_params, loss_params)
        root_node.calculate_cumulative_loss()
        critical_node = root_node.find_critical_node()

    if critical_node:
        crit_loss = critical_node.cum_head_loss
        st.success(f"🚩 最遠ルート末端: **{critical_node.name}**")
        m1, m2 = st.columns(2)
        m1.metric("合計損失水頭", f"{crit_loss:.3f} m")
        m2.metric("総配管長", f"{critical_node.cum_length:.1f} m")

    graph = graphviz.Digraph()
    graph.attr(rankdir=rankdir, nodesep='0.8', ranksep='1.0')
    graph.attr('node', fontname='Meiryo'); graph.attr('edge', fontname='Meiryo')
    
    crit_ids = set()
    if critical_node:
        c = critical_node
        while c:
            crit_ids.add(c.id)
            if c.parent_id: c = node_map[c.parent_id]
            else: c = None

    def draw(n):
        col = "red" if n.id in crit_ids else "black"
        pw = "2" if n.id in crit_ids else "1"
        lbl = n.name
        if n.id=="root": shape="box"; fill="#FFF9C4"
        elif n.type=="branch": shape="circle"; fill="#E3F2FD"; lbl=""
        else: shape="plain"; fill="#E8F5E9"
        
        if n.type=="branch": graph.node(n.id, label=lbl, shape=shape, style="filled", fillcolor=fill, width="0.1", height="0.1", color=col, penwidth=pw)
        elif n.type=="system": graph.node(n.id, label=lbl, shape="box", style="filled", fillcolor=fill, color=col, penwidth=pw)
        else: graph.node(n.id, label=lbl, shape=shape, style="filled", fillcolor=fill, color=col, penwidth=pw)

        for child in n.children:
            ecol = "red" if (n.id in crit_ids and child.id in crit_ids) else "black"
            epw = "3.0" if (n.id in crit_ids and child.id in crit_ids) else "1.0"
            style = "dashed" if child.size.startswith("規格外") else "solid"
            if child.size.startswith("規格外"): ecol="red"
            
            label = f"{child.size}\n{int(child.flow_lpm)}L"
            if show_length: label += f"\nL={child.length}m"
            if show_head_loss: label += f"\nΔh={child.head_loss}m"
            if show_calc_formula and child.calc_description: edge_label += f"\n[{child.calc_description}]"
            graph.edge(n.id, child.id, label=label, color=ecol, penwidth=epw, style=style)
            draw(child)

    if root_node:
        draw(root_node)
        st.graphviz_chart(graph)
        
        if "一般" in building_type:
            with st.expander("流量線図"):
                if st.button("線図更新"):
                    img_buf = get_flow_curve_image(0, 0, is_fv) # 簡易呼び出し
                    st.image(img_buf, caption="流量線図")

    st.markdown("---")
    if st.button("📊 Excel計算書作成"):
        if root_node:
            try:
                all_data = root_node.get_excel_data()
                df_all = pd.DataFrame(all_data)
                
                crit_data = []
                if critical_node:
                    curr = critical_node
                    path = []
                    while curr:
                        path.append(curr)
                        if curr.parent_id: curr = node_map[curr.parent_id]
                        else: curr = None
                    path.reverse()
                    for p in path:
                        if p.id=="root": continue
                        c_val = p.loss_params_used.get("C", "")
                        fit_val = p.loss_params_used.get("fitting", "")
                        crit_data.append({
                            "区間": f"{p.parent_name} -> {p.name}", "流量(L/min)": p.flow_lpm, "管径": p.size,
                            "流速(m/s)": p.velocity, "流速係数": c_val, "継手割増": fit_val,
                            "管長(m)": p.length, "損失水頭(m)": p.head_loss, "累計損失(m)": p.cum_head_loss
                        })
                df_crit = pd.DataFrame(crit_data)

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_all.to_excel(writer, index=False, sheet_name="全区間計算書")
                    if not df_crit.empty: df_crit.to_excel(writer, index=False, sheet_name="最遠ルート計算書")

                st.download_button("💾 Excel計算書をダウンロード", buffer.getvalue(), "calc_result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e: st.error(f"Excel作成エラー: {e}")