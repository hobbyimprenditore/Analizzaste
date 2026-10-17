// Analizzaste — modulo consulenze (da aggiungere al Worker esistente).
// Nessuna chiamata a Claude: solo inoltro richieste e risposte via Resend.
//
// Variabili d'ambiente richieste nel Worker:
//   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY  (già presenti)
//   RESEND_API_KEY        chiave API Resend, solo invio (da impostare come segreto)
//   ADMIN_EMAIL           analizzaste@gmail.com
//   FROM_EMAIL            richieste@analizzaste.it  (dominio verificato su Resend)

const TIPI = ['legale', 'tecnica', 'quotazione', 'investitore', 'amministratore'];
const TIPI_CON_ZONA = ['quotazione', 'amministratore'];
const REPLY_TO = 'richieste@analizzaste.it';
const MAX_RISPOSTA = 8000;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const cors = {
  'Access-Control-Allow-Origin': 'https://analizzaste.it',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Vary': 'Origin',
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', ...cors } });
}

function sb(env, path, init = {}) {
  return fetch(`${env.SUPABASE_URL}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
      ...(init.headers || {}),
    },
  });
}

async function utenteDaToken(request, env) {
  const auth = request.headers.get('Authorization');
  if (!auth) return null;
  const r = await fetch(`${env.SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: env.SUPABASE_ANON_KEY, Authorization: auth },
  });
  if (!r.ok) return null;
  return r.json();
}

async function eAdmin(userId, env) {
  const r = await sb(env, `profiles?id=eq.${encodeURIComponent(userId)}&select=is_admin`);
  const d = await r.json();
  return !!(d && d[0] && d[0].is_admin);
}

async function inviaEmail(env, { to, subject, text, replyTo, attachments }) {
  const body = { from: `Analizzaste <${env.FROM_EMAIL}>`, to: [to], subject, text };
  if (replyTo) body.reply_to = replyTo;
  if (attachments) body.attachments = attachments;
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`Resend ${r.status}`);
  return r.json();
}

// POST /consulenza — il cliente sceglie tipo, zona e professionista; la piattaforma inoltra.
export async function richiestaConsulenza(request, env) {
  const user = await utenteDaToken(request, env);
  if (!user) return json({ error: 'Devi effettuare il login.' }, 401);

  let b;
  try { b = await request.json(); } catch { return json({ error: 'Richiesta non valida.' }, 400); }

  if (!TIPI.includes(b.tipo)) return json({ error: 'Tipo di consulenza non valido.' }, 400);
  if (!UUID_RE.test(b.professionista_id || '')) return json({ error: 'Scegli un professionista.' }, 400);
  if (!EMAIL_RE.test(b.email || '')) return json({ error: 'Email non valida.' }, 400);
  if (b.consenso !== true) return json({ error: 'Serve il consenso per inviare il report.' }, 400);
  if (TIPI_CON_ZONA.includes(b.tipo) && (!b.provincia || !b.regione)) {
    return json({ error: 'Zona obbligatoria per questa consulenza.' }, 400);
  }

  // Il professionista deve esistere, essere attivo e del tipo richiesto.
  const pr = await sb(env, `professionisti?id=eq.${b.professionista_id}&attivo=eq.true&select=id,nome,email,tipo`);
  const [prof] = await pr.json();
  if (!prof || prof.tipo !== b.tipo) return json({ error: 'Professionista non disponibile.' }, 400);

  // Il report deve appartenere all'utente che lo invia.
  let reportData = null;
  if (b.report_id) {
    if (!UUID_RE.test(b.report_id)) return json({ error: 'Report non valido.' }, 400);
    const rr = await sb(env, `reports?id=eq.${b.report_id}&user_id=eq.${user.id}&select=report_data,created_at`);
    const [rep] = await rr.json();
    if (!rep) return json({ error: 'Report non trovato.' }, 404);
    reportData = rep.report_data;
  }

  const ins = await sb(env, 'richieste_consulenza', {
    method: 'POST',
    body: JSON.stringify({
      user_id: user.id,
      tipo: b.tipo,
      professionista_id: prof.id,
      email_cliente: b.email,
      regione: b.regione || null,
      provincia: b.provincia || null,
      report_id: b.report_id || null,
      stato: 'inviata',
    }),
  });
  const [riga] = await ins.json();
  if (!riga) return json({ error: 'Errore temporaneo, riprova.' }, 503);

  const testo = [
    `Nuova richiesta di consulenza (${b.tipo}).`,
    `Zona: ${b.provincia || '—'}${b.regione ? ' (' + b.regione + ')' : ''}.`,
    `Rispondi a questa email indicando il costo della prima consulenza e il metodo di pagamento.`,
    `Il cliente non ha ricevuto i tuoi contatti: risponderemo noi al cliente dopo verifica.`,
  ].join('\n\n');

  const attachments = reportData
    ? [{ filename: `report-${riga.id}.json`, content: btoa(unescape(encodeURIComponent(JSON.stringify(reportData)))) }]
    : undefined;

  await inviaEmail(env, {
    to: prof.email,
    subject: `[Consulenza ${riga.id}] Richiesta di ${b.tipo}`,
    text: testo,
    replyTo: REPLY_TO,
    attachments,
  });

  return json({ ok: true, id: riga.id });
}

// POST /consulenza/approva — solo admin: inoltra la risposta al cliente e registra il prezzo.
export async function approvaRisposta(request, env) {
  const user = await utenteDaToken(request, env);
  if (!user || !(await eAdmin(user.id, env))) return json({ error: 'Non autorizzato.' }, 403);

  let b;
  try { b = await request.json(); } catch { return json({ error: 'Richiesta non valida.' }, 400); }
  if (!UUID_RE.test(b.id || '')) return json({ error: 'ID non valido.' }, 400);
  const prezzo = Number(b.prezzo);
  if (!(prezzo >= 0)) return json({ error: 'Prezzo non valido.' }, 400);

  const r = await sb(env, `richieste_consulenza?id=eq.${b.id}&select=*`);
  const [richiesta] = await r.json();
  if (!richiesta || richiesta.stato !== 'risposta_ricevuta') {
    return json({ error: 'Nessuna risposta da approvare.' }, 400);
  }

  await inviaEmail(env, {
    to: richiesta.email_cliente,
    subject: `La tua richiesta di consulenza (${richiesta.tipo})`,
    text: `${richiesta.risposta_professionista}\n\nPrezzo indicato dal professionista: ${prezzo.toFixed(2)} EUR.\nIl pagamento non è gestito dalla piattaforma: seguilo direttamente con il professionista.`,
  });

  await sb(env, `richieste_consulenza?id=eq.${b.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ stato: 'approvata', prezzo_richiesto: prezzo, updated_at: new Date().toISOString() }),
  });

  return json({ ok: true });
}

// Email in arrivo su richieste@analizzaste.it (Email Routing → questo Worker).
// La risposta del professionista va all'admin, mai direttamente al cliente.
export async function riceviRispostaProfessionista(message, env) {
  const oggetto = message.headers.get('subject') || '';
  const m = oggetto.match(/\[Consulenza ([0-9a-f-]{36})\]/i);
  const raw = await new Response(message.raw).text();
  const testo = raw.slice(0, MAX_RISPOSTA);

  if (!m || !UUID_RE.test(m[1])) {
    await inviaEmail(env, { to: env.ADMIN_EMAIL, subject: `Email non collegata a una richiesta: ${oggetto}`, text: testo });
    return;
  }

  await sb(env, `richieste_consulenza?id=eq.${m[1]}`, {
    method: 'PATCH',
    body: JSON.stringify({ stato: 'risposta_ricevuta', risposta_professionista: testo, updated_at: new Date().toISOString() }),
  });

  await inviaEmail(env, {
    to: env.ADMIN_EMAIL,
    subject: `Risposta da approvare — consulenza ${m[1]}`,
    text: `Il professionista ha risposto. Controlla la risposta nel pannello admin e approva l'inoltro al cliente.\n\n---\n${testo}`,
  });
}

export function corsPreflight() {
  return new Response(null, { headers: cors });
}
