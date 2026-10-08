with open('templates/dashboard.html', encoding='utf-8') as f:
    content = f.read()
print('File size:', len(content), 'bytes, lines:', content.count('\n'))
js_start = content.find('<script>')
js_end = content.rfind('</script>')
js = content[js_start:js_end]
opens = js.count('{')
closes = js.count('}')
print('JS braces: opens=%d, closes=%d, diff=%d' % (opens, closes, opens-closes))
key_ids = ['chatMessages','typingIndicator','chatInput','sijilRecentTableBody','opDetailModalOverlay','opDetailModalBody']
for k in key_ids:
    found = ('id="%s"' % k) in content
    print('  %s: %s' % (k, 'FOUND' if found else 'MISSING'))
