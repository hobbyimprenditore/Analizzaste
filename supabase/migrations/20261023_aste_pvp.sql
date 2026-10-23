-- Aste immobiliari dal Portale delle Vendite Pubbliche (PVP), aggiornate ogni notte
-- dalla GitHub Action "Aste PVP notturne" (scripts/aggiorna_aste_pvp.py).
-- Contiene solo dati pubblici dell'annuncio: nessun dato personale (debitori, custodi).

create table if not exists public.aste_pvp (
  id bigint primary key,                 -- idAnnuncio del PVP
  categoria text,                        -- IMMOBILE_RESIDENZIALE, IMMOBILE_COMMERCIALE, ...
  categorie_bene text[],
  via text,
  cap text,
  citta text,
  provincia text,
  lat double precision,
  lng double precision,
  geo_fonte text,                        -- 'pvp' | 'indirizzo' | 'comune'
  procedura text,
  numero_lotto text,
  tribunale text,
  prezzo_base numeric,
  offerta_minima numeric,
  rialzo_minimo numeric,
  data_vendita date,
  ora_vendita text,
  data_pubblicazione date,
  disponibilita text[],                  -- LIBER, OCCUP, INCOR, ...
  descrizione text,
  esito text,                            -- SOSPE, ASDES, ... (null se in corso)
  attiva boolean not null default true,
  primo_rilevamento timestamptz not null default now(),
  ultimo_rilevamento timestamptz not null default now()
);

create index if not exists aste_pvp_attive_idx on public.aste_pvp (data_vendita) where attiva;

alter table public.aste_pvp enable row level security;

-- Sono dati pubblici del PVP: chiunque li può leggere, solo il service role li scrive.
create policy "aste pvp leggibili da tutti" on public.aste_pvp
  for select to anon, authenticated
  using (true);

grant select on public.aste_pvp to anon, authenticated;

-- Cache della geocodifica (Nominatim) per gli annunci senza coordinate.
-- Accessibile solo al service role.
create table if not exists public.geocodifiche (
  chiave text primary key,               -- 'comune|<citta>|<provincia>' oppure 'indirizzo|<via>|<citta>|<provincia>'
  lat double precision,
  lng double precision,
  trovato boolean not null,
  created_at timestamptz not null default now()
);

alter table public.geocodifiche enable row level security;

-- Dati compatti per la mappa, in una sola chiamata:
-- aste = [id, lat, lng, prezzo_base, data_vendita, categoria, citta, provincia, geo_fonte, disponibilita]
create or replace function public.aste_mappa()
returns json
language sql
stable
security invoker
set search_path = ''
as $$
  select json_build_object(
    'aggiornato_al', (select max(ultimo_rilevamento) from public.aste_pvp),
    'aste', coalesce(json_agg(json_build_array(
      a.id,
      round(a.lat::numeric, 5),
      round(a.lng::numeric, 5),
      a.prezzo_base,
      a.data_vendita,
      case a.categoria
        when 'IMMOBILE_RESIDENZIALE' then 'R'
        when 'IMMOBILE_COMMERCIALE' then 'C'
        when 'IMMOBILE_INDUSTRIALE' then 'I'
        when 'IMPIANTO_SPORTIVO' then 'S'
        else 'A'
      end,
      a.citta,
      a.provincia,
      a.geo_fonte,
      a.disponibilita[1]
    ) order by a.data_vendita), '[]'::json)
  )
  from public.aste_pvp a
  where a.attiva and a.lat is not null and a.data_vendita >= current_date;
$$;

grant execute on function public.aste_mappa() to anon, authenticated;
