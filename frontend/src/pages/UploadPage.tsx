import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { 
  Upload, 
  X, 
  FileText, 
  Loader2, 
  FolderUp,
  CheckCircle,
  Info,
  Sparkles,
  FileUp,
  Trash2,
} from 'lucide-react';
import { useCreateBatch } from '../hooks/useQueue';
import type { UploadOptions } from '../types';

export function UploadPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [batchName, setBatchName] = useState('');
  const [useMarkers, setUseMarkers] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  
  const createBatch = useCreateBatch();
  
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const docxFiles = acceptedFiles.filter(f => f.name.endsWith('.docx'));
    setFiles(prev => {
      const newFiles = [...prev];
      docxFiles.forEach(file => {
        if (!newFiles.some(f => f.name === file.name && f.size === file.size)) {
          newFiles.push(file);
        }
      });
      return newFiles;
    });
  }, []);
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: true,
  });
  
  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };
  
  const handleSubmit = async () => {
    if (files.length === 0) return;
    
    const options: UploadOptions = {
      document_type: "Medical Textbook",
      use_markers: useMarkers,
      batch_name: batchName,
    };
    
    try {
      const result = await createBatch.mutateAsync({ files, options });
      setUploadSuccess(true);
      // Redirect immediately to batch detail page
      navigate(`/batches/${result.batch.batch_id}`);
    } catch (error) {
      console.error('Error creating batch:', error);
    }
  };
  
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  const totalSize = files.reduce((acc, f) => acc + f.size, 0);
  
  if (uploadSuccess) {
    return (
      <div className="max-w-2xl mx-auto py-24 text-center">
        <div className="relative">
          <div className="w-24 h-24 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-2xl shadow-emerald-500/30">
            <CheckCircle className="h-12 w-12 text-white" />
          </div>
          <div className="absolute inset-0 w-24 h-24 mx-auto rounded-3xl bg-gradient-to-br from-emerald-400 to-teal-500 animate-ping opacity-20" />
        </div>
        <h2 className="text-2xl font-bold text-slate-800 mb-2">
          Documents Queued Successfully!
        </h2>
        <p className="text-slate-500">
          Redirecting to batch details...
        </p>
      </div>
    );
  }
  
  return (
    <div className="max-w-5xl mx-auto">
      {/* Page Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-xl bg-gradient-to-br from-amber-100 to-orange-100">
            <Sparkles className="h-5 w-5 text-amber-600" />
          </div>
          <span className="px-3 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-700 uppercase tracking-wider">
            AI Processing
          </span>
        </div>
        <h1 className="text-2xl font-bold text-slate-800">Process Documents</h1>
        <p className="text-slate-500 mt-1">
          Upload DOCX files for intelligent structural analysis and tagging
        </p>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Main Upload Area - Spans 3 columns */}
        <div className="lg:col-span-3 space-y-6">
          {/* Dropzone Card */}
          <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden">
            <div className="p-6">
              <div
                {...getRootProps()}
                className={`
                  relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer
                  transition-all duration-300
                  ${isDragActive 
                    ? 'border-amber-400 bg-gradient-to-br from-amber-50 to-orange-50' 
                    : 'border-slate-200 hover:border-amber-300 hover:bg-slate-50'}
                `}
              >
                <input {...getInputProps()} />
                
                <div className={`
                  w-20 h-20 mx-auto mb-6 rounded-2xl flex items-center justify-center transition-all
                  ${isDragActive 
                    ? 'bg-gradient-to-br from-amber-400 to-orange-500 shadow-lg shadow-amber-500/30 scale-110' 
                    : 'bg-slate-100'}
                `}>
                  <FolderUp className={`h-10 w-10 ${isDragActive ? 'text-white' : 'text-slate-400'}`} />
                </div>
                
                <p className="text-lg font-semibold text-slate-700 mb-2">
                  {isDragActive ? 'Drop files here' : 'Drag and drop files'}
                </p>
                <p className="text-sm text-slate-500 mb-4">
                  or click to browse from your computer
                </p>
                <p className="text-xs text-slate-400">
                  Supports .docx files only
                </p>
              </div>
            </div>
            
            {/* File List */}
            {files.length > 0 && (
              <div className="border-t border-slate-100">
                <div className="px-6 py-4 bg-slate-50 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileUp className="h-5 w-5 text-slate-400" />
                    <span className="font-medium text-slate-700">
                      {files.length} file{files.length > 1 ? 's' : ''} selected
                    </span>
                    <span className="text-sm text-slate-500">
                      ({formatFileSize(totalSize)})
                    </span>
                  </div>
                  <button
                    onClick={() => setFiles([])}
                    className="flex items-center gap-1.5 text-sm font-medium text-red-600 hover:text-red-700 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                    Clear all
                  </button>
                </div>
                
                <div className="max-h-64 overflow-y-auto divide-y divide-slate-100">
                  {files.map((file, index) => (
                    <div
                      key={`${file.name}-${index}`}
                      className="flex items-center justify-between px-6 py-3 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-lg bg-slate-100">
                          <FileText className="h-4 w-4 text-slate-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-700 truncate">{file.name}</p>
                          <p className="text-xs text-slate-400">{formatFileSize(file.size)}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => removeFile(index)}
                        className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={files.length === 0 || createBatch.isPending}
            className="w-full py-4 px-6 rounded-2xl font-semibold text-lg
                     transition-all duration-300 flex items-center justify-center gap-3
                     disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
                     bg-gradient-to-r from-slate-800 to-slate-900 text-white
                     hover:from-slate-700 hover:to-slate-800
                     shadow-xl shadow-slate-900/20 hover:shadow-slate-900/30
                     hover:-translate-y-0.5"
          >
            {createBatch.isPending ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Processing Upload...
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5" />
                Start AI Processing
                {files.length > 0 && (
                  <span className="ml-1 px-2 py-0.5 text-sm rounded-full bg-white/20">
                    {files.length} files
                  </span>
                )}
              </>
            )}
          </button>
          
          {createBatch.isError && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3">
              <div className="p-1 rounded-full bg-red-100">
                <X className="h-4 w-4 text-red-600" />
              </div>
              <div>
                <p className="font-medium text-red-800">Upload Failed</p>
                <p className="text-sm text-red-600">{(createBatch.error as Error).message}</p>
              </div>
            </div>
          )}
        </div>
        
        {/* Settings Panel - Spans 2 columns */}
        <div className="lg:col-span-2 space-y-6">
          {/* Batch Name */}
          <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm p-5">
            <label className="block text-sm font-semibold text-slate-700 mb-3">
              Batch Name
              <span className="font-normal text-slate-400 ml-1">(optional)</span>
            </label>
            <input
              type="text"
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="e.g., Chapter 1-5, Medical Review"
              className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50
                       focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400
                       transition-all placeholder:text-slate-400"
            />
          </div>
          
          {/* Output Format */}
          <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm p-5">
            <label className="block text-sm font-semibold text-slate-700 mb-3">
              Output Format
            </label>
            <div className="space-y-2">
              <label className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                !useMarkers ? 'border-amber-400 bg-amber-50/50' : 'border-transparent bg-slate-50 hover:bg-slate-100'
              }`}>
                <input
                  type="radio"
                  checked={!useMarkers}
                  onChange={() => setUseMarkers(false)}
                  className="sr-only"
                />
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                  !useMarkers ? 'border-amber-500 bg-amber-500' : 'border-slate-300'
                }`}>
                  {!useMarkers && <div className="w-2 h-2 rounded-full bg-white" />}
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">Word Styles</p>
                  <p className="text-xs text-slate-500">Recommended for most use cases</p>
                </div>
              </label>
              
              <label className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                useMarkers ? 'border-amber-400 bg-amber-50/50' : 'border-transparent bg-slate-50 hover:bg-slate-100'
              }`}>
                <input
                  type="radio"
                  checked={useMarkers}
                  onChange={() => setUseMarkers(true)}
                  className="sr-only"
                />
                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                  useMarkers ? 'border-amber-500 bg-amber-500' : 'border-slate-300'
                }`}>
                  {useMarkers && <div className="w-2 h-2 rounded-full bg-white" />}
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">XML Markers</p>
                  <p className="text-xs text-slate-500">Legacy format with inline tags</p>
                </div>
              </label>
            </div>
          </div>
          
          {/* Info Box */}
          <div className="p-4 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200/50">
            <div className="flex gap-3">
              <div className="p-2 rounded-lg bg-blue-100">
                <Info className="h-4 w-4 text-blue-600" />
              </div>
              <div className="text-sm">
                <p className="font-medium text-blue-800">Processing Time</p>
                <p className="text-blue-600 mt-1">
                  Each document takes 30-60 seconds depending on length and complexity.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
