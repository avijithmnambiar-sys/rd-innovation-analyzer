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
