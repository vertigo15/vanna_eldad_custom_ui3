# Testing Guide

## Test Structure

```
tests/
├── test_tools.py           # Unit tests for Chart and Insights tools
├── test_integration.py     # Integration tests (structure only)
├── test_ui_e2e.py         # End-to-end UI tests (NEW!)
└── README_TESTING.md      # This file
```

## Running Tests

### Unit Tests (Tools)

Test individual tools in isolation with mocked LLM:

```bash
# Run all unit tests
pytest tests/test_tools.py -v

# Run specific test class
pytest tests/test_tools.py::TestChartGenerationTool -v

# Run specific test
pytest tests/test_tools.py::TestChartGenerationTool::test_chart_generation_bar_chart -v
```

### End-to-End Tests (UI)

Test complete workflow through API and UI:

**Prerequisites:**
- Docker containers running (pgvector-db, vanna-app, vanna-ui)
- Services accessible at http://localhost:8000 and http://localhost:8501

```bash
# Run all E2E tests
pytest tests/test_ui_e2e.py -v -s

# Run with detailed output
pytest tests/test_ui_e2e.py -v -s --tb=short

# Run specific test category
pytest tests/test_ui_e2e.py -k "chart" -v      # Only chart tests
pytest tests/test_ui_e2e.py -k "insights" -v   # Only insights tests
pytest tests/test_ui_e2e.py -k "performance" -v # Only performance tests

# Run full workflow test
pytest tests/test_ui_e2e.py::TestUIEndToEnd::test_full_workflow_query_chart_insights -v -s
```

### All Tests with Coverage

```bash
# Run all tests with coverage report
pytest --cov=src --cov-report=html --cov-report=term -v

# Open coverage report
# Windows: start htmlcov/index.html
# Mac/Linux: open htmlcov/index.html
```

## Test Categories

### 1. Basic Query Tests
- `test_simple_query_execution` - Test SQL generation and execution
- `test_query_with_conversation_id` - Test conversation tracking
- `test_invalid_query_handling` - Test error handling

### 2. Chart Generation Tests
- `test_chart_generation_bar_chart` - Test bar charts
- `test_chart_generation_line_chart` - Test line/time series charts
- `test_chart_number_formatting` - Test K/M/B number formatting

### 3. Insights Generation Tests
- `test_insights_generation_basic` - Test basic insights
- `test_insights_with_numerical_data` - Test numerical analysis
- `test_insights_empty_dataset_handling` - Test edge cases

### 4. Integrated Workflow Tests
- `test_full_workflow_query_chart_insights` - Complete end-to-end flow
- `test_conversation_persistence` - Multi-turn conversations

### 5. Performance Tests
- `test_query_performance` - Query execution time (<10s)
- `test_chart_generation_performance` - Chart generation time (<5s)
- `test_insights_generation_performance` - Insights generation time (<10s)

## Manual Testing Checklist

After running automated tests, manually verify:

### Basic Functionality
1. ✅ Load UI at http://localhost:8501
2. ✅ Enter question: "show sales of 2006"
3. ✅ Verify SQL displays
4. ✅ Verify results table displays
5. ✅ Check browser console for errors (F12)

### Chart Generation
1. ✅ Query: "show monthly sales for 2006"
2. ✅ Verify chart section appears
3. ✅ Verify chart renders (bars/lines visible)
4. ✅ Verify axis labels present
5. ✅ Verify numbers formatted (e.g., "1.2M" not "1200000")

### Insights Generation
1. ✅ Query: "show top 10 products by sales"
2. ✅ Verify insights section appears
3. ✅ Verify summary is meaningful (not empty)
4. ✅ Verify findings mention specific numbers
5. ✅ Verify suggestions are actionable

### Conversation History
1. ✅ Ask: "show sales for 2006"
2. ✅ Ask follow-up: "what was the total?"
3. ✅ Verify context maintained
4. ✅ Check recent questions sidebar
5. ✅ Test "Clear History" button

## Common Issues and Solutions

### Issue: Tests fail with "Service not ready"
**Solution:** Start Docker containers:
```bash
docker-compose up -d
# Wait 10 seconds for services to initialize
```

### Issue: Chart/Insights tests fail with 404
**Solution:** Verify main_vanna2_full.py is running:
```bash
docker logs vanna-app | grep "Vanna 2.0 Full Agent"
# Should see: "✅ Vanna 2.0 Agent created!"
```

### Issue: Tests timeout
**Solution:** Check LLM service connectivity:
```bash
docker logs vanna-app | grep "LLM"
# Check for Azure OpenAI connection errors
```

### Issue: Tests pass but UI doesn't work
**Solution:** 
1. Check UI logs: `docker logs vanna-ui`
2. Verify UI container running: `docker ps | grep vanna-ui`
3. Test API directly: `curl http://localhost:8000/health`

## Test Data Requirements

Tests expect AdventureWorksDW database with:
- Sales data for years 2006-2007
- Product categories
- Monthly aggregations
- Regional data

If using different database, update test queries in `test_ui_e2e.py`.

## Continuous Integration

To run tests in CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Run Unit Tests
  run: pytest tests/test_tools.py -v

- name: Start Services
  run: docker-compose up -d

- name: Wait for Services
  run: sleep 15

- name: Run E2E Tests
  run: pytest tests/test_ui_e2e.py -v --tb=short

- name: Generate Coverage Report
  run: pytest --cov=src --cov-report=xml
```

## Performance Benchmarks

Expected performance (from `test_*_performance` tests):

| Operation | Target | Typical |
|-----------|--------|---------|
| Query execution | <10s | 3-5s |
| Chart generation | <5s | 1-2s |
| Insights generation | <10s | 3-6s |
| Full workflow | <20s | 10-15s |

If tests exceed targets, investigate:
1. LLM API latency
2. Database query optimization
3. Network issues
4. Resource constraints (CPU/memory)

## Debugging Failed Tests

Enable verbose logging:

```bash
# Run with pytest debug output
pytest tests/test_ui_e2e.py -v -s --log-cli-level=DEBUG

# Check application logs during test
docker logs -f vanna-app

# Check database queries
docker exec -it pgvector-db psql -U vannauser -d postgres \
  -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

## Test Coverage Goals

- **Unit Tests**: >90% coverage of tool code
- **E2E Tests**: All critical user paths
- **Manual Tests**: UI usability and edge cases

Run coverage report:
```bash
pytest --cov=src --cov-report=term-missing
```

## Contributing

When adding new features:
1. Write unit tests first (TDD)
2. Add E2E test for user-facing features
3. Update manual checklist if needed
4. Ensure all tests pass before PR
5. Check coverage doesn't decrease

---

For questions or issues, see `MAINTENANCE.md` for troubleshooting guide.
