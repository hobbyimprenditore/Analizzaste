-- Consulenza post-report: professionisti caricati dall'admin e richieste inoltrate.
-- Applicata al progetto Supabase AnalizzaASTE il 17/10/2026.

create table if not exists public.professionisti (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  tipo text not null check (tipo in ('legale','tecnica','quotazione','investitore','amministratore')),
  regione text not null,
  provincia text,
  email text not null,
  attivo boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.richieste_consulenza (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  tipo text not null check (tipo in ('legale','tecnica','quotazione','investitore','amministratore')),
  professionista_id uuid references public.professionisti(id) on delete set null,
  email_cliente text not null,
  regione text,
  provincia text,
  report_id uuid,
  stato text not null default 'inviata' check (stato in ('inviata','risposta_ricevuta','approvata','rifiutata','chiusa')),
  prezzo_richiesto numeric(10,2),
  risposta_professionista text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.professionisti enable row level security;
alter table public.richieste_consulenza enable row level security;

create policy "admin gestisce professionisti" on public.professionisti
  for all to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin))
  with check (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin));

create policy "admin gestisce richieste" on public.richieste_consulenza
  for all to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin))
  with check (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin));

-- Elenco pubblico dei professionisti: solo nome, tipo e zona, mai email o telefono.
create or replace function public.lista_professionisti(p_tipo text, p_regione text default null)
returns table(id uuid, nome text, tipo text, regione text, provincia text)
language sql stable security definer set search_path = public
as $$
  select p.id, p.nome, p.tipo, p.regione, p.provincia
  from public.professionisti p
  where p.attivo
    and p.tipo = p_tipo
    and (p_regione is null or p.regione = p_regione)
  order by p.nome;
$$;

grant execute on function public.lista_professionisti(text, text) to anon, authenticated;
