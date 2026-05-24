import asyncio
import json
import threading
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import service
import argparse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to a client: {e}")

manager = ConnectionManager()

# Global event loop reference for broadcasting from other threads
loop = None

def broadcast_event(event_type: str, data: dict):
    """Callback function called by service.py"""
    if loop is not None and manager.active_connections:
        message = json.dumps({"type": event_type, "data": data})
        # Schedule the broadcast safely in the asyncio event loop
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {"message": "Connected to Fruit Sorter Web Server"}
        }))
        while True:
            # Keep connection open
            data = await websocket.receive_text()
            print(f"Received from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def run_sorter_background(threshold_cm: float):
    """Runs the service sorting loop in a background thread"""
    try:
        service._running = True
        service.sorting_loop(threshold_cm=threshold_cm, on_event=broadcast_event)
    except Exception as e:
        print(f"Error in background sorter loop: {e}")
        broadcast_event("error", {"message": str(e)})

@app.on_event("startup")
async def startup_event():
    global loop
    loop = asyncio.get_running_loop()
    
    # Start the hardware loop in a thread
    thread = threading.Thread(target=run_sorter_background, args=(13.0,), daemon=True)
    thread.start()

@app.on_event("shutdown")
async def shutdown_event():
    service._running = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=str, help="Serial port")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--threshold", type=float, default=13.0, help="Sensor threshold in cm")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web server host")
    parser.add_argument("--web-port", type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    import arduino
    import camera

    if args.port: 
        arduino.SERIAL_PORT = args.port
    camera.CAMERA_INDEX = args.camera

    print("Iniciando servidor web en http://{}:{}".format(args.host, args.web_port))
    uvicorn.run(app, host=args.host, port=args.web_port)
