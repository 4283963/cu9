import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'

export default function DamageEvolutionChart({ data }) {
  if (!data) return <div className="empty-state"><span style={{ fontSize: 12 }}>无数据</span></div>
  const rows = data.t.map((t, i) => ({
    t,
    max: data.max_damage[i],
    mean: data.mean_damage[i],
    failed: data.failed_fraction[i] * 100,
  }))
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 18, left: 0 }}>
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
            yAxisId="left"
            tick={{ fill: '#5a6b5f', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            width={42}
            domain={[0, 1]}
            label={{ value: '损伤 D', angle: -90, position: 'insideLeft', fill: '#8fa394', fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fill: '#5a6b5f', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            width={42}
            domain={[0, 100]}
            label={{ value: '失效 (%)', angle: 90, position: 'insideRight', fill: '#8fa394', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: '#0e1411', border: '1px solid #2c3f33', borderRadius: 8, fontFamily: 'JetBrains Mono', fontSize: 12 }}
            labelStyle={{ color: '#8fa394' }}
            labelFormatter={(l) => `t = ${Number(l).toFixed(1)} μs`}
          />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'IBM Plex Sans' }} />
          <ReferenceLine yAxisId="left" y={0.85} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'D_c', fill: '#ef4444', fontSize: 10 }} />
          <Line yAxisId="left" type="monotone" dataKey="max" name="最大损伤" stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line yAxisId="left" type="monotone" dataKey="mean" name="平均损伤" stroke="#fbbf24" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line yAxisId="right" type="monotone" dataKey="failed" name="失效比例" stroke="#22d3ee" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
