import glob, os, sys

terms = ['blik', 'credit_card', 'three_d', 'adyen', 'wallet',
         'mangopay', 'payment_method', 'apple_pay', 'google_pay',
         'paypal', 'card_number', '3ds', 'payment_method_type',
         'saved_card', 'new_card']

base = r'C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\chunks'
files = glob.glob(os.path.join(base, '*.js'))

hits = {}
for f in files:
    s = open(f, encoding='utf-8', errors='replace').read().lower()
    for t in terms:
        if t in s:
            hits.setdefault(t, []).append(os.path.basename(f))

for t, v in sorted(hits.items()):
    sys.stdout.write(t + ' -> ' + str(len(v)) + ' plikow: ' + ', '.join(sorted(set(v))) + '\n')