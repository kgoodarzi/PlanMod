import { useEffect } from 'react'
import { Eye, Layers, Box, AlertTriangle, RefreshCw } from 'lucide-react'
import { useJobStore } from '../store/jobStore'

export function SceneGraphViewer() {
  const { currentJob, sceneGraph, fetchSceneGraph, isLoading } = useJobStore()

  useEffect(() => {
    if (currentJob?.id && !sceneGraph) {
      fetchSceneGraph(currentJob.id)
    }
  }, [currentJob?.id, sceneGraph, fetchSceneGraph])

  if (!sceneGraph) {
    return (
      <div className="text-center py-16">
        <Layers className="w-12 h-12 mx-auto text-[var(--color-text-muted)] mb-4" />
        <p className="text-[var(--color-text-muted)]">Scene graph not available yet</p>
        {currentJob && (
          <button
            onClick={() => fetchSceneGraph(currentJob.id)}
            className="mt-4 px-4 py-2 text-sm bg-[var(--color-surface)] rounded-lg hover:bg-[var(--color-surface-hover)] flex items-center gap-2 mx-auto"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Visualization */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center gap-2">
          <Eye className="w-4 h-4 text-indigo-400" />
          <span className="font-medium">Visualization</span>
        </div>
        <div className="p-4">
          {sceneGraph.visualization_url ? (
            <img 
              src={sceneGraph.visualization_url} 
              alt="Scene Graph Visualization"
              className="w-full rounded-lg"
            />
          ) : (
            <div className="aspect-video bg-[var(--color-bg)] rounded-lg flex items-center justify-center">
              <p className="text-[var(--color-text-muted)]">Visualization not available</p>
            </div>
          )}
        </div>
      </div>

      {/* Components List */}
      <div className="space-y-6">
        {/* Views */}
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl">
          <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center gap-2">
            <Layers className="w-4 h-4 text-green-400" />
            <span className="font-medium">Views ({sceneGraph.views.length})</span>
          </div>
          <div className="p-4 space-y-2 max-h-64 overflow-y-auto">
            {sceneGraph.views.map((view) => (
              <div 
                key={view.id}
                className="flex items-center justify-between p-3 bg-[var(--color-bg)] rounded-lg"
              >
                <div>
                  <p className="font-medium">{view.name}</p>
                  <p className="text-sm text-[var(--color-text-muted)]">{view.type}</p>
                </div>
                <span className="text-sm text-[var(--color-text-muted)]">
                  {(view.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
            {sceneGraph.views.length === 0 && (
              <p className="text-[var(--color-text-muted)] text-center py-4">No views detected</p>
            )}
          </div>
        </div>

        {/* Components */}
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl">
          <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center gap-2">
            <Box className="w-4 h-4 text-blue-400" />
            <span className="font-medium">Components ({sceneGraph.components.length})</span>
          </div>
          <div className="p-4 space-y-2 max-h-64 overflow-y-auto">
            {sceneGraph.components.map((component) => (
              <div 
                key={component.id}
                className="flex items-center justify-between p-3 bg-[var(--color-bg)] rounded-lg"
              >
                <div>
                  <p className="font-medium">{component.name || component.id.slice(0, 8)}</p>
                  <p className="text-sm text-[var(--color-text-muted)]">{component.type}</p>
                </div>
                <span className={`
                  text-sm px-2 py-0.5 rounded
                  ${component.confidence >= 0.8 ? 'bg-green-500/20 text-green-400' : ''}
                  ${component.confidence >= 0.5 && component.confidence < 0.8 ? 'bg-yellow-500/20 text-yellow-400' : ''}
                  ${component.confidence < 0.5 ? 'bg-red-500/20 text-red-400' : ''}
                `}>
                  {(component.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
            {sceneGraph.components.length === 0 && (
              <p className="text-[var(--color-text-muted)] text-center py-4">No components detected</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


