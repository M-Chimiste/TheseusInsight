import { useState, useEffect } from 'react';
import ModelCard from './components/ModelCard.jsx';
import './styles.css';

export default function Settings() {
  const [theme, setTheme] = useState('Light');
  const [providers, setProviders] = useState([]);
  const [orchestration, setOrchestration] = useState(null);
  const [arxiv, setArxiv] = useState({ main_category: 'cs', filter_categories: [] });
  const [researchInterests, setResearchInterests] = useState('');
  const [emailRecipients, setEmailRecipients] = useState('');

  useEffect(() => {
    document.body.classList.toggle('theme-dark', theme === 'Dark');
    document.body.classList.toggle('theme-light', theme === 'Light');
  }, [theme]);

  useEffect(() => {
    async function load() {
      try {
        const orch = await (await fetch('/api/settings/orchestration')).json();
        setOrchestration(orch);
        const providersData = await (await fetch('/api/model-providers')).json();
        setProviders(providersData.map(p => p.name));
        const arxivData = await (await fetch('/api/settings/arxiv-categories')).json();
        setArxiv(arxivData);
        const interests = await (await fetch('/api/settings/research-interests')).json();
        setResearchInterests(interests.interests || '');
        const recipients = await (await fetch('/api/settings/email-recipients')).json();
        setEmailRecipients((recipients.recipients || []).join('\n'));
      } catch (e) {
        console.error('Failed to load settings', e);
      }
    }
    load();
  }, []);

  if (!orchestration) return <p>Loading...</p>;

  const updateModel = (key, value) => {
    setOrchestration(prev => ({ ...prev, [key]: value }));
  };

  const saveOrchestration = async () => {
    await fetch('/api/settings/orchestration', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orchestration)
    });
  };

  const saveArxiv = async () => {
    await fetch('/api/settings/arxiv-categories', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(arxiv)
    });
  };

  const saveInterests = async () => {
    await fetch('/api/settings/research-interests', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interests: researchInterests })
    });
  };

  const saveRecipients = async () => {
    const list = emailRecipients.split(/\n|,/).map(e => e.trim()).filter(Boolean);
    await fetch('/api/settings/email-recipients', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipients: list })
    });
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h1>Settings</h1>
      <div className="card">
        <label>
          <input type="checkbox" checked={theme === 'Dark'} onChange={e => setTheme(e.target.checked ? 'Dark' : 'Light')} />
          Dark Mode
        </label>
      </div>

      <details open>
        <summary>Newsletter Model Settings</summary>
        {['embedding_model','judge_model','content_extraction_model','newsletter_sections_model','newsletter_intro_model'].map(key => (
          <ModelCard
            key={key}
            title={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            config={orchestration[key]}
            providers={providers}
            onChange={val => updateModel(key, val)}
          />
        ))}
        <button onClick={saveOrchestration}>Save Model Settings</button>
      </details>

      <details>
        <summary>Data Source Settings</summary>
        <div className="card">
          <label>Main Category
            <input value={arxiv.main_category} onChange={e => setArxiv({ ...arxiv, main_category: e.target.value })} />
          </label>
          <label>Filter Categories
            <input value={arxiv.filter_categories.join(',')} onChange={e => setArxiv({ ...arxiv, filter_categories: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
          </label>
          <button onClick={saveArxiv}>Save ArXiv Settings</button>
        </div>
      </details>

      <details>
        <summary>Research Interests</summary>
        <div className="card">
          <textarea rows="6" value={researchInterests} onChange={e => setResearchInterests(e.target.value)} />
          <button onClick={saveInterests}>Save Research Interests</button>
        </div>
      </details>

      <details>
        <summary>Email Recipients</summary>
        <div className="card">
          <textarea rows="4" value={emailRecipients} onChange={e => setEmailRecipients(e.target.value)} />
          <button onClick={saveRecipients}>Save Email Recipients</button>
        </div>
      </details>

      <details>
        <summary>Podcast Model Settings</summary>
        <ModelCard
          title="Podcast Model"
          config={orchestration.podcast_model}
          providers={providers}
          onChange={val => updateModel('podcast_model', val)}
        />
        <button onClick={saveOrchestration}>Save Podcast Model</button>
      </details>

      <details>
        <summary>TTS Model Settings</summary>
        <div className="card">
          <label>TTS Provider
            <input value={orchestration.tts_model.tts_provider} onChange={e => updateModel('tts_model', { ...orchestration.tts_model, tts_provider: e.target.value })} />
          </label>
          <label>Model Name
            <input value={orchestration.tts_model.tts_model_name} onChange={e => updateModel('tts_model', { ...orchestration.tts_model, tts_model_name: e.target.value })} />
          </label>
          <label>Speaker 1 Voice
            <input value={orchestration.tts_model.speaker_1_voice} onChange={e => updateModel('tts_model', { ...orchestration.tts_model, speaker_1_voice: e.target.value })} />
          </label>
          <label>Speaker 1 Speed
            <input type="number" step="0.05" value={orchestration.tts_model.speaker_1_speed} onChange={e => updateModel('tts_model', { ...orchestration.tts_model, speaker_1_speed: parseFloat(e.target.value) })} />
          </label>
          <label>Speaker 2 Voice
            <input value={orchestration.tts_model.speaker_2_voice} onChange={e => updateModel('tts_model', { ...orchestration.tts_model, speaker_2_voice: e.target.value })} />
          </label>
          <label>Speaker 2 Speed
            <input type="number" step="0.05" value={orchestration.tts_model.speaker_2_speed} onChange={e => updateModel('tts_model', { ...orchestration.tts_model, speaker_2_speed: parseFloat(e.target.value) })} />
          </label>
          <button onClick={saveOrchestration}>Save TTS Model</button>
        </div>
      </details>
    </div>
  );
}
