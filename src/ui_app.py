"""Vanna 2.0 Basic UI using Flask."""

import os
import logging
from flask import Flask, render_template, request, jsonify
import requests
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://vanna-app:8000')


@app.route('/')
def index():
    """Render the main UI page."""
    return render_template('index.html')


@app.route('/api/ask', methods=['POST'])
def ask_question():
    """
    Forward question to the Vanna API backend.
    
    Returns:
        JSON response with SQL, results, and explanation
    """
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'Question cannot be empty'}), 400
        
        logger.info(f"Forwarding question to API: {question}")
        
        # Call the FastAPI backend
        response = requests.post(
            f'{API_BASE_URL}/api/query',
            json={'question': question},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            has_prompt = 'prompt' in result
            prompt_length = len(result.get('prompt', '')) if has_prompt else 0
            logger.info(f"Received response from API - Has prompt: {has_prompt}, Prompt length: {prompt_length}")
            return jsonify(result)
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return jsonify({
                'error': f'API error: {response.status_code}',
                'details': response.text
            }), response.status_code
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return jsonify({'error': f'Failed to connect to API: {str(e)}'}), 503
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/tables', methods=['GET'])
def get_tables():
    """Get list of available tables."""
    try:
        response = requests.get(f'{API_BASE_URL}/api/tables', timeout=10)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch tables'}), response.status_code
    except Exception as e:
        logger.error(f"Error fetching tables: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/schema/<table_name>', methods=['GET'])
def get_schema(table_name: str):
    """Get schema for a specific table."""
    try:
        response = requests.get(f'{API_BASE_URL}/api/schema/{table_name}', timeout=10)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'Failed to fetch schema for {table_name}'}), response.status_code
    except Exception as e:
        logger.error(f"Error fetching schema: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    try:
        response = requests.get(f'{API_BASE_URL}/health', timeout=5)
        backend_status = response.json() if response.status_code == 200 else {'status': 'unhealthy'}
        
        return jsonify({
            'ui_status': 'healthy',
            'backend_status': backend_status
        })
    except Exception as e:
        return jsonify({
            'ui_status': 'healthy',
            'backend_status': {'status': 'unhealthy', 'error': str(e)}
        })


if __name__ == '__main__':
    port = int(os.getenv('UI_PORT', 8501))
    app.run(host='0.0.0.0', port=port, debug=True)
