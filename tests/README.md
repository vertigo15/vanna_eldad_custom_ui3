# Vanna Training Data Validation Tests

This test suite validates that all training data is being properly utilized by Vanna 2.0.

## What Gets Tested

The test suite covers **18 test cases** across **3 categories**:

### 1. DDL Tests (5 tests)
Validates that Vanna can use schema information from all 5 tables:
- `DimCustomer` - Customer table schema
- `FactInternetSales` - Sales fact table schema
- `DimProduct` - Product dimension schema
- `DimDate` - Date dimension schema
- `DimGeography` - Geography dimension schema

### 2. Documentation Tests (5 tests)
Validates that Vanna understands business rules and documentation:
- Customer Segmentation rules (high-value customers)
- Sales Metrics calculations (net revenue)
- Date Dimension usage (quarters, years)
- Product Information (product lines, pricing)
- Geography Data (country/state joins)

### 3. SQL Example Tests (8 tests)
Validates that Vanna learned from example question-SQL pairs:
- Total revenue calculation
- Top customers by purchases
- High-value customer count
- Sales by year
- Top products by revenue
- Average order value
- Orders count by year
- Sales by country

## Running the Tests

### Prerequisites
Make sure all services are running:
```bash
docker-compose up -d
```

And training data is loaded:
```bash
docker exec -it vanna-app python scripts/load_training_data.py
```

### Run Tests

**Option 1: Using Python directly**
```bash
python tests/test_training_data_usage.py
```

**Option 2: Using PowerShell script**
```powershell
.\run_tests.ps1
```

### Expected Output

The test will:
1. ✅ Check API health
2. 🧪 Execute all 18 test queries
3. ✔️ Validate each response against expected criteria
4. 📊 Show detailed summary with pass/fail rates
5. 💾 Save results to `tests/test_results.json`

## Test Results Format

Each test validates:
- **SQL Generation**: Was SQL generated without errors?
- **Tables Used**: Are the correct tables referenced?
- **Columns Used**: Are the expected columns present?
- **Conditions**: Are WHERE clauses correct?
- **Aggregations**: Are SUM, COUNT, AVG used properly?
- **Joins**: Are table joins correct?
- **Limits**: Are LIMIT/TOP clauses correct?

## Example Output

```
================================================================================
🧪 Vanna Training Data Validation Tests
================================================================================

🏥 Checking API health...
✅ API is healthy

────────────────────────────────────────────────────────────────────────────────
Test 1/18: DDL - ddl_001
Question: Show me customer names and email addresses
────────────────────────────────────────────────────────────────────────────────
✅ PASSED

Generated SQL:
SELECT FirstName, LastName, EmailAddress FROM DimCustomer;

Validation Checks:
  ✅ Table DimCustomer
  ✅ Column FirstName
  ✅ Column LastName
  ✅ Column EmailAddress

[... more tests ...]

================================================================================
📊 Test Summary
================================================================================
Total Tests: 18
Passed: 18 ✅
Failed: 0 ❌
Success Rate: 100.0%

📋 Category Breakdown:
  DDL: 5/5 (100.0%)
  Documentation: 5/5 (100.0%)
  SQL_Example: 8/8 (100.0%)
================================================================================
```

## Interpreting Results

### ✅ All Tests Pass (100%)
Perfect! All training data is being properly utilized by Vanna.

### ⚠️ Some Tests Fail (50-99%)
Review the failed tests:
- Check if training data was loaded correctly
- Review generated SQL for each failed test
- Examine validation checks to see what's missing

### ❌ Many Tests Fail (<50%)
Possible issues:
- Training data not loaded: Run `docker exec -it vanna-app python scripts/load_training_data.py`
- API not connected to correct database
- Configuration issues in `.env`

## Test Results File

Results are saved to `tests/test_results.json` with:
```json
{
  "test_run_timestamp": "2025-12-27T15:00:00",
  "total_tests": 18,
  "passed_tests": 18,
  "results": [
    {
      "test_number": 1,
      "category": "DDL",
      "training_id": "ddl_001",
      "question": "Show me customer names...",
      "passed": true,
      "sql_generated": "SELECT...",
      "checks": [...],
      "timestamp": "2025-12-27T15:00:01"
    }
  ]
}
```

## Troubleshooting

### Tests won't run
```bash
# Check if API is accessible
curl http://localhost:8000/health

# Check if containers are running
docker-compose ps
```

### All tests fail with connection errors
```bash
# Restart services
docker-compose restart vanna-app

# Check logs
docker-compose logs vanna-app
```

### Specific category fails
- **DDL tests fail**: Schema not loaded properly
- **Documentation tests fail**: Business rules not embedded
- **SQL Example tests fail**: Example queries not in memory

### Solution: Reload training data
```bash
docker exec -it vanna-app python scripts/load_training_data.py
```

## Adding New Tests

To add a new test, edit `test_training_data_usage.py` and add to `TEST_QUERIES`:

```python
{
    "category": "DDL",  # or "Documentation" or "SQL_Example"
    "training_id": "ddl_006",
    "table": "NewTable",
    "question": "Your test question here",
    "expected_tables": ["TableName"],
    "expected_columns": ["Column1", "Column2"],
    # Optional:
    "expected_conditions": ["WHERE clause"],
    "expected_aggregations": ["SUM", "COUNT"],
    "expected_joins": ["JoinColumn"],
    "expected_limit": 10
}
```

## CI/CD Integration

To integrate into CI/CD pipeline:

```bash
# Run tests and check exit code
python tests/test_training_data_usage.py
if [ $? -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests failed"
    exit 1
fi
```

Or parse JSON results:
```python
import json
with open('tests/test_results.json') as f:
    results = json.load(f)
    if results['passed_tests'] < results['total_tests']:
        raise Exception(f"Only {results['passed_tests']}/{results['total_tests']} tests passed")
```
