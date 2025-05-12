from flask import Flask, request, jsonify, render_template, send_file
from flask_mail import Mail, Message
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone
import json
from flask_mail import Mail, Message
from datetime import timedelta
import hashlib

load_dotenv()
app = Flask(__name__)

# Load URI from .env
MONGO_URI = os.getenv("MONGODB_URI")

# Initialize MongoDB client
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['air-monitor-final'] if 'air-monitor-final' not in MONGO_URI else client.get_default_database()
collection = db["AirMonitoring_final"]

# OTA update settings
FIRMWARE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firmware')
os.makedirs(FIRMWARE_DIR, exist_ok=True)
FIRMWARE_FILE = os.path.join(FIRMWARE_DIR, 'firmware.bin')
FIRMWARE_VERSION_FILE = os.path.join(FIRMWARE_DIR, 'version.txt')

# For storing device information
device_collection = db["Devices"]

@app.route("/ping-db", methods=["GET"])
def ping_db():
    try:
        client.admin.command('ping')
        return jsonify({"status": "success", "message": "MongoDB connected!"}), 200
    except ServerSelectionTimeoutError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/insert", methods=["POST"])
def insert_data():
    data = request.get_json()
    print(data)
    if not data:
        return jsonify({"error": "No data received"}), 400
    try:
        data["timestamp"] = datetime.now(timezone.utc)
        
        # Store device information if it includes device_id
        if "device_id" in data:
            device_info = {
                "device_id": data["device_id"],
                "ip_address": request.remote_addr,
                "last_seen": datetime.now(timezone.utc),
                "firmware_version": data.get("firmware_version", "unknown")
            }
            device_collection.update_one(
                {"device_id": data["device_id"]},
                {"$set": device_info},
                upsert=True
            )
        
        collection.insert_one(data)
        return jsonify({"message": "Data inserted successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/get-latest", methods=["GET"])
def get_latest():
    try:
        data = collection.find_one(sort=[("timestamp", -1)], projection={"_id": 0})
        if data and "timestamp" in data:
            adjusted_time = data["timestamp"] + timedelta(hours=5)
            data["timestamp"] = adjusted_time.strftime("%Y-%m-%d %H:%M:%S")
            return jsonify(data), 200
        return jsonify({"error": "No data found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get-history", methods=["GET"])
def get_history():
    try:
        # Get last 24 hours of data
        time_threshold = datetime.now() - timedelta(hours=24)
        data = list(collection.find(
            {"timestamp": {"$gte": time_threshold}},
            {"_id": 0}
        ).sort("timestamp", 1))
        
        # Format data for charts
        formatted = {
            "timestamps": [],
            "temperatures": [],
            "humidities": [],
            "air_qualities": []
        }

        for item in data:
            # Adjust for 5-hour difference (or whatever your timezone offset is)
            adjusted_time = item['timestamp'] + timedelta(hours=5)
            
            formatted["timestamps"].append(adjusted_time.strftime('%Y-%m-%d %H:%M:%S'))
            formatted["temperatures"].append(item['temperature'])
            formatted["humidities"].append(item['humidity'])
            formatted["air_qualities"].append(item['air_quality'])
        
        return jsonify(formatted), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# New routes for OTA updates
@app.route("/upload-firmware", methods=["POST"])
def upload_firmware():
    if 'firmware' not in request.files:
        return jsonify({"error": "No firmware file provided"}), 400
    
    firmware_file = request.files['firmware']
    if firmware_file.filename == '':
        return jsonify({"error": "No firmware file selected"}), 400
    
    try:
        # Save the firmware binary
        firmware_file.save(FIRMWARE_FILE)
        
        # Calculate hash for version tracking
        with open(FIRMWARE_FILE, 'rb') as f:
            firmware_hash = hashlib.md5(f.read()).hexdigest()
        
        # Save version information
        version = request.form.get('version', datetime.now().strftime('%Y%m%d%H%M%S'))
        with open(FIRMWARE_VERSION_FILE, 'w') as f:
            f.write(f"{version}:{firmware_hash}")
        
        return jsonify({
            "message": "Firmware uploaded successfully", 
            "version": version,
            "md5": firmware_hash
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/test-connection", methods=["GET"])
def test_connection():
    """Simple endpoint for ESP32 to verify connection to server"""
    client_ip = request.remote_addr
    return jsonify({
        "status": "success",
        "message": "Connection successful",
        "client_ip": client_ip,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route("/get-firmware", methods=["GET"])
def get_firmware():
    try:
        device_id = request.args.get('device_id')
        current_version = request.args.get('version')
        
        if not os.path.exists(FIRMWARE_FILE):
            return jsonify({"message": "No firmware available"}), 404
        
        # Check if firmware exists and needs to be updated
        if os.path.exists(FIRMWARE_VERSION_FILE):
            with open(FIRMWARE_VERSION_FILE, 'r') as f:
                version_info = f.read().strip()
                server_version = version_info.split(':')[0]
                
            # Log the check for update
            if device_id:
                device_collection.update_one(
                    {"device_id": device_id},
                    {"$set": {
                        "last_update_check": datetime.now(timezone.utc),
                        "current_version": current_version
                    }}
                )
                
            # If client specifies version and it matches server, no update needed
            if current_version and current_version == server_version:
                return jsonify({"message": "Firmware up to date"}), 304
                
        # Send the firmware binary
        return send_file(
            FIRMWARE_FILE,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='firmware.bin'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/devices", methods=["GET"])
def list_devices():
    try:
        devices = list(device_collection.find({}, {"_id": 0}))
        for device in devices:
            # Convert datetime objects to strings
            if "last_seen" in device:
                device["last_seen"] = device["last_seen"].strftime("%Y-%m-%d %H:%M:%S")
            if "last_update_check" in device:
                device["last_update_check"] = device["last_update_check"].strftime("%Y-%m-%d %H:%M:%S")
                
        return jsonify({"devices": devices}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/force-update", methods=["POST"])
def force_update():
    data = request.get_json()
    if not data or "device_id" not in data:
        return jsonify({"error": "No device ID provided"}), 400
    
    try:
        device_collection.update_one(
            {"device_id": data["device_id"]},
            {"$set": {"update_forced": True}}
        )
        return jsonify({"message": f"Update forced for device {data['device_id']}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'basit4502929@cloud.neduet.edu.pk'
app.config['MAIL_PASSWORD'] = 'fjvy cxsw gonq sxih'

mail = Mail(app)

def send_all():
    try:
        # Fetch latest document from MongoDB
        latest_data = collection.find_one(sort=[("timestamp", -1)])
        
        if latest_data:
            temperature = latest_data.get('temperature')
            humidity = latest_data.get('humidity')
            air_quality = latest_data.get('air_quality') 
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            msg = Message('🌤️ Latest Weather Station Report',
                          sender='basit4502929@cloud.neduet.edu.pk',
                          recipients=['abdulbasit.shaz@gmail.com'])

            msg.body = f"""
            Here are the latest sensor readings:

            Temperature: {temperature} °C
            Humidity: {humidity} %
            Air Quality Index: {air_quality}
            Current Time: {current_time}

            Stay safe and have a nice day! 🌞
            """
            msg.content_type = "text/plain"

            mail.send(msg)
            return 'Weather Report Email Sent!'
        else:
            return 'No sensor data found in database!', 404
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/admin/ota', methods=['GET'])
def ota_admin():
    return render_template("ota_admin.html")

if __name__ == "__main__":
    with app.app_context():
        send_all()    
    app.run(host="0.0.0.0", port=5000, debug=True)