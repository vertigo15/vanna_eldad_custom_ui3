# Chart Type Selection Debugging Guide

## Issue: Chart Gets Stuck When Changing Type

### Fixes Applied

1. **Updated `ChartTypeSelector.handleTypeChange()`** - Added `updateRecommendationDisplay()` call
2. **Updated `ChartManager.renderChart()`** - Only initialize chart instance once, reuse for subsequent renders

### How to Debug

#### 1. Check Browser Console (F12)

Look for these log messages:
```javascript
[ChartTypeSelector] Chart type changed to: [type]
[ChartManager] Chart type changed to: [type]
[ChartManager] Generating chart with LLM, type: [type]
[ChartManager] Calling LLM API for type: [type]  // or "Using cached LLM response"
[ChartManager] LLM response received
[ChartManager] Chart rendered successfully
```

**If stuck at "Loading chart...":**
- Check for errors in console
- Look for failed API calls in Network tab

#### 2. Check Backend Logs

```powershell
docker-compose logs --tail=20 vanna-app | Select-String -Pattern "chart"
```

Look for:
```
INFO - Generating chart for X rows, Y columns, type=<type>
INFO - Chart generated successfully: type=<type>
```

**If you see errors:**
- Check if LLM service is responding
- Verify request payload has `chart_type` parameter

#### 3. Clear Browser Cache

If charts are not updating:
```javascript
// In browser console:
sessionStorage.clear();
```

Then refresh the page and try again.

#### 4. Check sessionStorage Keys

```javascript
// In browser console:
Object.keys(sessionStorage).filter(k => k.startsWith('chart_'))
```

Should show keys like:
```
chart_llm_<hash>_auto
chart_llm_<hash>_bar
chart_llm_<hash>_line
```

### Common Issues

#### Issue: Chart Stuck on Loading Spinner

**Cause**: Chart container was being re-initialized on every render

**Fix**: Check `if (!this.chartContainer.chartInstance)` before calling `init()`

**Verification**:
```javascript
// Should see only once per page load:
[ChartContainer] ECharts instance initialized
```

#### Issue: Chart Type Doesn't Change

**Cause**: Dropdown change not triggering regeneration

**Fix**: Ensure `handleTypeChange()` calls `this.onChange(chartType)`

**Verification**:
```javascript
// Should see after changing dropdown:
[ChartManager] Chart type changed to: <new-type>
```

#### Issue: Recommendation Not Updating

**Cause**: Missing `updateRecommendationDisplay()` call in `handleTypeChange()`

**Fix**: Added in line 101 of ChartTypeSelector.js

**Verification**: Yellow badge should update to show:
- When "Auto": "LLM selected: Bar Chart"
- When override: "LLM originally recommended: Bar Chart"

### Testing Steps

1. **Initial Load**:
   - Execute query
   - Click Chart tab
   - Should see "Auto (LLM Recommended)" selected
   - Chart should load within 2-5 seconds
   - Yellow badge shows "LLM selected: [type]"

2. **Change Type**:
   - Select "Line Chart" from dropdown
   - Loading spinner appears
   - New chart loads within 2-5 seconds
   - Badge updates to "LLM originally recommended: [type]"

3. **Switch Back**:
   - Select original type
   - Should load instantly from cache
   - No API call in Network tab

4. **New Query**:
   - Execute different query
   - Chart tab resets to "Auto"
   - Cache is cleared for new dataset
   - Dropdown shows "Auto (LLM Recommended)"

### Performance Expectations

| Action | Expected Time | Cache Hit |
|--------|---------------|-----------|
| First chart generation | 2-5 seconds | No |
| Change to new type | 2-5 seconds | No |
| Change to cached type | < 100ms | Yes |
| New query → Chart | 2-5 seconds | No |

### Emergency Reset

If charts completely break:

1. Clear all browser storage:
```javascript
sessionStorage.clear();
localStorage.clear();
```

2. Hard refresh: `Ctrl + Shift + R`

3. Restart containers:
```powershell
docker-compose restart vanna-app vanna-ui
```

4. Check logs for errors:
```powershell
docker-compose logs --tail=50 vanna-app
docker-compose logs --tail=50 vanna-ui
```
