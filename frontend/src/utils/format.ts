import type { AnalysisResult, Message } from '../types';

export function money(value: number, currency = 'USD'): string {
  return `${currency} ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function breakdownToMarkdown(data: AnalysisResult): string {
  if (!data.service_breakdown.length) return '';
  const rows = data.service_breakdown.map(
    (s) => `| ${s.service} | ${money(s.cost, data.currency)} | ${s.percentage.toFixed(1)}% | ${s.change ? `${s.change > 0 ? '+' : ''}${s.change.toFixed(1)}%` : '-'} |`,
  );
  return ['| Service | Cost | Share | Change |', '|---|---:|---:|---:|', ...rows].join('\n');
}

export function analysisToMarkdown(data: AnalysisResult): string {
  const parts: string[] = [data.summary.trim()];
  const meta: string[] = [];
  if (data.total_cost) meta.push(`**Total:** ${money(data.total_cost, data.currency)}`);
  if (data.period) meta.push(`**Period:** ${data.period}`);
  if (meta.length) parts.push(meta.join(' · '));

  const providers = Object.entries(data.providers ?? {});
  if (providers.length > 1) {
    parts.push(['| Provider | Total |', '|---|---:|', ...providers.map(([n, t]) => `| ${n.toUpperCase()} | ${money(t.total, data.currency)} |`)].join('\n'));
  }
  const table = breakdownToMarkdown(data);
  if (table) parts.push(table);
  if (data.time_series.length) {
    parts.push(['| Date | Cost |', '|---|---:|', ...data.time_series.map((p) => `| ${p.date} | ${money(p.cost, data.currency)} |`)].join('\n'));
  }
  if (data.recommendations.length) {
    parts.push(['**Recommendations**', ...data.recommendations.map((r) => `- ${r}`)].join('\n'));
  }
  return parts.join('\n\n');
}

export function messageToMarkdown(message: Message): string {
  if (message.role === 'system') return `> _${message.content}_`;
  if (message.role === 'user') return `**You:** ${message.content}`;
  const body = message.data ? analysisToMarkdown(message.data) : message.content;
  return `**Shimo:**\n\n${body}`;
}

export function conversationToMarkdown(messages: Message[], title = 'CloudCost Analyzer session'): string {
  const lines = [`# ${title}`, '', `_Exported ${new Date().toLocaleString()}_`, ''];
  for (const message of messages) {
    if (message.loading) continue;
    lines.push(messageToMarkdown(message), '');
  }
  return lines.join('\n').trim();
}
