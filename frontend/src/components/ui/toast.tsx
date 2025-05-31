"use client"

import * as React from "react"
import { type VariantProps, cva } from "class-variance-authority"
import { AnimatePresence, motion } from "framer-motion"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const toastVariants = cva(
  "pointer-events-auto relative flex w-full items-center space-x-4 overflow-hidden rounded-md border p-4 pr-6 shadow-lg transition-all",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground",
        success: "bg-green-600 text-white",
        destructive: "bg-red-600 text-white",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export type ToastProps = React.HTMLAttributes<HTMLDivElement> &
  VariantProps<typeof toastVariants> & {
    title?: string
    description?: string
    id: string
    onClose?: () => void
  }

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({ className, title, description, variant, id, onClose, ...props }, ref) => {
    return (
      <motion.div
        initial={{ opacity: 0, y: 50 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 50 }}
        layout
      >
        <div
          ref={ref}
          className={cn(toastVariants({ variant }), className)}
          {...props}
        >
          <div className="flex-1">
            {title && <p className="text-sm font-semibold">{title}</p>}
            {description && <p className="text-sm opacity-90">{description}</p>}
          </div>
          <button
            className="absolute top-2 right-2 text-white/60 hover:text-white transition"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </motion.div>
    )
  }
)
Toast.displayName = "Toast"

export interface ToastContextType {
  toast: (options: Omit<ToastProps, "id">) => void
}

export const ToastContext = React.createContext<ToastContextType | undefined>(
  undefined
)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastProps[]>([])

  const toast = (options: Omit<ToastProps, "id">) => {
    const id = crypto.randomUUID()
    setToasts((current) => [
      ...current,
      { ...options, id, onClose: () => removeToast(id) },
    ])
  }

  const removeToast = (id: string) => {
    setToasts((current) => current.filter((t) => t.id !== id))
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        <AnimatePresence>
          {toasts.map((t) => (
            <Toast key={t.id} {...t} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
