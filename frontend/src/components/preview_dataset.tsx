import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { Pencil, ChevronLeft, ChevronRight, Upload } from "lucide-react";

const images: Array<string> = [
  "https://picsum.photos/500/300?random=1",
  "https://picsum.photos/500/300?random=2",
  "https://picsum.photos/500/300?random=3",
  "https://picsum.photos/500/300?random=4",
  "https://picsum.photos/500/300?random=5",
];

export default function GalleryPage() {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [isHovering, setIsHovering] = useState(false);

  const nextImage = useCallback(() => {
    setCurrentImageIndex((prevIndex) => (prevIndex + 1) % images.length);
  }, [images.length]);

  const prevImage = useCallback(() => {
    setCurrentImageIndex((prevIndex) =>
      prevIndex === 0 ? images.length - 1 : prevIndex - 1
    );
  }, [images.length]);

  const toggleSelection = useCallback(
    (img: string) => {
      setSelectedImages((prev) =>
        prev.includes(img) ? prev.filter((i) => i !== img) : [...prev, img]
      );
    },
    []
  );

  const handleEdit = () => {
    toggleSelection(images[currentImageIndex]);
  };

  const uploadToCVAT = () => {
    alert(`Uploading ${selectedImages.length} images to CVAT`);
    // Actual API call would go here in a real implementation
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        nextImage();
      } else if (e.key === "ArrowLeft") {
        prevImage();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [nextImage, prevImage]);

  const isCurrentImageSelected = selectedImages.includes(
    images[currentImageIndex]
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6 flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold mb-6">Image Gallery</h1>

      <div
        className="relative w-full max-w-3xl"
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        <Image
          src={images[currentImageIndex]}
          alt={`Image ${currentImageIndex + 1}`}
          width={500}
          height={300}
          className="rounded-lg shadow-md object-cover"
          style={{ aspectRatio: "500 / 300", width: "100%", height: "auto" }}
        />

        <div
          className={`absolute top-0 left-0 w-full h-full flex justify-between items-center transition-opacity duration-300 ${
            isHovering ? "opacity-100" : "opacity-0"
          }`}
        >
          <button
            onClick={prevImage}
            className="h-full px-4 text-white hover:bg-black hover:bg-opacity-20 transition-colors duration-300 focus:outline-none"
            aria-label="Previous Image"
          >
            <ChevronLeft size={48} />
          </button>
          <button
            onClick={nextImage}
            className="h-full px-4 text-white hover:bg-black hover:bg-opacity-20 transition-colors duration-300 focus:outline-none"
            aria-label="Next Image"
          >
            <ChevronRight size={48} />
          </button>
        </div>
      </div>

      <div className="mt-6 flex gap-4">
        <button
          className={`flex items-center gap-2 px-4 py-2 rounded-lg focus:outline-none ${
            isCurrentImageSelected
              ? "bg-blue-800 hover:bg-blue-700"
              : "bg-blue-600 hover:bg-blue-500"
          }`}
          onClick={handleEdit}
        >
          <Pencil size={16} />
          {isCurrentImageSelected ? "Unselect" : "Select"}
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 rounded-lg focus:outline-none ${
            selectedImages.length > 0
              ? "bg-green-600 hover:bg-green-500"
              : "bg-gray-600 cursor-not-allowed"
          }`}
          onClick={uploadToCVAT}
          disabled={selectedImages.length === 0}
        >
          <Upload size={16} />
          Upload to CVAT
        </button>
      </div>

      <div className="mt-4">
        <p>Selected Images: {selectedImages.length}</p>
      </div>
    </div>
  );
}
