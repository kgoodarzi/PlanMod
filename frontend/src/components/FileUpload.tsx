import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, AlertCircle, Loader2, Play } from 'lucide-react'
import { useJobStore } from '../store/jobStore'

interface FileUploadProps {
  onJobCreated: () => void
}

export function FileUpload({ onJobCreated }: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const { createJob, uploadFile, startProcessing, currentJob, isLoading, error, setError } = useJobStore()

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0])
      setError(null)
    }
  }, [setError])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'application/dxf': ['.dxf'],
      'application/acad': ['.dwg'],
    },
    maxFiles: 1,
  })

  const handleUpload = async () => {
    if (!selectedFile) return

    try {
      const fileType = selectedFile.name.split('.').pop()?.toLowerCase() || 'unknown'
      const { jobId } = await createJob(selectedFile.name, fileType)
      await uploadFile(jobId, selectedFile)
      await startProcessing(jobId)
      onJobCreated()
    } catch (err) {
      console.error('Upload failed:', err)
    }
  }

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    const colors: Record<string, string> = {
      pdf: 'text-red-400',
      png: 'text-green-400',
      jpg: 'text-green-400',
      jpeg: 'text-green-400',
      dxf: 'text-blue-400',
      dwg: 'text-purple-400',
    }
    return colors[ext || ''] || 'text-gray-400'
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Upload Area */}
      <div
        {...getRootProps()}
        className={`
          relative border-2 border-dashed rounded-xl p-12
          transition-all cursor-pointer
          ${isDragActive 
            ? 'border-indigo-500 bg-indigo-500/10' 
            : 'border-[var(--color-border)] hover:border-indigo-500/50 hover:bg-[var(--color-surface)]'}
        `}
      >
        <input {...getInputProps()} />
        
        <div className="flex flex-col items-center gap-4 text-center">
          <div className={`
            w-16 h-16 rounded-full flex items-center justify-center
            ${isDragActive ? 'bg-indigo-500/20' : 'bg-[var(--color-surface)]'}
          `}>
            <Upload className={`w-8 h-8 ${isDragActive ? 'text-indigo-400' : 'text-[var(--color-text-muted)]'}`} />
          </div>
          
          <div>
            <p className="text-lg font-medium">
              {isDragActive ? 'Drop your file here' : 'Drag & drop your drawing'}
            </p>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              or click to browse • PDF, PNG, JPG, DXF, DWG
            </p>
          </div>
        </div>
      </div>

      {/* Selected File */}
      {selectedFile && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
          <div className="flex items-center gap-3">
            <FileText className={`w-8 h-8 ${getFileIcon(selectedFile.name)}`} />
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{selectedFile.name}</p>
              <p className="text-sm text-[var(--color-text-muted)]">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              onClick={handleUpload}
              disabled={isLoading}
              className={`
                px-6 py-2.5 rounded-lg font-medium flex items-center gap-2
                transition-all
                ${isLoading
                  ? 'bg-indigo-500/50 cursor-not-allowed'
                  : 'bg-indigo-500 hover:bg-indigo-400'}
              `}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Processing
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-400">Error</p>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Processing Status */}
      {currentJob && currentJob.status !== 'pending' && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <span className="font-medium">Processing Status</span>
            <span className={`
              px-2 py-1 rounded text-xs font-medium
              ${currentJob.status === 'complete' ? 'bg-green-500/20 text-green-400' : ''}
              ${currentJob.status === 'failed' ? 'bg-red-500/20 text-red-400' : ''}
              ${!['complete', 'failed'].includes(currentJob.status) ? 'bg-indigo-500/20 text-indigo-400' : ''}
            `}>
              {currentJob.status}
            </span>
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-[var(--color-text-muted)]">{currentJob.current_stage}</span>
              <span>{currentJob.progress_percent}%</span>
            </div>
            <div className="h-2 bg-[var(--color-bg)] rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
                style={{ width: `${currentJob.progress_percent}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Supported Formats Info */}
      <div className="text-center text-sm text-[var(--color-text-muted)]">
        <p>Supported formats: PDF, PNG, JPG, DXF, DWG</p>
        <p className="mt-1">Max file size: 50MB • Processing time varies by complexity</p>
      </div>
    </div>
  )
}


