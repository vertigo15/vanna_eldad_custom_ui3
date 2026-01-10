"""FastAPI application for Vanna 2.0 Text-to-SQL."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
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
    session_id: Optional[UUID] = None  # For conversation continuity
    user_context: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for SQL query."""
    question: str
    query_id: Optional[UUID] = None  # ID for feedback/history tracking
    session_id: Optional[UUID] = None  # Session for conversation continuity
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
            session_id=request.session_id,
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
    query_id: Optional[UUID] = None  # For linking insights to query history


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
        import time
        
        # Get context from agent memory (for business rules)
        context = await agent.memory.get_context_for_question(request.question)
        
        # Generate insights (async call) with timing
        start_time = time.time()
        insights = await generate_insights(
            dataset=request.dataset,
            context=context,
            original_question=request.question,
            llm_service=agent.llm
        )
        exec_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Insights generated: {len(insights.get('findings', []))} findings")
        
        # Log insights to history if query_id provided
        if agent.history and request.query_id:
            try:
                # Log summary
                await agent.history.add_insight(
                    query_id=request.query_id,
                    insight_type="summary",
                    content=insights.get("summary", "Analysis complete"),
                    llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    llm_execution_time_ms=exec_time_ms,
                    tokens_input=insights.get("usage", {}).get("prompt_tokens", 0),
                    tokens_output=insights.get("usage", {}).get("completion_tokens", 0)
                )
                
                # Log each finding
                for finding in insights.get("findings", []):
                    await agent.history.add_insight(
                        query_id=request.query_id,
                        insight_type="finding",
                        content=finding,
                        llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME
                    )
                
                # Log each suggestion
                for suggestion in insights.get("suggestions", []):
                    await agent.history.add_insight(
                        query_id=request.query_id,
                        insight_type="suggestion",
                        content=suggestion,
                        llm_model=settings.AZURE_OPENAI_DEPLOYMENT_NAME
                    )
            except Exception as e:
                logger.error(f"Failed to log insights to history: {e}")
        
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

## 3. Number Formatting

**CRITICAL: Apply smart number formatting to make charts readable**

### Large Numbers — Use K/M/B Abbreviations:
- < 1,000: Show as-is (e.g., 850)
- 1,000 - 999,999: X.XK (e.g., 1.2K, 45.8K, 850K)
- 1,000,000 - 999,999,999: X.XM (e.g., 1.2M, 45.8M)
- ≥ 1,000,000,000: X.XB (e.g., 1.2B, 3.5B)

### Decimal Precision:
- Currency/Money: 0-2 decimals (e.g., $1.2M, $45.80)
- Percentages: 1 decimal (e.g., 45.5%)
- Counts/Units: 0 decimals (e.g., 1.2K not 1.23K)
- Ratios/Rates: 2 decimals (e.g., 3.45)

### Auto-Detection Rules:
**Currency:** If column name contains: price, amount, revenue, sales, cost, profit, total → Add $ prefix
**Percentage:** If column name contains: percent, pct, rate, ratio, share → Add % suffix

### Implementation:
1. Transform the data values BEFORE passing to ECharts
2. For Y-axis with values ≥ 1000, divide by appropriate scale and add suffix
3. Update axis labels to show scale (e.g., "Sales Amount (Millions)")
4. Format tooltip to show original values with K/M/B notation

### Example with large numbers:
Instead of:
```
"yAxis": { "type": "value" },
"series": [{ "data": [1200000, 1500000, 850000] }]
```

Use:
```
"yAxis": { 
  "type": "value",
  "name": "Sales (USD)",
  "axisLabel": { "formatter": "{value}M" }
},
"series": [{ "data": [1.2, 1.5, 0.85] }]
```

And add to tooltip:
```
"tooltip": {
  "formatter": "{b}<br/>{a}: ${c}M"
}
```

## 4. String Formatters

Use ECharts template strings:

### Tooltip Formatters:
- `{a}` - Series name
- `{b}` - Category name (x-axis value)
- `{c}` - Data value
- `{d}` - Percentage (pie/funnel charts)

### Label Formatters:
- `"{b}: {c}"` → "January: 150"
- `"{c}K"` → "1.2K" (for thousands)
- `"${c}M"` → "$1.2M" (for millions)

## 5. Layout and Spacing Requirements

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

## 6. Return Requirements

- Return ONLY valid JSON (no explanatory text before or after)
- Do NOT wrap JSON in markdown code blocks (no ```json)
- Do NOT include JavaScript functions
- Ensure all property names are double-quoted
- Use arrays for data, not objects with numeric keys

## 7. ECharts Examples

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


class EnhanceChartRequest(BaseModel):
    """Request model for chart enhancement."""
    columns: List[ColumnInfo]
    sample_data: List[List[Any]]
    chart_type: str  # line/bar/pie
    current_config: Dict[str, Any]  # Current basic chart config


@app.post("/api/enhance-chart")
async def enhance_chart_endpoint(request: EnhanceChartRequest):
    """
    Enhance chart configuration using LLM with smart number formatting.
    
    Args:
        request: EnhanceChartRequest with columns, data, chart type, and current config
        
    Returns:
        Enhanced ECharts configuration with professional formatting
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Enhancing {request.chart_type} chart")
    
    try:
        # System prompt with number formatting rules
        system_prompt = """You are a data visualization expert specializing in Apache ECharts configurations.

Your task is to enhance basic ECharts configurations to make them more professional, readable, and insightful.

Guidelines:
- Improve titles to be descriptive and meaningful based on the actual data
- Choose appropriate color palettes that match the data context
- Format numbers appropriately (currencies, percentages, thousands separators)
- Add meaningful axis labels and units
- Optimize tooltip formatting for better readability
- Adjust chart sizing and spacing for optimal viewing
- Add subtle styling improvements (shadows, gradients, etc.) where appropriate
- Keep the chart type unchanged unless there's a strong reason
- Ensure all returned JSON is valid ECharts option format

## NUMBER FORMATTING

Apply these formatting rules to axis labels, tooltips, and data labels:

### Large Numbers — Use K/M/B Abbreviations:
- < 1,000: Show as-is (e.g., 850)
- 1,000 - 999,999: X.XK (e.g., 1.2K, 45.8K, 850K)
- 1,000,000 - 999,999,999: X.XM (e.g., 1.2M, 45.8M)
- ≥ 1,000,000,000: X.XB (e.g., 1.2B, 3.5B)

### Decimal Precision:
- Currency/Money: 0-2 decimals (e.g., $1.2M, $45.80)
- Percentages: 1 decimal (e.g., 45.5%)
- Counts/Units: 0 decimals (e.g., 1.2K not 1.23K)
- Ratios/Rates: 2 decimals (e.g., 3.45)

### Currency Detection:
If column name contains: price, amount, revenue, sales, cost, profit, total
→ Add $ prefix: $1.2M, $850K

### Percentage Detection:
If column name contains: percent, pct, rate, ratio, share
OR if all values are between 0-100 or 0-1
→ Add % suffix: 45.5%, 12.3%

### Apply Formatting To:
1. Y-axis labels (axisLabel.formatter)
2. Tooltip values  
3. Data labels on bars/points (if shown)

### ECharts Formatter Implementation:
Use ECharts template strings for simple cases, or JavaScript formatter functions for complex number formatting.

For axis labels with large numbers, use JavaScript formatter:
```javascript
function(value) {
  if (value >= 1e9) return '$' + (value/1e9).toFixed(1) + 'B';
  if (value >= 1e6) return '$' + (value/1e6).toFixed(1) + 'M';
  if (value >= 1e3) return '$' + (value/1e3).toFixed(1) + 'K';
  return '$' + value.toFixed(0);
}
```

For tooltips with formatted numbers, use formatter functions that apply K/M/B abbreviations.

IMPORTANT: When using JavaScript functions in JSON, represent them as strings that will be evaluated by ECharts.

Important constraints:
- Do NOT change the fundamental data or series structure
- Return ONLY valid JSON that can be directly used as ECharts option
- Do NOT include any explanatory text outside the JSON
- Maintain backward compatibility with ECharts 5.x
- Formatter functions must be valid JavaScript code as strings"""
        
        # User prompt
        user_prompt = f"""Enhance this {request.chart_type} chart configuration.

Column Information:
{chr(10).join([f"- {col.name} ({col.type})" for col in request.columns])}

Sample Data (first few rows):
{json.dumps(request.sample_data[:5], indent=2)}

Current Basic Configuration:
{json.dumps(request.current_config, indent=2)}

Please return an enhanced ECharts configuration as pure JSON with:
1. A meaningful, descriptive title based on what the data represents
2. Smart number formatting with K/M/B abbreviations for large numbers
3. Automatic currency detection (add $ prefix for price/amount/revenue/sales/cost/profit columns)
4. Automatic percentage detection (add % suffix for percent/rate/ratio columns or values 0-100)
5. Better color scheme that fits the data context
6. Improved axis labels with units if applicable
7. Enhanced tooltip formatting with properly formatted numbers
8. Professional styling touches
9. Ensure title and legend do not overlap

Return ONLY the JSON configuration, no other text."""
        
        # Call LLM
        response = await agent.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=4096
        )
        
        # Parse response
        config_text = response["content"]
        logger.info(f"Enhancement LLM response (first 300 chars): {config_text[:300]}")
        
        # Extract JSON
        if "```json" in config_text:
            config_text = config_text.split("```json")[1].split("```")[0].strip()
        elif "```" in config_text:
            config_text = config_text.split("```")[1].split("```")[0].strip()
        
        config_text = config_text.strip()
        if not config_text.startswith("{"):
            start_idx = config_text.find("{")
            end_idx = config_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                config_text = config_text[start_idx:end_idx+1]
        
        enhanced_config = json.loads(config_text)
        
        # Validate
        if not isinstance(enhanced_config, dict):
            raise ValueError("Enhanced config is not a valid object")
        
        logger.info("Chart enhancement successful")
        
        return {"enhanced_config": enhanced_config}
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse enhancement response: {e}")
        raise HTTPException(
            status_code=500,
            detail="LLM returned invalid JSON"
        )
    except Exception as e:
        logger.error(f"Chart enhancement error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chart enhancement failed: {str(e)}"
        )


# Feedback and conversation history endpoints
class FeedbackRequest(BaseModel):
    """Request model for user feedback."""
    query_id: UUID
    feedback: str  # 'thumbs_up', 'thumbs_down', 'edited'
    corrected_sql: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/feedback")
async def record_feedback(request: FeedbackRequest):
    """
    Record user feedback for a query.
    
    Args:
        request: FeedbackRequest with query_id and feedback
        
    Returns:
        Success message
    """
    if not agent or not agent.history:
        raise HTTPException(status_code=503, detail="History service not available")
    
    logger.info(f"Recording {request.feedback} feedback for query {request.query_id}")
    
    try:
        await agent.history.record_feedback(
            query_id=request.query_id,
            user_feedback=request.feedback,
            corrected_sql=request.corrected_sql,
            feedback_notes=request.notes
        )
        
        return {"status": "success", "message": "Feedback recorded"}
        
    except Exception as e:
        logger.error(f"Error recording feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversation/{session_id}")
async def get_conversation_history(session_id: UUID, include_insights: bool = True):
    """
    Retrieve conversation history for a session.
    
    Args:
        session_id: Session UUID
        include_insights: Whether to include insights for each query
        
    Returns:
        Conversation history with all queries and insights
    """
    if not agent or not agent.history:
        raise HTTPException(status_code=503, detail="History service not available")
    
    logger.info(f"Retrieving conversation history for session {session_id}")
    
    try:
        history = await agent.history.get_conversation_history(
            session_id=session_id,
            include_insights=include_insights
        )
        
        return history
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
