#!/usr/bin/env python3
"""Email del sabato alle 9: a ogni iscritto alla newsletter con un'area di interesse
manda le aste nuove della settimana e quelle in arrivo nella sua zona.

Gira nella GitHub Action "Email aste del sabato". Usa solo la libreria standard.

Variabili d'ambiente:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  (obbligatorie)
  RESEND_API_KEY                           (obbligatoria, salvo con --anteprima)
  EMAIL_MITTENTE   default "Analizzaste <aste@analizzaste.it>" (dominio verificato su Resend)

Opzioni:
  --forza             invia anche se non è sabato dopo le 9 (ora italiana)
  --anteprima CARTELLA non invia: salva ogni email come file HTML in CARTELLA
"""
import datetime
import html
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

SITO = 'https://analizzaste.it'
RESEND = 'https://api.resend.com/emails'
USER_AGENT = 'analizzaste.it/1.0 (+https://analizzaste.it)'
ROMA = ZoneInfo('Europe/Rome')
GIORNI_NUOVE = 7        # "nuove": pubblicate sul PVP negli ultimi 7 giorni
GIORNI_PROSSIME = 14    # "in arrivo": asta nei prossimi 14 giorni
MAX_PER_SEZIONE = 12

CATEGORIE = {'IMMOBILE_RESIDENZIALE': ('R', 'Residenziale'), 'IMMOBILE_COMMERCIALE': ('C', 'Commerciale'),
             'IMMOBILE_INDUSTRIALE': ('I', 'Industriale'), 'IMPIANTO_SPORTIVO': ('S', 'Sportivo')}
DISPONIBILITA = {'LIBER': 'Libero', 'OCCUP': 'Occupato', 'OCCST': 'Occupato senza titolo',
                 'INCOR': 'In corso di liberazione'}


def log(msg):
    print(time.strftime('%H:%M:%S'), msg, flush=True)


def http_json(url, dati=None, headers=None, metodo=None):
    corpo = json.dumps(dati).encode() if dati is not None else None
    h = {'User-Agent': USER_AGENT, 'Accept': 'application/json', **(headers or {})}
    if corpo is not None:
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=corpo, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            testo = r.read().decode()
            return json.loads(testo) if testo else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{metodo or "GET"} {url[:80]} -> HTTP {e.code}: {e.read()[:300]!r}') from None


class Supabase:
    def __init__(self, url, chiave):
        self.base = url.rstrip('/') + '/rest/v1/'
        self.h = {'apikey': chiave, 'Authorization': f'Bearer {chiave}'}

    def get(self, percorso):
        return http_json(self.base + percorso, headers=self.h)

    def rpc(self, funzione):
        return http_json(f'{self.base}rpc/{funzione}', {}, headers=self.h, metodo='POST')

    def insert(self, tabella, riga):
        http_json(self.base + tabella, riga, metodo='POST',
                  headers={**self.h, 'Prefer': 'resolution=ignore-duplicates,return=minimal'})

    def aste_attive(self, oggi):
        campi = ('id,lat,lng,categoria,prezzo_base,data_vendita,ora_vendita,citta,provincia,via,'
                 'disponibilita,data_pubblicazione,geo_fonte')
        righe, offset = [], 0
        while True:
            parte = self.get(f'aste_pvp?select={campi}&attiva=eq.true&lat=not.is.null'
                             f'&data_vendita=gte.{oggi}&order=id&limit=1000&offset={offset}')
            righe += parte
            if len(parte) < 1000:
                return righe
            offset += 1000


def km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def codice_categoria(cat):
    return CATEGORIE.get(cat, ('A', 'Altro'))[0]


def aste_per(dest, aste, oggi):
    cats = set(dest['categorie'] or [])
    pmax = dest['prezzo_max']
    zona = [a for a in aste
            if codice_categoria(a['categoria']) in cats
            and (not pmax or (a['prezzo_base'] or 0) > 0 and a['prezzo_base'] <= pmax)
            and km(dest['lat'], dest['lng'], a['lat'], a['lng']) <= dest['raggio_km']]
    da_nuove = (oggi - datetime.timedelta(days=GIORNI_NUOVE)).isoformat()
    fino_a = (oggi + datetime.timedelta(days=GIORNI_PROSSIME)).isoformat()
    per_data = lambda a: (a['data_vendita'], a['ora_vendita'] or '')  # noqa: E731
    nuove = sorted((a for a in zona if (a['data_pubblicazione'] or '') >= da_nuove), key=per_data)
    id_nuove = {a['id'] for a in nuove}
    prossime = sorted((a for a in zona if a['id'] not in id_nuove and a['data_vendita'] <= fino_a), key=per_data)
    return nuove, prossime, len(zona)


# ---------------------------------------------------------------- email

def fmt_euro(v):
    if not v or v <= 0:
        return 'Prezzo n.d.'
    return '€ ' + f'{v:,.0f}'.replace(',', '.')


def fmt_data(d):
    a, m, g = d.split('-')
    return f'{g}/{m}/{a}'


def luogo(a):
    c, p = a['citta'] or '', a['provincia'] or ''
    return f'{c} ({p})' if p and p != c else c


def riga_asta_html(a):
    e = html.escape
    cat = CATEGORIE.get(a['categoria'], ('A', 'Altro'))[1]
    disp = DISPONIBILITA.get((a['disponibilita'] or [None])[0])
    dettagli = ' · '.join(x for x in (cat, disp) if x)
    quando = fmt_data(a['data_vendita']) + (f" ore {e(a['ora_vendita'])}" if a['ora_vendita'] else '')
    indirizzo = f"<br><span style=\"color:#6b7280\">{e(a['via'])}</span>" if a['via'] and a['geo_fonte'] != 'comune' else ''
    mappa = f'{SITO}/mappa.html?asta={a["id"]}'
    pvp = f'https://pvp.giustizia.it/pvp/it/detail_annuncio.page?idAnnuncio={a["id"]}'
    return f'''<tr><td style="padding:14px 0;border-bottom:1px solid #e5e7eb">
  <div style="font-size:18px;font-weight:800;color:#0f1117">{fmt_euro(a["prezzo_base"])}</div>
  <div style="font-size:14px;color:#374151;margin-top:2px"><b>{e(luogo(a))}</b> · {e(dettagli)}{indirizzo}</div>
  <div style="font-size:13px;color:#374151;margin-top:4px">Asta il <b>{quando}</b></div>
  <div style="font-size:13px;margin-top:6px"><a href="{mappa}" style="color:#2563eb;font-weight:700;text-decoration:none">Vedi sulla mappa</a>
  &nbsp;·&nbsp; <a href="{pvp}" style="color:#2563eb;text-decoration:none">Scheda PVP</a></div>
</td></tr>'''


def sezione_html(titolo, aste, totale):
    if not aste:
        return ''
    righe = ''.join(riga_asta_html(a) for a in aste[:MAX_PER_SEZIONE])
    altre = (f'<p style="font-size:13px;color:#6b7280;margin:10px 0 0">…e altre {totale - MAX_PER_SEZIONE} '
             f'sulla mappa.</p>' if totale > MAX_PER_SEZIONE else '')
    return f'''<h2 style="font-size:16px;margin:28px 0 4px;color:#0f1117">{titolo} ({totale})</h2>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{righe}</table>{altre}'''


def riga_asta_testo(a):
    cat = CATEGORIE.get(a['categoria'], ('A', 'Altro'))[1]
    return (f"- {fmt_euro(a['prezzo_base'])} · {luogo(a)} · {cat} · asta il {fmt_data(a['data_vendita'])}\n"
            f"  {SITO}/mappa.html?asta={a['id']}")


def componi(dest, nuove, prossime, n_zona):
    nome = dest['nome'] or f"la tua area di {dest['raggio_km']} km"
    disiscrivi = f"{SITO}/disiscrizione.html?t={dest['token_disiscrizione']}"
    area = f'{SITO}/mappa.html?area=1'
    parti = []
    if nuove:
        parti.append(f'{len(nuove)} {"nuova asta" if len(nuove) == 1 else "nuove aste"}')
    if prossime:
        parti.append(f'{len(prossime)} in arrivo')
    oggetto = f"🏠 {' e '.join(parti)} · {nome}"

    e = html.escape
    corpo = f'''<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(oggetto)}</title></head>
<body style="margin:0;background:#f8f9fc;font-family:Helvetica,Arial,sans-serif;color:#0f1117">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px">
<tr><td style="padding:24px 24px 8px">
  <div style="font-size:20px;font-weight:800"><span style="color:#0f1117">analizz</span><span style="color:#2563eb">aste</span><span style="color:#0f1117">.it</span></div>
  <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#2563eb;margin-top:18px">Le aste della settimana</div>
  <h1 style="font-size:22px;margin:4px 0 6px;line-height:1.25">{e(nome[:1].upper() + nome[1:])}</h1>
  <p style="font-size:14px;color:#6b7280;margin:0">Raggio di {dest["raggio_km"]} km · oggi in quest'area ci sono {n_zona} aste in programma.</p>
</td></tr>
<tr><td style="padding:0 24px 8px">
{sezione_html("Nuove questa settimana", nuove, len(nuove))}
{sezione_html("In arrivo nei prossimi 14 giorni", prossime, len(prossime))}
  <p style="margin:28px 0 8px"><a href="{area}" style="display:inline-block;background:#2563eb;color:#ffffff;font-weight:700;font-size:14px;padding:12px 20px;border-radius:8px;text-decoration:none">Apri la mappa della tua area</a></p>
  <p style="font-size:13px;color:#374151;margin:16px 0">Hai trovato un'asta interessante? Scarica l'avviso di vendita dalla scheda PVP e
  <a href="{SITO}/#inizia" style="color:#2563eb">analizzalo su Analizzaste</a>: in pochi minuti hai rischi, costi e aspetti legali.</p>
</td></tr>
<tr><td style="padding:16px 24px 24px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;line-height:1.5">
  Dati dal Portale delle Vendite Pubbliche del Ministero della Giustizia: verifica sempre data, prezzo e condizioni sulla scheda ufficiale e sull'avviso di vendita.<br><br>
  Ricevi questa email perché sei iscritto alla newsletter di Analizzaste e hai scelto un'area di interesse sulla mappa.
  <a href="{area}" style="color:#6b7280">Modifica l'area</a> · <a href="{disiscrivi}" style="color:#6b7280">Disiscriviti dalla newsletter</a>
</td></tr></table></td></tr></table></body></html>'''

    testo = [f'Le aste della settimana · {nome}', f"Raggio di {dest['raggio_km']} km.", '']
    if nuove:
        testo += [f'NUOVE QUESTA SETTIMANA ({len(nuove)})', *map(riga_asta_testo, nuove[:MAX_PER_SEZIONE]), '']
    if prossime:
        testo += [f'IN ARRIVO NEI PROSSIMI 14 GIORNI ({len(prossime)})',
                  *map(riga_asta_testo, prossime[:MAX_PER_SEZIONE]), '']
    testo += [f'La mappa della tua area: {area}', '',
              'Dati dal Portale delle Vendite Pubbliche: verifica sempre la scheda ufficiale.',
              f'Disiscriviti dalla newsletter: {disiscrivi}']
    return oggetto, corpo, '\n'.join(testo), disiscrivi


def invia(chiave, mittente, a, oggetto, corpo, testo, disiscrivi):
    http_json(RESEND, {
        'from': mittente, 'to': [a], 'subject': oggetto, 'html': corpo, 'text': testo,
        'headers': {'List-Unsubscribe': f'<{disiscrivi}>'},
    }, headers={'Authorization': f'Bearer {chiave}'}, metodo='POST')


def main():
    args = sys.argv[1:]
    forza = '--forza' in args
    anteprima = args[args.index('--anteprima') + 1] if '--anteprima' in args else None

    adesso = datetime.datetime.now(ROMA)
    # Due orari nel workflow (07:00 e 08:00 UTC) coprono ora legale e solare:
    # si invia solo dal sabato alle 9 italiane, una volta sola (registro invii_settimanali).
    if not forza and not anteprima and (adesso.weekday() != 5 or adesso.hour < 9):
        giorno = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica'][adesso.weekday()]
        log(f'In Italia sono le {adesso:%H:%M} di {giorno}: invio solo il sabato dalle 9.')
        return
    oggi = adesso.date()

    sb = Supabase(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    destinatari = sb.rpc('destinatari_settimanali') or []
    gia = {r['user_id'] for r in sb.get(f'invii_settimanali?select=user_id&settimana=eq.{oggi}')}
    da_fare = [d for d in destinatari if anteprima or d['user_id'] not in gia]
    log(f'{len(destinatari)} iscritti con un\'area, {len(da_fare)} da servire oggi')
    if not da_fare:
        return

    aste = sb.aste_attive(oggi.isoformat())
    log(f'{len(aste)} aste attive con coordinate')
    if anteprima:
        os.makedirs(anteprima, exist_ok=True)
    else:
        chiave = os.environ['RESEND_API_KEY']
        mittente = os.environ.get('EMAIL_MITTENTE') or 'Analizzaste <aste@analizzaste.it>'

    inviate = saltate = errori = 0
    for d in da_fare:
        nuove, prossime, n_zona = aste_per(d, aste, oggi)
        if not nuove and not prossime:
            saltate += 1  # niente di nuovo in zona: nessuna email
            continue
        oggetto, corpo, testo, disiscrivi = componi(d, nuove, prossime, n_zona)
        if anteprima:
            nome_file = os.path.join(anteprima, f"{d['user_id']}.html")
            with open(nome_file, 'w', encoding='utf-8') as f:
                f.write(corpo)
            log(f'Anteprima: {oggetto} -> {nome_file}')
            inviate += 1
            continue
        try:
            invia(chiave, mittente, d['email'], oggetto, corpo, testo, disiscrivi)
        except Exception as e:  # noqa: BLE001 - un errore su un indirizzo non blocca gli altri
            errori += 1
            log(f'Invio non riuscito ({e})')
            continue
        sb.insert('invii_settimanali', {'user_id': d['user_id'], 'settimana': oggi.isoformat(),
                                        'n_nuove': len(nuove), 'n_prossime': len(prossime)})
        inviate += 1
        time.sleep(0.6)  # Resend: al massimo 2 richieste al secondo
    log(f'Fatto: {inviate} email, {saltate} senza aste in zona, {errori} errori')
    if errori:
        sys.exit(1)


if __name__ == '__main__':
    main()
