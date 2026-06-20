import { useEffect, useState, useRef } from 'react'
import ParameterPanel from './components/ParameterPanel'
import SummaryCards from './components/SummaryCards'
import StressHeatmap from './components/StressHeatmap'
import TimeSeriesChart from './components/TimeSeriesChart'
import SpatialProfileChart from './components/SpatialProfileChart'
import StressStrainChart from './components/StressStrainChart'
import DamageEvolutionChart from './components/DamageEvolutionChart'
import AnimationPlayer from './components/AnimationPlayer'
import {
  fetchParams,
  runSimulationFull,
  submitAsyncSimulation,
  cancelTask,
  pollTaskUntilDone,
  checkHealth,
} from './api'
import { formatNumber, formatSci } from './utils'

const HEATMAP_W = 480
const HEATMAP_H = 480

export default function App() {
  const [backendOk, setBackendOk] = useState(true)
  const [schema, setSchema] = useState(null)
  const [params, setParams] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [taskState, setTaskState] = useState(null)
  const [toast, setToast] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [defects, setDefects] = useState([])
  const [initialDamage, setInitialDamage] = useState(0.55)
  const [defectRadius, setDefectRadius] = useState(5.0)

  const simMode = params?.mode?.sim_mode || 'wave'

  const cancelFlagRef = useRef(false)

  // 后端健康检查
  useEffect(() => {
    let alive = true
    const loop = () =>
      checkHealth().then((ok) => alive && setBackendOk(ok))
    loop()
    const t = setInterval(loop, 4000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  // 加载参数 schema
  useEffect(() => {
    (async () => {
      try {
        const p = await fetchParams()
        setSchema(p.schema)
        setParams(p.defaults)
      } catch (e) {
        showToast('后端参数加载失败，请检查后端服务', 'error')
      }
    })()
  }, [])

  const showToast = (msg, type = 'info') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3200)
  }

  const handleChange = (group, key, value) => {
    setParams((prev) => ({ ...prev, [group]: { ...prev[group], [key]: value } }))
  }

  const handleReset = () => {
    fetchParams().then((p) => {
      setParams(p.defaults)
      setDefects([])
      setInitialDamage(0.55)
      setDefectRadius(5.0)
    })
  }

  // 模式切换时重置对应的相关值
  useEffect(() => {
    if (!schema || !params) return
  }, [params?.mode?.sim_mode])

  const loadViews = async (taskOrResult) => {
    const views = taskOrResult.views || taskOrResult.data?.views
    if (!views) return
    const summary = taskOrResult.summary || views.summary
    const frames = views.animation?.frames || []
    const t_axis = views.heatmap_stress?.t_axis || []
    const x_axis = views.heatmap_stress?.x_axis || []
    const sim_summary = summary?.data || summary || {}
    setResult({
      views,
      summary: sim_summary,
      frames,
      heatmap_stress: views.heatmap_stress,
      heatmap_damage: views.heatmap_damage,
      t_axis,
      x_axis,
      n_frames: frames.length,
    })
  }

  const runSim = async () => {
    if (!params) return
    const mode = params.mode.sim_mode
    const shouldAsync = mode === 'quasi_static' || params.mode.use_async
    cancelFlagRef.current = false
    setError(null)
    setTaskState(null)

    const payload = {
      ...params,
      geometry: {
        ...params.geometry,
        defects: defects.map((d) => ({
          x_mm: d.x_mm,
          radius_mm: d.radius_mm,
          initial_damage: d.initial_damage,
        })),
      },
    }

    if (shouldAsync) {
      setTaskState({
        status: 'queued',
        progress_pct: 0,
        message: '任务已提交，等待执行...',
        task_id: null,
        live_stats: null,
      })
      try {
        const init = await submitAsyncSimulation(payload)
        const taskId = init.task_id
        setTaskState({ ...init, _start: Date.now() })
        const final = await pollTaskUntilDone(
          taskId,
          (t) => {
            if (cancelFlagRef.current) {
              cancelTask(taskId).catch(() => {})
              return false
            }
            setTaskState((s) => ({ ...s, ...t }))
          },
          350,
          20000,
        )
        if (final.status === 'done') {
          setTaskState({ ...final, _finish: Date.now() })
          await loadViews(final)
          const elapsed = (Date.now() - taskState?._start) / 1000 || 0
          showToast(`仿真完成，耗时 ${elapsed.toFixed(1)}s，共 ${final.views?.animation?.frames?.length || 0} 帧`, 'success')
        } else if (final.status === 'cancelled') {
          setTaskState({ ...final, _finish: Date.now() })
          showToast('任务已取消', 'warning')
        } else if (final.status === 'error') {
          setTaskState({ ...final, _finish: Date.now() })
          showToast(`错误: ${final.message?.slice?.(0, 120) || final.error || '求解器异常'}`, 'error')
          setError(final.message || final.error)
        }
      } catch (err) {
        setTaskState((s) => s ? { ...s, status: 'error', message: err.message } : null)
        showToast('通信失败: ' + err.message, 'error')
        setError(err.message)
      } finally {
        setTaskState((s) => s && (!['running', 'queued'].includes(s.status) ? s : null))
      }
      return
    }

    // 同步模式
    setRunning(true)
    try {
      const r = await runSimulationFull(payload)
      await loadViews(r)
      const msg = defects.length > 0
        ? `仿真完成 · ${defects.length} 个缺陷点已计入`
        : '仿真完成'
      showToast(msg, 'success')
    } catch (err) {
      const m = err.response?.data?.error || err.message
      setError(m)
      showToast('错误: ' + m, 'error')
    } finally {
      setRunning(false)
    }
  }

  const doCancel = () => {
    cancelFlagRef.current = true
    if (taskState?.task_id) {
      cancelTask(taskState.task_id).then(() => {
        showToast('取消请求已发送', 'warning')
      })
    }
  }

  const simSummary = result?.summary || null
  const simModeFinal = simSummary?.sim_mode || simMode

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">B</div>
          <div>
            <div className="brand-title">竹纤维复合材料</div>
            <div className="brand-sub">管壁轴向压损仿真平台</div>
          </div>
          <div
            className={`health-dot ${backendOk ? 'ok' : 'bad'}`}
            title={backendOk ? '后端在线' : '后端离线'}
          />
        </div>

        <ParameterPanel
          schema={schema}
          values={params || { mode: {}, material: {}, geometry: {} }}
          onChange={handleChange}
          onRun={runSim}
          onReset={handleReset}
          running={running}
          asyncRunning={taskState && ['queued', 'running'].includes(taskState.status)}
          simMode={simMode}
          defects={defects}
          onDefectsChange={setDefects}
          initialDamage={initialDamage}
          onInitialDamageChange={setInitialDamage}
          defectRadius={defectRadius}
          onDefectRadiusChange={setDefectRadius}
        />

        {taskState && (
          <ProgressPanel
            task={taskState}
            onCancel={doCancel}
          />
        )}

        {error && (
          <div className="error-box">
            <div className="error-title">求解错误</div>
            <div className="error-body">{error}</div>
          </div>
        )}
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="tabs">
            {['dashboard', 'stress', 'damage'].map((t) => (
              <button
                key={t}
                className={`tab ${activeTab === t ? 'active' : ''}`}
                onClick={() => setActiveTab(t)}
              >
                {t === 'dashboard' ? '总览 Dashboard' : t === 'stress' ? '应力时空场' : '损伤演化'}
              </button>
            ))}
          </div>
          <div className="topbar-right">
            <div className={`chip ${simModeFinal}`}>
              <span className="chip-dot" />
              {simModeFinal === 'quasi_static'
                ? '长时准静态 · 24h蠕变'
                : '瞬态波动 · 冲击加载'}
            </div>
            {!result && <div className="chip warn">等待仿真运行…</div>}
            {defects.length > 0 && (
              <div className="chip" style={{ borderColor: 'rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.08)', color: '#fca5a5' }}>
                <span className="chip-dot" />
                {defects.length} 个缺陷点
              </div>
            )}
            {result && (
              <div className="chip">
                <span className="chip-dot done" />
                共 {result.n_frames || result.frames?.length || 0} 帧 · dx {simSummary?.dx_mm?.toFixed?.(1) || formatNumber(simSummary?.dx_mm || 0)} mm
              </div>
            )}
          </div>
        </div>

        {!result ? (
          <div className="empty">
            <div className="empty-illust" />
            <div className="empty-title">
              {simMode === 'quasi_static'
                ? '24小时纤维网格蠕变损伤仿真'
                : '1D 阻尼波动方程 · 轴向应力传播'}
            </div>
            <div className="empty-sub">
              {simMode === 'quasi_static'
                ? '左侧选择【长时准静态模式】，调整蠕变参数后点击▶ 运行仿真 — 后台异步执行，前端实时显示进度，永不 504'
                : '左侧参数面板调整材料/几何/加载条件，点击▶ 运行仿真即可获得完整时空应力图谱'}
            </div>
            {simMode === 'quasi_static' && (
              <div className="empty-hints">
                <div>⏱ 典型 24h 仿真耗时 <b>~150ms</b></div>
                <div>🧵 纤维随机起伏 + Kachanov 蠕变损伤演化</div>
                <div>📡 HTTP 提交后立即返回 task_id，后台执行</div>
                <div style={{ gridColumn: '1 / -1', color: 'var(--amber)', marginTop: 4 }}>
                  💡 在左侧【几何与加载参数】中可点击网格添加纤维缺陷点
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="dashboard">
            <SummaryCards summary={simSummary} />

            <div className="panel">
              <div className="panel-title">
                <span>动画播放器</span>
                <span className="panel-title-right">
                  {formatNumber(result.frames?.length || 0)} 帧 · 步长 {formatNumber(simSummary?.mean_dt_seconds || 0)}s
                </span>
              </div>
              <AnimationPlayer
                frames={result.frames || []}
                xAxis={result.x_axis}
                tAxis={result.t_axis}
                tTotalSec={simSummary?.total_time_us ? simSummary.total_time_us * 1e-6 : simSummary.total_time_hours * 3600}
                simMode={simModeFinal}
              />
            </div>

            {activeTab === 'dashboard' && (
              <>
                <div className="panel heatmap-panel">
                  <div className="panel-title">
                    <span>应力 σ(x,t) 时空分布</span>
                    <span className="panel-title-right">
                      峰值 ≈ {formatSci(simSummary?.max_stress_MPa || 0)} MPa
                    </span>
                  </div>
                  <StressHeatmap
                    data={result.heatmap_stress}
                    colorMode="viridis"
                    label="应力 σ (MPa)"
                    width={HEATMAP_W}
                    height={HEATMAP_H}
                  />
                </div>

                <div className="panel heatmap-panel">
                  <div className="panel-title">
                    <span>损伤 D(x,t) 时空分布</span>
                    <span className="panel-title-right">
                      最大 D = {formatNumber(simSummary?.max_damage || 0)}
                    </span>
                  </div>
                  <StressHeatmap
                    data={result.heatmap_damage}
                    colorMode="damage"
                    label="损伤变量 D"
                    width={HEATMAP_W}
                    height={HEATMAP_H}
                  />
                </div>

                <div className="panel">
                  <div className="panel-title">应力 - 应变曲线</div>
                  <StressStrainChart data={result.views?.stress_strain} />
                </div>
              </>
            )}

            {activeTab === 'stress' && (
              <div className="charts-grid">
                <div className="panel">
                  <div className="panel-title">应力 σ(x,t) 时空分布</div>
                  <StressHeatmap
                    data={result.heatmap_stress}
                    colorMode="viridis"
                    label="应力 σ (MPa)"
                    width={HEATMAP_W + 40}
                    height={HEATMAP_H + 40}
                  />
                </div>
                <div className="panel">
                  <div className="panel-title">应力时间序列（关键点）</div>
                  <TimeSeriesChart data={result.views?.time_series_stress} label="σ (MPa)" color="#22d3ee" />
                </div>
                <div className="panel">
                  <div className="panel-title">典型时刻应力剖面</div>
                  <SpatialProfileChart data={result.views?.spatial_stress} label="σ (MPa)" color="#22d3ee" />
                </div>
                <div className="panel">
                  <div className="panel-title">应力 - 应变曲线</div>
                  <StressStrainChart data={result.views?.stress_strain} />
                </div>
              </div>
            )}

            {activeTab === 'damage' && (
              <div className="charts-grid">
                <div className="panel">
                  <div className="panel-title">损伤 D(x,t) 时空分布</div>
                  <StressHeatmap
                    data={result.heatmap_damage}
                    colorMode="damage"
                    label="损伤 D"
                    width={HEATMAP_W + 40}
                    height={HEATMAP_H + 40}
                  />
                </div>
                <div className="panel">
                  <div className="panel-title">损伤时间序列（关键点）</div>
                  <TimeSeriesChart data={result.views?.time_series_damage} label="D" color="#fb923c" />
                </div>
                <div className="panel">
                  <div className="panel-title">典型时刻损伤剖面</div>
                  <SpatialProfileChart data={result.views?.spatial_damage} label="D" color="#fb923c" />
                </div>
                <div className="panel">
                  <div className="panel-title">损伤演化曲线（全局指标）</div>
                  <DamageEvolutionChart data={result.views?.damage_evolution} />
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}

function ProgressPanel({ task, onCancel }) {
  const {
    status, progress_pct = 0, message = '', task_id, live_stats,
    _start, _finish,
  } = task

  const elapsedMs = _start
    ? (_finish || Date.now()) - _start
    : 0
  const elapsed = (elapsedMs / 1000).toFixed(1)

  const statusColor =
    status === 'done' ? 'done'
    : status === 'error' ? 'error'
    : status === 'cancelled' ? 'cancelled'
    : ''

  const stats = live_stats || {}

  return (
    <div className="progress-panel">
      <div className="progress-head">
        <div className="progress-task-id">{task_id || '…'}</div>
        <div className="progress-pct" style={{
          color: status === 'done' ? 'var(--cyan)'
                 : status === 'error' ? 'var(--red)'
                 : status === 'cancelled' ? 'var(--amber)'
                 : undefined,
        }}>
          {progress_pct}%
        </div>
      </div>
      <div className="progress-bar">
        <div
          className={`progress-fill ${statusColor}`}
          style={{ width: `${Math.min(100, progress_pct)}%` }}
        />
      </div>
      <div className="progress-msg">{message || '等待执行…'}</div>
      <div className="progress-stats">
        <div className="progress-stat">
          <b>{elapsed}s</b>
          已用时
        </div>
        <div className="progress-stat">
          <b>{stats.step || '-'}</b>
          步进次数
        </div>
        <div className="progress-stat">
          <b>{stats.max_stress_MPa != null ? formatNumber(stats.max_stress_MPa) : '-'}</b>
          实时 σ_max (MPa)
        </div>
      </div>
      {['queued', 'running'].includes(status) && (
        <div className="progress-actions">
          <button className="btn-cancel" onClick={onCancel}>
            取消任务
          </button>
        </div>
      )}
    </div>
  )
}
