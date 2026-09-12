import type { Message } from '../types';
import AnalysisCard from './AnalysisCard';
import CopyButton from './CopyButton';
import { messageToMarkdown } from '../utils/format';
import { User, Bot, Wrench, AlertTriangle, Layers, FileText } from 'lucide-react';

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
          <div key={msg.id} className={`group flex gap-3 animate-fade-in ${isUser ? 'justify-end' : ''}`}>
            {!isUser && (
              <div className="brand-gradient w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1 shadow-lg shadow-primary-900/30">
                <Bot className="w-4 h-4 text-white" />
              </div>
            )}

            <div className={`max-w-[88%] min-w-0 ${isUser ? 'order-first' : 'flex-1'}`}>
              {isUser ? (
                <div className="rounded-2xl rounded-tr-md border border-primary-500/30 bg-primary-600/15 px-4 py-3">
                  <p className="text-sm text-slate-100 whitespace-pre-wrap">{msg.content}</p>
                </div>
              ) : msg.loading ? (
                <div className="glass rounded-2xl rounded-tl-md px-4 py-3 flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <span className="typing-dot size-1.5 rounded-full bg-primary-400" />
                    <span className="typing-dot size-1.5 rounded-full bg-primary-400" />
                    <span className="typing-dot size-1.5 rounded-full bg-primary-400" />
                  </span>
                  <span className="text-sm text-slate-400">Shimo is querying your cloud billing data…</span>
                </div>
              ) : msg.error ? (
                <div className="rounded-2xl rounded-tl-md border border-red-800/50 bg-red-950/40 px-4 py-3 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-red-200 whitespace-pre-wrap">{msg.content}</p>
                </div>
              ) : msg.data ? (
                <AnalysisCard data={msg.data} />
              ) : (
                <div className="glass rounded-2xl rounded-tl-md px-4 py-3">
                  <p className="text-sm text-slate-200 whitespace-pre-wrap">{msg.content}</p>
                </div>
              )}

              <div className={`mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-600 ${isUser ? 'justify-end' : ''}`}>
                <span>{msg.timestamp.toLocaleTimeString()}</span>
                {msg.toolCalls?.map((call) => (
                  <span key={call.tool} className="inline-flex items-center gap-1 rounded-full border border-slate-800 px-2 py-0.5 text-slate-500">
                    <Wrench className="w-3 h-3" />
                    {call.tool}{call.calls > 1 ? ` ×${call.calls}` : ''}
                  </span>
                ))}
                {!msg.loading && (
                  <span className="inline-flex gap-1 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                    <CopyButton text={msg.content} title="Copy text" successMessage="Message copied" />
                    {!isUser && msg.data && (
                      <CopyButton
                        text={() => messageToMarkdown(msg)}
                        icon={<FileText className="w-3.5 h-3.5" />}
                        title="Copy as Markdown"
                        successMessage="Markdown copied"
                      />
                    )}
                  </span>
                )}
              </div>
            </div>

            {isUser && (
              <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 mt-1">
                <User className="w-4 h-4 text-slate-300" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
