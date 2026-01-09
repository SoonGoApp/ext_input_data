/*
  This SQL script loads raw vehicle json into a clean format by extracting
  specific capabilities such as engine and location.
*/

create or replace table clean as (
    with capabilities as (
        select
            vin,
            coalesce(
                json_extract(data, '$.engine.status.data')::text,
                st_point(
                    json_extract(
                        data, '$.vehicle_location.coordinates.data.longitude'
                    )::double,
                    json_extract(
                        data, '$.vehicle_location.coordinates.data.latitude'
                    )::double
                )::text
            ) as val,
            coalesce(
                json_extract(
                    data, '$.engine.status.timestamp'
                ),
                json_extract(
                    data, '$.vehicle_location.coordinates.timestamp'
                )
            )::timestamptz as ts,
            capability
        from raw
    )

    select
        v.id as vehicle_id,
        c.capability,
        c.val,
        c.ts
    from capabilities as c
    join db.vehicles v on v.vin = c.vin
);

create or replace table points as (

    -- forward fill engine status to discard points when engine is off
    with engine_status as (
        select
            *,
            case
                when capability = 'engine' then val
            end as status
        from clean
    ),

    point_status as (
        select
            *,
            last_value(status ignore nulls) over (partition by vehicle_id order by ts rows between unbounded preceding and current row) as status_ffill
        from engine_status
    )

    select
        vehicle_id,
        val::geometry as geom,
        ts
    from point_status
    where
        capability = 'vehicle_location'
        and (status_ffill == '"on"' or status_ffill is null) -- keep points when engine is on or unknown
);

select -- aggregated stats for logging purposes
    count(*) as vehicles_nb,
    min(ts) as min_ts,
    max(ts) as max_ts,
    count(distinct vehicle_id) as vehicles_distinct_nb
from points;
