import { useState } from 'react';

function App() {
  const [status, setStatus] = useState('');

  const startNewsletterRun = async () => {
    const response = await fetch('/api/actions/run-newsletter-pipeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_date: '2024-01-01',
        end_date: '2024-01-07',
        email_recipients: [],
        research_interests: 'AI',
        generate_podcast_run: false,
      })
    });
    const data = await response.json();
    setStatus('Task started: ' + data.task_id);
    listenForUpdates(data.task_id);
  };

  const listenForUpdates = (taskId) => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/newsletter/${taskId}`);
    socket.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setStatus(update.message);
    };
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Theseus Insight React UI</h1>
      <button onClick={startNewsletterRun}>Start Newsletter Run</button>
      <p>{status}</p>
    </div>
  );
}

export default App;
