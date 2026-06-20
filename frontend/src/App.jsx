import { useState, useEffect, useCallback, useRef } from 'react'
import ParameterPanel from './components/ParameterPanel'
import SummaryCards from './components/SummaryCards'
import StressHeatmap from './components/StressHeatmap'
import TimeSeriesChart from './components/TimeSeriesChart'
import SpatialProfileChart from './components/SpatialProfileChart'
import StressStrainChart from './components/StressStrainChart'
import DamageEvolutionChart from './components/DamageEvolutionChart'
import AnimationPlayer from './components/AnimationPlayer'
import { fetchParams, runSimulationFull, checkHealth } from './api'
import { FIELD_LABELS } from './utils'

const BambooIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="#04140a" strokeWidth="2.2" strokeLinecap="round">
    <path d="M9 2v20M15 2v20M9 7h6M9 12h6M9 17h6" />
  </svg>
)

export default function App() {
  const [schema, setSchema] = useState(null)
  const [values, setValues] = useState({ material: {}, geometry: {} })
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [online, setOnline] = useState(false)
  const [error, setError] = useState(null)
  const [heatmapField, setHeatmapField] = useState('stress')
  const [tsField, setTsField] = useState('stress')
  const [spField, setSpField] = useState('damage')
  const [hasRun, setHasRun] = useState(false)
  const toastTimer = useRef(null)

  const showToast = (msg) => {
    setError(msg)
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setError(null), 5000)
  }

  useEffect(() => {
    checkHealth().then(setOnline)
    fetchParams()
      .then((d) => {
        setSchema(d.schema)
        setValues({ material: { ...d.defaults.material }, geometry: { ...d.defaults.geometry } })
      })
      .catch(() => showToast('无法连接后端 API, 请确认 Flask 服务已启动 (端口 5001)'))
  }, [])

  const handleParamChange = (group, key, val) => {
    setValues((s) => ({
      ...s,
      [group]: { ...s[group], [key]: val },
    }))
  }

  const handleReset = () => {
    if (!schema) return
    const defaults = {}
    Object.keys(schema).forEach((g) => {
      defaults[g] = {}
      Object.keys(schema[g]).forEach((k) => {
        defaults[g][k] = schema[g][k].default
      })
    })
    setValues(defaults)
  }

  const handleRun = useCallback(async () => {
    setRunning(true)
    setError(null)
    try {
      const data = await runSimulationFull(values)
      setResult(data)
      setHasRun(true)
    } catch (e) {
      const msg = e.response?.data?.error || e.message || '仿真请求失败'
      showToast(msg)
    } finally {
      setRunning(false)
    }
  }, [values])

  useEffect(() => {
    if (schema && Object.keys(values.material).length > 0 && !hasRun) {
      handleRun()
    }
  }, [schema, values, hasRun, handleRun])

  const heatmapData = heatmapField === 'damage' ? result?.heatmap_damage : result?.heatmap_stress
  const tsData = tsField === 'damage' ? result?.time_series_damage : result?.time_series_stress
  const spData = spField === 'damage' ? result?.spatial_damage : result?.spatial_stress

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="logo-mark"><BambooIcon /></div>
          <div>
            <div className="header-title">竹纤维复合材料管壁应力-损伤演化分析系统</div>
            <div className="header-sub">Axial Compression · 1D Wave PDE · Continuum Damage Mechanics</div>
          </div>
        </div>
        <div className="header-right">
          <div className="status-pill">
            <span className={`status-dot ${online ? 'online' : ''}`} />
            {online ? '后端在线' : '后端离线'}
          </div>
          <div className="status-pill">
            <span className={`status-dot ${running ? 'busy' : ''}`} />
            {running ? '求解中' : '就绪'}
          </div>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <ParameterPanel
            schema={schema}
            values={values}
            onChange={handleParamChange}
            onRun={handleRun}
            onReset={handleReset}
            running={running}
          />
        </aside>

        <main className="main">
          {result && <SummaryCards summary={result.summary} />}

          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">二维应力分布图谱 (时间 × 空间)</span>
              <div className="panel-controls">
                <div className="field-tabs">
                  <button
                    className={`field-tab ${heatmapField === 'stress' ? 'active' : ''}`}
                    onClick={() => setHeatmapField('stress')}
                  >应力</button>
                  <button
                    className={`field-tab ${heatmapField === 'damage' ? 'active' : ''}`}
                    onClick={() => setHeatmapField('damage')}
                  >损伤</button>
                </div>
              </div>
            </div>
            <StressHeatmap data={heatmapData} field={heatmapField} label={FIELD_LABELS[heatmapField]} />
          </div>

          <div className="charts-grid">
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">采样点时程曲线</span>
                <div className="field-tabs">
                  <button className={`field-tab ${tsField === 'stress' ? 'active' : ''}`} onClick={() => setTsField('stress')}>应力</button>
                  <button className={`field-tab ${tsField === 'damage' ? 'active' : ''}`} onClick={() => setTsField('damage')}>损伤</button>
                </div>
              </div>
              <TimeSeriesChart data={tsData} label={FIELD_LABELS[tsField]} />
            </div>

            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">空间分布剖面</span>
                <div className="field-tabs">
                  <button className={`field-tab ${spField === 'stress' ? 'active' : ''}`} onClick={() => setSpField('stress')}>应力</button>
                  <button className={`field-tab ${spField === 'damage' ? 'active' : ''}`} onClick={() => setSpField('damage')}>损伤</button>
                </div>
              </div>
              <SpatialProfileChart data={spData} label={FIELD_LABELS[spField]} />
            </div>

            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">应力-应变本构曲线</span>
              </div>
              <StressStrainChart data={result?.stress_strain} />
            </div>

            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">损伤演化统计</span>
              </div>
              <DamageEvolutionChart data={result?.damage_evolution} />
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">应力波传播动画</span>
            </div>
            <AnimationPlayer frames={result?.animation} label={FIELD_LABELS.stress} />
          </div>

          {!result && !running && (
            <div className="empty-state" style={{ minHeight: 120 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                等待仿真启动…
              </div>
            </div>
          )}
        </main>
      </div>

      {error && <div className="toast">{error}</div>}
    </div>
  )
}
