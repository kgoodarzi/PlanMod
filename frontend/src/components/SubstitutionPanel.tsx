import { useState } from 'react'
import { Settings, Plus, Trash2, Play, Loader2 } from 'lucide-react'
import { useJobStore } from '../store/jobStore'

interface SubstitutionRule {
  id: string
  target_component_type?: string
  target_component_id?: string
  replacement_catalog_id?: string
  description: string
}

export function SubstitutionPanel() {
  const [rules, setRules] = useState<SubstitutionRule[]>([])
  const { currentJob, sceneGraph, applySubstitutions, isLoading } = useJobStore()

  const addRule = () => {
    setRules([
      ...rules,
      {
        id: crypto.randomUUID(),
        description: '',
      },
    ])
  }

  const removeRule = (id: string) => {
    setRules(rules.filter(r => r.id !== id))
  }

  const updateRule = (id: string, updates: Partial<SubstitutionRule>) => {
    setRules(rules.map(r => r.id === id ? { ...r, ...updates } : r))
  }

  const handleApply = async () => {
    if (!currentJob || rules.length === 0) return
    
    try {
      await applySubstitutions(currentJob.id, rules)
    } catch (err) {
      console.error('Failed to apply substitutions:', err)
    }
  }

  const componentTypes = [
    'rib', 'former', 'spar', 'stringer', 'bulkhead',
    'skin', 'fastener', 'hinge', 'motor', 'propeller',
  ]

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-display font-semibold">Component Substitutions</h2>
        </div>
        <button
          onClick={addRule}
          className="px-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-hover)] flex items-center gap-2 text-sm"
        >
          <Plus className="w-4 h-4" />
          Add Rule
        </button>
      </div>

      {/* Rules List */}
      <div className="space-y-4">
        {rules.map((rule, index) => (
          <div 
            key={rule.id}
            className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4"
          >
            <div className="flex items-start justify-between gap-4 mb-4">
              <span className="text-sm text-[var(--color-text-muted)]">Rule {index + 1}</span>
              <button
                onClick={() => removeRule(rule.id)}
                className="text-[var(--color-text-muted)] hover:text-red-400"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-[var(--color-text-muted)] mb-1">
                  Target Component Type
                </label>
                <select
                  value={rule.target_component_type || ''}
                  onChange={(e) => updateRule(rule.id, { target_component_type: e.target.value })}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Select type...</option>
                  {componentTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-[var(--color-text-muted)] mb-1">
                  Specific Component ID
                </label>
                <select
                  value={rule.target_component_id || ''}
                  onChange={(e) => updateRule(rule.id, { target_component_id: e.target.value })}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-indigo-500"
                >
                  <option value="">All of type</option>
                  {sceneGraph?.components
                    .filter(c => !rule.target_component_type || c.type === rule.target_component_type)
                    .map(c => (
                      <option key={c.id} value={c.id}>{c.name || c.id.slice(0, 8)}</option>
                    ))}
                </select>
              </div>

              <div className="col-span-2">
                <label className="block text-sm text-[var(--color-text-muted)] mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={rule.description}
                  onChange={(e) => updateRule(rule.id, { description: e.target.value })}
                  placeholder="e.g., Replace 1/8 spars with 3/16"
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          </div>
        ))}

        {rules.length === 0 && (
          <div className="text-center py-12 bg-[var(--color-surface)] border border-dashed border-[var(--color-border)] rounded-xl">
            <Settings className="w-8 h-8 mx-auto text-[var(--color-text-muted)] mb-2" />
            <p className="text-[var(--color-text-muted)]">No substitution rules defined</p>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">Add rules to modify components</p>
          </div>
        )}
      </div>

      {/* Apply Button */}
      {rules.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={handleApply}
            disabled={isLoading}
            className={`
              px-6 py-2.5 rounded-lg font-medium flex items-center gap-2
              ${isLoading
                ? 'bg-indigo-500/50 cursor-not-allowed'
                : 'bg-indigo-500 hover:bg-indigo-400'}
            `}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Apply Substitutions
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}


