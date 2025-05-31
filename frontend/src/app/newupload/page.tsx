"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "react-hot-toast";
import DashboardNav from "@/components/DashboardNav";
import { 
  Upload, 
  Brain, 
  Heart, 
  Loader2, 
  FileArchive, 
  Check, 
  Info, 
  ArrowRight, 
  Database
} from "lucide-react";

type DatasetConfig = {
  id: string;
  name: string;
  description: string;
  filePattern: string;
  icon: JSX.Element;
  color: string;
};

const DATASET_CONFIGS: { [key: string]: DatasetConfig } = {
  "Dataset001_BrainTumour": {
    id: "Dataset001_BrainTumour",
    name: "Brain Tumor Dataset",
    description: "BRATS dataset for brain tumor segmentation",
    filePattern: "BRATS_XXX_XXXX.nii.gz or XXXX_0000.nii.gz",
    icon: <Brain className="h-6 w-6" />,
    color: "blue"
  },
  "Dataset002_Heart": {
    id: "Dataset002_Heart",
    name: "Heart Dataset",
    description: "Left atrium segmentation dataset",
    filePattern: "la_XXX_0000.nii.gz",
    icon: <Heart className="h-6 w-6" />,
    color: "red"
  }
};

export default function NewUploadPage() {
  const router = useRouter();
  const [config, setConfig] = useState<"2d" | "3d_fullres">("3d_fullres");
  const [selectedDataset, setSelectedDataset] = useState<string>("Dataset001_BrainTumour");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);

  // Progress bar label state
  const [progressBarText, setProgressBarText] = useState("Upload Files");
  // Stepper state: 1 = Select Dataset, 2 = Upload Files, 3 = Processing
  const [currentStep, setCurrentStep] = useState(1);

  useEffect(() => {
    const skipAuth = localStorage.getItem("skipAuth");
    if (skipAuth === "true") {
      setIsAuthenticated(true);
      return;
    }
    const checkAuth = async () => {
      try {
        const response = await fetch("http://localhost:5328/auth/user", {
          method: "GET",
          credentials: "include",
        });
        if (!response.ok) throw new Error("Authentication failed");
        const data = await response.json();
        if (!data.authenticated) {
          toast.error("Please log in first.");
          router.push("/login");
          return;
        }
        if (data.user && data.user.username) {
          localStorage.setItem("username", data.user.username);
        }
        setIsAuthenticated(true);
      } catch (error) {
        console.error("Error checking authentication:", error);
        toast.error("Authentication check failed");
        router.push("/login");
      }
    };
    checkAuth();
  }, [router]);

  // Update stepper and progress bar label
  useEffect(() => {
    if (isProcessing) {
      setCurrentStep(3);
      setProgressBarText("Processing");
    } else if (selectedFile) {
      setCurrentStep(2);
      setProgressBarText("Upload Files");
    } else {
      setCurrentStep(1);
      setProgressBarText("Upload Files");
    }
  }, [selectedFile, isProcessing, selectedDataset, config]);

  const handleSubmit = async () => {
    if (!isAuthenticated) {
      toast.error("Please log in first");
      router.push("/login");
      return;
    }
    if (!selectedFile) {
      toast.error("Please select a file to upload");
      return;
    }
    const username = localStorage.getItem("username");
    if (!username) {
      toast.error("User not found. Please log in again.");
      router.push("/login");
      return;
    }
    setIsProcessing(true);
    setUploadProgress(0);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("config", config);
      formData.append("username", username);
      formData.append("dataset", selectedDataset);
      // Simulate upload progress (in a real app, use XMLHttpRequest with progress events)
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 95) {
            clearInterval(progressInterval);
            return 95;
          }
          return prev + Math.random() * 10;
        });
      }, 500);
      const uploadResponse = await fetch("http://localhost:5328/inference/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      clearInterval(progressInterval);
      setUploadProgress(100);
      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json();
        if (uploadResponse.status === 401) {
          toast.error("Session expired. Please log in again.");
          router.push("/login");
          return;
        }
        throw new Error(errorData.error || "Upload failed");
      }
      const uploadData = await uploadResponse.json();
      if (!uploadData.success) throw new Error(uploadData.error);
      const inferenceResponse = await fetch("http://localhost:5328/inference/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          job_id: uploadData.job_id,
          config: uploadData.config,
          inference_dir: uploadData.inference_dir,
          dataset: selectedDataset
        }),
      });
      if (!inferenceResponse.ok) {
        const errorData = await inferenceResponse.json();
        if (inferenceResponse.status === 401) {
          toast.error("Session expired. Please log in again.");
          router.push("/login");
          return;
        }
        throw new Error(errorData.error || "Inference failed");
      }
      toast.success("Processing completed! Redirecting to results...");
      router.push("/predictions");
    } catch (error: any) {
      console.error("Processing error:", error);
      toast.error(error.message || "Processing failed");
    } finally {
      setIsProcessing(false);
    }
  };

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-gray-50 to-gray-200">
        <div className="animate-pulse flex items-center space-x-2 text-blue-600">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-lg font-medium">Authenticating...</span>
        </div>
      </div>
    );
  }

  const selectedDatasetConfig = DATASET_CONFIGS[selectedDataset];
  const datasetIconColor = selectedDatasetConfig.color === "blue" ? "text-blue-600" : "text-red-600";
  const datasetBgColor = selectedDatasetConfig.color === "blue" ? "bg-blue-100" : "bg-red-100";
  const datasetBorderColor = selectedDatasetConfig.color === "blue" ? "border-blue-200" : "border-red-200";

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-200">
      <DashboardNav />
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">Medical Image Upload</h1>
          <p className="text-gray-600">Upload medical scans for AI-assisted analysis and annotation</p>
        </div>
        <div className="max-w-3xl mx-auto">
          <div className="bg-white rounded-xl shadow-xl overflow-hidden">
            {/* Stepper */}
            <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className={`flex items-center justify-center h-8 w-8 rounded-full font-medium
                    ${currentStep === 1 ? "bg-blue-600 text-white" : "bg-gray-300 text-white"}`}>1</div>
                  <span className={`ml-2 font-medium ${currentStep === 1 ? "text-blue-600" : "text-gray-400"}`}>Select Dataset</span>
                </div>
                <div className="h-0.5 flex-1 mx-4 bg-gray-300"></div>
                <div className="flex items-center">
                  <div className={`flex items-center justify-center h-8 w-8 rounded-full font-medium
                    ${currentStep === 2 ? "bg-blue-600 text-white" : "bg-gray-300 text-white"}`}>2</div>
                  <span className={`ml-2 font-medium ${currentStep === 2 ? "text-blue-600" : "text-gray-400"}`}>Upload Files</span>
                </div>
                <div className="h-0.5 flex-1 mx-4 bg-gray-300"></div>
                <div className="flex items-center">
                  <div className={`flex items-center justify-center h-8 w-8 rounded-full font-medium
                    ${currentStep === 3 ? "bg-blue-600 text-white" : "bg-gray-300 text-white"}`}>3</div>
                  <span className={`ml-2 font-medium ${currentStep === 3 ? "text-blue-600" : "text-gray-400"}`}>Processing</span>
                </div>
              </div>
            </div>
            <div className="px-8 py-6">
              {/* Dataset Selection */}
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Database className="h-5 w-5 mr-2 text-blue-600" />
                  Dataset Selection
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.values(DATASET_CONFIGS).map((dataset) => (
                    <div 
                      key={dataset.id}
                      className={`cursor-pointer border-2 rounded-lg p-4 transition ${
                        selectedDataset === dataset.id 
                          ? `border-${dataset.color === "blue" ? "blue" : "red"}-500 bg-${dataset.color === "blue" ? "blue" : "red"}-50`
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                      onClick={() => setSelectedDataset(dataset.id)}
                    >
                      <div className="flex items-center">
                        <div className={`flex-shrink-0 h-12 w-12 rounded-lg ${dataset.color === "blue" ? "bg-blue-100" : "bg-red-100"} flex items-center justify-center`}>
                          {React.cloneElement(dataset.icon, {
                            className: `h-6 w-6 ${dataset.color === "blue" ? "text-blue-600" : "text-red-600"}`
                          })}
                        </div>
                        <div className="ml-4">
                          <h4 className="font-medium text-gray-900">{dataset.name}</h4>
                          <p className="text-sm text-gray-500">{dataset.description}</p>
                        </div>
                        {selectedDataset === dataset.id && (
                          <Check className={`ml-auto h-5 w-5 ${dataset.color === "blue" ? "text-blue-600" : "text-red-600"}`} />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                <div className={`mt-4 p-4 rounded-lg ${datasetBgColor} ${datasetBorderColor} border flex items-start`}>
                  <Info className={`h-5 w-5 ${datasetIconColor} mt-0.5 flex-shrink-0`} />
                  <div className="ml-3">
                    <p className="text-sm text-gray-700">
                      <span className="font-medium">Expected file format:</span> {selectedDatasetConfig.filePattern}
                    </p>
                    <p className="text-sm text-gray-600 mt-1">
                      Make sure your files match the expected naming convention for accurate analysis.
                    </p>
                  </div>
                </div>
              </div>
              {/* File Upload */}
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Upload className="h-5 w-5 mr-2 text-blue-600" />
                  Upload Scan Data
                </h3>
                <div 
                  className={`border-2 ${dragActive ? "border-blue-500 bg-blue-50" : "border-dashed border-gray-300"} rounded-lg p-8 text-center transition-all duration-200`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                >
                  <input
                    type="file"
                    accept=".zip"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                  />
                  {!selectedFile ? (
                    <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center space-y-4">
                      <div className="p-3 bg-blue-100 rounded-full">
                        <FileArchive className="h-8 w-8 text-blue-600" />
                      </div>
                      <div>
                        <p className="text-gray-700 font-medium">Drag &amp; drop your ZIP file here</p>
                        <p className="text-sm text-gray-500 mt-1">
                          or <span className="text-blue-600">browse files</span>
                        </p>
                      </div>
                      <p className="text-xs text-gray-500 bg-gray-100 py-1 px-2 rounded-full">
                        Supported format: .zip containing scan data
                      </p>
                    </label>
                  ) : (
                    <div className="flex flex-col items-center space-y-3">
                      <div className="p-3 bg-green-100 rounded-full">
                        <Check className="h-8 w-8 text-green-600" />
                      </div>
                      <div>
                        <p className="text-gray-700 font-medium">{selectedFile.name}</p>
                        <p className="text-sm text-gray-500 mt-1">
                          {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                      <button 
                        className="text-sm text-blue-600 hover:text-blue-800 underline"
                        onClick={() => setSelectedFile(null)}
                      >
                        Change file
                      </button>
                    </div>
                  )}
                </div>
              </div>
              {/* Scan Configuration */}
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Database className="h-5 w-5 mr-2 text-blue-600" />
                  Scan Configuration
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div 
                    className={`cursor-pointer border-2 rounded-lg p-4 transition ${
                      config === "2d" 
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                    onClick={() => setConfig("2d")}
                  >
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                        <span className="font-bold text-blue-600">2D</span>
                      </div>
                      <div className="ml-4">
                        <h4 className="font-medium text-gray-900">2D Slice Collection</h4>
                        <p className="text-sm text-gray-500">Analysis of individual 2D slices</p>
                      </div>
                      {config === "2d" && <Check className="ml-auto h-5 w-5 text-blue-600" />}
                    </div>
                  </div>
                  <div 
                    className={`cursor-pointer border-2 rounded-lg p-4 transition ${
                      config === "3d_fullres" 
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                    onClick={() => setConfig("3d_fullres")}
                  >
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                        <span className="font-bold text-blue-600">3D</span>
                      </div>
                      <div className="ml-4">
                        <h4 className="font-medium text-gray-900">3D Volume (High Resolution)</h4>
                        <p className="text-sm text-gray-500">Full volumetric analysis</p>
                      </div>
                      {config === "3d_fullres" && <Check className="ml-auto h-5 w-5 text-blue-600" />}
                    </div>
                  </div>
                </div>
              </div>
              {/* Progress Bar and Submit Button */}
              {selectedFile && (
                <div className="mb-4">
                  <div className="flex justify-between text-sm text-gray-600 mb-1">
                    <span>{progressBarText}</span>
                    <span>{Math.round(uploadProgress)}%</span>
                  </div>
                  <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden mb-2">
                    <div 
                      className="h-full bg-blue-600 transition-all duration-500"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                </div>
              )}
              <div>
                <button
                  onClick={handleSubmit}
                  disabled={!selectedFile || isProcessing}
                  className="w-full flex items-center justify-center py-3 px-6 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <span>Start Analysis</span>
                      <ArrowRight className="ml-2 h-5 w-5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
          <div className="mt-6 text-center text-sm text-gray-500">
            Having issues? <a href="#" className="text-blue-600 hover:underline">Contact support</a> or check our <a href="#" className="text-blue-600 hover:underline">documentation</a>.
          </div>
        </div>
      </div>
    </div>
  );
}
