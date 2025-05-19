import { useState, useEffect } from 'react';

export default function ModelCard({ title, config = {}, providers = [], onChange }) {
  const [state, setState] = useState({
    model_name: '',
    model_type: providers[0] || '',
    max_new_tokens: 0,
    temperature: 0.7,
    num_ctx: 0,
    trust_remote_code: false,
    ...config
  });

  useEffect(() => {
    setState(prev => ({ ...prev, ...config }));
  }, [config]);

  useEffect(() => {
    onChange && onChange(state);
  }, [state]);

  return (
    <div className="card">
      <h3>{title}</h3>
      <label>Model Name
        <input value={state.model_name} onChange={e => setState({ ...state, model_name: e.target.value })} />
      </label>
      <label>Model Type
        <select value={state.model_type} onChange={e => setState({ ...state, model_type: e.target.value })}>
          {providers.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      {title !== 'Embedding Model' && (
        <>
          <label>Max New Tokens
            <input type="number" value={state.max_new_tokens} onChange={e => setState({ ...state, max_new_tokens: Number(e.target.value) })} />
          </label>
          <label>Temperature
            <input type="number" step="0.01" value={state.temperature} onChange={e => setState({ ...state, temperature: parseFloat(e.target.value) })} />
          </label>
          {(state.model_type === 'ollama' || state.model_type === 'llamacpp') && (
            <label>Context Window Size
              <input type="number" value={state.num_ctx || 0} onChange={e => setState({ ...state, num_ctx: Number(e.target.value) })} />
            </label>
          )}
        </>
      )}
      {title === 'Embedding Model' && (
        <label>
          <input type="checkbox" checked={state.trust_remote_code} onChange={e => setState({ ...state, trust_remote_code: e.target.checked })} />
          Trust Remote Code
        </label>
      )}
    </div>
  );
}
