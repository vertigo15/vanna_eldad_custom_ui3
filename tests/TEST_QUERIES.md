# Test Queries Reference

Quick reference of all 18 test queries used to validate training data.

## DDL Tests (5)

### Test 1: DimCustomer (ddl_001)
**Question:** Show me customer names and email addresses  
**Expected:** Uses DimCustomer table with FirstName, LastName, EmailAddress

### Test 2: FactInternetSales (ddl_002)
**Question:** List all sales with order numbers and amounts  
**Expected:** Uses FactInternetSales with SalesOrderNumber, SalesAmount

### Test 3: DimProduct (ddl_003)
**Question:** Show product names with their prices and costs  
**Expected:** Uses DimProduct with EnglishProductName, ListPrice, StandardCost

### Test 4: DimDate (ddl_004)
**Question:** Show calendar years with their quarters  
**Expected:** Uses DimDate with CalendarYear, CalendarQuarter

### Test 5: DimGeography (ddl_005)
**Question:** List cities with their state and country information  
**Expected:** Uses DimGeography with City, StateProvinceName, EnglishCountryRegionName

---

## Documentation Tests (5)

### Test 6: Customer Segmentation (doc_001)
**Question:** Show me all high-value customers with income over 100000  
**Expected:** Uses DimCustomer with condition YearlyIncome > 100000

### Test 7: Sales Metrics (doc_002)
**Question:** Calculate the net revenue excluding tax and freight  
**Expected:** Uses FactInternetSales with formula: SalesAmount - TaxAmt - Freight

### Test 8: Date Dimension (doc_003)
**Question:** Show sales by calendar quarter and year  
**Expected:** Joins FactInternetSales and DimDate on DateKey, uses CalendarYear and CalendarQuarter

### Test 9: Product Information (doc_004)
**Question:** Show Road bikes with their retail prices  
**Expected:** Uses DimProduct with condition ProductLine = 'R', shows EnglishProductName, ListPrice

### Test 10: Geography Data (doc_005)
**Question:** Show customer counts by country using geography information  
**Expected:** Joins DimCustomer and DimGeography on GeographyKey, uses EnglishCountryRegionName

---

## SQL Example Tests (8)

### Test 11: Total Revenue (sql_001)
**Question:** What is the total revenue?  
**Expected:** `SELECT SUM(SalesAmount) FROM FactInternetSales`

### Test 12: Top Customers (sql_002)
**Question:** Show me top 10 customers by total purchases  
**Expected:** Joins FactInternetSales and DimCustomer, groups by customer, limits to 10

### Test 13: High-Value Customers (sql_003)
**Question:** How many high-value customers do we have?  
**Expected:** `SELECT COUNT(*) FROM DimCustomer WHERE YearlyIncome > 100000`

### Test 14: Sales by Year (sql_004)
**Question:** What are the total sales by year?  
**Expected:** Joins FactInternetSales and DimDate, groups by CalendarYear

### Test 15: Top Products (sql_005)
**Question:** Show me the top 5 products by revenue  
**Expected:** Joins FactInternetSales and DimProduct, groups by product, limits to 5

### Test 16: Average Order Value (sql_006)
**Question:** What is the average order value?  
**Expected:** `SELECT AVG(SalesAmount) FROM FactInternetSales`

### Test 17: Orders in 2023 (sql_007)
**Question:** How many orders were placed in 2023?  
**Expected:** Joins with DimDate, filters CalendarYear = 2023, counts records

### Test 18: Sales by Country (sql_008)
**Question:** Show sales by country  
**Expected:** Joins FactInternetSales, DimCustomer, DimGeography; groups by EnglishCountryRegionName

---

## Testing Coverage

| Category | Tests | Training Items | Coverage |
|----------|-------|----------------|----------|
| DDL | 5 | 5 tables | 100% |
| Documentation | 5 | 5 business rules | 100% |
| SQL Examples | 8 | 8 Q&A pairs | 100% |
| **TOTAL** | **18** | **18 items** | **100%** |

## Using These Queries

### Via API
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue?"}'
```

### Via UI
1. Open http://localhost:8501
2. Type any question from above
3. Click "Ask Question"

### Via Test Script
```bash
python tests/test_training_data_usage.py
```

### Via PowerShell
```powershell
.\run_tests.ps1
```

---

## Expected Results

All tests should:
- ✅ Generate valid SQL
- ✅ Reference correct tables
- ✅ Use appropriate columns
- ✅ Apply correct business logic
- ✅ Execute without errors

## Success Criteria

- **100% Pass Rate**: All training data is being utilized correctly
- **80-99% Pass Rate**: Most training data works, some edge cases
- **<80% Pass Rate**: Issues with training data loading or configuration
