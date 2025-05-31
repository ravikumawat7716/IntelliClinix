// src/hooks/use-toast.ts

import * as React from "react"
import { toast as sonner } from "sonner"

export function useToast() {
  const toast = React.useCallback((props: Parameters<typeof sonner>[0]) => {
    sonner(props)
  }, [])

  return {
    toast,
  }
}
