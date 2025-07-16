import { create } from 'zustand';


// TYPES

export interface GraphClass {
  id: string;
  section: number;
  user_added: boolean;
}

export interface PositionedGraphClass {
  x: number;
  y: number;
  width: number;
  height: number;

  id: string;
  section: number;
  user_added: boolean;
}




// STORES



interface GraphClassStore {
    // Define state types here, for example:
    classes: GraphClass[];

    addClass: (newClass: GraphClass) => void;
}


export const useGraphClassStore = create<GraphClassStore>((set) => ({
    classes: [],
    addClass: (newClass) => set((state) => ({ ...state, classes: [...state.classes, newClass] })),
}));
