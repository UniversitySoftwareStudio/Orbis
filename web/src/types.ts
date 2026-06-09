export interface ChatSource {
  title: string;
  url: string;
  type?: string;
  category?: string;
  language?: string;
  snippet?: string;
  content?: string;
}

export interface ChatStep {
  message: string;
  detail?: string;
}

export interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  steps?: ChatStep[];
  sources?: ChatSource[];
  running?: boolean;
}
