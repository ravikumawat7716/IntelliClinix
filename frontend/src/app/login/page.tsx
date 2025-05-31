"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { BrainCircuit, Loader2, Lock, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/hooks/use-toast"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const { toast } = useToast()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage("") // Clear previous errors
    setIsLoading(true)

    if (!username || !password) {
      setErrorMessage("Both username and password are required.")
      setIsLoading(false)
      return
    }

    try {
      const response = await fetch("http://localhost:5328/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Important for cookies
        body: JSON.stringify({ username, password }),
      })

      const data = await response.json()

      if (response.ok) {
        toast({
          title: "Login successful!",
          description: "Redirecting to annotation dashboard...",
          variant: "default",
        })
        document.cookie = `token=${data.token}; path=/; SameSite=Lax` // Store token securely
        router.push("/newupload") // Redirect to newupload page (fixed path)
      } else {
        setErrorMessage(data.error || "Invalid credentials.")
      }
    } catch (error) {
      setErrorMessage("Failed to connect to the server. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-teal-900 via-slate-900 to-slate-900 p-4">
      {/* Medical-themed decorative elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute top-10 left-10 w-64 h-64 bg-teal-500/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-10 right-10 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"></div>
      </div>

      <div className="w-full text-center mb-6 relative">
        <div className="inline-flex items-center justify-center mb-2">
          <BrainCircuit className="h-12 w-12 text-teal-400 mr-2" />
          <h1 className="text-5xl sm:text-6xl font-bold text-white">MedNet</h1>
        </div>
        <p className="text-teal-200 text-lg">AI-Powered Medical Imaging Annotation</p>
      </div>

      <Card className="w-full max-w-md bg-white/10 backdrop-blur-md border-teal-900/30 text-white shadow-xl">
        <CardHeader>
          <CardTitle className="text-2xl text-center text-white">Welcome Back</CardTitle>
          <CardDescription className="text-teal-200 text-center">
            Sign in to access your medical annotation workspace
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleLogin}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-white">
                Username
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-5 w-5 text-teal-300" />
                <Input
                  id="username"
                  type="text"
                  placeholder="Enter your username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="bg-slate-800/50 border-slate-700 text-white pl-10 focus-visible:ring-teal-500"
                  disabled={isLoading}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-white">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-5 w-5 text-teal-300" />
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="bg-slate-800/50 border-slate-700 text-white pl-10 focus-visible:ring-teal-500"
                  disabled={isLoading}
                  required
                />
              </div>
            </div>

            {errorMessage && (
              <div className="bg-red-900/30 border border-red-800 text-red-200 p-3 rounded-md text-sm">
                {errorMessage}
              </div>
            )}
          </CardContent>

          <CardFooter>
            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-white font-medium"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Authenticating...
                </>
              ) : (
                "Sign In"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <div className="mt-8 text-center text-teal-200/60 text-sm max-w-md">
        <p>MedNet uses advanced ML algorithms to enhance medical imaging annotation accuracy and efficiency.</p>
      </div>
    </div>
  )
}
