#!/usr/bin/env python3
with open('web_service.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '@app.get("/proposals"' in line:
        print(f'Found /proposals at line {i+1}')
        new_route = '''@app.get("/design-preview", response_class=HTMLResponse)
def get_design_preview_html() -> str:
    """Returns the improved design preview (unslopped version)."""
    preview_file = Path(__file__).parent / "templates" / "design_preview.html"
    if preview_file.exists():
        return preview_file.read_text(encoding="utf-8")
    return "<h1>ملف design_preview.html غير متوفر</h1>"


'''
        lines.insert(i, new_route)
        break

with open('web_service.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Route added successfully!')
