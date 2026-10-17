-- Impostazioni condivise del sito (es. modalità manutenzione).
-- Lettura pubblica (il banner deve comparire a tutti); scrittura solo admin.

create table if not exists public.impostazioni (
  chiave text primary key,
  valore jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.impostazioni enable row level security;

create policy "impostazioni lettura pubblica" on public.impostazioni
  for select to anon, authenticated
  using (true);

create policy "admin gestisce impostazioni" on public.impostazioni
  for all to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin))
  with check (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin));

insert into public.impostazioni (chiave, valore)
values ('manutenzione', '{"attiva": false}'::jsonb)
on conflict (chiave) do nothing;
