#!/usr/bin/env python3
"""Scarica le aste immobiliari future dal PVP e le salva in Supabase (tabella aste_pvp).

Gira ogni notte nella GitHub Action "Aste PVP notturne". Usa solo la libreria standard.

Variabili d'ambiente:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  (obbligatorie, salvo con --prova)
  GEOCODIFICA_MINUTI  minuti massimi di geocodifica per esecuzione (default 60)

Opzioni:
  --prova FILE  non scrive su Supabase: salva il risultato in FILE (JSON) e salta la geocodifica
"""
import datetime
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PVP_RICERCA = ('https://pvp.giustizia.it/ric-496b258c-986a1b71/ric-ms/ricerca/vendite'
               '?language=it&page={pagina}&size=1000&sort=dataOraVendita,desc&sort=id,asc')
NOMINATIM = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'analizzaste.it/1.0 (+https://analizzaste.it)'

# Date oltre questo orizzonte sono errori di battitura nel PVP (es. anno 3019)
ORIZZONTE_GIORNI = 3 * 365
# Riquadro dell'Italia: coordinate fuori da qui sono considerate sbagliate
LAT_MIN, LAT_MAX, LNG_MIN, LNG_MAX = 35.2, 47.2, 6.5, 18.7
# Un indirizzo geocodificato a più di questi km dal suo comune viene scartato
DISTANZA_MAX_KM = 30
# Se il PVP restituisce meno di questa frazione delle aste già attive, non disattiviamo nulla
SOGLIA_SICUREZZA = 0.5


def log(msg):
    print(time.strftime('%H:%M:%S'), msg, flush=True)


def http_json(url, dati=None, headers=None, metodo=None, tentativi=3):
    corpo = json.dumps(dati).encode() if dati is not None else None
    h = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    if corpo is not None:
        h['Content-Type'] = 'application/json'
    h.update(headers or {})
    for t in range(1, tentativi + 1):
        try:
            req = urllib.request.Request(url, data=corpo, headers=h, method=metodo)
            with urllib.request.urlopen(req, timeout=90) as r:
                testo = r.read().decode()
                return json.loads(testo) if testo else None
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise RuntimeError(f'{metodo or "GET"} {url[:90]} -> HTTP {e.code}: {e.read()[:300]!r}')
            if t == tentativi:
                raise
        except (urllib.error.URLError, TimeoutError):
            if t == tentativi:
                raise
        time.sleep(10 * t)


# ---------------------------------------------------------------- PVP

def scarica_pvp():
    """Tutte le aste immobiliari con data di vendita da oggi in poi."""
    oggi = datetime.date.today()
    limite = (oggi + datetime.timedelta(days=ORIZZONTE_GIORNI)).isoformat()
    oggi = oggi.isoformat()
    per_id, pagina = {}, 0
    while True:
        body = http_json(PVP_RICERCA.format(pagina=pagina),
                         {'tipoLotto': 'IMMOBILI', 'flagRicerca': 1})['body']
        lotti = body['content']
        for x in lotti:
            d = x.get('dataVendita') or ''
            if oggi <= d <= limite:
                per_id[x['id']] = x
        pagina += 1
        # ordinate dalla data più lontana: appena passiamo a ieri abbiamo finito
        if body['last'] or not lotti or (lotti[-1].get('dataVendita') or '') < oggi:
            break
        time.sleep(1)
    log(f'PVP: {pagina} pagine, {len(per_id)} aste future')
    return list(per_id.values())


def coordinate_valide(lat, lng):
    return (lat is not None and lng is not None
            and LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX)


def pulisci(s):
    return ' '.join(str(s or '').split())


def chiave_comune(ind):
    return 'comune|' + '|'.join(pulisci(ind.get(k)).upper() for k in ('citta', 'provincia'))


def chiave_indirizzo(ind):
    return 'indirizzo|' + '|'.join(pulisci(ind.get(k)).upper() for k in ('via', 'citta', 'provincia'))


# ---------------------------------------------------------------- geocodifica

def km(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def nominatim(testo):
    q = urllib.parse.urlencode({'q': testo, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'it'})
    ris = http_json(f'{NOMINATIM}?{q}')
    if ris:
        lat, lng = float(ris[0]['lat']), float(ris[0]['lon'])
        if coordinate_valide(lat, lng):
            return lat, lng
    return None


def geocodifica(aste, cache, minuti):
    """Aggiunge a `cache` le chiavi mancanti, entro il tempo concesso. Restituisce le nuove voci."""
    senza = [a['indirizzo'] or {} for a in aste if not coordinate_valide(*coord_pvp(a))]
    # prima i comuni (pochi e bastano a mettere tutto sulla mappa), poi gli indirizzi precisi
    da_fare = {}
    for ind in senza:
        k = chiave_comune(ind)
        if pulisci(ind.get('citta')) and k not in cache:
            da_fare[k] = f"{pulisci(ind.get('citta'))}, {pulisci(ind.get('provincia'))}, Italia"
    for ind in senza:
        k = chiave_indirizzo(ind)
        if len(pulisci(ind.get('via'))) >= 4 and pulisci(ind.get('citta')) and k not in cache:
            da_fare[k] = (f"{pulisci(ind.get('via'))}, {pulisci(ind.get('citta'))}, "
                          f"{pulisci(ind.get('provincia'))}, Italia")
    log(f'Geocodifica: {len(da_fare)} ricerche da fare, massimo {minuti} minuti')

    nuove, fine = {}, time.time() + minuti * 60
    for k, testo in da_fare.items():
        if time.time() > fine:
            break
        try:
            p = nominatim(testo)
        except Exception as e:  # noqa: BLE001 - un errore di rete non deve fermare l'aggiornamento
            log(f'Nominatim non risponde ({e}): riprendo la prossima notte')
            break
        if p and k.startswith('indirizzo|'):
            comune = cache.get('comune|' + k.split('|', 2)[2])
            if comune and comune.get('trovato') and km(p, (comune['lat'], comune['lng'])) > DISTANZA_MAX_KM:
                p = None
        voce = {'chiave': k, 'lat': p[0] if p else None, 'lng': p[1] if p else None, 'trovato': bool(p)}
        cache[k] = nuove[k] = voce
        time.sleep(1.1)  # regola di Nominatim: al massimo 1 richiesta al secondo
    log(f'Geocodifica: {len(nuove)} fatte, {sum(v["trovato"] for v in nuove.values())} trovate')
    return list(nuove.values())


def coord_pvp(a):
    c = (a.get('indirizzo') or {}).get('coordinate') or {}
    return c.get('latitudine'), c.get('longitudine')


def posizione(a, cache):
    lat, lng = coord_pvp(a)
    if coordinate_valide(lat, lng):
        return lat, lng, 'pvp'
    ind = a.get('indirizzo') or {}
    for k, fonte in ((chiave_indirizzo(ind), 'indirizzo'), (chiave_comune(ind), 'comune')):
        v = cache.get(k)
        if v and v.get('trovato'):
            return v['lat'], v['lng'], fonte
    return None, None, None


# ---------------------------------------------------------------- Supabase

class Supabase:
    def __init__(self, url, chiave):
        self.base = url.rstrip('/') + '/rest/v1/'
        self.h = {'apikey': chiave, 'Authorization': f'Bearer {chiave}'}

    def leggi_tutto(self, tabella, select):
        righe, offset = [], 0
        while True:
            parte = http_json(f'{self.base}{tabella}?select={select}&order=chiave&limit=1000&offset={offset}',
                              headers=self.h)
            righe += parte
            if len(parte) < 1000:
                return righe
            offset += 1000

    def upsert(self, tabella, righe, conflitto):
        for i in range(0, len(righe), 500):
            http_json(f'{self.base}{tabella}?on_conflict={conflitto}', righe[i:i + 500], metodo='POST',
                      headers={**self.h, 'Prefer': 'resolution=merge-duplicates,return=minimal'})

    def conta(self, filtro):
        req = urllib.request.Request(f'{self.base}aste_pvp?select=id&{filtro}&limit=1',
                                     headers={**self.h, 'Prefer': 'count=exact', 'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            return int(r.headers.get('Content-Range', '*/0').split('/')[-1])

    def disattiva_vecchie(self, prima_di):
        filtro = urllib.parse.urlencode({'attiva': 'eq.true', 'ultimo_rilevamento': f'lt.{prima_di}'})
        http_json(f'{self.base}aste_pvp?{filtro}', {'attiva': False}, metodo='PATCH',
                  headers={**self.h, 'Prefer': 'return=minimal'})


def riga(a, cache, adesso):
    ind = a.get('indirizzo') or {}
    lat, lng, fonte = posizione(a, cache)
    return {
        'id': a['id'],
        'categoria': a.get('categoriaLotto'),
        'categorie_bene': a.get('categoriaBene') or [],
        'via': pulisci(ind.get('via')) or None,
        'cap': ind.get('cap'),
        'citta': pulisci(ind.get('citta')) or None,
        'provincia': pulisci(ind.get('provincia')) or None,
        'lat': lat,
        'lng': lng,
        'geo_fonte': fonte,
        'procedura': a.get('procedura'),
        'numero_lotto': a.get('numeroLotto'),
        'tribunale': a.get('tribunale'),
        'prezzo_base': a.get('prezzoBaseAsta'),
        'offerta_minima': a.get('offertaMinima'),
        'rialzo_minimo': a.get('rialzoMinimo'),
        'data_vendita': a.get('dataVendita'),
        'ora_vendita': a.get('orarioVendita'),
        'data_pubblicazione': a.get('dataPubblicazione'),
        'disponibilita': a.get('disponibilita') or [],
        'descrizione': pulisci(a.get('descLotto'))[:2000] or None,
        'esito': a.get('esito'),
        # un esito (sospesa, aggiudicata, deserta...) vuol dire che l'asta non è più in corso
        'attiva': not a.get('esito'),
        'ultimo_rilevamento': adesso,
    }


def main():
    inizio = datetime.datetime.now(datetime.timezone.utc).isoformat()
    aste = scarica_pvp()

    if len(sys.argv) == 3 and sys.argv[1] == '--prova':
        righe = [riga(a, {}, inizio) for a in aste]
        json.dump(righe, open(sys.argv[2], 'w'), ensure_ascii=False)
        log(f'Prova: {len(righe)} righe salvate in {sys.argv[2]}, '
            f'{sum(1 for r in righe if r["lat"] is None)} senza coordinate')
        return

    sb = Supabase(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    attive_prima = sb.conta('attiva=eq.true')
    if attive_prima and len(aste) < attive_prima * SOGLIA_SICUREZZA:
        sys.exit(f'Il PVP ha restituito solo {len(aste)} aste contro {attive_prima} attive: '
                 'probabile problema del portale, non aggiorno nulla.')

    cache = {v['chiave']: v for v in sb.leggi_tutto('geocodifiche', 'chiave,lat,lng,trovato')}
    nuove = geocodifica(aste, cache, float(os.environ.get('GEOCODIFICA_MINUTI', '60')))
    if nuove:
        sb.upsert('geocodifiche', nuove, 'chiave')

    righe = [riga(a, cache, inizio) for a in aste]
    sb.upsert('aste_pvp', righe, 'id')
    sb.disattiva_vecchie(inizio)

    senza = sum(1 for r in righe if r['lat'] is None)
    log(f'Fatto: {len(righe)} aste salvate, {sb.conta("attiva=eq.true")} attive, '
        f'{senza} ancora senza coordinate')


if __name__ == '__main__':
    main()
