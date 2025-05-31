"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "react-hot-toast";
import DashboardNav from "@/components/DashboardNav";

type CorrectedTask = {
  task_id: string;
  task_name: string;   // <-- raw filename from backend
  displayName: string; // what we show in the table
  scanType: "Brain" | "Heart" | "Unknown";
};


function getDisplayName(filename: string): string {
  const bare = filename.replace(/^Medical Scan\s*-\s*/, "");

  if (bare.includes("BRATS")) {
    return bare.replace(/BRATS_(\d+)_/, (_m, id) => `Case ${id}`);
  }

  if (bare.includes("_la_")) {
    return bare;
  }

  return bare;
}


function getDatasetType(filename: string): "Brain" | "Heart" | "Unknown" {
  if (filename.includes("BRATS")) return "Brain";
  if (filename.includes("la")) return "Heart";
  return "Unknown";
}

export default function CorrectedPage() {
  const router = useRouter();
  const [correctedTasks, setCorrectedTasks] = useState<CorrectedTask[]>([]);
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [resolution, setResolution] = useState<"2d" | "3d" | "3d_fullres">("3d_fullres");
  const [filter, setFilter] = useState<"All" | "Brain" | "Heart">("All");
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [showResolutionModal, setShowResolutionModal] = useState(false);
  const [cvatUsername, setCvatUsername] = useState("");
  const [cvatPassword, setCvatPassword] = useState("");

  useEffect(() => {
    fetchCorrectedTasks();
  }, []);

  const fetchCorrectedTasks = async () => {
    try {
      const res = await fetch("http://localhost:5328/cvat/corrected-tasks", {
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok || !Array.isArray(data.correctedTasks)) {
        throw new Error(data.error || "Failed to fetch tasks");
      }

      const tasks: CorrectedTask[] = data.correctedTasks.map((t: any) => {
        const raw = t.task_name as string;          
        const type = getDatasetType(raw);
        return {
          task_id: t.task_id,
          task_name: raw,
          displayName: getDisplayName(raw),        
          scanType: type,
        };
      });

      setCorrectedTasks(tasks);
    } catch (err) {
      console.error(err);
      toast.error("Could not load corrected tasks");
    } finally {
      setIsLoading(false);
    }
  };

  // filter by scanType only
  const filteredTasks = correctedTasks.filter((t) =>
    filter === "All" ? true : t.scanType === filter
  );

  const handleFilterChange = (f: "All" | "Brain" | "Heart") => {
    setFilter(f);
  };

  const toggleTask = (id: string) => {
    setSelectedTasks((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const submitToCVAT = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTasks.length) {
      toast.error("Select at least one task");
      return;
    }
    setIsProcessing(true);
    try {
      const payload = correctedTasks
        .filter((t) => selectedTasks.includes(t.task_id))
        .map((t) => ({ task_id: t.task_id, formatted_name: t.displayName }));

      const res = await fetch("http://localhost:5328/cvat/send-to-dataset", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: cvatUsername,
          password: cvatPassword,
          task_ids: selectedTasks,
          tasks: payload,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Send failed");
      toast.success("Sent to CVAT!");
      setShowCredentialsModal(false);
      setCvatUsername("");
      setCvatPassword("");
      fetchCorrectedTasks();
    } catch (err) {
      console.error(err);
      toast.error("Failed to send to Dataset");
    } finally {
      setIsProcessing(false);
    }
  };

  const startTraining = async () => {
    if (!selectedTasks.length) {
      toast.error("Select at least one task");
      return;
    }
    setShowResolutionModal(false);
    setIsProcessing(true);
    try {
      const payload = correctedTasks
        .filter((t) => selectedTasks.includes(t.task_id))
        .map((t) => ({ task_id: t.task_id, formatted_name: t.displayName }));

      const res = await fetch("http://localhost:5328/train-nnunet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolution, tasks: payload }),
      });
      if (!res.ok) throw new Error("Train failed");
      toast.success("Training started!");
      router.push("/training");
    } catch (err) {
      console.error(err);
      toast.error("Training error");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-100 to-gray-300">
      <DashboardNav />
      <main className="max-w-6xl mx-auto p-6">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {/* Header + Tabs */}
          <div className="flex flex-col md:flex-row md:justify-between items-center mb-8 gap-4">
            <h1 className="text-3xl font-bold">Corrected Tasks</h1>
            <div className="inline-flex rounded-md shadow-sm">
              {(["All", "Brain", "Heart"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => handleFilterChange(type)}
                  className={`px-4 py-2 text-sm font-medium border ${
                    filter === type
                      ? "bg-blue-600 text-white"
                      : "bg-white text-gray-700 hover:bg-gray-100"
                  } border-gray-200 ${
                    type === "All"
                      ? "rounded-l-lg"
                      : type === "Heart"
                      ? "rounded-r-lg"
                      : ""
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* Table or Empty */}
          {isLoading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-xl">
              <p className="text-gray-500">
                No corrected {filter.toLowerCase()} tasks
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto border rounded-lg">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Select
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Type
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredTasks.map((t) => (
                      <tr key={t.task_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4">
                          <input
                            type="checkbox"
                            checked={selectedTasks.includes(t.task_id)}
                            onChange={() => toggleTask(t.task_id)}
                            className="h-4 w-4 text-blue-600"
                          />
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {t.displayName}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {t.scanType}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-6 flex justify-end gap-4">
                <button
                  onClick={() => setShowCredentialsModal(true)}
                  disabled={!selectedTasks.length || isProcessing}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg disabled:opacity-50"
                >
                  Send to Dataset
                </button>
                <button
                  onClick={() => setShowResolutionModal(true)}
                  disabled={!selectedTasks.length || isProcessing}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
                >
                  {isProcessing ? "Processing…" : "Train Model"}
                </button>
              </div>
            </>
          )}
        </div>
      </main>

      {/* CVAT Credentials Modal */}
      {showCredentialsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white p-6 rounded-xl shadow-xl w-full max-w-md">
            <h2 className="text-2xl mb-4">CVAT Credentials</h2>
            <form onSubmit={submitToCVAT} className="space-y-4">
              <input
                className="w-full px-3 py-2 border rounded"
                placeholder="Username"
                value={cvatUsername}
                onChange={(e) => setCvatUsername(e.target.value)}
                required
              />
              <input
                type="password"
                className="w-full px-3 py-2 border rounded"
                placeholder="Password"
                value={cvatPassword}
                onChange={(e) => setCvatPassword(e.target.value)}
                required
              />
              <div className="flex justify-end gap-4 mt-6">
                <button
                  type="button"
                  onClick={() => setShowCredentialsModal(false)}
                  className="px-4 py-2 text-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isProcessing}
                  className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
                >
                  {isProcessing ? "…Sending" : "Send"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Resolution Modal */}
      {showResolutionModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white p-6 rounded-xl shadow-xl w-full max-w-md">
            <h2 className="text-2xl mb-4">Select Resolution</h2>
            <div className="space-y-4">
              <select
                className="w-full px-3 py-2 border rounded"
                value={resolution}
                onChange={(e) =>
                  setResolution(e.target.value as any)
                }
              >
                <option value="2d">2D</option>
                <option value="3d">3D</option>
                <option value="3d_fullres">3D FullRes</option>
              </select>
              <div className="flex justify-end gap-4 mt-6">
                <button
                  onClick={() => setShowResolutionModal(false)}
                  className="px-4 py-2 text-gray-700"
                >
                  Cancel
                </button>
                <button
                  onClick={startTraining}
                  disabled={isProcessing}
                  className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
                >
                  {isProcessing ? "…Starting" : "Start Training"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
