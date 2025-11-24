"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { extractCoursesFromRequirement, prefetchCourses } from "@/lib/cache";

export function RequirementPrefetcher() {
  const queryClient = useQueryClient();
  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);
  const prevRequirementsRef = React.useRef<string[]>([]);

  React.useEffect(() => {
    const newRequirements = selectedRequirements.filter(
      req => !prevRequirementsRef.current.includes(req)
    );

    if (newRequirements.length > 0) {
      newRequirements.forEach(async (requirement) => {
        const courseIds = await extractCoursesFromRequirement(requirement);
        if (courseIds.length > 0) {
          prefetchCourses(queryClient, courseIds);
        }
      });
    }

    prevRequirementsRef.current = selectedRequirements;
  }, [selectedRequirements, queryClient]);

  return null;
}
