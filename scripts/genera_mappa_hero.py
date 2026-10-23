#!/usr/bin/env python3
"""Genera img/mappa-italia-aste.svg, la cartina dell'Italia in rilievo con i puntini delle aste
mostrata nella home. Da rilanciare a mano ogni tanto: non serve aggiornarla ogni notte.

Uso: python3 scripts/genera_mappa_hero.py [file_world_atlas.json]
  Confini: Natural Earth 1:50m dal pacchetto world-atlas (scaricato se non indicato).
  Aste: un campione delle posizioni reali, dalla funzione pubblica aste_mappa() di Supabase.
"""
import json
import math
import os
import random
import sys
import urllib.request

WORLD_ATLAS = 'https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json'
SUPABASE_URL = 'https://hvmnernovucnsksszsbe.supabase.co'
SUPABASE_ANON_KEY = 'sb_publishable_5bBF51zEshWF3YtBh-YQoA_keV7WfCH'
USCITA = os.path.join(os.path.dirname(__file__), '..', 'img', 'mappa-italia-aste.svg')

LARGHEZZA = 400                      # unità SVG
MARGINE = 10
LAT0 = 42.0                          # latitudine media: corregge lo schiacciamento
SPESSORE = 9                         # altezza del rilievo, in unità SVG
N_PUNTI = 750                        # puntini delle aste nel disegno
# Città con un'onda che pulsa: danno movimento senza appesantire il disegno
CITTA = [(45.464, 9.190), (41.903, 12.496), (40.852, 14.268), (45.070, 7.687), (38.116, 13.361),
         (44.494, 11.343), (41.117, 16.872), (43.770, 11.256), (37.503, 15.087), (39.224, 9.122),
         (45.441, 12.316), (44.405, 8.946)]


def scarica_json(url, headers=None, dati=None):
    req = urllib.request.Request(url, data=dati, headers={'User-Agent': 'analizzaste.it', **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def italia(topo):
    """Anelli (lng, lat) dell'Italia dal TopoJSON di world-atlas."""
    sx, sy = topo['transform']['scale']
    tx, ty = topo['transform']['translate']
    archi = []
    for arco in topo['arcs']:
        x = y = 0
        punti = []
        for dx, dy in arco:
            x += dx
            y += dy
            punti.append((x * sx + tx, y * sy + ty))
        archi.append(punti)

    def anello(indici):
        pts = []
        for i in indici:
            a = archi[i] if i >= 0 else archi[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    geo = next(g for g in topo['objects']['countries']['geometries'] if g.get('properties', {}).get('name') == 'Italy')
    poligoni = geo['arcs'] if geo['type'] == 'MultiPolygon' else [geo['arcs']]
    return [anello(p[0]) for p in poligoni]  # solo il contorno esterno: niente buchi (San Marino, Vaticano)


def proiettore(anelli):
    k = math.cos(math.radians(LAT0))
    xs = [lng * k for a in anelli for lng, _ in a]
    ys = [lat for a in anelli for _, lat in a]
    scala = (LARGHEZZA - 2 * MARGINE) / (max(xs) - min(xs))
    altezza = (max(ys) - min(ys)) * scala + 2 * MARGINE + SPESSORE
    return (lambda lng, lat: (MARGINE + (lng * k - min(xs)) * scala, MARGINE + (max(ys) - lat) * scala)), altezza


def area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def percorso(anelli, proj):
    d = []
    for a in anelli:
        pts = [proj(lng, lat) for lng, lat in a]
        if area(pts) < 4:            # isolotti troppo piccoli per vedersi
            continue
        semplici = [pts[0]]
        for p in pts[1:]:
            if math.dist(p, semplici[-1]) >= 0.9:
                semplici.append(p)
        d.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in semplici) + 'Z')
    return ''.join(d)


def main():
    topo = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else scarica_json(WORLD_ATLAS)
    anelli = italia(topo)
    proj, altezza = proiettore(anelli)
    d = percorso(anelli, proj)

    h = {'apikey': SUPABASE_ANON_KEY, 'Authorization': f'Bearer {SUPABASE_ANON_KEY}', 'Content-Type': 'application/json'}
    aste = scarica_json(f'{SUPABASE_URL}/rest/v1/rpc/aste_mappa', h, b'{}')['aste']
    random.seed(23)
    campione = random.sample(aste, min(N_PUNTI, len(aste)))
    punti = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6"/>'
                    for x, y in (proj(a[2], a[1]) for a in campione))
    onde = ''.join(f'<g transform="translate({x:.1f},{y:.1f})"><circle class="onda" r="3" style="animation-delay:{i * 0.37 % 3:.2f}s"/>'
                   f'<circle class="nucleo" r="2.6"/></g>'
                   for i, (x, y) in enumerate(proj(lng, lat) for lat, lng in CITTA))
    # Il rilievo: la stessa sagoma ripetuta verso il basso, sempre più scura
    lati = ''.join(f'<use href="#it" y="{s}" fill="url(#lato)"/>' for s in range(SPESSORE, 0, -1))

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGHEZZA} {altezza:.0f}" role="img" aria-label="Cartina dell'Italia con le aste immobiliari">
<title>Le aste immobiliari in Italia</title>
<defs>
  <path id="it" d="{d}"/>
  <g id="punti">{punti}</g>
  <linearGradient id="terra" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#f8fafc"/><stop offset=".55" stop-color="#e2e8f0"/><stop offset="1" stop-color="#cbd5e1"/>
  </linearGradient>
  <linearGradient id="lato" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#64748b"/><stop offset="1" stop-color="#334155"/>
  </linearGradient>
  <filter id="alone" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.4"/></filter>
</defs>
<style>
  .onda{{fill:none;stroke:#3b82f6;stroke-width:1.4;transform-box:fill-box;transform-origin:center;animation:onda 3s ease-out infinite}}
  .nucleo{{fill:#2563eb;stroke:#fff;stroke-width:1}}
  @keyframes onda{{0%{{transform:scale(1);opacity:.9}}100%{{transform:scale(4.5);opacity:0}}}}
  @media (prefers-reduced-motion:reduce){{.onda{{animation:none;opacity:0}}}}
</style>
{lati}
<use href="#it" fill="url(#terra)" stroke="#ffffff" stroke-width=".8"/>
<use href="#punti" fill="#3b82f6" filter="url(#alone)" opacity=".55"/>
<use href="#punti" fill="#2563eb"/>
{onde}
</svg>
'''
    with open(USCITA, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'{os.path.normpath(USCITA)}: {len(svg) // 1024} KB, {len(campione)} aste su {len(aste)}')


if __name__ == '__main__':
    main()
