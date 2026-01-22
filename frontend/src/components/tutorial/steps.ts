import type { StepOptions } from 'shepherd.js';
import { QueryClient } from '@tanstack/react-query';
import { useGraphStore } from '@/stores/roadStore';
import {
  DEMO_MARKERS_WITH_PROBLEMS,
  DEMO_MARKERS_FIXED_SEMESTER,
  DEMO_MARKERS_ALL_FIXED,
  DEMO_OPTIMIZER_NODES,
  DEMO_COST_BREAKDOWN,
  DEMO_SIMPLE_MARKERS,
} from './demoData';

// Reference to the query client - set by TutorialProvider
let queryClient: QueryClient | null = null;

export function setQueryClient(client: QueryClient) {
  queryClient = client;
}

// Helper to wait for element
function waitForElement(selector: string, timeout = 2000): Promise<Element | null> {
  return new Promise((resolve) => {
    const element = document.querySelector(selector);
    if (element) {
      resolve(element);
      return;
    }

    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) {
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => {
      observer.disconnect();
      resolve(document.querySelector(selector));
    }, timeout);
  });
}

// State management
let savedMarkers: ReturnType<typeof useGraphStore.getState>['markers'] | null = null;
let savedOptimizerNodes: ReturnType<typeof useGraphStore.getState>['optimizerNodes'] | null = null;
let savedCostBreakdown: ReturnType<typeof useGraphStore.getState>['lastCostBreakdown'] | null = null;
let savedStatus: ReturnType<typeof useGraphStore.getState>['lastOptimizationStatus'] | null = null;

function saveCurrentState() {
  const store = useGraphStore.getState();
  savedMarkers = [...store.markers];
  savedOptimizerNodes = [...store.optimizerNodes];
  savedCostBreakdown = store.lastCostBreakdown;
  savedStatus = store.lastOptimizationStatus;
}

export function restoreState() {
  if (savedMarkers !== null) {
    useGraphStore.setState({
      markers: savedMarkers,
      optimizerNodes: savedOptimizerNodes || [],
      lastCostBreakdown: savedCostBreakdown,
      lastOptimizationStatus: savedStatus,
      markersChangedSinceOptimization: false,
    });
  }
  savedMarkers = null;
  savedOptimizerNodes = null;
  savedCostBreakdown = null;
  savedStatus = null;
}

function loadState(markers: typeof DEMO_MARKERS_WITH_PROBLEMS, optimizerNodes: typeof DEMO_OPTIMIZER_NODES = [], status: 'OPTIMAL' | null = null) {
  // Reset prerequisite queries BEFORE updating state to avoid showing stale data
  // resetQueries clears the cache entirely (unlike invalidateQueries which keeps stale data)
  if (queryClient) {
    queryClient.resetQueries({ queryKey: ['prerequisites'] });
  }

  useGraphStore.setState({
    markers,
    optimizerNodes,
    lastCostBreakdown: status ? DEMO_COST_BREAKDOWN : null,
    lastOptimizationStatus: status,
    markersChangedSinceOptimization: false,
  });
}

// Check if 6.120A is in a valid semester (Fall or Spring, not IAP)
function is61200Fixed(): boolean {
  const markers = useGraphStore.getState().markers;
  const marker = markers.find(m => m.courseId === '6.120A');
  // Valid semesters for 6.120A: 0 (Fall), 2 (Spring), 4, 6, 8, 10 (other Falls/Springs)
  // IAP is section 1, 3, 5, etc.
  return marker ? marker.section !== 1 && marker.section >= 0 : false;
}

// Check if 6.1010's prerequisites are satisfied (6.1000 is in schedule before it)
function is61010PrereqFixed(): boolean {
  const markers = useGraphStore.getState().markers;
  const marker6100 = markers.find(m => m.courseId === '6.1000');
  const marker61010 = markers.find(m => m.courseId === '6.1010');
  if (!marker6100 || !marker61010) return false;
  // 6.1000 must be in a semester before 6.1010
  return marker6100.section < marker61010.section;
}

export const tutorialSteps: StepOptions[] = [
  // ==========================================
  // WELCOME
  // ==========================================
  {
    id: 'welcome',
    title: 'Welcome to Autoroad',
    text: `Autoroad helps you complete your degree by picking the easiest classes that satisfies it.</br></br>Let's learn how to use it!`,
    buttons: [
      { text: 'Skip', action: function() { restoreState(); return this.complete(); }, secondary: true },
      { text: 'Start', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return new Promise<void>((resolve) => {
        saveCurrentState();
        loadState([], []);
        setTimeout(resolve, 100);
      });
    },
  },

  // ==========================================
  // THE GRID
  // ==========================================
  {
    id: 'the-grid',
    title: 'Your 4-Year Schedule',
    text: `This grid shows your schedule from Freshman Fall to Senior Spring. Each colored circle is a <strong style="color: #93c5fd">course marker</strong>, which is how you tell the optimizer what you want to take.`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { loadState([], []); return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return new Promise<void>((resolve) => {
        loadState(DEMO_MARKERS_WITH_PROBLEMS);
        setTimeout(resolve, 400);
      });
    },
  },

  // ==========================================
  // HOVER NODE
  // ==========================================
  {
    id: 'hover-node',
    title: 'Course Markers',
    text: `Courses in a normal state are <strong style="color: #93c5fd">blue</strong>.<br><br>
      Try hovering over this node to see more details.`,
    attachTo: { element: '[data-course-id="18.01"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  // ==========================================
  // SPECIAL COLUMNS
  // ==========================================
  {
    id: 'special-columns',
    title: 'Special Columns',
    text: `The first two columns are special.<br><br>
      <strong style="color: #a78bfa">Must Take</strong>: courses you want to take at some point.</br>
      <strong>ASEs</strong>: courses you've tested out of.`,
    attachTo: { element: '[data-tutorial="must-take-column"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  // ==========================================
  // MUST TAKE EXPLANATION
  // ==========================================
  {
    id: 'must-take-nodes',
    title: 'Must Take Nodes',
    text: `<strong style="color: #a78bfa">Normal markers</strong> placed here mean "I want this course, but the optimizer can pick the best semester for it."<br><br><strong style="color: #ef4444">Banish</strong> markers placed here tell autoroad to avoid ever taking this class.`,
    attachTo: { element: '[data-course-id="8.01"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  // ==========================================
  // WRONG SEMESTER WARNING
  // ==========================================
  {
    id: 'wrong-semester',
    title: 'Wrong Semester Warning',
    text: `Look at 6.120A. It's yellow!<br><br><strong style="color: #fbbf24">Warning markers</strong> have been placed in semesters where they aren't offered.
      To avoid this, try reading the ring. A full ring means a class is offered in <strong style="background: linear-gradient(90deg, #f97316, #22c55e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">both semesters</strong>, while left is offered in <strong style="color: #f97316">Fall</strong> and right is offered in <strong style="color: #22c55e">Spring</strong>.`,
    attachTo: { element: '[data-course-id="6.120A"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Let\'s Fix It', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'fix-semester',
    title: 'Fix: Move to Spring',
    text: `Drag 6.120A from IAP to Freshman Spring.`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          if (is61200Fixed()) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          loadState(DEMO_MARKERS_FIXED_SEMESTER);
          return this.next();
        },
        secondary: true,
      },
    ],
    when: {
      show: function() {
        const step = this;
        const checkInterval = setInterval(() => {
          if (is61200Fixed()) {
            // Enable the Next button
            const nextBtn = step.el?.querySelector('.shepherd-button:not(.shepherd-button-secondary)') as HTMLButtonElement;
            if (nextBtn) {
              nextBtn.disabled = false;
              nextBtn.classList.remove('shepherd-button-disabled');
            }
            clearInterval(checkInterval);
          }
        }, 500);
        // Store interval ID for cleanup
        (step as unknown as { _checkInterval: ReturnType<typeof setInterval> })._checkInterval = checkInterval;
      },
      hide: function() {
        const step = this as unknown as { _checkInterval?: ReturnType<typeof setInterval> };
        if (step._checkInterval) {
          clearInterval(step._checkInterval);
        }
      },
    },
  },

  // ==========================================
  // MISSING PREREQ
  // ==========================================
  {
    id: 'missing-prereq',
    title: 'Missing Prerequisite',
    text: `Now look at 6.1010: it has a <strong style="color: #ef4444">red border</strong> and shows <strong style="color: #ef4444">6.1000</strong> floating above it.
      This means 6.1010 requires 6.1000, which isn't in your schedule yet!<br><br><i><small>More specifically, the classes shown above a missing prerequisite marker are the minimum required set to complete that class. If you hover over 6.1010, you'll see it can also be completed by taking 6.100a AND 6.100b, which would take too long.</small></i>`,
    attachTo: { element: '[data-course-id="6.1010"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_WITH_PROBLEMS); return this.back(); }, secondary: true },
      { text: 'Let\'s Add It', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return new Promise<void>((resolve) => {
        loadState(DEMO_MARKERS_FIXED_SEMESTER);
        setTimeout(resolve, 400);
      });
    },
  },

  {
    id: 'fix-prereq',
    title: 'Fix: Add 6.1000',
    text: `Search for <strong>6.1000</strong> in the Courses tab and drag it to a semester before 6.1010.`,
    attachTo: { element: '[data-tutorial="course-search"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000, // Large padding to allow interaction with entire page
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          if (is61010PrereqFixed()) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          loadState(DEMO_MARKERS_ALL_FIXED);
          return this.next();
        },
        secondary: true,
      },
    ],
    when: {
      show: function() {
        const step = this;
        const checkInterval = setInterval(() => {
          if (is61010PrereqFixed()) {
            // Enable the Next button
            const nextBtn = step.el?.querySelector('.shepherd-button:not(.shepherd-button-secondary)') as HTMLButtonElement;
            if (nextBtn) {
              nextBtn.disabled = false;
              nextBtn.classList.remove('shepherd-button-disabled');
            }
            clearInterval(checkInterval);
          }
        }, 500);
        (step as unknown as { _checkInterval: ReturnType<typeof setInterval> })._checkInterval = checkInterval;
      },
      hide: function() {
        const step = this as unknown as { _checkInterval?: ReturnType<typeof setInterval> };
        if (step._checkInterval) {
          clearInterval(step._checkInterval);
        }
      },
    },
  },

  // ==========================================
  // ALL FIXED
  // ==========================================
  {
    id: 'all-fixed',
    title: 'All Fixed!',
    text: `Now 6.1000 satisfies 6.1010's prerequisite. The arrows show the prerequisite relationship. No more red borders!`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000, // Large padding to allow interaction with entire page
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_FIXED_SEMESTER); return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return new Promise<void>((resolve) => {
        loadState(DEMO_MARKERS_ALL_FIXED);
        setTimeout(resolve, 400);
      });
    },
  },

  // ==========================================
  // RIGHT-CLICK MENU
  // ==========================================
  {
    id: 'right-click',
    title: 'Right-Click Options',
    text: `Right-click any course for more options:<br><br>
      <strong>Pin</strong>: the normal functionality<br>
      <strong>Override</strong>: ignore prerequisites (for petitions)<br>
      <strong style="color: #ef4444">Banish</strong>: never take this course in this semester`,
    attachTo: { element: '[data-course-id="6.120A"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  // ==========================================
  // OPTIMIZATION
  // ==========================================
  {
    id: 'ready-to-optimize',
    title: 'Ready to Optimize',
    text: `Your markers look good! Click <strong>Optimize</strong> to have Autoroad fill in the rest of your schedule.<br><br>
      It will satisfy your degree requirements while respecting your markers.`,
    attachTo: { element: '[data-tutorial="optimize-button"]', on: 'bottom' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'See Result', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'optimized',
    title: 'Optimization Complete!',
    text: `<strong style="color: #d1d5db">White circles</strong> are the optimizer's suggestions.<br><br>
      The <strong style="color: #22c55e">green border</strong> means this is mathematically optimal!<br><br>
      Notice 8.01 was placed in Fall (from Must Take), and GIRs were filled in.`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_ALL_FIXED); return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return new Promise<void>((resolve) => {
        loadState(DEMO_MARKERS_ALL_FIXED, DEMO_OPTIMIZER_NODES, 'OPTIMAL');
        setTimeout(resolve, 400);
      });
    },
  },

  {
    id: 'convert-to-marker',
    title: 'Keep Suggestions',
    text: `Want to keep an optimizer suggestion for next time?<br><br>
      <strong>Right-click → "Convert to marker"</strong><br><br>
      This turns white circles into blue markers that persist.`,
    attachTo: { element: '[data-course-id="6.006"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  // ==========================================
  // OBJECTIVES TAB
  // ==========================================
  {
    id: 'objectives-tab',
    title: 'Objectives Tab',
    text: `The <strong>Objectives</strong> tab lets you configure:<br><br>
      • Which degrees you're pursuing<br>
      • How to optimize (minimize units, balance workload, etc.)<br>
      • Priority tiers for what matters most`,
    attachTo: { element: '[data-tutorial="sidebar-tabs"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'tiers',
    title: 'Priority Tiers (⭐)',
    text: `Click the ⭐ icons to set priority tiers (1-4).<br><br>
      <strong>Higher tier = optimizer tries harder</strong><br><br>
      Tier 4: "Must have"<br>
      Tier 1: "Nice to have"`,
    attachTo: { element: '[data-tutorial="tier-selector"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return waitForElement('[data-tutorial="tier-selector"]').then(() => {});
    },
  },

  // ==========================================
  // FINISH
  // ==========================================
  {
    id: 'finish',
    title: 'You\'re Ready!',
    text: `<strong>Quick reference:</strong><br><br>
      <strong style="color: #fbbf24">Yellow ⚠️</strong> = wrong semester<br>
      <strong style="color: #ef4444">Red border</strong> = missing prereq<br>
      <strong style="color: #22c55e">Green border</strong> = optimal solution<br>
      <strong style="color: #eab308">Yellow border</strong> = re-optimize needed<br><br>
      Click <strong>Tutorial</strong> anytime to revisit.`,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Get Started', action: function() { restoreState(); return this.complete(); } },
    ],
  },
];

export { restoreState as clearDemoData };
