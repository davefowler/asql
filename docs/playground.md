# Interactive Playground

The best way to learn Analytic SQL is to use it. The interactive playground lets you write queries and see the generated SQL in real-time.

## Try It Now

**[Open the playground →](https://play.analyticsql.com)**

The playground provides:
- ✨ **Real-time compilation** - See SQL output as you type
- 🎨 **Clean interface** - Split-panel view with Analytic SQL input and SQL output
- 📝 **Example library** - Pre-built example queries to learn from
- 🔄 **Multiple dialects** - Switch between PostgreSQL, BigQuery, Snowflake, and more
- 📋 **Copy to clipboard** - Easy copying of queries

## Features

### Write and Compile

Type your Analytic SQL query in the left panel, and the SQL output appears automatically in the right panel. Switch between dialects to see how the same query generates different SQL for different databases.

### Example Queries

The playground includes example queries organized by category:
- Basic queries
- Filtering
- Aggregations
- Sorting and limiting
- Complex queries

Click any example to load it into the editor and start experimenting.

### Multiple Dialects

See how Analytic SQL compiles to different SQL dialects:
- PostgreSQL
- MySQL
- BigQuery
- Snowflake
- Redshift
- And more

The same Analytic SQL query works across all dialects—write once, run anywhere.

## Learning Path

1. **Start with examples** - Click an example query to see how it works
2. **Modify it** - Change table names, add filters, or try different aggregations
3. **Watch the SQL** - See how your changes affect the generated SQL
4. **Try different dialects** - Switch between dialects to see the differences
5. **Experiment** - Build your own queries from scratch

## Example Workflow

Here's a simple workflow to get started:

1. Open the playground
2. Click "Simple FROM" example
3. Modify it: `from users where status == "active"`
4. Add grouping: `group by country ( # as total_users )`
5. Sort results: `order by -total_users`
6. Limit output: `limit 10`

Watch the SQL update in real-time as you make changes!

---

**Ready to start?** [Open the playground →](https://play.analyticsql.com)
