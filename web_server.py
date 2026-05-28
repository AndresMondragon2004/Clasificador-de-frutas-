import asyncio
import json
import threading
import time
from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import service
import argparse

# Global event loop reference for broadcasting from other threads
loop = None

def run_sorter_background(threshold_cm: float):
    """Runs the service sorting loop in a background thread"""
    try:
        service._running = True
        service.sorting_loop(threshold_cm=threshold_cm, on_event=broadcast_event)
    except Exception as e:
        print(f"Error in background sorter loop: {e}")
        broadcast_event("error", {"message": str(e)})

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global loop
    loop = asyncio.get_running_loop()
    
    thread = threading.Thread(target=run_sorter_background, args=(13.0,), daemon=True)
    thread.start()
    
    yield
    
    # Shutdown
    service._running = False
    import camera
    camera.close()
    import arduino
    arduino.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to a client: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

def broadcast_event(event_type: str, data: dict):
    if loop is not None and manager.active_connections:
        message = json.dumps({"type": event_type, "data": data})
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {"message": "Connected to Fruit Sorter Web Server"}
        }))
        while True:
            data = await websocket.receive_text()
            print(f"Received from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def video_generator():
    import camera
    camera.start_camera()
    while service._running:
        frame_bytes = camera.get_latest_frame_jpeg()
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        # Stream a ~15-20 FPS
        time.sleep(0.06)

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

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
    uvicorn.run("web_server:app", host=args.host, port=args.web_port, log_level="info")
