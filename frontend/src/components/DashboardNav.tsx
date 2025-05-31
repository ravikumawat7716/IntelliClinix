"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Upload, PieChart, CheckCircle, Brain, CircleUser, LogOut } from "lucide-react";

export default function DashboardNav() {
  const pathname = usePathname();
  
  // Helper to determine if the current path is active
  const isActive = (path: string) => pathname === path;
  
  return (
    <div className="bg-gradient-to-r from-blue-900 to-indigo-900 shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between">
          {/* Logo and Brand */}
          <div className="flex items-center py-4">
            <div className="flex items-center space-x-2">
              <Brain className="h-8 w-8 text-blue-400" />
              <span className="text-white font-bold text-2xl">MedNet</span>
            </div>
            <span className="ml-2 px-2 py-1 bg-blue-800 text-xs text-blue-200 rounded-md">AI Annotation</span>
          </div>
          
          {/* Main Navigation */}
          <div className="flex space-x-1">
            <Link
              href="/newupload"
              className={`flex items-center px-4 py-5 text-sm font-medium transition-all duration-200 ${
                isActive("/newupload")
                  ? "text-white border-b-2 border-blue-400 bg-blue-800 bg-opacity-30"
                  : "text-blue-100 hover:bg-blue-800 hover:bg-opacity-20 hover:text-white"
              }`}
            >
              <Upload className="h-4 w-4 mr-2" />
              New Upload
            </Link>
            
            <Link
              href="/predictions"
              className={`flex items-center px-4 py-5 text-sm font-medium transition-all duration-200 ${
                isActive("/predictions")
                  ? "text-white border-b-2 border-blue-400 bg-blue-800 bg-opacity-30"
                  : "text-blue-100 hover:bg-blue-800 hover:bg-opacity-20 hover:text-white"
              }`}
            >
              <PieChart className="h-4 w-4 mr-2" />
              Predictions
            </Link>
            
            <Link
              href="/corrected"
              className={`flex items-center px-4 py-5 text-sm font-medium transition-all duration-200 ${
                isActive("/corrected")
                  ? "text-white border-b-2 border-blue-400 bg-blue-800 bg-opacity-30"
                  : "text-blue-100 hover:bg-blue-800 hover:bg-opacity-20 hover:text-white"
              }`}
            >
              <CheckCircle className="h-4 w-4 mr-2" />
              Corrected
            </Link>
          </div>
          
          {/* User Menu */}
          <div className="flex items-center space-x-4">
            <button className="p-2 rounded-full text-blue-200 hover:text-white hover:bg-blue-800 hover:bg-opacity-30 transition-colors duration-200">
              <CircleUser className="h-5 w-5" />
            </button>
            <div className="h-6 border-r border-blue-700"></div>
            <button className="p-2 rounded-full text-blue-200 hover:text-white hover:bg-blue-800 hover:bg-opacity-30 transition-colors duration-200">
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
      
      {/* Breadcrumb / Subtitle Bar */}
      <div className="bg-blue-800 bg-opacity-30 py-2 px-4">
        <div className="max-w-7xl mx-auto flex items-center text-xs text-blue-200">
          <span>Medical Image Annotation Platform</span>
          <span className="mx-2">•</span>
          <span className="font-medium text-white">
            {pathname.replace("/", "").charAt(0).toUpperCase() + pathname.replace("/", "").slice(1) || "Dashboard"}
          </span>
        </div>
      </div>
    </div>
  );
}