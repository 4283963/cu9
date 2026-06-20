import React, { useState } from 'react'

export default function ParameterPanel({ schema, values, onChange, onRun, onReset, running }) {
  const [expanded, setExpanded] = useState({ material: true, geometry: true })

  const toggle = (g) => setExpanded((s) => ({ ...s, [g]: !s[g] }))

  const renderField = (group, key) => {
    const meta = schema[group][key]
    const val = values[group][key]
    return (
      <div className="param-row" key={key}>
        <div className="param-head">
          <span className="param-label">{meta.label}</span>
          <span className="param-value">
            {Number(val).toFixed(meta.step < 1 ? 2 : meta.step < 10 ? 1 : 0)}
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
            type="number"
            min={meta.min}
            max={meta.max}
            step={meta.step}
            value={val}
            onChange={(e) => onChange(group, key, parseFloat(e.target.value))}
          />
        </div>
      </div>
    )
  }

  const groups = ['material', 'geometry']
  const groupLabels = { material: '材料本构参数', geometry: '几何与加载参数' }

  return (
    <div>
      <div className="section-title">仿真参数配置</div>
      {groups.map((g) => (
        <div className="param-group" key={g}>
          <div
            className="param-group-label"
            style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between' }}
            onClick={() => toggle(g)}
          >
            <span>{groupLabels[g]}</span>
            <span style={{ color: 'var(--text-faint)' }}>{expanded[g] ? '▾' : '▸'}</span>
          </div>
          {expanded[g] && schema && schema[g] &&
            Object.keys(schema[g]).map((key) => renderField(g, key))}
        </div>
      ))}
      <button className="btn-run" onClick={onRun} disabled={running}>
        {running ? '求解中…' : '▶ 运行仿真'}
      </button>
      <button className="btn-secondary" onClick={onReset} disabled={running}>
        重置默认参数
      </button>
    </div>
  )
}
