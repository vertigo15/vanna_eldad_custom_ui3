"""Script to load training data into pgvector."""

import asyncio
import json
import asyncpg
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.memory.embedding_service import AzureEmbeddingService
from src.config import settings


async def load_training_data():
    """Load DDL, documentation, and SQL examples into pgvector."""
    
    print("=" * 70)
    print("VANNA TEXT-TO-SQL TRAINING DATA LOADER")
    print("=" * 70)
    print()
    
    # Initialize embedding service
    print("🔧 Initializing Azure OpenAI embedding service...")
    embedder = AzureEmbeddingService(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        api_version=settings.AZURE_OPENAI_EMBEDDINGS_API_VERSION
    )
    print("✅ Embedding service ready")
    print()
    
    # Connect to pgvector
    print("🔧 Connecting to pgvector database...")
    try:
        conn = await asyncpg.connect(
            host=settings.PGVECTOR_HOST,
            port=settings.PGVECTOR_PORT,
            database=settings.PGVECTOR_DB,
            user=settings.PGVECTOR_USER,
            password=settings.PGVECTOR_PASSWORD
        )
        print("✅ Connected to pgvector")
    except Exception as e:
        print(f"❌ Failed to connect to pgvector: {e}")
        print("   Make sure the pgvector container is running.")
        return
    print()
    
    # Determine training data path
    if os.path.exists('/app/training_data'):
        training_path = Path('/app/training_data')
    else:
        training_path = Path(__file__).parent.parent / 'training_data'
    
    print(f"📂 Training data path: {training_path}")
    print()
    
    # Clear existing data
    print("🧹 Clearing existing training data...")
    try:
        await conn.execute("DELETE FROM vanna_ddl")
        await conn.execute("DELETE FROM vanna_documentation")
        await conn.execute("DELETE FROM vanna_sql_examples")
        print("✅ Existing data cleared")
    except Exception as e:
        print(f"⚠️  Warning: Could not clear existing data: {e}")
    print()
    
    # Load DDL from schema.json
    print("📥 Loading DDL statements from schema.json...")
    schema_file = training_path / 'schema.json'
    ddl_count = 0
    
    if schema_file.exists():
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        # Load from new format (schema.json with tables array)
        if 'tables' in schema_data:
            for table in schema_data['tables']:
                try:
                    # Combine table name, description, and DDL for better context
                    full_context = f"Table: {table['name']}\nDescription: {table['description']}\n{table['ddl']}"
                    embedding = await embedder.embed(full_context)
                    await conn.execute("""
                        INSERT INTO vanna_ddl (ddl_text, embedding)
                        VALUES ($1, $2::vector)
                    """, full_context, str(embedding))
                    ddl_count += 1
                    print(f"  ✓ {table['name']}")
                except Exception as e:
                    print(f"  ✗ Failed to load {table.get('name', 'unknown')}: {e}")
        
        print(f"✅ Loaded {ddl_count} DDL statements")
    else:
        print(f"⚠️  Schema file not found: {schema_file}")
        # Try old ddl.json format as fallback
        ddl_file = training_path / 'ddl.json'
        if ddl_file.exists():
            with open(ddl_file, 'r', encoding='utf-8') as f:
                ddl_data = json.load(f)
            
            for item in ddl_data['ddl_statements']:
                try:
                    embedding = await embedder.embed(item['ddl'])
                    await conn.execute("""
                        INSERT INTO vanna_ddl (ddl_text, embedding)
                        VALUES ($1, $2::vector)
                    """, item['ddl'], str(embedding))
                    ddl_count += 1
                    print(f"  ✓ {item.get('table_name', item['id'])}")
                except Exception as e:
                    print(f"  ✗ Failed to load {item.get('table_name', item['id'])}: {e}")
            
            print(f"✅ Loaded {ddl_count} DDL statements from fallback")
    print()
    
    # Load Documentation
    print("📥 Loading documentation...")
    doc_file = training_path / 'documentation.json'
    doc_count = 0
    
    if doc_file.exists():
        with open(doc_file, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
        
        for item in doc_data['documentation']:
            try:
                embedding = await embedder.embed(item['content'])
                await conn.execute("""
                    INSERT INTO vanna_documentation (doc_text, embedding)
                    VALUES ($1, $2::vector)
                """, item['content'], str(embedding))
                doc_count += 1
                print(f"  ✓ {item.get('topic', item['id'])}")
            except Exception as e:
                print(f"  ✗ Failed to load {item.get('topic', item['id'])}: {e}")
        
        print(f"✅ Loaded {doc_count} documentation entries")
    else:
        print(f"⚠️  Documentation file not found: {doc_file}")
    print()
    
    # Load Business Terms as documentation
    print("📥 Loading business terms glossary...")
    terms_file = training_path / 'business-terms.json'
    terms_count = 0
    
    if terms_file.exists():
        with open(terms_file, 'r', encoding='utf-8') as f:
            terms_data = json.load(f)
        
        # Group terms by category for better organization
        terms_by_category = {}
        for term in terms_data:
            category = term.get('category', 'general')
            if category not in terms_by_category:
                terms_by_category[category] = []
            terms_by_category[category].append(term)
        
        # Load each category as a documentation entry
        for category, terms in terms_by_category.items():
            try:
                # Format as documentation
                doc_text = f"Business Terms - {category}\n\n"
                for term in terms:
                    doc_text += f"**{term['term']}**: {term['definition']}\n\n"
                
                embedding = await embedder.embed(doc_text)
                await conn.execute("""
                    INSERT INTO vanna_documentation (doc_text, embedding)
                    VALUES ($1, $2::vector)
                """, doc_text, str(embedding))
                terms_count += len(terms)
                print(f"  ✓ {category} ({len(terms)} terms)")
            except Exception as e:
                print(f"  ✗ Failed to load terms for {category}: {e}")
        
        print(f"✅ Loaded {terms_count} business terms")
    else:
        print(f"⚠️  Business terms file not found: {terms_file}")
    print()
    
    # Load Sample Data (samples.json) as additional documentation
    print("📥 Loading sample data examples...")
    samples_file = training_path / 'samples.json'
    samples_count = 0
    
    if samples_file.exists():
        with open(samples_file, 'r', encoding='utf-8') as f:
            samples_data = json.load(f)
        
        # Load from samples format (data_samples array)
        if 'data_samples' in samples_data:
            for sample in samples_data['data_samples']:
                try:
                    # Create documentation entry with table samples
                    # Only include first 5 examples to keep it manageable
                    table_name = sample['table']
                    description = sample['description']
                    examples = sample['examples'][:5]  # Limit to 5 examples
                    
                    # Format as documentation
                    doc_text = f"Table: {table_name}\n{description}\n\nSample data:\n"
                    doc_text += json.dumps(examples, indent=2)
                    
                    embedding = await embedder.embed(doc_text)
                    await conn.execute("""
                        INSERT INTO vanna_documentation (doc_text, embedding)
                        VALUES ($1, $2::vector)
                    """, doc_text, str(embedding))
                    samples_count += 1
                    print(f"  ✓ {table_name} ({len(examples)} samples)")
                except Exception as e:
                    print(f"  ✗ Failed to load samples for {sample.get('table', 'unknown')}: {e}")
        
        print(f"✅ Loaded {samples_count} sample data entries")
    else:
        print(f"⚠️  Samples file not found: {samples_file}")
    print()
    
    # Load SQL Examples from sql_patterns.json
    print("📥 Loading SQL examples from sql_patterns.json...")
    patterns_file = training_path / 'sql_patterns.json'
    sql_count = 0
    
    if patterns_file.exists():
        with open(patterns_file, 'r', encoding='utf-8') as f:
            patterns_data = json.load(f)
        
        # Load from new format (sql_patterns.json with common_queries array)
        if 'common_queries' in patterns_data:
            for item in patterns_data['common_queries']:
                try:
                    # Use description as the question
                    question = item['description']
                    sql = item['sql']
                    
                    # Embed the question (not the SQL)
                    embedding = await embedder.embed(question)
                    await conn.execute("""
                        INSERT INTO vanna_sql_examples (question, sql_query, embedding)
                        VALUES ($1, $2, $3::vector)
                    """, question, sql, str(embedding))
                    sql_count += 1
                    question_preview = question[:50]
                    print(f"  ✓ {question_preview}{'...' if len(question) > 50 else ''}")
                except Exception as e:
                    print(f"  ✗ Failed to load example: {e}")
        
        print(f"✅ Loaded {sql_count} SQL examples")
    else:
        print(f"⚠️  SQL patterns file not found: {patterns_file}")
        # Try old sql_examples.json format as fallback
        sql_file = training_path / 'sql_examples.json'
        if sql_file.exists():
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_data = json.load(f)
            
            for item in sql_data['sql_examples']:
                try:
                    # Embed the question (not the SQL)
                    embedding = await embedder.embed(item['question'])
                    await conn.execute("""
                        INSERT INTO vanna_sql_examples (question, sql_query, embedding)
                        VALUES ($1, $2, $3::vector)
                    """, item['question'], item['sql'], str(embedding))
                    sql_count += 1
                    question_preview = item['question'][:50]
                    print(f"  ✓ {question_preview}{'...' if len(item['question']) > 50 else ''}")
                except Exception as e:
                    print(f"  ✗ Failed to load example: {e}")
            
            print(f"✅ Loaded {sql_count} SQL examples from fallback")
    print()
    
    await conn.close()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  DDL Statements:  {ddl_count}")
    print(f"  Documentation:   {doc_count}")
    print(f"  SQL Examples:    {sql_count}")
    print(f"  Total:           {ddl_count + doc_count + sql_count}")
    print()
    print("✅ Training data loaded successfully!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(load_training_data())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
