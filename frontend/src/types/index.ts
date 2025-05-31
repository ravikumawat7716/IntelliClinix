export interface NiftiFile {
    id: string;
    filename: string;
    jobId: string;
    scanType: "Brain" | "Heart" | "Unknown";
    timestamp: string;
  }
  
  export interface GallerySlices {
    original: string[];
    result: string[];
    totalSlices: number;
  }
  
  export interface LegendItem {
    color: string;
    label: string;
    description: string;
  } 