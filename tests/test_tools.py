"""Unit tests for Vanna tools."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from src.tools.chart_generation_tool import ChartGenerationTool
from src.tools.insights_generation_tool import InsightsGenerationTool
from vanna.core.tool import ToolContext


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_agent_memory():
    """Mock agent memory for testing."""
    mock = AsyncMock()
    mock.get_context_for_question = AsyncMock(return_value={
        "documentation": ["Business rule 1", "Business rule 2"]
    })
    return mock


@pytest.fixture
def mock_tool_context():
    """Mock tool execution context."""
    return ToolContext(
        user_id="test_user",
        conversation_id="test_conversation",
        metadata={}
    )


@pytest.fixture
def sample_data_bar_chart():
    """Sample data suitable for bar chart."""
    return {
        "columns": [
            {"name": "category", "type": "string"},
            {"name": "sales_amount", "type": "numeric"}
        ],
        "column_names": ["category", "sales_amount"],
        "data": [
            {"category": "Electronics", "sales_amount": 150000},
            {"category": "Clothing", "sales_amount": 120000},
            {"category": "Food", "sales_amount": 95000}
        ]
    }


@pytest.fixture
def sample_data_line_chart():
    """Sample data suitable for line chart (time series)."""
    return {
        "columns": [
            {"name": "month", "type": "string"},
            {"name": "revenue", "type": "numeric"}
        ],
        "column_names": ["month", "revenue"],
        "data": [
            {"month": "2023/01", "revenue": 45000},
            {"month": "2023/02", "revenue": 52000},
            {"month": "2023/03", "revenue": 48000},
            {"month": "2023/04", "revenue": 55000}
        ]
    }


class TestChartGenerationTool:
    """Test ChartGenerationTool."""
    
    @pytest.mark.asyncio
    async def test_tool_schema(self, mock_llm_service):
        """Test that tool schema is properly defined."""
        tool = ChartGenerationTool(mock_llm_service)
        schema = tool.get_schema()
        
        assert schema["name"] == "generate_chart"
        assert "description" in schema
        assert "parameters" in schema
        assert "columns" in schema["parameters"]["properties"]
        assert "data" in schema["parameters"]["properties"]
    
    @pytest.mark.asyncio
    async def test_chart_generation_bar_chart(
        self,
        mock_llm_service,
        mock_tool_context,
        sample_data_bar_chart
    ):
        """Test generating a bar chart."""
        # Mock LLM response with valid bar chart config
        mock_chart_config = {
            "title": {"text": "Sales by Category"},
            "xAxis": {"type": "category", "data": ["Electronics", "Clothing", "Food"]},
            "yAxis": {"type": "value"},
            "series": [{
                "name": "Sales",
                "type": "bar",
                "data": [150, 120, 95]
            }]
        }
        
        mock_llm_service.generate = AsyncMock(return_value={
            "content": json.dumps(mock_chart_config)
        })
        
        tool = ChartGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            columns=sample_data_bar_chart["columns"],
            column_names=sample_data_bar_chart["column_names"],
            data=sample_data_bar_chart["data"],
            chart_type="auto"
        )
        
        assert result.success is True
        assert "chart_config" in result.data
        assert "chart_type" in result.data
        assert result.data["chart_type"] == "bar"
        assert result.data["chart_config"]["title"]["text"] == "Sales by Category"
    
    @pytest.mark.asyncio
    async def test_chart_generation_line_chart(
        self,
        mock_llm_service,
        mock_tool_context,
        sample_data_line_chart
    ):
        """Test generating a line chart."""
        mock_chart_config = {
            "title": {"text": "Monthly Revenue Trend"},
            "xAxis": {"type": "category", "data": ["2023/01", "2023/02", "2023/03", "2023/04"]},
            "yAxis": {"type": "value"},
            "series": [{
                "name": "Revenue",
                "type": "line",
                "data": [45, 52, 48, 55],
                "smooth": True
            }]
        }
        
        mock_llm_service.generate = AsyncMock(return_value={
            "content": json.dumps(mock_chart_config)
        })
        
        tool = ChartGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            columns=sample_data_line_chart["columns"],
            column_names=sample_data_line_chart["column_names"],
            data=sample_data_line_chart["data"],
            chart_type="line"
        )
        
        assert result.success is True
        assert result.data["chart_type"] == "line"
        assert "smooth" in result.data["chart_config"]["series"][0]
    
    @pytest.mark.asyncio
    async def test_chart_generation_with_markdown_wrapper(
        self,
        mock_llm_service,
        mock_tool_context,
        sample_data_bar_chart
    ):
        """Test parsing chart config wrapped in markdown code block."""
        mock_chart_config = {
            "title": {"text": "Test Chart"},
            "series": [{"type": "bar", "data": [1, 2, 3]}]
        }
        
        # LLM returns config wrapped in markdown
        markdown_response = f"```json\n{json.dumps(mock_chart_config)}\n```"
        mock_llm_service.generate = AsyncMock(return_value={
            "content": markdown_response
        })
        
        tool = ChartGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            columns=sample_data_bar_chart["columns"],
            column_names=sample_data_bar_chart["column_names"],
            data=sample_data_bar_chart["data"]
        )
        
        assert result.success is True
        assert result.data["chart_config"]["title"]["text"] == "Test Chart"
    
    @pytest.mark.asyncio
    async def test_chart_generation_error_handling(
        self,
        mock_llm_service,
        mock_tool_context,
        sample_data_bar_chart
    ):
        """Test error handling when LLM returns invalid JSON."""
        mock_llm_service.generate = AsyncMock(return_value={
            "content": "This is not valid JSON"
        })
        
        tool = ChartGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            columns=sample_data_bar_chart["columns"],
            column_names=sample_data_bar_chart["column_names"],
            data=sample_data_bar_chart["data"]
        )
        
        assert result.success is False
        assert result.error is not None


class TestInsightsGenerationTool:
    """Test InsightsGenerationTool."""
    
    @pytest.mark.asyncio
    async def test_tool_schema(self, mock_llm_service):
        """Test that tool schema is properly defined."""
        tool = InsightsGenerationTool(mock_llm_service)
        schema = tool.get_schema()
        
        assert schema["name"] == "generate_insights"
        assert "description" in schema
        assert "parameters" in schema
        assert "dataset" in schema["parameters"]["properties"]
        assert "question" in schema["parameters"]["properties"]
    
    @pytest.mark.asyncio
    async def test_insights_generation_success(
        self,
        mock_llm_service,
        mock_agent_memory,
        mock_tool_context
    ):
        """Test successful insights generation."""
        dataset = {
            "rows": [
                {"product": "A", "sales": 100},
                {"product": "B", "sales": 200},
                {"product": "C", "sales": 150}
            ],
            "columns": ["product", "sales"]
        }
        
        mock_insights = {
            "summary": "Product B leads with 200 sales (40% of total)",
            "findings": [
                "Product B accounts for 40% of total sales",
                "Product C is 25% below Product B"
            ],
            "suggestions": [
                "Focus marketing efforts on Product B",
                "Investigate why Product A underperforms"
            ]
        }
        
        mock_llm_service.generate = AsyncMock(return_value={
            "content": json.dumps(mock_insights)
        })
        
        tool = InsightsGenerationTool(mock_llm_service, mock_agent_memory)
        result = await tool.execute(
            context=mock_tool_context,
            dataset=dataset,
            question="What are the sales by product?"
        )
        
        assert result.success is True
        assert "summary" in result.data
        assert "findings" in result.data
        assert "suggestions" in result.data
        assert len(result.data["findings"]) == 2
    
    @pytest.mark.asyncio
    async def test_insights_empty_dataset(
        self,
        mock_llm_service,
        mock_tool_context
    ):
        """Test handling of empty dataset."""
        dataset = {"rows": [], "columns": []}
        
        tool = InsightsGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            dataset=dataset,
            question="Test question"
        )
        
        assert result.success is True
        assert result.data["summary"] == "No data returned from query"
        assert len(result.data["findings"]) == 0
    
    @pytest.mark.asyncio
    async def test_insights_single_row(
        self,
        mock_llm_service,
        mock_tool_context
    ):
        """Test handling of single row dataset."""
        dataset = {
            "rows": [{"value": 100}],
            "columns": ["value"]
        }
        
        tool = InsightsGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            dataset=dataset,
            question="Test question"
        )
        
        assert result.success is True
        assert result.data["summary"] == "Single record returned, no patterns to analyze"
    
    @pytest.mark.asyncio
    async def test_insights_with_markdown_wrapper(
        self,
        mock_llm_service,
        mock_tool_context
    ):
        """Test parsing insights wrapped in markdown code block."""
        dataset = {
            "rows": [
                {"product": "A", "sales": 100},
                {"product": "B", "sales": 200}
            ],
            "columns": ["product", "sales"]
        }
        
        mock_insights = {
            "summary": "Test summary",
            "findings": ["Finding 1"],
            "suggestions": ["Suggestion 1"]
        }
        
        markdown_response = f"```json\n{json.dumps(mock_insights)}\n```"
        mock_llm_service.generate = AsyncMock(return_value={
            "content": markdown_response
        })
        
        tool = InsightsGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            dataset=dataset,
            question="Test question"
        )
        
        assert result.success is True
        assert result.data["summary"] == "Test summary"
    
    @pytest.mark.asyncio
    async def test_insights_error_handling(
        self,
        mock_llm_service,
        mock_tool_context
    ):
        """Test error handling returns graceful fallback."""
        dataset = {
            "rows": [{"value": 100}, {"value": 200}],
            "columns": ["value"]
        }
        
        # Simulate LLM error
        mock_llm_service.generate = AsyncMock(side_effect=Exception("LLM error"))
        
        tool = InsightsGenerationTool(mock_llm_service)
        result = await tool.execute(
            context=mock_tool_context,
            dataset=dataset,
            question="Test question"
        )
        
        # Should still succeed but with empty insights
        assert result.success is True
        assert result.data["summary"] == "Unable to generate insights"
        assert len(result.data["findings"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
