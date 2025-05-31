import type { NextApiRequest, NextApiResponse } from "next";
import axios from "axios";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ message: "Method not allowed" });
  }

  try {
    const response = await axios.post("http://localhost:5000/create-cvat-task", req.body);
    res.status(200).json(response.data);
  } catch (error) {
    console.error("Error creating CVAT task:", error);
    res.status(500).json({ message: "Error creating CVAT task" });
  }
}
