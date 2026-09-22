# FloatChat Data Dictionary

## ARGO Variables

| Variable | Standard Name | Units | Description | QC Flag Field |
|----------|---------------|-------|-------------|---------------|
| temperature | sea_water_temperature | °C (degrees Celsius) | In-situ temperature at measurement depth | temperature_qc |
| salinity | sea_water_practical_salinity | PSU (Practical Salinity Units) | Practical salinity | salinity_qc |
| pressure | sea_water_pressure | dbar (decibars) | Pressure at measurement level | pressure_qc |
| depth | depth | m (meters) | Calculated depth from pressure | — |
| oxygen | mole_concentration_of_dissolved_molecular_oxygen_in_sea_water | μmol/kg | Dissolved oxygen concentration | oxygen_qc |
| chlorophyll | mass_concentration_of_chlorophyll_in_sea_water | mg/m³ | Chlorophyll-a concentration | chlorophyll_qc |
| nitrate | mole_concentration_of_nitrate_in_sea_water | μmol/kg | Nitrate concentration | nitrate_qc |
| ph | sea_water_ph_reported_on_total_scale | 0-14 | pH on total scale | ph_qc |

## ARGO Quality Control Flags

| Flag | Meaning | Action |
|------|---------|--------|
| 0 | No QC performed | Use with caution |
| 1 | Good data | ✅ Use |
| 2 | Probably good data | ✅ Use (recommended filter includes) |
| 3 | Probably bad data | ⚠️ Exclude for "good_only", include for "recommended" |
| 4 | Bad data | ❌ Exclude |
| 5 | Value changed | Use adjusted value if available |
| 6 | Not used | — |
| 7 | Not used | — |
| 8 | Estimated value | ⚠️ Use with caution |
| 9 | Missing value | ❌ Exclude |

### Quality Filter Levels

| Level | Included Flags | Use Case |
|-------|----------------|----------|
| `all` | 0-9 | Raw exploration only |
| `recommended` | 1, 2 | **Default for MVP** — balances coverage and quality |
| `good_only` | 1 | High-stakes decisions |

## Profile Metadata

| Field | Type | Description |
|-------|------|-------------|
| platform_number | Integer | WMO float identifier (e.g., 1901234) |
| cycle_number | Integer | Profile cycle number for this float |
| profile_time | Timestamp (UTC) | Date/time of profile |
| latitude | Decimal degrees | -90 to 90 |
| longitude | Decimal degrees | -180 to 180 |
| position_qc | Integer | Position quality flag (1=good) |
| direction | Character | 'A' (ascending) or 'D' (descending) |
| data_mode | Character | 'R' (real-time), 'D' (delayed-mode), 'A' (adjusted) |

## Derived Fields

| Field | Calculation | Units |
|-------|-------------|-------|
| depth_m | From pressure via UNESCO 1983 equation of state | m |
| potential_temperature | Temperature adjusted to surface pressure | °C |
| density | From T, S, P via TEOS-10 | kg/m³ |
| mixed_layer_depth | Depth where density increases by 0.03 kg/m³ from 10m | m |

## Missing Values

- NetCDF fill value: `9.96921e+36` (float) or `99999` (int)
- Represented as `null` in database/JSON
- Excluded from all aggregations automatically

## Spatial Reference

- Coordinate System: WGS84 (EPSG:4326)
- Geometry Type: `GEOGRAPHY(POINT, 4326)` in PostGIS
- Bounding Box for Indian Ocean: `30°S-30°N, 30°E-120°E`

## Temporal Reference

- All times in UTC (no timezone offset)
- Profile time = mid-profile timestamp
- Delayed-mode data typically available 6-12 months after collection

## Dataset Snapshots

| Field | Description |
|-------|-------------|
| dataset_name | Unique identifier (e.g., `argo_indian_ocean_2015_2025`) |
| region | Human-readable region description |
| start_time / end_time | Temporal coverage of data |
| source | Data source (e.g., `ARGO GDAC`, `ERDDAP`, `Argovis`) |
| source_version | Version/timestamp of source data |
| record_count | Total observation records |
| profile_count | Total profiles |
| float_count | Unique floats |
| checksum | SHA256 of source files for reproducibility |

## Regional Definitions (Named Regions)

| Name | Bounding Box (min_lat, max_lat, min_lon, max_lon) |
|------|---------------------------------------------------|
| Arabian Sea | 8.0, 25.0, 60.0, 78.0 |
| Bay of Bengal | 5.0, 22.0, 80.0, 100.0 |
| Kerala Coast | 8.0, 13.0, 74.0, 77.0 |
| Indian Ocean (full) | -30.0, 30.0, 30.0, 120.0 |
| Equatorial Indian Ocean | -10.0, 10.0, 40.0, 110.0 |

## Units Reference

| Quantity | Unit | Symbol | Conversion |
|----------|------|--------|------------|
| Temperature | Celsius | °C | Kelvin = °C + 273.15 |
| Salinity | Practical Salinity Unit | PSU | Unitless (≈ g/kg) |
| Pressure | Decibar | dbar | 1 dbar ≈ 1 m depth |
| Depth | Meter | m | — |
| Oxygen | Micromole per kilogram | μmol/kg | 1 ml/L ≈ 44.66 μmol/kg |
| Chlorophyll | Milligram per cubic meter | mg/m³ | — |
| Distance | Kilometer | km | 1 nmi = 1.852 km |
| Speed | Knot | kt | 1 kt = 0.514 m/s |
| Wave Height | Meter | m | — |
| Wind Speed | Meter per second | m/s | 1 kt = 0.514 m/s |