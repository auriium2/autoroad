import { createContext, useContext, useRef, useState, useEffect, type ReactNode } from 'react';
import Shepherd from 'shepherd.js';
import { useQueryClient } from '@tanstack/react-query';
import 'shepherd.js/dist/css/shepherd.css';
import './tutorial.css';
import { tutorialSteps, restoreState, setQueryClient } from './steps';

interface TutorialContextValue {
  startTutorial: () => void;
  isActive: boolean;
  getCurrentStepId: () => string | undefined;
  advanceTutorial: () => void;
}

const TutorialContext = createContext<TutorialContextValue | null>(null);

const STORAGE_KEY = 'autoroad-tutorial-completed';

export function TutorialProvider({ children }: { children: ReactNode }) {
  const tourRef = useRef<InstanceType<typeof Shepherd.Tour> | null>(null);
  const [isActive, setIsActive] = useState(false);
  const queryClient = useQueryClient();

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

    // Auto-start tutorial for first-time visitors (desktop only)
    const hasCompletedTutorial = localStorage.getItem(STORAGE_KEY);
    const isMobile = window.innerWidth < 768;
    if (!hasCompletedTutorial && !isMobile) {
      // Small delay to ensure the UI is fully rendered
      const timeoutId = setTimeout(() => {
        tour.start();
      }, 500);
      return () => {
        clearTimeout(timeoutId);
        if (tour.isActive()) {
          restoreState();
        }
        tour.complete();
      };
    }

    return () => {
      if (tour.isActive()) {
        restoreState();
      }
      tour.complete();
    };
  }, []);

  const startTutorial = () => {
    // Don't start tutorial on mobile
    if (window.innerWidth < 768) return;
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
