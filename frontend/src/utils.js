export function stressColor(v) {
  const t = Math.max(0, Math.min(1, v))
  const stops = [
    [0.0, [7, 18, 30]],
    [0.2, [12, 74, 110]],
    [0.4, [14, 116, 144]],
    [0.55, [22, 163, 74]],
    [0.7, [250, 204, 21]],
    [0.85, [251, 146, 60]],
    [1.0, [239, 68, 68]],
  ]
  for (let i = 0; i < stops.length - 1; i++) {
    if (t <= stops[i + 1][0]) {
      const span = stops[i + 1][0] - stops[i][0]
      const f = span === 0 ? 0 : (t - stops[i][0]) / span
      const c0 = stops[i][1]
      const c1 = stops[i + 1][1]
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * f),
        Math.round(c0[1] + (c1[1] - c0[1]) * f),
        Math.round(c0[2] + (c1[2] - c0[2]) * f),
      ]
    }
  }
  return stops[stops.length - 1][1]
}

export function damageColor(v) {
  const t = Math.max(0, Math.min(1, v))
  const stops = [
    [0.0, [10, 20, 16]],
    [0.3, [34, 80, 45]],
    [0.5, [250, 204, 21]],
    [0.7, [251, 146, 60]],
    [0.85, [239, 68, 68]],
    [1.0, [127, 29, 29]],
  ]
  for (let i = 0; i < stops.length - 1; i++) {
    if (t <= stops[i + 1][0]) {
      const span = stops[i + 1][0] - stops[i][0]
      const f = span === 0 ? 0 : (t - stops[i][0]) / span
      const c0 = stops[i][1]
      const c1 = stops[i + 1][1]
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * f),
        Math.round(c0[1] + (c1[1] - c0[1]) * f),
        Math.round(c0[2] + (c1[2] - c0[2]) * f),
      ]
    }
  }
  return stops[stops.length - 1][1]
}

export function rgbStr(rgb) {
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`
}

export function fmt(n, digits = 2) {
  if (n === null || n === undefined || isNaN(n)) return '—'
  if (Math.abs(n) >= 1000) return n.toFixed(0)
  if (Math.abs(n) >= 10) return n.toFixed(1)
  return n.toFixed(digits)
}

export function gradientCss(stops, horizontal = true) {
  const parts = stops.map((s, i) => {
    const pct = (i / (stops.length - 1)) * 100
    return `${rgbStr(s)} ${pct.toFixed(1)}%`
  })
  return `linear-gradient(${horizontal ? 'to right' : 'to bottom'}, ${parts.join(', ')})`
}

export const FIELD_LABELS = {
  stress: '应力',
  strain: '应变',
  damage: '损伤',
  displacement: '位移',
  effective_modulus: '有效模量',
}
