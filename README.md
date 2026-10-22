# Global R&D and Systems Innovation Analyzer

A second-year Introduction to Python project exploring how research investment,
patents, institutions and infrastructure contribute to innovation. It connects
to SDG 9, especially research capacity (9.5) and ICT access (9.c).

## Features

- Research Spending: data quality checks, validated create/read/update/delete,
  country search, sector/year filters, sorting, permanent atomic CSV saves,
  filtered CSV and timestamped summary downloads.
- Analysis: sector averages, annual expenditure, country-year benchmark gaps,
  countries reaching the project's 2%-of-GDP benchmark, period growth and
  year-on-year changes with Up/Down/Unchanged indicators.
- Filtered charts: ten highest spenders using each country's latest selected
  observation and country expenditure trends over time.
- Home: introduction, team ownership, module navigation, combined country
  profiles and normalized innovation scores with explicit missing-data coverage.
- Existing Patents and Institutions pages remain owned by their teammates.

## Team responsibilities

| Member | Dataset and page | Shared responsibility |
| --- | --- | --- |
| Manish J | Research Spending — `pages/1_RD_Investment.py` | Home, country profiles, composite score, README |
| Avijith M Nambiar | Patents & IP Output — `pages/2_Patents.py` | Shared `CSVManager` |
| Jayasurya Jay Nair | Research Institutions — `pages/3_Institutions.py` | Dependencies and clean-install checks |
| Surya R | Innovation Infrastructure — `pages/4_Infrastructure.py` | Repository, screenshots and demonstration video |

## Installation and running

Python 3.10 or newer and pip are required. Run these commands in the repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run home.py
```

On macOS/Linux use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`.
The application normally opens at `http://localhost:8501`. Use the sidebar or
Home links to navigate. The application uses absolute dataset paths relative to
its source files. Stop the server with Ctrl+C.

For the automated checks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.test_tmp
```

Tests use temporary datasets for modifications. They cover inheritance, read-only
properties, CRUD persistence, validation, failed atomic replacement, missing and
malformed CSVs, filtering, calculations, reports, Home joins and score calculation.
Streamlit AppTest checks page rendering and interactions without changing the
committed datasets.

## Project structure

```text
home.py                         Home landing page
csv_manager.py                  Avijith's shared CSV base class (unchanged)
rd_manager.py                   Manish's ResearchSpendingManager and report builder
country_profile.py              Read-only Home integration and scoring
pages/
  1_RD_Investment.py            Research Spending management and analysis
  2_Patents.py                  Avijith's existing module
  3_Institutions.py             Jayasurya's existing module
data/
  rd_investment.csv             Synthetic sector contributions
  patents.csv                   Existing teammate data
  institutions.csv              Existing teammate data
  README.md                     Spending data assumptions
requirements.txt                Runtime dependencies
requirements-dev.txt            Test dependencies
tests/                          Temporary-data and Streamlit regression tests
```

The Infrastructure page and `data/infrastructure.csv` have not been supplied in
the current repository. Home shows an unavailable navigation control and missing
score component until Surya adds them. No teammate file is created or modified by
Home. A minimal dependency list is included because none existed in the baseline;
Jayasurya can maintain it as further modules arrive.

## Data sources and spending assumptions

The supplied spending CSV contains **144 synthetic sample records**, explicitly
identified by `SYN_RD` IDs: 12 countries, four years (2021–2024), and Business,
Government and Higher Education funding sectors. They are illustrative values,
not official World Bank/UNESCO/OECD observations. See `data/README.md` for their
construction and units. Existing teammate sample CSVs are preserved; they contain
no authoritative source metadata and should not be interpreted as official data.

The required spending columns are `record_id`, `country`, `iso_code`, `year`,
`gerd_pct_gdp`, `gerd_usd_millions`, `researchers_per_million`, `funding_sector`.
Each row's expenditure and GDP percentage are **sector contributions**, summed
once per country-year. Researchers per million is a repeated national density,
so it is never summed. New records require unique IDs, unique country/year/sector
keys, consistent country/ISO mappings, matching within-year workforce densities,
finite non-negative values, years from 1900 to the current year, and GDP percentages
from 0 to 100. Accepted sectors also include Private Non-profit.

Missing or empty spending files load as an empty table. Wrong headers, malformed
CSV and file errors produce clear messages. Invalid numeric source values are
retained on disk and treated as missing for analysis. Ambiguous duplicate keys
are excluded from statistics; duplicate IDs require source correction before a
single record can be edited or deleted. Other records can still be managed.
Writes reuse `CSVManager.save`: write a temporary file in the destination folder,
then atomically replace the original. As a small local CSV application, concurrent
editors should coordinate changes; it has no multi-user database transactions.

Sector averages are means of observed sector contributions. Totals use all present
contributions; any missing contribution makes that total unavailable. Annual
totals report country coverage and represent this sample, not worldwide spending.
Sector filters produce partial coverage, including partial benchmark comparisons.
The shortfall is `max(2 - gerd_pct_gdp, 0)` in percentage points. The 2% benchmark
is a project comparison value, not an official universal SDG target.

Year-on-year growth is `100 * (current / previous - 1)` only for adjacent years
with identical sector coverage and a positive previous value. Period growth uses
the earliest and latest valid observations with identical endpoint coverage;
otherwise it is unavailable. Missing observations and zero baselines are not
converted to zero growth. Changes in country/sector coverage must be considered
when comparing aggregate totals. Amounts are nominal USD millions; no inflation
adjustment or currency conversion is applied.

## Combined profiles and composite score

Home reads all available datasets and matches annual observations by country and
the selected year: spending `year`, patents `filing_year`, infrastructure `year`.
USA/United States and UK/United Kingdom aliases are normalized in memory. Patent
grants are summed by country-year; infrastructure allows one unambiguous
country-year record. Missing, malformed, incomplete and duplicate-key teammate
data is handled without writing to those CSVs. Missing numeric observations are
not assumed to be zero.

Institutions have **no observation year**. `founded_year` is never joined to annual
data. Institution counts and impact are an undated snapshot shown alongside each
year's metrics. Impact is total citations / total publications across institutions
with valid counts and positive publications, so zero-publication records are
excluded from the ratio. It is not an unweighted average of individual ratios.

Four higher-is-better headline metrics receive equal weight:

1. R&D expenditure as a percentage of GDP, summed across funding sectors.
2. Patent grants in the selected year.
3. Institution citations per publication from the undated snapshot.
4. Infrastructure innovation index in the selected year.

Each metric is scaled separately across available countries in the selected year:

```text
component_score = 100 * (value - minimum) / (maximum - minimum)
composite_score = (rd_score + patents_score + impact_score + infrastructure_score) / 4
```

If all available values of a metric are identical, its score is 50. Missing values
remain missing. A complete composite requires all four components. A separately
labelled **provisional score** averages only available components and displays
coverage (for example, 3/4). Provisional scores with different coverage are not
equivalent rankings. Scores are relative to this sample's country coverage and
can change when the sample changes; they are not official innovation rankings.

The shared base class and existing teammate pages/data are preserved. Member 1's
work does not complete another member's unfinished features.
