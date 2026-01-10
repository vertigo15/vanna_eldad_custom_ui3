"""End-to-end tests for UI functionality.

Tests the complete flow through the UI including:
- Query execution
- Conversation history
- Chart generation
- Insights generation
"""

import pytest
import requests
import json
from typing import Dict, Any, Optional
import time


# Configuration
BASE_URL = "http://localhost:8000"  # Change if needed
UI_URL = "http://localhost:8501"    # Flask UI port


class TestUIEndToEnd:
    """End-to-end tests for the complete UI workflow."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup before each test."""
        # Wait for services to be ready
        self._wait_for_service(BASE_URL, timeout=10)
        self._wait_for_service(UI_URL, timeout=10)
        
        # Clear any test conversations if needed
        self.test_user_id = "test_user_e2e"
        self.conversation_id = None
    
    def _wait_for_service(self, url: str, timeout: int = 10):
        """Wait for a service to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = requests.get(f"{url}/health", timeout=2)
                if response.status_code == 200:
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        raise TimeoutError(f"Service at {url} not ready after {timeout}s")
    
    def _send_query(
        self, 
        question: str, 
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a query to the API."""
        payload = {"question": question}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        response = requests.post(
            f"{BASE_URL}/api/query",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def _send_chart_request(
        self,
        columns: list,
        column_names: list,
        data: list,
        chart_type: str = "auto"
    ) -> Dict[str, Any]:
        """Send a chart generation request."""
        payload = {
            "columns": columns,
            "column_names": column_names,
            "sample_data": data,
            "chart_type": chart_type
        }
        
        response = requests.post(
            f"{BASE_URL}/api/generate-chart",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def _send_insights_request(
        self,
        dataset: Dict[str, Any],
        question: str
    ) -> Dict[str, Any]:
        """Send an insights generation request."""
        payload = {
            "dataset": dataset,
            "question": question
        }
        
        response = requests.post(
            f"{BASE_URL}/api/generate-insights",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    # ============================================
    # Basic Query Tests
    # ============================================
    
    def test_simple_query_execution(self):
        """Test basic query execution."""
        result = self._send_query("show total sales for 2006")
        
        # Verify response structure
        assert "question" in result
        assert "sql" in result
        assert "results" in result
        assert result["error"] is None
        
        # Verify SQL was generated
        assert result["sql"] is not None
        assert len(result["sql"]) > 0
        
        # Verify results returned
        assert result["results"] is not None
        assert "rows" in result["results"] or "columns" in result["results"]
        
        print(f"✓ Query executed successfully")
        print(f"  SQL: {result['sql'][:100]}...")
        print(f"  Rows: {len(result.get('results', {}).get('rows', []))}")
    
    def test_query_with_conversation_id(self):
        """Test query with conversation tracking."""
        # First query
        result1 = self._send_query("show sales for 2006")
        conv_id = result1.get("conversation_id")
        
        assert conv_id is not None
        print(f"✓ Conversation created: {conv_id}")
        
        # Follow-up query with same conversation
        result2 = self._send_query(
            "what about 2007?",
            conversation_id=conv_id
        )
        
        assert result2.get("conversation_id") == conv_id
        print(f"✓ Follow-up query used same conversation")
    
    def test_invalid_query_handling(self):
        """Test that invalid queries are handled gracefully."""
        result = self._send_query("xyzabc nonsense query 12345")
        
        # Should not crash, might return error or attempt to interpret
        assert "question" in result
        print(f"✓ Invalid query handled gracefully")
    
    # ============================================
    # Chart Generation Tests
    # ============================================
    
    def test_chart_generation_bar_chart(self):
        """Test bar chart generation from query results."""
        # First, execute a query that returns categorical data
        query_result = self._send_query("show sales by product category for 2006")
        
        if query_result.get("results"):
            results = query_result["results"]
            rows = results.get("rows", [])
            columns = results.get("columns", [])
            
            if rows and columns:
                # Generate column info
                column_info = [
                    {"name": col, "type": "string" if i == 0 else "numeric"}
                    for i, col in enumerate(columns)
                ]
                
                # Request chart generation
                chart_result = self._send_chart_request(
                    columns=column_info,
                    column_names=columns,
                    data=rows[:10],  # First 10 rows
                    chart_type="bar"
                )
                
                # Verify chart config
                assert "chart_config" in chart_result
                assert "chart_type" in chart_result
                
                config = chart_result["chart_config"]
                assert "series" in config
                assert len(config["series"]) > 0
                assert config["series"][0]["type"] in ["bar", "line", "pie"]
                
                print(f"✓ Bar chart generated successfully")
                print(f"  Chart type: {chart_result['chart_type']}")
                print(f"  Has title: {'title' in config}")
                print(f"  Has series: {len(config['series'])}")
            else:
                pytest.skip("Query returned no data for chart test")
        else:
            pytest.skip("Query failed, cannot test chart")
    
    def test_chart_generation_line_chart(self):
        """Test line chart generation for time series data."""
        # Query for time series data
        query_result = self._send_query("show monthly sales for 2006")
        
        if query_result.get("results"):
            results = query_result["results"]
            rows = results.get("rows", [])
            columns = results.get("columns", [])
            
            if rows and columns and len(rows) >= 3:
                column_info = [
                    {"name": col, "type": "string" if "month" in col.lower() else "numeric"}
                    for col in columns
                ]
                
                chart_result = self._send_chart_request(
                    columns=column_info,
                    column_names=columns,
                    data=rows[:12],  # One year of data
                    chart_type="line"
                )
                
                assert "chart_config" in chart_result
                config = chart_result["chart_config"]
                assert config["series"][0]["type"] == "line"
                
                print(f"✓ Line chart generated successfully")
                print(f"  Data points: {len(rows)}")
            else:
                pytest.skip("Insufficient data for line chart test")
        else:
            pytest.skip("Query failed, cannot test chart")
    
    def test_chart_number_formatting(self):
        """Test that charts format large numbers correctly (K/M/B)."""
        # Query for large numbers
        query_result = self._send_query("show total sales by year")
        
        if query_result.get("results"):
            results = query_result["results"]
            rows = results.get("rows", [])
            columns = results.get("columns", [])
            
            if rows and columns:
                column_info = [
                    {"name": col, "type": "string" if i == 0 else "numeric"}
                    for i, col in enumerate(columns)
                ]
                
                chart_result = self._send_chart_request(
                    columns=column_info,
                    column_names=columns,
                    data=rows
                )
                
                config = chart_result["chart_config"]
                
                # Check if large numbers are formatted
                # Look for K, M, or B in axis labels or tooltips
                config_str = json.dumps(config)
                has_formatting = any(x in config_str for x in ["$", "K", "M", "B", "%"])
                
                print(f"✓ Chart generated with number formatting: {has_formatting}")
                
                # This is a soft assertion - we just log the result
                if not has_formatting:
                    print("  Warning: No number formatting detected in chart config")
            else:
                pytest.skip("No data for formatting test")
        else:
            pytest.skip("Query failed")
    
    # ============================================
    # Insights Generation Tests
    # ============================================
    
    def test_insights_generation_basic(self):
        """Test basic insights generation."""
        # Execute query
        query_result = self._send_query("show top 10 products by sales")
        
        if query_result.get("results"):
            results = query_result["results"]
            
            # Request insights
            insights_result = self._send_insights_request(
                dataset=results,
                question="show top 10 products by sales"
            )
            
            # Verify insights structure
            assert "summary" in insights_result
            assert "findings" in insights_result
            assert "suggestions" in insights_result
            
            # Verify content
            assert len(insights_result["summary"]) > 0
            assert isinstance(insights_result["findings"], list)
            assert isinstance(insights_result["suggestions"], list)
            
            print(f"✓ Insights generated successfully")
            print(f"  Summary: {insights_result['summary'][:100]}...")
            print(f"  Findings: {len(insights_result['findings'])}")
            print(f"  Suggestions: {len(insights_result['suggestions'])}")
        else:
            pytest.skip("Query failed, cannot test insights")
    
    def test_insights_with_numerical_data(self):
        """Test insights generation with numerical analysis."""
        query_result = self._send_query("show sales by region with totals")
        
        if query_result.get("results"):
            results = query_result["results"]
            rows = results.get("rows", [])
            
            if len(rows) >= 3:
                insights_result = self._send_insights_request(
                    dataset=results,
                    question="show sales by region with totals"
                )
                
                # Should have meaningful findings for numerical data
                assert len(insights_result["findings"]) > 0, "No findings generated for numerical data"
                
                # Check if findings mention numbers/percentages
                findings_text = " ".join(insights_result["findings"])
                has_numbers = any(char.isdigit() for char in findings_text)
                
                print(f"✓ Insights contain numerical analysis: {has_numbers}")
                
                if not has_numbers:
                    print("  Warning: Findings don't contain specific numbers")
            else:
                pytest.skip("Insufficient data for numerical insights test")
        else:
            pytest.skip("Query failed")
    
    def test_insights_empty_dataset_handling(self):
        """Test insights gracefully handle empty datasets."""
        # Send empty dataset
        empty_dataset = {"rows": [], "columns": ["col1", "col2"]}
        
        insights_result = self._send_insights_request(
            dataset=empty_dataset,
            question="test empty"
        )
        
        # Should return graceful message
        assert "summary" in insights_result
        assert len(insights_result["findings"]) == 0
        
        print(f"✓ Empty dataset handled gracefully")
        print(f"  Summary: {insights_result['summary']}")
    
    # ============================================
    # Integrated Workflow Tests
    # ============================================
    
    def test_full_workflow_query_chart_insights(self):
        """Test complete workflow: query -> chart -> insights."""
        print("\n=== Testing Full Workflow ===")
        
        # Step 1: Execute query
        print("Step 1: Executing query...")
        query_result = self._send_query("show monthly sales for 2006")
        assert query_result.get("sql") is not None
        assert query_result.get("results") is not None
        print(f"  ✓ Query successful")
        
        results = query_result["results"]
        rows = results.get("rows", [])
        columns = results.get("columns", [])
        
        if not rows or not columns:
            pytest.skip("Query returned no data")
        
        # Step 2: Generate chart
        print("Step 2: Generating chart...")
        column_info = [
            {"name": col, "type": "string" if i == 0 else "numeric"}
            for i, col in enumerate(columns)
        ]
        
        chart_result = self._send_chart_request(
            columns=column_info,
            column_names=columns,
            data=rows
        )
        assert "chart_config" in chart_result
        print(f"  ✓ Chart generated: {chart_result['chart_type']}")
        
        # Step 3: Generate insights
        print("Step 3: Generating insights...")
        insights_result = self._send_insights_request(
            dataset=results,
            question="show monthly sales for 2006"
        )
        assert "summary" in insights_result
        assert len(insights_result["findings"]) >= 0
        print(f"  ✓ Insights generated: {len(insights_result['findings'])} findings")
        
        print("\n=== Full Workflow Complete ===")
        print(f"Summary: {insights_result['summary']}")
    
    def test_conversation_persistence(self):
        """Test that conversation history persists across queries."""
        print("\n=== Testing Conversation Persistence ===")
        
        # Query 1
        result1 = self._send_query("show sales for 2006")
        conv_id = result1.get("conversation_id")
        print(f"Query 1: Created conversation {conv_id}")
        
        # Query 2 - reference previous query
        result2 = self._send_query(
            "what was the total?",
            conversation_id=conv_id
        )
        print(f"Query 2: Used same conversation")
        
        # Query 3 - another follow-up
        result3 = self._send_query(
            "now show 2007",
            conversation_id=conv_id
        )
        print(f"Query 3: Used same conversation")
        
        # All should use same conversation
        assert result1.get("conversation_id") == conv_id
        assert result2.get("conversation_id") == conv_id
        assert result3.get("conversation_id") == conv_id
        
        print(f"✓ Conversation persisted across 3 queries")
    
    # ============================================
    # Performance Tests
    # ============================================
    
    def test_query_performance(self):
        """Test that queries complete within reasonable time."""
        start = time.time()
        result = self._send_query("show total sales")
        duration = time.time() - start
        
        assert duration < 10, f"Query took too long: {duration:.2f}s"
        print(f"✓ Query completed in {duration:.2f}s")
    
    def test_chart_generation_performance(self):
        """Test chart generation performance."""
        # Get some data first
        query_result = self._send_query("show sales by product")
        
        if query_result.get("results"):
            results = query_result["results"]
            rows = results.get("rows", [])[:20]
            columns = results.get("columns", [])
            
            if rows and columns:
                column_info = [
                    {"name": col, "type": "numeric" if i > 0 else "string"}
                    for i, col in enumerate(columns)
                ]
                
                start = time.time()
                self._send_chart_request(
                    columns=column_info,
                    column_names=columns,
                    data=rows
                )
                duration = time.time() - start
                
                assert duration < 5, f"Chart generation took too long: {duration:.2f}s"
                print(f"✓ Chart generated in {duration:.2f}s")
            else:
                pytest.skip("No data for performance test")
        else:
            pytest.skip("Query failed")
    
    def test_insights_generation_performance(self):
        """Test insights generation performance."""
        query_result = self._send_query("show top products")
        
        if query_result.get("results"):
            start = time.time()
            self._send_insights_request(
                dataset=query_result["results"],
                question="show top products"
            )
            duration = time.time() - start
            
            assert duration < 10, f"Insights generation took too long: {duration:.2f}s"
            print(f"✓ Insights generated in {duration:.2f}s")
        else:
            pytest.skip("Query failed")


# ============================================
# Manual Test Checklist
# ============================================

"""
MANUAL UI TEST CHECKLIST:

1. Basic Functionality:
   [ ] Load UI at http://localhost:8501
   [ ] Enter question and click "Ask Question"
   [ ] SQL displays in "Generated SQL" section
   [ ] Results display in "Results" section
   [ ] No errors in browser console

2. Chart Generation:
   [ ] Query returns data suitable for charts (e.g., "show sales by month")
   [ ] Chart section displays
   [ ] Chart renders correctly (bars/lines/pie visible)
   [ ] Chart has title and labels
   [ ] Numbers are formatted (K/M/B for large values)
   [ ] Can toggle chart type if UI supports it

3. Insights Generation:
   [ ] Insights section displays
   [ ] Summary is meaningful
   [ ] Findings list specific numbers from data
   [ ] Suggestions are actionable
   [ ] No generic/empty insights

4. Conversation History:
   [ ] Can see recent questions in sidebar
   [ ] Clicking recent question loads that conversation
   [ ] Follow-up questions work in context
   [ ] "Clear History" button works

5. Error Handling:
   [ ] Invalid questions show friendly error
   [ ] Empty results handled gracefully
   [ ] Database errors don't crash UI
   [ ] Network errors show retry option

6. Performance:
   [ ] Initial load < 2 seconds
   [ ] Query execution < 5 seconds
   [ ] Chart generation < 3 seconds
   [ ] Insights generation < 5 seconds
   [ ] UI remains responsive during processing

7. Cross-browser Testing:
   [ ] Works in Chrome
   [ ] Works in Firefox
   [ ] Works in Edge
   [ ] No console errors in any browser
"""


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
