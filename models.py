# models.py
import math
import pandas as pd
from constants import FIXTURE_SPECS, FIXTURE_DATA, SU_FLOW_CAPACITY
from utils import interpolate_flow, get_display_size

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

    def calculate_self_stats(self, building_type, fixture_specs=None):
        # カスタム器具データがなければデフォルトを使用
        specs = fixture_specs if fixture_specs else FIXTURE_SPECS
        # 負荷単位辞書を生成
        f_data = {k: v["lu"] for k, v in specs.items()}
        
        load = 0.0
        count = 0
        for fname_key, qty in self.fixtures.items():
            if qty > 0:
                count += qty
                if fname_key in f_data:
                    load += qty * f_data[fname_key]
        
        if self.type == "fixture" and self.fixture_type:
            spec = specs.get(self.fixture_type)
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

    def calculate(self, all_pipe_db, default_pipe_type, max_velocity, building_type, is_fv, person_calc_params=None, loss_params=None, fixture_specs=None):
        # 自身の負荷計算にカスタムスペックを渡す
        self.calculate_self_stats(building_type, fixture_specs)
        
        child_load_sum = 0.0
        child_system_sum = 0
        child_person_sum = 0
        child_fixture_sum = 0
        
        for child in self.children:
            # 子ノードにもカスタムスペックを伝播
            c_load, c_sys, c_person, c_fix = child.calculate(
                all_pipe_db, default_pipe_type, max_velocity, building_type, is_fv, person_calc_params, loss_params, fixture_specs
            )
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
        specs = fixture_specs if fixture_specs else FIXTURE_SPECS
        
        if self.type == "system" and self.fixtures:
            max_inner_loss = 0.0
            for f_name, qty in self.fixtures.items():
                if qty <= 0: continue
                spec = specs.get(f_name)
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
            req_head_m = t.required_pressure
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