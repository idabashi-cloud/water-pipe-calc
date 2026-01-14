# utils.py
import os
import sys
import platform
import io
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from constants import FLOW_TABLE_FV, FLOW_TABLE_FT

def setup_environment(file_path):
    """環境設定・パス設定"""
    if getattr(sys, 'frozen', False):
        application_path = sys._MEIPASS
        if platform.system() == "Windows":
            graphviz_path = os.path.join(application_path, "Graphviz", "bin")
            os.environ["PATH"] += os.pathsep + graphviz_path
    else:
        application_path = os.path.dirname(file_path)
        if platform.system() == "Windows":
            local_gv_path = os.path.join(application_path, "Graphviz", "bin")
            if os.path.exists(local_gv_path):
                os.environ["PATH"] += os.pathsep + local_gv_path
    return application_path

def setup_fonts():
    """グラフの日本語フォント設定"""
    # 利用可能なフォント一覧を取得
    available_fonts = set(f.name for f in fm.fontManager.ttflist)

    # 優先順位リスト（iPad/iOS対応のためHiragino系を上位に追加）
    preferred_fonts = [
        'Hiragino Sans',           # macOS / iOS
        'Hiragino Kaku Gothic ProN',# macOS / iOS
        'AppleGothic',             # macOS / iOS (Older)
        'Meiryo',                  # Windows
        'Yu Gothic',               # Windows
        'MS Gothic',               # Windows
        'Noto Sans CJK JP',        # Linux / Android / Others (Streamlit Cloud often has Noto Sans)
        'Noto Sans JP',            # Linux / Android / Others
        'IPAexGothic',             # Linux
        'IPAGothic',               # Linux
        'TakaoGothic',             # Linux
        'VL Gothic',               # Linux
        'WenQuanYi Zen Hei',       # Linux
        'JapanSan',                # Some Androids
    ]
    
    found_font = None
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            found_font = font_name
            break
            
    # フォントが見つかった場合はそれを設定
    if found_font:
        plt.rcParams['font.family'] = found_font
    else:
        # 見つからない場合、sans-serifに設定し、fallbackリストに追加
        # Streamlit Cloud等の環境では fc-list で日本語フォントが入っているか確認が必要だが
        # ここではできる限りの候補を追加する
        plt.rcParams['font.family'] = 'sans-serif'
        current_sans = plt.rcParams['font.sans-serif']
        if isinstance(current_sans, str):
            current_sans = [current_sans]
        
        # 重複を除きつつ優先リストを先頭に追加
        new_sans = []
        for f in preferred_fonts:
            if f not in new_sans:
                new_sans.append(f)
        for f in current_sans:
            if f not in new_sans:
                new_sans.append(f)
        plt.rcParams['font.sans-serif'] = new_sans

    # マイナス記号の文字化け防止
    plt.rcParams['axes.unicode_minus'] = False

def interpolate_flow(lu, is_fv=False):
    """負荷単位から同時使用水量を補間計算"""
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

def get_display_size(size_a, pipe_type):
    """表示用口径（A/Su/mm）の取得"""
    if "SGP" in pipe_type:
        return f"{size_a}A"
    elif "VP" in pipe_type or "PE" in pipe_type:
        map_size = {15:"13", 20:"20", 25:"25", 32:"30", 40:"40", 50:"50"}
        return map_size.get(size_a, f"{size_a}")
    elif "SU" in pipe_type:
        map_size = {15:"13Su", 20:"20Su", 25:"25Su", 32:"30Su", 40:"40Su", 50:"50Su"}
        return map_size.get(size_a, f"{size_a}Su")
    return f"{size_a}A"

def get_flow_curve_image(current_lu, current_flow, is_fv):
    """流量線図の画像を生成"""
    # グラフ生成前にフォント設定を再適用して確実にする
    setup_fonts()
    
    x_vals = []
    v = 10
    while v <= 4000:
        x_vals.append(v)
        v *= 1.1
    y_fv = [interpolate_flow(x, True) for x in x_vals]
    y_ft = [interpolate_flow(x, False) for x in x_vals]
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    # 線図のプロット
    ax.plot(x_vals, y_fv, label='曲線① (洗浄弁)', color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax.plot(x_vals, y_ft, label='曲線② (タンク)', color='gray', linestyle=':', alpha=0.5, linewidth=1)
    
    active_y = y_fv if is_fv else y_ft
    label_txt = "選択中の基準"
    ax.plot(x_vals, active_y, color='blue', linewidth=1.5, label=label_txt)
    
    if current_lu > 0:
        ax.scatter([current_lu], [current_flow], color='red', s=80, zorder=5, label='現在値')
        ax.axvline(x=current_lu, color='red', linestyle='-', linewidth=0.5, alpha=0.7)
        ax.axhline(y=current_flow, color='red', linestyle='-', linewidth=0.5, alpha=0.7)
        # テキスト表示
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
    # bbox_inches='tight' で文字切れを防ぐ
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf