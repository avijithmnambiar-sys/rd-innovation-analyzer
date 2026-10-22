# Demonstration video plan

Each member presents their own page, as agreed in the project plan. Record the
screen at 1920x1080, one take per member, then join the four takes in order.

## Before recording

1. Create a clean virtual environment and install from `requirements.txt`, so the
   run shown in the video is the run Jayasurya verifies for submission.
2. Start the app with `streamlit run home.py` and open `http://localhost:8501`.
3. Collapse the browser bookmarks bar and set the browser zoom to 100%.
4. Keep a copy of the `data/` folder, because the video shows real add, edit and
   delete operations that change the CSV files.

## Running order (about six minutes)

| Time | Who | What is on screen |
| --- | --- | --- |
| 0:00-0:40 | Manish | Home: the question the app answers, SDG 9 targets, the four modules, the combined country profile and the composite score |
| 0:40-2:00 | Manish | Research Spending: add a record, filter by sector and year, the 2%-of-GDP gap and growth table, download the report |
| 2:00-3:20 | Avijith | Patents: the regex search box, the pie and grouped bar, patents per billion dollars, then the shared `CSVManager` in the editor |
| 3:20-4:40 | Jayasurya | Institutions: add and edit an institution, citations per publication by type, the scatter chart, then undo a deletion |
| 4:40-6:00 | Surya | Infrastructure: data quality, add a record, tier and year filters, the group comparison, then the activity log showing the change just made |

## What each dataset owner must show

- One create that is **rejected**, with the on-page message, followed by a valid one.
- One edit through the pre-filled form.
- One delete with the confirmation step.
- Both charts redrawing after a filter change.
- The report download with its timestamp.

## Surya's segment, in order

1. Open the Infrastructure page and read the Data Quality metrics aloud.
2. Expand "Missing values by column" and point out the deliberately blank cells.
3. Try to add a record for a country-year that already exists; show the error.
4. Add a valid record; show the success message and the new row in the table.
5. Filter to the High tier, then clear it, so both charts redraw.
6. Open Group comparison and read the High-minus-Low gap sentence.
7. Scroll to the Activity Log and show the entry written by step 4.
8. Download the summary report and open it to show the timestamp and filters.
