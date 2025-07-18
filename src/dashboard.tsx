"use client";

import * as React from "react";
import { AppSidebar } from "./components/AppSidebar";
import { StarOnGithubPopup } from "./components/StarOnGithubPopup";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { SimpleSelect } from "@/components/ui/simple-select";
import { Download, Rocket, Lock, X } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { NodeGraph } from "./components/nodegraph/NodeGraph";

export default function Dashboard() {
  // Info alert dismissed state
  const [infoAlertDismissed, setInfoAlertDismissed] = React.useState(false);

  // // Check if any nodes are disabled
  // const hasDisabledNodes = React.useMemo(() => {
  //   return sections.some((section) =>
  //   //   //section.nodes.some((node) => "disabled" in node && node.disabled),

  //   // //);
  //   // false
  // }, []);

  const hasDisabledNodes = false
  return (
    <SidebarProvider>
      <div className="flex w-screen h-screen">
        <AppSidebar />
        <SidebarInset className="flex-1 min-w-0 z-0 flex flex-col">
          <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4 relative z-10">
            <div className="flex items-center gap-2">
              <SidebarTrigger />
              <Separator orientation="vertical" className="mr-2 h-4" />
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem className="hidden md:block">
                    <BreadcrumbLink href="#">Autoroad</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator className="hidden md:block" />
                  <BreadcrumbItem>
                    <BreadcrumbPage>Autoroad</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4" />
                Export
              </Button>
              <Button size="sm">Open in CourseRoad</Button>
            </div>
          </header>
          <div className="flex flex-col p-4 gap-4 flex-grow min-h-0 relative z-0">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Autoroad</h1>
                <p className="text-muted-foreground">
                  Integer Programming Test
                </p>
              </div>
              <div className="flex items-center gap-2">
                <SimpleSelect
                  className="w-40"
                  placeholder="Select Year"
                  options={[
                    { value: "freshman", label: "Freshman" },
                    { value: "sophomore", label: "Sophomore" },
                    { value: "junior", label: "Junior" },
                    { value: "senior", label: "Senior" },
                  ]}
                  onValueChange={(value) => console.log("Selected:", value)}
                />
                <Button size="sm" variant="outline">
                  Optimize!
                </Button>
              </div>
            </div>

            {/* Alerts constrained with max height and internal scroll */}
            {hasDisabledNodes || !infoAlertDismissed ? (
              <div>
                {hasDisabledNodes ? (
                  <Alert className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20 py-2 px-3 text-sm">
                    <Lock className="h-4 w-4 text-yellow-600" />
                    <AlertDescription className="text-yellow-800 dark:text-yellow-200">
                      <strong>Warning</strong> You&apos;ve added a forced class
                      to a semester! Make sure to click the optimize button to
                      see if it will fit.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert className="border-blue-500 bg-blue-50 dark:bg-blue-950/20 relative pr-10 py-2 px-3 text-sm">
                    <Rocket className="h-4 w-4 text-blue-600" />
                    <AlertDescription className="text-blue-800 dark:text-blue-200">
                      <strong>Welcome!</strong> This is the Autoroad dashboard.
                      Here you can plan your semesters and optimize your
                      schedule.
                    </AlertDescription>
                    <button
                      onClick={() => setInfoAlertDismissed(true)}
                      className="absolute top-0.5 right-0.5 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="Close"
                      style={{
                        background: "none",
                        border: "none",
                        fontSize: 20,
                        cursor: "pointer",
                        lineHeight: 1,
                      }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </Alert>
                )}
              </div>
            ) : null}

            {/* NodeGraph area fills remaining space without internal scroll */}
            <div className="flex-grow relative min-h-0">
              <NodeGraph />
            </div>
          </div>
        </SidebarInset>
        <StarOnGithubPopup />
      </div>
    </SidebarProvider>
  );
}
