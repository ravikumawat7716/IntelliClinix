"use client";
import { useState } from "react";
import Image from "next/image";
import { Pencil, Upload } from "lucide-react";

const images: Array<string> = [
  "https://source.unsplash.com/random/200x200?sig=1",
  "https://source.unsplash.com/random/200x200?sig=2",
  "https://source.unsplash.com/random/200x200?sig=3",
  "https://source.unsplash.com/random/200x200?sig=4",
  "https://source.unsplash.com/random/200x200?sig=5",
];

export default function GalleryPage() {
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isUploaded, setIsUploaded] = useState(false);

  const toggleSelection = (img: string) => {
    setSelectedImages((prev) =>
      prev.includes(img) ? prev.filter((i) => i !== img) : [...prev, img]
    );
  };

  const handleUpload = async () => {
    setIsUploading(true);
    try {
      const response = await fetch('/api/create-cvat-task', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ selectedImages }),
      });

      if (!response.ok) {
        throw new Error('Failed to create CVAT task');
      }

      const { taskId } = await response.json();
      
      // Open the CVAT task in a new tab
      window.open(`https://app.cvat.ai/tasks/${taskId}`, '_blank');
      
      setIsUploaded(true);
    } catch (error) {
      console.error('Error uploading to CVAT:', error);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6 flex flex-col items-center">
      <h1 className="text-3xl font-bold mb-6">Image Gallery</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {images.map((img, index) => (
          <div
            key={index}
            className={`relative cursor-pointer transition-all rounded-xl overflow-hidden shadow-md border-2 p-2 ${
              selectedImages.includes(img) ? "border-blue-500" : "border-gray-700"
            }`}
            onClick={() => toggleSelection(img)}
          >
            <Image
              src={img}
              alt={`Image ${index + 1}`}
              width={160}
              height={160}
              className="w-40 h-40 object-cover"
            />
          </div>
        ))}
      </div>
      <div className="mt-6 flex gap-4">
        <button
          disabled={selectedImages.length === 0}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Pencil size={16} /> Edit
        </button>
        <button
          disabled={selectedImages.length === 0 || isUploading || isUploaded}
          onClick={handleUpload}
          className="flex items-center gap-2 bg-green-600 hover:bg-green-500 px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {isUploading ? (
            "Uploading..."
          ) : isUploaded ? (
            "Corrected"
          ) : (
            <>
              <Upload size={16} /> Upload to CVAT
            </>
          )}
        </button>
      </div>
    </div>
  );
}
