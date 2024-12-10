from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration: URL of the lora_service APIs
# Replace with your actual ngrok URL
LORA_SERVICE_URL = "https://303c-124-111-21-208.ngrok-free.app"

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.start()

# Ensure the scheduler shuts down gracefully on application exit
atexit.register(lambda: scheduler.shutdown())

# Helper function to send requests to lora_service
def send_lora_request(method, endpoint, **kwargs):
    """
    Sends an HTTP request to the lora_service.

    :param method: HTTP method ('get', 'post', etc.)
    :param endpoint: API endpoint (e.g., '/node_data/1')
    :param kwargs: Additional arguments for requests.request
    :return: Tuple (response_json, status_code)
    """
    url = f"{LORA_SERVICE_URL}{endpoint}"
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
        response.raise_for_status()
        logger.info(f"Successful {method.upper()} request to {url}")
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during {method.upper()} request to {url}: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route('/periodic_data/<int:node_id>', methods=['GET'])
def periodic_data(node_id):
    """
    Fetch periodic data from a node.
    """
    response, status_code = send_lora_request('get', f"/periodic_data/{node_id}")
    return jsonify(response), status_code

@app.route('/tank_data/<int:node_id>', methods=['GET'])
def tank_data(node_id):
    """
    Fetches the tank data (e.g., water level threshold) for a specific node from the LoRa service.
    """
    response, status_code = send_lora_request('get', f"/tank-data/{node_id}")
    return jsonify(response), status_code

@app.route('/set_threshold/<int:node_id>', methods=['POST'])
def set_threshold(node_id):
    """
    Set threshold for a specific node.
    """
    data = request.get_json()
    if not data or "threshold" not in data:
        return jsonify({"status": "error", "message": "Threshold not provided"}), 400

    threshold = data.get("threshold")

    # Ensure threshold is an integer
    try:
        threshold = int(threshold)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Threshold must be an integer"}), 400

    payload = {"threshold": threshold}
    response, status_code = send_lora_request('post', f"/set_threshold/{node_id}", json=payload)
    return jsonify(response), status_code

@app.route('/all_node_data', methods=['GET'])
def all_node_data():
    """
    Retrieve data from all nodes.
    """
    response, status_code = send_lora_request('get', "/all_node_data")
    return jsonify(response), status_code

@app.route('/get_node_data/<int:node_id>', methods=['GET'])
def get_node_data(node_id):
    """
    Fetch data from a specific node.
    """
    response, status_code = send_lora_request('get', f"/node_data/{node_id}")
    return jsonify(response), status_code

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    """
    return jsonify({"status": "healthy"}), 200

def scheduled_periodic_data():
    """
    Scheduled task to fetch periodic data for all nodes.
    """
    node_ids = [1, 2, 3]  # Replace with your actual node IDs
    for node_id in node_ids:
        logger.info(f"Fetching periodic data for Node {node_id}")
        response, status_code = send_lora_request('get', f"/periodic_data/{node_id}")
        if status_code == 200:
            logger.info(f"Periodic data for Node {node_id}: {response}")
        else:
            logger.error(f"Failed to fetch periodic data for Node {node_id}: {response}")

# Schedule the periodic task to run every 30 minutes
scheduler.add_job(
    func=scheduled_periodic_data,
    trigger=IntervalTrigger(minutes=30),
    id='fetch_periodic_data',
    name='Fetch periodic data for all nodes every 30 minutes',
    replace_existing=True
)

if __name__ == "__main__":
    try:
        port = 8000  # Set your desired port here
        app.run(host="0.0.0.0", port=port, debug=True)
    except Exception as e:
        logger.error(f"Failed to start the application: {e}")
