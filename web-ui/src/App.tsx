import { useState, useEffect, useRef } from 'react'
import './index.css'

type AppState = 'IDLE' | 'WAITING' | 'DETECTED' | 'CAPTURING' | 'ANALYZING' | 'SUCCESS' | 'DISCARDED';

interface HistoryItem {
  id: number;
  time: string;
  type: 'APPLE' | 'ORANGE' | 'DISCARD';
  message: string;
}

function App() {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [message, setMessage] = useState('Iniciando sistema...');
  const [imageB64, setImageB64] = useState<string | null>(null);
  
  const [stats, setStats] = useState({
    apples: 0,
    oranges: 0,
    total: 0
  });
  
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to backend WebSocket
    const connectWs = () => {
      ws.current = new WebSocket('ws://127.0.0.1:8000/ws');
      
      ws.current.onopen = () => {
        console.log("WS Connected");
        setMessage("Conectado al servidor. Esperando inicio...");
      };

      ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const type = data.type;
        const payload = data.data;

        const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        switch (type) {
          case 'system_status':
            setMessage(payload.message);
            break;
          case 'waiting_fruit':
            setAppState('WAITING');
            setMessage('Esperando fruta en el sensor...');
            break;
          case 'fruit_detected':
            setAppState('DETECTED');
            setMessage(`¡Fruta detectada a ${payload.distance}cm!`);
            break;
          case 'capturing_image':
            setAppState('CAPTURING');
            setMessage('Capturando imagen...');
            break;
          case 'analyzing_image':
            setAppState('ANALYZING');
            setMessage('IA analizando la imagen...');
            if (payload.image_b64) {
              setImageB64(`data:image/jpeg;base64,${payload.image_b64}`);
            }
            break;
          case 'sorted_success':
            setAppState('SUCCESS');
            // Payload status is like "SUCCESS:apple:LEFT"
            const parts = payload.status.split(':');
            const fruitName = parts.length > 1 ? parts[1].toLowerCase() : 'unknown';
            const isApple = fruitName === 'apple' || fruitName === 'manzana';
            
            setMessage(`¡Clasificado con éxito! Movido a la ${parts[2] || 'banda'}`);
            
            setStats(prev => ({
              ...prev,
              total: prev.total + 1,
              apples: isApple ? prev.apples + 1 : prev.apples,
              oranges: !isApple ? prev.oranges + 1 : prev.oranges
            }));

            setHistory(prev => [{
              id: Date.now(),
              time: timeNow,
              type: isApple ? 'APPLE' : 'ORANGE',
              message: isApple ? 'Manzana detectada' : 'Naranja detectada'
            }, ...prev].slice(0, 5));
            break;
          case 'sorted_discarded':
            setAppState('DISCARDED');
            const reason = payload.status.split(':')[1] || 'No reconocido';
            setMessage(`Descartado: ${reason}`);
            
            setHistory(prev => [{
              id: Date.now(),
              time: timeNow,
              type: 'DISCARD',
              message: reason
            }, ...prev].slice(0, 5));
            break;
          case 'error':
            setMessage(`Error: ${payload.message}`);
            break;
        }
      };

      ws.current.onclose = () => {
        setMessage("Desconectado. Reintentando...");
        setTimeout(connectWs, 3000);
      };
    };

    connectWs();
    return () => {
      ws.current?.close();
    };
  }, []);

  const getStatusColor = () => {
    if (appState === 'WAITING') return 'status-wait';
    if (appState === 'SUCCESS') return 'status-success';
    if (appState === 'ANALYZING') return 'status-analyzing';
    if (appState === 'DISCARDED') return 'status-wait'; // red glow maybe
    return 'status-wait';
  };

  const getStatusIcon = () => {
    if (appState === 'WAITING') return '⏳';
    if (appState === 'DETECTED') return '📦';
    if (appState === 'CAPTURING') return '📷';
    if (appState === 'ANALYZING') return '🧠';
    if (appState === 'SUCCESS') return '✅';
    if (appState === 'DISCARDED') return '⚠️';
    return '🔄';
  };

  return (
    <>
      <div>
        <h1>Fruit Sorter <span style={{ color: 'var(--wait-color)' }}>Pro</span></h1>
        <p className="subtitle">Agentic Classification System V4+</p>
      </div>

      <div className="dashboard-grid">
        {/* Main Feed */}
        <div className="glass-panel">
          <div className="camera-container">
            {appState === 'ANALYZING' && <div className="scanning-line"></div>}
            
            {imageB64 ? (
              <img src={imageB64} alt="Camera Feed" className="camera-feed" />
            ) : (
              <div className="camera-placeholder">
                <div className="pulsing-dot"></div>
                <span>Esperando cámara...</span>
              </div>
            )}
          </div>

          <div className="status-banner">
            <div>
              <div className="status-label">Estado Actual</div>
              <div className={`status-value ${getStatusColor()}`}>
                {getStatusIcon()} {appState}
              </div>
            </div>
            <div style={{ textAlign: 'right', maxWidth: '50%' }}>
              <div className="status-label">Mensaje</div>
              <div style={{ fontSize: '1.1rem', color: 'var(--text-main)', opacity: 0.9 }}>
                {message}
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar Stats */}
        <div className="sidebar">
          <div className="glass-panel" style={{ marginBottom: '2rem' }}>
            <div className="stats-header">
              📊 Estadísticas Globales
            </div>
            
            <div className="stat-box">
              <div className="stat-details">
                <h3>Total Manzanas</h3>
                <p className="apple-count">{stats.apples}</p>
              </div>
              <div className="stat-icon-apple">🍎</div>
            </div>

            <div className="stat-box">
              <div className="stat-details">
                <h3>Total Naranjas</h3>
                <p className="orange-count">{stats.oranges}</p>
              </div>
              <div className="stat-icon-orange">🍊</div>
            </div>
          </div>

          <div className="glass-panel">
            <div className="stats-header">
              📋 Últimas Clasificaciones
            </div>
            <div className="history-list">
              {history.length === 0 && (
                <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
                  Sin actividad reciente
                </div>
              )}
              {history.map(item => (
                <div key={item.id} className="history-item">
                  <div style={{ fontSize: '1.5rem' }}>
                    {item.type === 'APPLE' ? '🍎' : item.type === 'ORANGE' ? '🍊' : '⚠️'}
                  </div>
                  <div className="history-fruit">
                    <span style={{ 
                      color: item.type === 'APPLE' ? 'var(--apple-color)' : 
                             item.type === 'ORANGE' ? 'var(--orange-color)' : 'var(--text-muted)' 
                    }}>
                      {item.message}
                    </span>
                  </div>
                  <div className="history-time">{item.time}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default App
