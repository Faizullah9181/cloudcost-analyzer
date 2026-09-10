import type { Message } from '../types';
import AnalysisCard from './AnalysisCard';
import { User, Bot, Loader2, Wrench, AlertTriangle, Layers } from 'lucide-react';

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  return (
    <div className="space-y-6">
      {messages.map((msg) => {
        if (msg.role === 'system') {
          return (
            <div key={msg.id} className="flex items-center gap-3 text-[11px] text-slate-500">
              <div className="flex-1 h-px bg-slate-800" />
              <span className="inline-flex items-center gap-1"><Layers className="w-3 h-3" /> Context compressed</span>
              <div className="flex-1 h-px bg-slate-800" />
            </div>
          );
        }

        const isUser = msg.role === 'user';
        return (
          <div key={msg.id} className={`flex gap-3 animate-fade-in ${isUser ? 'justify-end' : ''}`}>
            {!isUser && (
              <div className="w-8 h-8 rounded-lg bg-primary-600/20 flex items-center justify-center flex-shrink-0 mt-1">
                <Bot className="w-4 h-4 text-primary-400" />
              </div>
            )}

            <div className={`max-w-[85%] min-w-0 ${isUser ? 'order-first' : 'flex-1'}`}>
              {isUser ? (
                <div className="bg-primary-600/20 border border-primary-500/20 rounded-xl px-4 py-3">
                  <p className="text-sm text-gray-200 whitespace-pre-wrap">{msg.content}</p>
                </div>
              ) : msg.loading ? (
                <div className="bg-gray-800/50 rounded-xl px-4 py-3 border border-gray-700/50 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-primary-400" />
                  <span className="text-sm text-gray-400">Analyzing your cloud costs…</span>
                </div>
              ) : msg.error ? (
                <div className="bg-red-950/40 rounded-xl px-4 py-3 border border-red-800/50 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-red-200 whitespace-pre-wrap">{msg.content}</p>
                </div>
              ) : msg.data ? (
                <AnalysisCard data={msg.data} />
              ) : (
                <div className="bg-gray-800/50 rounded-xl px-4 py-3 border border-gray-700/50">
                  <p className="text-sm text-gray-200 whitespace-pre-wrap">{msg.content}</p>
                </div>
              )}

              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-gray-600">
                <span>{msg.timestamp.toLocaleTimeString()}</span>
                {msg.toolCalls?.map((call) => (
                  <span key={call.tool} className="inline-flex items-center gap-1 rounded-full border border-slate-800 px-2 py-0.5 text-slate-500">
                    <Wrench className="w-3 h-3" />
                    {call.tool}{call.calls > 1 ? ` ×${call.calls}` : ''}
                  </span>
                ))}
              </div>
            </div>

            {isUser && (
              <div className="w-8 h-8 rounded-lg bg-gray-700 flex items-center justify-center flex-shrink-0 mt-1">
                <User className="w-4 h-4 text-gray-400" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
