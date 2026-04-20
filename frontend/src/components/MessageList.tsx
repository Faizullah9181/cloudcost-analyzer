import type { Message } from '../types';
import AnalysisCard from './AnalysisCard';
import { User, Bot, Loader2 } from 'lucide-react';

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  return (
    <div className="space-y-6">
      {messages.map((msg) => (
        <div key={msg.id} className={`flex gap-3 animate-fade-in ${msg.role === 'user' ? 'justify-end' : ''}`}>
          {msg.role === 'assistant' && (
            <div className="w-8 h-8 rounded-lg bg-primary-600/20 flex items-center justify-center flex-shrink-0 mt-1">
              <Bot className="w-4 h-4 text-primary-400" />
            </div>
          )}

          <div className={`max-w-[85%] ${msg.role === 'user' ? 'order-first' : ''}`}>
            {msg.role === 'user' ? (
              <div className="bg-primary-600/20 border border-primary-500/20 rounded-xl px-4 py-3">
                <p className="text-sm text-gray-200">{msg.content}</p>
              </div>
            ) : msg.loading ? (
              <div className="bg-gray-800/50 rounded-xl px-4 py-3 border border-gray-700/50 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary-400" />
                <span className="text-sm text-gray-400">Analyzing your AWS costs...</span>
              </div>
            ) : msg.data ? (
              <AnalysisCard data={msg.data} />
            ) : (
              <div className="bg-gray-800/50 rounded-xl px-4 py-3 border border-gray-700/50">
                <p className="text-sm text-gray-200 whitespace-pre-wrap">{msg.content}</p>
              </div>
            )}

            <span className="text-[10px] text-gray-600 mt-1 block">
              {msg.timestamp.toLocaleTimeString()}
            </span>
          </div>

          {msg.role === 'user' && (
            <div className="w-8 h-8 rounded-lg bg-gray-700 flex items-center justify-center flex-shrink-0 mt-1">
              <User className="w-4 h-4 text-gray-400" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
