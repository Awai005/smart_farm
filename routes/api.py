from flask import Blueprint, request, jsonify
from models import db, NodeData
from lora_service import send_threshold, get_node_data, cleanup, send_pump_status, get_pump_status, get_tank_threshold

api_bp = Blueprint('api', __name__)

# POST route to receive data for a specific node
@api_bp.route('/send-data', methods=['POST'])
def receive_data():
    data = request.get_json()
    if not data or not all(k in data for k in ('node_id', 'soil_moisture', 'temperature', 'humidity')):
        return jsonify({"error": "Invalid data format"}), 400

    node_id = data['node_id']
    soil_moisture = data['soil_moisture']
    temperature = data['temperature']
    humidity = data['humidity']

    # Save the received data to the database
    new_entry = NodeData(node_id=node_id, soil_moisture=soil_moisture, temperature=temperature, humidity=humidity)
    db.session.add(new_entry)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Data saved successfully for node {node_id}"
    }), 201


# GET route to fetch data for a specific node from the database
@api_bp.route('/get-data/<node_id>', methods=['GET'])
def get_data(node_id):
    # Fetch the latest 5 data points for the specified node
    data = NodeData.query.filter_by(node_id=node_id).order_by(NodeData.timestamp.desc()).limit(5).all()

    if not data:
        return jsonify({"error": f"No data found for node {node_id}"}), 404

    # Serialize the data
    result = [
        {
            "id": d.id,
            "node_id": d.node_id,
            "soil_moisture": d.soil_moisture,
            "temperature": d.temperature,
            "humidity": d.humidity,
            "timestamp": d.timestamp
        } for d in data
    ]

    return jsonify({
        "status": "success",
        "node_id": node_id,
        "data": result
    }), 200


# POST route to set a threshold for a specific node
@api_bp.route('/set-threshold', methods=['POST'])
def set_threshold():
    data = request.get_json()

    if not data or not all(k in data for k in ('node_id', 'threshold_moisture')):
        return jsonify({"error": "Invalid data format"}), 400

    node_id = data['node_id']
    threshold_moisture = data['threshold_moisture']

    try:
        # Send the threshold to the node using LoRa
        send_threshold(node_id, threshold_moisture)
        return jsonify({
            "status": "success",
            "message": f"Threshold {threshold_moisture} set for Node {node_id}"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to set threshold for Node {node_id}: {str(e)}"
        }), 500
# POST route to fetch real-time data from nodes and save it to the database
@api_bp.route('/get-data-from-nodes', methods=['POST'])
def get_data_from_nodes():
    try:
        fetched_data = []
        for node_id in [1, 2]:  # Add more nodes if needed
            data = get_node_data(node_id)  # Fetch real-time data from the node
            if data:
                try:
                    parts = data.split("|")[1].strip()
                    values = {kv.split(":")[0]: float(kv.split(":")[1]) for kv in parts.split(", ")}

                    soil_moisture = values['M']
                    humidity = values['H']
                    temperature = values['T']

                    new_entry = NodeData(
                        node_id=f"node{node_id}",
                        soil_moisture=soil_moisture,
                        temperature=temperature,
                        humidity=humidity
                    )
                    db.session.add(new_entry)
                    db.session.commit()

                    fetched_data.append({
                        "node_id": f"node{node_id}",
                        "soil_moisture": soil_moisture,
                        "humidity": humidity,
                        "temperature": temperature
                    })
                except (KeyError, ValueError) as e:
                    return jsonify({
                        "status": "error",
                        "message": f"Failed to parse data from Node {node_id}: {data}, Error: {str(e)}"
                    }), 400
            else:
                fetched_data.append({
                    "node_id": f"node{node_id}",
                    "message": "No response from node"
                })

        return jsonify({
            "status": "success",
            "data": fetched_data
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# GET route to fetch pump status for a specific node
@api_bp.route('/get-pump-status/<node_id>', methods=['GET'])
def get_pump_status_route(node_id):
    try:
        pump_status = get_pump_status(node_id)
        return jsonify({
            "status": "success",
            "node_id": node_id,
            "isPumpOn": pump_status
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# POST route to toggle pump status for a specific node
@api_bp.route('/toggle-pump-status', methods=['POST'])
def toggle_pump_status():
    data = request.get_json()
    if not data or not all(k in data for k in ('node_id', 'status')):
        return jsonify({"error": "Invalid data format"}), 400

    node_id = data['node_id']
    status = data['status']

    try:
        send_pump_status(node_id, status)
        return jsonify({
            "status": "success",
            "message": f"Pump for Node {node_id} turned {'On' if status else 'Off'}"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# GET route to fetch water level threshold for the tank node
@api_bp.route('/get-tank-threshold', methods=['GET'])
def get_tank_threshold_route():
    try:
        threshold = get_tank_threshold()
        return jsonify({
            "status": "success",
            "threshold": threshold
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
