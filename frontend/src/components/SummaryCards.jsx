import React from 'react'
import { fmt } from '../utils'

export default function SummaryCards({ summary }) {
  if (!summary) return null
  const cards = [
    { label: '峰值应力', value: summary.max_stress_MPa, unit: 'MPa', tone: 'amber' },
    { label: '最大应变', value: summary.max_strain, unit: '', tone: '' },
    { label: '最大损伤', value: summary.max_damage, unit: '', tone: summary.max_damage > 0.5 ? 'red' : 'amber' },
    { label: '失效节点', value: summary.failed_nodes, unit: `/${summary.n_spatial_nodes}`, tone: summary.failed_nodes > 0 ? 'red' : '' },
    { label: '波速', value: summary.wave_speed_m_s, unit: 'm/s', tone: 'cyan' },
    { label: 'CFL 数', value: summary.cfl_number, unit: '', tone: '' },
    { label: '计算耗时', value: summary.compute_time_s, unit: 's', tone: 'cyan' },
    { label: '时间帧数', value: summary.n_time_frames, unit: '', tone: '' },
  ]
  return (
    <div className="cards-row">
      {cards.map((c, i) => (
        <div className={`metric-card ${c.tone}`} key={i}>
          <div className="metric-label">{c.label}</div>
          <div className="metric-value">
            {fmt(c.value, c.value < 1 ? 4 : 2)}
            {c.unit && <span className="unit">{c.unit}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}
