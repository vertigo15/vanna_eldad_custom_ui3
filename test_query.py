import requests
import json

r = requests.post('http://localhost:8000/api/query', json={'question': 'show me top 10 products by sales'}, timeout=40)
print('Status:', r.status_code)
res = r.json()
print('SQL Found:', bool(res.get('sql')))
print('Results Found:', bool(res.get('results')))
print('Error:', res.get('error'))
if res.get('sql'):
    print('SQL:', res['sql'][:200])
if res.get('results'):
    print('Row count:', res['results'].get('row_count'))
