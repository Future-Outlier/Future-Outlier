import requests
import os
import re
from datetime import datetime
from collections import defaultdict

GITHUB_USERNAME = 'future-outlier'
TOKEN = os.getenv('GITHUB_TOKEN')

HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}

def test_github_connection():
    """Test GitHub API connection"""
    if not TOKEN:
        print("❌ Error: GITHUB_TOKEN environment variable is not set!")
        print("Please set your GitHub token:")
        print("export GITHUB_TOKEN=your_token_here")
        return False
    
    # Test with a simple API call
    test_url = "https://api.github.com/user"
    response = requests.get(test_url, headers=HEADERS)
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ GitHub API connection successful!")
        print(f"Authenticated as: {user_data.get('login', 'Unknown')}")
        return True
    else:
        print(f"❌ GitHub API connection failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False

def fetch_all_prs(org, role):
    """Fetch all PRs for a specific organization and role"""
    all_prs = []
    page = 1
    per_page = 100
    
    while True:
        if role == 'author':
            # 獲取作者的所有 merged PR
            url = f'https://api.github.com/search/issues?q=org:{org}+type:pr+author:{GITHUB_USERNAME}+is:merged&per_page={per_page}&page={page}'
        else:  # reviewed
            # 獲取審核的所有已關閉 PR（非作者創建的）
            url = f'https://api.github.com/search/issues?q=org:{org}+reviewed-by:{GITHUB_USERNAME}+is:pr+is:merged+-author:{GITHUB_USERNAME}&per_page={per_page}&page={page}'
        
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            prs = data.get('items', [])
            if not prs:
                break
            all_prs.extend(prs)
            page += 1
        else:
            print(f'Error fetching {role} PRs for {org}: {response.status_code}')
            print(f'Response: {response.text}')
            break
    
    return all_prs

def generate_contribution_chart(org, authored_prs, reviewed_prs):
    """Generate SVG chart for all contributions"""
    # Group PRs by year
    authored_by_year = defaultdict(int)
    reviewed_by_year = defaultdict(int)
    
    for pr in authored_prs:
        merged_date = pr.get('merged_at', '')
        if merged_date:
            year = merged_date[:4]  # YYYY
            authored_by_year[year] += 1
    
    for pr in reviewed_prs:
        closed_date = pr.get('closed_at', '')
        if closed_date:
            year = closed_date[:4]  # YYYY
            reviewed_by_year[year] += 1
    
    # Get all years in range
    all_years = set(authored_by_year.keys()) | set(reviewed_by_year.keys())
    all_years = sorted(list(all_years))
    
    if not all_years:
        return f"<p>No contributions found for {org}</p>"
    
    # Generate SVG
    width = 800
    height = 400
    margin = 50
    chart_width = width - 2 * margin
    chart_height = height - 2 * margin
    
    max_contributions = max(
        max(authored_by_year.values(), default=0),
        max(reviewed_by_year.values(), default=0)
    )
    
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
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
    
    <!-- Background -->
    <rect width="{width}" height="{height}" fill="#f8f9fa" stroke="#dee2e6" stroke-width="1"/>
    
    <!-- Title -->
    <text x="{width//2}" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#212529">
        {org.title()} Contributions History
    </text>
    
    <!-- Chart area -->
    <rect x="{margin}" y="{margin}" width="{chart_width}" height="{chart_height}" fill="white" stroke="#dee2e6" stroke-width="1"/>
    
    <!-- Y-axis labels -->
    <text x="{margin-10}" y="{margin+15}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#6c757d">PRs</text>
    '''
    
    # Draw Y-axis grid lines and labels
    for i in range(6):
        y = margin + (chart_height * i / 5)
        value = int(max_contributions * (5-i) / 5)
        svg += f'<line x1="{margin}" y1="{y}" x2="{margin+chart_width}" y2="{y}" stroke="#e9ecef" stroke-width="1"/>'
        svg += f'<text x="{margin-15}" y="{y+5}" text-anchor="end" font-family="Arial, sans-serif" font-size="10" fill="#6c757d">{value}</text>'
    
    # Draw bars
    bar_width = chart_width / (len(all_years) * 2.5)
    spacing = bar_width * 0.1
    
    for i, year in enumerate(all_years):
        x = margin + (chart_width * i / len(all_years)) + spacing
        
        # Authored PRs bar
        authored_count = authored_by_year.get(year, 0)
        authored_height = (authored_count / max_contributions) * chart_height if max_contributions > 0 else 0
        authored_y = margin + chart_height - authored_height
        
        svg += f'<rect x="{x}" y="{authored_y}" width="{bar_width}" height="{authored_height}" fill="url(#authoredGradient)" stroke="#28a745" stroke-width="1"/>'
        
        # Reviewed PRs bar
        reviewed_count = reviewed_by_year.get(year, 0)
        reviewed_height = (reviewed_count / max_contributions) * chart_height if max_contributions > 0 else 0
        reviewed_y = margin + chart_height - reviewed_height
        
        svg += f'<rect x="{x + bar_width + spacing}" y="{reviewed_y}" width="{bar_width}" height="{reviewed_height}" fill="url(#reviewedGradient)" stroke="#007bff" stroke-width="1"/>'
        
        # Year labels
        svg += f'<text x="{x + bar_width}" y="{margin + chart_height + 20}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#6c757d">{year}</text>'
    
    # Legend
    legend_x = margin + chart_width - 200
    legend_y = margin - 10
    
    svg += f'''
    <!-- Legend -->
    <rect x="{legend_x}" y="{legend_y-20}" width="180" height="40" fill="white" stroke="#dee2e6" stroke-width="1" rx="5"/>
    <rect x="{legend_x+10}" y="{legend_y-10}" width="12" height="12" fill="url(#authoredGradient)"/>
    <text x="{legend_x+30}" y="{legend_y-2}" font-family="Arial, sans-serif" font-size="12" fill="#212529">Merged PRs</text>
    <rect x="{legend_x+10}" y="{legend_y+5}" width="12" height="12" fill="url(#reviewedGradient)"/>
    <text x="{legend_x+30}" y="{legend_y+13}" font-family="Arial, sans-serif" font-size="12" fill="#212529">Reviewed PRs</text>
    
    <!-- Stats -->
    <text x="{margin}" y="{margin + chart_height + 50}" font-family="Arial, sans-serif" font-size="12" fill="#6c757d">
        Total Merged PRs: {len(authored_prs)} | Total Reviewed PRs: {len(reviewed_prs)}
    </text>
    <text x="{margin}" y="{margin + chart_height + 70}" font-family="Arial, sans-serif" font-size="10" fill="#6c757d">
        Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
    </text>
    </svg>'''
    
    return svg

def update_readme():
    """Update README with contribution stats and charts"""
    # Test connection first
    if not test_github_connection():
        return
    
    # 檢查 README 是否存在，如果不存在則創建
    try:
        with open('README.md', 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        content = ""
    
    # 如果 README 是空的，創建基本結構
    if not content.strip():
        content = """<h1 align="center">Hi , I'm Han-Ju Chen</h1>

Resume: [link](https://drive.google.com/file/d/1HlnmBUAPkuEfEA11emRpWD-kNGl5Worr/view?usp=sharing)

## 📊 Open Source Contributions

### Flyte Organization Contributions
<!-- FLYTEORG-CONTRIBUTIONS:START -->
<!-- FLYTEORG-CONTRIBUTIONS:END -->

### Ray Project Contributions
<!-- RAY-PROJECT-CONTRIBUTIONS:START -->
<!-- RAY-PROJECT-CONTRIBUTIONS:END -->
"""

    for org in ['flyteorg', 'ray-project']:
        print(f"\n📊 Fetching all data for {org}...")
        
        # Fetch all PR history
        authored_prs = fetch_all_prs(org, 'author')
        reviewed_prs = fetch_all_prs(org, 'reviewed')
        
        print(f"✅ Found {len(authored_prs)} authored PRs and {len(reviewed_prs)} reviewed PRs for {org}")
        
        # Generate chart
        chart_svg = generate_contribution_chart(org, authored_prs, reviewed_prs)
        
        # Format the content with chart
        new_content = f"""
<div align="center">

{chart_svg}

</div>

**Total Merged PRs**: {len(authored_prs)}  
**Total Reviewed PRs**: {len(reviewed_prs)}  

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*"""

        placeholder_start = f'<!-- {org.upper()}-CONTRIBUTIONS:START -->'
        placeholder_end = f'<!-- {org.upper()}-CONTRIBUTIONS:END -->'

        # 檢查佔位符是否存在
        if placeholder_start in content and placeholder_end in content:
            content = re.sub(
                f'{placeholder_start}.*?{placeholder_end}',
                f'{placeholder_start}\n{new_content}\n{placeholder_end}',
                content,
                flags=re.DOTALL
            )
        else:
            print(f"❌ Placeholders not found for {org}")
            print(f"Looking for: {placeholder_start} and {placeholder_end}")

    with open('README.md', 'w', encoding='utf-8') as file:
        file.write(content)
    
    print("\n🎉 README updated successfully!")

if __name__ == '__main__':
    update_readme()
