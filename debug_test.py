import requests
import json
import time

print("Testing Vanna Agent SQL generation...")
print("=" * 60)

# Test with a very simple, direct question
questions = [
    "SELECT * FROM dimproduct LIMIT 5",  # Direct SQL should work
    "show me 5 products",  # Natural language
    "What tables are available?"  # Meta question
]

for i, question in enumerate(questions, 1):
    print(f"\n{i}. Testing: {question}")
    print("-" * 60)
    
    try:
        response = requests.post(
            'http://localhost:8000/api/query',
            json={'question': question},
            timeout=30
        )
        
        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"SQL Generated: {result.get('sql', 'None')[:100] if result.get('sql') else 'None'}")
        print(f"Has Results: {bool(result.get('results'))}")
        print(f"Error: {result.get('error')}")
        print(f"Explanation: {result.get('explanation', '')[:150] if result.get('explanation') else 'None'}")
        
        if result.get('sql'):
            print(f"✅ SUCCESS - SQL was generated!")
            break
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    time.sleep(2)

print("\n" + "=" * 60)
