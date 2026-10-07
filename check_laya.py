import sys, re, time
sys.path.insert(0, 'laya-main')
t = time.time()
import laya, laya.lang as L
print('import seconds:', round(time.time() - t, 2))
print(laya.__file__, getattr(laya, '__version__', None))
samples = [
    '\u0645\u0631\u062d\u0628\u0627',
    'Hello',
    '\u0645\u0648\u0638\u0641 Ahmed',
    '12345',
    '',
    '\u0645\u0631\u062d\u0628\u0627 Hello',
]
for s in samples:
    print(repr(s), L.analyse(s), bool(re.search(r'[\u0600-\u06FF]', s)))