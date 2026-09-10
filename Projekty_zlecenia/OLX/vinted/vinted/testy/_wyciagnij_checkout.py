import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
p = r'C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\chunks\0~~ak8p40jr.6.js'
s = open(p, encoding='utf-8', errors='replace').read()
for t in ['initiateSingleCheckout', 'purchases/checkout/build', 'shipping_pickup', 'purchase_items', 'payment_method']:
    i = s.find(t)
    print('===== ' + t + ' @pos ' + str(i))
    if i >= 0:
        print(s[max(0, i-300):i+600])
    else:
        print('N/A')
    print()