import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function TimeSeriesChart({ data, label }) {
  if (!data) return <div className="empty-state"><span style={{ fontSize: 12 }}>无数据</span></div>
  const rows = data.t.map((t, i) => ({ t, v: data.values[i] }))
  const max = Math.max(...data.values.map(Math.abs))
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 18, left: 4 }}>
          <CartesianGrid stroke="#1e2b23" strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            type="number"
            domain={['dataMin', 'dataMax']}
            tick={{ fill: '#5a6b5f', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            label={{ value: '时间 (μs)', position: 'insideBottom', offset: -8, fill: '#8fa394', fontSize: 11 }}
            tickCount={6}
          />
          <YAxis
            tick={{ fill: '#5a6b5f', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            width={52}
            label={{ value: label, angle: -90, position: 'insideLeft', fill: '#8fa394', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: '#0e1411', border: '1px solid #2c3f33', borderRadius: 8, fontFamily: 'JetBrains Mono', fontSize: 12 }}
            labelStyle={{ color: '#8fa394' }}
            formatter={(v) => [Number(v).toFixed(4), label]}
            labelFormatter={(l) => `t = ${Number(l).toFixed(2)} μs`}
          />
          <ReferenceLine y={0} stroke="#2c3f33" />
          <Line type="monotone" dataKey="v" stroke="#4ade80" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-faint)', marginTop: 4 }}>
        采样点 x = {data.x_position_mm?.toFixed(1)} mm · 峰值 {max.toFixed(3)}
      </div>
    </div>
  )
}
