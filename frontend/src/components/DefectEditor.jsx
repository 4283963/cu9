import { useRef, useState, useEffect } from 'react'

export default function DefectEditor({
  defects,
  onChange,
  lengthMm = 500,
  initialDamage = 0.6,
  radiusMm = 5,
  disabled = false,
}) {
  const canvasRef = useRef(null)
  const [hoverX, setHoverX] = useState(null)
  const [brushMode, setBrushMode] = useState('paint')

  const W = 320
  const H = 64
  const PAD_L = 36
  const PAD_R = 8
  const PAD_T = 12
  const PAD_B = 22
  const plotW = W - PAD_L - PAD_R
  const plotH = H - PAD_T - PAD_B

  const xToPx = (xMm) => PAD_L + (xMm / lengthMm) * plotW
  const pxToX = (px) => ((px - PAD_L) / plotW) * lengthMm

  useEffect(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    c.width = W * dpr
    c.height = H * dpr
    c.style.width = W + 'px'
    c.style.height = H + 'px'
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    ctx.clearRect(0, 0, W, H)

    ctx.fillStyle = '#0e1411'
    ctx.fillRect(0, 0, W, H)

    ctx.strokeStyle = '#1a241e'
    ctx.lineWidth = 1
    for (let i = 0; i <= 10; i++) {
      const x = PAD_L + (i / 10) * plotW
      ctx.beginPath()
      ctx.moveTo(x, PAD_T)
      ctx.lineTo(x, PAD_T + plotH)
      ctx.stroke()
    }

    const grad = ctx.createLinearGradient(0, PAD_T, 0, PAD_T + plotH)
    grad.addColorStop(0, 'rgba(74, 222, 128, 0.06)')
    grad.addColorStop(1, 'rgba(74, 222, 128, 0.02)')
    ctx.fillStyle = grad
    ctx.fillRect(PAD_L, PAD_T, plotW, plotH)

    ctx.strokeStyle = '#2c3f33'
    ctx.lineWidth = 1
    ctx.strokeRect(PAD_L + 0.5, PAD_T + 0.5, plotW - 1, plotH - 1)

    ctx.fillStyle = '#5a6b5f'
    ctx.font = '9px IBM Plex Mono, monospace'
    ctx.textAlign = 'center'
    for (let i = 0; i <= 5; i++) {
      const xMm = (i / 5) * lengthMm
      const x = xToPx(xMm)
      ctx.fillText(`${xMm.toFixed(0)}`, x, H - 6)
    }
    ctx.textAlign = 'right'
    ctx.fillText('mm', PAD_L - 4, H - 6)

    if (hoverX !== null && !disabled) {
      const x = xToPx(hoverX)
      ctx.fillStyle = 'rgba(251, 191, 36, 0.08)'
      ctx.fillRect(PAD_L, PAD_T, x - PAD_L, plotH)
      ctx.strokeStyle = 'rgba(251, 191, 36, 0.6)'
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(x, PAD_T)
      ctx.lineTo(x, PAD_T + plotH)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = '#fbbf24'
      ctx.font = '9px IBM Plex Mono, monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`${hoverX.toFixed(1)} mm`, x + 5, PAD_T + 11)
    }

    defects.forEach((d, i) => {
      const cx = xToPx(d.x_mm)
      const rPx = (d.radius_mm / lengthMm) * plotW
      const centerY = PAD_T + plotH / 2

      const g = ctx.createRadialGradient(cx, centerY, 0, cx, centerY, Math.max(rPx, 4))
      const alpha = 0.2 + (d.initial_damage || 0.5) * 0.7
      g.addColorStop(0, `rgba(239, 68, 68, ${alpha})`)
      g.addColorStop(0.5, `rgba(251, 146, 60, ${alpha * 0.5})`)
      g.addColorStop(1, 'rgba(239, 68, 68, 0)')
      ctx.fillStyle = g
      ctx.fillRect(cx - rPx - 2, PAD_T, rPx * 2 + 4, plotH)

      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = 1.5
      ctx.setLineDash([2, 2])
      ctx.beginPath()
      ctx.moveTo(cx, PAD_T)
      ctx.lineTo(cx, PAD_T + plotH)
      ctx.stroke()
      ctx.setLineDash([])

      ctx.fillStyle = '#ef4444'
      ctx.beginPath()
      ctx.arc(cx, centerY, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#7f1d1d'
      ctx.lineWidth = 1
      ctx.stroke()

      ctx.fillStyle = '#fecaca'
      ctx.font = 'bold 9px IBM Plex Mono, monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`#${i + 1} D=${(d.initial_damage || 0).toFixed(2)}`, cx, PAD_T + 11)
    })
  }, [defects, hoverX, lengthMm, disabled])

  const onCanvasMove = (e) => {
    if (disabled) return
    const rect = canvasRef.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const x = pxToX(px)
    if (x < 0 || x > lengthMm) {
      setHoverX(null)
      return
    }
    setHoverX(x)
  }

  const onCanvasLeave = () => setHoverX(null)

  const onCanvasClick = (e) => {
    if (disabled) return
    const rect = canvasRef.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const x = pxToX(px)
    if (x < 0 || x > lengthMm) return
    const xSnapped = Math.round(x / 2.5) * 2.5

    if (brushMode === 'erase') {
      const nearest = defects.findIndex(
        (d) => Math.abs(d.x_mm - xSnapped) <= Math.max(d.radius_mm, radiusMm)
      )
      if (nearest >= 0) {
        const next = [...defects]
        next.splice(nearest, 1)
        onChange(next)
        return
      }
    }

    const overlapIdx = defects.findIndex(
      (d) => Math.abs(d.x_mm - xSnapped) <= d.radius_mm * 0.6
    )
    if (overlapIdx >= 0) {
      const next = [...defects]
      next.splice(overlapIdx, 1)
      onChange(next)
      return
    }

    if (defects.length >= 10) return
    onChange([
      ...defects,
      {
        x_mm: xSnapped,
        radius_mm: radiusMm,
        initial_damage: initialDamage,
      },
    ])
  }

  const clearAll = () => onChange([])

  return (
    <div className="param-row" style={{ display: 'block' }}>
      <div className="param-head" style={{ marginBottom: 4 }}>
        <span className="param-label">初始纤维缺陷点</span>
        <span className="param-value">
          {defects.length} / 10
          <span className="param-unit">点</span>
        </span>
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center' }}>
        <div
          className={`field-tab ${brushMode === 'paint' ? 'active' : ''}`}
          style={{ padding: '4px 10px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.4 : 1 }}
          onClick={() => !disabled && setBrushMode('paint')}
        >
          ✎ 画缺陷
        </div>
        <div
          className={`field-tab ${brushMode === 'erase' ? 'active' : ''}`}
          style={{ padding: '4px 10px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.4 : 1 }}
          onClick={() => !disabled && setBrushMode('erase')}
        >
          ⌫ 擦除
        </div>
        <div
          className="field-tab"
          style={{ padding: '4px 10px', marginLeft: 'auto', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.4 : 1, color: defects.length === 0 ? '#5a6b5f' : undefined }}
          onClick={() => !disabled && defects.length > 0 && clearAll()}
        >
          清空全部
        </div>
      </div>

      <canvas
        ref={canvasRef}
        onMouseMove={onCanvasMove}
        onMouseLeave={onCanvasLeave}
        onClick={onCanvasClick}
        style={{
          cursor: disabled ? 'not-allowed' : (brushMode === 'paint' ? 'crosshair' : 'pointer'),
          display: 'block',
          borderRadius: 6,
          border: '1px solid #1e2b23',
          width: '100%',
          maxWidth: W,
          height: H,
        }}
      />
      <div style={{
        fontSize: 10.5, color: '#5a6b5f', fontFamily: 'IBM Plex Mono, monospace',
        marginTop: 4, lineHeight: 1.5,
      }}>
        {brushMode === 'paint'
          ? '点击位置添加缺陷点（再次点击可移除）'
          : '点击已有缺陷区域移除该缺陷'}
        · 缺陷处刚度系数按 (1-D) 比例降低
      </div>
    </div>
  )
}
