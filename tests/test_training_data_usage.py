"""
Test script to validate that all training data is being used by Vanna.

This script sends test queries that should utilize each piece of training data:
- DDL statements (5 tables)
- Documentation (5 business rules)
- SQL examples (8 question-SQL pairs)

Run with: python tests/test_training_data_usage.py
"""

import requests
import json
import time
from typing import Dict, Any, List
from datetime import datetime


# Configuration
API_BASE_URL = "http://localhost:8000"
TESTS_OUTPUT_FILE = "tests/test_results.json"


# Test queries designed to use specific training data
TEST_QUERIES = [
    # Tests for DDL Usage (Tables)
    {
        "category": "DDL",
        "training_id": "ddl_001",
        "table": "DimCustomer",
        "question": "Show me customer names and email addresses",
        "expected_tables": ["DimCustomer"],
        "expected_columns": ["FirstName", "LastName", "EmailAddress"]
    },
    {
        "category": "DDL",
        "training_id": "ddl_002",
        "table": "FactInternetSales",
        "question": "List all sales with order numbers and amounts",
        "expected_tables": ["FactInternetSales"],
        "expected_columns": ["SalesOrderNumber", "SalesAmount"]
    },
    {
        "category": "DDL",
        "training_id": "ddl_003",
        "table": "DimProduct",
        "question": "Show product names with their prices and costs",
        "expected_tables": ["DimProduct"],
        "expected_columns": ["EnglishProductName", "ListPrice", "StandardCost"]
    },
    {
        "category": "DDL",
        "training_id": "ddl_004",
        "table": "DimDate",
        "question": "Show calendar years with their quarters",
        "expected_tables": ["DimDate"],
        "expected_columns": ["CalendarYear", "CalendarQuarter"]
    },
    {
        "category": "DDL",
        "training_id": "ddl_005",
        "table": "DimGeography",
        "question": "List cities with their state and country information",
        "expected_tables": ["DimGeography"],
        "expected_columns": ["City", "StateProvinceName", "EnglishCountryRegionName"]
    },
    
    # Tests for Documentation Usage (Business Rules)
    {
        "category": "Documentation",
        "training_id": "doc_001",
        "topic": "Customer Segmentation",
        "question": "Show me all high-value customers with income over 100000",
        "expected_tables": ["DimCustomer"],
        "expected_conditions": ["YearlyIncome > 100000"]
    },
    {
        "category": "Documentation",
        "training_id": "doc_002",
        "topic": "Sales Metrics",
        "question": "Calculate the net revenue excluding tax and freight",
        "expected_tables": ["FactInternetSales"],
        "expected_columns": ["SalesAmount", "TaxAmt", "Freight"],
        "expected_operations": ["SalesAmount - TaxAmt - Freight"]
    },
    {
        "category": "Documentation",
        "training_id": "doc_003",
        "topic": "Date Dimension",
        "question": "Show sales by calendar quarter and year",
        "expected_tables": ["DimDate", "FactInternetSales"],
        "expected_columns": ["CalendarYear", "CalendarQuarter"],
        "expected_joins": ["DateKey"]
    },
    {
        "category": "Documentation",
        "training_id": "doc_004",
        "topic": "Product Information",
        "question": "Show Road bikes with their retail prices",
        "expected_tables": ["DimProduct"],
        "expected_columns": ["EnglishProductName", "ListPrice", "ProductLine"],
        "expected_conditions": ["ProductLine = 'R'"]
    },
    {
        "category": "Documentation",
        "training_id": "doc_005",
        "topic": "Geography Data",
        "question": "Show customer counts by country using geography information",
        "expected_tables": ["DimCustomer", "DimGeography"],
        "expected_columns": ["EnglishCountryRegionName"],
        "expected_joins": ["GeographyKey"]
    },
    
    # Tests for SQL Examples Usage (Direct Questions)
    {
        "category": "SQL_Example",
        "training_id": "sql_001",
        "question": "What is the total revenue?",
        "expected_tables": ["FactInternetSales"],
        "expected_aggregations": ["SUM(SalesAmount)"]
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_002",
        "question": "Show me top 10 customers by total purchases",
        "expected_tables": ["FactInternetSales", "DimCustomer"],
        "expected_aggregations": ["SUM"],
        "expected_limit": 10
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_003",
        "question": "How many high-value customers do we have?",
        "expected_tables": ["DimCustomer"],
        "expected_aggregations": ["COUNT"],
        "expected_conditions": ["YearlyIncome > 100000"]
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_004",
        "question": "What are the total sales by year?",
        "expected_tables": ["FactInternetSales", "DimDate"],
        "expected_columns": ["CalendarYear"],
        "expected_aggregations": ["SUM"]
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_005",
        "question": "Show me the top 5 products by revenue",
        "expected_tables": ["FactInternetSales", "DimProduct"],
        "expected_columns": ["EnglishProductName"],
        "expected_limit": 5
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_006",
        "question": "What is the average order value?",
        "expected_tables": ["FactInternetSales"],
        "expected_aggregations": ["AVG(SalesAmount)"]
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_007",
        "question": "How many orders were placed in 2023?",
        "expected_tables": ["FactInternetSales", "DimDate"],
        "expected_conditions": ["CalendarYear = 2023"],
        "expected_aggregations": ["COUNT"]
    },
    {
        "category": "SQL_Example",
        "training_id": "sql_008",
        "question": "Show sales by country",
        "expected_tables": ["FactInternetSales", "DimCustomer", "DimGeography"],
        "expected_columns": ["EnglishCountryRegionName"],
        "expected_aggregations": ["SUM"]
    }
]


class VannaTestRunner:
    """Test runner for Vanna training data validation."""
    
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.results = []
        
    def check_health(self) -> bool:
        """Check if API is healthy."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def execute_query(self, question: str) -> Dict[str, Any]:
        """Execute a query against the API."""
        try:
            response = requests.post(
                f"{self.api_url}/api/query",
                json={"question": question},
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"API returned status {response.status_code}",
                    "question": question
                }
        except Exception as e:
            return {
                "error": str(e),
                "question": question
            }
    
    def validate_response(self, test: Dict, response: Dict) -> Dict[str, Any]:
        """Validate response against expected criteria."""
        validation = {
            "passed": True,
            "checks": [],
            "sql": response.get("sql") or ""
        }
        
        sql = (response.get("sql") or "").upper()
        
        if response.get("error"):
            validation["passed"] = False
            validation["checks"].append({
                "check": "No errors",
                "passed": False,
                "message": response["error"]
            })
            return validation
        
        if not sql:
            validation["passed"] = False
            validation["checks"].append({
                "check": "SQL generated",
                "passed": False,
                "message": "No SQL was generated"
            })
            return validation
        
        # Check expected tables
        if "expected_tables" in test:
            for table in test["expected_tables"]:
                found = table.upper() in sql
                validation["checks"].append({
                    "check": f"Table {table}",
                    "passed": found
                })
                if not found:
                    validation["passed"] = False
        
        # Check expected columns
        if "expected_columns" in test:
            for column in test["expected_columns"]:
                found = column.upper() in sql
                validation["checks"].append({
                    "check": f"Column {column}",
                    "passed": found
                })
                if not found:
                    validation["passed"] = False
        
        # Check expected conditions
        if "expected_conditions" in test:
            for condition in test["expected_conditions"]:
                found = condition.replace(" ", "").upper() in sql.replace(" ", "")
                validation["checks"].append({
                    "check": f"Condition '{condition}'",
                    "passed": found
                })
                if not found:
                    validation["passed"] = False
        
        # Check expected aggregations
        if "expected_aggregations" in test:
            for agg in test["expected_aggregations"]:
                found = agg.upper() in sql
                validation["checks"].append({
                    "check": f"Aggregation {agg}",
                    "passed": found
                })
                if not found:
                    validation["passed"] = False
        
        # Check expected joins
        if "expected_joins" in test:
            for join_col in test["expected_joins"]:
                found = join_col.upper() in sql
                validation["checks"].append({
                    "check": f"Join on {join_col}",
                    "passed": found
                })
                if not found:
                    validation["passed"] = False
        
        # Check limit
        if "expected_limit" in test:
            limit = test["expected_limit"]
            found = f"LIMIT {limit}" in sql or f"TOP {limit}" in sql
            validation["checks"].append({
                "check": f"Limit {limit}",
                "passed": found
            })
            if not found:
                validation["passed"] = False
        
        return validation
    
    def run_tests(self) -> List[Dict]:
        """Run all test queries."""
        print(f"\n{'='*80}")
        print("🧪 Vanna Training Data Validation Tests")
        print(f"{'='*80}\n")
        
        # Health check
        print("🏥 Checking API health...")
        if not self.check_health():
            print("❌ API is not healthy. Please start the services.")
            return []
        print("✅ API is healthy\n")
        
        # Run tests
        total_tests = len(TEST_QUERIES)
        passed_tests = 0
        
        for idx, test in enumerate(TEST_QUERIES, 1):
            print(f"\n{'─'*80}")
            print(f"Test {idx}/{total_tests}: {test['category']} - {test['training_id']}")
            print(f"Question: {test['question']}")
            print(f"{'─'*80}")
            
            # Execute query
            response = self.execute_query(test["question"])
            
            # Wait a bit between queries
            time.sleep(1)
            
            # Validate response
            validation = self.validate_response(test, response)
            
            # Store result
            result = {
                "test_number": idx,
                "category": test["category"],
                "training_id": test["training_id"],
                "question": test["question"],
                "passed": validation["passed"],
                "sql_generated": validation["sql"],
                "checks": validation["checks"],
                "timestamp": datetime.now().isoformat()
            }
            
            if "table" in test:
                result["table"] = test["table"]
            if "topic" in test:
                result["topic"] = test["topic"]
            
            self.results.append(result)
            
            # Print results
            if validation["passed"]:
                print("✅ PASSED")
                passed_tests += 1
            else:
                print("❌ FAILED")
            
            print(f"\nGenerated SQL:\n{validation['sql']}\n")
            
            print("Validation Checks:")
            for check in validation["checks"]:
                status = "✅" if check["passed"] else "❌"
                message = f" - {check.get('message', '')}" if 'message' in check else ""
                print(f"  {status} {check['check']}{message}")
        
        # Summary
        print(f"\n{'='*80}")
        print(f"📊 Test Summary")
        print(f"{'='*80}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {total_tests - passed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Category breakdown
        print(f"\n📋 Category Breakdown:")
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"passed": 0, "total": 0}
            categories[cat]["total"] += 1
            if result["passed"]:
                categories[cat]["passed"] += 1
        
        for cat, stats in categories.items():
            rate = (stats["passed"] / stats["total"]) * 100
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
        
        print(f"\n{'='*80}\n")
        
        return self.results
    
    def save_results(self, filepath: str):
        """Save test results to JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    "test_run_timestamp": datetime.now().isoformat(),
                    "total_tests": len(self.results),
                    "passed_tests": sum(1 for r in self.results if r["passed"]),
                    "results": self.results
                }, f, indent=2)
            print(f"💾 Results saved to: {filepath}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")


def main():
    """Main entry point."""
    runner = VannaTestRunner(API_BASE_URL)
    results = runner.run_tests()
    
    if results:
        runner.save_results(TESTS_OUTPUT_FILE)


if __name__ == "__main__":
    main()
