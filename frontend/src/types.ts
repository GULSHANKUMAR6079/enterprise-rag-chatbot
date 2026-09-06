export interface SourceCitation {
  id: string;
  title: string;
  url?: string;
  category?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: SourceCitation[];
  confidence?: 'grounded' | 'partially_grounded' | 'insufficient_evidence';
  timestamp: string;
  isStreaming?: boolean;
  error?: boolean;
}

export interface ChatApiResponse {
  request_id: string;
  conversation_id: string;
  answer: string;
  sources: SourceCitation[];
  confidence: 'grounded' | 'partially_grounded' | 'insufficient_evidence';
}
