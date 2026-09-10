class SummaryCOP extends COPModules {
    constructor(options = {}) {
        super(options);
        this.initEventsOnce();
    }
    getDeliveryOverrideConfig() {
        // v31: Wymuszamy pobieranie z PL (plik 43), bo tam są wszystkie reguły
        return {
            prefix: "/pl",
            slug: "wyjatki-czasu-dostawy-43-43",
            defaultBusinessDays: 3,
        };
    }

    normalizeDeliveryOverrideText(text = "") {
        return String(text)
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ") // normalizacja spacji
            .toUpperCase()
            .trim();
    }

    normalizeDeliveryOverridePath(path = "") {
        if (!path) return "";

        try {
            const rawPath = String(path).trim().replace(/\u00A0/g, " ");
            const url = /^https?:\/\//i.test(rawPath) || rawPath.startsWith("//")
                ? new URL(rawPath, window.location.origin)
                : new URL(rawPath.startsWith("/") ? rawPath : `/${rawPath}`, window.location.origin);

            let pathname = (url.pathname || "/").replace(/\/+$/g, "") || "/";

            // v27: Dodajemy pomocniczą funkcję do usuwania prefixów językowych dla "Dual Match"
            return pathname || "/";
        } catch (error) {
            let raw = String(path).split("#")[0].split("?")[0].replace(/\u00A0/g, " ").trim().replace(/\/+$/g, "");
            if (!raw.startsWith("/")) raw = "/" + raw;
            return raw || "/";
        }
    }

    // v27: Pomocnicza metoda do "miękkiego" dopasowania (bez /pl, /en)
    getSimplifiedPath(path = "") {
        return path.replace(/^\/(pl|en)(?=\/|$)/i, "") || "/";
    }

    getDeliveryOverrideProductLinks() {
        const selectors = [
            '[data-product-url]',
            '[data-product-link]',
            '.basket__name a[href]',
            '.basket__product_name a[href]',
            '.basketedit_product__name a[href]',
            '.basketedit_products__name a[href]',
            '.productslist__name a[href]',
            '.product__name a[href]',
            '.s_product__name a[href]',
            '.orderdetails_product__name a[href]',
            '.cop_products a[href]',
            '.product_name a[href]',
            'a.basketedit_product__img[href]',
            'a.basketedit_products__img[href]',
            'a[href*="/products/"]',
            'a[href*="/produkt/"]',
        ];

        const links = new Set();

        selectors.forEach((selector) => {
            document.querySelectorAll(selector).forEach((element) => {
                const rawLink =
                    element.getAttribute("data-product-url") ||
                    element.getAttribute("data-product-link") ||
                    element.getAttribute("href");

                const normalizedPath = this.normalizeDeliveryOverridePath(rawLink);
                if (normalizedPath) {
                    links.add(normalizedPath);
                }
            });
        });

        return links;
    }

    parseDeliveryOverrideRules(html = "") {
        if (!html) return [];

        console.log(`[Parser v30] CMS RAW HTML length: ${html.length}`);
        console.log(`[Parser v30] Sample: ${html.slice(0, 300)}...`);

        const isNotFound = html.includes("404") || html.includes("Page not found") || html.includes("Strona nie istnieje");
        if (isNotFound && html.length < 100000) {
            console.warn("[Parser v30] Detected potental 404/Error page in CMS response!");
        }

        const doc = new DOMParser().parseFromString(html, "text/html");

        // v30: Szukamy słów kluczowych w całym dokumencie dla pewności
        const bodyText = (doc.body.textContent || "").toUpperCase();
        console.log(`[Parser v30] "DELIVERY EXCEPTION" present in body: ${bodyText.includes("DELIVERY EXCEPTION")}`);
        console.log(`[Parser v30] "WYJATEK DOSTAWY" present in body: ${bodyText.includes("WYJATEK DOSTAWY")}`);

        const container =
            doc.querySelector("._ae_desc, .text_menu__txt_sub, .projector_cms_content, .p_text, .iai-section-html, .iai-description, .text_menu__txt, .iai_description") ||
            doc.body;

        const elements = container.querySelectorAll("h1,h2,h3,h4,h5,h6,p,li,div,span");
        const rules = [];
        let currentRule = null;

        elements.forEach((element) => {
            const text = (element.textContent || "").trim();
            if (!text || text.length > 500) return;

            const normalizedText = this.normalizeDeliveryOverrideText(text);

            if (normalizedText.includes("WYJATEK DOSTAWY") || normalizedText.includes("DELIVERY EXCEPTION")) {
                if (!text.includes(":") || normalizedText.startsWith("WYJATEK") || normalizedText.startsWith("DELIVERY")) {
                    currentRule = { links: [], days: 0 };
                    rules.push(currentRule);
                    return;
                }
            }

            if (!currentRule || !text.includes(":")) return;

            const separatorIndex = text.indexOf(":");
            const rawKey = text.slice(0, separatorIndex);
            const key = this.normalizeDeliveryOverrideText(rawKey);
            const value = text.slice(separatorIndex + 1).trim();

            if (key === "LINK" || key === "LINK_EN" || key === "URL") {
                const path = this.normalizeDeliveryOverridePath(
                    element.querySelector("a[href]")?.getAttribute("href") || value,
                );
                if (path && !currentRule.links.includes(path)) {
                    currentRule.links.push(path);
                }
            }

            if (key === "DNI_ROBOCZE" || key === "BUSINESS_DAYS" || key === "DAYS" || key === "DNI") {
                const days = Number.parseInt(value.replace(/[^0-9]/g, ""), 10) || 0;
                if (days > 0) currentRule.days = days;
            }
        });

        const finalRules = rules.filter((rule) => rule.links.length > 0 && rule.days > 0);
        console.log(`[Parser v30] Final Rules Found: ${finalRules.length}`);
        return finalRules;
    }

    async getMaxDeliveryOverrideDays() {
        const { prefix, slug, defaultBusinessDays } = this.getDeliveryOverrideConfig();
        const productLinks = this.getDeliveryOverrideProductLinks();

        if (!productLinks.size) {
            return defaultBusinessDays;
        }

        try {
            // v27: Dodajemy timestamp, aby uniknąć cache
            const response = await fetch(`${prefix}/cms/${slug}?t=${Date.now()}`);
            if (!response.ok) {
                console.warn(`Delivery override CMS fetch failed (${response.status}) for ${prefix}/cms/${slug}`);
                return defaultBusinessDays;
            }

            const html = await response.text();
            const rules = this.parseDeliveryOverrideRules(html);

            console.group("COP Delivery Override Debug v27");
            console.log("Basket Product Links (Normalized):", Array.from(productLinks));
            console.log("CMS Rules Found:", rules);
            console.log("CMS RAW HTML length:", html.length);

            const result = Array.from(productLinks).reduce((maxDays, productLink) => {
                const simpleProductLink = this.getSimplifiedPath(productLink);

                const matchedRule = rules.find((rule) => {
                    return rule.links && rule.links.some(link => {
                        const simpleLink = this.getSimplifiedPath(link);
                        // v27: Dual Match - dopasuj dokładnie LUB po uproszczonej ścieżce
                        return link === productLink || simpleLink === simpleProductLink;
                    });
                });

                if (matchedRule) {
                    console.log(`Match Found: ${productLink} (simple: ${simpleProductLink}) -> ${matchedRule.days} days`);
                    return Math.max(maxDays, matchedRule.days);
                } else {
                    console.log(`No Match for: ${productLink} (simple: ${simpleProductLink}). CMS links checked:`,
                        rules.map(r => r.links).flat());
                    return Math.max(maxDays, defaultBusinessDays);
                }
            }, 0) || defaultBusinessDays;

            console.log("Final Max Days Result:", result);
            console.groupEnd();

            return result;
        } catch (error) {
            console.warn("Delivery override CMS error", error);
            return defaultBusinessDays;
        }
    }

    formatDeliveryOverrideDays(days) {
        const safeDays = Number.parseInt(days, 10) || 3;
        const isEnglish = /^\/en(\/|$)/i.test(window.location.pathname || "");

        if (isEnglish) {
            return safeDays === 1 ? "up to 1 business day" : `up to ${safeDays} business days`;
        }

        return safeDays === 1 ? "do 1 dnia roboczego" : `do ${safeDays} dni roboczych`;
    }


    addLoading() {
        const contentElement = document.querySelector(`.${this.prefix}__content`);
        if (contentElement) contentElement.classList.add('--loading');
        this.summaryElement?.classList.add('--loading');
    }

    removeLoading() {
        const contentElement = document.querySelector(`.${this.prefix}__content`);
        if (contentElement) contentElement.classList.remove('--loading');
        this.summaryElement?.classList.remove('--loading');
    }

    addHighlightError() {
        const allFailedElements = document.querySelectorAll('.f-feedback.--error .f-control');
        allFailedElements.forEach((el) => {
            el.classList.add('--highlight');
            setTimeout(() => {
                el.classList.remove('--highlight');
            }, 2000);
        });
    }

    addHighlightColorError() {
        const allLinkElements = document.querySelectorAll('.--add-highlight-color');
        allLinkElements.forEach((el) => {
            el.classList.remove('--add-highlight-color');
            el.classList.add('--highlight-color');
            setTimeout(() => {
                el.classList.remove('--highlight-color');
            }, 2000);
        });
    }

    formValidationFailed() {
        const firstFailedElement = document.querySelector('.f-feedback.--error .f-control.--validate:not(:disabled)')
            || document.querySelector('.f-group.--error .f-control.--validate:not(:disabled)') || document.querySelector('.f-feedback.--error .f-group.f-select.--validate .f-select-select:not(:disabled)');
        super.scrollToElement({
            element: firstFailedElement.closest('.--error'),
            callback: this.addHighlightError.bind(this),
        });
        firstFailedElement?.focus();
    }

    validatePayment() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return true;
        const serializeForm = new FormData(formElement);
        if (serializeForm.has('payform_id')) return true;
        if (serializeForm.has('first_payment_id')) return true;
        if (serializeForm.has('selected_group_only')) return true;
        return false;
    }

    paymentValidationFailed() {
        const paymentsElement = document.querySelector(`.${this.prefix}_payments`);
        const paymentElement = document.querySelector(`.${this.prefix}_payments__select_payment`);
        if (!paymentsElement || !paymentElement) return;
        this.scrollToElement({ element: paymentsElement });
        paymentElement.focus();
        Alertek.Info(this.txt['Wybierz formę płatności']);
    }

    validateDelivery() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return true;
        const serializeForm = new FormData(formElement);
        if (!serializeForm.has('shipping')) return false;
        if (serializeForm.get('division') === 'turn_on' && !serializeForm.has('shipping_division')) return false;
        return true;
    }

    deliveryValidationFailed() {
        const serializeForm = new FormData(document.querySelector(`.${this.prefix}`));
        Alertek.Info(this.txt['Wybierz opcję dostawy']);
        const division = (!serializeForm.has('shipping')) ? 'now' : 'later';
        const deliveriesElement = document.querySelector(`.${this.prefix}_deliveries`);
        if (!deliveriesElement) return;
        const blockElement = deliveriesElement.querySelector(`.${this.prefix}_deliveries__block.--${division}`);
        if (!blockElement) return;
        const labelLinkElement = document.querySelector(`.${this.prefix}_deliveries__label_link.--${division}`);
        if (deliveriesElement.classList.contains('--later') && division === 'now') labelLinkElement?.click?.();
        if (!deliveriesElement.classList.contains('--later') && division === 'later') labelLinkElement?.click?.();
        this.scrollToElement({ element: blockElement });
        if (deliveriesElement.classList.contains('--dvp')) {
            blockElement.querySelectorAll(`.${this.prefix}_deliveries__item[data-prepaid="dvp"] .${this.prefix}_deliveries__select_delivery`)?.[0]?.focus();
        } else {
            blockElement.querySelectorAll(`.${this.prefix}_deliveries__item[data-prepaid="prepaid"] .${this.prefix}_deliveries__select_delivery`)?.[0]?.focus();
        }
    }

    validatePickupPoint() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return true;
        const serializeForm = new FormData(formElement);
        if (serializeForm.get('pickup_point') === '') return false;
        if (serializeForm.get('stock') === '') return false;
        if (serializeForm.get('pickup_point_division') === '') return false;
        if (serializeForm.get('stock_division') === '') return false;
        return true;
    }

    pickupValidationFailed() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return;
        const serializeForm = new FormData(formElement);
        Alertek.Info(this.txt['Wybierz punkt odbioru']);
        const division = (serializeForm.get('pickup_point') === '' || serializeForm.get('stock') === '') ? 'now' : 'later';
        const deliveriesElement = document.querySelector(`.${this.prefix}_deliveries`);
        if (!deliveriesElement) return;
        const blockElement = deliveriesElement.querySelector(`.${this.prefix}_deliveries__block.--${division}`);
        if (!blockElement) return;
        const deliveryElement = blockElement.querySelector(`.${this.prefix}_delivery.--checked`);
        if (!deliveryElement) return;
        const pickupFindLinkElement = deliveryElement.querySelector(`.${this.prefix}_delivery__pickup_find`);
        if (!pickupFindLinkElement) return;
        pickupFindLinkElement.classList.add('--add-highlight-color');
        const labelLinkElement = document.querySelector(`.${this.prefix}_deliveries__label_link.--${division}`);
        if (deliveriesElement.classList.contains('--later') && division === 'now') labelLinkElement?.click?.();
        if (!deliveriesElement.classList.contains('--later') && division === 'later') labelLinkElement?.click?.();
        this.scrollToElement({
            element: deliveryElement,
            callback: this.addHighlightColorError.bind(this),
        });
        if (deliveriesElement.classList.contains('--dvp')) {
            blockElement.querySelectorAll(`.${this.prefix}_deliveries__item[data-prepaid="dvp"] .${this.prefix}_deliveries__select_delivery`)?.[0]?.focus();
        } else {
            blockElement.querySelectorAll(`.${this.prefix}_deliveries__item[data-prepaid="prepaid"] .${this.prefix}_deliveries__select_delivery`)?.[0]?.focus();
        }
    }

    formatAddressData(serializeForm, type) {
        const street = serializeForm.get(`${type}_street`);
        const streetNumber = serializeForm.get(`${type}_street_number`);
        if (street && streetNumber) {
            serializeForm.set(`${type}_street`, `${street} ${streetNumber}`);
            serializeForm.delete(`${type}_street_number`);
        }

        const phone = serializeForm.get(`${type}_phone`);
        const phonePrefix = serializeForm.get(`${type}_phone_prefix`);
        if (phone && phonePrefix) {
            serializeForm.set(`${type}_phone`, `${phonePrefix} ${phone}`);
            serializeForm.delete(`${type}_phone_prefix`);
        }
        const data = [...serializeForm].filter((el) => el[0].startsWith(`${type}_`));
        let dataString = '';
        data.forEach((el) => {
            if (el[0] === `${type}_firm` || el[0] === `${type}_additional`) {
                dataString += `companyName:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_nip` && type !== 'client') {
                dataString += `taxNumber:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_firstname`) {
                dataString += `firstname:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_lastname`) {
                dataString += `lastname:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_street`) {
                dataString += `street:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_zipcode`) {
                dataString += `zipcode:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_city`) {
                dataString += `city:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_region`) {
                dataString += `country:${el[1]?.replace?.(/"/g, '\\"')},`;
                return;
            }
            if (el[0] === `${type}_province`) {
                dataString += `province:"${el[1]?.replace?.(/"/g, '\\"')}",`;
                return;
            }
            if (el[0] === `${type}_phone`) {
                dataString += `phone:"${el[1]?.replace?.(/"/g, '\\"')}",`;
            }
        });
        return dataString;
    }

    getClientDeliveryData(serializeForm, name) {
        let clientString = `${name || 'clientDeliveryData'}: {`;
        clientString += this.formatAddressData(serializeForm, 'client');
        clientString += '}';
        return clientString;
    }

    getClientDeliveryOtherAddressData(serializeForm, name) {
        if (!serializeForm.has('deliver_to_billingaddr')) return '';
        let deliveryString = `${name || 'clientDeliveryOtherAddressData'}: {`;
        deliveryString += this.formatAddressData(serializeForm, 'delivery');
        deliveryString += '}';
        return deliveryString;
    }

    getClientBillingOtherData(serializeForm, name) {
        if (!serializeForm.has('invoice_to_billingaddr')) return '';
        let invoiceString = `${name || 'clientBillingOtherData'}: {`;
        invoiceString += this.formatAddressData(serializeForm, 'invoice');
        invoiceString += '}';
        return invoiceString;
    }

    getTypeData(serializeForm) {
        if (!serializeForm.has('client_type')) return '';
        const typeData = serializeForm.get('client_type');
        return `type: ${typeData}`;
    }

    getBirthdateData(serializeForm) {
        if (!serializeForm.has('birth_date')) return '';
        const birthdateData = serializeForm.get('birth_date');
        return `birthDate: "${birthdateData.replace(/"/g, '\\"')}"`;
    }

    getTaxNumberData(serializeForm) {
        if (!serializeForm.has('client_nip')) return '';
        const taxNumberData = serializeForm.get('client_nip');
        return `taxNumber: "${taxNumberData.replace(/"/g, '\\"')}"`;
    }

    getEmailData(serializeForm) {
        if (!serializeForm.has('client_email')) return '';
        const emailData = serializeForm.get('client_email');
        return `email: "${emailData.replace(/"/g, '\\"')}"`;
    }

    getLoginData(serializeForm) {
        if (!serializeForm.has('client_login')) return '';
        const loginData = serializeForm.get('client_login');
        return `login: "${loginData.replace(/"/g, '\\"')}"`;
    }

    getPasswordData(serializeForm) {
        if (!serializeForm.has('client_password')) return '';
        const passwordData = serializeForm.get('client_password');
        return `password: "${passwordData.replace(/"/g, '\\"')}", passwordRepeat: "${passwordData.replace(/"/g, '\\"')}", `;
    }

    getDeliveryAddressId(serializeForm, formElement) {
        if (!serializeForm.has('deliver_to_billingaddr')) return 'activeDeliveryAddress: 0';

        const deliveryAddressId = formElement.querySelector('input[name="deliver_to_billingaddr"]')?.getAttribute('data-id') || 0;

        return `activeDeliveryAddress: ${deliveryAddressId}`;
    }

    getInvoiceAddressId(serializeForm, formElement) {
        if (!serializeForm.has('invoice_to_billingaddr')) return 'activeInvoiceAddress: 0';

        const invoiceAddressId = formElement.querySelector('input[name="invoice_to_billingaddr"]')?.getAttribute('data-id') || 0;

        return `activeInvoiceAddress: ${invoiceAddressId}`;
    }

    getClientData(serializeForm) {
        const typeData = this.getTypeData(serializeForm);
        if (!typeData) return '';
        const birthdateData = this.getBirthdateData(serializeForm);
        const taxNumberData = this.getTaxNumberData(serializeForm);
        const emailData = this.getEmailData(serializeForm);
        const clientDeliveryData = this.getClientDeliveryData(serializeForm);
        const clientDeliveryOtherAddressData = this.getClientDeliveryOtherAddressData(serializeForm);
        const clientBillingOtherData = this.getClientBillingOtherData(serializeForm);
        const saveToMailingData = this.getSaveToMailingData(serializeForm);
        const saveToSmsData = this.getSaveToSmsData(serializeForm);
        const vatCompany = this.getVatCompanyData(serializeForm);

        return `clientData: {
      ${clientDeliveryData}
      ${clientDeliveryOtherAddressData}
      ${clientBillingOtherData}
      ${typeData}
      ${birthdateData}
      ${taxNumberData}
      ${emailData}
      ${saveToMailingData}
      ${saveToSmsData}
      ${vatCompany}
    }`;
    }

    getPaymentData(serializeForm) {
        if (serializeForm.has('payform_id')) {
            const paymentId = serializeForm.get('payform_id');
            return `paymentMethodId: ${paymentId}`;
        }
        if (serializeForm.has('first_payment_id')) {
            const paymentId = serializeForm.get('first_payment_id');
            return `paymentMethodId: ${paymentId}`;
        }
        if (serializeForm.has('selected_group_only')) {
            const paymentGorupId = serializeForm.get('selected_group_only');
            return `selectedGroup: "${paymentGorupId}"`;
        }
        return '';
    }

    getCourierData(serializeForm) {
        if (!serializeForm.has('shipping')) return '';
        const courierData = serializeForm.get('shipping').split('-')[0];
        return `courierId: "${courierData}"`;
    }

    getCourierAdditionalData(serializeForm) {
        if (!serializeForm.has('calendar_services') && !serializeForm.has('shipping')) return '';
        const service = serializeForm.get('calendar_services')?.split?.('-')?.[2]
            || serializeForm.get('shipping')?.split?.('-')?.[2];
        if (!service) return '';
        let serviceName = 'SERVICE_WEEKEND_DELIVERY';
        if (service === '2') serviceName = 'SERVICE_SATURDAY_DELIVERY';
        if (service === '3') serviceName = 'ATYPICAL_PRODUCT_SIZE';
        return `deliveryAdditionalServicesId: ${serviceName}`;
    }

    getCourierForPointsData(serializeForm) {
        if (!serializeForm.has('shipping_for_points') && !serializeForm.has('calendar_services_points')) return '';
        const forPointsData = serializeForm.get('shipping_for_points') || serializeForm.get('calendar_services_points');
        const forPointsChoice = forPointsData === '1' ? true : forPointsData;
        return `isShippingForPoints: ${forPointsChoice}`;
    }

    getCourierLaterData(serializeForm) {
        if (!serializeForm.has('calendar_services_division') && !serializeForm.has('shipping_division')) return '';
        const courier = serializeForm.get('calendar_services_division') || serializeForm.get('shipping_division');
        const courierLaterData = courier.split('-')[0];
        return `courierIdLater: "${courierLaterData}"`;
    }

    getPrepaidData(serializeForm) {
        if (!serializeForm.has('shipping')) return '';
        const prepaid = serializeForm.get('shipping').split('-')[1];
        const prepaidData = (prepaid === '1') ? 'prepaid' : 'dvp';
        return `prepaid: ${prepaidData}`;
    }

    getPickupPointData(serializeForm) {
        if (!serializeForm.has('pickup_point')) return '';
        const pickupPointData = serializeForm.get('pickup_point');
        return `pickupPointId: "${pickupPointData}"`;
    }

    getPickupPointLaterData(serializeForm) {
        if (!serializeForm.has('pickup_point_division')) return '';
        const pickupPointLaterData = serializeForm.get('pickup_point_division');
        return `pickupPointIdLater: "${pickupPointLaterData}"`;
    }

    getClientCourierNumberData(serializeForm) {
        if (!serializeForm.has('client_courier_number')) return '';
        const clientCourierNumber = serializeForm.get('client_courier_number');
        return `clientCourierNumber: "${clientCourierNumber}"`;
    }

    getStockData(serializeForm) {
        if (!serializeForm.has('stock')) return '';
        const stockData = serializeForm.get('stock');
        return `stockId: ${stockData}`;
    }

    getStockLaterData(serializeForm) {
        if (!serializeForm.has('stock_division')) return '';
        const stockDivisionData = serializeForm.get('stock_division');
        return `stockIdLater: ${stockDivisionData}`;
    }

    getCalendarData(serializeForm) {
        const date = serializeForm.get('calendar_select_date');
        const hour = serializeForm.get('calendar_select_hour');
        const service = serializeForm.get('calendar_services');
        if (!date && !hour && !service) return '';
        const dateData = (date) ? `selectedDate: "${date}"` : '';
        const hourData = (hour) ? `selectedHour: "${hour}"` : '';
        const serviceData = (service)
            ? `calendarServiceCourierId: "${service.split('-')[0]}",calendarServicePaymentType: ${service.split('-')[1]}`
            : '';
        return `courierCalendarDetails: {
      ${dateData}
      ${hourData}
      ${serviceData}
    }`;
    }

    getRemarksData(serializeForm) {
        if (!serializeForm.has('remarks')) return '';
        const remarksData = serializeForm.get('remarks');
        return `remarks: """${remarksData.replace(/"/g, '\\"')}"""`;
    }

    getDeliveryRemarksData(serializeForm) {
        if (!serializeForm.has('delivery_remarks')) return '';
        const deliveryRemarksData = serializeForm.get('delivery_remarks');
        return `deliveryRemarks: """${deliveryRemarksData.replace(/"/g, '\\"')}"""`;
    }

    getDocumentTypeData(serializeForm) {
        if (!serializeForm.has('invoice')) return '';
        const documentTypeData = serializeForm.get('invoice');
        if (documentTypeData === '0') return 'purchaseDocumentType: confirmation';
        if (documentTypeData === '1') return 'purchaseDocumentType: invoice';
        if (documentTypeData === '2') return 'purchaseDocumentType: eInvoice';
        return '';
    }

    getSaveToMailingData(serializeForm) {
        if (!serializeForm.has('client_mailing')) return '';
        return 'saveToMailingAfterOrder: true';
    }

    getSaveToSmsData(serializeForm) {
        if (!serializeForm.has('client_sms')) return '';
        return 'saveToSmsAfterOrder: true';
    }

    getEmailProcessingData(serializeForm) {
        if (!serializeForm.has('order_email-processing')) return '';
        return 'emailProcessingConsent: true';
    }

    getCheckoutTypeData() {
        const type = (this.type === 'oscop') ? 'oscop' : 'multistep';
        return `checkoutType: ${type}`;
    }

    getVatCompanyData(serializeForm) {
        if (!serializeForm.has('vat_company')) return 'vatCompany: false';
        return 'vatCompany: true';
    }

    getOrderData(serializeForm) {
        const paymentData = this.getPaymentData(serializeForm);
        if (!paymentData) return '';
        const courierData = this.getCourierData(serializeForm);
        const courierAdditionalData = this.getCourierAdditionalData(serializeForm);
        const courierForPointsData = this.getCourierForPointsData(serializeForm);
        const courierLaterData = this.getCourierLaterData(serializeForm);
        const prepaidData = this.getPrepaidData(serializeForm);
        const pickupPointData = this.getPickupPointData(serializeForm);
        const pickupPointLaterData = this.getPickupPointLaterData(serializeForm);
        const clientCourierNumberData = this.getClientCourierNumberData(serializeForm);
        const stockData = this.getStockData(serializeForm);
        const stockLaterData = this.getStockLaterData(serializeForm);
        const calendarData = this.getCalendarData(serializeForm);
        const remarksData = this.getRemarksData(serializeForm);
        const deliveryRemarksData = this.getDeliveryRemarksData(serializeForm);
        const documentTypeData = this.getDocumentTypeData(serializeForm);
        const emailProcessingConsent = this.getEmailProcessingData(serializeForm);
        const checkoutTypeData = this.getCheckoutTypeData();
        return `orderData: {
      ${paymentData}
      ${courierData}
      ${courierAdditionalData}
      ${courierForPointsData}
      ${courierLaterData}
      ${prepaidData}
      ${pickupPointData}
      ${pickupPointLaterData}
      ${clientCourierNumberData}
      ${stockData}
      ${stockLaterData}
      ${calendarData}
      ${remarksData}
      ${deliveryRemarksData}
      ${documentTypeData}
      ${emailProcessingConsent}
      ${checkoutTypeData}
    }`;
    }

    prepareOrderCreateInput() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return 'orderCreateInput: {}';
        const serializeForm = new FormData(formElement);
        const clientData = this.getClientData(serializeForm);
        const orderData = this.getOrderData(serializeForm);
        return `orderCreateInput: {
      ${clientData}
      ${orderData}
    }`;
    }

    async orderCreate() {
        const orderCreateInput = this.prepareOrderCreateInput();
        const orderCreateData = await this.fetchData({
            data: this.queries.ORDER_CREATE(orderCreateInput),
            linkParameter: `?mutation=copModulesOrderCreate&type=${this.type}`,
        });
        if (orderCreateData?.data?.orderCreate?.location) {
            sessionStorage.removeItem('userOnceData');
            window.location.href = orderCreateData.data.orderCreate.location;
            return;
        }
        this.removeLoading();
    }

    getCheapestCourier(shipping = []) {
        const availableCouriers = shipping.filter((courier) => courier.minworthReached && courier.courier.id !== 0);
        const cheapestCourier = availableCouriers.sort((a, b) => a.cost.value - b.cost.value);
        return cheapestCourier[0];
    }

    getFastestCourier(shipping = [], later = false) {
        const couriers = (later)
            ? shipping.filter((courier) => courier.minworthReached && courier.availability === 'later' && courier.courier.id !== 0)
            : shipping.filter((courier) => courier.minworthReached && courier.availability === 'now' && courier.courier.id !== 0);
        const todayCouriers = couriers.filter((courier) => courier.deliveryTime.today);
        if (todayCouriers.length) return todayCouriers[0];
        const fastestCourier = couriers.sort((a, b) => a.deliveryTime.time.days - b.deliveryTime.time.days);
        return fastestCourier[0];
    }

    getDeliveryTimeObject(delivery) {
        if (!delivery) return false;
        const pickup = (delivery.courier?.id === 0);
        const { today } = delivery.deliveryTime || {};
        if (today) return { dateFormatted: this.locale.weekdays[0], pickup };
        const { weekDay, weekAmount } = delivery?.deliveryTime;
        if (weekAmount > 0) {
            const { days } = delivery?.deliveryTime?.time || {};
            const { day, month } = super.calculateDate({
                days,
            }) || {};
            return { dateFormatted: `${this.locale.weekdays[weekDay]}\u00A0(${day}.${month})`, pickup };
        }
        return { dateFormatted: this.locale.weekdays[weekDay], pickup };
    }

    async getDeliveryTime() {
        const deliveryOverrideRequestId = (this.deliveryOverrideRequestId || 0) + 1;
        this.deliveryOverrideRequestId = deliveryOverrideRequestId;

        const defaultDays = this.getDeliveryOverrideConfig().defaultBusinessDays;

        await this.updateTime({
            now: {
                dateFormatted: this.formatDeliveryOverrideDays(defaultDays),
            },
            later: false,
            hideLater: true,
        });

        const [maxDays] = await Promise.all([
            this.getMaxDeliveryOverrideDays().catch((error) => {
                console.warn("Delivery override CMS error", error);
                return defaultDays;
            }),
            super.fetchData({
                data: this.queries.DELIVERY_TIME(),
                linkParameter: `?query=copModulesDeliveryTime&type=${this.type}`,
            })
                .then((deliveryTimeData) => {
                    const { shipping } = deliveryTimeData?.data?.shipping || {};
                    if (shipping) {
                        this.vars.cheapestCourier = this.getCheapestCourier(shipping);
                        if (this.type === 'basket') {
                            this.updateCosts();
                        }
                    }
                })
                .catch((error) => {
                    console.warn("Delivery time query error", error);
                }),
        ]);

        if (this.deliveryOverrideRequestId !== deliveryOverrideRequestId) return;

        await this.updateTime({
            now: {
                dateFormatted: this.formatDeliveryOverrideDays(maxDays),
            },
            later: false,
            hideLater: true,
        });
    }

    async updateTime(options) {
        if (!this.summaryElement) return;
        if (!options) {
            await this.getDeliveryTime();
            return;
        }

        const timeContainer = this.summaryElement.querySelector(`.${this.prefix}_time`);
        if (!timeContainer) return;

        const { now, later, hideLater } = options;

        const isEnglish = /^\/en(\/|$)/i.test(window.location.pathname || "");
        const nowElement = timeContainer.querySelector(`.${this.prefix}_time__item.--now`);
        if (now && nowElement) {
            const nowValueElement = nowElement.querySelector(`.${this.prefix}_time__value`);
            if (nowValueElement) {
                nowValueElement.textContent = now.dateFormatted;
            }

            const nowLabelElement = nowElement.querySelector(`.${this.prefix}_time__label`);
            if (nowLabelElement) {
                nowLabelElement.textContent = isEnglish ? "Shipping:" : "Wysyłka:";
            }
        }

        const laterElement = timeContainer.querySelector(`.${this.prefix}_time__item.--later`);
        if (!laterElement) return;

        if (hideLater) {
            laterElement.classList.remove("--active");
        }

        if (later) {
            const laterValueElement = laterElement.querySelector(`.${this.prefix}_time__value`);
            if (laterValueElement) {
                laterValueElement.textContent = later.dateFormatted;
            }

            const laterLabelElement = laterElement.querySelector(`.${this.prefix}_time__label`);
            if (laterLabelElement) {
                laterLabelElement.textContent = isEnglish ? "Shipping (remaining products):" : "Wysyłka (pozostałe produkty):";
            }

            laterElement.classList.add("--active");
        }
    }

    async getRegisterRecaptchaToken() {
        const token = await window?.getRecaptchaToken?.();
        if (token) return `reCaptchaToken: "${token || ''}"`;
        return '';
    }

    async prepareRegisterClientInput(userOnce, userOnceRegister, name = 'RegisterClientInput') {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return `${name}: {}`;
        const serializeForm = new FormData(formElement);
        const clientDeliveryData = this.getClientDeliveryData(serializeForm);
        const clientDeliveryOtherAddressData = this.getClientDeliveryOtherAddressData(serializeForm);
        const clientBillingOtherData = this.getClientBillingOtherData(serializeForm);
        const typeData = this.getTypeData(serializeForm);
        const birthdateData = this.getBirthdateData(serializeForm);
        const taxNumberData = this.getTaxNumberData(serializeForm);
        const emailData = this.getEmailData(serializeForm);
        const loginData = this.getLoginData(serializeForm);
        const passwordData = this.getPasswordData(serializeForm);
        const saveToMailingData = this.getSaveToMailingData(serializeForm);
        const saveToSmsData = this.getSaveToSmsData(serializeForm);
        const recaptchaToken = await this.getRegisterRecaptchaToken();
        const vatCompany = this.getVatCompanyData(serializeForm);
        return `${name}: {
      clientData: {
        ${clientDeliveryData}
        ${clientDeliveryOtherAddressData}
        ${clientBillingOtherData}
        ${typeData}
        ${birthdateData}
        ${taxNumberData}
        ${emailData}
        ${saveToMailingData}
        ${saveToSmsData}
        ${vatCompany}
      }
      ${!userOnce || userOnceRegister ? `
      loginAndPassword: {
        ${loginData}
        ${passwordData}
      }
      ` : ''}
      ${recaptchaToken}
      ${userOnceRegister ? 'isOnceUserCreatingAccount: true' : ''}
      ${!userOnceRegister && userOnce ? 'isOnceUserCreatingAccount: false' : ''}
    }`;
    }

    prepareUpdateClientInput(data) {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return 'UpdateClientData: {}';
        const serializeForm = data || new FormData(formElement);
        const clientDeliveryData = this.getClientDeliveryData(serializeForm);
        const typeData = this.getTypeData(serializeForm);
        const birthdateData = this.getBirthdateData(serializeForm);
        const taxNumberData = this.getTaxNumberData(serializeForm);
        const emailData = this.getEmailData(serializeForm);
        const deliveryAddressId = this.getDeliveryAddressId(serializeForm, formElement);
        const invoiceAddressId = this.getInvoiceAddressId(serializeForm, formElement);
        const vatCompany = this.getVatCompanyData(serializeForm);

        return `UpdateClientInput: {
      ${clientDeliveryData}
      ${typeData}
      ${birthdateData}
      ${taxNumberData}
      ${emailData}
      ${deliveryAddressId}
      ${invoiceAddressId}
      ${vatCompany}
    }`;
    }

    prepareUpdateClientDeliveryOtherAddressInput() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return `UpdateDeliveryAddressInput: {}`;
        const serializeForm = new FormData(formElement);
        const input = formElement.querySelector('input[name="deliver_to_billingaddr"]');
        const type = input?.getAttribute('data-edit') === 'true' && input?.getAttribute('data-id') ? 'update' : 'insert';
        const clientDeliveryOtherAddressData = app_shop.vars.isOtherAddressChange ? this.getClientDeliveryOtherAddressData(serializeForm, type === 'update' ? 'clientDeliveryData' : 'ClientDeliveryData') : '';

        if (type === 'insert') {
            return clientDeliveryOtherAddressData ? this.queries.INSERT_CLIENT_OTHER_ADDRESS(clientDeliveryOtherAddressData) : '';
        }

        const clientDeliveryOtherAddressid = input?.getAttribute('data-id') || 0;

        return clientDeliveryOtherAddressData ? this.queries.UPDATE_CLIENT_OTHER_ADDRESS(`UpdateDeliveryAddressInput: {
      id: ${clientDeliveryOtherAddressid}
      ${clientDeliveryOtherAddressData}
    }`) : '';
    }

    prepareClientBillingOtherAddressInput() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return 'UpdateInvoiceAddressInput: {}';
        const serializeForm = new FormData(formElement);
        const input = formElement.querySelector('input[name="invoice_to_billingaddr"]');
        const clientBillingOtherAddressid = input?.getAttribute('data-id') || 0;
        const type = input?.getAttribute('data-used') === 'false' && clientBillingOtherAddressid !== 0 ? 'update' : 'insert';
        const clientBillingOtherData = app_shop.vars.isBillingOtherAddressChange ? this.getClientBillingOtherData(serializeForm, type === 'update' ? 'clientInvoiceData' : 'ClientInvoiceData') : '';

        if (type === 'insert') {
            return clientBillingOtherData ? this.queries.INSERT_CLIENT_BILLING_OTHER_ADDRESS(clientBillingOtherData) : '';
        }

        return clientBillingOtherData ? this.queries.UPDATE_CLIENT_BILLING_OTHER_ADDRESS(`UpdateInvoiceAddressInput: {
      id: ${clientBillingOtherAddressid}
      ${clientBillingOtherData}
    }`) : '';
    }

    async registerClient() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return false;
        const serializeForm = new FormData(formElement);
        if (!serializeForm.has('register_client')) return false;
        const registerClientInput = await this.prepareRegisterClientInput();
        const registerClientData = await super.fetchData({
            data: this.queries.REGISTER_CLIENT(registerClientInput),
            linkParameter: `?mutation=copModulesRegisterClient&type=${this.type}`,
        });
        return registerClientData;
    }

    setDeliveryAndBillingAddressInputs(activeDeliveryAddress, activeInvoiceAddress) {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return;
        if (activeDeliveryAddress) {
            const deliveryInput = formElement.querySelector('input[name="deliver_to_billingaddr"]');
            deliveryInput?.setAttribute('data-id', activeDeliveryAddress);
        }
        if (activeInvoiceAddress) {
            const invoiceInput = formElement.querySelector('input[name="invoice_to_billingaddr"]');
            invoiceInput?.setAttribute('data-id', activeInvoiceAddress);
        }
    }

    async updateClient() {
        const updateClientDeliveryOtherAddressInput = this.prepareUpdateClientDeliveryOtherAddressInput();
        const updateClientBillingOtherAddressInput = this.prepareClientBillingOtherAddressInput();

        if (updateClientDeliveryOtherAddressInput || updateClientBillingOtherAddressInput) {
            const updateAddressesQuery = JSON.stringify({
                query: `mutation {
          ${updateClientDeliveryOtherAddressInput}
          ${updateClientBillingOtherAddressInput}
        }`,
            });

            const updateAddressesData = await super.fetchData({
                data: updateAddressesQuery,
                linkParameter: `?mutation=copModulesUpdateClientAddresses&type=${this.type}`,
                alert: false,
            });

            const {
                data: {
                    insertDeliveryAddress: { result: { id: activeDeliveryAddress } = {} } = {},
                    insertInvoiceAddress: { result: { id: activeInvoiceAddress } = {} } = {},
                } = {},
            } = updateAddressesData || {};

            this.setDeliveryAndBillingAddressInputs(activeDeliveryAddress, activeInvoiceAddress);
        }

        const updateClientInput = this.prepareUpdateClientInput();
        if (this.vars.initUpdateClientInput === updateClientInput) return true;

        const query = JSON.stringify({
            query: `mutation {
        ${this.queries.UPDATE_CLIENT(updateClientInput)}
      }`,
        });

        const updateClientData = await super.fetchData({
            data: query,
            linkParameter: `?mutation=copModulesUpdateClient&type=${this.type}`,
            alert: false,
        });
        return updateClientData;
    }

    async setOnceOrderClient() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return false;
        const serializeForm = new FormData(formElement);
        const userOnceInput = await this.prepareRegisterClientInput(true, serializeForm.has('register_client'), 'SetUserOnceInput');
        const userOnceData = await super.fetchData({
            data: this.queries.SET_USER_ONCE(userOnceInput),
            linkParameter: `?mutation=copModulesUserOnceClient&type=${this.type}`,
        });

        if (userOnceData?.data?.setUserOnce?.status === 'success') {
            sessionStorage.setItem('userOnceData', 'true');
        }
        return userOnceData;
    }

    getDeliveryCostData(serializeForm) {
        const courier = serializeForm.get('shipping');
        const service = serializeForm.get('calendar_services');
        if (!courier && !service) return '';
        const [did, prepaid] = (service) ? service.split('-') : courier.split('-');
        return `delivery: {courierId: "${did}", prepaid: ${!!(+prepaid)}}`;
    }

    getDeliveryDivisionCostData(serializeForm) {
        const courier = serializeForm.get('shipping_division');
        const service = serializeForm.get('calendar_services_division');
        if (!courier && !service) return '';
        const [did, prepaid] = (service) ? service.split('-') : courier.split('-');
        return `deliveryDivision: {courierId: "${did}", prepaid: ${!!(+prepaid)}}`;
    }

    getForPointsCostData(serializeForm) {
        if (!serializeForm.has('shipping_for_points') && !serializeForm.has('calendar_services_points')) return '';
        const forPointsData = serializeForm.get('shipping_for_points') || serializeForm.get('calendar_services_points');
        const forPointsChoice = forPointsData === '1' ? true : forPointsData;
        return `shippingForPoints: ${forPointsChoice}`;
    }

    getForPointsDivisionCostData(serializeForm) {
        if (!serializeForm.has('shipping_for_points_division')) return '';
        const forPointsDivisionData = serializeForm.get('shipping_for_points_division');
        const forPointsDivisionChoice = forPointsDivisionData === '1' ? true : forPointsDivisionData;
        return `shippingForPointsLater: ${forPointsDivisionChoice}`;
    }

    getPaymentCostData(serializeForm) {
        const selected = serializeForm.get('payform_id');
        const first = serializeForm.get('first_payment_id');
        if (!selected && !first) return '';
        if (selected) return `paymentMethodId: ${selected}`;
        return `paymentMethodId: ${first}`;
    }

    getServicesCostData(serializeForm) {
        if (!serializeForm.has('calendar_services')) return '';
        return 'deliveryCalendarServices: true';
    }

    getServicesPointsCostData(serializeForm) {
        if (!serializeForm.has('calendar_services_points')) return '';
        return 'deliveryCalendarServicesPoints: true';
    }

    getServicesAdditionalCostData(serializeForm) {
        if (!serializeForm.has('calendar_services') && !serializeForm.has('shipping')) return '';
        const service = serializeForm.get('calendar_services')?.split?.('-')?.[2]
            || serializeForm.get('shipping')?.split?.('-')?.[2];
        if (!service) return '';
        let serviceName = 'SERVICE_WEEKEND_DELIVERY';
        if (service === '2') serviceName = 'SERVICE_SATURDAY_DELIVERY';
        if (service === '3') serviceName = 'ATYPICAL_PRODUCT_SIZE';
        return `deliveryAdditionalServicesId: ${serviceName}`;
    }

    prepareBasketCostInput() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement || this.vars.cheapestCourier) {
            const { courier: { fullId } = {} } = this.vars.cheapestCourier || {};
            if (!fullId) return 'BasketCostInput: {}';
            return `BasketCostInput: {
        delivery: {
          courierId: "${fullId.split('-')[0]}",
          prepaid: ${fullId.split('-')[1] === '1'},
        },
      }`;
        }
        const serializeForm = new FormData(formElement);
        const deliveryData = this.getDeliveryCostData(serializeForm);
        const deliveryDivisionData = this.getDeliveryDivisionCostData(serializeForm);
        const forPointsData = this.getForPointsCostData(serializeForm);
        const forPointsDivisionData = this.getForPointsDivisionCostData(serializeForm);
        const paymentData = this.getPaymentCostData(serializeForm);
        const servicesData = this.getServicesCostData(serializeForm);
        const servicesPointsData = this.getServicesPointsCostData(serializeForm);
        const servicesAdditionalData = this.getServicesAdditionalCostData(serializeForm);
        return `BasketCostInput: {
      ${deliveryData}
      ${deliveryDivisionData}
      ${forPointsData}
      ${forPointsDivisionData}
      ${paymentData}
      ${servicesData}
      ${servicesPointsData}
      ${servicesAdditionalData}
    }`;
    }

    updateWorth(basketCost) {
        const worthElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--worth`);
        if (!worthElement) return;
        const { formatted } = basketCost?.totalProductsCost || {};
        if (!formatted) {
            worthElement.classList.remove('--active');
            return;
        }
        const valueElement = worthElement.querySelector(`.${this.prefix}_costs__value`);
        if (!valueElement) return;
        valueElement.textContent = formatted;
        worthElement.classList.add('--active');
    }

    updateWorthPoints(basketCost) {
        const worthPointsElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--worth-points`);
        if (!worthPointsElement) return;
        const { value } = basketCost?.totalProductsCostAtPoints || {};
        if (!value) {
            worthPointsElement.classList.remove('--active');
            return;
        }
        const valueElement = worthPointsElement.querySelector(`.${this.prefix}_costs__value`);
        if (!valueElement) return;
        valueElement.textContent = `${value} ${this.txt['pkt']}.`;
        worthPointsElement.classList.add('--active');
    }

    updateRebate(basketCost) {
        const rebateElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--rebate`);
        if (!rebateElement) return;
        const { formatted, value } = basketCost?.totalRebateWithoutShipping || {};
        if (!formatted || !value) {
            rebateElement.classList.remove('--active');
            return;
        }
        const valueElement = rebateElement.querySelector(`.${this.prefix}_costs__value`);
        if (!valueElement) return;
        valueElement.textContent = formatted;
        rebateElement.classList.add('--active');
    }

    updatePaymentCost(basketCost) {
        const paymentCostElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--paymentcost`);
        if (!paymentCostElement) return;
        const { formatted, value } = basketCost?.prepaidCost || {};
        if (!formatted || !value) {
            paymentCostElement.classList.remove('--active');
            return;
        }
        const valueElement = paymentCostElement.querySelector(`.${this.prefix}_costs__value`);
        if (!valueElement) return;
        valueElement.textContent = formatted;
        paymentCostElement.classList.add('--active');
    }

    updateCheapestShippingCost(basketCost, elementName) {
        const shippingCostElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--${elementName}`);
        if (!shippingCostElement) return;
        const basketShippingCostName = elementName === 'shipping-to-door' ? 'cheapestShippingToDoorCourier' : 'cheapestShippingToPickupPoint'
        const { shippingCost, icon } = basketCost?.basketShippingCost?.[basketShippingCostName] || {};
        if (!shippingCost || !icon) return;

        const valueElement = shippingCostElement.querySelector(`.${this.prefix}_costs__value`);
        const imgElement = shippingCostElement.querySelector(`.${this.prefix}_costs__img`);
        if (!valueElement || !imgElement) {
            shippingCostElement.classList.remove('--active');
            return;
        }

        imgElement.setAttribute('src', icon);

        if (!shippingCost) {
            shippingCostElement.classList.add('--active');
            valueElement.textContent = `${this.txt['Gratis']}!`;
            valueElement.classList.remove('--plus');
            return;
        }
        valueElement.classList.add('--plus');

        valueElement.textContent = shippingCost;
        shippingCostElement.classList.add('--active');
    }

    updateShippingCost(basketCost, summaryBasket) {
        // wycofane do czasu realizacji porpawki w backend wracanych wartości
        /*if (this.type === 'basket') {
          this.updateCheapestShippingCost(basketCost, 'shipping-to-door');
          this.updateCheapestShippingCost(basketCost, 'shipping-to-pickup-point');
          return;
        }*/

        const shippingCostElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--shipping`);
        if (!shippingCostElement) return;
        let { formatted, value } = basketCost?.basketShippingCost?.shippingCostAfterRebate || {};
        const { shippingCostPoints: points } = basketCost?.basketShippingCost || {};

        // W widoku koszyka priorytet ma najtańszy kurier wyliczony przez API
        if (this.type === 'basket' && this.vars?.cheapestCourier?.cost?.formatted) {
            formatted = this.vars.cheapestCourier.cost.formatted;
            value = this.vars.cheapestCourier.cost.value;
        } else if (!value || value === 0) {
            const selectedDeliveryCostEl = document.querySelector('input[name="shipping"]:checked')
                ?.closest('.cop_delivery')
                ?.querySelector('.cop_delivery__cost');
            if (selectedDeliveryCostEl && selectedDeliveryCostEl.textContent.trim()) {
                formatted = selectedDeliveryCostEl.textContent.trim();
                const numMatch = formatted.replace(/\s/g, '').replace(',', '.').match(/[0-9]+(?:\.[0-9]+)?/);
                value = numMatch ? parseFloat(numMatch[0]) : 0;
            } else if (app_shop?.fn?.copModules?.vars?.shipping?.shipping) {
                const selectedInput = document.querySelector('input[name="shipping"]:checked');
                const selectedId = selectedInput?.value || app_shop.fn.copModules.vars.shipping.settings?.checked;
                const courierObj = app_shop.fn.copModules.vars.shipping.shipping.find(s => s.courier?.fullId === selectedId || s.courier?.id == selectedId);
                if (courierObj?.cost?.formatted) {
                    formatted = courierObj.cost.formatted;
                    value = courierObj.cost.value;
                }
            } else {
                const summaryGross = summaryBasket?.shipping?.cost?.gross;
                if (summaryGross?.value > 0) {
                    formatted = summaryGross.formatted;
                    value = summaryGross.value;
                }
            }
        }

        this.vars = this.vars || {};
        this.vars.shippingCostValue = value || 0;
        this.vars.shippingCostFormatted = formatted || '';

        const valueElement = shippingCostElement.querySelector(`.${this.prefix}_costs__value`);
        const labelElement = shippingCostElement.querySelector(`.${this.prefix}_costs__label`);
        if (!valueElement || !labelElement) {
            shippingCostElement.classList.remove('--active');
            return;
        }

        // W widoku koszyka, gdy nie ma wyznaczonego kuriera (np. gość bez kodu pocztowego na Czechy), nie pokazuj "Gratis!"
        if (this.type === 'basket' && (!this.vars?.cheapestCourier?.cost?.formatted || value === 0)) {
            shippingCostElement.classList.add('--active');
            labelElement.textContent = `${this.txt['Koszt przesyłki']}:`;
            const lang = document.documentElement.lang || 'pl';
            const stepText = (lang === 'cs' ? 'V dalším kroku' : (lang === 'en' ? 'Calculated at checkout' : 'W kolejnym kroku'));
            valueElement.textContent = stepText;
            valueElement.classList.remove('--plus');
            return;
        }

        if (!points && !formatted) {
            shippingCostElement.classList.add('--active');
            labelElement.textContent = `${this.txt['Koszt przesyłki']}:`;
            valueElement.textContent = `${this.txt['Gratis']}!`;
            valueElement.classList.remove('--plus');
            return;
        }
        valueElement.classList.add('--plus');

        if (points) {
            valueElement.textContent = `${points}\u00A0${this.txt.pkt}.`;
            shippingCostElement.classList.add('--active');
            return;
        }
        valueElement.textContent = formatted;
        shippingCostElement.classList.add('--active');
    }


    updateInsurance(basketCost) {
        const insuranceElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--insurance`);
        if (!insuranceElement) return;
        const { formatted, value } = basketCost?.insuranceCost || {};
        if (!formatted || !value) {
            insuranceElement.classList.remove('--active');
            return;
        }
        const valueElement = insuranceElement.querySelector(`.${this.prefix}_costs__value`);
        if (!valueElement) return;
        valueElement.textContent = formatted;
        insuranceElement.classList.add('--active');
    }

    updateBalance(basketCost) {
        const balanceElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--balance`);
        if (!balanceElement) return;
        const { formatted, value, type } = basketCost?.paymentAmountFromClientBalance || {};
        if (!formatted || !value) {
            balanceElement.classList.remove('--active');
            return;
        }
        const valueElement = balanceElement.querySelector(`.${this.prefix}_costs__value`);
        const labelElement = balanceElement.querySelector(`.${this.prefix}_costs__label`);
        if (!valueElement || !labelElement) return;
        valueElement.textContent = formatted;
        balanceElement.classList.add('--active');
        if (type !== 'underpayment') return;
        labelElement.innerHTML = `${this.txt['Opłacone z salda']}:<br>(${this.txt['niedopłata na koncie klienta']})`;
        valueElement.classList.remove('--minus');
        valueElement.classList.add('--plus');
    }

    updateDeposit(basketCost) {
        const depositElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--deposit`);
        if (!depositElement) return;
        const { formatted, value } = basketCost?.totalDeposit || {};
        if (!formatted || !value) {
            depositElement.classList.remove('--active');
            return;
        }
        const valueElement = depositElement.querySelector(`.${this.prefix}_costs__value`);
        if (!valueElement) return;
        valueElement.textContent = formatted;
        depositElement.classList.add('--active');
        if (typeof app_shop.fn.addDepositInfo !== 'function') return;
        app_shop.fn.addDepositInfo('.cop_costs__label_deposit', { priceDirect: formatted });
    }

    checkDeliveryType() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return '';
        const serializeForm = new FormData(formElement);
        if (!serializeForm.has('shipping')) return '';
        const prepaid = serializeForm.get('shipping').split('-')[1];
        const prepaidData = (prepaid === '1') ? 'prepaid' : 'dvp';
        return prepaidData;
    }

    showHideAdvance(advanceElement, type) {
        const deliveryType = this.checkDeliveryType();
        if (!deliveryType) {
            advanceElement.classList.add('--active');
            return;
        }
        if (deliveryType === type) {
            advanceElement.classList.add('--active');
            return;
        }
        if (type === 'both') {
            advanceElement.classList.add('--active');
            return;
        }
        advanceElement.classList.remove('--active');
    }

    updateAdvance(basketCost) {
        const advanceElement = this.summaryElement.querySelector(`.${this.prefix}_costs__item.--advance`);
        if (!advanceElement) return;
        // Do czasu aż PD obsłuży zaliczki PMT-1579
        const formDataObj = super.getFormDataFromSessionStorage();
        const {
            basket_cost_advance: advance,
            basket_cost_advance_type: advanceType,
        } = formDataObj || {};
        const advancePayObj = (advance) ? {
            value: advance,
            formatted: advance,
            type: advanceType || 'both',
        } : basketCost?.advancePay;
        // Do czasu aż PD obsłuży zaliczki PMT-1579 - END
        const { formatted, value, type } = advancePayObj || {};
        if (!formatted || !value) {
            advanceElement.classList.remove('--active');
            return;
        }
        const valueElement = advanceElement.querySelector(`.${this.prefix}_costs__value`);
        const labelElement = advanceElement.querySelector(`.${this.prefix}_costs__label`);
        if (!valueElement || !labelElement) return;
        this.showHideAdvance(advanceElement, type);
        valueElement.textContent = formatted;
        if (type === 'prepaid') {
            advanceElement.classList.add('--prepaid');
            advanceElement.classList.remove('--dvp');
            labelElement.innerHTML = `${this.txt['Wymagana zaliczka']}:<br>(${this.txt['przy zamówieniu za przedpłatą']})`;
            return;
        }
        if (type === 'dvp') {
            advanceElement.classList.add('--dvp');
            advanceElement.classList.remove('--prepaid');
            // eslint-disable-next-line max-len
            labelElement.innerHTML = `${this.txt['Wymagana zaliczka']}:<br>(${this.txt['przy zamówieniu z płatnością przy odbiorze']})`;
            return;
        }
        labelElement.innerHTML = `${this.txt['Wymagana zaliczka']}:`;
        advanceElement.classList.remove('--prepaid', '--dvp');
    }

    updateTotal(basketCost) {
        const totalValueElement = this.summaryElement
            .querySelector(`.${this.prefix}_total__item.--value .${this.prefix}_total__value`);
        if (!totalValueElement) return;
        let { formatted } = basketCost?.totalToPay || {};
        if (!formatted) return;

        // Jeśli backend IdoSell pominął koszt dostawy lub w widoku koszyka użyto dynamicznego kuriera:
        const worthStr = basketCost?.totalProductsCost?.formatted || '';
        const worthNumMatch = worthStr.replace(/\s/g, '').replace(',', '.').match(/[0-9]+(?:\.[0-9]+)?/);
        const productsWorth = worthNumMatch ? parseFloat(worthNumMatch[0]) : null;

        const backendShippingVal = basketCost?.basketShippingCost?.shippingCostAfterRebate?.value || 0;
        const actualShippingVal = this.vars?.shippingCostValue || 0;

        if (this.type === 'basket' && productsWorth !== null && actualShippingVal > 0) {
            const currencyMatch = formatted.match(/[^0-9\s,\.]+/);
            const currency = currencyMatch ? `\u00A0${currencyMatch[0]}` : '';
            const newTotal = (productsWorth + actualShippingVal).toFixed(2).replace('.', ',');
            formatted = `${newTotal}${currency}`;
        } else if (backendShippingVal === 0 && actualShippingVal > 0) {
            const currencyMatch = formatted.match(/[^0-9\s,\.]+/);
            const currency = currencyMatch ? `\u00A0${currencyMatch[0]}` : '';
            const totalNumMatch = formatted.replace(/\s/g, '').replace(',', '.').match(/[0-9]+(?:\.[0-9]+)?/);
            const currentTotal = totalNumMatch ? parseFloat(totalNumMatch[0]) : 0;
            const newTotal = (currentTotal + actualShippingVal).toFixed(2).replace('.', ',');
            formatted = `${newTotal}${currency}`;
        }

        totalValueElement.textContent = `${formatted}`;
        const totalSummaryProgressBar = document.querySelector(`.progress__item.--shopping-cart .progress__description`);
        if (!totalSummaryProgressBar) return;
        totalSummaryProgressBar.textContent = `${formatted}`;
        const totalSummaryButton = this.summaryElement.querySelector(`.${this.prefix}_buttons__cost`);
        if (!totalSummaryButton) return;
        totalSummaryButton.textContent = `${formatted}`;
    }

    updateTotalPoints(basketCost) {
        const totalPointsElement = this.summaryElement.querySelector(`.${this.prefix}_total__item.--points`);
        if (!totalPointsElement) return;
        const totalPointsValueElement = totalPointsElement.querySelector(`.${this.prefix}_total__value`);
        if (!totalPointsValueElement) return;
        const { value } = basketCost?.totalToPayAtPoints || {};
        if (!value) {
            totalPointsElement.classList.remove('--active');
            return;
        }
        totalPointsElement.classList.add('--active');
        totalPointsValueElement.textContent = `${value} ${this.txt['pkt']}.`;
    }

    updateSubscription(basketGroups) {
        const subscriptioElement = this.summaryElement.querySelector(`.${this.prefix}_subscription_term`);
        if (!subscriptioElement) return;
        if (!basketGroups?.length) {
            subscriptioElement.classList.remove('--active');
            return;
        }
        const subscriptionGroup = basketGroups.find((items) => items.types.includes('subscription'));
        if (!subscriptionGroup) {
            subscriptioElement.classList.remove('--active');
            return;
        }
        const { formatted, value } = subscriptionGroup?.worthTotal?.gross || {};
        if (!formatted || !value) {
            subscriptioElement.classList.remove('--active');
            return;
        }
        subscriptioElement.textContent = subscriptioElement.textContent.replace(/%s/g, formatted);
        subscriptioElement.classList.add('--active');
    }

    getDelayTime(startTime) {
        const endTime = Date.now();
        const requestDuration = endTime - startTime;
        let delayTime = 0;
        if (requestDuration < super.minDelayTime) {
            delayTime = super.minDelayTime - requestDuration;
        }
        return delayTime;
    }

    getBasketCostData() {
        const formDataObj = super.getFormDataFromSessionStorage();
        const {
            basket_cost_total: total,
            basket_cost_worth: worth,
        } = formDataObj || {};
        if (!total || !worth) return false;
        const {
            basket_cost_worth_points: worthPoints,
            basket_cost_rebate: rebate,
            basket_cost_shipping: shipping,
            basket_cost_shipping_to_door: shippingToDoor,
            basket_cost_shipping_to_pickup: shippingToPickup,
            basket_cost_shipping_to_door_icon: shippingToDoorIcon,
            basket_cost_shipping_to_pickup_icon: shippingToPickupIcon,
            basket_cost_balance: balance,
            basket_cost_balance_type: balanceType,
            basket_cost_total_points: totalPoints,
            basket_cost_subscription: subscription,
            basket_cost_advance: advance,
            basket_cost_advance_type: advanceType,
            basket_cost_deposit: deposit,
            orderMinimalWholesaleNotReached,
        } = formDataObj || {};
        const totalProductsCostAtPoints = (worthPoints) ? {
            totalProductsCostAtPoints: {
                value: worthPoints,
            },
        } : {};
        const totalRebateWithoutShipping = (rebate) ? {
            totalRebateWithoutShipping: {
                value: rebate,
                formatted: rebate,
            },
        } : {};
        const basketShippingCost = (shipping || shippingToDoor || shippingToPickup) ? {
            basketShippingCost: {
                shippingCostAfterRebate: {
                    value: shipping,
                    formatted: shipping,
                },
                cheapestShippingToDoorCourier: {
                    shippingCost: shippingToDoor,
                    icon: shippingToDoorIcon,
                },
                cheapestShippingToPickupPoint: {
                    shippingCost: shippingToPickup,
                    icon: shippingToPickupIcon,
                },
            },
        } : {};
        const paymentAmountFromClientBalance = (balance) ? {
            paymentAmountFromClientBalance: {
                value: balance,
                formatted: balance,
                type: balanceType,
            },
        } : {};
        const totalToPayAtPoints = (totalPoints) ? {
            totalToPayAtPoints: {
                value: totalPoints,
            },
        } : {};
        const advancePay = (advance) ? {
            advancePay: {
                value: advance,
                formatted: advance,
                type: advanceType || 'both',
            },
        } : {};
        const basketGroups = (subscription) ? {
            basketGroups: [{
                types: ['subscription'],
                worthTotal: {
                    gross: {
                        value: subscription,
                        formatted: subscription,
                    },
                },
            }],
        } : { basketGroups: [] };
        const totalDeposit = (deposit) ? {
            totalDeposit: {
                value: deposit,
                formatted: deposit,
            },
        } : {};
        return {
            data: {
                basket: {
                    basketCost: {
                        orderMinimalWholesaleNotReached,
                        totalToPay: {
                            formatted: total,
                        },
                        totalProductsCost: {
                            formatted: worth,
                        },
                        ...totalProductsCostAtPoints,
                        ...totalRebateWithoutShipping,
                        ...basketShippingCost,
                        ...paymentAmountFromClientBalance,
                        ...totalToPayAtPoints,
                        ...advancePay,
                        ...totalDeposit,
                    },
                    ...basketGroups,
                },
            },
        };
    }

    async updateCosts() {
        if (!this.summaryElement) return;
        this.summaryElement.classList.add('--loading');
        const basketCostInput = this.prepareBasketCostInput();
        const startTime = Date.now();
        const costData = this.getBasketCostData() || await super.fetchData({
            data: this.queries.BASKET_COST(basketCostInput),
            linkParameter: `?query=copModulesBasketCost&type=${this.type}`,
        });
        const { basketCost, basketGroups, summaryBasket } = costData?.data?.basket || {};
        if (!basketCost) return;
        const { orderMinimalWholesaleNotReached } = basketCost;
        this.vars.orderMinimalWholesaleNotReached = orderMinimalWholesaleNotReached;
        this.updateWorth(basketCost);
        this.updateWorthPoints(basketCost);
        this.updateRebate(basketCost);
        this.updatePaymentCost(basketCost);
        this.updateShippingCost(basketCost, summaryBasket);
        this.updateInsurance(basketCost);
        this.updateBalance(basketCost);
        this.updateAdvance(basketCost);
        this.updateTotal(basketCost);
        this.updateTotalPoints(basketCost);
        this.updateSubscription(basketGroups);
        this.updateDeposit(basketCost);
        setTimeout(() => {
            this.summaryElement.classList.remove('--loading');
        }, this.getDelayTime(startTime));
    }

    updateFreeDelivery() {
        const freeDeliveryElement = this.summaryElement.querySelector(`.${this.prefix}_free_delivery`);
        if (!freeDeliveryElement) return;
        if (this.type === 'order1' || this.type === 'order2' || this.type === 'oscop') {
            freeDeliveryElement.remove();
        }
    }

    updateClause(clauses = []) {
        const clausesElement = this.summaryElement.querySelector(`.${this.prefix}_clauses`);
        if (!clausesElement) return;
        if (this.type === 'basket' || this.type === 'order1') {
            clausesElement.remove();
            return;
        }
        clausesElement.innerHTML = '';
        clausesElement.classList.remove('--active');
        if (!clauses?.length) return;
        clauses.forEach((el) => {
            const { clause, type } = el;
            if (!clause) return;
            const clauseTemplateElement = document
                .getElementById(`${this.prefix}_clause_item_template`)?.content.cloneNode(true);
            if (!clauseTemplateElement) return;
            clauseTemplateElement.firstChild.innerHTML = clause;
            clauseTemplateElement.firstChild.setAttribute('data-type', type);
            clausesElement.appendChild(clauseTemplateElement);
        });
        const clauseElement = clausesElement.querySelector(`.${this.prefix}_clauses__item`);
        if (clauseElement) clausesElement.classList.add('--active');
    }

    updateAgreeTerms(dataProcessingText) {
        const termsElement = this.summaryElement.querySelector(`.${this.prefix}_terms__item.--agree`);
        if (!termsElement) return;
        const termsLabelElement = termsElement.querySelector('.f-label');
        if (!termsLabelElement || !dataProcessingText) {
            termsElement.remove();
            return;
        }
        termsLabelElement.innerHTML = dataProcessingText;
    }

    updateEmailProcessingTerms(emailProcessingText, emailProcessingChecked) {
        const termsElement = this.summaryElement.querySelector(`.${this.prefix}_terms__item.--email-processing`);
        if (!termsElement) return;
        const termsLabelElement = termsElement.querySelector('.f-label');
        const termsCheckboxElement = termsElement.querySelector('.f-control');
        if (!termsLabelElement || !termsCheckboxElement || !emailProcessingText) {
            termsElement.remove();
            return;
        }
        termsLabelElement.innerHTML = emailProcessingText;
        termsCheckboxElement.checked = emailProcessingChecked;
    }

    updateVirtualProductsTerms(virtualProducts = []) {
        const termsElement = this.summaryElement.querySelector(`.${this.prefix}_terms__item.--virtual`);
        if (!termsElement || virtualProducts.length) return;
        termsElement.remove();
    }

    updateServiceProductsTerms(serviceProducts = []) {
        const termsElement = this.summaryElement.querySelector(`.${this.prefix}_terms__item.--service`);
        if (!termsElement || serviceProducts.length) return;
        termsElement.remove();
    }

    updateEmailNewsletter(isEmailNewsletterCheckedByDefault) {
        const mailingElement = this.summaryElement.querySelector(`.${this.prefix}_terms__item.--mailing`);
        if (!mailingElement) return;
        if (app_shop.vars?.logged) {
            mailingElement.remove();
            return;
        }
        if (!isEmailNewsletterCheckedByDefault) return;
        const mailingCheckboxElement = mailingElement.querySelector('.f-control');
        if (!mailingCheckboxElement) return;
        mailingCheckboxElement.checked = true;
    }

    updateSmsNewsletter(isSmsNewsletterCheckedByDefault) {
        const smsElement = this.summaryElement.querySelector(`.${this.prefix}_terms__item.--sms`);
        if (!smsElement) return;
        if (app_shop.vars?.logged) {
            smsElement.remove();
            return;
        }
        if (!isSmsNewsletterCheckedByDefault) return;
        const smsCheckboxElement = smsElement.querySelector('.f-control');
        if (!smsCheckboxElement) return;
        smsCheckboxElement.checked = true;
    }

    updateTerms() {
        const termsElement = this.summaryElement.querySelector(`.${this.prefix}_terms`);
        if (!termsElement) return;
        if (this.type === 'basket' || this.type === 'order1') {
            termsElement.remove();
            return;
        }
        const {
            order: {
                personalDataProcessing: {
                    dataProcessingText, emailProcessingText, emailProcessingChecked,
                } = {},
            } = {},
            client: {
                registrationFormFields: {
                    isEmailNewsletterCheckedByDefault,
                    isSmsNewsletterCheckedByDefault,
                } = {},
            } = {},
        } = this.vars.settings || {};
        this.updateAgreeTerms(dataProcessingText);
        this.updateEmailNewsletter(isEmailNewsletterCheckedByDefault);
        this.updateSmsNewsletter(isSmsNewsletterCheckedByDefault);
        this.updateEmailProcessingTerms(emailProcessingText, emailProcessingChecked);
        const { products = [] } = this.vars.basket || {};
        const virtualProducts = products.filter((el) => el.data?.type === 'virtual');
        this.updateVirtualProductsTerms(virtualProducts);
        const serviceProducts = products.filter((el) => el.data?.type === 'service');
        this.updateServiceProductsTerms(serviceProducts);
    }

    updateBuyButton(buttonElement) {
        if (!buttonElement) return;
        if (this.type === 'basket' || this.type === 'order1') {
            buttonElement.remove();
            return;
        }
        const buttonTextElement = buttonElement.querySelector(`.${this.prefix}_buttons__button_text`);
        if (!buttonTextElement) return;
        const formDataObj = super.getFormDataFromSessionStorage();
        const { buy_button_text: buyButtonText = this.txt['Akceptuję, zamawiam i płacę'] } = formDataObj || {};
        if (!buyButtonText) return;
        buttonTextElement.textContent = buyButtonText;
    }

    afterChangePayment(paymentId) {
        const buttonElement = this.summaryElement.querySelector(`.${this.prefix}_buttons__button.--buy`);
        if (!buttonElement) return;
        const buttonTextElement = buttonElement.querySelector(`.${this.prefix}_buttons__button_text`);
        if (!buttonTextElement) return;
        if (paymentId !== '203') {
            buttonTextElement.textContent = this.txt['Akceptuję, zamawiam i płacę'];
            return;
        }
        buttonTextElement.textContent = this.txt['Zamawiam i płacę później'];
    }

    updateNextButton(buttonElement) {
        if (!buttonElement) return;
        if (this.type === 'order2' || this.type === 'oscop') {
            buttonElement.remove();
        }
    }

    updateExpressCheckoutButton(buttonElement) {
        if (!buttonElement) return;
        if (!this.validateOrderMinimalWholesale()) {
            buttonElement.remove();
        }
    }

    updateButtons() {
        const buttonsElement = this.summaryElement.querySelector(`.${this.prefix}_buttons`);
        if (!buttonsElement) return;
        this.updateBuyButton(buttonsElement.querySelector(`.${this.prefix}_buttons__button.--buy`));
        this.updateNextButton(buttonsElement.querySelector(`.${this.prefix}_buttons__button.--next`));
        this.updateExpressCheckoutButton(buttonsElement.querySelector('express-checkout'));
    }

    updateInpostPay(element) {
        if (!element) return;
        // Style dla przycisku InPost, które są wstrzykiwane do shadowRoot
        const inpostPayButtonStyle = (inpostPayElement) => {
            const borderRadius = getComputedStyle(inpostPayElement).getPropertyValue('--border-radius') || '0px';
            const inpostPayCSS = `
        .inpostizi-bind-button-body,
        div[role="button"],
        button {
          width: 100% !important;
          max-width: none !important;
          border-radius: ${borderRadius} !important;
        }
      `;

            const inpostPayStyleElement = document.createElement('style');
            inpostPayStyleElement.id = 'inpostPayStyle';
            inpostPayStyleElement.innerHTML = inpostPayCSS;

            // Dodawanie styli do shadowRoot
            const addStylesToShadowRoot = (shadowRoot) => {
                if (!shadowRoot.querySelector('style#inpostPayStyle')) {
                    shadowRoot.appendChild(inpostPayStyleElement.cloneNode(true));
                }
            };

            // Obserwowanie, czy shadowRoot został zaktualizowany
            const observeShadowRoot = (shadowRoot) => {
                const shadowRootObserver = new MutationObserver(() => {
                    addStylesToShadowRoot(shadowRoot);
                });
                shadowRootObserver.observe(shadowRoot, { childList: true, subtree: true });
            };

            // Sprawdzanie, czy shadowRoot został już wyrenderowany
            const checkForShadowRoot = (iziButton) => {
                const check = () => {
                    if (iziButton.shadowRoot) {
                        addStylesToShadowRoot(iziButton.shadowRoot);
                        observeShadowRoot(iziButton.shadowRoot);
                    } else {
                        requestAnimationFrame(check);
                    }
                };
                requestAnimationFrame(check);
            };

            // Obserwowanie, czy wyrenderowany został przycisk InPost
            const observer = new MutationObserver(() => {
                const inpostIziButtonElement = inpostPayElement.querySelector('inpost-izi-button');
                if (!inpostIziButtonElement) return;
                checkForShadowRoot(inpostIziButtonElement);
                observer.disconnect();
            });

            const config = { childList: true };
            observer.observe(inpostPayElement, config);
        };

        const inpostPayElement = element;

        // Style dla przycisku InPost
        inpostPayButtonStyle(inpostPayElement);

        // Wyrenderowanie przycisku płatności
        if (typeof renderInpostPayButton === 'function') {
            renderInpostPayButton('basket', 'copInpostPay');
        }
    }

    updateOneClick(element) {
        if (!element) return;
        const oneClickItems = element.querySelectorAll(`.${this.prefix}_oneclick_pay__item`);
        oneClickItems.forEach((el) => {
            if (typeof expressCheckoutApi !== 'undefined' && typeof expressCheckoutApi.basketCheckout === 'function') {
                const currentId = el.getAttribute('data-id');
                expressCheckoutApi.basketCheckout(currentId, el);
            }
        });
    }

    updateOneClicks() {
        const oneClicksElement = this.summaryElement?.querySelector(`.${this.prefix}_oneclick`);
        if (!oneClicksElement) return;
        if (this.type === 'order1'
            || this.type === 'order2'
            || this.type === 'oscop'
            || !this.validateOrderMinimalWholesale()
        ) {
            oneClicksElement.remove();
            return;
        }
        this.updateInpostPay(oneClicksElement.querySelector(`.${this.prefix}_inpost_pay`));
        this.updateOneClick(oneClicksElement.querySelector(`.${this.prefix}_oneclick_pay`));
    }

    updateSafe() {
        const safeElement = this.summaryElement.querySelector(`.${this.prefix}_safe`);
        if (!safeElement) return;
        if (this.type === 'basket' || this.type === 'order1') {
            safeElement.remove();
        }
    }

    validateOrderMinimalWholesale() {
        const orderMinimalWholesaleNotReached = this.vars?.orderMinimalWholesaleNotReached
            ?? this.getBasketCostData()?.data?.basket?.basketCost?.orderMinimalWholesaleNotReached;

        return !orderMinimalWholesaleNotReached;
    }

    orderMinimalWholesaleValidationFailed() {
        Alertek.Error(`${this.txt['Nie można przejść dalej, ponieważ wartość zamówienia nie osiągnęła minimalnej wartości hurtowej']}.`);
    }

    async validateAllData() {
        this.addLoading();
        const validOrderMinimalWholesale = this.validateOrderMinimalWholesale();
        if (!validOrderMinimalWholesale) {
            this.removeLoading();
            this.orderMinimalWholesaleValidationFailed();
            return false;
        }
        if (this.type === 'basket') return true;
        const validFormData = await this.validate.validateForm();
        if (!validFormData) {
            this.removeLoading();
            this.formValidationFailed();
            return false;
        }
        const validPayment = this.validatePayment();
        if (!validPayment) {
            this.removeLoading();
            this.paymentValidationFailed();
            return false;
        }
        const validDelivery = this.validateDelivery();
        if (!validDelivery) {
            this.removeLoading();
            this.deliveryValidationFailed();
            return false;
        }
        const validPickupPoint = this.validatePickupPoint();
        if (!validPickupPoint) {
            this.removeLoading();
            this.pickupValidationFailed();
            return false;
        }
        return true;
    }

    checkFixedBuyButton() {
        if (this.type !== 'oscop') {
            return false;
        }

        if (document.documentElement.scrollTop === 0) {
            return false;
        }

        const summaryTop = this.summaryElement.getBoundingClientRect().top;
        const buttonsHeight = this.summaryElement.querySelector(`.${this.prefix}_buttons`)?.offsetHeight || 0;
        const widnowHeight = window.innerHeight;

        if ((summaryTop - widnowHeight + buttonsHeight) <= 0) {
            return false;
        }


        return true;
    }

    async saveClient() {
        let saveClientResponse = false;
        if (app_shop.vars?.logged) {
            saveClientResponse = await this.updateClient();
        } else {
            saveClientResponse = await this.setOnceOrderClient();
        }

        if (!saveClientResponse || saveClientResponse?.errors || saveClientResponse?.data?.insertDeliveryAddress?.isError || saveClientResponse?.data?.updateClient?.isError) {
            Alertek.Error(this.txt['Wystąpił błąd w zapisie danych, zweryfikuj ich poprawność i spróbuj ponownie']);
            return false;
            //Alertek.Error(this.txt['Wystąpił błąd w zapisie danych, zweryfikuj ich poprawność w następnym kroku']);
            //return new Promise(resolve => setTimeout(resolve, 6000));
        }
        return true;
    }

    async disableInvoice() {
        if (app_shop.vars.copModulesType !== 'oscop' || !app_shop.vars?.logged) return;
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return;
        const serializeForm = new FormData(formElement);
        if (serializeForm.has('invoice_to_billingaddr')) return;
        await super.fetchData({
            data: JSON.stringify({
                query: `mutation {
          updateClient(UpdateClientInput: { activeInvoiceAddress: 0 }) { status }
        }`,
            }),
            linkParameter: `?mutation=copModulesDisableInvoice&type=${this.type}`,
            alert: false,
        });
    }

    preserveLocaleInFormAction(form) {
        if (!form) return;
        const currentAction = form.getAttribute('action') || '';
        const currentPath = window.location.pathname;

        // v33: Agresywne wykrywanie lokalizacji z pathname
        const localeMatch = currentPath.match(/^\/([a-z]{2})\//i);
        if (localeMatch) {
            const locale = localeMatch[1].toLowerCase();
            const localePrefix = `/${locale}/`;

            // Jeśli action jest relatywna i nie zaczyna się od prefixu, lub jest absolutna ale na tę samą domenę
            if (!currentAction.startsWith(localePrefix) && !currentAction.startsWith('http')) {
                const newAction = localePrefix + currentAction.replace(/^\/+/, '');
                console.log(`[SummaryCOP v33] Preserving locale: ${currentAction} -> ${newAction}`);
                form.setAttribute('action', newAction);
            } else if (currentAction.startsWith(window.location.origin)) {
                // Obsługa absolutnych URLi wskazujących na tę samą domenę
                const url = new URL(currentAction);
                if (!url.pathname.startsWith(localePrefix)) {
                    url.pathname = localePrefix + url.pathname.replace(/^\/+/, '');
                    console.log(`[SummaryCOP v33] Preserving locale (absolute): ${currentAction} -> ${url.toString()}`);
                    form.setAttribute('action', url.toString());
                }
            }
        }
    }

    async onClickNextButton(e) {
        // v33: Always prevent default to take full control of the redirection in multi-language context
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault();
        }

        if (!await this.validateAllData()) {
            return;
        }

        const { target } = e;
        super.saveFormDataToSessionStorage();

        const formSelector = this.vars.formSelector || '.basket__form';
        const formElement = document.querySelector(formSelector);

        if (!formElement) {
            console.error('[SummaryCOP v33] Form element not found for redirection');
            return;
        }

        // Zapewnij zachowanie lokalizacji w akcji formularza
        this.preserveLocaleInFormAction(formElement);

        if (app_shop.vars.copModulesType === 'order1') {
            const saveClientResponseError = await this.saveClient();
            if (!saveClientResponseError) {
                this.removeLoading();
                return false;
            }
            formElement.submit();
            return;
        }

        // Standardowe zachowanie dla koszyka (przejście do order1)
        if (!formElement.querySelector('input[name="after_basket_change"]')) {
            const inputElement = document.createElement('input');
            inputElement.type = 'hidden';
            inputElement.name = 'after_basket_change';
            inputElement.value = 'order';
            formElement.appendChild(inputElement);
        }

        formElement.submit();
    }

    async onClickBuyButton() {
        if (!await this.validateAllData()) return;
        await this.registerClient();
        await this.disableInvoice();
        this.orderCreate();
    }

    onScrollFixedBuyButton() {
        document.documentElement.classList.toggle('--cop-fixed-button', this.checkFixedBuyButton());
    }

    initEvents() {
        this.summaryElement.addEventListener('click', (e) => {
            const { target } = e;
            if (target.closest(`.${this.prefix}_buttons__button.--next`)) {
                this.onClickNextButton(e);
                return;
            }
            if (target.closest(`.${this.prefix}_buttons__button.--buy`)) {
                e.preventDefault();
                this.onClickBuyButton();
                return;
            }
        });
    }

    onFocusInput() {
        document.documentElement.classList.add('--focus');
    }

    onBlurInput() {
        if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
        document.documentElement.classList.remove('--focus');
    }

    onResizeWindow() {
        if (window.visualViewport.height < window.innerHeight) {
            document.documentElement.classList.add('--focus');
            return;
        }
        document.documentElement.classList.remove('--focus');
    }

    initFocus() {
        const inputElements = document
            .querySelectorAll(`.${this.prefix} input:not([type="checkbox"]):not([type="radio"]), .${this.prefix} textarea`);
        inputElements.forEach((input) => {
            input.addEventListener('focus', this.onFocusInput);
            input.addEventListener('blur', this.onBlurInput);
        });

        window.addEventListener('resize', this.onResizeWindow);
    }

    initEventsOnce() {
        document.addEventListener('scroll', this.onScrollFixedBuyButton.bind(this), true);
        const oldAfterAllModulesInit = app_shop.fn.copModules?.afterAllModulesInit;
        app_shop.fn.copModules.afterAllModulesInit = () => {
            oldAfterAllModulesInit?.();
            this.initFocus();
        };
    }

    afterLogin() {
        this.saveFormData();
        this.updateSmsNewsletter();
        this.updateEmailNewsletter();
    }

    saveFormData() {
        const formElement = document.querySelector(this.vars.formSelector);
        if (!this.vars.formSelector || !formElement) return;
        this.vars.initUpdateClientInput = this.prepareUpdateClientInput(new FormData(formElement));
    }

    setVatInput() {
        const formDataObj = super.getFormDataFromSessionStorage();
        const {
            vat_company,
        } = formDataObj || {};
        const vatInput = document.querySelector('#cop_terms_vat_checkbox');
        if (vat_company && vatInput) {
            vatInput.checked = true;
        }
    }

    generate() {
        const summaryTemplateElement = document.getElementById(`${this.prefix}_summary_template`)?.content.cloneNode(true);
        if (!summaryTemplateElement || !summaryTemplateElement.firstChild) return;
        const currentSummaryElement = this.summaryElement;
        this.summaryElement = summaryTemplateElement.firstChild;
        this.updateFreeDelivery();
        this.updateClause();
        this.updateTerms();
        this.updateButtons();
        this.updateSafe();
        this.initEvents();
        if (currentSummaryElement && document.body.contains(currentSummaryElement)) {
            currentSummaryElement.replaceWith(this.summaryElement);
            this.updateOneClicks();
            this.validate.reInit();
            this.saveFormData();
            return;
        }
        super.move({
            element: this.summaryElement,
            ...this.vars.move,
        });
        this.updateOneClicks();
        this.validate.reInit();
        this.saveFormData();
        this.setVatInput();
    }

    init(options = {}) {
        this.type = options.type || app_shop.vars.copModulesType || 'order1';
        this.vars = {
            afterReady: options.afterReady || (() => { }),
            move: options.move || this.vars?.move || {},
            formSelector: options.formSelector || false,
            basket: options.basket || {},
            settings: options.settings || {},
        };
        this.generate();
        this.vars.afterReady(this.summaryElement);
    }
}
try {
    app_shop.fn.copModulesSummary = new SummaryCOP();
    app_shop.vars.copModulesClasses.push(() => {
        app_shop.fn.copModulesSummary = new SummaryCOP();
    });
} catch (error) {
    window?.errorLog?.(error);
}

// --- CZ/SK B2B: Customowa logika dla koszyka (v2 — EN/PL) ---
;(function() {
    'use strict';

    // Wlasny CSS — IdoSell nie ma dostepu do tych klas, wiec nie moze ich nadpisac
    var _styleId = 'cop_czsk_style';
    if (!document.getElementById(_styleId)) {
        var st = document.createElement('style');
        st.id = _styleId;
        st.textContent = '.cop_summary .cop_terms__item.cop_czsk_visible { display: flex !important; } .cop_summary .cop_terms__item.cop_czsk_hidden { display: none !important; } .cop_czsk_notice { margin-bottom: 15px; }';
        document.head.appendChild(st);
    }

    var UE = ['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PT','RO','SK','SI','ES','SE'];
    var BLOCK_PRIVATE = UE.slice();
    var HIDE = 'cop_czsk_hidden';
    var SHOW = 'cop_czsk_visible';
    var _currentCountry = null;

    var REGION_MAP = {
        '1143020041': 'CZ', '1143020182': 'SK', '1143020003': 'PL', '1143020038': 'HR',
        '1143020016': 'AT', '1143020022': 'BE', '1143020033': 'BG', '1143020051': 'EE',
        '1143020057': 'FR', '1143020062': 'GR', '1143020075': 'ES', '1143020076': 'NL',
        '1143020116': 'LT', '1143020118': 'LV', '1143020143': 'DE', '1143020169': 'RO',
        '1143020183': 'SI', '1143020217': 'HU', '1143020220': 'IT', '1143020040': 'CY',
        '1143020042': 'DK', '1143020056': 'FI', '1143020080': 'IE', '1143020117': 'LU',
        '1143020126': 'MT', '1143020163': 'PT', '1143020193': 'SE',
    };

    function getLang() {
        var p = location.pathname;
        if (p.indexOf('/en/') === 0) return 'en';
        if (p.indexOf('/cs/') === 0) return 'cs';
        return 'pl';
    }

    function regionToCountry(sel) {
        if (!sel || sel.selectedIndex < 0) return null;
        var val = sel.options[sel.selectedIndex].value;
        if (val && val.length === 2) return val.toUpperCase();
        if (REGION_MAP[val]) return REGION_MAP[val];
        var txt = sel.options[sel.selectedIndex].text;
        if (/Czech|Česko|Česká|Czech Republic|Czechia/i.test(txt)) return 'CZ';
        if (/Slovak|S\u0142owacja|Slovensko|Slovakia/i.test(txt)) return 'SK';
        if (/Pol|Polska|Poland/i.test(txt)) return 'PL';
        return null;
    }

    function getCountry() {
        var sel = document.querySelector('select[name="country"]:not([disabled])');
        if (!sel || sel.selectedIndex < 0) {
            var lang = getLang();
            if (lang === 'cs') return 'CZ';
            try {
                var geo = window.app_shop && window.app_shop.vars && app_shop.vars.geoipCountryCode;
                if (geo) return geo.toUpperCase();
            } catch(e) {}
            return _currentCountry || 'PL';
        }
        var c = regionToCountry(sel);
        if (c) return c;
        var val = sel.options[sel.selectedIndex].value;
        if (/^\d+$/.test(val)) return 'NON_EU';
        if (val && val.length === 2) return 'NON_EU';
        return _currentCountry || 'PL';
    }

    function applyVatVisibility(vatEl, show) {
        if (!vatEl) return;
        if (show) {
            vatEl.classList.remove(HIDE);
            vatEl.classList.add(SHOW);
        } else {
            vatEl.classList.remove(SHOW);
            vatEl.classList.add(HIDE);
        }
    }

    function applyState(country) {
        _currentCountry = country;

        var vatEl = document.querySelector('.cop_terms__item.--vat');
        var nextBtn = document.querySelector('button.cop_buttons__button.--next');

        var oldNotice = document.querySelector('.cop_czsk_notice');
        if (oldNotice) oldNotice.remove();

        var lang = getLang();

        if (country === 'PL') {
            applyVatVisibility(vatEl, false);
            var cb = vatEl && vatEl.querySelector('#cop_terms_vat_checkbox');
            if (cb) cb.disabled = true;
            if (nextBtn) nextBtn.disabled = false;
        } else if (BLOCK_PRIVATE.indexOf(country) !== -1) {
            applyVatVisibility(vatEl, true);
            var cb = vatEl && vatEl.querySelector('#cop_terms_vat_checkbox');
            if (cb) {
                cb.disabled = false;
                if (!cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
            if (nextBtn) nextBtn.disabled = false;
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
            applyVatVisibility(vatEl, true);
            var cb = vatEl && vatEl.querySelector('#cop_terms_vat_checkbox');
            if (cb) cb.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            showNotice(lang === 'en'
                ? 'Unfortunately we cannot ship to your country. Please contact us to arrange shipping terms.'
                : 'Niestety nie mo\u017Cemy zrealizowa\u0107 zam\u00F3wienia do Twojego kraju. Skontaktuj si\u0119 z nami w celu ustalenia warunk\u00F3w wysy\u0142ki.',
                'error');
        }
    }

    function showNotice(msg, type) {
        var old = document.querySelector('.cop_czsk_notice');
        if (old) old.remove();
        var wrapper = document.querySelector('.summary_wrapper');
        if (!wrapper) return;
        var el = document.createElement('div');
        el.className = 'cop_czsk_notice --' + (type || 'info');
        el.textContent = msg;
        wrapper.parentNode.insertBefore(el, wrapper);
    }

    // --- INIT ---
    (function tryInit() {
        var tries = 0;
        var timer = setInterval(function() {
            tries++;
            var c = getCountry();
            var vatEl = document.querySelector('.cop_terms__item.--vat');
            if ((c && vatEl) || tries > 30) {
                clearInterval(timer);
                applyState(c || 'PL');
            }
        }, 100);
    })();

    // --- EVENT: zmiana kraju ---
    document.addEventListener('change', function(e) {
        if (e.target && e.target.name === 'country') {
            applyState(getCountry());
        }
    });

    // --- POLLING: obrona przed IdoSell re-renderem DOM ---
    setInterval(function() {
        var c = getCountry();
        if (c !== _currentCountry) {
            applyState(c);
            return;
        }

        var vatEl = document.querySelector('.cop_terms__item.--vat');
        var lang = getLang();

        if (c === 'PL') {
            if (vatEl) {
                if (!vatEl.classList.contains(HIDE)) {
                    vatEl.classList.remove(SHOW);
                    vatEl.classList.add(HIDE);
                }
                var cb = vatEl.querySelector('#cop_terms_vat_checkbox');
                if (cb) cb.disabled = true;
            }
            var notice = document.querySelector('.cop_czsk_notice');
            if (notice) notice.remove();
        } else if (BLOCK_PRIVATE.indexOf(c) !== -1) {
            if (vatEl) {
                if (!vatEl.classList.contains(SHOW)) {
                    vatEl.classList.remove(HIDE);
                    vatEl.classList.add(SHOW);
                }
                var cb = vatEl.querySelector('#cop_terms_vat_checkbox');
                if (cb && cb.disabled) {
                    cb.disabled = false;
                }
            }
            if (!document.querySelector('.cop_czsk_notice')) {
                var msg;
                if (c === 'CZ' || c === 'SK') {
                    msg = lang === 'en'
                        ? 'Orders from Czechia and Slovakia \u2014 you may order without VAT after EU VAT verification.'
                        : 'Zakupy dla firm z Czech i S\u0142owacji \u2014 mo\u017Cesz zam\u00F3wi\u0107 bez VAT po weryfikacji VAT UE.';
                } else {
                    msg = lang === 'en'
                        ? 'You are ordering from an EU country. You may order without VAT after EU VAT verification. Contact us if you have questions.'
                        : 'Zamawiasz z kraju UE. Mo\u017Cesz zam\u00F3wi\u0107 bez VAT po weryfikacji VAT UE. W razie pyta\u0144 skontaktuj si\u0119 z nami.';
                }
                showNotice(msg, 'info');
            }
        } else {
            if (vatEl) {
                if (!vatEl.classList.contains(SHOW)) {
                    vatEl.classList.remove(HIDE);
                    vatEl.classList.add(SHOW);
                }
                var cb = vatEl.querySelector('#cop_terms_vat_checkbox');
                if (cb) cb.disabled = true;
            }
            var nextBtn = document.querySelector('button.cop_buttons__button.--next');
            if (nextBtn && !nextBtn.disabled) {
                nextBtn.disabled = true;
            }
        }
    }, 100);
})();
