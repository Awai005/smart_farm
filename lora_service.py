import serial
import time
import os

# Try importing RPi.GPIO for Raspberry Pi; fallback for other environments
try:
    import RPi.GPIO as GPIO
    IS_RASPBERRY_PI = True
except ImportError:
    IS_RASPBERRY_PI = False
    print("RPi.GPIO not available. Running in non-Raspberry Pi mode.")

# Pin Definitions for Mode Selection (Raspberry Pi only)
M0_PIN = 31  # GPIO23 for M0
M1_PIN = 29  # GPIO24 for M1

if IS_RASPBERRY_PI:
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(M0_PIN, GPIO.OUT)
    GPIO.setup(M1_PIN, GPIO.OUT)

    # Set to Normal Mode (M0 = LOW, M1 = LOW)
    GPIO.output(M0_PIN, GPIO.LOW)
    GPIO.output(M1_PIN, GPIO.LOW)

# Initialize UART communication
try:
    ser = serial.Serial(
        port='/dev/serial0',
        baudrate=9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
    )
except Exception as e:
    print(f"Serial communication initialization failed: {e}")
    ser = None

def send_message(message):
    """Send a message via LoRa"""
    if ser:
        try:
            ser.write((message + '\n').encode())
            print(f"Sent: {message}")
        except Exception as e:
            print(f"Error sending message: {e}")
    else:
        print(f"Mock Send: {message}")

def receive_message():
    """Receive messages via LoRa"""
    if ser:
        try:
            if ser.in_waiting > 0:
                incoming_data = ser.readline().decode('utf-8').strip()
                print(f"Received: {incoming_data}")
                return incoming_data
        except Exception as e:
            print(f"Error receiving message: {e}")
    else:
        print("Mock Receive: No message received (non-Raspberry Pi mode).")
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
    
    print(f"Mock Response: No data received for Node {node_id}.")
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
            try:
                status = data.split(":")[1].strip()
                return status == "ON"
            except IndexError:
                print(f"Error parsing pump status for Node {node_id}: {data}")
    
    print(f"Mock Response: Pump status for Node {node_id} is OFF.")
    return None

def get_tank_threshold():
    """Request water level threshold from the tank node and wait for the response"""
    message = "REQUEST_TANK_THRESHOLD"
    send_message(message)
    start_time = time.time()
    
    while time.time() - start_time < 10:  # Wait for up to 10 seconds
        data = receive_message()
        if data and "TANK_THRESHOLD" in data:
            try:
                threshold = float(data.split(":")[1].strip())
                return threshold
            except (IndexError, ValueError):
                print(f"Error parsing tank threshold: {data}")
    
    print("Mock Response: Tank threshold is 0.0.")
    return 0.0

def cleanup():
    """Clean up GPIO and close serial connection"""
    if IS_RASPBERRY_PI:
        GPIO.cleanup()
    if ser:
        ser.close()
