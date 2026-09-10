// engine_server.js
// Fastify HTTP API Server dla lekkiego silnika JS
// Uruchamia: node engine_server.js
// API na porcie 3000

const Fastify = require('fastify');
const { DataDomeEngine } = require('./datadome_engine.js');
const { IncogniaExtendedEngine } = require('./incognia_engine_extended.js');
const HAR_FINGERPRINT = require('./HAR_FINGERPRINT.json');

const fastify = Fastify({ logger: true });

// Globalne instancje silników
let datadomeEngine = null;
let incogniaEngine = null;

// === HEALTH CHECK ===
fastify.get('/health', async () => {
  return {
    status: 'ok',
    datadome: !!datadomeEngine,
    incognia: !!incogniaEngine,
    incogniaState: incogniaEngine?.getState()
  };
});

// === DATADOME ENDPOINTS ===

// Inicjalizuj DataDome z fingerprintem z HAR
fastify.post('/datadome/init', async (request, reply) => {
  try {
    const customFp = request.body?.fingerprint || HAR_FINGERPRINT;
    datadomeEngine = DataDomeEngine.init(customFp);
    return { success: true, sessionId: datadomeEngine.sessionId, clientId: datadomeEngine.clientId };
  } catch (e) {
    reply.code(500);
    return { success: false, error: e.message };
  }
});

// Pobierz kontekst requestu (cookies + headers)
fastify.post('/datadome/context', async (request, reply) => {
  if (!datadomeEngine) {
    reply.code(400);
    return { success: false, error: 'DataDome not initialized' };
  }
  const { url, method } = request.body;
  if (!url || !method) {
    reply.code(400);
    return { success: false, error: 'url and method required' };
  }
  return { success: true, context: datadomeEngine.getRequestContext(url, method) };
});

// Behavioral simulation
fastify.post('/datadome/behavioral/mouse-move', async (request, reply) => {
  if (!datadomeEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const { x, y, duration } = request.body;
  datadomeEngine.simulateMouseMove(x, y, duration);
  return { success: true };
});

fastify.post('/datadome/behavioral/click', async (request, reply) => {
  if (!datadomeEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const { x, y } = request.body;
  datadomeEngine.simulateClick(x, y);
  return { success: true };
});

fastify.post('/datadome/behavioral/scroll', async (request, reply) => {
  if (!datadomeEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const { deltaY } = request.body;
  datadomeEngine.simulateScroll(deltaY);
  return { success: true };
});

fastify.post('/datadome/behavioral/key-press', async (request, reply) => {
  if (!datadomeEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const { key } = request.body;
  datadomeEngine.simulateKeyPress(key);
  return { success: true };
});

// Fingerprint beacon (dla /dd.vinted.lt/js)
fastify.get('/datadome/beacon', async (request, reply) => {
  if (!datadomeEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  return { success: true, beacon: datadomeEngine.getFingerprintBeacon() };
});

// Challenge solving
fastify.post('/datadome/challenge/solve', async (request, reply) => {
  if (!datadomeEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const result = await datadomeEngine.solveChallenge(request.body);
  return { success: true, result };
});

// === INCOGNIA ENDPOINTS ===

// Inicjalizuj Incognia
fastify.post('/incognia/init', async (request, reply) => {
  try {
    const config = request.body || {};
    incogniaEngine = new IncogniaExtendedEngine(config);
    await incogniaEngine.init();
    return { success: true, state: incogniaEngine.getState() };
  } catch (e) {
    reply.code(500);
    return { success: false, error: e.message };
  }
});

// Generuj x-incognia-request-token
fastify.post('/incognia/request-token', async (request, reply) => {
  if (!incogniaEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const token = await incogniaEngine.generateRequestToken();
  return { success: true, token };
});

// Pobierz consume payload (type: 'pls' | 'it')
fastify.post('/incognia/consume-payload', async (request, reply) => {
  if (!incogniaEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  const { type } = request.body;
  const payload = await incogniaEngine.buildConsumePayload(type || 'pls');
  return { success: true, payload };
});

// Dodaj interakcję do bufora
fastify.post('/incognia/interaction', async (request, reply) => {
  if (!incogniaEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  incogniaEngine.addInteraction(request.body);
  return { success: true };
});

// Pobierz stan
fastify.get('/incognia/state', async (request, reply) => {
  if (!incogniaEngine) { reply.code(400); return { success: false, error: 'Not initialized' }; }
  return { success: true, state: incogniaEngine.getState() };
});

// Zatrzymaj
fastify.post('/incognia/stop', async (request, reply) => {
  if (incogniaEngine) incogniaEngine.stop();
  return { success: true };
});

// === CHECKOUT HELPER ===

// Buduj payload dla /checkout/build
fastify.post('/checkout/build-payload', async (request, reply) => {
  const { itemId, quantity, fingerprint, incogniaState } = request.body;
  if (!itemId) { reply.code(400); return { success: false, error: 'itemId required' }; }

  const payload = {
    item_id: parseInt(itemId),
    quantity: quantity || 1,
    checkout_type: 'buy_now',
    currency: 'PLN',
    protection_fee: true,
    payment_method: 'wallet',
    browser_info: {
      user_agent: fingerprint?.navigator?.userAgent || HAR_FINGERPRINT.navigator.userAgent,
      screen_width: fingerprint?.screen?.width || HAR_FINGERPRINT.screen.width,
      screen_height: fingerprint?.screen?.height || HAR_FINGERPRINT.screen.height,
      timezone_offset: fingerprint?.timezone?.timezoneOffset || HAR_FINGERPRINT.timezone.timezoneOffset,
      language: fingerprint?.navigator?.language || HAR_FINGERPRINT.navigator.language,
    }
  };
  return { success: true, payload };
});

// Buduj kroki PUT /checkout
fastify.post('/checkout/steps', async (request, reply) => {
  const { purchaseId } = request.body;
  if (!purchaseId) { reply.code(400); return { success: false, error: 'purchaseId required' }; }

  const steps = [
    { // Initial
      endpoint: `PUT /api/v2/purchases/${purchaseId}/checkout`,
      body: { components: { additional_service: {}, payment_method: {}, shipping_address: {}, shipping_pickup_options: {}, shipping_pickup_details: {} } }
    },
    { // Payment method
      endpoint: `PUT /api/v2/purchases/${purchaseId}/checkout`,
      body: { components: { additional_service: {}, payment_method: { card_id: null, pay_in_method_id: "12" }, shipping_address: {}, shipping_pickup_options: {}, shipping_pickup_details: {} } }
    },
    { // Shipping pickup
      endpoint: `PUT /api/v2/purchases/${purchaseId}/checkout`,
      body: { components: { additional_service: {}, payment_method: {}, shipping_address: {}, shipping_pickup_options: { pickup_type: 1 }, shipping_pickup_details: {} } }
    },
    { // Shipping rate
      endpoint: `PUT /api/v2/purchases/${purchaseId}/checkout`,
      body: { components: { additional_service: {}, payment_method: {}, shipping_address: {}, shipping_pickup_options: {}, shipping_pickup_details: { rate_uuid: "9c6994ca-684b-4a27-8d1b-1a75d01c7e84" } } }
    }
  ];
  return { success: true, steps };
});

// Generuj payment token
fastify.post('/checkout/payment-token', async (request, reply) => {
  if (!incogniaEngine) { reply.code(400); return { success: false, error: 'Incognia not initialized' }; }
  const { checksum } = request.body || {};
  const token = await incogniaEngine.generateRequestToken();
  return {
    success: true,
    token,
    paymentBody: {
      checksum: checksum || "81043dda779dede26e8b40630aaf2c51|4f2ff5adfdcf999ed4a3e9d1c47afe91",
      payment_options: {
        browser_info: {
          language: "pl",
          color_depth: 24,
          java_enabled: false,
          screen_height: 1080,
          screen_width: 1920,
          timezone_offset: -120
        }
      }
    }
  };
});

// === START SERVER ===
const start = async () => {
  try {
    await fastify.listen({ port: 3000, host: '0.0.0.0' });
    console.log('🚀 Engine Server running on http://localhost:3000');
    console.log('Endpoints:');
    console.log('  GET  /health');
    console.log('  POST /datadome/init');
    console.log('  POST /datadome/context');
    console.log('  POST /datadome/behavioral/*');
    console.log('  GET  /datadome/beacon');
    console.log('  POST /incognia/init');
    console.log('  POST /incognia/request-token');
    console.log('  POST /incognia/consume-payload');
    console.log('  POST /checkout/build-payload');
    console.log('  POST /checkout/steps');
    console.log('  POST /checkout/payment-token');
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();