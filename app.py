from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_cors import CORS
from config import Config
from models import db, NodeData
from routes.api import api_bp
from lora_service import get_node_data, get_pump_status, get_tank_threshold
import math
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize SQLAlchemy
db.init_app(app)

# Register API Blueprint
app.register_blueprint(api_bp, url_prefix='/api')

# Create database tables
with app.app_context():
    db.create_all()

# Scheduler configuration
class ConfigWithScheduler(Config):
    SCHEDULER_API_ENABLED = True


app.config.from_object(ConfigWithScheduler)
scheduler = APScheduler()
scheduler.init_app(app)

# Task to fetch data from nodes, parse it, and save to the database
def fetch_node_data():
    logging.info("Fetching data from nodes...")
    for node_id in [1, 2]:  # Add more node IDs if needed
        raw_data = get_node_data(node_id)
        if raw_data:
            logging.info(f"Raw data from Node {node_id}: {raw_data}")
            try:
                # Parse data in the format: "Node <NODE_ID> | M:<moisture>, H:<humidity>, T:<temperature>"
                parts = raw_data.split("|")[1].strip()  # Extract "M:<value>, H:<value>, T:<value>"
                values = {kv.split(":")[0]: float(kv.split(":")[1]) for kv in parts.split(", ")}

                # Extract parsed values
                soil_moisture = values['M']
                humidity = values['H']
                temperature = values['T']

                # Set default values for NaN
                humidity = 0.0 if math.isnan(humidity) else humidity
                temperature = 0.0 if math.isnan(temperature) else temperature

                # Save to database
                with app.app_context():
                    new_entry = NodeData(
                        node_id=f"node{node_id}",
                        soil_moisture=soil_moisture,
                        temperature=temperature,
                        humidity=humidity
                    )
                    db.session.add(new_entry)
                    db.session.commit()

                logging.info(f"Data saved for Node {node_id}: M={soil_moisture}, H={humidity}, T={temperature}")

            except (KeyError, ValueError) as e:
                logging.error(f"Failed to parse data from Node {node_id}: {raw_data}, Error: {str(e)}")
        else:
            logging.warning(f"No response from Node {node_id}.")
# Task to log pump statuses
def log_pump_status():
    logging.info("Fetching pump statuses...")
    for node_id in [1, 2]:  # Add more node IDs if needed
        status = get_pump_status(node_id)
        if status is not None:
            logging.info(f"Pump status for Node {node_id}: {'ON' if status else 'OFF'}")
        else:
            logging.warning(f"No response for pump status from Node {node_id}.")

# Task to log tank water level threshold
def log_tank_threshold():
    logging.info("Fetching tank water level threshold...")
    threshold = get_tank_threshold()
    if threshold is not None:
        logging.info(f"Tank water level threshold: {threshold} liters")
    else:
        logging.warning("No response from tank node.")

# Add scheduled tasks
scheduler.add_job(
    id="fetch_node_data",  # Unique job ID
    func=fetch_node_data,  # Function to call
    trigger="interval",  # Trigger type
    minutes=1  # Run every 1 minute
)
scheduler.add_job(
    id="log_pump_status",  # Unique job ID
    func=log_pump_status,  # Function to call
    trigger="interval",  # Trigger type
    minutes=2  # Run every 2 minutes
)
scheduler.add_job(
    id="log_tank_threshold",  # Unique job ID
    func=log_tank_threshold,  # Function to call
    trigger="interval",  # Trigger type
    minutes=5  # Run every 5 minutes
)

# Start the scheduler
scheduler.start()

if __name__ == '__main__':
    try:
        # Get the port number from the environment (default to 5000 for local development)
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)  # Accessible over the network
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
