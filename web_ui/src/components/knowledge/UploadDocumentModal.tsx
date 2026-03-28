'use client';

import { useState, useRef } from 'react';
import { Loader2, X, Upload, FileText, Type } from 'lucide-react';

interface UploadDocumentModalProps {
  treeName: string;
  onClose: () => void;
  onUploaded: () => void;
}

type UploadMode = 'file' | 'text';

export function UploadDocumentModal({
  treeName,
  onClose,
  onUploaded,
}: UploadDocumentModalProps) {
  const [mode, setMode] = useState<UploadMode>('file');
  const [textContent, setTextContent] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (mode === 'file' && !selectedFile) {
      setError('Please select a file');
      return;
    }
    if (mode === 'text' && !textContent.trim()) {
      setError('Please enter some content');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      let res: Response;

      if (mode === 'file' && selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('tree', treeName);

        res = await fetch('/api/team/knowledge/tree/documents', {
          method: 'POST',
          body: formData,
        });
      } else {
        res = await fetch('/api/team/knowledge/tree/documents', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: textContent, tree: treeName }),
        });
      }

      if (res.ok) {
        onUploaded();
        onClose();
      } else {
        const data = await res.json();
        setError(data.error || data.detail || 'Failed to upload document');
      }
    } catch (e) {
      setError('Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-stone-800 rounded-2xl w-full max-w-lg p-6 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-forest flex items-center justify-center">
              <Upload className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-stone-900 dark:text-white">
                Add Document
              </h2>
              <p className="text-xs text-stone-500">
                to <span className="font-medium">{treeName}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Toggle */}
        <div className="flex items-center gap-2 mb-4 p-1 bg-stone-100 dark:bg-stone-700 rounded-lg">
          <button
            onClick={() => setMode('file')}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-all ${
              mode === 'file'
                ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-white shadow-sm'
                : 'text-stone-600 dark:text-stone-400'
            }`}
          >
            <FileText className="w-4 h-4" />
            Upload File
          </button>
          <button
            onClick={() => setMode('text')}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-all ${
              mode === 'text'
                ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-white shadow-sm'
                : 'text-stone-600 dark:text-stone-400'
            }`}
          >
            <Type className="w-4 h-4" />
            Paste Text
          </button>
        </div>

        <div className="space-y-4">
          {mode === 'file' ? (
            <div>
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileChange}
                accept=".md,.txt,.json,.yaml,.yml"
                className="hidden"
              />
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-stone-200 dark:border-stone-600 rounded-xl p-8 text-center cursor-pointer hover:border-forest dark:hover:border-forest transition-colors"
              >
                {selectedFile ? (
                  <div>
                    <FileText className="w-8 h-8 mx-auto text-forest mb-2" />
                    <p className="text-sm font-medium text-stone-900 dark:text-white">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-stone-500 mt-1">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                    <p className="text-xs text-forest mt-2">Click to change</p>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-8 h-8 mx-auto text-stone-400 mb-2" />
                    <p className="text-sm text-stone-600 dark:text-stone-400">
                      Click to select a file
                    </p>
                    <p className="text-xs text-stone-400 mt-1">
                      Supports .md, .txt, .json, .yaml
                    </p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                Content
              </label>
              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                rows={8}
                placeholder="Paste your knowledge content here..."
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 focus:outline-none focus:ring-2 focus:ring-forest font-mono text-sm"
              />
              <p className="text-xs text-stone-500 mt-1">
                {textContent.length} characters
              </p>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-clay-light/10 dark:bg-clay/20 border border-clay-light/40 dark:border-clay-dark text-clay-dark dark:text-clay-light text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-white"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={uploading || (mode === 'file' ? !selectedFile : !textContent.trim())}
            className="px-4 py-2 bg-forest text-white rounded-lg hover:bg-forest-dark disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
            {uploading ? 'Uploading...' : 'Add to Tree'}
          </button>
        </div>
      </div>
    </div>
  );
}
