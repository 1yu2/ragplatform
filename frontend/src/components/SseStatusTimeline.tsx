import type { SseState } from '../lib/types'

const ORDER: SseState[] = ['queued', 'retrieving', 'analyzing', 'generating', 'uploading', 'done', 'failed']

const STATE_LABEL: Record<SseState, string> = {
  queued: '已排队',
  retrieving: '检索中',
  analyzing: '分析中',
  generating: '生成中',
  uploading: '上传中',
  done: '已完成',
  failed: '失败',
}

export function SseStatusTimeline({ states }: { states: SseState[] }) {
  return (
    <div className="card">
      <h3>任务时间线</h3>
      <ul className="timeline">
        {ORDER.map((s) => (
          <li key={s} className={states.includes(s) ? 'hit' : ''}>
            <span className="dot" />
            <span>{STATE_LABEL[s]}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
