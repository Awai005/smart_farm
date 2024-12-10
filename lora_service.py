from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
import serial
import time
import sqlite3
import RPi.GPIO as GPIO

# Pin Definitions for Mode Selection
M0_PIN = 31  # GPIO23 for M0
M1_PIN = 29  # GPIO24 for M1

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(M0_PIN, GPIO.OUT)
GPIO.setup(M1_PIN, GPIO.OUT)

# Set to Normal Mode (M0 = LOW, M1 = LOW)
GPIO.output(M0_PIN, GPIO.LOW)
GPIO.output(M1_PIN, GPIO.LOW)

# Initialize UART communication
ser = serial.Serial(
    port='/dev/serial0',
    baudrate=9600,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database setup
DB_NAME = "node_data.db"

def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS node_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER NOT NULL,
            moisture INTEGER,
            humidity REAL,
            temperature REAL,
            pump_status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_node_data(node_id, moisture, humidity, temperature, pump_status):
    """Save node data to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO node_data (node_id, moisture, humidity, temperature, pump_status)
        VALUES (?, ?, ?, ?, ?)
    """, (node_id, moisture, humidity, temperature, pump_status))
    conn.commit()
    conn.close()

def get_all_data():
    """Retrieve all node data from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM node_data ORDER BY timestamp DESC")
    data = cursor.fetchall()
    conn.close()
    return data

def send_message(message):
    """Send a message via LoRa."""
    try:
        ser.write((message + '\n').encode())
        print(f"Sent: {message}")
    except Exception as e:
        print(f"Error sending message: {e}")

def receive_message(timeout=10):
    """Receive messages via LoRa with a timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if ser.in_waiting > 0:
                incoming_data = ser.readline().decode('utf-8').strip()
                if incoming_data:
                    print(f"Received: {incoming_data}")
                    return incoming_data
        except Exception as e:
            print(f"Error receiving message: {e}")
    return None

def parse_node_data(response):
    """Parse node data from the received response."""
    try:
        # Split the response into parts based on '|' separator
        parts = response.split("|")
        if len(parts) != 2:
            raise ValueError("Incorrect number of '|' delimiters.")

        # Extract and parse node_id
        node_id_part = parts[0].strip()
        node_id_str = node_id_part.split(" ")[1].strip()
        node_id = int(node_id_str)
        print(f"Parsed Node ID: {node_id}")

        # Extract and parse the sensor data
        sensor_data = parts[1].split(",")
        if len(sensor_data) != 4:
            raise ValueError("Incorrect number of sensor data segments.")

        moisture_str = sensor_data[0].split(":")[1].strip()
        moisture = int(moisture_str)
        print(f"Parsed Moisture: {moisture}")

        humidity_str = sensor_data[1].split(":")[1].strip()
        humidity = float(humidity_str)
        print(f"Parsed Humidity: {humidity}")

        temperature_str = sensor_data[2].split(":")[1].strip()
        temperature = float(temperature_str)
        print(f"Parsed Temperature: {temperature}")

        pump_status_str = sensor_data[3].split(":")[1].strip()
        if pump_status_str not in ["ON", "OFF"]:
            raise ValueError("Invalid pump status value.")
        pump_status = pump_status_str
        print(f"Parsed Pump Status: {pump_status}")

        return node_id, moisture, humidity, temperature, pump_status
    except (IndexError, ValueError) as e:
        # Log error if parsing fails
        print(f"Error parsing node data: {e}")
        print(f"Received Response: '{response}'")
        return None

def request_data(command, node_id):
    """Send a command to a node and wait for its response."""
    message = f"{command}_NODE_{node_id}"
    send_message(message)
    response = receive_message()
    if response:
        data = parse_node_data(response)
        if data:
            # Save the parsed data to the database
            save_node_data(*data)
            return response
    return None

def set_command(node_id, command, value):
    """Send a command with a value to a specific node."""
    message = f"{command}_NODE_{node_id}:{value}"
    send_message(message)
    return receive_message()

@app.route('/periodic_data/<int:node_id>', methods=['GET'])
def periodic_data(node_id):
    """Fetch data from the node and save it to the database."""
    response = request_data("REQUEST", node_id)
    if response:
        data = parse_node_data(response)
        if data:
            # Data has already been saved in request_data
            return jsonify({
                "status": "success",
                "message": "Data fetched and saved to the database",
                "data": {
                    "node_id": data[0],
                    "moisture": data[1],
                    "humidity": data[2],
                    "temperature": data[3],
                    "pump_status": data[4]
                }
            }), 200
        else:
            return jsonify({"status": "error", "message": "Failed to parse node data"}), 500
    else:
        return jsonify({"status": "error", "message": "No response from node"}), 500

@app.route('/node_data/<int:node_id>', methods=['GET'])
def get_node_data_route(node_id):
    """Get the 5 most recent data entries for a specific node from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, node_id, moisture, humidity, temperature, pump_status, timestamp
        FROM node_data
        WHERE node_id = ?
        ORDER BY timestamp DESC
        LIMIT 5
    """, (node_id,))
    rows = cursor.fetchall()
    conn.close()

    if rows:
        data = [
            {
                "id": row[0],
                "node_id": row[1],
                "moisture": row[2],
                "humidity": row[3],
                "temperature": row[4],
                "pump_status": row[5],
                "timestamp": row[6]
            }
            for row in rows
        ]
        return jsonify({"status": "success", "data": data}), 200
    else:
        return jsonify({"status": "error", "message": f"No data found for node_id {node_id}"}), 404

@app.route('/set_threshold/<int:node_id>', methods=['POST'])
def set_threshold(node_id):
    """Set threshold for a specific node."""
    data = request.get_json()
    if not data or "threshold" not in data:
        return jsonify({"status": "error", "message": "Missing 'threshold' parameter"}), 400

    threshold = data["threshold"]
    try:
        threshold = int(threshold)
    except ValueError:
        return jsonify({"status": "error", "message": "'threshold' must be an integer"}), 400

    response = set_command(node_id, "THRESHOLD", threshold)
    if response:
        return jsonify({"status": "success", "message": "Threshold updated", "response": response}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to update threshold"}), 500

@app.route('/all_node_data', methods=['GET'])
def get_all_node_data_route():
    """Retrieve all node data from the database."""
    data = get_all_data()
    formatted_data = [
        {
            "id": row[0],
            "node_id": row[1],
            "moisture": row[2],
            "humidity": row[3],
            "temperature": row[4],
            "pump_status": row[5],
            "timestamp": row[6]
        }
        for row in data
    ]
    return jsonify({"status": "success", "data": formatted_data}), 200

def cleanup():
    """Clean up GPIO and close serial connection."""
    print("Cleaning up GPIO and closing serial connection...")
    ser.close()
    GPIO.cleanup()

if __name__ == "__main__":
    try:
        print("Initializing database...")
        init_db()
        print("Starting Flask app...")
        app.run(host="0.0.0.0", port=5000)  # Expose API on Raspberry Pi
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Cleaning up...")
        cleanup()
    except Exception as e:
        print(f"An error occurred: {e}")
        cleanup()
