
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
            <div className="grid gap-1">
              {props.title && <ToastTitle>{props.title}</ToastTitle>}
              {props.description && (
                <ToastDescription>{props.description}</ToastDescription>
              )}
            </div>
            {props.action}
            <ToastClose />
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
