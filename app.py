# app.py
import streamlit as st
import graphviz
import pandas as pd
import json
import io

# 自作モジュールのインポート
from constants import (
    FIXTURE_SPECS, FIXTURE_DATA, PRESETS, PIPE_DATABASES, PIPE_COLORS,
    DEFAULT_PUBLIC_LIST, DEFAULT_PRIVATE_LIST
)
from utils import (
    setup_environment, setup_fonts, get_display_size, get_flow_curve_image
)
from models import PipeSection
from callbacks import (
    add_node, insert_node_before, renumber_nodes,
    delete_current_node, delete_specific_node, reset_all, set_parent
)

# --- 0. 環境設定 ---
setup_fonts()
setup_environment(__file__)

# --- UI設定 ---
st.set_page_config(layout="wide", page_title="給水管計算ツール Final v67")

# Session State 初期化
if "pipes" not in st.session_state:
    reset_all() # 初期化
if "branch_counter" not in st.session_state: st.session_state["branch_counter"] = 0
if "system_counter" not in st.session_state: st.session_state["system_counter"] = 0
if "selected_id" not in st.session_state: st.session_state["selected_id"] = "root"
if "input_mode" not in st.session_state: st.session_state["input_mode"] = "public"
if "custom_presets" not in st.session_state: st.session_state["custom_presets"] = PRESETS.copy()
if "is_pro" not in st.session_state: st.session_state["is_pro"] = False
if "fixture_specs" not in st.session_state:
    st.session_state["fixture_specs"] = FIXTURE_SPECS.copy()

# --- サイドバー UI ---
with st.sidebar:
    # 🔓 ライセンス認証エリア
    with st.expander("🔓 ライセンス"):
        if st.session_state["is_pro"]:
            st.success("💎 Pro版 (制限解除済)")
            if st.button("ログアウト"):
                st.session_state["is_pro"] = False
                st.rerun()
        else:
            st.info("現在は「無料版」です")
            st.link_button("Pro版を購入 (¥500/月)", "https://buy.stripe.com/test_5kQ6oA7Zc07pbEKdpU5Ne00")
            input_pass = st.text_input("パスワード", type="password", key="pro_pass_input")
            if st.button("有効化"):
                CORRECT_PASSWORD = st.secrets.get("APP_PASSWORD", "password") 
                if input_pass == CORRECT_PASSWORD:
                    st.session_state["is_pro"] = True
                    st.balloons()
                    st.rerun()
                else:
                    st.error("パスワード不一致")
    
    # 🔧 器具データ編集
    with st.expander("🛠 器具データ編集"):
        specs_list = []
        for name, data in st.session_state["fixture_specs"].items():
            type_label = "公" if "(公)" in name else ("私" if "(私)" in name else "その他")
            clean_name = name.replace(" (公)", "").replace(" (私)", "")
            specs_list.append({
                "名称": clean_name, "区分": type_label,
                "負荷(LU)": data["lu"], "口径(A)": data["size_a"]
            })
        df_specs = pd.DataFrame(specs_list)
        edited_df = st.data_editor(
            df_specs,
            column_config={
                "名称": st.column_config.TextColumn("名称", required=True),
                "区分": st.column_config.SelectboxColumn("区分", options=["公", "私", "その他"], required=True),
                "負荷(LU)": st.column_config.NumberColumn("負荷", min_value=0.0, step=0.1, required=True),
                "口径(A)": st.column_config.NumberColumn("口径", min_value=10, step=5, required=True),
            },
            num_rows="dynamic", key="fixture_editor", width="stretch"
        )
        if st.button("器具データを更新"):
            new_specs = {}
            for index, row in edited_df.iterrows():
                suffix = f" ({row['区分']})" if row['区分'] in ["公", "私"] else ""
                new_key = f"{row['名称']}{suffix}"
                new_specs[new_key] = {"lu": float(row["負荷(LU)"]), "size_a": int(row["口径(A)"])}
            st.session_state["fixture_specs"] = new_specs
            st.success("更新しました"); st.rerun()
        if st.button("デフォルトに戻す"):
            st.session_state["fixture_specs"] = FIXTURE_SPECS.copy(); st.rerun()

    # ファイル操作
    col_dl, col_ul = st.columns([1, 1.5])
    with col_dl:
        save_data = {"version": 2, "pipes": st.session_state["pipes"], "fixture_specs": st.session_state["fixture_specs"]}
        current_json = json.dumps(save_data, ensure_ascii=False, indent=2)
        st.download_button("💾 保存", current_json, "pipe_config.json", "application/json", key="json_download", help="構成をJSON保存")
    with col_ul:
        uploaded_file = st.file_uploader("構成読込", type=["json"], label_visibility="collapsed", help="構成を読込")
    
    if uploaded_file is not None:
        try:
            loaded_raw = json.load(uploaded_file)
            if isinstance(loaded_raw, dict) and "pipes" in loaded_raw:
                st.session_state["pipes"] = loaded_raw["pipes"]
                st.session_state["fixture_specs"] = loaded_raw.get("fixture_specs", FIXTURE_SPECS.copy())
            else:
                st.session_state["pipes"] = loaded_raw
                st.session_state["fixture_specs"] = FIXTURE_SPECS.copy()
            max_b, max_s = 0, 0
            for p in st.session_state["pipes"]:
                try:
                    num = int(p["id"].split("_")[-1])
                    if p["type"] == "branch" and num > max_b: max_b = num
                    if p["type"] == "system" and num > max_s: max_s = num
                except: pass
            st.session_state["branch_counter"] = max_b + 1
            st.session_state["system_counter"] = max_s + 1
            st.session_state["selected_id"] = "root"
            st.success("読込完了"); st.rerun()
        except: st.error("読込エラー")

    # 設計条件
    building_type = st.selectbox("建物用途", ["一般・事務所 (負荷単位法)", "集合住宅 (BL基準)", "集合住宅 (人数基準)", "一戸建て (総水栓数法)"], key="building_type_selection")
    person_calc_params = {}
    is_fv = False
    
    if "一般" in building_type:
        toilet_type = st.radio("大便器", ["ロータンク式", "洗浄弁式"])
        is_fv = (toilet_type == "洗浄弁式")
    elif "人数基準" in building_type:
        col1, col2 = st.columns(2)
        c1 = col1.number_input("C1", value=26.0, step=0.1, format="%.1f")
        k1 = col2.number_input("k1", value=0.36, step=0.01, format="%.2f")
        col3, col4 = st.columns(2)
        c2 = col3.number_input("C2", value=13.0, step=0.1, format="%.1f")
        k2 = col4.number_input("k2", value=0.56, step=0.01, format="%.2f")
        person_calc_params = {"C1": c1, "k1": k1, "C2": c2, "k2": k2}
    else:
        toilet_type = st.radio("大便器(参考)", ["ロータンク式", "洗浄弁式"])
        is_fv = (toilet_type == "洗浄弁式")

    selected_pipe_type = st.selectbox("基本管種", list(PIPE_DATABASES.keys()))
    
    col_g1, col_g2 = st.columns(2)
    with col_g1: graph_direction = st.radio("向き", ["横(LR)", "縦(TB)", "縦(BT)"], horizontal=True, label_visibility="collapsed")
    with col_g2: color_mode = st.selectbox("色分け", ["なし", "管種別", "流速別"], index=0, label_visibility="collapsed")
    rankdir = "LR" if "LR" in graph_direction else ("TB" if "TB" in graph_direction else "BT")
    show_fixtures_mode = st.radio("器具表示", ["なし", "すべて", "最遠のみ"], horizontal=True)

    col_chk1, col_chk2 = st.columns(2)
    with col_chk1:
        show_pipe_length = st.checkbox("管長", value=False)
        show_velocity = st.checkbox("流速", value=False)
    with col_chk2:
        show_head_loss = st.checkbox("損失", value=False)
        show_calc_formula = st.checkbox("計算式", value=False)
    max_vel_setting = st.number_input("許容流速 (m/s)", value=2.0, step=0.1, format="%.1f")
    
    with st.expander("🌊 摩擦損失設定"):
        c_val_setting = st.number_input("C値", value=130.0, step=1.0)
        fitting_ratio = st.number_input("継手割増", value=1.2, step=0.1, format="%.1f")
        loss_params = {"C": c_val_setting, "fitting": fitting_ratio}

# --- メインエリア ---
col_ctrl, col_edit, col_view = st.columns([0.7, 1.3, 2.5], gap="small")

with col_ctrl:
    st.subheader("1. 構成")
    current_parent = next((p for p in st.session_state["pipes"] if p["id"] == st.session_state["selected_id"]), None)
    if current_parent:
        icon = '🔵' if current_parent['type'] == 'branch' else ('🚰' if current_parent['type'] == 'fixture' else '🏠')
        st.success(f"接続先: **{icon} {current_parent['name']}**")
    else:
        st.session_state["selected_id"] = "root"
        st.warning("接続先を選択")

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        branches = [p for p in st.session_state["pipes"] if p["type"] == "branch"]
        for p in branches:
            btn_type = "primary" if p["id"] == st.session_state["selected_id"] else "secondary"
            if st.button(f"{p['name']}", key=f"sel_{p['id']}", type=btn_type, width="stretch"):
                set_parent(p["id"]); st.rerun()
    with sel_col2:
        systems = [p for p in st.session_state["pipes"] if p["type"] == "system"]
        for p in systems:
            btn_type = "primary" if p["id"] == st.session_state["selected_id"] else "secondary"
            if st.button(f"{p['name']}", key=f"sel_{p['id']}", type=btn_type, width="stretch"):
                set_parent(p["id"]); st.rerun()

    st.write("▼ 追加")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.button("＋分岐", width="stretch", on_click=add_node, args=("branch",))
        if st.session_state["selected_id"] != "root":
            st.button("＋挿入", width="stretch", on_click=insert_node_before)
    with btn_col2:
        st.button("＋系統", width="stretch", on_click=add_node, args=("system",))
        st.button("＋器具", width="stretch", on_click=add_node, args=("fixture",))
    
    with st.expander("⚡ プリセット"):
        for pname, pdata in st.session_state["custom_presets"].items():
            pass_data = pdata.copy(); pass_data["name"] = pname
            if st.button(f"＋ {pname}", width="stretch"):
                add_node("system", pass_data); st.rerun()

    st.markdown("")
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1: st.button("番号修正", on_click=renumber_nodes, width="stretch")
    with c_btn2: st.button("リセット", on_click=reset_all, width="stretch")

# --- 計算 ---
custom_fixture_data = {k: v["lu"] for k, v in st.session_state["fixture_specs"].items()}
current_public_list = sorted([k.replace(" (公)", "") for k in st.session_state["fixture_specs"].keys() if "(公)" in k])
current_private_list = sorted([k.replace(" (私)", "") for k in st.session_state["fixture_specs"].keys() if "(私)" in k])

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
    root_node.calculate(PIPE_DATABASES, selected_pipe_type, max_vel_setting, building_type, is_fv, person_calc_params, loss_params, fixture_specs=st.session_state["fixture_specs"])
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
        tab_settings, tab_connection = st.tabs(["⚙️ 設定", "🔗 接続"])
        
        with tab_settings:
            # 1. 基本
            def update_name(): st.session_state["pipes"][current_idx]["name"] = st.session_state[f"name_{current_data['id']}"]
            st.text_input("名称", value=current_data["name"], key=f"name_{current_data['id']}", on_change=update_name)

            # D. 器具リスト (Systemのみ) - 統合のため名称の真下に移動
            if current_data["type"] == "system" and "一般" in building_type:
                st.caption("▼ 簡易器具リスト")
                if "input_mode_sys" not in st.session_state: st.session_state["input_mode_sys"] = "public"
                mode_col1, mode_col2 = st.columns(2)
                if mode_col1.button("公共", type="primary" if st.session_state["input_mode_sys"]=="public" else "secondary", width="stretch", key="smode_pub"):
                    st.session_state["input_mode_sys"] = "public"; st.rerun()
                if mode_col2.button("個人", type="primary" if st.session_state["input_mode_sys"]=="private" else "secondary", width="stretch", key="smode_priv"):
                    st.session_state["input_mode_sys"] = "private"; st.rerun()
                
                src_list = current_public_list if st.session_state["input_mode_sys"] == "public" else current_private_list
                suffix = "(公)" if st.session_state["input_mode_sys"] == "public" else "(私)"
                
                fix_cols = st.columns(2, gap="small")
                for i, fname in enumerate(src_list):
                    save_key = f"{fname} {suffix}"
                    target_col = fix_cols[i % 2]
                    with target_col:
                        def update_fix(f_key=save_key, ui_key=f"f_{current_data['id']}_{save_key}"):
                            st.session_state["pipes"][current_idx]["fixtures"][f_key] = st.session_state[ui_key]
                        
                        # 修正: 名称を入力欄の上（ラベル）として表示し、入力欄の幅を確保して+-ボタンを表示させる
                        st.number_input(
                            label=fname, 
                            min_value=0, step=1, 
                            value=current_data["fixtures"].get(save_key, 0), 
                            key=f"f_{current_data['id']}_{save_key}", 
                            on_change=update_fix
                            # label_visibility="visible" # デフォルト
                        )

            if current_data["id"] == "root":
                st.info("🏭 起点（ポンプ）")
            elif current_data["type"] == "fixture":
                st.info("🚰 器具（終端）")
                if "input_mode" not in st.session_state: st.session_state["input_mode"] = "public"
                mode_col1, mode_col2 = st.columns(2)
                if mode_col1.button("公共用", type="primary" if st.session_state["input_mode"]=="public" else "secondary", width="stretch", key="fmode_pub"):
                    st.session_state["input_mode"] = "public"; st.rerun()
                if mode_col2.button("個人用", type="primary" if st.session_state["input_mode"]=="private" else "secondary", width="stretch", key="fmode_priv"):
                    st.session_state["input_mode"] = "private"; st.rerun()
                
                f_list = current_public_list if st.session_state["input_mode"] == "public" else current_private_list
                suffix = "(公)" if st.session_state["input_mode"] == "public" else "(私)"
                full_list = [f"{f} {suffix}" for f in f_list]
                
                curr_ft = current_data.get("fixture_type")
                idx_ft = 0 
                if curr_ft in full_list: idx_ft = full_list.index(curr_ft)
                
                def update_fixture_type(): st.session_state["pipes"][current_idx]["fixture_type"] = st.session_state[f"ftype_{current_data['id']}"]
                st.selectbox("器具種類", options=full_list, index=idx_ft, key=f"ftype_{current_data['id']}", on_change=update_fixture_type)
                
                if curr_ft and curr_ft in st.session_state["fixture_specs"]:
                    spec = st.session_state["fixture_specs"][curr_ft]
                    st.caption(f"負荷: {spec['lu']} LU | 口径: {spec['size_a']}A")
                    if st.button("標準口径を適用", width="stretch"):
                        size_disp = get_display_size(spec["size_a"], selected_pipe_type)
                        current_pipe_db = PIPE_DATABASES[selected_pipe_type]
                        size_options = [d["サイズ"] for d in current_pipe_db]
                        if size_disp in size_options:
                            st.session_state["pipes"][current_idx]["manual_size"] = size_disp
                            st.success(f"{size_disp} 適用"); st.rerun()
                        else: st.warning("規格外")

            # --- 統合設定エリア ---
            st.markdown("---") # 唯一の区切り線

            # A. 最遠ルート指定 (末端のみ)
            if current_data["type"] in ["system", "fixture"]:
                is_crit = st.checkbox("最遠ルート指定", value=current_data.get("is_manual_critical", False), key=f"crit_{current_data['id']}")
                if is_crit != current_data.get("is_manual_critical", False):
                    if is_crit:
                        for p in st.session_state["pipes"]: p["is_manual_critical"] = False
                    st.session_state["pipes"][current_idx]["is_manual_critical"] = is_crit
                    st.rerun()

            # B. 配管設定 (Root以外)
            if current_data["id"] != "root":
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    def update_length(): st.session_state["pipes"][current_idx]["length"] = st.session_state[f"len_{current_data['id']}"]
                    st.number_input("管長 (m)", min_value=0.0, step=0.1, value=current_data.get("length", 2.0), key=f"len_{current_data['id']}", on_change=update_length)
                with col_p2:
                    def update_eq_len(): st.session_state["pipes"][current_idx]["equivalent_length"] = st.session_state[f"eq_len_{current_data['id']}"]
                    st.number_input("局所損失+(m)", min_value=0.0, step=0.1, value=current_data.get("equivalent_length", 0.0), key=f"eq_len_{current_data['id']}", on_change=update_eq_len)

                col_p3, col_p4 = st.columns(2)
                with col_p3:
                    pipe_opts = ["(基本)"] + list(PIPE_DATABASES.keys())
                    curr_spec = current_data.get("specific_pipe_type")
                    idx_spec = 0 if curr_spec not in PIPE_DATABASES else pipe_opts.index(curr_spec)
                    def update_specific_pipe():
                        val = st.session_state[f"spec_pipe_{current_data['id']}"]
                        st.session_state["pipes"][current_idx]["specific_pipe_type"] = None if val == "(基本)" else val
                    st.selectbox("管種指定", options=pipe_opts, index=idx_spec, key=f"spec_pipe_{current_data['id']}", on_change=update_specific_pipe)
                with col_p4:
                    current_pipe_db = PIPE_DATABASES[selected_pipe_type]
                    if curr_spec and curr_spec in PIPE_DATABASES: current_pipe_db = PIPE_DATABASES[curr_spec]
                    size_options = ["自動計算"] + [d["サイズ"] for d in current_pipe_db]
                    current_manual = current_data.get("manual_size")
                    if current_manual not in size_options: current_manual = "自動計算"
                    def update_manual_size():
                        new_val = st.session_state[f"manual_{current_data['id']}"]
                        st.session_state["pipes"][current_idx]["manual_size"] = None if new_val == "自動計算" else new_val
                    st.selectbox("口径固定", options=size_options, index=size_options.index(current_manual), key=f"manual_{current_data['id']}", on_change=update_manual_size)

            # C. 流量・負荷 (Fixture以外)
            if current_data["type"] != "fixture":
                col_f1, col_f2 = st.columns([0.4, 0.6])
                with col_f1:
                    is_fixed = st.checkbox("流量固定", value=current_data.get("is_fixed_flow", False), key=f"is_fixed_{current_data['id']}")
                    def update_fixed_flow_flag(): st.session_state["pipes"][current_idx]["is_fixed_flow"] = st.session_state[f"is_fixed_{current_data['id']}"]
                    if is_fixed != current_data.get("is_fixed_flow", False):
                        st.session_state["pipes"][current_idx]["is_fixed_flow"] = is_fixed; st.rerun()
                with col_f2:
                    if is_fixed:
                        def update_fixed_val(): st.session_state["pipes"][current_idx]["fixed_flow_val"] = st.session_state[f"fixed_val_{current_data['id']}"]
                        st.number_input("設定流量 (L/min)", min_value=0.0, step=1.0, value=current_data.get("fixed_flow_val", 0.0), key=f"fixed_val_{current_data['id']}", on_change=update_fixed_val, label_visibility="collapsed")
                
                if current_data["type"] == "system":
                    if "BL基準" in building_type:
                        def update_dw(): st.session_state["pipes"][current_idx]["dwelling_count"] = st.session_state[f"dw_{current_data['id']}"]
                        st.number_input("担当戸数", min_value=1, value=current_data.get("dwelling_count", 1), step=1, key=f"dw_{current_data['id']}", on_change=update_dw)
                    elif "人数基準" in building_type:
                        def update_pc(): st.session_state["pipes"][current_idx]["person_count"] = st.session_state[f"pc_{current_data['id']}"]
                        st.number_input("居住人数", min_value=1, value=current_data.get("person_count", 1), step=1, key=f"pc_{current_data['id']}", on_change=update_pc)

        with tab_connection:
            st.markdown(f"**{current_data['name']} の配下**")
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
                        "管長(m)": child.get("length", 2.0),
                        "器具": child.get("fixture_type", "") if child["type"]=="fixture" else "",
                        "口径": child.get("manual_size") if child.get("manual_size") else "自動",
                        "流速": round(vel_val, 2), "損失": round(loss_val, 3)
                    })
                df_children = pd.DataFrame(edit_data_list)
                # カスタムリスト対応
                all_fixtures_list = [""] + [f"{f} (公)" for f in current_public_list] + [f"{f} (私)" for f in current_private_list]
                
                size_list = ["自動計算"] + [d["サイズ"] for d in PIPE_DATABASES[selected_pipe_type]]
                child_config = {
                    "id": st.column_config.TextColumn("ID", disabled=True),
                    "名称": st.column_config.TextColumn("名称", required=True),
                    "種別": st.column_config.TextColumn("種別", disabled=True),
                    "管長(m)": st.column_config.NumberColumn("管長(m)", min_value=0.0, step=0.1, format="%.1f"),
                    "器具": st.column_config.SelectboxColumn("器具", options=all_fixtures_list, required=False),
                    "口径": st.column_config.SelectboxColumn("口径", options=size_list, required=True),
                    "流速": st.column_config.NumberColumn("流速", disabled=True, format="%.2f"),
                    "損失": st.column_config.NumberColumn("損失", disabled=True, format="%.3f"),
                }
                edited_children = st.data_editor(df_children, column_config=child_config, hide_index=True, width='stretch', key="children_editor", disabled=["id", "種別", "流速", "損失"])
                cols_to_check = ["id", "名称", "管長(m)", "器具", "口径"]
                if not df_children[cols_to_check].equals(edited_children[cols_to_check]):
                    for index, row in edited_children.iterrows():
                        t_id = row["id"]
                        t_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == t_id), None)
                        if t_idx is not None:
                            st.session_state["pipes"][t_idx]["name"] = row["名称"]
                            st.session_state["pipes"][t_idx]["length"] = row["管長(m)"]
                            st.session_state["pipes"][t_idx]["fixture_type"] = row["器具"] if row["器具"] else None
                            ms = row["口径"]
                            st.session_state["pipes"][t_idx]["manual_size"] = None if ms == "自動" else ms
                    st.rerun()

                st.markdown("")
                for child_idx in children_indices:
                    child = st.session_state["pipes"][child_idx]
                    c_col1, c_col2, c_col3 = st.columns([0.6, 0.2, 0.2])
                    c_icon = "🔵" if child["type"]=="branch" else ("🚰" if child["type"]=="fixture" else "🏠")
                    c_col1.write(f"{c_icon} {child['name']}")
                    if c_col2.button("選択", key=f"sel_c_{child['id']}", width="stretch"):
                        set_parent(child["id"]); st.rerun()
                    if c_col3.button("削除", key=f"del_c_{child['id']}", type="primary", width="stretch"):
                        delete_specific_node(child["id"]); st.rerun()
            else: st.caption("配下ノードなし")
            
            st.markdown("")
            st.caption("配下に追加")
            add_c1, add_c2, add_c3 = st.columns(3)
            if add_c1.button("＋分岐", key="add_br_here", on_click=add_node, args=("branch",)): pass
            if add_c2.button("＋系統", key="add_sys_here", on_click=add_node, args=("system",)): pass
            if add_c3.button("＋器具", key="add_fix_here", on_click=add_node, args=("fixture",)): pass

        st.markdown("---")
        if current_data["type"] != "root":
            st.button("このノードを削除", key="del_node_main", on_click=delete_current_node, type="primary", width="stretch")
    
    if sel_node:
        st.markdown("---")
        st.caption(f"根拠: {sel_node.calc_description}" if sel_node.calc_description else "計算情報なし")

with col_view:
    st.subheader(f"3. 系統図 ({building_type})")
    diagram_title = st.text_input("図面タイトル", "給水配管系統図")

    info_text = f"用途: {building_type} | 管種: {selected_pipe_type}"
    if "一般" in building_type: info_text += f" | 大便器: {toilet_type}"
    elif "人数基準" in building_type: info_text += f" | 式: Q=26P^0.36(≦30人), Q=13P^0.56(≧31人)"
    info_text += f" | 許容流速: {max_vel_setting}m/s"
    
    total_dynamic_head_val = 0.0
    critical_path_ids = set()
    if critical_node:
        curr = critical_node
        while curr:
            critical_path_ids.add(curr.id)
            if curr.parent_id and curr.parent_id in node_map: curr = node_map[curr.parent_id]
            else: curr = None
        friction_loss = critical_node.cum_head_loss
        static_head = critical_node.static_head
        # 修正: required_pressureはm単位として扱うため、102倍しない
        req_pressure_head = critical_node.required_pressure
        inner_loss = critical_node.critical_inner_loss
        total_dynamic_head_val = friction_loss + static_head + req_pressure_head + inner_loss
        info_text += f"\n全揚程: {total_dynamic_head_val:.2f}m (末端圧: {critical_node.required_pressure}m含む)"
    
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
            if n.required_pressure > 0: bottom_txt += f"<BR/>Req: {n.required_pressure}m"
            lbl = f'''<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{fill}"><TR><TD><B>🏠 {n.name}</B></TD></TR><TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{content_txt}</FONT></TD></TR>{"<TR><TD>"+bottom_txt+"</TD></TR>" if bottom_txt else ""}</TABLE>>'''
            graph.node(n.id, label=lbl, shape="plain", tooltip=tooltip_txt)
            is_show_fixtures = False
            if show_fixtures_mode == "すべて": is_show_fixtures = True
            elif show_fixtures_mode == "最遠ルート末端のみ" and critical_node and n.id == critical_node.id: is_show_fixtures = True
            if is_show_fixtures and n.fixtures:
                for f_name, qty in n.fixtures.items():
                    if qty > 0:
                        spec = st.session_state["fixture_specs"].get(f_name)
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
    
    # --- 計算結果・パラメータ編集 ---
    if critical_node:
        st.success(f"🚩 最遠ルート (末端: {critical_node.name})")
        if critical_node.is_manual_critical: st.info("※手動指定末端")
        
        target_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == critical_node.id), None)
        
        if target_idx is not None:
            res_c1, res_c2, res_c3 = st.columns(3)
            res_c1.metric("① 管摩擦損失", f"{friction_loss:.3f} m")
            
            def update_crit_head(): st.session_state["pipes"][target_idx]["static_head"] = st.session_state[f"crit_shead_{critical_node.id}"]
            res_c2.number_input("② 実揚程 (m)", value=critical_node.static_head, step=0.1, key=f"crit_shead_{critical_node.id}", on_change=update_crit_head)
            
            # 単位を m に変更
            def update_crit_press(): st.session_state["pipes"][target_idx]["required_pressure"] = st.session_state[f"crit_reqp_{critical_node.id}"]
            res_c3.number_input("③ 必要圧 (m)", value=critical_node.required_pressure, step=0.1, format="%.1f", key=f"crit_reqp_{critical_node.id}", on_change=update_crit_press)

        st.metric("🏆 必要ポンプ全揚程", f"{total_dynamic_head_val:.3f} m", help=f"器具接続管損失: {inner_loss:.3f}m 込")
        
        if current_flow > 0:
            pump_q_lpm = root_node.flow_lpm
            pump_q_m3_min = pump_q_lpm / 1000.0
            p_kw = (0.163 * pump_q_m3_min * total_dynamic_head_val * 1.1) / 0.55
            st.caption(f"参考軸動力: {p_kw:.2f} kW")
        total_len = 0.0
        curr = critical_node
        while curr:
            if curr.id != "root": total_len += curr.length
            if curr.parent_id and curr.parent_id in node_map: curr = node_map[curr.parent_id]
            else: curr = None
        st.caption(f"総配管長 (主管): {total_len:.1f} m")

    with st.expander("📊 パラメータ一括編集", expanded=False):
        df_source = []
        for p in st.session_state["pipes"]:
            calc_res = node_map.get(p["id"])
            vel_val = calc_res.velocity if calc_res else 0.0
            loss_val = calc_res.head_loss if calc_res else 0.0
            df_source.append({
                "id": p["id"], "名称": p["name"], "種別": p["type"],
                "管長": p.get("length", 2.0),
                "局所損失": p.get("equivalent_length", 0.0),
                "実揚程": p.get("static_head", 0.0) if p["type"] in ["system", "fixture"] else 0.0,
                "必要圧(m)": p.get("required_pressure", 0.0) if p["type"] in ["system", "fixture"] else 0.0,
                "口径固定": p.get("manual_size") if p.get("manual_size") else "自動計算",
                "流量固定": p.get("is_fixed_flow", False),
                "固定流量": p.get("fixed_flow_val", 0.0),
                "流速": round(vel_val, 2), "損失": round(loss_val, 3)   
            })
        df_editor = pd.DataFrame(df_source)
        size_list = ["自動計算"] + [d["サイズ"] for d in PIPE_DATABASES[selected_pipe_type]]
        column_config = {
            "id": st.column_config.TextColumn("ID", disabled=True),
            "名称": st.column_config.TextColumn("名称", required=True),
            "種別": st.column_config.TextColumn("種別", disabled=True),
            "管長": st.column_config.NumberColumn("管長(m)", min_value=0.0, step=0.1, format="%.1f"),
            "局所損失": st.column_config.NumberColumn("局所損失+(m)", min_value=0.0, step=0.1, format="%.1f"),
            "実揚程": st.column_config.NumberColumn("実揚程(m)", step=0.1, format="%.1f", help="末端のみ有効"),
            "必要圧(m)": st.column_config.NumberColumn("必要圧(m)", step=0.1, format="%.1f", help="末端のみ有効"),
            "口径固定": st.column_config.SelectboxColumn("口径固定", options=size_list, required=True),
            "流量固定": st.column_config.CheckboxColumn("流量固定", help="チェックすると固定流量が採用されます"),
            "固定流量": st.column_config.NumberColumn("固定流量(L/min)", min_value=0.0, step=1.0),
            "流速": st.column_config.NumberColumn("流速(m/s)", disabled=True, format="%.2f"),
            "損失": st.column_config.NumberColumn("損失(m)", disabled=True, format="%.3f"),
        }
        edited_df = st.data_editor(df_editor, column_config=column_config, hide_index=True, width='stretch', key="batch_editor", disabled=["id", "種別", "流速", "損失"])
        if st.button("一括変更を適用", type="primary"):
            for index, row in edited_df.iterrows():
                target_id = row["id"]
                pipe_idx = next((i for i, p in enumerate(st.session_state["pipes"]) if p["id"] == target_id), None)
                if pipe_idx is not None:
                    st.session_state["pipes"][pipe_idx]["name"] = row["名称"]
                    st.session_state["pipes"][pipe_idx]["length"] = row["管長"]
                    st.session_state["pipes"][pipe_idx]["equivalent_length"] = row["局所損失"]
                    if st.session_state["pipes"][pipe_idx]["type"] in ["system", "fixture"]:
                         st.session_state["pipes"][pipe_idx]["static_head"] = row["実揚程"]
                         st.session_state["pipes"][pipe_idx]["required_pressure"] = row["必要圧(m)"]
                    ms = row["口径固定"]
                    st.session_state["pipes"][pipe_idx]["manual_size"] = None if ms == "自動計算" else ms
                    st.session_state["pipes"][pipe_idx]["is_fixed_flow"] = row["流量固定"]
                    st.session_state["pipes"][pipe_idx]["fixed_flow_val"] = row["固定流量"]
            st.success("更新しました！"); st.rerun()

    if "一般" in building_type:
        st.markdown("---")
        st.markdown("##### 📉 流量線図 (Pro)")
        if st.session_state["is_pro"]:
            g_col1, g_col2 = st.columns([0.4, 0.6])
            with g_col1:
                if st.button("📉 作成・更新", width="stretch"):
                    img_buf = get_flow_curve_image(current_load, current_flow, is_fv)
                    st.session_state["chart_image"] = img_buf
                if "chart_image" in st.session_state:
                    if st.button("× 閉じる", width="stretch"): del st.session_state["chart_image"]; st.rerun()
            with g_col2:
                if "chart_image" in st.session_state:
                    st.image(st.session_state["chart_image"], caption="流量線図", width="stretch")
                    st.download_button(label="💾 画像保存", data=st.session_state["chart_image"].getvalue(), file_name="flow_chart.png", mime="image/png", key="graph_download")
        else:
                st.warning("🔒 Pro版 限定")
                st.button("📉 作成 (Pro)", disabled=True)

    st.markdown("---")
    
    if st.session_state["is_pro"]:
        excel_bytes = None
        if "excel_bytes" not in st.session_state: st.session_state["excel_bytes"] = None
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            if st.button("📊 Excel作成", width="stretch"):
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
                st.download_button("💾 Excel保存", st.session_state["excel_bytes"], "water_calc.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_download", width="stretch")
        
        if "pdf_bytes" not in st.session_state: st.session_state["pdf_bytes"] = None
        with exp_col2:
            if st.button("📄 PDF作成", width="stretch", key="btn_create_pdf"):
                try:
                    pdf_bytes = graph.pipe(format='pdf')
                    st.session_state["pdf_bytes"] = pdf_bytes
                except Exception as e: st.error(f"PDF作成エラー: {e}")
            if st.session_state["pdf_bytes"]:
                st.download_button("💾 PDF保存", st.session_state["pdf_bytes"], "diagram.pdf", "application/pdf", key="pdf_download", width="stretch")
    else:
        st.warning("🔒 Excel/PDF出力は Pro版 限定")
        d_col1, d_col2 = st.columns(2)
        with d_col1: st.button("📊 Excel (Pro)", disabled=True)
        with d_col2: st.button("📄 PDF (Pro)", disabled=True)