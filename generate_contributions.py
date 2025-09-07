import os
import re
import requests
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Set, Optional

# --- Configuration ---
# 將你的 GitHub 使用者名稱和要處理的組織列表放在這裡
GITHUB_USERNAME: str = 'future-outlier'
ORGS_TO_PROCESS: List[str] = ['flyteorg', 'ray-project']
README_FILE_PATH: str = 'README.md'

# 從環境變數讀取 GitHub Token
TOKEN: Optional[str] = os.getenv('GITHUB_TOKEN')
HEADERS: Dict[str, str] = {
    'Authorization': f'Bearer {TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}

# --- GitHub API Functions ---

def test_github_connection() -> bool:
    """
    測試與 GitHub API 的連線是否正常並驗證身份。
    """
    if not TOKEN:
        print("❌ 錯誤：環境變數 GITHUB_TOKEN 未設定！")
        print("請設定您的 GitHub Personal Access Token：")
        print("export GITHUB_TOKEN='your_token_here'")
        return False
    
    try:
        response = requests.get("https://api.github.com/user", headers=HEADERS, timeout=10)
        response.raise_for_status()  # 如果狀態碼不是 2xx，則會拋出異常
        user_data = response.json()
        print(f"✅ GitHub API 連線成功！已驗證身份為：{user_data.get('login', '未知')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ GitHub API 連線失敗：{e}")
        return False

def fetch_all_prs(org: str, role: str) -> List[Dict[str, Any]]:
    """
    分頁獲取指定組織中，使用者擔任特定角色的所有 PR。
    角色可以是 'author' (作者) 或 'reviewed' (審核者)。
    """
    all_prs: List[Dict[str, Any]] = []
    page = 1
    
    # 根據角色構建查詢語句
    if role == 'author':
        query = f'org:{org} type:pr author:{GITHUB_USERNAME} is:merged'
    else:  # 'reviewed'
        query = f'org:{org} reviewed-by:{GITHUB_USERNAME} is:pr is:merged -author:{GITHUB_USERNAME}'
        
    print(f"    - 開始獲取作為 {role} 的 PR...")
    
    while True:
        params = {'q': query, 'per_page': 100, 'page': page}
        try:
            response = requests.get(
                "https://api.github.com/search/issues", 
                headers=HEADERS, 
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            prs = data.get('items', [])
            
            if not prs:
                break
                
            all_prs.extend(prs)
            page += 1
            
            # 如果這頁的結果少於 100，表示是最後一頁
            if len(prs) < 100:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"    ❌ 獲取 {org} 的 {role} PRs 時出錯：{e}")
            break
            
    print(f"    - 完成，共找到 {len(all_prs)} 個作為 {role} 的 PR。")
    return all_prs

# --- SVG Chart Generation ---

def get_y_axis_config(max_value: int) -> tuple[int, list[int]]:
    """計算 Y 軸的最大值和刻度。"""
    if max_value == 0:
        return 10, [0, 2, 4, 6, 8, 10]
    
    # 找到一個比最大值略大的 "漂亮" 數字 (例如 10 的倍數)
    order_of_magnitude = 10 ** (len(str(max_value)) - 1)
    y_max = ((max_value // order_of_magnitude) + 1) * order_of_magnitude
    
    # 產生 5 個刻度
    ticks = [int(y_max / 5 * i) for i in range(6)]
    return y_max, ticks

def generate_svg_chart(org: str, authored_prs: List[Dict], reviewed_prs: List[Dict]) -> str:
    """
    產生一個分組長條圖的 SVG 字串，用於視覺化年度貢獻。
    """
    # 1. 處理數據：按年份分組
    authored_by_year: Dict[str, int] = defaultdict(int)
    for pr in authored_prs:
        if 'pull_request' in pr and pr['pull_request'].get('merged_at'):
            year = pr['pull_request']['merged_at'][:4]
            authored_by_year[year] += 1

    reviewed_by_year: Dict[str, int] = defaultdict(int)
    for pr in reviewed_prs:
        if pr.get('closed_at'):
            year = pr['closed_at'][:4]
            reviewed_by_year[year] += 1
    
    all_years: List[str] = sorted(list(set(authored_by_year.keys()) | set(reviewed_by_year.keys())))

    if not all_years:
        return f"<p>在 {org} 中沒有找到貢獻記錄。</p>"

    # 2. SVG 尺寸和樣式設定
    width, height = 800, 400
    margin = {'top': 70, 'right': 40, 'bottom': 80, 'left': 60}
    chart_width = width - margin['left'] - margin['right']
    chart_height = height - margin['top'] - margin['bottom']
    
    max_count = max(max(authored_by_year.values() or [0]), max(reviewed_by_year.values() or [0]))
    y_max, y_ticks = get_y_axis_config(max_count)

    # 3. 繪製 SVG
    svg_parts = []
    
    # SVG 開頭和樣式定義
    svg_parts.append(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">')
    svg_parts.append(f'''
    <defs>
        <linearGradient id="authoredGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#28a745;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#20c997;stop-opacity:1" />
        </linearGradient>
        <linearGradient id="reviewedGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#007bff;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#6f42c1;stop-opacity:1" />
        </linearGradient>
    </defs>
    <style>
        .title {{ font: bold 18px sans-serif; fill: #212529; text-anchor: middle; }}
        .axis-label {{ font: 12px sans-serif; fill: #6c757d; }}
        .tick-label {{ font: 10px sans-serif; fill: #6c757d; text-anchor: end; }}
        .bar-label {{ font: 9px sans-serif; fill: #333; text-anchor: middle; }}
        .legend-text {{ font: 12px sans-serif; fill: #212529; }}
        .stats-text {{ font: 12px sans-serif; fill: #6c757d; }}
        .update-text {{ font: 10px sans-serif; fill: #6c757d; }}
    </style>
    <rect width="100%" height="100%" fill="#f8f9fa" />
    <rect x="{margin['left']}" y="{margin['top']}" width="{chart_width}" height="{chart_height}" fill="white" stroke="#dee2e6"/>
    ''')

    # 標題
    svg_parts.append(f'<text x="{width/2}" y="35" class="title">{org.replace("-", " ").title()} Contributions History</text>')

    # Y 軸
    svg_parts.append(f'<text transform="translate({margin["left"]-35}, {margin["top"] + chart_height/2}) rotate(-90)" class="axis-label" text-anchor="middle">PRs</text>')
    for tick in y_ticks:
        y = margin['top'] + chart_height - (tick / y_max * chart_height)
        svg_parts.append(f'<line x1="{margin["left"]}" y1="{y}" x2="{margin["left"] + chart_width}" y2="{y}" stroke="#e9ecef"/>')
        svg_parts.append(f'<text x="{margin["left"]-8}" y="{y+3}" class="tick-label">{tick}</text>')

    # X 軸和長條圖 (分組長條圖邏輯)
    group_width = chart_width / len(all_years)
    bar_width = group_width * 0.3
    bar_padding = (group_width - 2 * bar_width) / 3

    for i, year in enumerate(all_years):
        group_x = margin['left'] + i * group_width
        
        # Authored PR Bar
        authored_count = authored_by_year.get(year, 0)
        authored_h = (authored_count / y_max) * chart_height if y_max > 0 else 0
        authored_x = group_x + bar_padding
        authored_y = margin['top'] + chart_height - authored_h
        svg_parts.append(f'<rect x="{authored_x}" y="{authored_y}" width="{bar_width}" height="{authored_h}" fill="url(#authoredGradient)"/>')
        svg_parts.append(f'<text x="{authored_x + bar_width/2}" y="{authored_y - 5}" class="bar-label">{authored_count}</text>')
        
        # Reviewed PR Bar
        reviewed_count = reviewed_by_year.get(year, 0)
        reviewed_h = (reviewed_count / y_max) * chart_height if y_max > 0 else 0
        reviewed_x = authored_x + bar_width + bar_padding
        reviewed_y = margin['top'] + chart_height - reviewed_h
        svg_parts.append(f'<rect x="{reviewed_x}" y="{reviewed_y}" width="{bar_width}" height="{reviewed_h}" fill="url(#reviewedGradient)"/>')
        svg_parts.append(f'<text x="{reviewed_x + bar_width/2}" y="{reviewed_y - 5}" class="bar-label">{reviewed_count}</text>')
        
        # Year Label
        svg_parts.append(f'<text x="{group_x + group_width/2}" y="{margin["top"] + chart_height + 20}" text-anchor="middle" class="axis-label">{year}</text>')

    # 圖例 (Legend)
    legend_items = [("Merged PRs", "authoredGradient"), ("Reviewed PRs", "reviewedGradient")]
    legend_x = margin['left']
    for i, (text, color_id) in enumerate(legend_items):
        svg_parts.append(f'<rect x="{legend_x}" y="15" width="12" height="12" fill="url(#{color_id})"/>')
        svg_parts.append(f'<text x="{legend_x + 18}" y="25" class="legend-text">{text}</text>')
        legend_x += 120
    
    # 統計數據和更新時間
    total_authored = len(authored_prs)
    total_reviewed = len(reviewed_prs)
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M UTC')
    svg_parts.append(f'<text x="{margin["left"]}" y="{height - 25}" class="stats-text">Total Merged PRs: {total_authored} | Total Reviewed PRs: {total_reviewed}</text>')
    svg_parts.append(f'<text x="{margin["left"]}" y="{height - 10}" class="update-text">Last updated: {update_time}</text>')
    
    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


# --- README Update Logic ---

def update_readme() -> None:
    """
    主函式：獲取所有數據，生成圖表，並更新 README.md 文件。
    """
    if not test_github_connection():
        return

    try:
        with open(README_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"⚠️ 檔案 '{README_FILE_PATH}' 不存在，將創建一個新的。")
        content = f"""<h1 align="center">Hi, I'm {GITHUB_USERNAME}</h1>
## 📊 Open Source Contributions
"""
        for org in ORGS_TO_PROCESS:
            placeholder_name = org.upper().replace('-', '_')
            content += f"""
### {org.replace("-", " ").title()} Contributions
<!-- {placeholder_name}_CONTRIBUTIONS:START -->
<!-- {placeholder_name}_CONTRIBUTIONS:END -->
"""

    for org in ORGS_TO_PROCESS:
        print(f"\n🔄 正在處理 {org} 的貢獻...")
        
        authored_prs = fetch_all_prs(org, 'author')
        reviewed_prs = fetch_all_prs(org, 'reviewed')
        
        chart_svg = generate_svg_chart(org, authored_prs, reviewed_prs)
        
        # 替換 README 中的佔位符
        placeholder_name = org.upper().replace('-', '_')
        start_placeholder = f'<!-- {placeholder_name}-CONTRIBUTIONS:START -->'
        end_placeholder = f'<!-- {placeholder_name}-CONTRIBUTIONS:END -->'
        
        if start_placeholder in content and end_placeholder in content:
            new_section = f"{start_placeholder}\n<div align=\"center\">\n{chart_svg}\n</div>\n{end_placeholder}"
            content = re.sub(
                f'{re.escape(start_placeholder)}.*?{re.escape(end_placeholder)}',
                new_section,
                content,
                flags=re.DOTALL
            )
            print(f"✅ 已更新 {org} 的貢獻圖表。")
        else:
            print(f"❌ 在 README 中找不到 {org} 的佔位符。")
            print(f"   請確保檔案中包含 '{start_placeholder}' 和 '{end_placeholder}'。")

    try:
        with open(README_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n🎉 README.md 更新成功！")
    except IOError as e:
        print(f"❌ 無法寫入檔案 '{README_FILE_PATH}'：{e}")


if __name__ == '__main__':
    update_readme()

