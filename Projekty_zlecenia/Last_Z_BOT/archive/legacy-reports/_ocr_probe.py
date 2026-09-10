import cv2
from mvp.bot.ocr import ChatOCR

o = ChatOCR()
o.initialize()
out = []
for name in ['no_chat.png', '1_scan_chat_without_arrow.png', 'helka_scrolled.png', 'details.png', '1_scan_chat_with_arrow.png']:
    img = cv2.imread('data/macro_testing/' + name)
    r = o._reader.readtext(img, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz: -', detail=1)
    out.append('=== ' + name + ' blocks ' + str(len(r)))
    for _b, t, c in sorted(r, key=lambda x: x[0][0][1]):
        out.append('  ' + repr(t) + ' ' + str(round(c, 2)))
with open('_ocr_probe_out.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done')