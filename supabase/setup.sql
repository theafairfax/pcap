-- Run in the Supabase SQL Editor. Only published Allen references go here.
create table if not exists public.pcap_reference_neurons (
  id text primary key,
  label text not null,
  species text not null,
  region text not null,
  analysis_version text not null,
  storage_path text not null,
  metadata jsonb not null,
  plot_bounds jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
create index if not exists pcap_reference_species_region
  on public.pcap_reference_neurons (species, region);
alter table public.pcap_reference_neurons enable row level security;
revoke all on public.pcap_reference_neurons from anon, authenticated;
grant select on public.pcap_reference_neurons to anon, authenticated;
grant all on public.pcap_reference_neurons to service_role;
drop policy if exists "Read published PCAP references" on public.pcap_reference_neurons;
create policy "Read published PCAP references" on public.pcap_reference_neurons
  for select to anon, authenticated using (true);

-- Public read access is intentional for this reference-only bucket.
-- Upload/write operations are reserved for the project owner's secret key.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('pcap-references', 'pcap-references', true, 8388608,
        array['application/octet-stream'])
on conflict (id) do nothing;
