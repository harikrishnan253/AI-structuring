import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, FileText, Loader2, FolderUp } from 'lucide-react';
import { useCreateBatch } from '../hooks/useQueue';
import type { DocumentType, UploadOptions } from '../types';

const DOCUMENT_TYPES: DocumentType[] = [
  'Academic Document',
  'Medical Textbook',
  'Research Paper',
  'Lab Manual',
  'Edwards Nursing Textbook',
];

interface FileUploadProps {
  onBatchCreated?: (batchId: string) => void;
}

export function FileUpload({ onBatchCreated }: FileUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [batchName, setBatchName] = useState('');
  const [documentType, setDocumentType] = useState<DocumentType>('Academic Document');
  const [useMarkers, setUseMarkers] = useState(false);
  
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
  
  const clearAll = () => {
    setFiles([]);
  };
  
  const handleSubmit = async () => {
    if (files.length === 0) return;
    
    const options: UploadOptions = {
      document_type: documentType,
      use_markers: useMarkers,
      batch_name: batchName || undefined,
    };
    
    try {
      const result = await createBatch.mutateAsync({ files, options });
      setFiles([]);
      setBatchName('');
      if (onBatchCreated && result.batch) {
        onBatchCreated(result.batch.batch_id);
      }
    } catch (error) {
      console.error('Error creating batch:', error);
    }
  };
  
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  return (
    <div className="bg-white rounded-xl border p-8" style={{ borderColor: '#e5e2dc' }}>
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg" style={{ backgroundColor: '#fef3c7' }}>
          <FolderUp className="h-5 w-5" style={{ color: '#d97706' }} />
        </div>
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#1e293b' }}>
            Upload Documents
          </h2>
          <p className="text-sm" style={{ color: '#64748b' }}>
            Drag and drop multiple DOCX files
          </p>
        </div>
      </div>
      
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
          transition-all duration-200
          ${isDragActive ? 'border-amber-500 bg-amber-50' : 'hover:border-amber-400 hover:bg-stone-50'}
        `}
        style={{ 
          borderColor: isDragActive ? '#d97706' : '#d1ccc3',
          background: isDragActive 
            ? 'linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%)' 
            : 'linear-gradient(180deg, #fafaf9 0%, #f5f4f1 100%)'
        }}
      >
        <input {...getInputProps()} />
        <div className="w-14 h-14 mx-auto mb-4 rounded-full flex items-center justify-center"
             style={{ backgroundColor: isDragActive ? '#fef3c7' : '#f1f5f9' }}>
          <Upload className="h-6 w-6" style={{ color: isDragActive ? '#d97706' : '#64748b' }} />
        </div>
        <p className="font-medium" style={{ color: '#334155' }}>
          {isDragActive ? 'Drop files here...' : 'Drop DOCX files here'}
        </p>
        <p className="text-sm mt-1" style={{ color: '#94a3b8' }}>
          or click to browse
        </p>
      </div>
      
      {/* File List */}
      {files.length > 0 && (
        <div className="mt-6 animate-fade-in">
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-medium" style={{ color: '#334155' }}>
              {files.length} file{files.length > 1 ? 's' : ''} selected
            </span>
            <button
              onClick={clearAll}
              className="text-sm font-medium transition-colors"
              style={{ color: '#dc2626' }}
            >
              Clear all
            </button>
          </div>
          
          <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center justify-between p-3 rounded-lg animate-fade-in"
                style={{ backgroundColor: '#f8fafc' }}
              >
                <div className="flex items-center min-w-0">
                  <FileText className="h-4 w-4 flex-shrink-0 mr-3" style={{ color: '#64748b' }} />
                  <span className="text-sm truncate" style={{ color: '#334155' }}>{file.name}</span>
                  <span className="text-xs ml-2 flex-shrink-0" style={{ color: '#94a3b8' }}>
                    {formatFileSize(file.size)}
                  </span>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 rounded hover:bg-red-50 ml-2 flex-shrink-0"
                >
                  <X className="h-4 w-4" style={{ color: '#dc2626' }} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Options */}
      <div className="mt-6 space-y-5">
        {/* Batch Name */}
        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: '#334155' }}>
            Batch Name
            <span className="font-normal ml-1" style={{ color: '#94a3b8' }}>(optional)</span>
          </label>
          <input
            type="text"
            value={batchName}
            onChange={(e) => setBatchName(e.target.value)}
            placeholder="e.g., Chapter 1-5, Medical Textbook Batch"
            className="w-full px-4 py-3 rounded-lg border transition-all duration-200
                     focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            style={{ borderColor: '#e5e2dc' }}
          />
        </div>
        
        {/* Document Type */}
        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: '#334155' }}>
            Document Type
          </label>
          <select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value as DocumentType)}
            className="w-full px-4 py-3 rounded-lg border transition-all duration-200 cursor-pointer
                     focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500
                     appearance-none bg-white"
            style={{ 
              borderColor: '#e5e2dc',
              backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
              backgroundPosition: 'right 0.75rem center',
              backgroundRepeat: 'no-repeat',
              backgroundSize: '1.25em 1.25em',
              paddingRight: '2.5rem'
            }}
          >
            {DOCUMENT_TYPES.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
        
        {/* Output Format */}
        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: '#334155' }}>
            Output Format
          </label>
          <div className="space-y-2">
            <label 
              className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
                ${!useMarkers ? 'border-amber-500 bg-amber-50/50' : 'border-gray-200 hover:border-gray-300'}`}
            >
              <input
                type="radio"
                name="format"
                checked={!useMarkers}
                onChange={() => setUseMarkers(false)}
                className="sr-only"
              />
              <div className={`w-4 h-4 rounded-full border-2 mr-3 flex items-center justify-center
                ${!useMarkers ? 'border-amber-500' : 'border-gray-300'}`}>
                {!useMarkers && <div className="w-2 h-2 rounded-full bg-amber-500" />}
              </div>
              <div>
                <span className="font-medium text-sm" style={{ color: '#334155' }}>Word Styles</span>
                <span className="text-sm block" style={{ color: '#64748b' }}>
                  Apply proper paragraph styles (recommended)
                </span>
              </div>
            </label>
            
            <label 
              className={`flex items-center p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
                ${useMarkers ? 'border-amber-500 bg-amber-50/50' : 'border-gray-200 hover:border-gray-300'}`}
            >
              <input
                type="radio"
                name="format"
                checked={useMarkers}
                onChange={() => setUseMarkers(true)}
                className="sr-only"
              />
              <div className={`w-4 h-4 rounded-full border-2 mr-3 flex items-center justify-center
                ${useMarkers ? 'border-amber-500' : 'border-gray-300'}`}>
                {useMarkers && <div className="w-2 h-2 rounded-full bg-amber-500" />}
              </div>
              <div>
                <span className="font-medium text-sm" style={{ color: '#334155' }}>XML Markers</span>
                <span className="text-sm block" style={{ color: '#64748b' }}>
                  Add &lt;TAG&gt; text markers (legacy)
                </span>
              </div>
            </label>
          </div>
        </div>
      </div>
      
      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={files.length === 0 || createBatch.isPending}
        className="w-full mt-6 py-3.5 px-6 rounded-lg font-semibold text-white
                 transition-all duration-200 flex items-center justify-center gap-2
                 disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ 
          background: files.length === 0 || createBatch.isPending 
            ? '#94a3b8' 
            : 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
          boxShadow: files.length > 0 && !createBatch.isPending 
            ? '0 2px 8px rgba(30, 41, 59, 0.25)' 
            : 'none'
        }}
      >
        {createBatch.isPending ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="h-5 w-5" />
            Process {files.length} Document{files.length !== 1 ? 's' : ''}
          </>
        )}
      </button>
      
      {createBatch.isError && (
        <p className="mt-4 text-sm text-center" style={{ color: '#dc2626' }}>
          Error: {(createBatch.error as Error).message}
        </p>
      )}
    </div>
  );
}
