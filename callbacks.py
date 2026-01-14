# callbacks.py
import streamlit as st

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
