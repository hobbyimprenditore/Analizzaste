-- Aste salvate nei preferiti da ogni utente (dalla mappa).
create table if not exists public.aste_preferite (
  user_id uuid not null references auth.users(id) on delete cascade,
  asta_id bigint not null references public.aste_pvp(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, asta_id)
);

create index if not exists aste_preferite_asta_idx on public.aste_preferite (asta_id);

alter table public.aste_preferite enable row level security;

-- Ognuno vede, aggiunge e toglie solo i propri preferiti.
create policy "preferiti: leggo i miei" on public.aste_preferite
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "preferiti: aggiungo i miei" on public.aste_preferite
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "preferiti: tolgo i miei" on public.aste_preferite
  for delete to authenticated using ((select auth.uid()) = user_id);

grant select, insert, delete on public.aste_preferite to authenticated;

-- Tetto per utente, per evitare abusi.
create or replace function public.limite_aste_preferite()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if (select count(*) from public.aste_preferite where user_id = new.user_id) >= 500 then
    raise exception 'Hai raggiunto il limite di 500 aste preferite.';
  end if;
  return new;
end;
$$;

create trigger aste_preferite_limite
  before insert on public.aste_preferite
  for each row execute function public.limite_aste_preferite();
