import React from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function SpatialProfileChart({ data, label }) {
  if (!data) return <div className="empty-state"><span style={{ fontSize: 12 }}>无数据</span></div>
  const rows = data.x.map((x, i) => ({ x, v: data.values[i] }))
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ top: 8, right: 16, bottom: 18, left: 4 }}>
          <defs>
            <linearGradient id="spGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.6} />
              <stop offset="100%" stopColor="#fbbf24" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1e2b23" strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            type="number"
            domain={['dataMin', 'dataMax']}
            tick={{ fill: '#5a6b5f', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            label={{ value: '轴向位置 (mm)', position: 'insideBottom', offset: -8, fill: '#8fa394', fontSize: 11 }}
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
            labelFormatter={(l) => `x = ${Number(l).toFixed(2)} mm`}
          />
          <ReferenceLine y={0} stroke="#2c3f33" />
          <Area type="monotone" dataKey="v" stroke="#fbbf24" strokeWidth={1.5} fill="url(#spGrad)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
      <div style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-faint)', marginTop: 4 }}>
        时刻 t = {data.t_us?.toFixed(1)} μs
      </div>
    </div>
  )
}
