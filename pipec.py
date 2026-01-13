import os
import sys
import platform
import streamlit as st
import graphviz
import math
import pandas as pd
import json
import io
import matplotlib.pyplot as plt
from matplotlib import font_manager

# --- 0. 環境設定・パス設定 ---

# 実行ファイル(exe/app)またはクラウド環境の判定
if getattr(sys, 'frozen', False):
    # PyInstallerで固めた場合 (_MEIPASS)
    application_path = sys._MEIPASS
    # WindowsのEXE化時のみ、同梱したGraphvizのパスを通す
    if platform.system() == "Windows":
        graphviz_path = os.path.join(application_path, "Graphviz", "bin")
        os.environ["PATH"] += os.pathsep + graphviz_path
else:
    # 開発環境 or Streamlit Cloud
    application_path = os.path.dirname(__file__)
    # Windowsのローカル開発環境の場合のみ、Graphvizのパスを必要に応じて追加
    if platform.system() == "Windows":
        # ※自分の環境に合わせてパスを変更、またはPATH環境変数に通っていればコメントアウト可
        local_gv_path = os.path.join(application_path, "Graphviz", "bin")
        if os.path.exists(local_gv_path):
            os.environ["PATH"] += os.pathsep + local_gv_path

# グラフの日本語フォント設定
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.family'] = 'Meiryo'
elif system_name == "Darwin": # Mac
    plt.rcParams['font.family'] = 'Hiragino Sans'
else:
    plt.rcParams['font.family'] = 'sans-serif'

# --- 定数データ定義 ---

# 器具データ（負荷単位LU, 標準接続口径A）
FIXTURE_SPECS = {
    # 公共用
    "大便器 (洗浄弁) (公)": {"lu": 10, "size_a": 25},
    "大便器 (タンク) (公)": {"lu": 5, "size_a": 15},
    "小便器 (洗浄弁) (公)": {"lu": 5, "size_a": 15},
    "小便器 (タンク) (公)": {"lu": 3, "size_a": 15},
    "洗面器 (公)": {"lu": 2, "size_a": 15},
    "手洗器 (公)": {"lu": 0.5, "size_a": 15},
    "掃除用流し (公)": {"lu": 4, "size_a": 20},
    "厨房流し (公)": {"lu": 4, "size_a": 20},
    "シャワー (公)": {"lu": 4, "size_a": 20},
    # 個人用
    "大便器 (洗浄弁) (私)": {"lu": 6, "size_a": 25},
    "大便器 (タンク) (私)": {"lu": 3, "size_a": 15},
    "小便器 (洗浄弁) (私)": {"lu": 5, "size_a": 15},
    "小便器 (タンク) (私)": {"lu": 3, "size_a": 15},
    "洗面器 (私)": {"lu": 1, "size_a": 15},
    "手洗器 (私)": {"lu": 1, "size_a": 15},
    "台所流し (私)": {"lu": 3, "size_a": 20},
    "浴槽 (私)": {"lu": 2, "size_a": 20},
    "シャワー (私)": {"lu": 2, "size_a": 15},
    "洗濯機 (私)": {"lu": 2, "size_a": 15}
}

# 後方互換性・計算用
FIXTURE_DATA = {k: v["lu"] for k, v in FIXTURE_SPECS.items()}
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

PIPE_DATABASES = {
    "SGP-VB (硬質塩化ビニルライニング鋼管)": [
        {"サイズ": "15A", "内径(mm)": 14.7}, {"サイズ": "20A", "内径(mm)": 20.2},
        {"サイズ": "25A", "内径(mm)": 26.2}, {"サイズ": "32A", "内径(mm)": 34.2},
        {"サイズ": "40A", "内径(mm)": 39.9}, {"サイズ": "50A", "内径(mm)": 51.0},
        {"サイズ": "65A", "内径(mm)": 65.5}, {"サイズ": "80A", "内径(mm)": 78.1},
        {"サイズ": "100A", "内径(mm)": 103.1}, {"サイズ": "125A", "内径(mm)": 127.6},
        {"サイズ": "150A", "内径(mm)": 151.0},
    ],
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
    ],
    "PE (水道用ポリエチレン二層管1種)": [
        {"サイズ": "13", "内径(mm)": 14.5}, {"サイズ": "20", "内径(mm)": 19.0},
        {"サイズ": "25", "内径(mm)": 25.0}, {"サイズ": "30", "内径(mm)": 31.0},
        {"サイズ": "40", "内径(mm)": 36.0}, {"サイズ": "50", "内径(mm)": 46.0},
        {"サイズ": "75", "内径(mm)": 71.8}, {"サイズ": "100", "内径(mm)": 94.2},
    ]
}
PIPE_DATABASES["HIVP (耐衝撃性硬質塩化ビニル管)"] = PIPE_DATABASES["VP (硬質ポリ塩化ビニル管)"]

PIPE_COLORS = {"SGP": "#1976D2", "VP": "#757575", "HIVP": "#1565C0", "SU": "#00796B", "PE": "#388E3C"}

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
        slope = (table[x2] - table[x1]) / (x2 - x1)
        return table[x2] + slope * (lu - x2)
    for i in range(len(points) - 1):
        x1, x2 = points[i], points[i+1]
        if x1 < lu < x2:
            return table[x1] + (table[x2] - table[x1]) * (lu - x1) / (x2 - x1)
    return 0

# --- クラス定義 ---
class PipeSection:
    def __init__(self, id, name, type, fixtures=None, manual_size=None, dwelling_count=1, person_count=0, specific_pipe_type=None, length=2.0, is_fixed_flow=False, fixed_flow_val=0.0, is_manual_critical=False, static_head=0.0, required_pressure=0.0, equivalent_length=0.0, inner_pipe_length=2.0, fixture_type=None):
        self.id = id
        self.name = name
        self.type = type
        self.fixtures = fixtures if fixtures else {}
        self.fixture_type = fixture_type
        self.manual_size = manual_size
        self.dwelling_count = dwelling_count
        self.person_count = person_count
        self.specific_pipe_type = specific_pipe_type
        self.length = length
        self.equivalent_length = equivalent_length
        self.inner_pipe_length = inner_pipe_length
        self.static_head = static_head
        self.required_pressure = required_pressure
        self.is_fixed_flow = is_fixed_flow
        self.fixed_flow_val = fixed_flow_val
        self.is_manual_critical = is_manual_critical
        self.children = []
        self.parent_name = ""
        self.parent_id = None
        
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
        self.is_manual = False
        self.calc_description = ""
        self.used_pipe_type = ""
        self.loss_params_used = {}
        self.critical_inner_loss = 0.0

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
        if self.type == "fixture" and self.fixture_type:
            spec = FIXTURE_SPECS.get(self.fixture_type)
            if spec:
                load = spec["lu"]
                count = 1
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
        child_load_sum = 0.0
        child_system_sum = 0
        child_person_sum = 0
        child_fixture_sum = 0
        
        for child in self.children:
            c_load, c_sys, c_person, c_fix = child.calculate(all_pipe_db, default_pipe_type, max_velocity, building_type, is_fv, person_calc_params, loss_params)
            child_load_sum += c_load
            child_system_sum += c_sys
            child_person_sum += c_person
            child_fixture_sum += c_fix
            
        self.total_load = self.load_units + child_load_sum
        self.system_total = self.system_count + child_system_sum
        self.person_total = self.person_count_val + child_person_sum
        self.fixture_total = self.fixture_count + child_fixture_sum
        
        auto_flow = 0.0
        auto_desc = ""
        calc_by_dwelling = False
        
        if "集合住宅 (BL基準)" in building_type:
            N = self.system_total
            if N > 0:
                calc_by_dwelling = True
                if N < 10: auto_flow = 42 * (N ** 0.33); auto_desc = f"BL基準(N<10) {N}戸"
                else: auto_flow = 19 * (N ** 0.67); auto_desc = f"BL基準(N≧10) {N}戸"
        if "集合住宅 (人数基準)" in building_type:
            P = self.person_total
            if P > 0:
                calc_by_dwelling = True
                if person_calc_params:
                    if P <= 30: C = person_calc_params.get("C1", 26.0); k = person_calc_params.get("k1", 0.36)
                    else: C = person_calc_params.get("C2", 13.0); k = person_calc_params.get("k2", 0.56)
                    auto_flow = C * (P ** k); auto_desc = f"人数算定 {P}人"
        if "一戸建て" in building_type:
             N = self.fixture_total
             if N > 0:
                 calc_by_dwelling = True
                 auto_flow = 17 * (N ** 0.475); auto_desc = f"総水栓数法 {N}個"
        if not calc_by_dwelling:
            if self.total_load > 0:
                auto_flow = interpolate_flow(self.total_load, is_fv)
                auto_desc = f"負荷単位法 {self.total_load} LU"
            else:
                auto_flow = 0; auto_desc = "0 LU"

        if self.is_fixed_flow:
            self.flow_lpm = self.fixed_flow_val
            self.calc_description = f"固定 {self.flow_lpm}L/min"
        else:
            self.flow_lpm = auto_flow
            self.calc_description = auto_desc

        q_m3s = self.flow_lpm / 60000
        target_pipe_type = self.specific_pipe_type if self.specific_pipe_type else default_pipe_type
        self.used_pipe_type = target_pipe_type
        current_specs_df = pd.DataFrame(all_pipe_db.get(target_pipe_type, []))
        d_mm_actual = 0.0
        
        if self.manual_size and self.manual_size != "自動計算":
            self.size = self.manual_size
            self.is_manual = True
            if not current_specs_df.empty:
                row = current_specs_df[current_specs_df["サイズ"] == self.manual_size]
                if not row.empty and q_m3s > 0:
                    d_mm_actual = row.iloc[0]["内径(mm)"]
                    area = math.pi * ((d_mm_actual/1000)/2)**2
                    self.velocity = round(q_m3s / area, 2)
                else: self.velocity = 0.0
            self.calc_description += f" [固定: {self.size}]"
        else:
            self.is_manual = False
            best_size = "規格外"
            best_vel = 0.0
            if "SU" in target_pipe_type:
                sorted_capacity = sorted(SU_FLOW_CAPACITY.items(), key=lambda x: x[1])
                found_su = False
                for size_name, cap_lpm in sorted_capacity:
                    if self.flow_lpm <= cap_lpm:
                        best_size = size_name
                        row = current_specs_df[current_specs_df["サイズ"] == size_name]
                        if not row.empty:
                            d_mm_actual = row.iloc[0]["内径(mm)"]
                            area = math.pi * ((d_mm_actual/1000)/2)**2
                            best_vel = round(q_m3s / area, 2) if area > 0 else 0.0
                        found_su = True
                        break
                if not found_su and self.flow_lpm > 0: best_size = "規格外(過大)"
            else:
                if not current_specs_df.empty:
                    sorted_specs = current_specs_df.sort_values("内径(mm)")
                    for _, row in sorted_specs.iterrows():
                        d_mm = row["内径(mm)"]
                        area = math.pi * ((d_mm/1000)/2)**2
                        if area <= 0: continue
                        vel = q_m3s / area
                        if vel <= max_velocity:
                            best_size = row["サイズ"]
                            best_vel = round(vel, 2)
                            d_mm_actual = d_mm
                            break
            self.size = best_size
            self.velocity = best_vel
            
        self.head_loss = 0.0
        self.loss_params_used = loss_params.copy() if loss_params else {}
        if loss_params and d_mm_actual > 0 and q_m3s > 0:
            C_val = loss_params.get("C", 130.0)
            fit_rate = loss_params.get("fitting", 1.2)
            D_m = d_mm_actual / 1000.0
            L_eq = (self.length * fit_rate) + self.equivalent_length
            h = 10.666 * (C_val ** -1.852) * (D_m ** -4.87) * (q_m3s ** 1.852) * L_eq
            self.head_loss = round(h, 3)
        
        self.critical_inner_loss = 0.0
        if self.type == "system" and self.fixtures:
            max_inner_loss = 0.0
            for f_name, qty in self.fixtures.items():
                if qty <= 0: continue
                spec = FIXTURE_SPECS.get(f_name)
                if not spec: continue
                f_size_a = spec["size_a"]
                f_d_mm = 16.0 
                specs_df = pd.DataFrame(all_pipe_db.get(self.used_pipe_type, []))
                if not specs_df.empty:
                    search_str = get_display_size(f_size_a, self.used_pipe_type)
                    row = specs_df[specs_df["サイズ"] == search_str]
                    if not row.empty: f_d_mm = row.iloc[0]["内径(mm)"]
                if f_d_mm > 0 and loss_params:
                    f_lu = spec["lu"]
                    f_flow_lpm = interpolate_flow(f_lu, is_fv)
                    f_q_m3s = f_flow_lpm / 60000
                    f_D_m = f_d_mm / 1000.0
                    f_L_eq = self.inner_pipe_length * loss_params.get("fitting", 1.2)
                    f_h = 10.666 * (loss_params.get("C", 130.0) ** -1.852) * (f_D_m ** -4.87) * (f_q_m3s ** 1.852) * f_L_eq
                    if f_h > max_inner_loss: max_inner_loss = f_h
            self.critical_inner_loss = max_inner_loss
        return self.total_load, self.system_total, self.person_total, self.fixture_total

    def calculate_cumulative_loss(self, parent_cum_loss=0.0, parent_cum_len=0.0):
        self.cum_head_loss = parent_cum_loss + self.head_loss
        self.cum_length = parent_cum_len + self.length
        for child in self.children:
            child.calculate_cumulative_loss(self.cum_head_loss, self.cum_length)

    def find_critical_node(self):
        all_terminals = self.get_all_terminals()
        if not all_terminals: return self
        def get_total_head(t):
            req_head_m = t.required_pressure * 102.0
            return t.cum_head_loss + t.static_head + req_head_m + t.critical_inner_loss
        manual_targets = [t for t in all_terminals if t.is_manual_critical]
        if manual_targets: return max(manual_targets, key=get_total_head)
        else: return max(all_terminals, key=get_total_head)

    def get_all_terminals(self):
        terminals = []
        if not self.children: terminals.append(self)
        for child in self.children: terminals.extend(child.get_all_terminals())
        return terminals

    def get_excel_data(self):
        data = []
        if self.id != "root":
            section_name = f"{self.parent_name} → {self.name}"
            node_type_str = "分岐"
            if self.type == "system": node_type_str = "系統(PS)"
            elif self.type == "fixture": node_type_str = "器具"
            row = {
                "区間名称": section_name, "始点": self.parent_name, "終点": self.name,
                "種別": node_type_str, "流量 (L/min)": round(self.flow_lpm, 1),
                "管種": self.used_pipe_type, "口径": self.size,
                "流速 (m/s)": self.velocity, "管長 (m)": self.length,
                "単独損失 (m)": self.head_loss, "累計損失 (m)": round(self.cum_head_loss, 3),
                "器具接続損失(m)": round(self.critical_inner_loss, 3) if self.type=="system" else 0
            }
            data.append(row)
        for child in self.children: data.extend(child.get_excel_data())
        return data

# --- 2. コールバック ---
def add_node(node_type, preset_data=None):
    # === 無料版制限: ノード数チェック ===
    if not st.session_state.get("is_pro", False):
        current_branches = len([p for p in st.session_state["pipes"] if p["type"] == "branch"])
        current_terminals = len([p for p in st.session_state["pipes"] if p["type"] in ["system", "fixture"]])
        
        # 分岐4個以上禁止
        if node_type == "branch" and current_branches >= 4:
            st.toast("🚫 無料版では分岐点は4つまでです。Pro版をご購入ください。", icon="🔒")
            return
        
        # 末端4個以上禁止
        if node_type in ["system", "fixture"] and current_terminals >= 4:
            st.toast("🚫 無料版では末端は4つまでです。Pro版をご購入ください。", icon="🔒")
            return

    # 通常の追加処理
    if node_type == "branch":
        st.session_state["branch_counter"] += 1
        count = st.session_state["branch_counter"]
        name_prefix = "分岐"
        init_fixtures = {}
        init_dw, init_person, init_f_type = 1, 1, None
    elif node_type == "system":
        st.session_state["system_counter"] += 1
        count = st.session_state["system_counter"]
        name_prefix = "系統"
        if preset_data:
            init_fixtures = preset_data["fixtures"].copy()
            init_dw = preset_data.get("dw", 1)
            init_person = preset_data.get("person", 1)
            name_prefix = f"{name_prefix} ({preset_data.get('name', 'Preset')})"
        else:
            init_fixtures = {}
            init_dw, init_person = 1, 1
        init_f_type = None
    elif node_type == "fixture":
        st.session_state["branch_counter"] += 1 
        count = st.session_state["branch_counter"]
        name_prefix = "器具"
        init_fixtures = {}
        init_dw, init_person = 0, 0
        init_f_type = "洗面器 (私)"

    new_id = f"node_{node_type}_{count}"
    new_name = f"{name_prefix}-{count}"
    parent_id = st.session_state["selected_id"]
    st.session_state["pipes"].append({
        "id": new_id, "name": new_name, "type": node_type,
        "parent": parent_id, "fixtures": init_fixtures, "manual_size": None, 
        "dwelling_count": init_dw, "person_count": init_person, "specific_pipe_type": None,
        "length": 2.0, "is_fixed_flow": False, "fixed_flow_val": 0.0, "is_manual_critical": False,
        "static_head": 0.0, "required_pressure": 0.0, "equivalent_length": 0.0, "inner_pipe_length": 2.0, "fixture_type": init_f_type
    })
    st.session_state["selected_id"] = new_id

def insert_node_before():
    # 挿入も無料版制限対象にする(分岐が増えるため)
    if not st.session_state.get("is_pro", False):
        current_branches = len([p for p in st.session_state["pipes"] if p["type"] == "branch"])
        if current_branches >= 4:
            st.toast("🚫 無料版では分岐点は4つまでです。Pro版をご購入ください。", icon="🔒")
            return

    target_id = st.session_state["selected_id"]
    if target_id == "root": return
    target_node = next((p for p in st.session_state["pipes"] if p["id"] == target_id), None)
    if not target_node: return
    st.session_state["branch_counter"] += 1
    count = st.session_state["branch_counter"]
    new_id = f"node_branch_{count}"
    new_name = f"分岐-{count}"
    parent_id = target_node["parent"]
    new_node_data = {
        "id": new_id, "name": new_name, "type": "branch",
        "parent": parent_id, "fixtures": {}, "manual_size": None, 
        "dwelling_count": 1, "person_count": 1, "specific_pipe_type": None,
        "length": 2.0, "is_fixed_flow": False, "fixed_flow_val": 0.0, "is_manual_critical": False,
        "static_head": 0.0, "required_pressure": 0.0, "equivalent_length": 0.0, "inner_pipe_length": 2.0, "fixture_type": None
    }
    st.session_state["pipes"].append(new_node_data)
    target_node["parent"] = new_id
    st.session_state["selected_id"] = new_id

def renumber_nodes():
    pipes = st.session_state["pipes"]
    children_map = {p["id"]: [] for p in pipes}
    node_map = {p["id"]: p for p in pipes}
    root_id = None
    for p in pipes:
        if p["parent"] is None: root_id = p["id"]
        elif p["parent"] in children_map: children_map[p["parent"]].append(p["id"])
    if not root_id: return
    b_count = 1
    def traverse(nid):
        nonlocal b_count
        node = node_map[nid]
        if node["id"] != "root":
            if node["type"] == "branch":
                node["name"] = f"分岐-{b_count}"
                b_count += 1
        for child_id in children_map.get(nid, []): traverse(child_id)
    traverse(root_id)
    st.session_state["branch_counter"] = b_count
    st.success("分岐点の番号のみ自動修正しました！")

def delete_current_node():
    target_id = st.session_state["selected_id"]
    if target_id == "root": return
    st.session_state["pipes"] = [p for p in st.session_state["pipes"] if p["id"] != target_id]
    for p in st.session_state["pipes"]:
        if p["parent"] == target_id: p["parent"] = "root"
    st.session_state["selected_id"] = "root"

def delete_specific_node(node_id):
    if node_id == "root": return
    st.session_state["pipes"] = [p for p in st.session_state["pipes"] if p["id"] != node_id]
    for p in st.session_state["pipes"]:
        if p["parent"] == node_id: p["parent"] = "root"
    if st.session_state["selected_id"] == node_id:
        st.session_state["selected_id"] = "root"

def reset_all():
    st.session_state["pipes"] = [{"id": "root", "name": "ポンプ(始点)", "type": "branch", "parent": None, "fixtures": {}, "manual_size": None, "dwelling_count": 0, "person_count": 0, "specific_pipe_type": None, "length": 0.0, "is_fixed_flow": False, "fixed_flow_val": 0.0, "is_manual_critical": False, "static_head": 0.0, "required_pressure": 0.0, "equivalent_length": 0.0, "inner_pipe_length": 2.0, "fixture_type": None}]
    st.session_state["branch_counter"] = 0
    st.session_state["system_counter"] = 0
    st.session_state["selected_id"] = "root"
    if "chart_image" in st.session_state: del st.session_state["chart_image"]
    if "excel_bytes" in st.session_state: del st.session_state["excel_bytes"]
    if "pdf_bytes" in st.session_state: del st.session_state["pdf_bytes"]

def set_parent(node_id):
    st.session_state["selected_id"] = node_id

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
    ax.set_title('給水負荷単位同時使用流量線図')
    ax.legend(loc='upper left', fontsize='small')
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf

def get_display_size(size_a, pipe_type):
    if "SGP" in pipe_type:
        return f"{size_a}A"
    elif "VP" in pipe_type or "PE" in pipe_type:
        if size_a == 15: return "13"
        if size_a == 20: return "20"
        if size_a == 25: return "25"
        if size_a == 32: return "30"
        if size_a == 40: return "40"
        if size_a == 50: return "50"
        return f"{size_a}"
    elif "SU" in pipe_type:
        if size_a == 15: return "13Su"
        if size_a == 20: return "20Su"
        if size_a == 25: return "25Su"
        if size_a == 32: return "30Su"
        if size_a == 40: return "40Su"
        if size_a == 50: return "50Su"
        return f"{size_a}Su"
    return f"{size_a}A"

# --- 5. UI設定 ---
st.set_page_config(layout="wide", page_title="給水管計算ツール Final v61")

# Session State 初期化
if "pipes" not in st.session_state:
    st.session_state["pipes"] = [{"id": "root", "name": "ポンプ(始点)", "type": "branch", "parent": None, "fixtures": {}, "manual_size": None, "dwelling_count": 0, "person_count": 0, "specific_pipe_type": None, "length": 0.0, "is_fixed_flow": False, "fixed_flow_val": 0.0, "is_manual_critical": False, "static_head": 0.0, "required_pressure": 0.0, "equivalent_length": 0.0, "inner_pipe_length": 2.0, "fixture_type": None}]
if "branch_counter" not in st.session_state: st.session_state["branch_counter"] = 0
if "system_counter" not in st.session_state: st.session_state["system_counter"] = 0
if "selected_id" not in st.session_state: st.session_state["selected_id"] = "root"
if "input_mode" not in st.session_state: st.session_state["input_mode"] = "public"
if "custom_presets" not in st.session_state: st.session_state["custom_presets"] = PRESETS.copy()
if "is_pro" not in st.session_state: st.session_state["is_pro"] = False

# --- サイドバー UI ---
with st.sidebar:
    # 🔓 ライセンス認証エリア
    st.markdown("### 🔓 ライセンス認証")
    if st.session_state["is_pro"]:
        st.success("💎 Pro版 (制限解除済)")
        if st.button("ログアウト / 無効化"):
            st.session_state["is_pro"] = False
            st.rerun()
    else:
        st.info("現在は「無料版」です。\n- 分岐点・末端は各4つまで\n- Excel/PDF出力不可\n- 流量線図作成不可")
        # Stripeへのリンクなどを貼る場合はここ
        # st.link_button("Pro版を購入 (¥500/月)", "https://buy.stripe.com/...")
        input_pass = st.text_input("パスワードを入力", type="password", key="pro_pass_input")
        if st.button("Pro版を有効化"):
            CORRECT_PASSWORD = "2026-PIPE-USER" 
            # セキュリティを高めるなら st.secrets["APP_PASSWORD"] を使用
            if input_pass == CORRECT_PASSWORD:
                st.session_state["is_pro"] = True
                st.balloons()
                st.rerun()
            else:
                st.error("パスワードが違います")
    
    st.divider()
    
    st.header("📂 ファイル操作")
    current_json = json.dumps(st.session_state["pipes"], ensure_ascii=False, indent=2)
    st.download_button("💾 現在の構成を保存 (JSON)", current_json, "pipe_config.json", "application/json", key="json_download")
    uploaded_file = st.file_uploader("📂 保存データを読み込む", type=["json"])
    if uploaded_file is not None:
        try:
            loaded_data = json.load(uploaded_file)
            st.session_state["pipes"] = loaded_data
            max_b, max_s = 0, 0
            for p in loaded_data:
                try:
                    num = int(p["id"].split("_")[-1])
                    if p["type"] == "branch" and num > max_b: max_b = num
                    if p["type"] == "system" and num > max_s: max_s = num
                except: pass
            st.session_state["branch_counter"] = max_b + 1
            st.session_state["system_counter"] = max_s + 1
            st.session_state["selected_id"] = "root"
            st.success("読込完了！")
            st.rerun()
        except: st.error("読込エラー")

    st.divider()
    st.header("⚙️ 設計条件")
    building_type = st.selectbox("建物の用途", ["一般・事務所 (負荷単位法)", "集合住宅 (BL基準)", "集合住宅 (人数基準)", "一戸建て (総水栓数法)"], key="building_type_selection")
    person_calc_params = {}
    is_fv = False
    
    if "一般" in building_type:
        toilet_type = st.radio("大便器方式", ["洗浄弁式", "ロータンク式"])
        is_fv = (toilet_type == "洗浄弁式")
    elif "人数基準" in building_type:
        st.caption("👥 人数計算の係数設定 (Q = C × P^k)")
        col1, col2 = st.columns(2)
        c1 = col1.number_input("係数 C1", value=26.0, step=0.1, format="%.1f")
        k1 = col2.number_input("指数 k1", value=0.36, step=0.01, format="%.2f")
        col3, col4 = st.columns(2)
        c2 = col3.number_input("係数 C2", value=13.0, step=0.1, format="%.1f")
        k2 = col4.number_input("指数 k2", value=0.56, step=0.01, format="%.2f")
        person_calc_params = {"C1": c1, "k1": k1, "C2": c2, "k2": k2}
    else:
        st.caption("▼ グラフ表示用設定")
        toilet_type = st.radio("大便器方式 (参考)", ["洗浄弁式", "ロータンク式"])
        is_fv = (toilet_type == "洗浄弁式")

    st.divider()
    selected_pipe_type = st.selectbox("基本の管種", list(PIPE_DATABASES.keys()))
    
    st.markdown("#### 🎨 図面表示設定")
    graph_direction = st.radio("図面の向き", ["横書き (左→右)", "縦書き (上→下)", "縦書き (下→上)"], horizontal=True)
    rankdir = "LR" if "左→右" in graph_direction else ("TB" if "上→下" in graph_direction else "BT")
    color_mode = st.selectbox("色分けモード", ["なし (標準)", "管種別", "流速別"], index=0)
    show_fixtures_mode = st.radio("末端器具の表示", ["なし", "すべて", "最遠ルート末端のみ"])

    st.divider()
    show_pipe_length = st.checkbox("図面に管長を表示", value=False)
    show_velocity = st.checkbox("図面に流速を表示", value=False)
    show_head_loss = st.checkbox("図面に損失水頭を表示", value=False)
    show_calc_formula = st.checkbox("図面に計算式を表示", value=False)
    max_vel_setting = st.number_input("許容流速 (m/s)", value=2.0, step=0.1, format="%.1f")
    
    with st.expander("🌊 摩擦損失計算の設定"):
        st.caption("ヘーゼン・ウィリアムス式 (H = 10.666 * C^-1.85 * D^-4.87 * Q^1.85 * L)")
        c_val_setting = st.number_input("流速係数 C", value=130.0, step=1.0)
        fitting_ratio = st.number_input("継手類による割増率", value=1.2, step=0.1, format="%.1f")
        loss_params = {"C": c_val_setting, "fitting": fitting_ratio}

# --- メインエリア ---
col_ctrl, col_edit, col_view = st.columns([0.8, 1.2, 2.5])

with col_ctrl:
    st.subheader("1. 構成作成")
    current_parent = next((p for p in st.session_state["pipes"] if p["id"] == st.session_state["selected_id"]), None)
    if current_parent:
        icon = '🔵' if current_parent['type'] == 'branch' else ('🚰' if current_parent['type'] == 'fixture' else '🏠')
        st.info(f"現在の接続先:\n\n**{icon} {current_parent['name']}**")
    else:
        st.session_state["selected_id"] = "root"
        st.warning("接続先を選択してください")

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        st.caption("🔵 分岐点")
        branches = [p for p in st.session_state["pipes"] if p["type"] == "branch"]
        for p in branches:
            is_active = (p["id"] == st.session_state["selected_id"])
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"{p['name']}", key=f"sel_{p['id']}", type=btn_type, width="stretch"):
                set_parent(p["id"])
                st.rerun()
    with sel_col2:
        st.caption("🏠 系統・末端")
        systems = [p for p in st.session_state["pipes"] if p["type"] == "system"]
        for p in systems:
            is_active = (p["id"] == st.session_state["selected_id"])
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"{p['name']}", key=f"sel_{p['id']}", type=btn_type, width="stretch"):
                set_parent(p["id"])
                st.rerun()

    st.write("▼ 追加ボタン")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.button("＋分岐点\n(通過)", width="stretch", on_click=add_node, args=("branch",))
        if st.session_state["selected_id"] != "root":
            st.button("＋ 親との間に挿入", width="stretch", on_click=insert_node_before)
    with btn_col2:
        sys_btn_label = "＋住戸/系統\n(複合末端)" if "集合住宅" in building_type else "＋系統\n(複合末端)"
        st.button(sys_btn_label, width="stretch", on_click=add_node, args=("system",))
        st.button("＋ 器具\n(終端)", width="stretch", on_click=add_node, args=("fixture",))
    
    with st.expander("⚡ プリセットから追加"):
        for pname, pdata in st.session_state["custom_presets"].items():
            pass_data = pdata.copy()
            pass_data["name"] = pname
            if st.button(f"＋ {pname}", width="stretch"):
                add_node("system", pass_data)
                st.rerun()

    st.markdown("---")
    st.button("🔢 番号の自動修正", on_click=renumber_nodes)
    st.button("🗑️ 全リセット", on_click=reset_all)

# --- 計算ロジック実行 ---
node_map = {
    p["id"]: PipeSection(
        p["id"], p["name"], p["type"], p["fixtures"], 
        p.get("manual_size"), p.get("dwelling_count", 1), 
        p.get("person_count", 0), p.get("specific_pipe_type"),
        p.get("length", 2.0),
        p.get("is_fixed_flow", False), p.get("fixed_flow_val", 0.0),
        p.get("is_manual_critical", False),
        p.get("static_head", 0.0), p.get("required_pressure", 0.0),
        p.get("equivalent_length", 0.0),
        p.get("inner_pipe_length", 2.0),
        p.get("fixture_type", None)
    ) for p in st.session_state["pipes"]
}
root_node = None
for p in st.session_state["pipes"]:
    node = node_map[p["id"]]
    if p["parent"]:
        parent = node_map.get(p["parent"])
        if parent: parent.add_child(node)
    else:
        root_node = node

current_flow = 0
current_load = 0
critical_node = None
sel_node = None
if root_node: 
    root_node.calculate(PIPE_DATABASES, selected_pipe_type, max_vel_setting, building_type, is_fv, person_calc_params, loss_params)
    root_node.calculate_cumulative_loss()
    critical_node = root_node.find_critical_node()
    if st.session_state["selected_id"] in node_map:
        sel_node = node_map[st.session_state["selected_id"]]
        current_flow = sel_node.flow_lpm
        current_load = sel_node.total_load

with col_edit:
    st.subheader("2. 詳細設定")
    current_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == st.session_state["selected_id"]), None)
    
    if current_idx is not None:
        current_data = st.session_state["pipes"][current_idx]
        tab_basic, tab_pipe, tab_terminal, tab_children = st.tabs(["📝 基本情報", "📏 配管・損失", "🚩 末端条件", "🌲 配下・接続"])
        
        with tab_basic:
            def update_name():
                st.session_state["pipes"][current_idx]["name"] = st.session_state[f"name_{current_data['id']}"]
            st.text_input("名称", value=current_data["name"], key=f"name_{current_data['id']}", on_change=update_name)

            if current_data["id"] == "root":
                st.info("🏭 起点（ポンプ）")
            else:
                if current_data["type"] == "fixture":
                    st.info("🚰 器具（終端）")
                    if "input_mode" not in st.session_state: st.session_state["input_mode"] = "public"
                    mode_col1, mode_col2 = st.columns(2)
                    if mode_col1.button("公共用", type="primary" if st.session_state["input_mode"]=="public" else "secondary", width="stretch", key="fmode_pub"):
                        st.session_state["input_mode"] = "public"; st.rerun()
                    if mode_col2.button("個人用", type="primary" if st.session_state["input_mode"]=="private" else "secondary", width="stretch", key="fmode_priv"):
                        st.session_state["input_mode"] = "private"; st.rerun()
                    
                    f_list = DEFAULT_PUBLIC_LIST if st.session_state["input_mode"] == "public" else DEFAULT_PRIVATE_LIST
                    suffix = "(公)" if st.session_state["input_mode"] == "public" else "(私)"
                    full_list = [f"{f} {suffix}" for f in f_list]
                    curr_ft = current_data.get("fixture_type")
                    idx_ft = 0
                    if curr_ft in full_list: idx_ft = full_list.index(curr_ft)
                    
                    def update_fixture_type():
                        st.session_state["pipes"][current_idx]["fixture_type"] = st.session_state[f"ftype_{current_data['id']}"]
                    st.selectbox("器具の種類", options=full_list, index=idx_ft, key=f"ftype_{current_data['id']}", on_change=update_fixture_type)
                    
                    if curr_ft and curr_ft in FIXTURE_SPECS:
                        spec = FIXTURE_SPECS[curr_ft]
                        st.caption(f"負荷単位: {spec['lu']} LU | 標準口径: {spec['size_a']}A")
                        if st.button("標準口径を適用"):
                            size_disp = get_display_size(spec["size_a"], selected_pipe_type)
                            current_pipe_db = PIPE_DATABASES[selected_pipe_type]
                            size_options = [d["サイズ"] for d in current_pipe_db]
                            if size_disp in size_options:
                                st.session_state["pipes"][current_idx]["manual_size"] = size_disp
                                st.success(f"{size_disp} を適用しました")
                                st.rerun()
                            else: st.warning(f"規格に {size_disp} が見つかりません")
                else:
                    st.markdown("##### 💧 流量設定")
                    is_fixed = st.checkbox("流量を固定する (手入力)", value=current_data.get("is_fixed_flow", False), key=f"is_fixed_{current_data['id']}")
                    def update_fixed_flow_flag():
                        st.session_state["pipes"][current_idx]["is_fixed_flow"] = st.session_state[f"is_fixed_{current_data['id']}"]
                    if is_fixed != current_data.get("is_fixed_flow", False):
                        st.session_state["pipes"][current_idx]["is_fixed_flow"] = is_fixed
                        st.rerun()

                    if is_fixed:
                        def update_fixed_val():
                            st.session_state["pipes"][current_idx]["fixed_flow_val"] = st.session_state[f"fixed_val_{current_data['id']}"]
                        st.number_input("設定流量 (L/min)", min_value=0.0, step=1.0, value=current_data.get("fixed_flow_val", 0.0), key=f"fixed_val_{current_data['id']}", on_change=update_fixed_val)
                    
                    if current_data["type"] == "system":
                        if "BL基準" in building_type:
                            def update_dw(): st.session_state["pipes"][current_idx]["dwelling_count"] = st.session_state[f"dw_{current_data['id']}"]
                            st.number_input("担当する戸数 (戸)", min_value=1, value=current_data.get("dwelling_count", 1), step=1, key=f"dw_{current_data['id']}", on_change=update_dw)
                        elif "人数基準" in building_type:
                            def update_pc(): st.session_state["pipes"][current_idx]["person_count"] = st.session_state[f"pc_{current_data['id']}"]
                            current_p = current_data.get("person_count", 1)
                            st.number_input("居住人数 (人)", min_value=1, value=current_p, step=1, key=f"pc_{current_data['id']}", on_change=update_pc)

        with tab_pipe:
            if current_data["id"] != "root":
                st.markdown("##### 📏 サイズ・管長")
                def update_length():
                    st.session_state["pipes"][current_idx]["length"] = st.session_state[f"len_{current_data['id']}"]
                st.number_input("管長 (m)", min_value=0.0, step=0.1, value=current_data.get("length", 2.0), key=f"len_{current_data['id']}", on_change=update_length)
                
                def update_eq_len():
                    st.session_state["pipes"][current_idx]["equivalent_length"] = st.session_state[f"eq_len_{current_data['id']}"]
                st.number_input("局所損失 加算長 (m)", min_value=0.0, step=0.1, value=current_data.get("equivalent_length", 0.0), key=f"eq_len_{current_data['id']}", on_change=update_eq_len)

                pipe_opts = ["(基本設定に従う)"] + list(PIPE_DATABASES.keys())
                curr_spec = current_data.get("specific_pipe_type")
                idx_spec = 0
                if curr_spec in PIPE_DATABASES: idx_spec = pipe_opts.index(curr_spec)
                def update_specific_pipe():
                    val = st.session_state[f"spec_pipe_{current_data['id']}"]
                    if val == "(基本設定に従う)": st.session_state["pipes"][current_idx]["specific_pipe_type"] = None
                    else: st.session_state["pipes"][current_idx]["specific_pipe_type"] = val
                st.selectbox("管種の個別指定:", options=pipe_opts, index=idx_spec, key=f"spec_pipe_{current_data['id']}", on_change=update_specific_pipe)

                current_pipe_db = PIPE_DATABASES[selected_pipe_type]
                if curr_spec and curr_spec in PIPE_DATABASES: current_pipe_db = PIPE_DATABASES[curr_spec]
                size_options = ["自動計算"] + [d["サイズ"] for d in current_pipe_db]
                current_manual = current_data.get("manual_size")
                if current_manual not in size_options: current_manual = "自動計算"
                def update_manual_size():
                    new_val = st.session_state[f"manual_{current_data['id']}"]
                    st.session_state["pipes"][current_idx]["manual_size"] = None if new_val == "自動計算" else new_val
                st.selectbox("口径固定:", options=size_options, index=size_options.index(current_manual), key=f"manual_{current_data['id']}", on_change=update_manual_size)
            else: st.write("ルートノードに配管設定はありません")

        with tab_terminal:
            if current_data["type"] == "system" or current_data["type"] == "fixture":
                st.markdown("##### 🚩 最遠ルート・必要圧力")
                is_crit = st.checkbox("この末端を最遠（計算）ルートとする", value=current_data.get("is_manual_critical", False), key=f"crit_{current_data['id']}")
                if is_crit != current_data.get("is_manual_critical", False):
                    if is_crit:
                        for p in st.session_state["pipes"]: p["is_manual_critical"] = False
                    st.session_state["pipes"][current_idx]["is_manual_critical"] = is_crit
                    st.rerun()
                
                def update_head_params():
                     st.session_state["pipes"][current_idx]["static_head"] = st.session_state[f"shead_{current_data['id']}"]
                     st.session_state["pipes"][current_idx]["required_pressure"] = st.session_state[f"reqp_{current_data['id']}"]
                col_h1, col_h2 = st.columns(2)
                col_h1.number_input("ポンプからの実揚程 (m)", value=current_data.get("static_head", 0.0), step=0.1, key=f"shead_{current_data['id']}", on_change=update_head_params)
                col_h2.number_input("末端必要圧力 (MPa)", value=current_data.get("required_pressure", 0.0), step=0.01, format="%.2f", key=f"reqp_{current_data['id']}", on_change=update_head_params)
                
                if current_data["type"] == "system" and "一般" in building_type:
                    st.markdown("##### 🚽 簡易器具設定")
                    if "input_mode_sys" not in st.session_state: st.session_state["input_mode_sys"] = "public"
                    mode_col1, mode_col2 = st.columns(2)
                    if mode_col1.button("公共用リスト", type="primary" if st.session_state["input_mode_sys"]=="public" else "secondary", width="stretch", key="smode_pub"):
                        st.session_state["input_mode_sys"] = "public"; st.rerun()
                    if mode_col2.button("個人用リスト", type="primary" if st.session_state["input_mode_sys"]=="private" else "secondary", width="stretch", key="smode_priv"):
                        st.session_state["input_mode_sys"] = "private"; st.rerun()
                    
                    src_list = DEFAULT_PUBLIC_LIST if st.session_state["input_mode_sys"] == "public" else DEFAULT_PRIVATE_LIST
                    suffix = "(公)" if st.session_state["input_mode_sys"] == "public" else "(私)"
                    fix_cols = st.columns(2)
                    for i, fname in enumerate(src_list):
                        save_key = f"{fname} {suffix}"
                        lu_val = FIXTURE_DATA.get(save_key, 0)
                        with fix_cols[i % 2]:
                            def update_fix(f_key=save_key, ui_key=f"f_{current_data['id']}_{save_key}"):
                                st.session_state["pipes"][current_idx]["fixtures"][f_key] = st.session_state[ui_key]
                            st.number_input(f"{fname} ({lu_val}LU)", min_value=0, step=1, value=current_data["fixtures"].get(save_key, 0), key=f"f_{current_data['id']}_{save_key}", on_change=update_fix)
            else: st.info("分岐点には末端条件を設定できません")

        with tab_children:
            st.markdown(f"**{current_data['name']} の配下ノード編集**")
            children_indices = [i for i, p in enumerate(st.session_state["pipes"]) if p["parent"] == current_data["id"]]
            if children_indices:
                edit_data_list = []
                for idx in children_indices:
                    child = st.session_state["pipes"][idx]
                    calc_res = node_map.get(child["id"])
                    vel_val = calc_res.velocity if calc_res else 0.0
                    loss_val = calc_res.head_loss if calc_res else 0.0
                    edit_data_list.append({
                        "id": child["id"], "名称": child["name"], "種別": child["type"],
                        "管長 (m)": child.get("length", 2.0),
                        "器具種別": child.get("fixture_type", "") if child["type"]=="fixture" else "",
                        "口径固定": child.get("manual_size") if child.get("manual_size") else "自動計算",
                        "流速 (m/s)": round(vel_val, 2), "損失 (m)": round(loss_val, 3)
                    })
                df_children = pd.DataFrame(edit_data_list)
                all_fixtures_list = [""] + [f"{f} (公)" for f in DEFAULT_PUBLIC_LIST] + [f"{f} (私)" for f in DEFAULT_PRIVATE_LIST]
                size_list = ["自動計算"] + [d["サイズ"] for d in PIPE_DATABASES[selected_pipe_type]]
                child_config = {
                    "id": st.column_config.TextColumn("ID", disabled=True),
                    "名称": st.column_config.TextColumn("名称", required=True),
                    "種別": st.column_config.TextColumn("種別", disabled=True),
                    "管長 (m)": st.column_config.NumberColumn("管長 (m)", min_value=0.0, step=0.1, format="%.1f"),
                    "器具種別": st.column_config.SelectboxColumn("器具種別", options=all_fixtures_list, required=False),
                    "口径固定": st.column_config.SelectboxColumn("口径固定", options=size_list, required=True),
                    "流速 (m/s)": st.column_config.NumberColumn("流速 (m/s)", disabled=True, format="%.2f"),
                    "損失 (m)": st.column_config.NumberColumn("損失 (m)", disabled=True, format="%.3f"),
                }
                edited_children = st.data_editor(df_children, column_config=child_config, hide_index=True, width='stretch', key="children_editor", disabled=["id", "種別", "流速 (m/s)", "損失 (m)"])
                cols_to_check = ["id", "名称", "管長 (m)", "器具種別", "口径固定"]
                if not df_children[cols_to_check].equals(edited_children[cols_to_check]):
                    for index, row in edited_children.iterrows():
                        t_id = row["id"]
                        t_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == t_id), None)
                        if t_idx is not None:
                            st.session_state["pipes"][t_idx]["name"] = row["名称"]
                            st.session_state["pipes"][t_idx]["length"] = row["管長 (m)"]
                            st.session_state["pipes"][t_idx]["fixture_type"] = row["器具種別"] if row["器具種別"] else None
                            ms = row["口径固定"]
                            st.session_state["pipes"][t_idx]["manual_size"] = None if ms == "自動計算" else ms
                    st.rerun()

                st.markdown("---")
                for child_idx in children_indices:
                    child = st.session_state["pipes"][child_idx]
                    c_col1, c_col2, c_col3 = st.columns([0.6, 0.2, 0.2])
                    c_icon = "🔵" if child["type"]=="branch" else ("🚰" if child["type"]=="fixture" else "🏠")
                    c_col1.write(f"{c_icon} {child['name']}")
                    if c_col2.button("選択", key=f"sel_c_{child['id']}", width="stretch"):
                        set_parent(child["id"])
                        st.rerun()
                    if c_col3.button("削除", key=f"del_c_{child['id']}", type="primary", width="stretch"):
                        delete_specific_node(child["id"])
                        st.rerun()
            else: st.write("(配下ノードはありません)")
            
            st.markdown("---")
            st.write("▼ ここに子ノードを追加")
            add_c1, add_c2, add_c3 = st.columns(3)
            if add_c1.button("＋分岐", key="add_br_here", on_click=add_node, args=("branch",)): pass
            if add_c2.button("＋系統", key="add_sys_here", on_click=add_node, args=("system",)): pass
            if add_c3.button("＋器具", key="add_fix_here", on_click=add_node, args=("fixture",)): pass

        st.markdown("---")
        if current_data["type"] != "root":
            st.button("このノードを削除", key="del_node_main", on_click=delete_current_node, type="primary")
    
    st.markdown("---")
    st.subheader("💧 流量計算の根拠")
    if sel_node:
        if sel_node.calc_description: st.info(sel_node.calc_description)
        else: st.write("(計算情報なし)")

with col_view:
    st.subheader(f"3. 系統図 ({building_type})")
    diagram_title = st.text_input("図面タイトル", "給水配管系統図")

    with st.expander("📊 パラメータ一括編集 (全体)", expanded=False):
        df_source = []
        for p in st.session_state["pipes"]:
            calc_res = node_map.get(p["id"])
            vel_val = calc_res.velocity if calc_res else 0.0
            loss_val = calc_res.head_loss if calc_res else 0.0
            df_source.append({
                "id": p["id"], "名称": p["name"], "種別": p["type"],
                "管長 (m)": p.get("length", 2.0),
                "局所損失加算(m)": p.get("equivalent_length", 0.0),
                "実揚程 (m)": p.get("static_head", 0.0) if p["type"] in ["system", "fixture"] else 0.0,
                "末端必要圧 (MPa)": p.get("required_pressure", 0.0) if p["type"] in ["system", "fixture"] else 0.0,
                "口径固定": p.get("manual_size") if p.get("manual_size") else "自動計算",
                "流量固定モード": p.get("is_fixed_flow", False),
                "固定流量 (L/min)": p.get("fixed_flow_val", 0.0),
                "流速 (m/s)": round(vel_val, 2), "損失 (m)": round(loss_val, 3)   
            })
        df_editor = pd.DataFrame(df_source)
        size_list = ["自動計算"] + [d["サイズ"] for d in PIPE_DATABASES[selected_pipe_type]]
        column_config = {
            "id": st.column_config.TextColumn("ID", disabled=True),
            "名称": st.column_config.TextColumn("名称", required=True),
            "種別": st.column_config.TextColumn("種別", disabled=True),
            "管長 (m)": st.column_config.NumberColumn("管長 (m)", min_value=0.0, step=0.1, format="%.1f"),
            "局所損失加算(m)": st.column_config.NumberColumn("局所損失+(m)", min_value=0.0, step=0.1, format="%.1f"),
            "実揚程 (m)": st.column_config.NumberColumn("実揚程 (m)", step=0.1, format="%.1f", help="末端のみ有効"),
            "末端必要圧 (MPa)": st.column_config.NumberColumn("必要圧(MPa)", step=0.01, format="%.2f", help="末端のみ有効"),
            "口径固定": st.column_config.SelectboxColumn("口径固定", options=size_list, required=True),
            "流量固定モード": st.column_config.CheckboxColumn("流量固定", help="チェックすると固定流量が採用されます"),
            "固定流量 (L/min)": st.column_config.NumberColumn("固定流量 (L/min)", min_value=0.0, step=1.0),
            "流速 (m/s)": st.column_config.NumberColumn("流速 (m/s)", disabled=True, format="%.2f"),
            "損失 (m)": st.column_config.NumberColumn("損失 (m)", disabled=True, format="%.3f"),
        }
        edited_df = st.data_editor(df_editor, column_config=column_config, hide_index=True, width='stretch', key="batch_editor", disabled=["id", "種別", "流速 (m/s)", "損失 (m)"])
        if st.button("一括変更を適用", type="primary"):
            for index, row in edited_df.iterrows():
                target_id = row["id"]
                pipe_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == target_id), None)
                if pipe_idx is not None:
                    st.session_state["pipes"][pipe_idx]["name"] = row["名称"]
                    st.session_state["pipes"][pipe_idx]["length"] = row["管長 (m)"]
                    st.session_state["pipes"][pipe_idx]["equivalent_length"] = row["局所損失加算(m)"]
                    if st.session_state["pipes"][pipe_idx]["type"] in ["system", "fixture"]:
                         st.session_state["pipes"][pipe_idx]["static_head"] = row["実揚程 (m)"]
                         st.session_state["pipes"][pipe_idx]["required_pressure"] = row["末端必要圧 (MPa)"]
                    ms = row["口径固定"]
                    st.session_state["pipes"][pipe_idx]["manual_size"] = None if ms == "自動計算" else ms
                    st.session_state["pipes"][pipe_idx]["is_fixed_flow"] = row["流量固定モード"]
                    st.session_state["pipes"][pipe_idx]["fixed_flow_val"] = row["固定流量 (L/min)"]
            st.success("パラメータを更新しました！")
            st.rerun()

    critical_path_ids = set()
    total_dynamic_head = 0.0
    if critical_node:
        curr = critical_node
        while curr:
            critical_path_ids.add(curr.id)
            if curr.parent_id and curr.parent_id in node_map: curr = node_map[curr.parent_id]
            else: curr = None
        friction_loss = critical_node.cum_head_loss
        static_head = critical_node.static_head
        req_pressure_head = critical_node.required_pressure * 102.0
        inner_loss = critical_node.critical_inner_loss
        total_dynamic_head = friction_loss + static_head + req_pressure_head + inner_loss
        st.success(f"🚩 最遠ルート (末端: {critical_node.name})")
        if critical_node.is_manual_critical: st.info("※手動指定された末端です")
        res_c1, res_c2, res_c3 = st.columns(3)
        res_c1.metric("① 管摩擦損失", f"{friction_loss:.3f} m")
        res_c2.metric("② 実揚程 (総高低差)", f"{static_head:.1f} m")
        res_c3.metric("③ 必要圧力換算", f"{req_pressure_head:.1f} m", help=f"{critical_node.required_pressure} MPa")
        st.metric("🏆 必要ポンプ全揚程 (①+②+③+器具管損失)", f"{total_dynamic_head:.3f} m", help=f"器具接続管損失: {inner_loss:.3f}m を含みます")
        if current_flow > 0:
            pump_q_lpm = root_node.flow_lpm
            pump_q_m3_min = pump_q_lpm / 1000.0
            p_kw = (0.163 * pump_q_m3_min * total_dynamic_head * 1.1) / 0.55
            st.caption(f"参考: ポンプ概算軸動力 (Q={int(pump_q_lpm)}L/min, H={total_dynamic_head:.1f}m, η=0.55, α=1.1) ≒ {p_kw:.2f} kW")
        total_len = 0.0
        curr = critical_node
        while curr:
            if curr.id != "root": total_len += curr.length
            if curr.parent_id and curr.parent_id in node_map: curr = node_map[curr.parent_id]
            else: curr = None
        st.caption(f"総配管長 (主管): {total_len:.1f} m")

    info_text = f"用途: {building_type} | 基本管種: {selected_pipe_type}"
    if "一般" in building_type: info_text += f" | 大便器: {toilet_type}"
    elif "人数基準" in building_type: info_text += f" | 式: Q=26P^0.36(≦30人), Q=13P^0.56(≧31人)"
    info_text += f" | 許容流速: {max_vel_setting}m/s"
    if critical_node: info_text += f"\n全揚程: {total_dynamic_head:.2f}m (末端圧: {critical_node.required_pressure}MPa含む)"
    full_caption = f"{diagram_title}\n[{info_text}]"
    
    graph = graphviz.Digraph()
    graph.attr(rankdir=rankdir, nodesep='1.0', ranksep='1.5')
    graph.attr('edge', fontsize='11', fontcolor='#D50000', fontname='Meiryo')
    graph.attr('node', fontname='Meiryo')
    graph.attr(label=full_caption, labelloc='t', fontsize='18', fontname='Meiryo')

    def draw_node(n):
        is_sel = (n.id == st.session_state["selected_id"])
        pw = "3.0" if is_sel else "1.0"
        sc = "red" if is_sel else "black"
        tooltip_txt = n.calc_description if n.calc_description else n.name
        if n.id == "root":
            info_txt = f"{int(n.flow_lpm)} L/min"
            if "BL基準" in building_type: info_txt += f"\n(計{n.system_total}戸)"
            elif "人数基準" in building_type: info_txt += f"\n(計{n.person_total}人)"
            elif "一戸建て" in building_type: info_txt += f"\n(器具{n.fixture_total}個)"
            else: info_txt += f"\n({n.total_load}LU)"
            lbl = f"{n.name}\n{info_txt}"
            graph.node(n.id, label=lbl, shape="box", style="filled", fillcolor="#FFF9C4", color=sc, penwidth=pw, tooltip=tooltip_txt)
        elif n.type == "branch":
            info_txt = ""
            if "BL基準" in building_type: info_txt = f"({n.system_total}戸)"
            elif "人数基準" in building_type: info_txt = f"({n.person_total}人)"
            elif "一戸建て" in building_type: info_txt = f"({n.fixture_total}個)"
            else: info_txt = f"({n.total_load} LU)"
            fill = "#E3F2FD"
            lbl = f'''<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0"><TR><TD><B><FONT POINT-SIZE="10">{n.name}</FONT></B></TD></TR><TR><TD><FONT POINT-SIZE="7">{info_txt}</FONT></TD></TR></TABLE>>'''
            graph.node(n.id, label=lbl, shape="circle", style="filled", fillcolor=fill, margin="0.01", width="0.1", height="0.1", color=sc, penwidth=pw, tooltip=tooltip_txt)
        elif n.type == "system":
            fill = "#FFF9C4" if is_sel else "#E8F5E9"
            if "BL基準" in building_type: content_txt = f"<B>{n.dwelling_count} 戸</B>"; bottom_txt = ""
            elif "人数基準" in building_type: content_txt = f"<B>{n.person_count} 人</B>"; bottom_txt = ""
            else:
                items = [f"{k}x{v}" for k,v in n.fixtures.items() if v>0]
                content_txt = "<BR/>".join(items) if items else "(下流へ接続)"
                total_lu_display = n.total_load
                bottom_txt = f"計: {total_lu_display} LU" if "一般" in building_type else ""
            if n.is_manual_critical: content_txt += "<BR/><FONT COLOR='red' POINT-SIZE='10'>[最遠指定]</FONT>"
            if n.required_pressure > 0: bottom_txt += f"<BR/>Req: {n.required_pressure}MPa"
            lbl = f'''<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{fill}"><TR><TD><B>🏠 {n.name}</B></TD></TR><TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{content_txt}</FONT></TD></TR>{"<TR><TD>"+bottom_txt+"</TD></TR>" if bottom_txt else ""}</TABLE>>'''
            graph.node(n.id, label=lbl, shape="plain", tooltip=tooltip_txt)
            is_show_fixtures = False
            if show_fixtures_mode == "すべて": is_show_fixtures = True
            elif show_fixtures_mode == "最遠ルート末端のみ" and critical_node and n.id == critical_node.id: is_show_fixtures = True
            if is_show_fixtures and n.fixtures:
                for f_name, qty in n.fixtures.items():
                    if qty > 0:
                        spec = FIXTURE_SPECS.get(f_name)
                        size_disp = "-"
                        if spec:
                            size_a = spec["size_a"]
                            size_disp = get_display_size(size_a, selected_pipe_type)
                        for i in range(qty):
                            f_node_id = f"{n.id}_fix_{f_name}_{i}"
                            f_label = f"{f_name.split(' ')[0]}"
                            graph.node(f_node_id, label=f_label, shape="oval", style="filled", fillcolor="white", fontsize="8", width="0.5", height="0.3")
                            edge_lbl = f"{size_disp}\n{n.inner_pipe_length}m"
                            graph.edge(n.id, f_node_id, label=edge_lbl, fontsize="8", color="gray", arrowhead="dot")
        elif n.type == "fixture":
            fill = "#FFF9C4" if is_sel else "#F3E5F5"
            lbl = f'''<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{fill}"><TR><TD><B>🚰 {n.name}</B></TD></TR><TR><TD><FONT POINT-SIZE="9">{n.fixture_type if n.fixture_type else "未設定"}</FONT></TD></TR><TR><TD><FONT POINT-SIZE="8">{n.load_units} LU</FONT></TD></TR></TABLE>>'''
            graph.node(n.id, label=lbl, shape="plain", tooltip=tooltip_txt)

        for child in n.children:
            manual_mark = "🔒" if child.is_manual else ""
            pipe_info = child.size
            if child.specific_pipe_type: pipe_info += f" ({child.specific_pipe_type})"
            edge_label = f"{manual_mark}{pipe_info}\n{int(child.flow_lpm)} L/min"
            if show_pipe_length: edge_label += f"\nL={child.length}m"
            if show_velocity: edge_label += f"\n({child.velocity} m/s)"
            if show_head_loss: edge_label += f"\nΔh={child.head_loss}m"
            if show_calc_formula and child.calc_description: edge_label += f"\n[{child.calc_description}]"
            style = "solid"
            color = "black"
            penwidth = "1.0"
            fontcolor = "black"
            if color_mode == "管種別":
                p_type = child.used_pipe_type
                if "SGP" in p_type: color = PIPE_COLORS["SGP"]
                elif "HIVP" in p_type: color = PIPE_COLORS["HIVP"]
                elif "VP" in p_type: color = PIPE_COLORS["VP"]
                elif "SU" in p_type: color = PIPE_COLORS["SU"]
                elif "PE" in p_type: color = PIPE_COLORS["PE"]
                fontcolor = color
            elif color_mode == "流速別":
                vel = child.velocity
                if vel >= max_vel_setting: color = "#D32F2F"
                elif vel >= max_vel_setting * 0.7: color = "#F57C00"
                else: color = "#1976D2"
                fontcolor = color
            if n.id in critical_path_ids and child.id in critical_path_ids:
                color = "red"
                penwidth = "3.0"
            if child.size == "規格外" and not "SU" in str(child.used_pipe_type):
                color = "red"; style = "dashed"; penwidth="1.0"
            elif child.size == "規格外(過大)":
                color = "red"; style = "dashed"; penwidth="1.0"
            graph.edge(n.id, child.id, label=edge_label, color=color, fontcolor=fontcolor, style=style, penwidth=penwidth)
            draw_node(child)

    if root_node:
        draw_node(root_node)
        try:
            st.graphviz_chart(graph)
        except Exception as e:
            st.error(f"描画エラー: {e}")
            st.warning("Graphvizがインストールされていない可能性があります。")
        
        if "一般" in building_type:
            # === 無料版制限: 流量線図 ===
            st.markdown("---")
            st.markdown("##### 📉 流量線図 (Pro版)")
            if st.session_state["is_pro"]:
                g_col1, g_col2 = st.columns([0.4, 0.6])
                with g_col1:
                    if st.button("📉 流量線図を作成・更新", width="stretch"):
                        img_buf = get_flow_curve_image(current_load, current_flow, is_fv)
                        st.session_state["chart_image"] = img_buf
                    if "chart_image" in st.session_state:
                        if st.button("× 線図を閉じる", width="stretch"): del st.session_state["chart_image"]; st.rerun()
                with g_col2:
                    if "chart_image" in st.session_state:
                        st.image(st.session_state["chart_image"], caption="流量線図 (図3.3.1)", width="stretch")
                        st.download_button(label="💾 グラフ画像を保存", data=st.session_state["chart_image"].getvalue(), file_name="flow_chart.png", mime="image/png", key="graph_download")
            else:
                 st.warning("🔒 流量線図機能は Pro版 限定です")
                 st.button("📉 流量線図を作成 (Pro)", disabled=True)

        st.markdown("---")
        
        # === 無料版制限: Excel/PDF出力 ===
        if st.session_state["is_pro"]:
            # Pro版: ボタン表示
            excel_bytes = None
            if "excel_bytes" not in st.session_state: st.session_state["excel_bytes"] = None
            exp_col1, exp_col2 = st.columns(2)
            with exp_col1:
                if st.button("📊 Excelデータを作成・更新", width="stretch"):
                    if root_node:
                        try:
                            excel_data = root_node.get_excel_data()
                            df_all = pd.DataFrame(excel_data)
                            crit_data_list = []
                            if critical_node:
                                path_nodes = []
                                curr = critical_node
                                while curr:
                                    path_nodes.append(curr)
                                    if curr.parent_id and curr.parent_id in node_map: curr = node_map[curr.parent_id]
                                    else: curr = None
                                path_nodes.reverse()
                                for p in path_nodes:
                                    if p.id == "root": continue
                                    c_val = p.loss_params_used.get("C", "")
                                    fit_val = p.loss_params_used.get("fitting", "")
                                    row = {
                                        "区間": f"{p.parent_name} -> {p.name}", "流量 (L/min)": round(p.flow_lpm, 1),
                                        "管種": p.used_pipe_type, "口径": p.size,
                                        "流速 (m/s)": p.velocity, "流速係数": c_val, "継手割増": fit_val,
                                        "管長 (m)": p.length, "加算等価長 (m)": p.equivalent_length,
                                        "単独損失 (m)": p.head_loss, "累計損失 (m)": round(p.cum_head_loss, 3),
                                        "器具接続損失(m)": round(p.critical_inner_loss, 3) if p.type=="system" else 0
                                    }
                                    crit_data_list.append(row)
                            df_crit = pd.DataFrame(crit_data_list)
                            with io.BytesIO() as buffer:
                                with pd.ExcelWriter(buffer) as writer: 
                                    df_all.to_excel(writer, index=False, sheet_name="全区間一覧")
                                    if not df_crit.empty: df_crit.to_excel(writer, index=False, sheet_name="最遠ルート計算書")
                                st.session_state["excel_bytes"] = buffer.getvalue()
                        except Exception as e: st.error(f"Excel作成エラー: {e}")
                if st.session_state["excel_bytes"]:
                    st.download_button("💾 Excel計算書をダウンロード", st.session_state["excel_bytes"], "water_calc.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_download", width="stretch")
            
            if "pdf_bytes" not in st.session_state: st.session_state["pdf_bytes"] = None
            with exp_col2:
                if st.button("📄 PDF図面を作成・更新", width="stretch", key="btn_create_pdf"):
                    try:
                        pdf_bytes = graph.pipe(format='pdf')
                        st.session_state["pdf_bytes"] = pdf_bytes
                    except Exception as e: st.error(f"PDF作成エラー: {e}")
                if st.session_state["pdf_bytes"]:
                    st.download_button("💾 系統図PDFを保存", st.session_state["pdf_bytes"], "diagram.pdf", "application/pdf", key="pdf_download", width="stretch")
        else:
            # 無料版: ロック表示
            st.warning("🔒 Excel出力・PDF出力機能は Pro版 限定です")
            st.caption("制限を解除するにはサイドバーからPro版を有効化してください。")
            d_col1, d_col2 = st.columns(2)
            with d_col1: st.button("📊 Excel作成 (Pro)", disabled=True)
            with d_col2: st.button("📄 PDF作成 (Pro)", disabled=True)