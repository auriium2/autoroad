import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";

export function ErrorDisplay({ 
  error, 
  onRetry, 
  title = "Something went wrong" 
}: { error: string; onRetry?: () => void; title?: string }) {
  return (
    <div className="flex items-center justify-center h-full p-8">
      <Alert variant="destructive" className="max-w-lg">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription className="mt-2">
          <p className="mb-4">{error}</p>
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="gap-2"
            >
              <RefreshCw className="h-3 w-3" />
              Try Again
            </Button>
          )}
        </AlertDescription>
      </Alert>
    </div>
  );
}
