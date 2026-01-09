create schema publ;

create table publ.vehicles (
    id uuid primary key,
    vin varchar(17) unique not null
);

create table publ.trips (
    id serial,
    vehicle_id uuid not null,
    geometry geometry (geometry, 4326) not null,
    start_location text,
    end_location text,
    start_at timestamptz not null,
    end_at timestamptz not null,
    primary key (id),
    foreign key (vehicle_id) references publ.vehicles (id)
);

create table publ.ban_addresses (
    number varchar,
    street varchar,
    postal_code varchar,
    city varchar,
    geom geometry (point, 4326)
);

create index ban_addresses_geom_idx on publ.ban_addresses using gist (geom);
