# Chart Feature Implementation

## Overview
This feature adds chart visualization capabilities to query results with a two-tier system:
- **Tier 1**: Instant auto-generated charts (frontend only)
- **Tier 2**: AI-enhanced charts (optional, via LLM API)

## Architecture

### Clean Separation of Concerns
```
chart-feature/
├── components/          # UI components (no business logic)
│   ├── ChartToggle.js
│   ├── ChartContainer.js
│   ├── ChartTypeSelector.js
│   └── EnhanceButton.js
├── services/            # Business logic (no DOM dependencies)
│   ├── chartConfigGenerator.js
│   └── chartEnhancerService.js
├── prompts/             # LLM prompts (easily editable)
│   └── chartEnhancerPrompt.js
├── utils/               # Pure utility functions
│   ├── dataAnalyzer.js
│   └── echartsValidator.js
├── types/               # TypeScript/JSDoc definitions
│   └── chart.types.js
├── chartManager.js      # Main orchestrator
└── README.md
```

## Key Features

### 1. Automatic Chart Type Detection
- **Line Chart**: Date/time + numeric data
- **Pie Chart**: Category (≤10 unique) + numeric data
- **Bar Chart**: Category (>10 unique) + numeric data, or default

### 2. Data Analysis
- Detects column types: numeric, category, date
- Identifies suitable X and Y axis columns
- Validates data is chartable (needs 2+ columns, at least 1 numeric)

### 3. Two-Tier Chart Generation

#### Tier 1: Auto-Generation (Default)
- Instant rendering, no API calls
- Basic but professional chart configs
- Proper axis labels and formatting
- Responsive design

#### Tier 2: AI Enhancement (On-Demand)
- Click "✨ Enhance with AI" button
- LLM improves:
  - Titles and descriptions
  - Color schemes
  - Number formatting
  - Axis labels and units
  - Tooltip customization
- Results cached in sessionStorage

### 4. User Preferences
- **localStorage**: Remembers last view mode (table/chart)
- **sessionStorage**: Caches enhanced chart configs per query/type

### 5. Edge Case Handling
- Single column: Chart disabled
- No numeric columns: Chart disabled
- Empty results: "No data to display"
- LLM fails: Falls back to Tier 1 config
- Network timeouts: Graceful fallback

## Data Flow

```
Query Results
    ↓
Data Analyzer (detect types, suggest chart)
    ↓
Chart Config Generator (Tier 1 - basic config)
    ↓
Chart Container (render with ECharts)
    ↓
[Optional] User clicks "Enhance"
    ↓
Chart Enhancer Service (Tier 2 - call API)
    ↓
Validator (validate LLM response)
    ↓
Chart Container (re-render with enhanced config)
```

## API Integration

### Backend Endpoint
**POST /api/enhance-chart**

Request:
```json
{
  "columns": [
    {"name": "date", "type": "date"},
    {"name": "sales", "type": "numeric"}
  ],
  "sample_data": [[...], [...], ...],
  "chart_type": "line",
  "current_config": {...}
}
```

Response:
```json
{
  "enhanced_config": {...}
}
```

### Main API Implementation
The main Vanna API backend needs to implement `/api/enhance-chart` endpoint that:
1. Receives the request from UI
2. Calls LLM with the prompt from `chartEnhancerPrompt.js`
3. Returns enhanced ECharts JSON configuration

## Usage

### For Users
1. Run a query
2. Click "📈 Chart" button to switch views
3. Select chart type from dropdown (Line/Bar/Pie)
4. (Optional) Click "✨ Enhance with AI" for better styling
5. Toggle back to "📊 Table" anytime

### For Developers

#### Modifying Prompts
Edit `prompts/chartEnhancerPrompt.js` - no other code changes needed:
```javascript
export const CHART_ENHANCER_SYSTEM_PROMPT = `
  Your prompt here...
`;
```

#### Adding New Chart Types
1. Add type to `types/chart.types.js`
2. Add generation logic in `services/chartConfigGenerator.js`
3. Update selector in `components/ChartTypeSelector.js`

#### Customizing Auto-Detection Rules
Edit `utils/dataAnalyzer.js` `suggestChartType()` function.

## Logging

All modules include comprehensive console logging with prefixes:
- `[ChartManager]` - Main orchestration
- `[DataAnalyzer]` - Data analysis
- `[ChartConfigGenerator]` - Config generation
- `[ChartEnhancerService]` - API calls
- `[EChartsValidator]` - Validation
- `[ChartContainer]` - Rendering
- `[ChartToggle]`, `[ChartTypeSelector]`, `[EnhanceButton]` - UI components

## Dependencies

### External
- **ECharts 5.x**: Loaded lazily from CDN when user first views chart

### Internal
- Vanilla JavaScript (ES6 modules)
- No build step required
- No framework dependencies

## Browser Compatibility
- Modern browsers with ES6 module support
- ResizeObserver for responsive charts (graceful fallback)
- AbortSignal timeout for API calls

## Testing

### Manual Testing Checklist
- [ ] Table with 2+ columns, 1+ numeric → Chart enabled
- [ ] Table with 1 column → Chart disabled
- [ ] Table with no numeric columns → Chart disabled
- [ ] Empty results → "No data to display"
- [ ] Switch between Line/Bar/Pie
- [ ] Enhance button shows loading state
- [ ] Enhancement fails gracefully
- [ ] View preference persists
- [ ] Cache works (no duplicate API calls)
- [ ] Responsive design works
- [ ] Charts resize properly

## Future Enhancements
- Multiple Y-axis support
- Stacked bar/line charts
- Custom color picker
- Chart export (PNG/SVG)
- More chart types (scatter, area, etc.)
- Drill-down interactions
