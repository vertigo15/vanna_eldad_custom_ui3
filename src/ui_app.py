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


@app.route('/api/generate-chart', methods=['POST'])
def generate_chart():
    """
    Generate chart configuration using LLM.
    LLM decides chart type and creates ECharts JSON.
    
    Request:
        columns: List of column info with name and type
        column_names: List of column names
        sample_data: Sample data rows (first 10)
        all_data: All data if dataset is small
    
    Returns:
        chart_config: ECharts configuration JSON
        chart_type: Type of chart chosen by LLM
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info(f"Generating chart with LLM for {len(data.get('column_names', []))} columns")
        
        # Forward to the main API backend for LLM chart generation
        response = requests.post(
            f'{API_BASE_URL}/api/generate-chart',
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info('Chart generation successful')
            return jsonify(result)
        else:
            logger.error(f"Chart generation API error: {response.status_code}")
            return jsonify({
                'error': f'Chart generation service unavailable: {response.status_code}'
            }), 503
            
    except requests.exceptions.Timeout:
        logger.error('Chart generation request timed out')
        return jsonify({'error': 'Chart generation request timed out'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Chart generation request error: {e}")
        return jsonify({'error': f'Failed to connect to chart generation service: {str(e)}'}), 503
    except Exception as e:
        logger.error(f"Unexpected error in chart generation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-insights', methods=['POST'])
def generate_insights_endpoint():
    """
    Generate insights for query results using LLM.
    
    Request:
        dataset: Query results (dict with 'rows' and 'columns')
        question: Original user question
    
    Returns:
        insights: Dict with 'summary', 'findings', 'suggestions'
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info(f"Generating insights for question: {data.get('question', 'N/A')[:50]}...")
        
        # Forward to the main API backend for LLM insight generation
        response = requests.post(
            f'{API_BASE_URL}/api/generate-insights',
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info('Insights generation successful')
            return jsonify(result)
        else:
            logger.error(f"Insights API error: {response.status_code}")
            return jsonify({
                'error': f'Insights service unavailable: {response.status_code}'
            }), 503
            
    except requests.exceptions.Timeout:
        logger.error('Insights request timed out')
        return jsonify({'error': 'Insights request timed out'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Insights request error: {e}")
        return jsonify({'error': f'Failed to connect to insights service: {str(e)}'}), 503
    except Exception as e:
        logger.error(f"Unexpected error in insights generation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-profile', methods=['POST'])
def generate_profile_endpoint():
    """
    Generate data profiling report using ydata-profiling.
    
    Request:
        dataset: Query results (dict with 'rows' and 'columns')
    
    Returns:
        html: HTML string containing the full profile report
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info('Generating data profile report...')
        
        # Forward to the main API backend for profiling
        response = requests.post(
            f'{API_BASE_URL}/api/generate-profile',
            json=data,
            timeout=120  # Profiling can take longer for large datasets
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info('Profile report generated successfully')
            return jsonify(result)
        else:
            logger.error(f"Profile API error: {response.status_code}")
            return jsonify({
                'error': f'Profile service unavailable: {response.status_code}'
            }), 503
            
    except requests.exceptions.Timeout:
        logger.error('Profile request timed out')
        return jsonify({'error': 'Profile generation timed out. Try with a smaller dataset.'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Profile request error: {e}")
        return jsonify({'error': f'Failed to connect to profile service: {str(e)}'}), 503
    except Exception as e:
        logger.error(f"Unexpected error in profile generation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/enhance-chart', methods=['POST'])
def enhance_chart():
    """
    Enhance chart configuration using LLM.
    
    Request:
        columns: List of column info with name and type
        sample_data: Sample data rows (first 10)
        chart_type: Type of chart (line/bar/pie)
        current_config: Current basic chart config
    
    Returns:
        enhanced_config: Enhanced ECharts configuration
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info(f"Enhancing chart: type={data.get('chart_type')}")
        
        # Forward to the main API backend for LLM enhancement
        # Note: This endpoint needs to be implemented in the main Vanna API
        response = requests.post(
            f'{API_BASE_URL}/api/enhance-chart',
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info('Chart enhancement successful')
            return jsonify(result)
        else:
            logger.error(f"Chart enhancement API error: {response.status_code}")
            # Fallback: return error so frontend uses Tier 1 config
            return jsonify({
                'error': f'Enhancement service unavailable: {response.status_code}'
            }), 503
            
    except requests.exceptions.Timeout:
        logger.error('Chart enhancement request timed out')
        return jsonify({'error': 'Enhancement request timed out'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Chart enhancement request error: {e}")
        return jsonify({'error': f'Failed to connect to enhancement service: {str(e)}'}), 503
    except Exception as e:
        logger.error(f"Unexpected error in chart enhancement: {e}", exc_info=True)
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
