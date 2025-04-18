# Module for interacting with Home Assistant API and WebSocket 

import os
import json
import asyncio
import requests
import websockets

class HomeAssistantAPI:
    def __init__(self, url=None, token=None):
        # Use environment variables if not provided
        self.base_url = url or os.environ.get('HA_URL', 'http://localhost:8123')
        self.token = token or os.environ.get('HA_TOKEN')
        
        if not self.token:
            raise ValueError("Home Assistant token is required. Set HA_TOKEN environment variable or pass token to constructor.")
            
        # Remove trailing slash if present
        self.base_url = self.base_url.rstrip('/')
        
        # Prepare headers for API requests
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
    
    def get_states(self):
        """Get all entity states from Home Assistant"""
        response = requests.get(f"{self.base_url}/api/states", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_state(self, entity_id):
        """Get state of a specific entity"""
        response = requests.get(f"{self.base_url}/api/states/{entity_id}", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def call_service(self, domain, service, service_data=None):
        """Call a Home Assistant service"""
        url = f"{self.base_url}/api/services/{domain}/{service}"
        response = requests.post(url, headers=self.headers, json=service_data or {})
        response.raise_for_status()
        return response.json()


class WebSocketClient:
    def __init__(self, url=None, token=None):
        # Use environment variables if not provided
        self.base_url = url or os.environ.get('HA_URL', 'http://localhost:8123')
        self.token = token or os.environ.get('HA_TOKEN')
        
        if not self.token:
            raise ValueError("Home Assistant token is required")
            
        # Convert HTTP URL to WebSocket URL if needed
        if self.base_url.startswith('http://'):
            self.ws_url = self.base_url.replace('http://', 'ws://')
        elif self.base_url.startswith('https://'):
            self.ws_url = self.base_url.replace('https://', 'wss://')
        else:
            self.ws_url = self.base_url
            
        self.ws_url = f"{self.ws_url.rstrip('/')}/api/websocket"
        self.id_counter = 0
    
    def _get_id(self):
        """Get a unique ID for WebSocket messages"""
        self.id_counter += 1
        return self.id_counter
    
    async def connect(self):
        """Connect to Home Assistant WebSocket API"""
        self.connection = await websockets.connect(self.ws_url)
        
        # Wait for auth required message
        auth_message = await self.connection.recv()
        auth_message = json.loads(auth_message)
        
        if auth_message['type'] == 'auth_required':
            # Send authentication
            await self.connection.send(json.dumps({
                'type': 'auth',
                'access_token': self.token
            }))
            
            # Wait for auth_ok message
            auth_result = await self.connection.recv()
            auth_result = json.loads(auth_result)
            
            if auth_result['type'] != 'auth_ok':
                raise ConnectionError(f"Authentication failed: {auth_result}")
        
        return self.connection
    
    async def subscribe_to_events(self, event_type=None):
        """Subscribe to Home Assistant events"""
        msg_id = self._get_id()
        message = {
            'id': msg_id,
            'type': 'subscribe_events',
        }
        
        if event_type:
            message['event_type'] = event_type
            
        await self.connection.send(json.dumps(message))
        result = await self.connection.recv()
        return json.loads(result)
    
    async def close(self):
        """Close the WebSocket connection"""
        if hasattr(self, 'connection'):
            await self.connection.close() 