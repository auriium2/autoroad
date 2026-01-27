import type { StepOptions } from 'shepherd.js';
import { QueryClient } from '@tanstack/react-query';
import { useGraphStore } from '@/stores/roadStore';
import { useOptimizationStore } from '@/stores/optimizationStore';
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
    text: `Courses in a normal state are <strong style="color: #93c5fd">blue</strong>.<br><br>
      Try hovering over this node to see more details.`,
    attachTo: { element: '[data-course-id="18.01"]', on: 'right' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: () => panToCourse('18.01'),
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
    text: `Drag <strong>6.120A</strong> from IAP to Freshman Spring.`,
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
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { loadState(DEMO_MARKERS_WITH_PROBLEMS); return this.back(); }, secondary: true },
      { text: 'Let\'s Add It', action: function() { return this.next(); } },
    ],
    beforeShowPromise: async function() {
      loadState(DEMO_MARKERS_FIXED_SEMESTER);
      await new Promise(resolve => setTimeout(resolve, 400));
      await panToCourse('6.1010');
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
  // OPTIMIZATION
  // ==========================================
  {
    id: 'ready-to-optimize',
    title: 'Ready to Optimize',
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
    title: 'Optimization Complete!',
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
      <strong>Right-click → "Convert to marker"</strong> gives you a marker node!`,
    attachTo: { element: '[data-course-id="5.111"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: () => panToCourse('5.111'),
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
  // RIGHT-CLICK MENU
  // ==========================================
  {
    id: 'right-click',
    title: 'Right-Click Options',
    text: `Right-click any marker for more options:<br><br>
      <strong>Pin</strong>: the normal functionality<br>
      <strong>Override</strong>: ignore prerequisites (for petitions)<br>
      <strong style="color: #ef4444">Banish</strong>: never take this course in this semester`,
    attachTo: { element: '[data-course-id="6.120A"]', on: 'left' },
    scrollTo: false,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      { text: 'Next', action: function() { return this.next(); } },
    ],
    beforeShowPromise: () => panToCourse('6.120A'),
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
    title: 'Class Year & Past Semesters',
    text: `You can select your class year here, which affects what classes are available in which semesters.<br><br>
      Try enabling <strong style="color: #ef4444">Freeze Past Semesters</strong> to see what happens.`,
    attachTo: { element: '[data-tutorial="class-year"]', on: 'right' },
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
    text: `See the <strong style="color: #ef4444">red overlay</strong> on past semesters? That means the optimizer will not place any courses there.<br><br>
      This is useful if you've already completed some semesters and want to plan the remaining ones.`,
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
      <span id="check-63">☐</span> <strong>6-3</strong> (either new or original): a major<br>
      <span id="check-chinese">☐</span> <strong>Chinese</strong>: a concentration<br>
      <span id="check-finals">☐</span> <strong>Minimize Finals Load</strong>: an objective`,
    attachTo: { element: '[data-tutorial="parameter-search"]', on: 'right' },
    scrollTo: { behavior: 'smooth', block: 'center' },
    modalOverlayOpeningPadding: 5000,
    buttons: [
      { text: 'Back', action: function() { return this.back(); }, secondary: true },
      {
        text: 'Next',
        action: function() {
          const state = useOptimizationStore.getState();
          const has63 = state.selectedRequirements.some(r => r.includes('6-3new'));
          const hasChinese = state.selectedRequirements.some(r => r.includes('chinese'));
          const hasFinals = state.selectedObjectives.some(o => o.key === 'minimize_finals_load');
          if (has63 && hasChinese && hasFinals) {
            return this.next();
          }
        },
        disabled: true,
      },
      {
        text: 'Solution',
        action: function() {
          const store = useOptimizationStore.getState();
          store.addRequirement('major6-3new');
          store.addRequirement('chinese_concentration');
          const existingObjectives = store.selectedObjectives;
          if (!existingObjectives.some(o => o.key === 'minimize_finals_load')) {
            store.setObjectives([...existingObjectives, { key: 'minimize_finals_load', parameters: { max_finals: 2 } }]);
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
          const has63 = state.selectedRequirements.some(r => r.includes('6-3'));
          const hasChinese = state.selectedRequirements.some(r => r.includes('chinese'));
          const hasFinals = state.selectedObjectives.some(o => o.key === 'minimize_finals_load');

          const check63 = document.getElementById('check-63');
          const checkChinese = document.getElementById('check-chinese');
          const checkFinals = document.getElementById('check-finals');

          if (check63) check63.textContent = has63 ? '☑' : '☐';
          if (checkChinese) checkChinese.textContent = hasChinese ? '☑' : '☐';
          if (checkFinals) checkFinals.textContent = hasFinals ? '☑' : '☐';

          const nextBtn = step.el?.querySelector('.shepherd-button:not(.shepherd-button-secondary)') as HTMLButtonElement;
          if (nextBtn) {
            if (has63 && hasChinese && hasFinals) {
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
