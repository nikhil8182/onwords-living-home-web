from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from ha_interface import HomeAssistantAPI
from dotenv import load_dotenv
import os.path
import re

# Load environment variables from config.env file
if os.path.exists('config.env'):
    print("Loading configuration from config.env")
    load_dotenv('config.env')
else:
    print("config.env file not found! Using environment variables.")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_testing')

# Initialize Home Assistant API
def get_ha_api():
    try:
        return HomeAssistantAPI()
    except ValueError as e:
        return None

def extract_room_from_entity(entity):
    """Extract room information from an entity"""
    # Try to get room from area_id or entity attributes
    if 'attributes' in entity and 'area_id' in entity['attributes']:
        return entity['attributes']['area_id']
    
    # Try to extract from friendly name
    if 'attributes' in entity and 'friendly_name' in entity['attributes']:
        friendly_name = entity['attributes']['friendly_name']
        # Common room prefixes like "Living Room Light", "Kitchen Switch", etc.
        rooms = ["living room", "bedroom", "kitchen", "bathroom", "hallway", 
                "office", "dining room", "garage", "basement", "attic", "den",
                "foyer", "entry", "guest room", "master bedroom", "laundry"]
        
        for room in rooms:
            if room.lower() in friendly_name.lower():
                return room.title()
    
    # Try to extract from entity_id
    entity_id = entity['entity_id']
    if '.' in entity_id:
        device_id = entity_id.split('.')[1]
        
        # Check for common room patterns in device_id
        room_pattern = re.search(r'(living|bed|kitchen|bath|hall|office|dining|garage|basement|attic|den|foyer|entry|guest|master|laundry)(?:_room|_area)?', device_id)
        if room_pattern:
            return room_pattern.group(0).replace('_', ' ').title()
    
    # Default if no room info found
    return "Other"

@app.route('/')
def index():
    ha_api = get_ha_api()
    
    # Check if HA is configured
    if not ha_api:
        return render_template('setup.html')
    
    try:
        # Get all states from Home Assistant
        states = ha_api.get_states()
        
        # Filter for switches only
        switches = [entity for entity in states if entity['entity_id'].startswith('switch.')]
        
        # Organize switches by room
        rooms = {}
        for switch in switches:
            room = extract_room_from_entity(switch)
            if room not in rooms:
                rooms[room] = []
            rooms[room].append(switch)
        
        return render_template('index.html', rooms=rooms, switches=switches)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/entity/<entity_id>')
def entity_detail(entity_id):
    ha_api = get_ha_api()
    if not ha_api:
        return redirect(url_for('index'))
    
    try:
        state = ha_api.get_state(entity_id)
        return render_template('entity.html', entity=state)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/service', methods=['GET', 'POST'])
def call_service():
    ha_api = get_ha_api()
    if not ha_api:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        domain = request.form.get('domain')
        service = request.form.get('service')
        entity_id = request.form.get('entity_id')
        
        # Create service data with entity_id if provided
        service_data = {}
        if entity_id:
            service_data['entity_id'] = entity_id
        
        try:
            result = ha_api.call_service(domain, service, service_data)
            return jsonify({'success': True, 'result': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    # GET request - show service form
    return render_template('service.html')

@app.route('/toggle/<entity_id>', methods=['POST'])
def toggle_entity(entity_id):
    ha_api = get_ha_api()
    if not ha_api:
        return redirect(url_for('index'))
    
    domain = entity_id.split('.')[0]
    
    # Handle common domains
    if domain == 'light' or domain == 'switch':
        # Get current state
        state = ha_api.get_state(entity_id)
        current_state = state.get('state')
        
        # Determine service to call
        service = 'turn_off' if current_state == 'on' else 'turn_on'
        
        try:
            ha_api.call_service(domain, service, {'entity_id': entity_id})
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'Unsupported entity type'})

if __name__ == '__main__':
    # Use port 5001 instead of default 5000 to avoid conflicts
    app.run(debug=True, port=5001) 