import * as React from 'react';
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

const TutorialContext = React.createContext<TutorialContextValue | null>(null);

const STORAGE_KEY = 'autoroad-tutorial-completed';

export function TutorialProvider({ children }: { children: React.ReactNode }) {
  const tourRef = React.useRef<InstanceType<typeof Shepherd.Tour> | null>(null);
  const [isActive, setIsActive] = React.useState(false);
  const queryClient = useQueryClient();

  // Set query client reference for steps.ts to use
  React.useEffect(() => {
    setQueryClient(queryClient);
  }, [queryClient]);

  React.useEffect(() => {
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

  const startTutorial = React.useCallback(() => {
    tourRef.current?.start();
  }, []);

  const getCurrentStepId = React.useCallback(() => {
    return tourRef.current?.getCurrentStep()?.id;
  }, []);

  const advanceTutorial = React.useCallback(() => {
    tourRef.current?.next();
  }, []);

  const value = React.useMemo(
    () => ({ startTutorial, isActive, getCurrentStepId, advanceTutorial }),
    [startTutorial, isActive, getCurrentStepId, advanceTutorial]
  );

  return (
    <TutorialContext.Provider value={value}>
      {children}
    </TutorialContext.Provider>
  );
}

export function useTutorial() {
  const ctx = React.useContext(TutorialContext);
  if (!ctx) {
    throw new Error('useTutorial must be used within TutorialProvider');
  }
  return ctx;
}
