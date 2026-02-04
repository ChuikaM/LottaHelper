'use client';

import { useState, useEffect, useRef } from 'react';

export default function ImageUploadWidget() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type.startsWith('image/')) {
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type.startsWith('image/')) {
      setFile(droppedFile);
      setPreview(URL.createObjectURL(droppedFile));
    }
  };

  const handleReset = () => {
    setFile(null);
    setPreview(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleChooseFile = () => {
    fileInputRef.current?.click();
  };

  return (
    <div 
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className="flex justify-center rounded-xl overflow-hidden"
    >
      {!file ? (
        <div className="border-2 border-blue-500 border-dashed rounded-xl p-8 text-center bg-gray-900 w-screen sm:w-3/4 h-[30vh] sm:h-[50vh]">
          <div className="flex justify-center mb-4">
            <img 
              src="/upload.svg" 
              alt="Upload icon" 
              className="w-12 h-12"
            />
          </div>
          <p className="text-lg mb-2">Перетащите файл</p>
          <p className="text-gray-400 mb-4">— или —</p>
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
            id="file-upload"
            ref={fileInputRef}
          />
         <label
            htmlFor="file-upload"
            className="bg-gray-800 hover:bg-gray-700 px-6 py-2 rounded cursor-pointer transition-colors inline-flex items-center gap-2"
          >
            <img src="/select.svg" alt="" className="w-4 h-4" />
            Выбрать файл
          </label>
        </div>
      ) : (
        <div className="border-2 border-blue-500 rounded-xl overflow-hidden">
          <div className="relative pb-[75%]">
            <img 
              src={preview} 
              alt="Uploaded interior" 
              className="absolute top-0 left-0 w-full h-full object-cover"
            />
          </div>
          <div className="p-4 bg-gray-900">
            <div className="flex justify-between items-center mb-3">
              <p className="truncate text-sm">{file.name}</p>
              <button
                onClick={handleReset}
                className="text-gray-400 hover:text-white transition-colors"
                aria-label="Remove file"
              >
                ✕
              </button>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={handleChooseFile}
                className="flex-1 bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded transition-colors"
              >
                Выбрать файл
              </button>
              <button className="flex-1 bg-orange-500 hover:bg-orange-600 px-4 py-2 rounded transition-colors font-medium">
 Подобрать
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}