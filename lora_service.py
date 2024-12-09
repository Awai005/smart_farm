import serial
import time
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

def send_message(message):
    """Send a message via LoRa"""
    try:
        ser.write((message + '\n').encode())
        print(f"Sent: {message}")
    except Exception as e:
        print(f"Error sending message: {e}")

def receive_message():
    """Receive messages via LoRa"""
    try:
        if ser.in_waiting > 0:
            incoming_data = ser.readline().decode('utf-8').strip()
            print(f"Received: {incoming_data}")
            return incoming_data
    except Exception as e:
        print(f"Error receiving message: {e}")
    return None

def send_threshold(node_id, threshold):
    """Send threshold value to a specific node"""
    message = f"THRESHOLD_NODE_{node_id}:{threshold}"
    send_message(message)

def get_node_data(node_id):
    """Request data from a specific node and wait for the response"""
    message = f"REQUEST_NODE_{node_id}"
    send_message(message)
    start_time = time.time()
    
    while time.time() - start_time < 10:  # Wait for up to 10 seconds
        data = receive_message()
        if data:
            return data
    
    return None

def send_pump_status(node_id, status):
    """Send pump status to a specific node"""
    status_str = "ON" if status else "OFF"
    message = f"PUMP_NODE_{node_id}:{status_str}"
    send_message(message)

def get_pump_status(node_id):
    """Request pump status from a specific node and wait for the response"""
    message = f"REQUEST_PUMP_NODE_{node_id}"
    send_message(message)
    start_time = time.time()
    
    while time.time() - start_time < 10:  # Wait for up to 10 seconds
        data = receive_message()
        if data and f"PUMP_STATUS_NODE_{node_id}" in data:
            # Expected format: "PUMP_STATUS_NODE_<node_id>:<ON/OFF>"
            try:
                status = data.split(":")[1].strip()
                return status == "ON"
            except IndexError:
                print(f"Error parsing pump status for Node {node_id}: {data}")
    
    return None

def get_tank_threshold():
    """Request water level threshold from the tank node and wait for the response"""
    message = "REQUEST_TANK_THRESHOLD"
    send_message(message)
    start_time = time.time()
    
    while time.time() - start_time < 10:  # Wait for up to 10 seconds
        data = receive_message()
        if data and "TANK_THRESHOLD" in data:
            # Expected format: "TANK_THRESHOLD:<value>"
            try:
                threshold = float(data.split(":")[1].strip())
                return threshold
            except (IndexError, ValueError):
                print(f"Error parsing tank threshold: {data}")
    
    return None

def cleanup():
    """Clean up GPIO and close serial connection"""
    ser.close()
    GPIO.cleanup()
