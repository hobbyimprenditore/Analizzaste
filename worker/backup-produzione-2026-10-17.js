// Analizzaste — Worker Cloudflare (versione rinforzata, 01/10/2026)
// Copia di sicurezza del codice in produzione prima di aggiungere il modulo consulenze.
// Versione Cloudflare: a2d865d264f9b765f1462f7821e99f9d366eaf053021755cee1ebc05dd2f
// Ripristino: incollare questo file nell'editor del Worker e fare Deploy.

const SUPABASE_URL = 'https://hvmnernovucnsksszsbe.supabase.co';

// Modello forzato lato server: il client NON può scegliere quale modello usare.
const MODEL = 'claude-haiku-4-5-20251001';
const MAX_TOKENS_CAP = 3000;
const MAX_BODY_BYTES = 20 * 1024 * 1024; // 20 MB (PDF in base64 compresi)
const TIPI_GRATUITI = ['unione', 'quotazione'];
const WEB_SEARCH_TOOL = { type: 'web_search_20250305', name: 'web_search', max_uses: 3 };
const PAYPAL_RECEIVER = 'hobbyimprenditore@gmail.com';
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const corsHeaders = {
  'Access-Control-Allow-Origin': 'https://analizzaste.it',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Vary': 'Origin',
};

function jsonError(message, status) {
  return new Response(JSON.stringify({ error: { message } }), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders }
  });
}

function sbHeaders(env, extra) {
  return {
    'apikey': env.SUPABASE_SERVICE_ROLE_KEY,
    'Authorization': `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    ...(extra || {})
  };
}

async function rpc(env, fn, args) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: sbHeaders(env, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(args)
  });
  if (!r.ok) throw new Error(`RPC ${fn} fallita: ${r.status}`);
  const t = await r.text();
  return t ? JSON.parse(t) : null;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }
    if (request.method === 'POST' && url.pathname === '/ipn') {
      return handleIPN(request, env);
    }
    if (request.method === 'POST' && url.pathname === '/') {
      return handleClaude(request, env);
    }
    return new Response('Not Found', { status: 404, headers: corsHeaders });
  }
};

async function handleIPN(request, env) {
  const body = await request.text();
  if (body.length > 20000) return new Response('Too large', { status: 413 });

  // Verifica con PayPal che il messaggio sia autentico
  const verifyResponse = await fetch('https://ipnpb.paypal.com/cgi-bin/webscr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'analizzaste-ipn' },
    body: 'cmd=_notify-validate&' + body
  });
  const verifyText = await verifyResponse.text();
  if (verifyText.trim() !== 'VERIFIED') {
    return new Response('Invalid', { status: 400 });
  }

  const params = new URLSearchParams(body);
  const paymentStatus = params.get('payment_status');
  const custom = (params.get('custom') || '').trim();
  const amount = parseFloat(params.get('mc_gross') || '0');
  const currency = params.get('mc_currency');
  const receiverEmail = (params.get('receiver_email') || '').toLowerCase();
  const txnId = params.get('txn_id');

  // Rispondiamo sempre 200 a PayPal, ma accreditiamo solo pagamenti validi
  const ok = new Response('OK', { status: 200 });
  if (paymentStatus !== 'Completed') return ok;
  if (receiverEmail !== PAYPAL_RECEIVER) return ok;
  if (currency !== 'EUR') return ok;               // evita pagamenti in valute "economiche"
  if (!UUID_RE.test(custom) || !txnId) return ok;
  if (!(amount >= 1)) return ok;

  const creditsToAdd = Math.floor(amount);
  try {
    // La funzione nel database accredita una sola volta per ogni txn_id
    await rpc(env, 'accredita_donazione', {
      p_user: custom,
      p_crediti: creditsToAdd,
      p_txn: txnId,
      p_note: `Donazione automatica €${amount} (txn: ${txnId})`
    });
  } catch (e) {
    // Errore temporaneo: rispondendo 500 PayPal riproverà più tardi (il doppio accredito è comunque impedito)
    return new Response('Retry', { status: 500 });
  }
  return ok;
}

async function handleClaude(request, env) {
  // 1) Token Supabase valido
  const authHeader = request.headers.get('Authorization');
  if (!authHeader) return jsonError('Devi effettuare il login.', 401);

  const len = parseInt(request.headers.get('Content-Length') || '0', 10);
  if (len > MAX_BODY_BYTES) return jsonError('File troppo grande.', 413);

  const userResp = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { 'apikey': env.SUPABASE_ANON_KEY, 'Authorization': authHeader }
  });
  if (!userResp.ok) return jsonError('Sessione non valida, effettua di nuovo il login.', 401);
  const user = await userResp.json();
  const userId = user.id;

  // 2) Leggi la richiesta: teniamo SOLO i campi che servono
  let raw;
  try { raw = await request.text(); } catch { return jsonError('Richiesta non valida.', 400); }
  if (raw.length > MAX_BODY_BYTES) return jsonError('File troppo grande.', 413);
  let bodyJson;
  try { bodyJson = JSON.parse(raw); } catch { return jsonError('Richiesta non valida.', 400); }
  if (!Array.isArray(bodyJson.messages) || bodyJson.messages.length === 0 || bodyJson.messages.length > 20) {
    return jsonError('Richiesta non valida.', 400);
  }
  const tipo = TIPI_GRATUITI.includes(bodyJson.tipo) ? bodyJson.tipo : 'file';
  const gratuita = tipo !== 'file';

  const anthropicBody = {
    model: MODEL,
    max_tokens: Math.min(Number(bodyJson.max_tokens) || MAX_TOKENS_CAP, MAX_TOKENS_CAP),
    messages: bodyJson.messages,
  };
  if (typeof bodyJson.system === 'string') anthropicBody.system = bodyJson.system.slice(0, 20000);
  if (tipo === 'quotazione' && Array.isArray(bodyJson.tools) && bodyJson.tools.length) {
    anthropicBody.tools = [WEB_SEARCH_TOOL]; // definito dal server, non dal client
  }

  // 3) Amministratore? -> nessun controllo sui crediti
  const profResp = await fetch(
    `${SUPABASE_URL}/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}&select=is_admin,is_blocked`,
    { headers: sbHeaders(env) }
  );
  const profData = await profResp.json();
  const isAdmin = !!(profData && profData[0]?.is_admin);
  if (profData && profData[0]?.is_blocked) return jsonError('Account sospeso.', 403);

  // 4) Scala il credito PRIMA della chiamata, in modo atomico
  if (!isAdmin) {
    let scalato = false;
    try { scalato = await rpc(env, 'scala_credito', { p_user: userId, p_gratuita: gratuita }); }
    catch { return jsonError('Errore temporaneo, riprova.', 503); }
    if (!scalato) {
      return gratuita
        ? jsonError('Carica e analizza prima un file per usare questa funzione.', 402)
        : jsonError('Crediti esauriti. Ricarica per continuare.', 402);
    }
  }

  // 5) Chiamata a Claude
  let response, responseBody;
  try {
    response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify(anthropicBody)
    });
    responseBody = await response.text();
  } catch {
    response = null;
  }

  // 6) Se Claude fallisce, restituiamo il credito
  if ((!response || !response.ok) && !isAdmin) {
    try { await rpc(env, 'rimborsa_credito', { p_user: userId, p_gratuita: gratuita }); } catch {}
  }
  if (!response) return jsonError('Servizio di analisi non raggiungibile, riprova.', 502);

  return new Response(responseBody, {
    status: response.status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders }
  });
}
