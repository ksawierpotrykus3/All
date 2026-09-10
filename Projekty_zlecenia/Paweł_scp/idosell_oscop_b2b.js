;(function() {
    'use strict';

    (function() {
        var id = 'cop_czsk_style_nip';
        if (document.getElementById(id)) return;
        var s = document.createElement('style');
        s.id = id;
        s.textContent = '.cop_nip_error, .cop_nip_status { min-height: 1.5em; display: block; }';
        if (document.head) document.head.appendChild(s);
    })();

    var UE = ['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PT','RO','SK','SI','ES','SE'];
    var BLOCK_PRIVATE = UE.slice();

    var REGION_MAP = {
        '1143020041': 'CZ', '1143020182': 'SK', '1143020003': 'PL', '1143020038': 'HR',
        '1143020016': 'AT', '1143020022': 'BE', '1143020033': 'BG', '1143020051': 'EE',
        '1143020057': 'FR', '1143020062': 'GR', '1143020075': 'ES', '1143020076': 'NL',
        '1143020116': 'LT', '1143020118': 'LV', '1143020143': 'DE', '1143020169': 'RO',
        '1143020183': 'SI', '1143020217': 'HU', '1143020220': 'IT', '1143020040': 'CY',
        '1143020042': 'DK', '1143020056': 'FI', '1143020080': 'IE', '1143020117': 'LU',
        '1143020126': 'MT', '1143020163': 'PT', '1143020193': 'SE'
    };

    var _currentCountry = null;

    function getLang() {
        var p = (window.location && window.location.pathname) ? window.location.pathname : '';
        if (p.indexOf('/en/') === 0) return 'en';
        if (p.indexOf('/cs/') === 0) return 'cs';
        return 'pl';
    }

    function regionToCountry(sel) {
        if (!sel || sel.selectedIndex < 0) return null;
        var val = sel.options[sel.selectedIndex].value;
        if (val && val.length === 2) return val.toUpperCase();
        if (REGION_MAP[val]) return REGION_MAP[val];
        var txt = sel.options[sel.selectedIndex].text || '';
        if (/Czech|Česko|Česká|Czech Republic|Czechia/i.test(txt)) return 'CZ';
        if (/Slovak|S\u0142owacja|Slovensko|Slovakia/i.test(txt)) return 'SK';
        if (/Pol|Polska|Poland/i.test(txt)) return 'PL';
        return null;
    }

    function getCountry() {
        var isClientNew = false;
        try {
            if (window.app_shop && window.app_shop.vars && window.app_shop.vars.copModulesType === 'client-new') {
                isClientNew = true;
            }
        } catch (e) {}

        var regionNames = isClientNew
            ? ['client_region', 'delivery_region', 'invoice_region', 'country']
            : ['delivery_region', 'client_region', 'invoice_region', 'country'];

        for (var r = 0; r < regionNames.length; r++) {
            try {
                var s = document.querySelector('select[name="' + regionNames[r] + '"]:not([disabled])');
                if (!s) continue;
                var isHidden = false;
                var p = s;
                while (p && p !== document.body) {
                    if (p.classList && (p.classList.contains('--hidden') || p.style.display === 'none')) {
                        isHidden = true;
                        break;
                    }
                    p = p.parentNode;
                }
                if (!isHidden) {
                    var c = regionToCountry(s);
                    if (c) return c;
                }
            } catch(e) {}
        }

        try {
            return (window.app_shop && window.app_shop.vars && window.app_shop.vars.geoipCountryCode) || 'PL';
        } catch(e) {
            return 'PL';
        }
    }

    function applyState(country) {
        if (!country) country = 'PL';
        _currentCountry = country;

        var vatEl = document.querySelector('.cop_terms__item.--vat');
        if (vatEl) {
            if (country === 'PL') {
                vatEl.classList.add('--hidden');
                vatEl.classList.remove('--visible');
                setCheckboxDisabled(vatEl, true);
                setNextBtn(false);
                hideNotice();
            } else if (BLOCK_PRIVATE.indexOf(country) !== -1) {
                vatEl.classList.remove('--hidden');
                vatEl.classList.add('--visible');
                setCheckboxDisabled(vatEl, false);
                setCheckboxChecked(vatEl, true);
                setNextBtn(false);
                var lang = getLang();
                var msg;
                if (country === 'CZ' || country === 'SK') {
                    msg = lang === 'en'
                        ? 'Orders from Czechia and Slovakia \u2014 you may order without VAT after EU VAT verification.'
                        : 'Zakupy dla firm z Czech i S\u0142owacji \u2014 mo\u017Cesz zam\u00F3wi\u0107 bez VAT po weryfikacji VAT UE.';
                } else {
                    msg = lang === 'en'
                        ? 'You are ordering from an EU country. You may order without VAT after EU VAT verification. Contact us if you have questions.'
                        : 'Zamawiasz z kraju UE. Mo\u017Cesz zam\u00F3wi\u0107 bez VAT po weryfikacji VAT UE. W razie pyta\u0144 skontaktuj si\u0119 z nami.';
                }
                showNotice(msg, 'info');
            } else {
                setNextBtn(true);
                var langErr = getLang();
                var msgErr = langErr === 'en'
                    ? 'Unfortunately we cannot ship to your country. Please contact us to arrange shipping terms.'
                    : 'Niestety nie mo\u017Cemy zrealizowa\u0107 zam\u00F3wienia do Twojego kraju. Skontaktuj si\u0119 z nami w celu ustalenia warunk\u00F3w wysy\u0142ki.';
                showNotice(msgErr, 'error');
            }
        }

        if (BLOCK_PRIVATE.indexOf(country) !== -1) {
            forceClientTypeFirm();
        } else if (country === 'PL') {
            restoreClientType();
        }

        if (country !== 'PL') {
            hideReceiptOption();
        } else {
            restoreReceiptOption();
        }

        validateNip(country);
    }

    function setCheckboxDisabled(vatEl, disabled) {
        var cb = vatEl.querySelector('#cop_terms_vat_checkbox');
        if (cb) cb.disabled = disabled;
    }

    function setCheckboxChecked(vatEl, checked) {
        var cb = vatEl.querySelector('#cop_terms_vat_checkbox');
        if (cb && cb.checked !== checked) {
            cb.checked = checked;
            try {
                cb.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (e) {}
        }
    }

    function forceClientTypeFirm() {
        var firmRadio = document.querySelector('input[type="radio"][name="client_type"][value="firm"]');
        var privateRadio = document.querySelector('input[type="radio"][name="client_type"][value="private"]');

        if (privateRadio) {
            privateRadio.disabled = true;
            var privParent = privateRadio.closest('.f-group, .cop_switch__radio, .f-option');
            if (privParent) privParent.classList.add('--disabled');
        }
        if (firmRadio) firmRadio.disabled = false;

        if (firmRadio && !firmRadio.checked) {
            firmRadio.checked = true;
            try {
                firmRadio.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (e) {}
        }

        showFirmFields();
    }

    function restoreClientType() {
        var privateRadio = document.querySelector('input[type="radio"][name="client_type"][value="private"]');
        if (privateRadio) {
            privateRadio.disabled = false;
            var privParent = privateRadio.closest('.f-group, .cop_switch__radio, .f-option');
            if (privParent) privParent.classList.remove('--disabled');
        }
        var firmRadio = document.querySelector('input[type="radio"][name="client_type"][value="firm"]');
        if (firmRadio) firmRadio.disabled = false;
    }

    function showFirmFields() {
        var items = document.querySelectorAll('.cop_client_data__item[data-firm="show"]');
        for (var i = 0; i < items.length; i++) {
            items[i].classList.remove('--hidden');
            var inp = items[i].querySelector('input, select, textarea');
            if (inp) inp.disabled = false;
        }
    }

    function validateNip(country) {
        var nip = document.querySelector('input[name="client_nip"]:not([disabled])');
        if (!nip) return;

        if (BLOCK_PRIVATE.indexOf(country) === -1) {
            nip.removeAttribute('required');
            nip.classList.remove('--error', '--success');
            hideNipError(nip);
            removeNipStatus(nip);
            setNextBtn(false);
            return;
        }

        nip.setAttribute('required', 'required');
        var val = (nip.value || '').trim().replace(/\s/g, '');

        if (val.length === 0) {
            nip.classList.add('--error');
            nip.classList.remove('--success');
            removeNipStatus(nip);
            setNextBtn(true);
            var lang = getLang();
            showNipError(nip, lang === 'en'
                ? 'VAT ID / NIP is required for orders from this country.'
                : 'Numer NIP / VAT ID jest wymagany dla zakup\u00F3w z tego kraju.');
        } else if (val.length < 4) {
            nip.classList.add('--error');
            nip.classList.remove('--success');
            removeNipStatus(nip);
            setNextBtn(true);
            var langShort = getLang();
            showNipError(nip, langShort === 'en'
                ? 'VAT ID is too short (minimum 4 characters).'
                : 'Numer NIP jest za kr\u00F3tki (minimum 4 znaki).');
        } else {
            nip.classList.remove('--error');
            nip.classList.add('--success');
            hideNipError(nip);
            removeNipStatus(nip);
            setNextBtn(false);
        }
    }

    function showNipError(nip, msg) {
        if (!nip || !nip.parentNode) return;
        var el = nip.parentNode.querySelector('.cop_nip_error');
        if (!el) {
            el = document.createElement('div');
            el.className = 'cop_nip_error';
            nip.parentNode.appendChild(el);
        }
        el.textContent = msg;
        el.style.visibility = 'visible';
    }

    function hideNipError(nip) {
        if (!nip || !nip.parentNode) return;
        var el = nip.parentNode.querySelector('.cop_nip_error');
        if (el) {
            el.textContent = '';
            el.style.visibility = 'hidden';
        }
    }

    function removeNipStatus(nip) {
        if (!nip || !nip.parentNode) return;
        var el = nip.parentNode.querySelector('.cop_nip_status');
        if (el) {
            el.textContent = '';
            el.className = 'cop_nip_status';
            el.style.visibility = 'hidden';
        }
    }

    function setNextBtn(blocked) {
        var btn = document.querySelector('button.cop_buttons__button.--next, button.cop_buttons__button.--submit');
        if (!btn) return;
        btn.disabled = blocked;
        btn.classList.toggle('--disabled', blocked);
    }

    function showNotice(msg, type) {
        hideNotice();
        var container = document.querySelector('.cop_summary') 
            || document.querySelector('.cop.--oscop') 
            || document.querySelector('.cop.--client-new') 
            || document.querySelector('.cop');
        if (!container) return;

        var el = document.createElement('div');
        el.className = 'cop_czsk_notice --' + (type || 'info');
        el.textContent = msg;
        var btns = container.querySelector('.cop_buttons');
        (btns ? btns.parentNode : container).insertBefore(el, btns || null);
    }

    function hideNotice() {
        var old = document.querySelector('.cop_czsk_notice');
        if (old) old.remove();
    }

    function hideReceiptOption() {
        var docSelect = document.querySelector('select[name="invoice"]');
        if (!docSelect) return;
        for (var i = 0; i < docSelect.options.length; i++) {
            var opt = docSelect.options[i];
            if (opt.value === '0') {
                if (opt.style.display !== 'none') opt.style.display = 'none';
                if (opt.selected) {
                    for (var j = 0; j < docSelect.options.length; j++) {
                        var val = docSelect.options[j].value;
                        if ((val === '1' || val === '2') && docSelect.options[j].style.display !== 'none') {
                            docSelect.selectedIndex = j;
                            try {
                                docSelect.dispatchEvent(new Event('change', { bubbles: true }));
                            } catch (e) {}
                            break;
                        }
                    }
                }
                break;
            }
        }
    }

    function restoreReceiptOption() {
        var docSelect = document.querySelector('select[name="invoice"]');
        if (!docSelect) return;
        for (var i = 0; i < docSelect.options.length; i++) {
            docSelect.options[i].style.display = '';
        }
    }

    (function tryInit() {
        var c = getCountry();
        var radio = document.querySelector('input[type="radio"][name="client_type"]');
        if (radio) {
            applyState(c);
        } else {
            var tries = 0;
            var timer = setInterval(function() {
                tries++;
                if (document.querySelector('input[type="radio"][name="client_type"]') || tries > 30) {
                    clearInterval(timer);
                    applyState(getCountry());
                }
            }, 100);
        }
    })();

    document.addEventListener('change', function(e) {
        if (e.target && e.target.name
            && (e.target.name === 'client_region'
                || e.target.name === 'delivery_region'
                || e.target.name === 'invoice_region'
                || e.target.name === 'country')) {
            applyState(getCountry());
        }
    });

    function normalizeZipcode(input) {
        if (!input) return;
        var country = _currentCountry || getCountry();
        var val = (input.value || '').trim();
        if (country === 'CZ' || country === 'SK') {
            var clean = val.replace(/\s+/g, '');
            if (/^\d{5}$/.test(clean)) {
                var formatted = clean.slice(0, 3) + ' ' + clean.slice(3);
                if (val !== formatted) {
                    input.value = formatted;
                    try {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    } catch (e) {}
                }
            }
        } else if (country === 'PL') {
            var cleanPL = val.replace(/[\s-]+/g, '');
            if (/^\d{5}$/.test(cleanPL)) {
                var formattedPL = cleanPL.slice(0, 2) + '-' + cleanPL.slice(2);
                if (val !== formattedPL) {
                    input.value = formattedPL;
                    try {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    } catch (e) {}
                }
            }
        }
    }

    document.addEventListener('change', function(e) {
        if (e.target && (e.target.name === 'client_zipcode' || e.target.name === 'delivery_zipcode' || e.target.name === 'invoice_zipcode')) {
            normalizeZipcode(e.target);
        }
    });

    document.addEventListener('blur', function(e) {
        if (e.target && (e.target.name === 'client_zipcode' || e.target.name === 'delivery_zipcode' || e.target.name === 'invoice_zipcode')) {
            normalizeZipcode(e.target);
        }
    }, true);

    document.addEventListener('input', function(e) {
        if (e.target && (e.target.name === 'client_zipcode' || e.target.name === 'delivery_zipcode' || e.target.name === 'invoice_zipcode')) {
            var val = (e.target.value || '').trim().replace(/\s+/g, '');
            if (/^\d{5}$/.test(val)) {
                normalizeZipcode(e.target);
            }
        }
    });

    document.addEventListener('input', function(e) {
        if (e.target && (e.target.name === 'client_nip' || e.target.name === 'invoice_nip')) {
            var c = _currentCountry || getCountry();
            validateNip(c);
        }
    });

    document.addEventListener('change', function(e) {
        if (e.target && e.target.name === 'client_type') {
            var c = _currentCountry || getCountry();
            if (BLOCK_PRIVATE.indexOf(c) !== -1) {
                forceClientTypeFirm();
            }
        }
    });

    setInterval(function() {
        try {
            var c = getCountry();
            if (c !== _currentCountry) {
                applyState(c);
                return;
            }

            var privateRadio = document.querySelector('input[type="radio"][name="client_type"][value="private"]');

            if (BLOCK_PRIVATE.indexOf(c) !== -1) {
                if (privateRadio && !privateRadio.disabled) {
                    forceClientTypeFirm();
                }
                var vatEl = document.querySelector('.cop_terms__item.--vat');
                if (vatEl) {
                    if (vatEl.classList.contains('--hidden')) {
                        applyState(c);
                    }
                    var cb = vatEl.querySelector('#cop_terms_vat_checkbox');
                    if (cb && cb.disabled) {
                        cb.disabled = false;
                    }
                }
                var docSelect = document.querySelector('select[name="invoice"]');
                if (docSelect) {
                    for (var i = 0; i < docSelect.options.length; i++) {
                        if (/Rachunek|receipt/i.test(docSelect.options[i].text) && docSelect.options[i].style.display !== 'none') {
                            docSelect.options[i].style.display = 'none';
                        }
                    }
                }
                validateNip(c);
            } else if (c === 'PL') {
                if (privateRadio && privateRadio.disabled) {
                    restoreClientType();
                }
                var vatElPL = document.querySelector('.cop_terms__item.--vat');
                if (vatElPL && !vatElPL.classList.contains('--hidden')) {
                    applyState(c);
                }
                var docSelectPL = document.querySelector('select[name="invoice"]');
                if (docSelectPL) {
                    for (var j = 0; j < docSelectPL.options.length; j++) {
                        if (docSelectPL.options[j].style.display === 'none') {
                            docSelectPL.options[j].style.display = '';
                        }
                    }
                }
            } else {
                setNextBtn(true);
            }

            var zipInput = document.querySelector('input[name="client_zipcode"], input[name="delivery_zipcode"]');
            if (zipInput && zipInput.value) {
                normalizeZipcode(zipInput);
            }

            var checkedCourier = document.querySelector('input[name="shipping"]:checked');
            var isCourier47 = checkedCourier && (checkedCourier.value === '47' || checkedCourier.value === '47-1' || checkedCourier.getAttribute('data-id') === '47');
            var standardCourierRadio = document.querySelector('input[name="shipping"][value*="690003"], input[name="shipping"]:not([value^="47"])');

            if (isCourier47 && standardCourierRadio) {
                standardCourierRadio.checked = true;
                standardCourierRadio.dispatchEvent(new Event('change', { bubbles: true }));
                if (window.app_shop && window.app_shop.fn && window.app_shop.fn.copModulesSummary && window.app_shop.fn.copModulesSummary.updateCosts) {
                    window.app_shop.fn.copModulesSummary.updateCosts();
                }
            }
        } catch (err) {}
    }, 200);
})();
