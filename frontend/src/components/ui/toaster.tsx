
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast"
import { useToast } from "@/hooks/useToast"

export function Toaster() {
  const { toasts } = useToast()

  return (
    <ToastProvider>
      {toasts.map(function ({ id, ...props }) {
        return (
          <Toast key={id} {...props}>
            <div className="flex-1 grid gap-1">
              {props.title && <ToastTitle>{props.title}</ToastTitle>}
              {props.description && (
                <ToastDescription>{props.description}</ToastDescription>
              )}
              {props.action && <div className="mt-1.5">{props.action}</div>}
            </div>
            <ToastClose />
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
