import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const api = {
  async createJob(fileName: string, fileType: string) {
    const response = await client.post('/jobs', {
      file_name: fileName,
      file_type: fileType,
    })
    return response.data
  },
  
  async uploadFile(jobId: string, file: File) {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await client.post(`/jobs/${jobId}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
  
  async startProcessing(jobId: string) {
    const response = await client.post(`/jobs/${jobId}/process`)
    return response.data
  },
  
  async getJobStatus(jobId: string) {
    const response = await client.get(`/jobs/${jobId}`)
    return response.data
  },
  
  async getSceneGraph(jobId: string) {
    const response = await client.get(`/jobs/${jobId}/scene-graph`)
    return response.data
  },
  
  async applySubstitutions(jobId: string, rules: any[]) {
    const response = await client.post(`/jobs/${jobId}/substitute`, {
      job_id: jobId,
      rules,
    })
    return response.data
  },
  
  async getDownloadUrl(jobId: string, fileType: string) {
    const response = await client.get(`/jobs/${jobId}/download/${fileType}`)
    return response.data
  },
  
  async listComponents(category?: string) {
    const params = category ? { category } : {}
    const response = await client.get('/components', { params })
    return response.data
  },
  
  async listJobs(limit = 20) {
    const response = await client.get('/jobs', { params: { limit } })
    return response.data
  },
}


