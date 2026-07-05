import { useEffect, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function useAuth() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const login = (t) => {
    localStorage.setItem('token', t)
    setToken(t)
  }
  const logout = () => {
    localStorage.removeItem('token')
    setToken('')
  }
  return { token, login, logout }
}

function Switch({ checked, onChange }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="switch-track" />
    </label>
  )
}

function StatusBadge({ status }) {
  const variant = status === 'failed' ? 'badge-danger' : status === 'processed' ? 'badge-success' : 'badge-neutral'
  return <span className={`badge ${variant}`}>{status}</span>
}

function LoginForm({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) throw new Error('Invalid username or password')
      const data = await res.json()
      onLogin(data.access_token)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">🤖</div>
        <h2>Admin Login</h2>
        <p className="login-subtitle">Discord Bot Dashboard</p>
        <form onSubmit={submit} className="login-form">
          <input
            className="input"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <input
            className="input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Signing in…' : 'Log in'}
          </button>
          {error && <p className="error-text">{error}</p>}
        </form>
      </div>
    </div>
  )
}

function LogsTable({ token }) {
  const [logs, setLogs] = useState([])

  const fetchLogs = async () => {
    const res = await fetch(`${API_BASE}/dashboard/logs`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) setLogs(await res.json())
  }

  useEffect(() => {
    fetchLogs()
    const id = setInterval(fetchLogs, 4000) // live-ish log
    return () => clearInterval(id)
  }, [])

  return (
    <div className="section">
      <div className="section-header">
        <h3>Command Log</h3>
        <span className="section-hint">refreshes every 4s</span>
      </div>

      {logs.length === 0 ? (
        <div className="empty-state">No commands logged yet — run <code>/status</code> or <code>/report</code> in Discord to see it appear here.</div>
      ) : (
        <div className="table-wrap">
          <table className="log-table">
            <thead>
              <tr>
                <th>Time</th><th>User</th><th>Command</th><th>Text</th>
                <th>Action</th><th>Status</th><th>Mirrored</th><th>AI</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td>{new Date(l.created_at).toLocaleTimeString()}</td>
                  <td>{l.user_tag}</td>
                  <td>/{l.command_name}</td>
                  <td>{l.command_text || '—'}</td>
                  <td>{l.action_taken || '—'}</td>
                  <td><StatusBadge status={l.status} /></td>
                  <td>{l.mirror_delivered ? '✅' : '—'}</td>
                  <td>{l.ai_summary || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ServerSetup({ token, onConnected }) {
  const [inviteUrl, setInviteUrl] = useState('')
  const [guilds, setGuilds] = useState([])
  const [channels, setChannels] = useState([])
  const [servers, setServers] = useState([])
  const [selectedGuild, setSelectedGuild] = useState(null)
  const [selectedChannel, setSelectedChannel] = useState('')
  const [slackUrl, setSlackUrl] = useState('')
  const [error, setError] = useState('')
  const [loadingGuilds, setLoadingGuilds] = useState(false)

  const authHeaders = { Authorization: `Bearer ${token}` }

  const fetchServers = async () => {
    const res = await fetch(`${API_BASE}/dashboard/servers`, { headers: authHeaders })
    if (res.ok) setServers(await res.json())
  }

  const fetchInviteUrl = async () => {
    const res = await fetch(`${API_BASE}/dashboard/discord/invite-url`, { headers: authHeaders })
    if (res.ok) setInviteUrl((await res.json()).invite_url)
  }

  useEffect(() => { fetchServers(); fetchInviteUrl() }, [])

  const loadGuilds = async () => {
    setError('')
    setLoadingGuilds(true)
    try {
      const res = await fetch(`${API_BASE}/dashboard/discord/guilds`, { headers: authHeaders })
      if (res.ok) setGuilds(await res.json())
      else setError('Could not load servers — has the bot been invited yet?')
    } finally {
      setLoadingGuilds(false)
    }
  }

  const pickGuild = async (guild) => {
    setSelectedGuild(guild)
    setChannels([])
    setSelectedChannel('')
    const res = await fetch(`${API_BASE}/dashboard/discord/guilds/${guild.id}/channels`, { headers: authHeaders })
    if (res.ok) setChannels(await res.json())
  }

  const connect = async () => {
    await fetch(`${API_BASE}/dashboard/servers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({
        guild_id: selectedGuild.id,
        guild_name: selectedGuild.name,
        mirror_channel_id: selectedChannel || null,
        mirror_channel_name: channels.find((c) => c.id === selectedChannel)?.name || null,
        slack_webhook_url: slackUrl || null,
      }),
    })
    setSelectedGuild(null)
    setGuilds([])
    setSlackUrl('')
    fetchServers()
    onConnected?.()
  }

  const disconnect = async (guildId) => {
    await fetch(`${API_BASE}/dashboard/servers/${guildId}`, { method: 'DELETE', headers: authHeaders })
    fetchServers()
    onConnected?.()
  }

  return (
    <div className="section">
      <div className="section-header">
        <h3>Connected Servers</h3>
      </div>

      {servers.length === 0 ? (
        <div className="empty-state">No servers connected yet — connect one below.</div>
      ) : (
        <div className="card-grid" style={{ marginBottom: 20 }}>
          {servers.map((s) => (
            <div key={s.guild_id} className="card server-card">
              <div className="server-avatar">{s.guild_name?.[0]?.toUpperCase() || '?'}</div>
              <div className="server-info">
                <div className="server-name">{s.guild_name}</div>
                <div className="server-meta">
                  Mirrors to {s.slack_webhook_url ? 'a Slack webhook' : s.mirror_channel_name ? `#${s.mirror_channel_name}` : 'nothing configured'}
                </div>
              </div>
              <button className="btn btn-sm btn-danger" onClick={() => disconnect(s.guild_id)}>Disconnect</button>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div className="config-card-head">
          <span className="config-command">Connect a server</span>
        </div>
        <div className="wizard">
          <div className="wizard-step">
            <span className="step-num">1</span>
            {inviteUrl ? (
              <a className="btn btn-sm" href={inviteUrl} target="_blank" rel="noreferrer">Add the bot to your server ↗</a>
            ) : (
              <span className="section-hint">Loading invite link…</span>
            )}
          </div>

          <div className="wizard-step">
            <span className="step-num">2</span>
            <button className="btn btn-sm" onClick={loadGuilds} disabled={loadingGuilds}>
              {loadingGuilds ? 'Refreshing…' : 'Refresh server list'}
            </button>
            {error && <span className="error-text">{error}</span>}
          </div>

          {guilds.length > 0 && (
            <>
              <hr className="wizard-divider" />
              <div className="wizard-step" style={{ width: '100%' }}>
                <span className="step-num">3</span>
                <select
                  className="input"
                  style={{ maxWidth: 260 }}
                  value={selectedGuild?.id || ''}
                  onChange={(e) => pickGuild(guilds.find((g) => g.id === e.target.value))}
                >
                  <option value="" disabled>Select a server…</option>
                  {guilds.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </div>

              {selectedGuild && (
                <>
                  <div className="wizard-step" style={{ width: '100%' }}>
                    <span className="step-num">4</span>
                    <select
                      className="input"
                      style={{ maxWidth: 260 }}
                      value={selectedChannel}
                      onChange={(e) => setSelectedChannel(e.target.value)}
                    >
                      <option value="">Pick a channel it can post to…</option>
                      {channels.map((c) => <option key={c.id} value={c.id}>#{c.name}</option>)}
                    </select>
                    <span className="section-hint">or</span>
                    <input
                      className="input"
                      style={{ maxWidth: 260 }}
                      placeholder="Slack webhook URL instead"
                      value={slackUrl}
                      onChange={(e) => setSlackUrl(e.target.value)}
                    />
                  </div>
                  <div className="card-footer" style={{ width: '100%' }}>
                    <button className="btn btn-primary" onClick={connect} disabled={!selectedChannel && !slackUrl}>
                      Connect server
                    </button>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ConfigCard({ cfg, onSave }) {
  const [draft, setDraft] = useState(cfg)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await onSave(draft)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card">
      <div className="config-card-head">
        <span className="config-command">/{cfg.command_name}</span>
        <span className="badge badge-neutral">{cfg.guild_id ? 'this server' : 'global default'}</span>
      </div>

      <div className="field">
        <label>Reply template (use {'{text}'})</label>
        <input
          className="input"
          value={draft.reply_template}
          onChange={(e) => setDraft({ ...draft, reply_template: e.target.value })}
        />
      </div>

      <div className="switch-row">
        <span>Mirror to second channel</span>
        <Switch checked={draft.mirror_enabled} onChange={(v) => setDraft({ ...draft, mirror_enabled: v })} />
      </div>
      <div className="switch-row">
        <span>AI summarize / tag</span>
        <Switch checked={draft.ai_enabled} onChange={(v) => setDraft({ ...draft, ai_enabled: v })} />
      </div>

      <div className="card-footer">
        <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

function ConfigPanel({ token }) {
  const [configs, setConfigs] = useState([])
  const [servers, setServers] = useState([])
  const [guildId, setGuildId] = useState('')

  const fetchServers = async () => {
    const res = await fetch(`${API_BASE}/dashboard/servers`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) setServers(await res.json())
  }

  const fetchConfigs = async (forGuildId) => {
    const query = forGuildId ? `?guild_id=${forGuildId}` : ''
    const res = await fetch(`${API_BASE}/dashboard/configs${query}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) setConfigs(await res.json())
  }

  useEffect(() => { fetchServers(); fetchConfigs('') }, [])

  const save = async (cfg) => {
    await fetch(`${API_BASE}/dashboard/configs/${cfg.command_name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...cfg, guild_id: cfg.guild_id ?? (guildId || null) }),
    })
    fetchConfigs(guildId)
  }

  return (
    <div className="section">
      <div className="section-header">
        <h3>Command Configuration</h3>
        <select
          className="input"
          style={{ width: 'auto' }}
          value={guildId}
          onChange={(e) => { setGuildId(e.target.value); fetchConfigs(e.target.value) }}
        >
          <option value="">Global (all servers)</option>
          {servers.map((s) => <option key={s.guild_id} value={s.guild_id}>{s.guild_name}</option>)}
        </select>
      </div>

      {configs.length === 0 ? (
        <div className="empty-state">No commands logged yet — run one in Discord first.</div>
      ) : (
        <div className="card-grid">
          {configs.map((cfg) => (
            <ConfigCard key={`${cfg.command_name}-${cfg.guild_id || 'global'}`} cfg={cfg} onSave={save} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const { token, login, logout } = useAuth()

  if (!token) return <LoginForm onLogin={login} />

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">
          <div className="brand-mark">🤖</div>
          <div>
            <h1>Discord Bot Dashboard</h1>
            <p className="brand-sub">Live command log, servers &amp; behavior config</p>
          </div>
        </div>
        <button className="btn" onClick={logout}>Log out</button>
      </div>

      <ServerSetup token={token} />
      <LogsTable token={token} />
      <ConfigPanel token={token} />
    </div>
  )
}
