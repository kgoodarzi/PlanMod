import { CheckCircle, AlertCircle, Loader2, Clock } from 'lucide-react'
import type { Job } from '../store/jobStore'

interface JobStatusProps {
  job: Job
}

export function JobStatus({ job }: JobStatusProps) {
  const getStatusIcon = () => {
    switch (job.status) {
      case 'complete':
        return <CheckCircle className="w-4 h-4 text-green-400" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-400" />
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-400" />
      default:
        return <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
    }
  }

  const getStatusColor = () => {
    switch (job.status) {
      case 'complete':
        return 'bg-green-500/20 text-green-400'
      case 'failed':
        return 'bg-red-500/20 text-red-400'
      case 'pending':
        return 'bg-yellow-500/20 text-yellow-400'
      default:
        return 'bg-indigo-500/20 text-indigo-400'
    }
  }

  return (
    <div className="flex items-center gap-3">
      <div className={`px-3 py-1.5 rounded-lg flex items-center gap-2 ${getStatusColor()}`}>
        {getStatusIcon()}
        <span className="text-sm font-medium capitalize">{job.status}</span>
      </div>
      
      {!['complete', 'failed', 'pending'].includes(job.status) && (
        <div className="flex items-center gap-2">
          <div className="w-24 h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
            <div 
              className="h-full bg-indigo-500 transition-all"
              style={{ width: `${job.progress_percent}%` }}
            />
          </div>
          <span className="text-xs text-[var(--color-text-muted)]">
            {job.progress_percent}%
          </span>
        </div>
      )}
    </div>
  )
}


