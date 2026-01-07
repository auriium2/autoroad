export interface NodeStyleConfig {
  borderColor: string;
  bgColor: string;
  textColor: string;
  boxShadow: string;
}

export interface NodeStyleProperties {
  section: number;
  userControlled?: boolean;
  disabled?: boolean;
}

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';
