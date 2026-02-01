import type { StepOptions } from 'shepherd.js';
import { QueryClient } from '@tanstack/react-query';
import { useGraphStore } from '@/stores/roadStore';
import { useOptimizationStore } from '@/stores/optimizationStore';
import {
  DEMO_MARKERS_WITH_PROBLEMS,
  DEMO_MARKERS_FIXED_SEMESTER,
  DEMO_MARKERS_ALL_FIXED,
  DEMO_MARKERS_OVERRIDE_FIXED,
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

// Helper to pan React Flow viewport to a course
function panToCourse(courseId: string): Promise<void> {
  return new Promise((resolve) => {
    const pan = (window as unknown as { panToCourse?: (id: string) => void }).panToCourse;
    if (pan) {
      pan(courseId);
      setTimeout(resolve, 350); // Wait for animation
    } else {
      resolve();
    }
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

// Check if 6.1010 has override status
function is61010Override(): boolean {
  const markers = useGraphStore.getState().markers;
  const marker61010 = markers.find(m => m.courseId === '6.1010');
  return marker61010?.status === 'override';
}

export const tutorialSteps: StepOptions[] = [
  // ==========================================
  // WELCOME
  // ==========================================
  {
    id: 'welcome',
    title: 'Welcome to Autoroad',
    text: `Do the full tutorial so things make sense<br><br>thanks`,
    buttons: [
      { text: 'Skip', action: function() { restoreState(); return this.complete(); }, secondary: true },
      { text: 'Start', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return new Promise<void>((resolve) => {
        saveCurrentState();
        loadState([], []);
        // Switch to courses tab
        const coursesTab = document.querySelector('[data-tab="courses"]') as HTMLElement;
        if (coursesTab) coursesTab.click();
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
    text: `Courses in a normal state are represented with <strong style="color: #93c5fd">blue</strong> nodes. The number inside is the units the class is worth.<br><br>
      Hover over nodes to see course details like prerequisites, hours, and ratings.`,
    attachTo: { element: '[data-course-id="18.01"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      await panToCourse('18.01');
      // Open the course tooltip
      const openTooltip = (window as unknown as Record<string, (open: boolean) => void>)['openCourseTooltip_18.01'];
      if (openTooltip) openTooltip(true);
      // Wait for tooltip to render
      await new Promise(resolve => setTimeout(resolve, 300));
    },
    when: {
      hide: function() {
        // Close the course tooltip
        const openTooltip = (window as unknown as Record<string, (open: boolean) => void>)['openCourseTooltip_18.01'];
        if (openTooltip) openTooltip(false);
      },
    },
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
    text: `<strong style="color: #a78bfa">Normal markers</strong> placed here mean "I want this course, but the optimizer can pick the best semester for it. <strong>Don't put your class requirements here</strong>. This is for classes <i>you want to take</i>."<br><br><strong style="color: #ef4444">Banish</strong> markers placed here tell autoroad to avoid ever taking this class.`,
    attachTo: { element: '[data-course-id="8.01"]', on: 'right' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: () => panToCourse('8.01'),
  },

  // ==========================================
  // WRONG SEMESTER WARNING
  // ==========================================
  {
    id: 'wrong-semester',
    title: 'Wrong Semester Warning',
    text: `<strong style="color: #fbbf24">Warning markers</strong> have been placed in semesters where they aren't offered.<br><br>
      To avoid this, try reading the ring. A full ring means a class is offered in <strong style="background: linear-gradient(90deg, #f97316, #22c55e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">both semesters</strong>, while left is offered in <strong style="color: #f97316">Fall</strong> and right is offered in <strong style="color: #22c55e">Spring</strong>.`,
    attachTo: { element: '[data-course-id="6.120A"]', on: 'right' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Let\'s Fix It', action: function() { return this.next(); } },
    ],
    beforeShowPromise: () => panToCourse('6.120A'),
  },

  {
    id: 'fix-semester',
    title: 'Fix: Move to Spring',
    text: `Drag the node with <strong>6.120A</strong> underneath it from the section labeled IAP to the section labeled Freshman Spring.`,
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
      This means 6.1010 requires 6.1000, which isn't in your schedule yet!`,
    attachTo: { element: '[data-course-id="6.1010"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_WITH_PROBLEMS); return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      loadState(DEMO_MARKERS_FIXED_SEMESTER);
      await new Promise(resolve => setTimeout(resolve, 400));
      await panToCourse('6.1010');
    },
  },

  {
    id: 'red-blocks-optimizer',
    title: 'Red Nodes Block Optimization',
    text: `<strong style="color: #ef4444">Red nodes</strong> have missing prerequisites. The optimizer won't run until you fix them.<br><br>
      Let's learn two ways to fix this.`,
    attachTo: { element: '[data-course-id="6.1010"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'fix-prereq',
    title: 'Fix #1: Add the Prereq',
    text: `The most common fix is adding the missing course.<br><br>
      Search for <strong>6.1000</strong> in the Courses tab and drag it to a semester before 6.1010.`,
    attachTo: { element: '[data-tutorial="course-search"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000,
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

  {
    id: 'prereq-fixed',
    title: 'Prereq Added',
    text: `The red border is gone because 6.1010 now has its prerequisite.<br><br>
      But what if you've already learned the material or have a petition? There's another way.`,
    attachTo: { element: '[data-course-id="6.1010"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_FIXED_SEMESTER); return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      loadState(DEMO_MARKERS_ALL_FIXED);
      await new Promise(resolve => setTimeout(resolve, 400));
      await panToCourse('6.1010');
    },
  },

  // ==========================================
  // OVERRIDE PREREQ
  // ==========================================
  {
    id: 'override-prereq',
    title: 'Fix #2: Override',
    text: `Let's reset and try the other method.<br><br>
      <strong>Right-click</strong> on 6.1010 and select <strong>Ignore Prerequisites / Semester</strong> to skip the prereq check.`,
    attachTo: { element: '[data-course-id="6.1010"]', on: 'left' },
    scrollTo: false,
    modalOverlayOpeningPadding: 5000,
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_ALL_FIXED); return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          if (is61010Override()) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          loadState(DEMO_MARKERS_OVERRIDE_FIXED);
          return this.next();
        },
        secondary: true,
      },
    ],
    beforeShowPromise: async function() {
      // Reset to state without 6.1000, so 6.1010 is red again
      loadState(DEMO_MARKERS_FIXED_SEMESTER);
      await new Promise(resolve => setTimeout(resolve, 400));
      await panToCourse('6.1010');
    },
    when: {
      show: function() {
        const step = this;
        const checkInterval = setInterval(() => {
          if (is61010Override()) {
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

  {
    id: 'override-result',
    title: 'Override Applied',
    text: `The red border is gone and the optimizer will accept it.`,
    attachTo: { element: '[data-course-id="6.1010"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_FIXED_SEMESTER); return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      loadState(DEMO_MARKERS_OVERRIDE_FIXED);
      await new Promise(resolve => setTimeout(resolve, 400));
      await panToCourse('6.1010');
    },
  },

  // ==========================================
  // ALL FIXED
  // ==========================================
  {
    id: 'all-fixed',
    title: 'Handling blockers',
    text: `Now you know both ways to fix red nodes.
      The key is: <strong style="color: #ef4444">no red</strong> or <strong style="color: #eab308">yellow</strong> nodes must be present for the optimizer to work. <br><br>Other things can stop the optimizer from running, including having duplicate classes or having classes in the wrong spot.`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
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
  // OPTIMIZATION
  // ==========================================
  {
    id: 'ready-to-optimize',
    title: 'Optimization, Part 1',
    text: `Your markers look good! Click <strong>Optimize</strong> to have Autoroad fill in the rest of your schedule.<br><br>
      <small><i>In our current configuration, Autoroad will just try to make sure you have the GIRs by the end of your 4 years. We'll explain how to ask for a degree and more in the next steps.</i></small>`,
    attachTo: { element: '[data-tutorial="optimize-button"]', on: 'bottom' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'See Result', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'optimized',
    title: 'Optimization, Part 1',
    text: `<strong style="color: #d1d5db">White nodes</strong> are the optimizer's suggestions.
      When a marker contains a <strong style="color: #22c55e">green inner ring</strong>, this means the optimizer agreed with the marker you placed.<br><br>
      <small>By default, autoroad can suggest classes even in semesters in the past. We'll show how to handle this later.</small>`,
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
    Right-click on <strong>5.111</strong> → "Convert to marker" gives you a marker node!`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          const markers = useGraphStore.getState().markers;
          if (markers.some(m => m.courseId === '5.111')) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          const markers = useGraphStore.getState().markers;
          if (!markers.some(m => m.courseId === '5.111')) {
            useGraphStore.getState().addMarker('5.111', 0, 'pin');
            const optimizerNodes = useGraphStore.getState().optimizerNodes;
            useGraphStore.setState({
              optimizerNodes: optimizerNodes.filter(n => n.courseId !== '5.111'),
            });
          }
          return this.next();
        },
        secondary: true,
      },
    ],
    beforeShowPromise: () => panToCourse('5.111'),
    when: {
      show: function() {
        const step = this;
        const checkInterval = setInterval(() => {
          const markers = useGraphStore.getState().markers;
          if (markers.some(m => m.courseId === '5.111')) {
            clearInterval(checkInterval);
            const nextBtn = step.el?.querySelector('.shepherd-button:not(.shepherd-button-secondary)') as HTMLButtonElement;
            if (nextBtn) {
              nextBtn.disabled = false;
              nextBtn.classList.remove('shepherd-button-disabled');
            }
          }
        }, 300);
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
  // SCHEDULE PREVIEW
  // ==========================================
  {
    id: 'schedule-preview',
    title: 'Weekly Schedule Preview',
    text: `Hover over a semester header to see your weekly schedule preview.<br><br>
      <strong>Solid blocks</strong>: required class times<br>
      <strong>Outlined blocks</strong>: section options (you pick one)<br>
      <strong>Striped blocks</strong>: time conflicts<br><br>
      The letter in the top right is the block type (Lecture, Recitation, Lab (B), etc). Click the <strong>↗</strong> icon to open in Hydrant.`,
    attachTo: { element: '[data-tutorial="schedule-hover-card"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    //modalOverlayOpeningPadding: 0,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      // Open the hover card first so the element exists
      const openHover = (window as unknown as { openSemesterHoverCard?: (open: boolean) => void }).openSemesterHoverCard;
      if (openHover) openHover(true);
      // Wait for the hover card to render and animate in
      await waitForElement('[data-tutorial="schedule-hover-card"]');
      await new Promise(resolve => setTimeout(resolve, 300));
    },
    when: {
      hide: function() {
        // Close the semester header hover card
        const openHover = (window as unknown as { openSemesterHoverCard?: (open: boolean) => void }).openSemesterHoverCard;
        if (openHover) openHover(false);
      },
    },
  },

  // ==========================================
  // CLEARING
  // ==========================================
  {
    id: 'clear-optimizer',
    title: 'Clearing Results',
    text: `Try clicking <strong>Clear Optimizer</strong> to remove the white suggestion nodes.<br><br>
      Your blue markers will stay. There's also a <strong>Clear Markers</strong> button if you want to remove those too.`,
    attachTo: { element: '[data-tutorial="clear-optimizer-button"]', on: 'bottom' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 8,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          const optimizerNodes = useGraphStore.getState().optimizerNodes;
          if (optimizerNodes.length === 0) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          useGraphStore.setState({ optimizerNodes: [], lastCostBreakdown: null, lastOptimizationStatus: null });
          return this.next();
        },
        secondary: true,
      },
    ],
    when: {
      show: function() {
        const step = this;
        const checkInterval = setInterval(() => {
          const optimizerNodes = useGraphStore.getState().optimizerNodes;
          if (optimizerNodes.length === 0) {
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
  // OBJECTIVES TAB
  // ==========================================
  {
    id: 'objectives-tab',
    title: 'Objectives Tab',
    text: `The <strong>Objectives</strong> tab is where you configure what autoroad optimizes for.<br><br>
      Let's explore its features.`,
    attachTo: { element: '[data-tutorial="sidebar-tabs"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      const objectivesTab = document.querySelector('[data-tab="objectives"]') as HTMLElement;
      if (objectivesTab) {
        objectivesTab.click();
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    },
  },

  {
    id: 'class-year',
    title: 'Class Year',
    text: `Select your graduation year here. This affects which academic year each semester corresponds to, determining what classes are available when.`,
    attachTo: { element: '[data-tutorial="class-year"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'freeze-past',
    title: 'Freeze Past Semesters',
    text: `Try enabling <strong style="color: #ef4444">Freeze Past Semesters</strong> to see what happens!`,
    attachTo: { element: '[data-tutorial="freeze-past"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          const isEnabled = useOptimizationStore.getState().lockPastSemesters;
          if (isEnabled) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          useOptimizationStore.getState().setLockPastSemesters(true);
          return this.next();
        },
        secondary: true,
      },
    ],
    when: {
      show: function() {
        const step = this;
        // Make sure freeze is off when step starts
        useOptimizationStore.getState().setLockPastSemesters(false);

        const unsubscribe = useOptimizationStore.subscribe((state) => {
          if (state.lockPastSemesters) {
            const nextBtn = step.el?.querySelector('.shepherd-button:not(.shepherd-button-secondary)') as HTMLButtonElement;
            if (nextBtn) {
              nextBtn.disabled = false;
              nextBtn.classList.remove('shepherd-button-disabled');
            }
          }
        });
        (step as unknown as { _unsubscribe?: () => void })._unsubscribe = unsubscribe;
      },
      hide: function() {
        const step = this as unknown as { _unsubscribe?: () => void };
        if (step._unsubscribe) {
          step._unsubscribe();
        }
      },
    },
  },

  {
    id: 'freeze-effect',
    title: 'Frozen Semesters',
    text: `See the <strong style="color: #ef4444">red overlay</strong> on past semesters? That overlay represents semesters that have passed <strong style="color: #ef4444">(based on your year)</strong> and means the optimizer will not place any courses there.<br><br>
      For this to work correctly, you <strong style="color: #ef4444">must place the courses you've already taken</strong> in these semesters`,
    attachTo: { element: '[data-tutorial="graph"]', on: 'left' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    when: {
      hide: function() {
        // Auto-disable freeze when leaving this step
        useOptimizationStore.getState().setLockPastSemesters(false);
      },
    },
  },

  {
    id: 'add-degree',
    title: 'Add Requirements & Objectives',
    text: `Use the search bar to add degrees, concentrations, and objectives.<br><br>
      <span id="check-2a">☐</span> <strong>2-A</strong>: a major<br>
      <span id="check-chinese">☐</span> <strong>Chinese</strong>: a concentration<br>
      <span id="check-finals">☐</span> <strong>Limit Finals Per Semester</strong>: an objective`,
    attachTo: { element: '[data-tutorial="parameter-search"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          const state = useOptimizationStore.getState();
          const has2a = state.selectedRequirements.some(r => r.includes('2a') || r.includes('2-A'));
          const hasChinese = state.selectedRequirements.some(r => r.includes('chinese'));
          const hasFinals = state.selectedObjectives.some(o => o.key === 'limit_finals_per_semester');
          if (has2a && hasChinese && hasFinals) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          const store = useOptimizationStore.getState();
          store.addRequirement('major2a');
          store.addRequirement('chinese_concentration');
          const existingObjectives = store.selectedObjectives;
          if (!existingObjectives.some(o => o.key === 'limit_finals_per_semester')) {
            store.setObjectives([...existingObjectives, { key: 'limit_finals_per_semester', parameters: { max_finals: 2 } }]);
          }
          return this.next();
        },
        secondary: true,
      },
    ],
    when: {
      show: function() {
        const step = this;
        const updateCheckboxes = () => {
          const state = useOptimizationStore.getState();
          const has2a = state.selectedRequirements.some(r => r.includes('2a') || r.includes('2-A'));
          const hasChinese = state.selectedRequirements.some(r => r.includes('chinese'));
          const hasFinals = state.selectedObjectives.some(o => o.key === 'limit_finals_per_semester');

          const check2a = document.getElementById('check-2a');
          const checkChinese = document.getElementById('check-chinese');
          const checkFinals = document.getElementById('check-finals');

          if (check2a) check2a.textContent = has2a ? '☑' : '☐';
          if (checkChinese) checkChinese.textContent = hasChinese ? '☑' : '☐';
          if (checkFinals) checkFinals.textContent = hasFinals ? '☑' : '☐';

          const nextBtn = step.el?.querySelector('.shepherd-button:not(.shepherd-button-secondary)') as HTMLButtonElement;
          if (nextBtn) {
            if (has2a && hasChinese && hasFinals) {
              nextBtn.disabled = false;
              nextBtn.classList.remove('shepherd-button-disabled');
            } else {
              nextBtn.disabled = true;
              nextBtn.classList.add('shepherd-button-disabled');
            }
          }
        };

        updateCheckboxes();
        const checkInterval = setInterval(updateCheckboxes, 300);
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

  {
    id: 'beta-mode',
    title: 'Beta Requirements',
    text: `Some degrees have a <strong style="color: #22d3ee">BETA</strong> version. Look for the <strong style="color: #22d3ee">→β</strong> button on 2-A.<br><br>
      <strong style="color: #22d3ee">Beta</strong>: autoroad-updated requirements. Almost always more accurate and override courseroad's vague manual degree requirements<br>
      <strong>Canonical</strong>: official Fireroad version, stable but may be outdated<br><br>
      <small>Beta may have some incorrectness in edge cases. Switch back anytime with <strong>→C</strong>.</small>`,
    attachTo: { element: '[data-requirement-key="major2a"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'objectives',
    title: 'Constraints & Objectives',
    text: `Below your degrees are:<br><br>
      <strong style="color: #a78bfa">Hard Constraints</strong>: must be satisfied. The optimizer will fail if it can't meet these (e.g. blocked time slots).<br><br>
      <strong style="color: #ef4444">Objectives</strong>: <i>soft goals</i> that shape the schedule. The optimizer tries to achieve these, but won't fail if it can't perfectly satisfy them.`,
    attachTo: { element: '[data-tutorial="objective-card"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      const card = await waitForElement('[data-tutorial="objective-card"]');
      if (card) {
        // Click to expand if not already expanded
        const button = card.querySelector('button');
        const chevronRight = card.querySelector('svg.lucide-chevron-right');
        if (button && chevronRight) {
          button.click();
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }
    },
  },

  {
    id: 'tiers',
    title: 'Priority Tiers',
    text: `Objectives are <i>soft</i>, which means they shape what you want via penalty, but don't completely exclude bad options. In order to determine how hard the optimizer should try, we give you <strong>penalty tiers</strong> (⭐ icons) to set your priorities.<br>
      Higher tier = optimizer tries harder<br><br>
      <strong style="color: rgb(239, 68, 68)">Tier 4</strong>: "Must have"<br>
      <strong style="color: rgb(251, 191, 36)">Tier 3</strong>: "This is important"<br>
      <strong style="color: rgb(59, 130, 246)">Tier 2</strong>: "Try to have this"<br>
      <strong style="color: rgb(34, 197, 94)">Tier 1</strong>: "Nice to have"<br><br>

      <small>Under the hood, most penalties are normalized so that for each violation, a cost of 5^tier units are applied, which is necessary because the objective function was defined in terms of units. Some objectives do not follow this pattern, since it could cause costs to balloon in certain cases. The quirks of integer programming and technical debt...</small>
      `
    ,
    attachTo: { element: '[data-tutorial="tier-selector"]', on: 'right-start' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 20,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: function() {
      return waitForElement('[data-tutorial="tier-selector"]');
    },
  },

  // ==========================================
  // IMPORT/EXPORT
  // ==========================================
  {
    id: 'import-export',
    title: 'Import & Export',
    text: `You can save and load your schedule using <strong>.road (Courseroad)</strong> files.<br><br>
      <strong>Import</strong>: Load a schedule from a .road file<br>
      <strong>Export Markers</strong>: Save your blue markers<br>
      <strong>Export Generated</strong>: Save the optimizer's suggestions<br><br>
      <small>Caveat: Must Take markers do not get saved. Sorry!</small>`,
    attachTo: { element: 'header', on: 'bottom' },
    scrollTo: { behavior: 'smooth', block: 'start' },
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
  },

  {
    id: 'support',
    title: 'One Last Thing...',
    text: `Autoroad is a passion project built by one dude. If you found it useful, please consider:<br><br>
      <a href="https://github.com/auriium2/autoroad" target="_blank" rel="noopener noreferrer" style="color: #60a5fa; text-decoration: underline;">Starring the repo on GitHub (i need a job)</a><br>
      <i>Sharing it with friends</i> who might benefit<br>
      Send Feedback <i>(bottom left)</i> if you find bugs<br><br>
      Thank you for using Autoroad!`,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Get Started', action: function() { restoreState(); return this.complete(); } },
    ],
  },
  {
    id: 'finish',
    title: 'You\'re Ready!',
    text: `Click <strong>Tutorial</strong> anytime to revisit.`,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Done!', action: function() { return this.next(); } },
    ],
  },


];

export { restoreState as clearDemoData };
