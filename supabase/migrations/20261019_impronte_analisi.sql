-- Registro delle impronte dei documenti analizzati (sola misurazione, nessun riuso).
create table if not exists public.impronte_analisi (
  id bigint generated always as identity primary key,
  hash text not null,
  modello text not null,
  prompt_versione text not null,
  created_at timestamptz not null default now()
);

create index if not exists impronte_analisi_hash_idx on public.impronte_analisi (hash);

alter table public.impronte_analisi enable row level security;

create policy "admin legge impronte" on public.impronte_analisi
  for select to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_admin));

grant select on public.impronte_analisi to authenticated;
