# Chart Visualization Feature for ASQL

**Status**: Research / Ideation  
**Date**: 2025-01-14

## Inspiration

The [pqr.sql blog post](https://tanelpoder.com/posts/generate-qr-code-with-pure-sql-in-postgres/) demonstrates generating QR codes using pure SQL in PostgreSQL - no extensions needed. This raises an interesting question: could ASQL have a built-in `chart` clause to visualize query results directly in the terminal?

## Proposed Syntax

```asql
from users
  group by month(created_at) ( # )
  chart bar
```

Or with more options:

```asql
from sales
  group by region ( sum(amount) as revenue )
  chart bar --width=50 --color

from events  
  group by day(created_at) ( # as count )
  chart line --title="Daily Events"

from orders
  group by status ( # )
  chart pie
```

## Existing Implementations

### 1. Pure SQL Approaches (like the QR code post)

The QR code post shows that complex visualizations CAN be done in pure SQL using string manipulation. For charts, this is actually simpler:

```sql
-- Simple ASCII bar chart in pure SQL
WITH bins AS (
  SELECT
    FLOOR(value / 10) * 10 AS bin_floor,
    COUNT(*) AS count
  FROM data_table
  GROUP BY 1
)
SELECT
  bin_floor,
  REPEAT('█', count) AS bar  -- or REPEAT('|', count)
FROM bins
ORDER BY bin_floor;
```

**Pros:**
- No dependencies
- Works anywhere SQL works
- Could be ASQL's "transpilation" approach - add a `chart` clause that generates pure SQL with string manipulation

**Cons:**
- Limited chart types (basically just horizontal bars)
- Hard to get proper scaling, axes, legends
- Terminal width issues

### 2. DuckDB textplot Extension

DuckDB has a community extension called `textplot` that generates Unicode/ASCII charts directly in SQL:

```sql
INSTALL textplot FROM community;
LOAD textplot;

-- Generate inline bar for each row
SELECT name, tp_bar(score, min := 0, max := 100, width := 20) 
FROM scores;
```

Output: `🟥🟥🟥🟥🟥⬜⬜⬜⬜⬜`

**Approach:** Column-level visualization - adds a visualization column to results.

### 3. ChartSQL (Annotation-Based)

ChartSQL uses SQL comments as directives:

```sql
-- @chart: bar
-- @title: Sales by Month
-- @formats: currency
SELECT 
    TRUNC(date_closed, 'MONTH') AS Month,
    SUM(amount) AS Sales
FROM sales
GROUP BY 1;
```

**Approach:** Out-of-band metadata - the SQL is valid SQL, but metadata controls visualization.

This is similar to ASQL's proposed approach, but using comments instead of keywords.

### 4. Python Terminal Chart Libraries

Several Python libraries can render charts in the terminal:

| Library | Stars | Approach | Chart Types |
|---------|-------|----------|-------------|
| **plotext** | ~3k | Matplotlib-like API | scatter, line, bar, histogram, datetime |
| **termgraph** | ~3k | Data + Args | bar, histogram, calendar heatmap |
| **py-ascii-graph** | ~400 | Simple histograms | horizontal bar |
| **cheshire-sql** | new | SQL-native TUI | bar, line, scatter, histogram, pie, waffle |

**Plotext example:**
```python
import plotext as plt
plt.bar(["A", "B", "C"], [10, 20, 15])
plt.show()
```

**Termgraph example:**
```python
from termgraph import BarChart, Data, Args
data = Data([[10], [20], [15]], ["A", "B", "C"])
BarChart(data, Args(title="My Chart")).draw()
```

### 5. External Tools (YouPlot, Cheshire)

**YouPlot** (Ruby): Pipe CSV data to generate terminal charts
```bash
duckdb -s "COPY (SELECT ...) TO '/dev/stdout' WITH (FORMAT csv)" \
| uplot bar -d, -H -t "Chart Title"
```

**Cheshire** (Python): Full SQL visualization TUI
```bash
cheshire "SELECT category, SUM(amount) FROM sales GROUP BY 1" --chart bar
```

## Implementation Options for ASQL

### Option A: Pure SQL Transpilation (Most ASQL-like)

Transform `chart` into SQL that produces ASCII output. Stay true to ASQL's philosophy of "just transpiles to SQL."

```asql
from users
  group by country ( # as cnt )
  chart bar
```

Transpiles to:
```sql
WITH data AS (
  SELECT country, COUNT(*) AS cnt
  FROM users
  GROUP BY country
),
scaled AS (
  SELECT country, cnt, 
         ROUND(cnt * 50.0 / MAX(cnt) OVER()) AS bar_width
  FROM data
)
SELECT 
  RPAD(country, 15) AS label,
  REPEAT('█', bar_width::INT) AS bar,
  cnt AS value
FROM scaled
ORDER BY cnt DESC;
```

**Pros:**
- Stays true to ASQL = SQL philosophy
- Works with any database that supports REPEAT()
- No Python dependencies at runtime

**Cons:**
- Limited to simple horizontal bar charts
- Hard to do proper axes, scaling, colors
- Different databases have different string functions

### Option B: Post-Processing in CLI (Most Practical)

Keep ASQL transpilation clean. Add visualization as a CLI concern.

```bash
asql run "from users group by country ( # )" --chart bar
```

Or with the `chart` clause parsed as metadata, not transpiled:

```asql
from users
  group by country ( # )
  chart bar
```

The compiler:
1. Strips `chart bar` from the query
2. Stores it as metadata
3. Transpiles the rest to SQL normally
4. CLI executes SQL, then pipes results to plotext/termgraph

**Pros:**
- Rich visualization options (colors, multiple chart types, proper scaling)
- Separates concerns (ASQL = query language, CLI = presentation)
- Can integrate with existing mature libraries

**Cons:**
- `chart` becomes CLI-only, not part of transpiled SQL
- Requires Python runtime for visualization

### Option C: Hybrid - Inline Sparklines + CLI Charts

Combine both:

1. **Inline sparklines** (transpiled to SQL):
   ```asql
   from users
     group by country ( #, sparkline(#) )
   ```
   Transpiles to SQL with REPEAT() for simple inline bars.

2. **Full charts** (CLI post-processing):
   ```asql
   from users
     group by country ( # )
     chart bar
   ```
   The `chart` clause triggers CLI visualization.

### Option D: Generate HTML/SVG (Web-Focused)

For the playground or web contexts:

```asql
from users
  group by country ( # )
  chart bar
```

Outputs JSON with chart spec:
```json
{
  "sql": "SELECT country, COUNT(*) FROM users GROUP BY country",
  "chart": {
    "type": "bar",
    "x": "country",
    "y": "count"
  }
}
```

The frontend renders using Vega-Lite, Chart.js, or similar.

## Recommended Approach

**Option B (Post-Processing in CLI)** with **Option C enhancements** seems most practical:

### Phase 1: CLI Chart Flag
```bash
asql run "from users group by country ( # )" --chart bar
```

- Use **plotext** as the rendering library (matplotlib-like API, good terminal support)
- Chart types: bar, line, scatter, histogram
- Auto-detect x/y from query results (first column = x, numeric columns = y)

### Phase 2: `chart` Clause as Metadata
```asql
from users
  group by country ( # as count )
  chart bar
```

- Parser recognizes `chart <type>` as a terminal clause
- Compiler strips it and stores as metadata
- CLI reads metadata and renders

### Phase 3: Inline Sparklines (Optional)
```asql
from users
  group by country ( 
    #,
    bar(#)  -- inline ASCII bar
  )
```

Transpiles to SQL with string manipulation.

## Chart Type Auto-Detection

ChartSQL's "Auto Mode" is smart:

| Result Shape | Auto Chart |
|--------------|------------|
| 1 string + 1 numeric | horizontal bar |
| 1 date + 1 numeric | line (time series) |
| 2 numerics | scatter |
| 1 string + multiple numerics | grouped bar |
| single numeric column | histogram |

ASQL could do similar inference.

## Prior Art Summary

| Tool | Approach | Integration |
|------|----------|-------------|
| DuckDB textplot | SQL extension, inline | Per-column |
| ChartSQL | SQL comments as directives | Out-of-band |
| YouPlot | Pipe to external tool | Post-process |
| Cheshire | Python TUI | Full app |
| pgVis | SQL extension | Browser render |

## Open Questions

1. **Should `chart` be part of ASQL grammar or CLI-only?**
   - Grammar: more integrated, but couples query language to presentation
   - CLI-only: cleaner separation, but less discoverable

2. **What's the minimum viable chart set?**
   - Start with: bar, line
   - Later: scatter, histogram, pie

3. **How to handle large result sets?**
   - Auto-truncate to N bins?
   - Warning if > 100 rows?

4. **Color support?**
   - Unicode blocks (█, ▓, ░) work everywhere
   - ANSI colors need terminal support detection

5. **Export options?**
   - `--chart bar --output chart.png` using plotext's save feature?

## References

- [pqr.sql - QR Codes in Pure SQL](https://tanelpoder.com/posts/generate-qr-code-with-pure-sql-in-postgres/)
- [DuckDB textplot extension](https://duckdb.org/community_extensions/extensions/textplot.html)
- [ChartSQL documentation](https://docs.chartsql.com/basics/quick-start)
- [plotext - Python terminal plots](https://pypi.org/project/plotext/)
- [termgraph - Terminal graphs](https://github.com/mkaz/termgraph)
- [YouPlot - Terminal plotting](https://github.com/red-data-tools/YouPlot)
- [Cheshire - SQL visualization TUI](https://pypi.org/project/cheshire-sql/)
