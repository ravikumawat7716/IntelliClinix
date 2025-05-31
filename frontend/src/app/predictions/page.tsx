"use client";

import { useState, useEffect, FormEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { toast } from "react-hot-toast";
import DashboardNav from "@/components/DashboardNav";
import { NiftiFile } from "@/types";
/// <reference types="node" />

const BACKEND_URL = "http://localhost:5328";

function getDisplayName(filename: string): string {
  // For brain scans (BRATS)
  if (filename.includes("BRATS")) {
    return filename.replace(/BRATS_\d+_/, "Case ");
  }
  // For heart scans (la_)
  if (filename.includes("_la_")) {
    return filename.replace(/la_(\d+)_\d+/, "Heart Case $1");
  }
  // Default case
  return filename.split("_")[0];
}

function getDatasetType(filename: string): "Brain" | "Heart" | "Unknown" {
  if (filename.includes("BRATS")) return "Brain";
  if (filename.includes("_la_")) return "Heart";
  return "Unknown";
}

export default function PredictionsPage() {
  const [selectedNiftis, setSelectedNiftis] = useState<string[]>([]);
  const [niftiFiles, setNiftiFiles] = useState<{
    id: string;
    filename: string;
    jobId: string;
    scanType: string;
    timestamp: string;
    created_at: string;
  }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingFiles, setIsFetchingFiles] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // CVAT credential modal state
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [cvatUsername, setCvatUsername] = useState("");
  const [cvatPassword, setCvatPassword] = useState("");
  
  // Gallery state
  const [showGallery, setShowGallery] = useState(false);
  const [currentSliceIndex, setCurrentSliceIndex] = useState<number>(0);
  const [gallerySlices, setGallerySlices] = useState<{
    original: string[];
    result: string[];
    totalSlices: number;
  }>({ original: [], result: [], totalSlices: 0 });
  const [overlayOpacity, setOverlayOpacity] = useState(0.7);
  const [selectedNiftiForGallery, setSelectedNiftiForGallery] = useState<string | null>(null);
  const [useScreenBlend, setUseScreenBlend] = useState(true);
  
  // Filter state
  const [filter, setFilter] = useState<"All" | "Brain" | "Heart" | "Unknown">("All");
  const [brainCount, setBrainCount] = useState(0);
  const [heartCount, setHeartCount] = useState(0);

  const router = useRouter();

  useEffect(() => {
    fetchNiftiFiles();
  }, []);

  const fetchNiftiFiles = async () => {
    setIsFetchingFiles(true);
    try {
      const response = await fetch("http://localhost:5328/inference/nifti_files", {
        method: "GET",
        credentials: "include",
      });
      
      if (!response.ok) {
        throw new Error("Failed to fetch NIfTI files");
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || "Failed to fetch NIfTI files");
      }
      
      // Add scanType and timestamp to each file
      const filesWithType = (data.nifti_files || []).map((file: any) => ({
        ...file,
        scanType: file.filename.includes("BRATS") ? "Brain" as const :
                 file.filename.includes("_la_") ? "Heart" as const : 
                 "Unknown" as const,
        created_at: file.created_at 
      }));
      
      // Sort files by timestamp, most recent first
      const sortedFiles = filesWithType.sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      
      setNiftiFiles(sortedFiles);

      // Update counts
      const brainFiles = sortedFiles.filter((f: NiftiFile) => f.scanType === "Brain").length;
      const heartFiles = sortedFiles.filter((f: NiftiFile) => f.scanType === "Heart").length;
      setBrainCount(brainFiles);
      setHeartCount(heartFiles);
    } catch (error) {
      console.error("Error fetching NIfTI files:", error);
      toast.error("Failed to load NIfTI files");
    } finally {
      setIsFetchingFiles(false);
    }
  };

  const toggleNiftiSelection = (niftiId: string) => {
    setSelectedNiftis((prev) =>
      prev.includes(niftiId) 
        ? prev.filter((id) => id !== niftiId) 
        : [...prev, niftiId]
    );
  };

  const handleGalleryOpen = async (niftiId: string, jobId: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/inference/comparison_slices?nifti_id=${niftiId}&job_id=${jobId}`);
      
      if (!response.ok) {
        throw new Error("Failed to fetch comparison slices");
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || "Failed to fetch comparison slices");
      }
      
      setGallerySlices({
        original: data.original_slices || [],
        result: data.result_slices || [],
        totalSlices: data.original_slices?.length || 0
      });
      
      setCurrentSliceIndex(0);
      setShowGallery(true);
      setSelectedNiftiForGallery(niftiId);
    } catch (error) {
      console.error("Error fetching comparison slices:", error);
      toast.error("Failed to load comparison images");
    } finally {
      setIsLoading(false);
    }
  };

  const navigateSlice = (direction: 'next' | 'prev') => {
    if (direction === 'next' && currentSliceIndex < gallerySlices.totalSlices - 1) {
      setCurrentSliceIndex(currentSliceIndex + 1);
    } else if (direction === 'prev' && currentSliceIndex > 0) {
      setCurrentSliceIndex(currentSliceIndex - 1);
    }
  };
  
  const handleSliderChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const newIndex = parseInt(e.target.value);
    setCurrentSliceIndex(newIndex);
  };

  // CVAT integration functions
  const handleSendToCVAT = () => {
    if (selectedNiftis.length === 0) {
      toast.error("Please select at least one file to send to CVAT");
      return;
    }
    setShowCredentialsModal(true);
  };
  
  const handleDiscardFiles = async () => {
    if (selectedNiftis.length === 0) {
      toast.error("Please select at least one file to discard");
      return;
    }
    
    if (!confirm("Are you sure you want to discard the selected files? This action cannot be undone.")) {
      return;
    }
    
    setIsProcessing(true);
    try {
      const response = await fetch(`${BACKEND_URL}/cvat/discard_files`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          nifti_ids: selectedNiftis
        }),
      });
      
      if (!response.ok) {
        throw new Error("Failed to discard files");
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || "Failed to discard files");
      }
      
      toast.success("Files discarded successfully");
      setSelectedNiftis([]);
      fetchNiftiFiles(); // Refresh the file list
    } catch (error) {
      console.error("Error discarding files:", error);
      toast.error("Failed to discard files");
    } finally {
      setIsProcessing(false);
    }
  };
  
  const handleCVATCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    
    try {
      const response = await fetch("http://localhost:5328/cvat/upload_tasks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          nifti_ids: selectedNiftis,
          cvat_username: cvatUsername,
          cvat_password: cvatPassword
        }),
      });
      
      if (!response.ok) {
        throw new Error("Failed to send to CVAT");
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || "Failed to send to CVAT");
      }
      
      toast.success(`Successfully sent ${selectedNiftis.length} task(s) to CVAT`);
      setShowCredentialsModal(false);
      setSelectedNiftis([]);
    } catch (error) {
      console.error("Error sending to CVAT:", error);
      if (error instanceof Error) {
        toast.error(`Failed to send to CVAT: ${error.message}`);
      } else {
        toast.error("Failed to send to CVAT");
      }
    } finally {
      setIsProcessing(false);
    }
  };

  // Filter functions for scan type
  const filteredFiles = niftiFiles.filter(file => {
    if (filter === "All") return true;
    return file.scanType === filter;
  });

  return (
    <div className="min-h-screen bg-gradient-to-r from-blue-50 to-indigo-50 flex flex-col">
      <DashboardNav />
      
      <div className="flex flex-1 w-full max-w-7xl mx-auto p-4">
        {/* Main content area */}
        <main className="flex-1 pr-4">
          <div className="bg-white shadow-xl rounded-xl p-6 border border-gray-200">
            <h2 className="text-2xl md:text-3xl font-extrabold mb-6 text-gray-900 text-center">
              Medical Scan Predictions
            </h2>
            
            {/* Filter tabs */}
            <div className="flex justify-center mb-6">
              <div className="inline-flex rounded-md shadow-sm" role="group">
                {["All", "Brain", "Heart", "Unknown"].map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setFilter(type as "All" | "Brain" | "Heart" | "Unknown")}
                    className={`px-4 py-2 text-sm font-medium ${
                      filter === type
                        ? "bg-blue-600 text-white"
                        : "bg-white text-gray-700 hover:bg-gray-100"
                    } border border-gray-200 ${
                      type === "All" ? "rounded-l-lg" : ""
                    } ${
                      type === "Unknown" ? "rounded-r-lg" : ""
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>
            
            {isFetchingFiles ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
                <p className="mt-4 text-gray-600">Loading medical scans...</p>
              </div>
            ) : filteredFiles.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="bg-gray-100">
                      <th className="p-4">Select</th>
                      <th className="p-4 text-left">File Name</th>
                      <th className="p-4 text-left">Date</th>
                      <th className="p-4 text-left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredFiles.map((file) => (
                      <tr key={file.id} className="border-t">
                        <td className="p-4 text-center">
                          <input
                            type="checkbox"
                            checked={selectedNiftis.includes(file.id)}
                            onChange={() => toggleNiftiSelection(file.id)}
                          />
                        </td>
                        <td className="p-4">{getDisplayName(file.filename)}</td>
                        <td className="p-4 text-gray-600">
                        <span title={new Date(parseInt(file.created_at)).toLocaleString()}>
                          {new Date(parseInt(file.created_at)).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                          })}
                          </span>
                        </td>
                        <td className="p-4">
                          <button
                            onClick={() => handleGalleryOpen(file.id, file.jobId)}
                            className="text-blue-500 hover:text-blue-700"
                          >
                            View Results
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 bg-gray-50 rounded-lg">
                <svg className="w-16 h-16 mx-auto text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p className="text-gray-500 mt-4 mb-6">No prediction results found in this category.</p>
                <button 
                  onClick={() => router.push('/newupload')}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                >
                  Upload New Scan
                </button>
              </div>
            )}
          </div>
        </main>
        
        {/* Right panel for actions */}
        <div className="w-72 bg-white shadow-xl rounded-xl p-5 border border-gray-200 h-fit sticky top-4">
          <div className="mb-5">
            <h3 className="text-lg font-bold text-gray-800 mb-2">Selected Files</h3>
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600">
                {selectedNiftis.length} file(s) selected
              </p>
              {selectedNiftis.length > 0 && (
                <button 
                  onClick={() => setSelectedNiftis([])}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Clear selection
                </button>
              )}
            </div>
          </div>
          
          <div className="space-y-3">
            <button
              onClick={handleSendToCVAT}
              disabled={selectedNiftis.length === 0 || isProcessing}
              className="w-full py-2 px-4 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isProcessing ? (
                <span className="mr-2 h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin"></span>
              ) : (
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                </svg>
              )}
              Send to CVAT
            </button>
            
            <button
              onClick={handleDiscardFiles}
              disabled={selectedNiftis.length === 0 || isProcessing}
              className="w-full py-2 px-4 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isProcessing ? (
                <span className="mr-2 h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin"></span>
              ) : (
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
              )}
              Discard Files
            </button>
          </div>
          
          {/* Quick statistic cards */}
          <div className="mt-6 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-600 mb-3">Current Session</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-xs text-blue-600">Brain Scans</p>
                <p className="text-lg font-bold text-blue-800">
                  {brainCount}
                </p>
              </div>
              <div className="p-3 bg-pink-50 rounded-lg">
                <p className="text-xs text-pink-600">Heart Scans</p>
                <p className="text-lg font-bold text-pink-800">
                  {heartCount}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* CVAT Credentials Modal */}
      {showCredentialsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white p-6 rounded-lg shadow-xl relative max-w-md w-full">
            <button
              onClick={() => setShowCredentialsModal(false)}
              className="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
              type="button"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
            
            <h3 className="text-xl font-bold text-gray-800 mb-4">CVAT Credentials</h3>
            <p className="text-sm text-gray-600 mb-4">
              Enter your CVAT credentials to upload selected files as tasks.
            </p>
            
            <form onSubmit={handleCVATCredentialsSubmit} className="space-y-4">
              <div>
                <label htmlFor="cvat-username" className="block text-sm font-medium text-gray-700 mb-1">
                  Username
                </label>
                <input
                  id="cvat-username"
                  type="text"
                  value={cvatUsername}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setCvatUsername(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label htmlFor="cvat-password" className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  id="cvat-password"
                  type="password"
                  value={cvatPassword}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setCvatPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <button
                type="submit"
                disabled={isProcessing}
                className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition flex items-center justify-center disabled:opacity-50"
              >
                {isProcessing ? (
                  <span className="mr-2 h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin"></span>
                ) : "Upload to CVAT"}
              </button>
            </form>
          </div>
        </div>
      )}
      
      {/* Enhanced Comparison Gallery Modal */}
      {showGallery && (
        <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl relative max-w-6xl w-full flex flex-col h-[90vh]">
            {/* Gallery header */}
            <div className="p-4 border-b border-gray-200 flex justify-between items-center">
              <div className="flex items-center">
                <h3 className="text-xl font-bold text-gray-800 mr-4">
                  {niftiFiles.find(f => f.id === selectedNiftiForGallery)?.scanType || "Unknown"} Scan Comparison
                </h3>
                <div className="flex items-center space-x-2">
                  <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                    Slice {currentSliceIndex + 1}/{gallerySlices.totalSlices}
                  </span>
                  <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-medium">
                    {getDisplayName(niftiFiles.find(f => f.id === selectedNiftiForGallery)?.filename || "")}
                  </span>
                </div>
              </div>
              
              <div className="flex items-center space-x-4">
                <button
                  onClick={() => setShowGallery(false)}
                  type="button"
                  className="text-gray-500 hover:text-gray-700"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
            </div>
            
            {/* Main content area with flex layout */}
            <div className="flex flex-1 overflow-hidden">
              {/* Image viewing area */}
              <div className="flex-1 relative">
                {/* Original image as background */}
                {gallerySlices.original[currentSliceIndex] && (
                  <img 
                    src={gallerySlices.original[currentSliceIndex]} 
                    alt={`Original slice ${currentSliceIndex + 1}`}
                    className="absolute inset-0 w-full h-full object-contain z-[1]"
                  />
                )}
                
                {/* Result image as overlay */}
                {gallerySlices.result[currentSliceIndex] && (
                  <img 
                    src={gallerySlices.result[currentSliceIndex]} 
                    alt={`Result slice ${currentSliceIndex + 1}`}
                    className="absolute inset-0 w-full h-full object-contain z-[2]"
                    style={{ 
                      opacity: overlayOpacity,
                      mixBlendMode: useScreenBlend ? 'screen' : 'normal'
                    }}
                  />
                )}
              </div>
            </div>
            
            {/* Navigation controls */}
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between space-x-4">
                <button
                  onClick={() => navigateSlice('prev')}
                  disabled={currentSliceIndex === 0}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
                  type="button"
                >
                  Previous
                </button>
                
                <div className="flex-1">
                  <input
                    type="range"
                    min={0}
                    max={gallerySlices.totalSlices - 1}
                    value={currentSliceIndex}
                    onChange={handleSliderChange}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>Slice 1</span>
                    <span>Slice {gallerySlices.totalSlices}</span>
                  </div>
                </div>
                
                <button
                  onClick={() => navigateSlice('next')}
                  disabled={currentSliceIndex === gallerySlices.totalSlices - 1}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
                  type="button"
                >
                  Next
                </button>
              </div>
              
              {/* Quick jump buttons */}
              <div className="flex justify-center mt-4 space-x-2">
                {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
                  const sliceIndex = Math.floor(fraction * (gallerySlices.totalSlices - 1));
                  return (
                    <button
                      key={fraction}
                      onClick={() => setCurrentSliceIndex(sliceIndex)}
                      className={`px-3 py-1 text-sm rounded ${
                        currentSliceIndex === sliceIndex
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                      type="button"
                    >
                      {Math.round(fraction * 100)}%
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}