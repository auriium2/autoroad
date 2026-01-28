import { createContext, useContext, useRef, useState, useEffect, type ReactNode } from 'react';
import Shepherd from 'shepherd.js';
import { useQueryClient, useQuery } from '@tanstack/react-query';
import 'shepherd.js/dist/css/shepherd.css';
import './tutorial.css';
import { tutorialSteps, restoreState, setQueryClient } from './steps';
import { queryKeys } from '@/lib/queryKeys';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface TutorialContextValue {
  startTutorial: () => void;
  isActive: boolean;
  getCurrentStepId: () => string | undefined;
  advanceTutorial: () => void;
}

const TutorialContext = createContext<TutorialContextValue | null>(null);

const STORAGE_KEY = 'autoroad-tutorial-completed-v2';

export function TutorialProvider({ children }: { children: ReactNode }) {
  const tourRef = useRef<InstanceType<typeof Shepherd.Tour> | null>(null);
  const [isActive, setIsActive] = useState(false);
  const queryClient = useQueryClient();

  // Check backend health before starting tutorial
  const { data: healthData, isSuccess: isHealthy } = useQuery({
    queryKey: queryKeys.health.backend(),
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/health`, {
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Health check failed');
      return response.json();
    },
    staleTime: 30000,
    retry: 2,
  });

  const backendHealthy = isHealthy && healthData?.services?.backend?.status === 'healthy';

  // Set query client reference for steps.ts to use
  useEffect(() => {
    setQueryClient(queryClient);
  }, [queryClient]);

  useEffect(() => {
    const tour = new Shepherd.Tour({
      useModalOverlay: true,
      defaultStepOptions: {
        cancelIcon: { enabled: true },
        scrollTo: false,
        modalOverlayOpeningPadding: 8,
        modalOverlayOpeningRadius: 8,
      },
    });

    // Add all steps
    tutorialSteps.forEach((step) => {
      tour.addStep(step);
    });

    tour.on('complete', () => {
      localStorage.setItem(STORAGE_KEY, 'true');
      setIsActive(false);
    });

    tour.on('cancel', () => {
      localStorage.setItem(STORAGE_KEY, 'true');
      setIsActive(false);
      // Restore user's original state when they cancel
      restoreState();
    });

    tour.on('start', () => {
      setIsActive(true);
    });

    tourRef.current = tour;

    return () => {
      if (tour.isActive()) {
        restoreState();
      }
      tour.complete();
    };
  }, []);

  // Auto-start tutorial for first-time visitors once backend is healthy
  useEffect(() => {
    if (!tourRef.current) return;

    const hasCompletedTutorial = localStorage.getItem(STORAGE_KEY);
    const isMobile = window.matchMedia('(max-width: 767px)').matches;
    if (isMobile) {
      localStorage.setItem(STORAGE_KEY, 'true');
      return;
    }

    // Wait for backend to be healthy before starting tutorial
    if (!backendHealthy) return;

    if (!hasCompletedTutorial && !tourRef.current.isActive()) {
      const timeoutId = setTimeout(() => {
        tourRef.current?.start();
      }, 500);
      return () => clearTimeout(timeoutId);
    }

  }, [backendHealthy]);

  const startTutorial = () => {
    // Don't start tutorial on mobile
    if (window.matchMedia('(max-width: 767px)').matches) return;
    tourRef.current?.start();
  };

  const getCurrentStepId = () => {
    return tourRef.current?.getCurrentStep()?.id;
  };

  const advanceTutorial = () => {
    tourRef.current?.next();
  };

  const value = { startTutorial, isActive, getCurrentStepId, advanceTutorial };

  return (
    <TutorialContext.Provider value={value}>
      {children}
    </TutorialContext.Provider>
  );
}

export function useTutorial() {
  const ctx = useContext(TutorialContext);
  if (!ctx) {
    throw new Error('useTutorial must be used within TutorialProvider');
  }
  return ctx;
}
