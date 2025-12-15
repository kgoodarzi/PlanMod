import { useState } from 'react'
import { Download, FileText, Image, FileCode, ExternalLink, Loader2 } from 'lucide-react'
import { useJobStore } from '../store/jobStore'

export function ResultsPanel() {
  const { currentJob, getDownloadUrl } = useJobStore()
  const [downloading, setDownloading] = useState<string | null>(null)

  const handleDownload = async (fileType: string) => {
    if (!currentJob) return
    
    setDownloading(fileType)
    try {
      const url = await getDownloadUrl(currentJob.id, fileType)
      window.open(url, '_blank')
    } catch (err) {
      console.error('Download failed:', err)
    } finally {
      setDownloading(null)
    }
  }

  const downloadOptions = [
    {
      id: 'base_dxf',
      label: 'Base DXF',
      description: 'Original vectorized drawing',
      icon: FileCode,
      color: 'text-blue-400',
    },
    {
      id: 'final_dxf',
      label: 'Final DXF',
      description: 'With substitutions applied',
      icon: FileCode,
      color: 'text-green-400',
    },
    {
      id: 'scene_graph',
      label: 'Scene Graph',
      description: 'JSON structure data',
      icon: FileText,
      color: 'text-purple-400',
    },
    {
      id: 'visualization',
      label: 'Visualization',
      description: 'Scene graph image',
      icon: Image,
      color: 'text-yellow-400',
    },
    {
      id: 'report',
      label: 'Report',
      description: 'Processing summary',
      icon: FileText,
      color: 'text-indigo-400',
    },
  ]

  if (!currentJob || currentJob.status !== 'complete') {
    return (
      <div className="text-center py-16">
        <Download className="w-12 h-12 mx-auto text-[var(--color-text-muted)] mb-4" />
        <p className="text-[var(--color-text-muted)]">Processing must complete before downloading results</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-2 mb-6">
        <Download className="w-5 h-5 text-indigo-400" />
        <h2 className="text-lg font-display font-semibold">Download Results</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {downloadOptions.map((option) => {
          const Icon = option.icon
          const isDownloading = downloading === option.id
          
          return (
            <button
              key={option.id}
              onClick={() => handleDownload(option.id)}
              disabled={isDownloading}
              className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4 text-left hover:bg-[var(--color-surface-hover)] hover:border-indigo-500/30 transition-all group"
            >
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg bg-[var(--color-bg)] ${option.color}`}>
                  {isDownloading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{option.label}</span>
                    <ExternalLink className="w-3 h-3 text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
                    {option.description}
                  </p>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Job Summary */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 mt-8">
        <h3 className="font-medium mb-4">Job Summary</h3>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-[var(--color-text-muted)]">Job ID</dt>
            <dd className="font-mono">{currentJob.id.slice(0, 8)}...</dd>
          </div>
          <div>
            <dt className="text-[var(--color-text-muted)]">Status</dt>
            <dd className="text-green-400 capitalize">{currentJob.status}</dd>
          </div>
          <div>
            <dt className="text-[var(--color-text-muted)]">Stage</dt>
            <dd>{currentJob.current_stage}</dd>
          </div>
          <div>
            <dt className="text-[var(--color-text-muted)]">Progress</dt>
            <dd>{currentJob.progress_percent}%</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}


