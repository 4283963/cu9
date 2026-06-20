import { useState } from 'react'

export default function ParameterPanel({ schema, values, onChange, onRun, onReset, running, asyncRunning, simMode }) {
  const [expanded, setExpanded] = useState({
    mode: true, material: true, geometry: true,
  })

  const toggle = (g) => setExpanded((s) => ({ ...s, [g]: !s[g] }))

  const fmtShow = (v, step) => {
    if (step >= 1) return v.toString()
    if (step < 0.01) return Number(v).toExponential(2)
    if (step < 1) return Number(v).toFixed(2)
    return v.toString()
  }

  const fieldIsVisible = (meta) => {
    if (!meta.mode) return true
    if (meta.mode === simMode) return true
    if (Array.isArray(meta.mode)) {
      return meta.mode.includes(simMode)
    }
    return false
  }

  const renderField = (group, key) => {
    const meta = schema[group][key]
    if (!fieldIsVisible(meta)) return null
    const val = values[group][key]

    if (meta.type === 'select') {
      return (
        <div className="param-row" key={key}>
          <div className="param-head">
            <span className="param-label">{meta.label}</span>
          </div>
          <div className="select-wrap">
            <select value={val} onChange={(e) => onChange(group, key, e.target.value)}>
              {meta.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )
    }

    if (meta.type === 'boolean') {
      return (
        <div className="param-row" key={key}>
          <div className="param-head">
            <span className="param-label">{meta.label}</span>
          </div>
          <div className="bool-row" style={{ flex: 1 }}>
            <label className="param-value">
              <span style={{ cursor: 'pointer', color: val ? 'var(--accent)' : 'var(--text-dim)', fontWeight: 500 }}>
                {val ? '已启用' : '已关闭'}
              </span>
            </label>
            <div
              className={`switch ${val ? 'on' : ''}`}
              onClick={() => onChange(group, key, !val)}
            />
          </div>
        </div>
      )
    }

    const step = meta.step
    const stepLog = step < 0.01
    return (
      <div className="param-row" key={key}>
        <div className="param-head">
          <span className="param-label">{meta.label}</span>
          <span className="param-value">
            {fmtShow(val, step)}
            <span className="param-unit">{meta.unit}</span>
          </span>
        </div>
        <div className="param-control">
          <input
            type="range"
            min={meta.min}
            max={meta.max}
            step={meta.step}
            value={val}
            onChange={(e) => onChange(group, key, parseFloat(e.target.value))}
          />
          <input
            type="text"
            value={stepLog ? Number(val).toExponential(2) : val}
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              if (!isNaN(v)) {
                onChange(group, key, Math.min(meta.max, Math.max(meta.min, v)))
              }
            }}
          />
        </div>
      </div>
    )
  }

  const groups = [
    { key: 'mode', label: '仿真模式配置' },
    { key: 'material', label: '材料本构参数' },
    { key: 'geometry', label: '几何与加载参数' },
  ]

  return (
    <div>
      <div className="section-title">仿真参数配置</div>

      <div className={`mode-banner ${simMode}`}>
        <span className="mode-banner-icon">
          {simMode === 'quasi_static' ? '⏱' : '💥'}
        </span>
        <div>
          <strong>
            {simMode === 'quasi_static' ? '长时准静态模式' : '瞬态波动模式'}
          </strong>
          <div>
            {simMode === 'quasi_static'
              ? '蠕变损伤演化 · 异步任务执行，避免504超时'
              : '弹性波传播 · 同步响应'}
          </div>
        </div>
      </div>

      {groups.map((g) => (
        <div className={`param-group ${expanded[g.key] ? '' : 'param-group-collapsed'}`}
             key={g.key}>
          <div
            className="param-group-label"
            style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', userSelect: 'none' }}
            onClick={() => toggle(g.key)}
          >
            <span>{g.label}</span>
            <span style={{ color: 'var(--text-faint)' }}>{expanded[g.key] ? '▾' : '▸'}</span>
          </div>
          {expanded[g.key] && schema && schema[g.key] &&
            Object.keys(schema[g.key]).map((key) => renderField(g.key, key))}
        </div>
      ))}

      <button className="btn-run" onClick={onRun} disabled={running || asyncRunning}>
        {running || asyncRunning ? '求解中…' : '▶ 运行仿真'}
      </button>
      <button className="btn-secondary" onClick={onReset} disabled={running || asyncRunning}>
        重置默认参数
      </button>
    </div>
  )
}
