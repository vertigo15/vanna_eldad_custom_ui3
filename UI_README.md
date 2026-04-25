# Vanna 2.0 Basic UI

A clean, modern web interface for Vanna 2.0 Text-to-SQL system.

## Features

- 🎨 **Clean Modern UI** - Beautiful gradient design with responsive layout
- 💬 **Natural Language Queries** - Ask questions in plain English
- 💻 **SQL Display** - View generated SQL with syntax highlighting
- 📊 **Results Table** - Display query results in formatted tables
- 📚 **Table Browser** - View available database tables
- 📝 **Sample Questions** - Quick-start with example queries
- 📋 **Copy SQL** - One-click SQL copying to clipboard

## Architecture

The UI is built with:
- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript + CSS
- **API**: Connects to FastAPI backend (vanna-app)

```
┌─────────────┐      HTTP       ┌──────────────┐      HTTP       ┌────────────────┐
│   Browser   │ ◄──────────────► │  Flask UI    │ ◄──────────────► │  FastAPI App   │
│  (Port TBD) │                  │  (Port 8501) │                  │  (Port 8000)   │
└─────────────┘                  └──────────────┘                  └────────────────┘
```

## Quick Start

### With Docker Compose (Recommended)

Start all services including the UI:

```bash
docker-compose up -d
```

The UI will be available at:
- **UI**: http://localhost:8501
- **API**: http://localhost:8000

### Standalone (Development)

If you want to run the UI separately:

```bash
# Install dependencies
pip install -r requirements.txt

# Set API URL (if different from default)
export API_BASE_URL=http://localhost:8000

# Run UI
python -m flask --app src.ui_app:app run --host 0.0.0.0 --port 8501
```

## Usage

1. **Open Browser** - Navigate to http://localhost:8501
2. **Ask Questions** - Type natural language questions about your data
3. **View Results** - See SQL, explanation, and query results
4. **Explore Tables** - Click "Load Tables" to see available tables
5. **Try Samples** - Click sample questions to get started quickly

### Keyboard Shortcuts

- `Ctrl + Enter` - Submit question

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://vanna-app:8000` | Backend API URL |
| `UI_PORT` | `8501` | UI server port |

## Files Structure

```
src/
├── ui_app.py              # Flask application
├── templates/
│   └── index.html         # Main UI template
└── static/
    ├── style.css          # UI styles
    └── script.js          # UI interactivity
```

## API Endpoints (UI Backend)

The UI Flask app provides:

- `GET /` - Main UI page
- `POST /api/ask` - Forward question to backend
- `GET /api/tables` - Get available tables
- `GET /api/schema/<table>` - Get table schema
- `GET /health` - Health check

## Troubleshooting

### UI Won't Start

Check if the backend is running:
```bash
curl http://localhost:8000/health
```

### Can't Connect to API

1. Verify `API_BASE_URL` environment variable
2. Check Docker network connectivity
3. Ensure vanna-app container is healthy

### No Results Showing

1. Check browser console for errors (F12)
2. Verify API is returning data
3. Check network tab for failed requests

## Development

To modify the UI:

1. Edit files in `src/templates/` and `src/static/`
2. Refresh browser (no restart needed for HTML/CSS/JS)
3. For Python changes, restart Flask:
   ```bash
   docker-compose restart vanna-ui
   ```

## Production Considerations

For production deployment:

1. **Security**:
   - Set `FLASK_ENV=production`
   - Configure proper CORS origins
   - Add authentication if needed

2. **Performance**:
   - Use production WSGI server (gunicorn)
   - Enable caching
   - Add rate limiting

3. **Monitoring**:
   - Add logging
   - Set up health checks
   - Monitor API response times

## License

Same as parent Vanna 2.0 project
