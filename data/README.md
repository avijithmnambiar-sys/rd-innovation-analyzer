# Data notes

`rd_investment.csv` contains **144 synthetic demonstration records**, identified by
the `SYN_RD` prefix. They were created for this college project and are not measured
country statistics. There are 12 countries, 2021–2024, and three sectors per country-year.
No external data source is claimed. Existing teammate CSV files have been preserved.

One spending row represents one **funding sector contribution** in a country-year:

- `gerd_usd_millions`: that sector's expenditure, in nominal USD millions.
- `gerd_pct_gdp`: that sector's contribution as a percentage of national GDP.
- `researchers_per_million`: the national workforce figure, repeated across sectors.
- `record_id`: unique text identifier; `iso_code`: three-letter country code.

For the supplied sample, Business contributes 60%, Government 30%, and Higher
Education 10% of each synthetic national total. Annual synthetic expenditure grows
by 5%; national GDP percentage rises by 0.05 percentage points per year; researchers
per million rises by 20 per year. Starting values are illustrative only.

Sum sector expenditure and sector GDP percentages once per country-year. Never
repeat an entire national total in each sector row. Never sum workforce density.
A sector filter deliberately represents partial coverage. Private Non-profit is
also an accepted sector for new records. Rows must be unique by country/year/sector.

Invalid source numbers are shown as missing in analysis and retained on disk until
explicitly repaired. Source rows with missing keys, invalid codes/sectors, duplicate
IDs, or duplicate country/year/sector keys are excluded from analysis. An ambiguous
duplicate ID must be corrected in the source CSV before a single row can be edited
or deleted. A missing contribution makes its numeric total unavailable rather than
silently treating it as zero. Year-on-year growth requires adjacent years and equal
sector coverage; period growth requires equal coverage at the endpoints. Zero
starting expenditure gives unavailable percentage growth. Year totals show country
coverage; they are totals of the sample, not global estimates.

Replace sample records with sourced sector-level observations before drawing real
conclusions. Record the source, currency basis, observation year and coverage here.
Do not mix national totals with sector contributions. In the institution dataset,
`founded_year` describes establishment; it cannot be used for a country-year join.

## Infrastructure notes

`infrastructure.csv` contains **48 synthetic demonstration records**, identified by
the `SYN_INF` prefix. They were created for this college project and are not measured
country statistics. There are the same 12 countries as the spending file and the same
four years, 2021–2024, with exactly one record per country-year. No external data
source is claimed.

One infrastructure row represents one **country-year observation**:

- `internet_penetration_pct`: share of the population using the internet, 0 to 100.
- `hightech_exports_pct`: high-technology share of manufactured exports, 0 to 100.
- `stem_graduates_per_1000`: STEM graduates per 1000 people; a density, not a percentage.
- `innovation_index_score`: composite index score on a 0 to 100 scale.
- `infrastructure_tier`: connectivity band derived from `internet_penetration_pct`
  (High from 85%, Medium from 60%, Low below 60%).
- `record_id`: unique text identifier.

For the supplied sample, each country starts from an illustrative 2021 baseline and
rises by 1.6 percentage points of internet penetration, 0.4 points of high-technology
export share, 0.18 graduates per 1000 and 0.7 index points per year. Penetration is
capped at 99%. Three cells are deliberately blank so that the Data Quality panel has
real missing values to report.

Rows must be unique by country and by country-year, and a stored tier must match its
own penetration. Invalid source numbers are shown as missing in analysis and retained
on disk until explicitly repaired; source rows with missing keys, duplicate IDs or
duplicate country-years are excluded from analysis. A missing value makes its average
unavailable for that row rather than counting as zero. Per-tier averages depend on
which countries and years are in view, so they are comparisons within this sample and
not global estimates. `index_per_stem_graduate` is unavailable where the graduate
figure is missing or zero.

Replace sample records with sourced country-year observations before drawing real
conclusions. Record the source, the definition of each indicator, the observation
year and coverage here. Internet penetration stands in for SDG target 9.c (access to
information and communications technology); it is not the official indicator series.

`infrastructure_log.csv` is the activity log for the Infrastructure page: one row per
successful change, with `logged_at_utc`, `action` (ADD, UPDATE or DELETE), `record_id` and
`detail`. It is written only by `pages/4_Infrastructure.py`, is never read by analysis, and
is safe to delete; the page recreates it on the next change.
