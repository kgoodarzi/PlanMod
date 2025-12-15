import { create } from 'zustand'
import { api } from '../services/api'

export interface Job {
  id: string
  status: string
  current_stage: string
  progress_percent: number
  error_message?: string
  scene_graph_id?: string
}

export interface SceneGraph {
  job_id: string
  scene_graph_id: string
  views: Array<{
    id: string
    name: string
    type: string
    confidence: number
  }>
  components: Array<{
    id: string
    name: string
    type: string
    confidence: number
  }>
  visualization_url?: string
}

interface JobState {
  currentJob: Job | null
  sceneGraph: SceneGraph | null
  isLoading: boolean
  error: string | null
  
  createJob: (fileName: string, fileType: string) => Promise<{ jobId: string; uploadUrl: string }>
  uploadFile: (jobId: string, file: File) => Promise<void>
  startProcessing: (jobId: string) => Promise<void>
  fetchJobStatus: (jobId: string) => Promise<void>
  fetchSceneGraph: (jobId: string) => Promise<void>
  applySubstitutions: (jobId: string, rules: any[]) => Promise<void>
  getDownloadUrl: (jobId: string, fileType: string) => Promise<string>
  setError: (error: string | null) => void
  reset: () => void
}

export const useJobStore = create<JobState>((set, get) => ({
  currentJob: null,
  sceneGraph: null,
  isLoading: false,
  error: null,
  
  createJob: async (fileName, fileType) => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.createJob(fileName, fileType)
      set({ 
        currentJob: { 
          id: response.job_id, 
          status: 'pending',
          current_stage: 'created',
          progress_percent: 0,
        },
        isLoading: false,
      })
      return { jobId: response.job_id, uploadUrl: response.upload_url }
    } catch (err: any) {
      set({ error: err.message, isLoading: false })
      throw err
    }
  },
  
  uploadFile: async (jobId, file) => {
    set({ isLoading: true, error: null })
    try {
      await api.uploadFile(jobId, file)
      await get().fetchJobStatus(jobId)
      set({ isLoading: false })
    } catch (err: any) {
      set({ error: err.message, isLoading: false })
      throw err
    }
  },
  
  startProcessing: async (jobId) => {
    set({ isLoading: true, error: null })
    try {
      await api.startProcessing(jobId)
      // Start polling for status
      const pollStatus = async () => {
        const job = get().currentJob
        if (job && !['complete', 'failed'].includes(job.status)) {
          await get().fetchJobStatus(jobId)
          setTimeout(pollStatus, 2000)
        }
      }
      pollStatus()
      set({ isLoading: false })
    } catch (err: any) {
      set({ error: err.message, isLoading: false })
      throw err
    }
  },
  
  fetchJobStatus: async (jobId) => {
    try {
      const response = await api.getJobStatus(jobId)
      set({ 
        currentJob: {
          id: jobId,
          status: response.status,
          current_stage: response.current_stage,
          progress_percent: response.progress_percent,
          error_message: response.error_message,
          scene_graph_id: get().currentJob?.scene_graph_id,
        },
      })
      
      // Fetch scene graph when available
      if (response.status === 'complete' || response.current_stage.includes('scene_graph')) {
        try {
          await get().fetchSceneGraph(jobId)
        } catch {
          // Scene graph might not be ready yet
        }
      }
    } catch (err: any) {
      set({ error: err.message })
    }
  },
  
  fetchSceneGraph: async (jobId) => {
    try {
      const response = await api.getSceneGraph(jobId)
      set({ 
        sceneGraph: response,
        currentJob: {
          ...get().currentJob!,
          scene_graph_id: response.scene_graph_id,
        },
      })
    } catch (err: any) {
      // Scene graph might not be ready yet
      console.warn('Scene graph not available:', err.message)
    }
  },
  
  applySubstitutions: async (jobId, rules) => {
    set({ isLoading: true, error: null })
    try {
      await api.applySubstitutions(jobId, rules)
      // Poll for completion
      const pollStatus = async () => {
        const job = get().currentJob
        if (job && job.status === 'transforming') {
          await get().fetchJobStatus(jobId)
          setTimeout(pollStatus, 2000)
        }
      }
      pollStatus()
      set({ isLoading: false })
    } catch (err: any) {
      set({ error: err.message, isLoading: false })
      throw err
    }
  },
  
  getDownloadUrl: async (jobId, fileType) => {
    const response = await api.getDownloadUrl(jobId, fileType)
    return response.download_url
  },
  
  setError: (error) => set({ error }),
  
  reset: () => set({ currentJob: null, sceneGraph: null, isLoading: false, error: null }),
}))


