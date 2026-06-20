import React, { useState, useEffect, useRef, useCallback } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function AnimationPlayer({ frames, label }) {
  const [frameIdx, setFrameIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const rafRef = useRef(null)
  const lastTimeRef = useRef(0)

  const total = frames ? frames.length : 0

  const tick = useCallback((ts) => {
    if (!lastTimeRef.current) lastTimeRef.current = ts
    const dt = ts - lastTimeRef.current
    lastTimeRef.current = ts
    setFrameIdx((prev) => {
      const next = prev + (dt / 60)
      if (next >= total - 1) {
        return 0
      }
      return next
    })
    rafRef.current = requestAnimationFrame(tick)
  }, [total])

  useEffect(() => {
    if (playing && total > 0) {
      lastTimeRef.current = 0
      rafRef.current = requestAnimationFrame(tick)
      return () => cancelAnimationFrame(rafRef.current)
    }
  }, [playing, tick, total])

  useEffect(() => {
    setFrameIdx(0)
    setPlaying(false)
  }, [frames])

  if (!frames || total === 0) {
    return <div className="empty-state"><span style={{ fontSize: 12 }}>无动画数据</span></div>
  }

  const idx = Math.min(total - 1, Math.floor(frameIdx))
  const frame = frames[idx]
  const rows = frame.x.map((x, i) => ({ x, v: frame.values[i] }))
  const allVals = frames.flatMap((f) => f.values)
  const globalMax = Math.max(...allVals.map(Math.abs)) * 1.05 || 1

  return (
    <div>
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 18, left: 4 }}>
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
              domain={[-globalMax, globalMax]}
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
            <Line type="monotone" dataKey="v" stroke="#4ade80" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="anim-controls" style={{ marginTop: 10 }}>
        <button className="btn-icon" onClick={() => setPlaying((p) => !p)}>
          {playing ? '❚❚' : '▶'}
        </button>
        <button className="btn-icon" onClick={() => { setFrameIdx(0); setPlaying(false) }}>↺</button>
        <input
          className="anim-slider"
          type="range"
          min={0}
          max={total - 1}
          step={0.1}
          value={frameIdx}
          onChange={(e) => { setFrameIdx(parseFloat(e.target.value)); setPlaying(false) }}
        />
        <span className="time-readout">t = {frame.t_us.toFixed(1)} μs</span>
      </div>
    </div>
  )
}
