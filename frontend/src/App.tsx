import { useState } from 'react'
import { FileUpload } from './components/FileUpload'
import { JobStatus } from './components/JobStatus'
import { SceneGraphViewer } from './components/SceneGraphViewer'
import { SubstitutionPanel } from './components/SubstitutionPanel'
import { ResultsPanel } from './components/ResultsPanel'
import { useJobStore } from './store/jobStore'
import { Layers, FileCode, Cpu, Settings, Download } from 'lucide-react'

type Tab = 'upload' | 'scene' | 'substitute' | 'results'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('upload')
  const { currentJob } = useJobStore()

  const tabs = [
    { id: 'upload', label: 'Upload', icon: FileCode, enabled: true },
    { id: 'scene', label: 'Scene Graph', icon: Layers, enabled: !!currentJob?.scene_graph_id },
    { id: 'substitute', label: 'Substitute', icon: Settings, enabled: currentJob?.status === 'complete' },
    { id: 'results', label: 'Results', icon: Download, enabled: currentJob?.status === 'complete' },
  ] as const

  return (
    <div className="min-h-screen grid-pattern">
      {/* Header */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <Cpu className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-display font-bold text-white">PlanMod</h1>
              <p className="text-xs text-[var(--color-text-muted)]">Drawing → DXF Pipeline</p>
            </div>
          </div>
          
          {currentJob && (
            <div className="flex items-center gap-4">
              <JobStatus job={currentJob} />
            </div>
          )}
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="border-b border-[var(--color-border)] bg-[var(--color-surface)]/50">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => tab.enabled && setActiveTab(tab.id)}
                  disabled={!tab.enabled}
                  className={`
                    px-4 py-3 flex items-center gap-2 text-sm font-medium
                    border-b-2 transition-all
                    ${activeTab === tab.id 
                      ? 'border-indigo-500 text-indigo-400' 
                      : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}
                    ${!tab.enabled && 'opacity-40 cursor-not-allowed'}
                  `}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'upload' && <FileUpload onJobCreated={() => setActiveTab('upload')} />}
        {activeTab === 'scene' && <SceneGraphViewer />}
        {activeTab === 'substitute' && <SubstitutionPanel />}
        {activeTab === 'results' && <ResultsPanel />}
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)]/30 mt-auto">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <p className="text-xs text-[var(--color-text-muted)] text-center">
            PlanMod v0.1.0 • AI-powered drawing to DXF conversion
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App


