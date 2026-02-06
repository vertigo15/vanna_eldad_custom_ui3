"""Insight generation service for analyzing query results."""

from typing import Dict, Any, List
import json
import pandas as pd
from pathlib import Path


async def generate_insights(
    dataset: Any,
    context: Dict[str, Any],
    original_question: str,
    llm_service: Any = None
) -> Dict[str, Any]:
    """
    Analyzes a dataset and returns insights.
    
    Args:
        dataset: DataFrame or dict - the query results
        context: dict - contains 'documentation' (business rules)
        original_question: str - the user's original question
        llm_service: LLM service instance for calling the model
    
    Returns:
        dict: {
            "summary": str (one-line summary),
            "findings": [list of insight strings],
            "suggestions": [list of suggestion strings],
            "prompt": str (the prompt used),
            "system_message": str (the system message used)
        }
    """
    system_message = "You are a senior data analyst specialized in finding actionable insights."
    
    try:
        # Convert dataset to DataFrame if needed
        if isinstance(dataset, dict):
            if 'rows' in dataset and 'columns' in dataset:
                df = pd.DataFrame(dataset['rows'], columns=dataset['columns'])
            else:
                df = pd.DataFrame(dataset)
        elif isinstance(dataset, pd.DataFrame):
            df = dataset
        else:
            prompt = "N/A - Unsupported dataset format"
            return _empty_insights("Unsupported dataset format", prompt, system_message)
        
        # Check if dataset is empty or too small
        if df.empty:
            prompt = "N/A - No data returned from query"
            return _empty_insights("No data returned from query", prompt, system_message)
        
        if len(df) == 1:
            prompt = "N/A - Single record, no patterns to analyze"
            return _empty_insights("Single record returned, no patterns to analyze", prompt, system_message)
        
        # Prepare dataset summary for LLM
        dataset_summary = _prepare_dataset_summary(df)
        
        # Build prompt
        prompt = _build_insight_prompt(
            dataset_summary=dataset_summary,
            context=context,
            original_question=original_question
        )
        
        # Call LLM if service is provided
        if llm_service is None:
            return _empty_insights("LLM service not available", prompt, system_message)
        
        # Generate insights using LLM (await the async call)
        response = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        
        # Parse LLM response
        content = response.get("content", "")
        insights = _parse_insights_response(content)
        
        # Include the prompt used
        insights["prompt"] = prompt
        insights["system_message"] = system_message
        
        return insights
        
    except Exception as e:
        return {
            "summary": "Unable to generate insights",
            "findings": [f"Error: {str(e)}"],
            "suggestions": [],
            "prompt": prompt if 'prompt' in locals() else "N/A - Error occurred before prompt generation",
            "system_message": system_message
        }


def _prepare_dataset_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Prepare a summary of the dataset for the LLM.
    Does NOT send full dataset - only statistics and samples.
    """
    summary = {
        "row_count": len(df),
        "column_names": list(df.columns),
        "data_sample": "",
        "column_stats": ""
    }
    
    # Get first 10 rows as sample
    sample_df = df.head(10)
    summary["data_sample"] = sample_df.to_string(index=False)
    
    # Get column statistics
    stats_parts = []
    
    for col in df.columns:
        col_type = df[col].dtype
        
        if pd.api.types.is_numeric_dtype(col_type):
            # Numeric column statistics
            stats_parts.append(f"{col} (numeric):")
            stats_parts.append(f"  - Min: {df[col].min()}")
            stats_parts.append(f"  - Max: {df[col].max()}")
            stats_parts.append(f"  - Mean: {df[col].mean():.2f}")
            stats_parts.append(f"  - Median: {df[col].median()}")
        else:
            # Categorical column statistics
            unique_count = df[col].nunique()
            stats_parts.append(f"{col} (categorical):")
            stats_parts.append(f"  - Unique values: {unique_count}")
            
            # Top 3 values
            top_values = df[col].value_counts().head(3)
            if not top_values.empty:
                stats_parts.append(f"  - Top values: {', '.join([str(v) for v in top_values.index])}")
    
    summary["column_stats"] = "\n".join(stats_parts)
    
    return summary


def _build_insight_prompt(
    dataset_summary: Dict[str, Any],
    context: Dict[str, Any],
    original_question: str
) -> str:
    """Build the insight generation prompt."""
    
    # Load prompt template
    template_path = Path(__file__).parent.parent.parent / "templates" / "insight_prompt.txt"
    
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    else:
        # Fallback inline template
        template = """You are a senior data analyst. Analyze the query results and provide insights.

## RULES
- ONLY report findings you are highly confident about
- Every insight must be backed by specific numbers from the data
- Be concise — max 3-5 key findings
- Match the user's language (English/Hebrew)

## CONFIDENCE THRESHOLDS — REPORT ONLY IF:
- Differences: ≥ 20% from average/baseline
- Patterns: Clear majority (≥70%) or minority (≤20%)
- Trends: Consistent direction across data points

DO NOT report vague findings like "seems to" or "might be".

## USER'S QUESTION:
{original_question}

## BUSINESS RULES:
{business_rules}

## DATASET SUMMARY:
- Total rows: {row_count}
- Columns: {column_names}
- Data sample:
{data_sample}

## COLUMN STATISTICS:
{column_stats}

## OUTPUT FORMAT (respond in JSON):
{{
  "summary": "One sentence summarizing the key takeaway",
  "findings": [
    "Finding 1 with specific numbers",
    "Finding 2 with specific numbers"
  ],
  "suggestions": [
    "Actionable suggestion based on findings"
  ]
}}

If the dataset is too small or no meaningful insights exist, return:
{{
  "summary": "Insufficient data for meaningful insights",
  "findings": [],
  "suggestions": []
}}"""
    
    # Get business rules from context
    business_rules = ""
    if context and 'documentation' in context:
        rules = context['documentation']
        if isinstance(rules, list):
            business_rules = "\n".join([f"- {rule}" for rule in rules[:5]])  # Limit to 5
        else:
            business_rules = str(rules)
    
    if not business_rules:
        business_rules = "No specific business rules provided"
    
    # Fill template
    prompt = template.format(
        original_question=original_question,
        business_rules=business_rules,
        row_count=dataset_summary["row_count"],
        column_names=", ".join(dataset_summary["column_names"]),
        data_sample=dataset_summary["data_sample"],
        column_stats=dataset_summary["column_stats"]
    )
    
    return prompt


def _parse_insights_response(content: str) -> Dict[str, Any]:
    """Parse LLM response into structured insights."""
    try:
        # Try to extract JSON from response
        content = content.strip()
        
        # Remove markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Find JSON object
        if not content.startswith("{"):
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx != -1 and end_idx != -1:
                content = content[start_idx:end_idx+1]
        
        # Parse JSON
        insights = json.loads(content)
        
        # Validate structure
        if not isinstance(insights, dict):
            return _empty_insights("Invalid response format")
        
        # Ensure required fields
        insights.setdefault("summary", "Analysis complete")
        insights.setdefault("findings", [])
        insights.setdefault("suggestions", [])
        
        return insights
        
    except json.JSONDecodeError:
        # Fallback: try to extract insights from plain text
        return {
            "summary": "Analysis generated",
            "findings": [content[:500]] if content else [],
            "suggestions": []
        }
    except Exception:
        return _empty_insights("Unable to parse insights")


def _empty_insights(message: str, prompt: str = "", system_message: str = "") -> Dict[str, Any]:
    """Return empty insights structure with a message."""
    return {
        "summary": message,
        "findings": [],
        "suggestions": [],
        "prompt": prompt,
        "system_message": system_message
    }


# Async version for use with asyncio
async def generate_insights_async(
    dataset: Any,
    context: Dict[str, Any],
    original_question: str,
    llm_service: Any = None
) -> Dict[str, Any]:
    """
    Async version of generate_insights.
    Calls the synchronous version in a thread pool.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            generate_insights,
            dataset,
            context,
            original_question,
            llm_service
        )
    
    return result
