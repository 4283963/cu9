import React, { useRef, useEffect, useState } from 'react'
import { stressColor, damageColor, rgbStr, gradientCss, fmt } from '../utils'

const COLOR_STOPS = [0, 0.2, 0.4, 0.55, 0.7, 0.85, 1.0].map((t) => stressColor(t))

export default function StressHeatmap({ data, field, label }) {
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)
  const [hover, setHover] = useState(null)
  const [size, setSize] = useState({ w: 700, h: 240 })

  useEffect(() => {
    const update = () => {
      if (wrapRef.current) {
        setSize({ w: wrapRef.current.clientWidth, h: 240 })
      }
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  useEffect(() => {
    if (!data) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const matrix = data.matrix
    const nt = matrix.length
    const nx = matrix[0].length
    const dpr = window.devicePixelRatio || 1
    const W = size.w
    const H = size.h
    canvas.width = W * dpr
    canvas.height = H * dpr
    canvas.style.width = W + 'px'
    canvas.style.height = H + 'px'
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.imageSmoothingEnabled = false

    const vmin = data.vmin
    const vmax = data.vmax || 1
    const range = vmax - vmin || 1
    const colorFn = field === 'damage' ? damageColor : stressColor

    const cellW = W / nx
    const cellH = H / nt
    for (let it = 0; it < nt; it++) {
      for (let ix = 0; ix < nx; ix++) {
        const v = matrix[it][ix]
        const t = (v - vmin) / range
        const c = colorFn(t)
        ctx.fillStyle = rgbStr(c)
        ctx.fillRect(ix * cellW, it * cellH, cellW + 0.6, cellH + 0.6)
      }
    }
  }, [data, field, size])

  const handleMove = (e) => {
    if (!data) return
    const rect = canvasRef.current.getBoundingClientRect()
    const px = (e.clientX - rect.left) / rect.width
    const py = (e.clientY - rect.top) / rect.height
    const matrix = data.matrix
    const ix = Math.min(matrix[0].length - 1, Math.max(0, Math.floor(px * matrix[0].length)))
    const it = Math.min(matrix.length - 1, Math.max(0, Math.floor(py * matrix.length)))
    setHover({
      x: data.x_axis[ix],
      t: data.t_axis[it],
      v: matrix[it][ix],
    })
  }

  if (!data) {
    return (
      <div className="empty-state">
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>运行仿真后显示二维分布</div>
      </div>
    )
  }

  const xMin = data.x_axis[0]
  const xMax = data.x_axis[data.x_axis.length - 1]
  const tMax = data.t_axis[data.t_axis.length - 1]

  return (
    <div>
      <div className="heatmap-wrap" ref={wrapRef}>
        <canvas
          id="heatmap-canvas"
          ref={canvasRef}
          onMouseMove={handleMove}
          onMouseLeave={() => setHover(null)}
        />
        <div className="heatmap-axes" style={{ justifyContent: 'space-between' }}>
          <span>x = {fmt(xMin, 1)} mm (加载端)</span>
          <span>管壁轴向位置</span>
          <span>x = {fmt(xMax, 1)} mm (固定端)</span>
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
        <div className="heatmap-legend">
          <span>{label} (归一化)</span>
          <div className="legend-bar" style={{ background: gradientCss(COLOR_STOPS) }} />
          <span>{fmt(data.vmin, 1)} → {fmt(data.vmax, 1)}</span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-faint)' }}>
          纵轴: 时间 0 → {fmt(tMax, 1)} μs
        </div>
      </div>
      {hover && (
        <div style={{
          position: 'absolute', pointerEvents: 'none',
          fontFamily: 'var(--font-mono)', fontSize: 11,
          background: 'var(--surface-2)', border: '1px solid var(--border-bright)',
          padding: '6px 10px', borderRadius: 6, color: 'var(--text)',
          left: 12, bottom: 12,
        }}>
          x={fmt(hover.x, 1)}mm · t={fmt(hover.t, 1)}μs · {label}={fmt(hover.v, 3)}
        </div>
      )}
    </div>
  )
}
