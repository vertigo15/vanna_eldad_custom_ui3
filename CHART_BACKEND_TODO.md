# Backend API Requirement for Chart Generation

## Overview
The chart feature uses a **simplified LLM-only approach**. When the user clicks the Chart button, the frontend calls the backend with the data, and the **LLM decides everything**: chart type, styling, colors, formatting, etc.

## What's Already Done ✅
- ✅ Complete frontend implementation
- ✅ UI Flask app forwards requests to main API at `/api/generate-chart`
- ✅ All validation and error handling in place
- ✅ Caching to avoid duplicate LLM calls
- ✅ Default to table view

## What Needs to Be Implemented ⚠️

### Main Vanna API Backend (main.py or equivalent)

You need to add this endpoint to your main FastAPI backend:

**POST /api/generate-chart**

### Implementation Steps

1. **Add the endpoint** (FastAPI example):

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import json

router = APIRouter()

class ColumnInfo(BaseModel):
    name: str
    type: str  # "numeric", "category", or "date"

class GenerateChartRequest(BaseModel):
    columns: List[ColumnInfo]
    column_names: List[str]
    sample_data: List[List[Any]]
    all_data: List[List[Any]]  # Optional: all data if dataset is small

class GenerateChartResponse(BaseModel):
    chart_config: Dict[str, Any]  # Complete ECharts configuration
    chart_type: str  # Type chosen by LLM: "line", "bar", "pie", etc.

@router.post("/api/generate-chart")
async def generate_chart(request: GenerateChartRequest):
    """
    Generate chart configuration using LLM.
    
    The LLM should:
    1. Analyze the data structure and content
    2. Decide the best chart type (line, bar, pie, etc.)
    3. Create a complete ECharts configuration JSON
    4. Include proper titles, colors, formatting, labels, tooltips
    5. Return ready-to-use ECharts option object
    """
    try:
        # Build prompt using the templates from:
        # src/static/chart-feature/prompts/chartEnhancerPrompt.js
        
        system_prompt = """You are a data visualization expert specializing in Apache ECharts.

Your task is to analyze data and create the perfect chart visualization.

You must:
1. Analyze the data structure and determine the BEST chart type:
   - Line chart: for time series, trends over time
   - Bar chart: for comparing categories, rankings
   - Pie chart: for showing proportions (only if ≤10 categories)
   - Other types if more appropriate

2. Create a complete, professional ECharts configuration with:
   - Descriptive title based on the data meaning
   - Appropriate color scheme
   - Proper number formatting (add commas, decimals, currency symbols)
   - Clear axis labels with units
   - Professional tooltip formatting
   - Proper legend if needed
   - Responsive grid/spacing

3. Return requirements:
   - Return ONLY valid JSON (no explanatory text)
   - Must be a complete ECharts option object
   - Must work with ECharts 5.x
   - Include all data in the series

ECharts Examples:

Line Chart:
{
  "xAxis": {
    "type": "category",
    "data": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
  },
  "yAxis": {
    "type": "value"
  },
  "series": [{
    "data": [150, 230, 224, 218, 135, 147, 260],
    "type": "line",
    "smooth": true
  }]
}

Bar Chart:
{
  "tooltip": {
    "trigger": "axis",
    "axisPointer": {
      "type": "shadow"
    }
  },
  "grid": {
    "left": "3%",
    "right": "4%",
    "bottom": "3%",
    "containLabel": true
  },
  "xAxis": [{
    "type": "category",
    "data": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "axisTick": {
      "alignWithLabel": true
    }
  }],
  "yAxis": [{
    "type": "value"
  }],
  "series": [{
    "name": "Direct",
    "type": "bar",
    "barWidth": "60%",
    "data": [10, 52, 200, 334, 390, 330, 220]
  }]
}

Pie Chart:
{
  "tooltip": {
    "trigger": "item"
  },
  "legend": {
    "top": "5%",
    "left": "center"
  },
  "series": [{
    "name": "Access From",
    "type": "pie",
    "radius": ["40%", "70%"],
    "data": [
      {"value": 1048, "name": "Category A"},
      {"value": 735, "name": "Category B"},
      {"value": 580, "name": "Category C"},
      {"value": 484, "name": "Category D"},
      {"value": 300, "name": "Category E"}
    ]
  }]
}
"""

        user_prompt = f"""Create a chart visualization for this data.

Column Names:
{json.dumps(request.column_names)}

Column Information (with detected types):
{chr(10).join([f"- {col.name} ({col.type})" for col in request.columns])}

Data (first {len(request.sample_data)} rows):
{json.dumps(request.sample_data, indent=2)}

Instructions:
1. Analyze the data and choose the BEST chart type
2. Create a complete ECharts configuration
3. Make the title descriptive and meaningful
4. Format numbers properly (add commas, decimals as needed)
5. Add clear axis labels
6. Create professional tooltips
7. Use an appropriate color scheme

Return ONLY the ECharts configuration JSON. No explanatory text."""

        # Call your LLM (Azure OpenAI in your case)
        # Example with Azure OpenAI:
        
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),  # e.g., "gpt-4"
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,  # Lower temperature for more consistent chart generation
            response_format={"type": "json_object"}  # Ensures JSON response
        )
        
        # Parse LLM response
        chart_config_text = response.choices[0].message.content
        chart_config = json.loads(chart_config_text)
        
        # Validate it's a dict and has required fields
        if not isinstance(chart_config, dict):
            raise ValueError("LLM response is not a valid object")
        
        if "series" not in chart_config:
            raise ValueError("Chart config missing 'series' field")
        
        # Determine chart type from the config
        chart_type = chart_config.get("series", [{}])[0].get("type", "bar")
        
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
        logger.error(f"Chart enhancement error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chart enhancement failed: {str(e)}"
        )
```

2. **Register the router** in your main FastAPI app:

```python
from your_router_file import router as chart_router

app.include_router(chart_router)
```

### Testing the Endpoint

#### Using curl:
```bash
curl -X POST http://localhost:8000/api/enhance-chart \
  -H "Content-Type: application/json" \
  -d '{
    "columns": [
      {"name": "month", "type": "category"},
      {"name": "sales", "type": "numeric"}
    ],
    "sample_data": [
      ["January", 1000],
      ["February", 1500],
      ["March", 1200]
    ],
    "chart_type": "bar",
    "current_config": {
      "title": {"text": "sales by month"},
      "xAxis": {"type": "category", "data": ["January", "February", "March"]},
      "yAxis": {"type": "value"},
      "series": [{"type": "bar", "data": [1000, 1500, 1200]}]
    }
  }'
```

#### Expected Response:
```json
{
  "enhanced_config": {
    "title": {
      "text": "Monthly Sales Performance",
      "subtext": "First Quarter 2024",
      "left": "center"
    },
    "xAxis": {
      "type": "category",
      "data": ["January", "February", "March"],
      "axisLabel": {
        "fontSize": 12
      }
    },
    "yAxis": {
      "type": "value",
      "name": "Sales ($)",
      "axisLabel": {
        "formatter": "${value}"
      }
    },
    "tooltip": {
      "trigger": "axis",
      "formatter": "{b}: ${c}"
    },
    "series": [{
      "type": "bar",
      "data": [1000, 1500, 1200],
      "itemStyle": {
        "color": "#5470c6"
      },
      "label": {
        "show": true,
        "position": "top",
        "formatter": "${c}"
      }
    }]
  }
}
```

## Fallback Behavior

**If the endpoint is not implemented**, the feature will still work:
- Tier 1 (auto-generation) will always work
- When user clicks "✨ Enhance with AI", they'll see an error message
- The app will fall back to Tier 1 config
- Everything else continues to function normally

## Priority

This is **optional** for basic functionality, but **recommended** for full feature experience:
- **Low priority**: Basic charts work without it
- **Medium priority**: Enhances user experience significantly
- **High priority**: If you want to showcase AI-powered features

## Notes for Azure OpenAI

Since you're using Azure OpenAI:
1. Make sure to use `response_format={"type": "json_object"}` for structured output
2. Consider adding retry logic for API failures
3. Add rate limiting if needed
4. Cache responses if the same query is enhanced multiple times
5. Set appropriate timeout (recommendation: 30 seconds)

## Questions?

Check the implementation in:
- `src/static/chart-feature/prompts/chartEnhancerPrompt.js` for prompt templates
- `src/ui_app.py` lines 102-152 for the UI proxy endpoint
- `src/static/chart-feature/services/chartEnhancerService.js` for the request format
