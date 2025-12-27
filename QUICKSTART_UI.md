# Vanna 2.0 UI - Quick Start Guide

## 🚀 Start Everything

```bash
docker-compose up -d
```

Wait about 30 seconds for all services to start.

## 🌐 Open the UI

Open your browser and go to:

**http://localhost:8501**

## 💬 Ask Your First Question

1. Type a question in the text box, for example:
   - "What are the top 10 products by sales?"
   - "Show me total revenue by year"
   - "Which customers have the highest order totals?"

2. Click **"Ask Question"** or press `Ctrl + Enter`

3. Wait a few seconds while Vanna:
   - Converts your question to SQL
   - Executes the query
   - Returns the results

## 📊 What You'll See

The UI displays:
- **Your Question** - The natural language question you asked
- **Generated SQL** - The SQL query Vanna created
- **Results** - Data in a formatted table
- **Explanation** - (if available) How the SQL works

## 🎯 Tips

- **Load Tables**: Click "Load Tables" in the sidebar to see available database tables
- **Try Samples**: Click any sample question in the sidebar to auto-fill it
- **Copy SQL**: Click "Copy SQL" button to copy the generated query
- **Keyboard Shortcut**: Use `Ctrl + Enter` to submit your question quickly

## 🔧 If Something Goes Wrong

### UI Won't Load?

Check if services are running:
```bash
docker-compose ps
```

All three containers should show "Up" status.

### No Results?

1. Make sure you loaded the training data:
```bash
docker exec -it vanna-app python scripts/load_training_data.py
```

2. Check the backend health:
```bash
curl http://localhost:8000/health
```

### Backend Issues?

Check the logs:
```bash
docker-compose logs vanna-app
docker-compose logs vanna-ui
```

## 🛑 Stop Everything

```bash
docker-compose down
```

## 📚 Need More Help?

- **UI Details**: See [UI_README.md](UI_README.md)
- **Full Documentation**: See [README.md](README.md)
- **Training Data**: See [TRAINING_DATA_SUMMARY.md](TRAINING_DATA_SUMMARY.md)

---

**Enjoy using Vanna 2.0! 🎉**
