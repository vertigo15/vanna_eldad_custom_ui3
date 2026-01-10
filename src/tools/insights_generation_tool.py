"""Insights Generation Tool for Vanna Agent.

Analyzes query results and generates insights using LLM.
"""

from typing import Any, Dict, List
import json
import logging

import pandas as pd
from vanna.core.tool import Tool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class InsightsGenerationTool(Tool):
    """Tool for generating insights from query results."""
    
    # Define as class attributes (required by abstract base class)
    name = "generate_insights"
    description = "Generate insights and findings from query results"
    
    def __init__(self, llm_service, agent_memory=None):
        """Initialize insights generation tool.
        
        Args:
            llm_service: LLM service instance compatible with Vanna's interface
            agent_memory: Optional agent memory for retrieving business context
        """
        self.llm_service = llm_service
        self.agent_memory = agent_memory
    
    def get_args_schema(self) -> Dict[str, Any]:
        """Return tool arguments schema for Vanna Agent."""
        return {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "object",
                    "description": "Query results with rows and columns",
                    "properties": {
                        "rows": {
                            "type": "array",
                            "description": "Data rows"
                        },
                        "columns": {
                            "type": "array",
                            "description": "Column names"
                        }
                    }
                },
                "question": {
                    "type": "string",
                    "description": "Original user question that generated this data"
                }
            },
            "required": ["dataset", "question"]
        }
    
    async def execute(
        self,
        context: ToolContext,
        dataset: Dict[str, Any],
        question: str
    ) -> ToolResult:
        """Execute insights generation.
        
        Args:
            context: Tool execution context from Vanna
            dataset: Query results with rows and columns
            question: Original user question
            
        Returns:
            ToolResult with insights (summary, findings, suggestions)
        """
        logger.info(f"Generating insights for: {question[:50]}...")
        
        try:
            # Convert to DataFrame
            df = self._dataset_to_dataframe(dataset)
            
            # Check if dataset is valid for insights
            if df.empty:
                return ToolResult(
                    success=True,
                    data={
                        "summary": "No data returned from query",
                        "findings": [],
                        "suggestions": []
                    }
                )
            
            if len(df) == 1:
                return ToolResult(
                    success=True,
                    data={
                        "summary": "Single record returned, no patterns to analyze",
                        "findings": [],
                        "suggestions": []
                    }
                )
            
            # Get business context from agent memory
            business_context = {}
            if self.agent_memory:
                try:
                    business_context = await self.agent_memory.get_context_for_question(question)
                except Exception as e:
                    logger.warning(f"Failed to get business context: {e}")
            
            # Prepare dataset summary
            dataset_summary = self._prepare_dataset_summary(df)
            
            # Build prompt
            prompt = self._build_insight_prompt(
                dataset_summary=dataset_summary,
                context=business_context,
                original_question=question
            )
            
            # Generate insights using LLM
            response = await self.llm_service.generate(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior data analyst specialized in finding actionable insights."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1024
            )
            
            # Parse response
            content = response.get("content", "")
            insights = self._parse_insights_response(content)
            
            logger.info(f"Insights generated: {len(insights.get('findings', []))} findings")
            
            return ToolResult(
                success=True,
                data=insights
            )
            
        except Exception as e:
            logger.error(f"Insights generation failed: {e}", exc_info=True)
            return ToolResult(
                success=True,  # Don't fail, just return empty insights
                data={
                    "summary": "Unable to generate insights",
                    "findings": [],
                    "suggestions": []
                }
            )
    
    def _dataset_to_dataframe(self, dataset: Any) -> pd.DataFrame:
        """Convert dataset to pandas DataFrame."""
        if isinstance(dataset, dict):
            if 'rows' in dataset and 'columns' in dataset:
                return pd.DataFrame(dataset['rows'], columns=dataset['columns'])
            else:
                return pd.DataFrame(dataset)
        elif isinstance(dataset, pd.DataFrame):
            return dataset
        else:
            return pd.DataFrame()
    
    def _prepare_dataset_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Prepare dataset summary for LLM prompt."""
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
        self,
        dataset_summary: Dict[str, Any],
        context: Dict[str, Any],
        original_question: str
    ) -> str:
        """Build the insight generation prompt."""
        
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
        
        # Build prompt
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
        
        return template.format(
            original_question=original_question,
            business_rules=business_rules,
            row_count=dataset_summary["row_count"],
            column_names=", ".join(dataset_summary["column_names"]),
            data_sample=dataset_summary["data_sample"],
            column_stats=dataset_summary["column_stats"]
        )
    
    def _parse_insights_response(self, content: str) -> Dict[str, Any]:
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
                return self._empty_insights("Invalid response format")
            
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
            return self._empty_insights("Unable to parse insights")
    
    def _empty_insights(self, message: str) -> Dict[str, Any]:
        """Return empty insights structure with a message."""
        return {
            "summary": message,
            "findings": [],
            "suggestions": []
        }
