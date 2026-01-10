"""Chart Generation Tool for Vanna Agent.

Generates ECharts configuration from query results using LLM.
"""

from typing import Any, Dict, List, Optional
import json
import logging

from vanna.core.tool import Tool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class ChartGenerationTool(Tool):
    """Tool for generating chart visualizations from query results."""
    
    # Define as class attributes (required by abstract base class)
    name = "generate_chart"
    description = "Generate chart visualization from query results"
    
    def __init__(self, llm_service):
        """Initialize chart generation tool.
        
        Args:
            llm_service: LLM service instance compatible with Vanna's interface
        """
        self.llm_service = llm_service
    
    def get_args_schema(self) -> Dict[str, Any]:
        """Return tool arguments schema for Vanna Agent."""
        return {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "description": "List of column definitions with name and type",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"}
                        }
                    }
                },
                "column_names": {
                    "type": "array",
                    "description": "Simple list of column names",
                    "items": {"type": "string"}
                },
                "data": {
                    "type": "array",
                    "description": "Query result data rows",
                    "items": {"type": "object"}
                },
                "chart_type": {
                    "type": "string",
                    "description": "Desired chart type (auto, bar, line, pie, scatter, area)",
                    "default": "auto"
                }
            },
            "required": ["columns", "column_names", "data"]
        }
    
    async def execute(
        self,
        context: ToolContext,
        columns: List[Dict[str, str]],
        column_names: List[str],
        data: List[Dict[str, Any]],
        chart_type: str = "auto"
    ) -> ToolResult:
        """Execute chart generation.
        
        Args:
            context: Tool execution context from Vanna
            columns: Column definitions with name and type
            column_names: Simple list of column names
            data: Query result rows
            chart_type: Desired chart type (auto, bar, line, pie, etc.)
            
        Returns:
            ToolResult with chart configuration
        """
        logger.info(f"Generating chart: {len(data)} rows, {len(columns)} columns, type={chart_type}")
        
        try:
            # Build system prompt with extensive chart generation guidelines
            system_prompt = self._build_system_prompt()
            
            # Build user prompt with data
            user_prompt = self._build_user_prompt(
                columns=columns,
                column_names=column_names,
                data=data,
                chart_type=chart_type
            )
            
            # Call LLM
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=4096
            )
            
            # Parse response
            chart_config_text = response.get("content", "")
            chart_config = self._parse_chart_config(chart_config_text)
            
            # Extract chart type from config
            detected_chart_type = "bar"
            if chart_config.get("series") and len(chart_config["series"]) > 0:
                detected_chart_type = chart_config["series"][0].get("type", "bar")
            
            logger.info(f"Chart generated successfully: type={detected_chart_type}")
            
            return ToolResult(
                success=True,
                data={
                    "chart_config": chart_config,
                    "chart_type": detected_chart_type
                }
            )
            
        except Exception as e:
            logger.error(f"Chart generation failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=str(e)
            )
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for chart generation."""
        return """You are a data visualization expert specializing in Apache ECharts.
Your task is to analyze data and create the perfect chart visualization.

## 1. Data Structure Analysis

Before selecting a chart type, analyze the data:
- **Column types**: Identify numeric, categorical, datetime, and boolean columns
- **Independent variable**: Usually the x-axis (time, categories, or continuous values)
- **Dependent variable(s)**: Usually the y-axis (metrics, measurements, counts)
- **Data cardinality**: Count unique values in categorical columns
- **Missing values**: Handle nulls by excluding or using placeholder values
- **Data range**: Check min/max for appropriate axis scaling

### Date Column Consolidation

When data contains multiple columns representing the same date (e.g., year, month_id, month_name, quarter, etc.), consolidate them into a single formatted date string:

**Format: `YYYY/MM` or `YYYY/MM/DD`**

Examples:
| Original Columns | Consolidated Output |
|------------------|---------------------|
| year: 2023, month_id: 1, month_name: "JAN" | "2023/01" |
| year: 2023, month: 3, month_name: "March" | "2023/03" |
| year: 2022, quarter: 2 | "2022/Q2" |
| year: 2024, month: 12, day: 25 | "2024/12/25" |
| fiscal_year: 2023, period: 6 | "2023/06" |

**Rules:**
1. Always use the numeric month (01-12), NOT the month name in the final output
2. Pad single-digit months with leading zero (1 → "01", 9 → "09")
3. Use "/" as the date separator
4. If only year and quarter exist, format as "YYYY/Q#"
5. Ignore redundant columns (month_name when month_id exists)
6. Sort data chronologically by the consolidated date

**Detection patterns for date columns:**
- Year: "year", "yr", "fiscal_year", "fy"
- Month: "month", "month_id", "month_num", "mm", "month_name", "month_abbr"
- Day: "day", "dd", "day_of_month"
- Quarter: "quarter", "qtr", "q"

## 2. Chart Type Selection

Choose the BEST chart type based on your analysis:

| Chart Type | Use When | Data Requirements |
|------------|----------|-------------------|
| **Line** | Time series, trends, continuous data | DateTime x-axis, numeric y-axis |
| **Bar** | Comparing categories, rankings | Categorical x-axis, numeric y-axis |
| **Pie/Doughnut** | Proportions, percentages | Single series, ≤10 categories |
| **Scatter** | Correlation between two variables | Two numeric columns |
| **Area** | Cumulative totals, volume over time | DateTime x-axis, numeric y-axis |
| **Heatmap** | Matrix data, density patterns | Two categorical + one numeric |
| **Radar** | Multi-dimensional comparison | 3-8 metrics per item |
| **Candlestick** | Financial OHLC data | Open, High, Low, Close values |

## 3. String Formatters (No JavaScript Functions!)

Use ECharts template strings instead of functions:

### Tooltip Formatters:
- `{a}` - Series name
- `{b}` - Category name (x-axis value)
- `{c}` - Data value
- `{d}` - Percentage (pie/funnel charts)
- `{e}` - Data name

### Label Formatters:
- `"{b}: {c}"` → "January: 150"
- `"{b}\\n{d}%"` → "Sales\\n25%"
- `"{c} units"` → "150 units"

### Axis Label Formatters:
- `"{value} kg"` → "100 kg"
- `"{value}%"` → "50%"

## 4. Number Formatting

Apply smart formatting to all numbers in axis labels, tooltips, and data labels for readability.

### Large Numbers — Use K/M/B Abbreviations:

| Value Range | Format | Examples |
|-------------|--------|----------|
| < 1,000 | Whole number | 45, 850, 999 |
| 1,000 - 999,999 | K suffix | 1.2K, 45K, 850K |
| 1,000,000 - 999,999,999 | M suffix | 1.2M, 45M, 850M |
| ≥ 1,000,000,000 | B suffix | 1.2B, 45B |

### Rounding Rules:
- Show maximum 2 decimal places: **1.23M** (not 1.235455M)
- Drop decimal if .0: **2M** (not 2.0M)
- For values < 1000: Show whole numbers or 1 decimal if needed

### Auto-Detect Data Type from Column Name:

**CURRENCY** (add $ prefix):
Column name contains: `price`, `amount`, `revenue`, `sales`, `cost`, `profit`, `total`, `budget`, `spend`, `payment`, `balance`
→ Format: **$1.2M**, **$850K**, **$45**

**PERCENTAGE** (add % suffix):
Column name contains: `percent`, `pct`, `rate`, `ratio`, `share`, `growth`, `margin`, `change`
→ Format: **45.5%**, **12%**, **0.5%**

**COUNTS/UNITS** (no prefix/suffix):
Column name contains: `count`, `quantity`, `units`, `orders`, `users`, `customers`, `items`, `transactions`
→ Format: **1.2K**, **850**, **45M**

### CRITICAL: Transform Data Values!

You MUST transform the actual data values, not just the formatter!

**EXAMPLE: Sales in Thousands**

Original data: [676763, 520818, 678560]
Max value: 678,560 → Use thousands (K)

**CORRECT Implementation:**
```json
"yAxis": { 
  "type": "value",
  "axisLabel": { "formatter": "${value}K" }
},
"series": [{ 
  "data": [676.8, 520.8, 678.6],
  "label": { "show": true, "formatter": "${value}K" }
}],
"tooltip": { "formatter": "{b}<br/>{a}: ${c}K" }
```
✅ Chart shows: $677K, $521K, $679K

## 5. Layout and Spacing Requirements

**CRITICAL - Prevent Overlapping Elements:**
- Title and legend must NEVER overlap
- If title is centered, place legend on the left or right (not top-center)
- Use grid padding (top: 15-20%, left: 8-10%) to ensure space for all elements

**Recommended Layouts:**
1. **Title centered + Legend left/right**: `{title: {left: "center", top: 10}, legend: {left: "left", top: "15%"}}`
2. **Title left + Legend right**: `{title: {left: "left"}, legend: {right: 10, top: "middle"}}`

## 6. Return Requirements

- Return ONLY valid JSON (no explanatory text before or after)
- Do NOT wrap JSON in markdown code blocks (no ```json)
- Do NOT include JavaScript functions
- Ensure all property names are double-quoted
- Use arrays for data, not objects with numeric keys

## 7. Edge Case Handling

- **>10 categories for pie**: Aggregate smallest values into "Other"
- **Empty dataset**: Return error message in JSON: {"error": "No data provided"}
- **Single data point**: Use bar chart or display as single metric card
- **All null values in a column**: Exclude that series or use 0 as placeholder
- **Negative values in pie chart**: Use bar chart instead
- **Multiple date columns**: Consolidate into single YYYY/MM format
- **Unsorted date data**: Always sort chronologically before generating chart
- **Title/Legend overlap**: ALWAYS follow Section 5 layout guidelines
- **Large numbers**: ALWAYS apply Section 4 number formatting rules"""
    
    def _build_user_prompt(
        self,
        columns: List[Dict[str, str]],
        column_names: List[str],
        data: List[Dict[str, Any]],
        chart_type: str
    ) -> str:
        """Build user prompt with data."""
        
        chart_type_instruction = ""
        if chart_type != "auto":
            chart_type_instruction = f"""

## CHART TYPE OVERRIDE

The user has selected: **{chart_type.upper()} CHART**

You MUST generate a {chart_type} chart. Do not suggest a different type.
Adapt the data to fit this chart type as best as possible.

If the data is not ideally suited for this chart type, still generate the chart
but you may add a "warning" field in the JSON response explaining any limitations.
Example: {{"warning": "Pie charts work best with ≤10 categories. Showing top 10 only.", ...}}
"""
        
        return f"""Create a chart visualization for this data.{chart_type_instruction}

Column Names:
{json.dumps(column_names)}

Column Information (with detected types):
{chr(10).join([f"- {col['name']} ({col['type']})" for col in columns])}

Data (first {len(data)} rows):
{json.dumps(data[:100], indent=2)}

Instructions:
1. {'Create a ' + chart_type + ' chart (user-selected)' if chart_type != 'auto' else 'Analyze the data and choose the BEST chart type'}
2. Create a complete ECharts configuration
3. Make the title descriptive and meaningful
4. Format numbers properly (add commas, decimals as needed)
5. Add clear axis labels
6. Create professional tooltips
7. Use an appropriate color scheme
8. **CRITICAL**: Ensure title and legend do NOT overlap (follow layout guidelines)

Return ONLY the ECharts configuration JSON. No explanatory text."""
    
    def _parse_chart_config(self, text: str) -> Dict[str, Any]:
        """Parse LLM response to extract chart configuration."""
        logger.info(f"Parsing chart config (first 500 chars): {text[:500]}")
        
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        # Strip whitespace
        text = text.strip()
        
        # Find JSON object boundaries
        if not text.startswith("{"):
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]
        
        # Parse JSON
        chart_config = json.loads(text)
        
        # Validate
        if not isinstance(chart_config, dict):
            raise ValueError("Chart config is not a valid object")
        
        if "series" not in chart_config:
            raise ValueError("Chart config missing 'series' field")
        
        return chart_config
