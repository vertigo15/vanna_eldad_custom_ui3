"""FastAPI application for Vanna 2.0 Text-to-SQL."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json

from src.agent.vanna_agent import create_vanna_agent, VannaTextToSqlAgent
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global agent instance
agent: Optional[VannaTextToSqlAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global agent
    
    # Startup: Initialize Vanna agent
    logger.info("🚀 Initializing Vanna Text-to-SQL Agent...")
    try:
        agent = await create_vanna_agent()
        logger.info("✅ Vanna Agent ready!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent: {e}")
        raise
    
    yield
    
    # Shutdown: Cleanup
    logger.info("👋 Shutting down...")
    if agent:
        await agent.close()


app = FastAPI(
    title="Vanna 2.0 Text-to-SQL",
    description="Natural language to SQL using Azure OpenAI and pgvector",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class QueryRequest(BaseModel):
    """Request model for SQL query."""
    question: str
    user_context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for SQL query."""
    question: str
    sql: Optional[str]
    results: Optional[Dict[str, Any]]
    explanation: Optional[str]
    prompt: Optional[str] = None
    error: Optional[str]


class ColumnInfo(BaseModel):
    """Column information for chart generation."""
    name: str
    type: str  # "numeric", "category", or "date"


class GenerateChartRequest(BaseModel):
    """Request model for chart generation."""
    columns: List[ColumnInfo]
    column_names: List[str]
    sample_data: List[List[Any]]
    all_data: Optional[List[List[Any]]] = None
    chart_type: Optional[str] = "auto"  # 'auto' lets LLM decide, or specific type like 'bar', 'line', etc.


class GenerateChartResponse(BaseModel):
    """Response model for chart generation."""
    chart_config: Dict[str, Any]  # Complete ECharts configuration
    chart_type: str  # Type chosen by LLM: "line", "bar", "pie", etc.


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Vanna 2.0 Text-to-SQL",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_ready": agent is not None,
        "services": {
            "llm": "Azure OpenAI gpt-5.1",
            "embeddings": "text-embedding-3-large-2",
            "vector_store": "pgvector",
            "data_source": "AdventureWorksDW"
        }
    }


@app.post("/api/query", response_model=QueryResponse)
async def query_database(request: QueryRequest):
    """
    Process natural language question and execute SQL.
    
    Args:
        request: QueryRequest with question and optional user context
        
    Returns:
        QueryResponse with SQL, results, and explanation
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    logger.info(f"Processing question: {request.question}")
    
    try:
        result = await agent.process_question(
            question=request.question,
            user_context=request.user_context or {}
        )
        
        logger.info(f"Query result: SQL={'✓' if result['sql'] else '✗'}, "
                   f"Results={'✓' if result['results'] else '✗'}, "
                   f"Error={'✗' if result['error'] else '✓'}")
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tables")
async def list_tables():
    """List all tables in the database."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        tables = await agent.sql_runner.list_tables()
        return {"tables": tables}
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        schema = await agent.sql_runner.get_table_schema(table_name)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        return {"table": table_name, "schema": schema}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class GenerateInsightsRequest(BaseModel):
    """Request model for insights generation."""
    dataset: Dict[str, Any]  # Query results with 'rows' and 'columns'
    question: str  # Original user question


class GenerateInsightsResponse(BaseModel):
    """Response model for insights generation."""
    summary: str
    findings: List[str]
    suggestions: List[str]


@app.post("/api/generate-insights", response_model=GenerateInsightsResponse)
async def generate_insights_endpoint(request: GenerateInsightsRequest):
    """
    Generate insights for query results using LLM.
    
    Analyzes the dataset and provides patterns, findings, and suggestions.
    
    Args:
        request: GenerateInsightsRequest with dataset and question
        
    Returns:
        GenerateInsightsResponse with summary, findings, and suggestions
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Generating insights for: {request.question[:50]}...")
    
    try:
        # Import insight service
        from src.agent.insight_service import generate_insights
        
        # Get context from agent memory (for business rules)
        context = await agent.memory.get_context_for_question(request.question)
        
        # Generate insights (async call)
        insights = await generate_insights(
            dataset=request.dataset,
            context=context,
            original_question=request.question,
            llm_service=agent.llm
        )
        
        logger.info(f"Insights generated: {len(insights.get('findings', []))} findings")
        
        return GenerateInsightsResponse(
            summary=insights.get("summary", "Analysis complete"),
            findings=insights.get("findings", []),
            suggestions=insights.get("suggestions", [])
        )
        
    except Exception as e:
        logger.error(f"Insights generation error: {e}", exc_info=True)
        # Return graceful fallback
        return GenerateInsightsResponse(
            summary="Unable to generate insights",
            findings=[],
            suggestions=[]
        )


class GenerateProfileRequest(BaseModel):
    """Request model for data profiling."""
    dataset: Dict[str, Any]  # Query results with 'rows' and 'columns'


@app.post("/api/generate-profile")
async def generate_profile_endpoint(request: GenerateProfileRequest):
    """
    Generate a comprehensive data profile report using ydata-profiling.
    
    Args:
        request: GenerateProfileRequest with dataset (rows and columns)
        
    Returns:
        HTML string containing the full profile report
    """
    logger.info("Generating data profile report")
    
    try:
        # Import profiling service
        from src.agent.profiling_service import generate_profile_report
        
        # Generate profile report (async call)
        html_report = await generate_profile_report(request.dataset)
        
        logger.info(f"Profile report generated: {len(html_report)} bytes")
        
        return {"html": html_report}
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Profile generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-chart", response_model=GenerateChartResponse)
async def generate_chart(request: GenerateChartRequest):
    """
    Generate chart configuration using LLM.
    
    The LLM analyzes the data and creates a complete ECharts configuration,
    deciding chart type, styling, colors, formatting, and all visual aspects.
    
    Args:
        request: GenerateChartRequest with columns and data
        
    Returns:
        GenerateChartResponse with ECharts config and chart type
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    chart_type_param = request.chart_type or "auto"
    logger.info(f"Generating chart for {len(request.sample_data)} rows, {len(request.columns)} columns, type={chart_type_param}")
    
    try:
        # System prompt: Instruct LLM to be a chart expert
        system_prompt = """You are a data visualization expert specializing in Apache ECharts.
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
- `"{b}\n{d}%"` → "Sales\n25%"
- `"{c} units"` → "150 units"

### Axis Label Formatters:
- `"{value} kg"` → "100 kg"
- `"{value}%"` → "50%"

## 4. Layout and Spacing Requirements

**CRITICAL - Prevent Overlapping Elements:**
- Title and legend must NEVER overlap
- If title is centered, place legend on the left or right (not top-center)
- If title is on left, place legend on the right or bottom
- Use grid padding (top: 15-20%, left: 8-10%) to ensure space for all elements
- For charts with legends, set title top position to ensure spacing

**Recommended Layouts:**
1. **Title centered + Legend left/right**: `{title: {left: "center", top: 10}, legend: {left: "left", top: "15%"}}`
2. **Title left + Legend right**: `{title: {left: "left"}, legend: {right: 10, top: "middle"}}`
3. **Title top-left + Legend bottom**: `{title: {left: "left", top: 10}, legend: {bottom: 10}}`

## 5. Return Requirements

- Return ONLY valid JSON (no explanatory text before or after)
- Do NOT wrap JSON in markdown code blocks (no ```json)
- Do NOT include JavaScript functions
- Ensure all property names are double-quoted
- Use arrays for data, not objects with numeric keys

## 6. ECharts Examples

### Line Chart (Time Series with Consolidated Dates)
{
  "title": { "text": "Monthly Sales Trend" },
  "tooltip": { 
    "trigger": "axis",
    "formatter": "{b}<br/>{a}: {c}"
  },
  "xAxis": { 
    "type": "category", 
    "data": ["2023/01", "2023/02", "2023/03", "2023/04", "2023/05", "2023/06"],
    "axisLabel": { "rotate": 45 }
  },
  "yAxis": { 
    "type": "value",
    "axisLabel": { "formatter": "{value} units" }
  },
  "series": [{
    "name": "Sales",
    "type": "line",
    "data": [150, 230, 224, 218, 135, 147],
    "smooth": true,
    "label": { "show": true, "formatter": "{c}" }
  }]
}

### Bar Chart (Category Comparison)
{
  "title": { "text": "Sales by Region" },
  "tooltip": { 
    "trigger": "axis",
    "axisPointer": { "type": "shadow" }
  },
  "xAxis": { 
    "type": "category", 
    "data": ["North", "South", "East", "West", "Central"] 
  },
  "yAxis": { 
    "type": "value",
    "axisLabel": { "formatter": "${value}" }
  },
  "series": [{
    "name": "Revenue",
    "type": "bar",
    "data": [320, 302, 341, 374, 390],
    "label": { 
      "show": true, 
      "position": "top",
      "formatter": "{c}"
    },
    "itemStyle": {
      "color": "#5470c6"
    }
  }]
}

### Pie Chart (Proportions)
{
  "title": { 
    "text": "Market Share",
    "left": "center"
  },
  "tooltip": { 
    "trigger": "item",
    "formatter": "{a}<br/>{b}: {c} ({d}%)"
  },
  "legend": { 
    "orient": "vertical", 
    "left": "left" 
  },
  "series": [{
    "name": "Market Share",
    "type": "pie",
    "radius": "50%",
    "data": [
      { "value": 1048, "name": "Product A" },
      { "value": 735, "name": "Product B" },
      { "value": 580, "name": "Product C" },
      { "value": 484, "name": "Product D" },
      { "value": 300, "name": "Other" }
    ],
    "label": { "formatter": "{b}\n{d}%" },
    "emphasis": {
      "itemStyle": {
        "shadowBlur": 10,
        "shadowOffsetX": 0,
        "shadowColor": "rgba(0, 0, 0, 0.5)"
      }
    }
  }]
}

### Scatter Chart (Correlation)
{
  "title": { "text": "Height vs Weight" },
  "tooltip": {
    "trigger": "item",
    "formatter": "Height: {c0} cm<br/>Weight: {c1} kg"
  },
  "xAxis": { 
    "type": "value",
    "name": "Height (cm)",
    "axisLabel": { "formatter": "{value} cm" }
  },
  "yAxis": { 
    "type": "value",
    "name": "Weight (kg)",
    "axisLabel": { "formatter": "{value} kg" }
  },
  "series": [{
    "name": "Measurements",
    "type": "scatter",
    "data": [[161, 51], [167, 59], [159, 49], [157, 63], [178, 73]],
    "symbolSize": 10
  }]
}

### Stacked Area Chart (Multi-Year Monthly Data)
{
  "title": { "text": "Traffic Sources Over Time" },
  "tooltip": { 
    "trigger": "axis",
    "axisPointer": { "type": "cross" }
  },
  "legend": { "data": ["Direct", "Search", "Referral"] },
  "xAxis": { 
    "type": "category", 
    "boundaryGap": false,
    "data": ["2022/10", "2022/11", "2022/12", "2023/01", "2023/02", "2023/03", "2023/04"],
    "axisLabel": { "rotate": 45 }
  },
  "yAxis": { "type": "value" },
  "series": [
    {
      "name": "Direct",
      "type": "line",
      "stack": "Total",
      "areaStyle": {},
      "data": [320, 332, 301, 334, 390, 330, 320]
    },
    {
      "name": "Search",
      "type": "line",
      "stack": "Total",
      "areaStyle": {},
      "data": [120, 132, 101, 134, 90, 230, 210]
    },
    {
      "name": "Referral",
      "type": "line",
      "stack": "Total",
      "areaStyle": {},
      "data": [220, 182, 191, 234, 290, 330, 310]
    }
  ]
}

## 7. Edge Case Handling

- **>10 categories for pie**: Aggregate smallest values into "Other"
- **Empty dataset**: Return error message in JSON: {"error": "No data provided"}
- **Single data point**: Use bar chart or display as single metric card
- **All null values in a column**: Exclude that series or use 0 as placeholder
- **Negative values in pie chart**: Use bar chart instead
- **Multiple date columns**: Consolidate into single YYYY/MM format (see Section 1)
- **Unsorted date data**: Always sort chronologically before generating chart
- **Mixed date formats**: Normalize all dates to consistent YYYY/MM or YYYY/MM/DD format
- **Title/Legend overlap**: ALWAYS follow Section 4 layout guidelines"""
        
        # User prompt: Provide the data
        chart_type_instruction = ""
        if chart_type_param != "auto":
            chart_type_instruction = f"""

## CHART TYPE OVERRIDE

The user has selected: **{chart_type_param.upper()} CHART**

You MUST generate a {chart_type_param} chart. Do not suggest a different type.
Adapt the data to fit this chart type as best as possible.

If the data is not ideally suited for this chart type, still generate the chart
but you may add a "warning" field in the JSON response explaining any limitations.
Example: {{"warning": "Pie charts work best with ≤10 categories. Showing top 10 only.", ...}}
"""
        else:
            chart_type_instruction = ""
        
        user_prompt = f"""Create a chart visualization for this data.{chart_type_instruction}

Column Names:
{json.dumps(request.column_names)}

Column Information (with detected types):
{chr(10).join([f"- {col.name} ({col.type})" for col in request.columns])}

Data (first {len(request.sample_data)} rows):
{json.dumps(request.sample_data, indent=2)}

Instructions:
1. {'Create a ' + chart_type_param + ' chart (user-selected)' if chart_type_param != 'auto' else 'Analyze the data and choose the BEST chart type'}
2. Create a complete ECharts configuration
3. Make the title descriptive and meaningful
4. Format numbers properly (add commas, decimals as needed)
5. Add clear axis labels
6. Create professional tooltips
7. Use an appropriate color scheme
8. **CRITICAL**: Ensure title and legend do NOT overlap (follow Section 4 layout guidelines)

Return ONLY the ECharts configuration JSON. No explanatory text."""
        
        # Call LLM using the agent's LLM service
        response = await agent.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,  # Lower temperature for more consistent chart generation
            max_tokens=4096
        )
        
        # Parse LLM response
        chart_config_text = response["content"]
        logger.info(f"LLM raw response (first 500 chars): {chart_config_text[:500]}")
        
        # Extract JSON from response (in case LLM adds markdown formatting)
        if "```json" in chart_config_text:
            chart_config_text = chart_config_text.split("```json")[1].split("```")[0].strip()
        elif "```" in chart_config_text:
            chart_config_text = chart_config_text.split("```")[1].split("```")[0].strip()
        
        # Strip any leading/trailing whitespace or explanatory text
        chart_config_text = chart_config_text.strip()
        if not chart_config_text.startswith("{"):
            # Try to find the first { and last }
            start_idx = chart_config_text.find("{")
            end_idx = chart_config_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                chart_config_text = chart_config_text[start_idx:end_idx+1]
        
        chart_config = json.loads(chart_config_text)
        
        # Validate it's a dict and has required fields
        if not isinstance(chart_config, dict):
            logger.error("LLM response is not a valid object")
            raise ValueError("LLM response is not a valid object")
        
        if "series" not in chart_config:
            logger.error("Chart config missing 'series' field")
            raise ValueError("Chart config missing 'series' field")
        
        # Determine chart type from the config
        chart_type = "bar"  # default
        if chart_config.get("series") and len(chart_config["series"]) > 0:
            chart_type = chart_config["series"][0].get("type", "bar")
        
        logger.info(f"Chart generated successfully: type={chart_type}")
        
        return GenerateChartResponse(
            chart_config=chart_config,
            chart_type=chart_type
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail="LLM returned invalid JSON"
        )
    except Exception as e:
        logger.error(f"Chart generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chart generation failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
