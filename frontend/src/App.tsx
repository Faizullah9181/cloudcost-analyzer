import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from './types';
import DashboardLayout from './components/DashboardLayout';
import ChatInput from './components/ChatInput';
import MessageList from './components/MessageList';
import { analyzeQuery, fetchSuggestions } from './api/client';

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchSuggestions().then(setSuggestions);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = useCallback(async (query: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    const loadingMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      loading: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setLoading(true);

    try {
      const res = await analyzeQuery(query);

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                loading: false,
                content: res.success && res.data ? res.data.summary : (res.error || 'Analysis failed'),
                data: res.success && res.data ? res.data : undefined,
              }
            : m
        )
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, loading: false, content: 'Failed to connect to the server. Please check your backend is running.' }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-140px)]">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto pb-4 custom-scrollbar">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary-600/10 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-gray-200 mb-2">Cloud Analytics</h2>
              <p className="text-sm text-gray-500 max-w-md">
                Ask questions about your AWS costs in plain English. Get detailed breakdowns,
                trends, and optimization recommendations with interactive charts.
              </p>
            </div>
          ) : (
            <MessageList messages={messages} />
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="pt-4 border-t border-gray-800/50">
          <ChatInput onSubmit={handleSubmit} loading={loading} suggestions={messages.length === 0 ? suggestions : []} />
        </div>
      </div>
    </DashboardLayout>
  );
}
