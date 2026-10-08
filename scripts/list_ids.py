import re
with open('templates/dashboard.html', encoding='utf-8') as f:
    txt = f.read()
ids = re.findall(r'id="([^"]+)"', txt)
for x in sorted(set(ids)):
    print(x)
