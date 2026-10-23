-- Area di interesse di ogni utente e email settimanale (sabato alle 9) con le aste della zona,
-- inviata solo a chi è iscritto alla newsletter. Script: scripts/email_aree_settimanali.py

-- Correzione della fase 1: su questo progetto service_role non riceve permessi automatici
-- sulle tabelle nuove, e lo script notturno non avrebbe potuto scrivere.
grant select, insert, update on public.aste_pvp to service_role;
grant select, insert, update on public.geocodifiche to service_role;

-- Nuova fonte di iscrizione alla newsletter: dalla mappa
alter table public.newsletter_iscritti drop constraint newsletter_iscritti_fonte_check;
alter table public.newsletter_iscritti add constraint newsletter_iscritti_fonte_check
  check (fonte = any (array['footer', 'registrazione', 'mappa']));

-- Una sola area per utente: un cerchio sulla mappa, con i filtri scelti
create table if not exists public.aree_interesse (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nome text check (length(nome) <= 80),
  lat double precision not null check (lat between 35.2 and 47.2),
  lng double precision not null check (lng between 6.5 and 18.7),
  raggio_km integer not null check (raggio_km between 1 and 150),
  categorie text[] not null default array['R', 'C', 'I', 'A', 'S']
    check (categorie <@ array['R', 'C', 'I', 'A', 'S'] and cardinality(categorie) > 0),
  prezzo_max numeric check (prezzo_max > 0),
  token_disiscrizione uuid not null default gen_random_uuid() unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.aree_interesse enable row level security;

create policy "aree: leggo la mia" on public.aree_interesse
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "aree: creo la mia" on public.aree_interesse
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "aree: modifico la mia" on public.aree_interesse
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "aree: elimino la mia" on public.aree_interesse
  for delete to authenticated using ((select auth.uid()) = user_id);

-- L'utente non può scegliere né cambiare il token di disiscrizione
grant select, delete on public.aree_interesse to authenticated;
grant insert (user_id, nome, lat, lng, raggio_km, categorie, prezzo_max, updated_at)
  on public.aree_interesse to authenticated;
-- user_id serve all'upsert dalla mappa; la policy impedisce comunque di usare l'id di un altro
grant update (user_id, nome, lat, lng, raggio_km, categorie, prezzo_max, updated_at)
  on public.aree_interesse to authenticated;
grant select on public.aree_interesse to service_role;

-- Registro degli invii: evita doppioni se lo script parte due volte nello stesso sabato
create table if not exists public.invii_settimanali (
  user_id uuid not null references auth.users(id) on delete cascade,
  settimana date not null,              -- il sabato dell'invio
  inviato_at timestamptz not null default now(),
  n_nuove integer not null default 0,
  n_prossime integer not null default 0,
  primary key (user_id, settimana)
);

alter table public.invii_settimanali enable row level security;
grant select, insert on public.invii_settimanali to service_role;

-- È iscritto alla newsletter l'utente collegato?
create or replace function public.stato_newsletter()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.newsletter_iscritti n
    join auth.users u on lower(u.email) = n.email
    where u.id = auth.uid() and n.disiscritto_at is null
  );
$$;

-- Iscrive (o riscrive, se si era disiscritto) l'utente collegato con la sua email di accesso
create or replace function public.iscrivimi_newsletter()
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_email text;
begin
  select lower(email) into v_email from auth.users
  where id = auth.uid() and email_confirmed_at is not null;
  if v_email is null then
    return false;
  end if;
  insert into public.newsletter_iscritti (email, fonte, consenso_at, disiscritto_at)
  values (v_email, 'mappa', now(), null)
  on conflict (email) do update set fonte = 'mappa', consenso_at = now(), disiscritto_at = null;
  return true;
end;
$$;

-- Disiscrizione dal link nell'email (senza login): basta il token dell'area
create or replace function public.disiscrivi_newsletter(p_token uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_email text;
begin
  select lower(u.email) into v_email
  from public.aree_interesse a join auth.users u on u.id = a.user_id
  where a.token_disiscrizione = p_token;
  if v_email is null then
    return false;
  end if;
  update public.newsletter_iscritti set disiscritto_at = now()
  where email = v_email and disiscritto_at is null;
  return true;
end;
$$;

-- Chi riceve l'email del sabato: area impostata, email confermata, iscritto, account non bloccato
create or replace function public.destinatari_settimanali()
returns table (
  user_id uuid, email text, nome text, lat double precision, lng double precision,
  raggio_km integer, categorie text[], prezzo_max numeric, token_disiscrizione uuid
)
language sql
stable
security definer
set search_path = ''
as $$
  select a.user_id, lower(u.email), a.nome, a.lat, a.lng, a.raggio_km, a.categorie, a.prezzo_max,
         a.token_disiscrizione
  from public.aree_interesse a
  join auth.users u on u.id = a.user_id and u.email_confirmed_at is not null
  join public.newsletter_iscritti n on n.email = lower(u.email) and n.disiscritto_at is null
  left join public.profiles p on p.id = a.user_id
  where not coalesce(p.is_blocked, false);
$$;

revoke execute on function public.stato_newsletter() from public, anon;
revoke execute on function public.iscrivimi_newsletter() from public, anon;
revoke execute on function public.disiscrivi_newsletter(uuid) from public;
revoke execute on function public.destinatari_settimanali() from public, anon, authenticated;
grant execute on function public.stato_newsletter() to authenticated;
grant execute on function public.iscrivimi_newsletter() to authenticated;
grant execute on function public.disiscrivi_newsletter(uuid) to anon, authenticated;
grant execute on function public.destinatari_settimanali() to service_role;
